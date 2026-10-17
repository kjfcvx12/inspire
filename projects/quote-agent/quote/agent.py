"""견적 에이전트. LLM이 도구(get_baseline, calculate_quote)를 골라 호출하고, 금액은 엔진 결과만 쓴다.
안전장치: 반복 6회 한도 · 입력 검증 오류는 모델에 돌려줘 재시도 · API 실패 시 규칙 기반 mock 폴백."""
import json
import re
from dataclasses import dataclass, field
from typing import List

from pydantic import ValidationError

from common import llm
from quote.engine import (BASELINE, CLIENT_SCALE, MODULE_WEIGHT, RATES, Quote, QuoteRequest, baseline_quote,
                          calculate, diff)

MAX_STEPS = 6
SYSTEM = f"""당신은 대학 연구행정 컨설팅 용역의 견적 에이전트다. 기준안은 서울대학교 연구행정시스템 PI 용역(가정 단가)이다.
규칙:
- 금액·공수는 반드시 calculate_quote 결과만 인용한다. 직접 계산하거나 추정하지 않는다.
- 요청에 없는 값은 기준안 값을 유지하고, 그렇게 가정한 항목을 답변에 밝힌다.
- 먼저 요청을 그대로 반영한 시나리오 1개를 계산한다. 경고(공수 부족/과다 등)가 있으면 보완 대안을 최대 2개까지 추가 계산한다.
- 인원·기간 변경이 금액에 준 영향을 기준안 대비 차이 항목으로 설명한다.
- 최종 답변은 한국어 5문장 이내: 결론(권장안), 기준안 대비 주요 차이, 경고와 가정.
역할: {list(RATES)} / 모듈: {list(MODULE_WEIGHT)} / 규모 계수가 있는 대학: {list(CLIENT_SCALE)}"""

TOOLS = [
    {"name": "get_baseline", "description": "서울대 기준안 견적(항목별 금액·총액·필요 공수)을 조회한다.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "calculate_quote", "description": "조건에 맞는 견적을 계산하고 기준안 대비 항목별 차이를 돌려준다. 안 준 값은 기준안 값이 쓰인다.",
     "input_schema": QuoteRequest.model_json_schema()},
]


@dataclass
class AgentResult:
    text: str
    quotes: List[Quote] = field(default_factory=list)   # 에이전트가 계산한 시나리오(순서대로)
    trace: List[str] = field(default_factory=list)      # 도구 호출 기록(화면·발표용)
    mock: bool = False
    steps: int = 0


def _quote_payload(q: Quote) -> dict:
    return {"label": q.request.label, "lines": q.lines, "supply": q.supply, "vat": q.vat, "total": q.total,
            "required_mm": q.required_mm, "staffed_mm": q.staffed_mm, "capacity": q.capacity,
            "warnings": q.warnings, "request": q.request.model_dump()}


def _run_tool(name: str, args: dict, res: AgentResult) -> str:
    if name == "get_baseline":
        return json.dumps(_quote_payload(baseline_quote()), ensure_ascii=False)
    if name == "calculate_quote":
        try:
            req = QuoteRequest(**{**BASELINE.model_dump(), **args})
        except (ValidationError, TypeError) as e:
            return f"입력 오류: {str(e)[:300]}. 값을 고쳐 다시 호출하세요."
        q = calculate(req)
        res.quotes.append(q)
        return json.dumps({**_quote_payload(q), "diff_vs_baseline": diff(baseline_quote(), q)}, ensure_ascii=False)
    return f"알 수 없는 도구: {name}"


def run(user_text: str, max_steps: int = MAX_STEPS) -> AgentResult:
    res = AgentResult(text="")
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
        team = {"PM": 1} if n >= 1 else {}
        rest = n - 1
        for role, share in (("수석컨설턴트", 0.2), ("컨설턴트", 0.4), ("분석가", 0.4)):
            k = round(rest * share)
            if k:
                team[role] = k
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
