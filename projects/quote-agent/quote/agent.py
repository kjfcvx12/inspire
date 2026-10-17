"""견적 에이전트. LLM이 도구(get_baseline, calculate_quote)를 골라 호출하고, 금액은 엔진 결과만 쓴다.
안전장치: 반복 6회 한도 · 입력 검증 오류는 모델에 돌려줘 재시도 · API 실패 시 규칙 기반 mock 폴백."""
import json
import re
from dataclasses import dataclass, field
from typing import List

from pydantic import ValidationError

from common import llm
from quote.engine import (BASELINE, CLIENT_SCALE, DELIVERABLE_WEIGHT, MODULE_WEIGHT, RATES, Quote, QuoteRequest,
                          baseline_quote, calculate, diff, fit_to_budget, right_size_team)
from quote.verify import unverified_amounts

MAX_STEPS = 8
SYSTEM = f"""당신은 대학 연구행정 컨설팅 용역의 견적 에이전트다. 기준안은 서울대학교 연구행정시스템 PI 용역(가정 단가)이다.
규칙:
- 금액·공수는 반드시 도구 결과만 인용한다. 직접 계산하거나 추정하지 않는다. 금액은 '317,690,000원'처럼 원 단위 전체 숫자로 쓴다(억·만 단위 축약 금지).
- 도구 결과의 내부 필드명(diff_vs_baseline, capacity, required_mm 등)을 답변에 쓰지 말고 '기준안 대비 차이', '필요 공수 대비 투입' 같은 말로 풀어 쓴다.
- 도구 결과에 없는 금액, 반올림하거나 '약·가까이'를 붙인 금액은 쓰지 않는다. 금액 차이는 도구가 준 diff_vs_baseline 값만 쓰고, 예산과의 차이는 금액으로 말하지 말고 '예산을 초과합니다/예산 안입니다'로만 표현한다.
- 요청에 없는 값은 기준안 값을 유지하고, 그렇게 가정한 항목을 답변에 밝힌다.
- 기간을 개월로 받으면 duration_months에 그대로 넣는다(주 환산은 엔진이 한다).
- 먼저 요청을 그대로 반영한 시나리오 1개를 calculate_quote로 계산한다. 경고(공수 부족/과다, 원가 미만 등)가 있으면 보완 대안을 최대 2개까지 추가 계산한다.
- 범위(단계·산출물·신규 항목)가 기준안과 다르면 인원이 그대로라 금액이 변하지 않을 수 있다(남는 공수로 소화). 이때 항상 right_size_team으로 범위에 맞는 팀의 견적도 계산해 비교하고, 금액이 그대로인 이유를 밝힌다.
- 예산이 주어지면 fit_to_budget으로 예산 안의 안을 찾고, 어떤 범위를 포기했는지 설명한다. 예산은 부가세 포함으로 본다.
- 기준 설계에 없는 단계·산출물 요청은 extra_items에 넣고 effort_pct(서울대 전체 공수 대비 %)를 비슷한 기존 항목에 빗대 추정하며 reason을 쓴다. 답변에서 '추정'이라고 밝힌다.
- 도구로 반영할 수 없는 요구(예: 출장비, 워크숍 횟수)는 무시하지 말고 답변 끝에 '반영하지 못한 요구: ...'로 적는다.
- 최종 답변은 한국어 6문장 이내: 결론(권장안), 기준안 대비 주요 차이, 경고와 가정.
역할: {list(RATES)} / 단계: {list(MODULE_WEIGHT)} / 산출물: {list(DELIVERABLE_WEIGHT)} / 규모 계수가 있는 대학: {list(CLIENT_SCALE)}"""

_SCHEMA = QuoteRequest.model_json_schema()
_BUDGET_SCHEMA = {**_SCHEMA, "properties": {**_SCHEMA["properties"], "budget_total": {
    "type": "integer", "description": "예산 상한(원, 부가세 포함)"}}, "required": ["budget_total"]}
TOOLS = [
    {"name": "get_baseline", "description": "서울대 기준안 견적(항목별 금액·총액·필요 공수)을 조회한다.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "calculate_quote", "description": "조건에 맞는 견적을 계산하고 기준안 대비 항목별 차이를 돌려준다. 안 준 값은 기준안 값이 쓰인다.",
     "input_schema": _SCHEMA},
    {"name": "right_size_team", "description": "요청한 범위·기간에 필요한 공수에 맞는 팀 구성을 찾아 그 견적을 돌려준다.",
     "input_schema": _SCHEMA},
    {"name": "fit_to_budget", "description": "예산(부가세 포함) 안에 드는 안을 최대 3개 찾는다. 범위를 최대한 유지하는 안부터 돌려준다.",
     "input_schema": _BUDGET_SCHEMA},
]


@dataclass
class AgentResult:
    text: str
    quotes: List[Quote] = field(default_factory=list)   # 에이전트가 계산한 시나리오(순서대로)
    trace: List[str] = field(default_factory=list)      # 도구 호출 기록(화면·발표용)
    budgets: List[int] = field(default_factory=list)    # 사용자가 준 예산(금액 대조에서 허용)
    unverified: List[str] = field(default_factory=list) # 설명 속 금액 중 엔진 결과에 없는 것
    mock: bool = False
    steps: int = 0


def _quote_payload(q: Quote) -> dict:
    return {"label": q.request.label, "lines": q.lines, "supply": q.supply, "vat": q.vat, "total": q.total,
            "required_mm": q.required_mm, "staffed_mm": q.staffed_mm, "capacity": q.capacity,
            "warnings": q.warnings, "request": q.request.model_dump()}


def _add(res: AgentResult, q: Quote) -> None:
    if all(q.request.model_dump() != o.request.model_dump() for o in res.quotes):   # 같은 조건 중복 방지
        res.quotes.append(q)


def _with_diff(q: Quote) -> dict:
    return {**_quote_payload(q), "diff_vs_baseline": diff(baseline_quote(), q)}


def _run_tool(name: str, args: dict, res: AgentResult) -> str:
    if name == "get_baseline":
        return json.dumps(_quote_payload(baseline_quote()), ensure_ascii=False)
    if name in ("calculate_quote", "right_size_team", "fit_to_budget"):
        args = dict(args)
        budget = args.pop("budget_total", None)
        try:
            req = QuoteRequest(**{**BASELINE.model_dump(), **args})
        except (ValidationError, TypeError) as e:
            return f"입력 오류: {str(e)[:300]}. 값을 고쳐 다시 호출하세요."
        if name == "calculate_quote":
            q = calculate(req)
            _add(res, q)
            return json.dumps(_with_diff(q), ensure_ascii=False)
        if name == "right_size_team":
            q = calculate(right_size_team(req).model_copy(update={"label": f"{req.label}(팀 재설계)"}))
            _add(res, q)
            return json.dumps(_with_diff(q), ensure_ascii=False)
        if not isinstance(budget, int) or budget <= 0:
            return "입력 오류: budget_total(원, 부가세 포함)이 필요합니다."
        res.budgets.append(budget)
        options = fit_to_budget(req, budget)
        for q in options:
            _add(res, q)
        if not options:
            return json.dumps({"options": [], "note": "이 예산으로는 최소 공수 조건(필요 공수의 90%)을 만족하는 안이 없습니다"},
                              ensure_ascii=False)
        return json.dumps({"options": [_with_diff(q) for q in options]}, ensure_ascii=False)
    return f"알 수 없는 도구: {name}"


def run(user_text: str, max_steps: int = MAX_STEPS, use_ai: bool = True) -> AgentResult:
    res = AgentResult(text="")
    if not use_ai:   # 요청 문장을 외부 AI로 보내지 않는 모드(민감한 건)
        return _mock(user_text, res, "AI 해석 사용 안 함")
    messages = [{"role": "user", "content": user_text}]
    for step in range(1, max_steps + 1):
        try:
            resp = llm.create(messages=messages, system=SYSTEM, tools=TOOLS, max_tokens=1500, tag="quote-agent")
        except llm.LLMUnavailable as e:
            return _mock(user_text, res, str(e))
        res.steps = step
        calls = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not calls:
            res.text = llm.text_of(resp)
            res.unverified = unverified_amounts(res.text, res.quotes, res.budgets)
            return res
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for c in calls:
            out = _run_tool(c.name, dict(c.input), res)
            res.trace.append(f"{c.name}({json.dumps(dict(c.input), ensure_ascii=False)[:160]})")
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out})
        messages.append({"role": "user", "content": results})
    res.text = "(반복 한도 도달) 계산된 시나리오까지만 표시합니다."
    return res


# ---- mock 폴백: API 없이도 데모가 죽지 않게 하는 규칙 기반 파서(정확도 낮음, 화면에 mock 표시) ----
def _mock_request(text: str) -> QuoteRequest:
    kw: dict = {"label": "요청(mock 해석)"}
    for name in CLIENT_SCALE:
        if name[:2] in text or name in text:
            kw["client"] = name
    if "고대" in text:
        kw["client"] = "고려대학교"
    if "연대" in text:
        kw["client"] = "연세대학교"
    if m := re.search(r"(\d+)\s*개월", text):
        kw["weeks"] = max(1, round(int(m.group(1)) * 4.345))
    elif m := re.search(r"(\d+)\s*주", text):
        kw["weeks"] = int(m.group(1))
    if m := re.search(r"(\d+)\s*명", text):
        n = max(1, min(20, int(m.group(1))))
        team = {"PM": 1}
        order = ("컨설턴트", "분석가", "수석컨설턴트", "분석가", "컨설턴트")  # 합계가 n과 정확히 같도록 순환 배분
        for i in range(n - 1):
            team[order[i % len(order)]] = team.get(order[i % len(order)], 0) + 1
        kw["team"] = team
    kw["onsite"] = "상주" in text
    kw["english_deliverables"] = "영문" in text
    return QuoteRequest(**{**BASELINE.model_dump(), **kw})


def _mock(user_text: str, res: AgentResult, err: str) -> AgentResult:
    q = calculate(_mock_request(user_text))
    res.quotes.append(q)
    res.trace.append("mock: 규칙 기반 해석 → calculate_quote")
    d = diff(baseline_quote(), q)
    res.text = (f"(mock) API를 사용할 수 없어 규칙 기반으로 해석했습니다. {q.request.client}, {q.request.weeks}주, "
                f"{sum(q.request.team.values())}명 기준 총액 {q.total:,}원(기준안 대비 {d['합계(VAT 포함)']:+,}원). "
                f"경고: {'; '.join(q.warnings) or '없음'}. 원인: {err[:80]}")
    res.mock = True
    return res
