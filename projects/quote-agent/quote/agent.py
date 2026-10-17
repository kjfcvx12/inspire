"""견적 에이전트. LLM이 도구(get_baseline, calculate_quote)를 골라 호출하고, 금액은 엔진 결과만 쓴다.
안전장치: 반복 6회 한도 · 입력 검증 오류는 모델에 돌려줘 재시도 · API 실패 시 규칙 기반 mock 폴백."""
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import ValidationError

from common import llm
from quote.engine import (BASELINE, CLIENT_SCALE, DELIVERABLE_WEIGHT, MODULE_WEIGHT, RATES, Quote, QuoteRequest,
                          baseline_quote, calculate, diff, fit_to_budget, right_size_team)
from quote import effort, history, planner, scale
from quote.verify import unverified_amounts

MAX_STEPS = 8
MAX_REVISIONS = 2     # 검증이 문제를 찾았을 때 설명을 다시 쓰게 하는 최대 횟수
SYSTEM = f"""당신은 대학 연구행정 컨설팅 용역의 견적 에이전트다. 기준안은 서울대학교 연구행정시스템 PI 용역(가정 단가)이다.
규칙:
- 금액·공수는 반드시 도구 결과만 인용한다. 직접 계산하거나 추정하지 않는다. 금액은 '317,690,000원'처럼 원 단위 전체 숫자로 쓴다(억·만 단위 축약 금지).
- 도구 결과의 내부 필드명(diff_vs_baseline, capacity, required_mm 등)을 답변에 쓰지 말고 '기준안 대비 차이', '필요 공수 대비 투입' 같은 말로 풀어 쓴다.
- 도구 결과에 없는 금액, 반올림하거나 '약·가까이'를 붙인 금액은 쓰지 않는다. 금액 차이는 도구가 준 diff_vs_baseline 값만 쓰고, 예산과의 차이는 금액으로 말하지 말고 '예산을 초과합니다/예산 안입니다'로만 표현한다.
- 요청에 없는 값은 기준안 값을 유지하고, 그렇게 가정한 항목을 답변에 밝힌다.
- 요청에 대학·기간·인원·범위 같은 조건이 거의 없으면 get_baseline만 부르고 끝내지 말고 calculate_quote로 기준안을 계산해 시나리오 표에 나오게 한다. 답변에는 '조건을 알 수 없어 기준안 값으로 가정했다'고 밝히고, 어떤 정보(발주 대학, 기간, 인원, 범위)를 주면 정교해지는지 한 문장으로 묻는다.
- 기간을 개월로 받으면 duration_months에 그대로 넣는다(주 환산은 엔진이 한다).
- 먼저 요청을 그대로 반영한 시나리오 1개를 calculate_quote로 계산한다. 경고(공수 부족/과다, 원가 미만 등)가 있으면 보완 대안을 최대 2개까지 추가 계산한다.
- 범위(단계·산출물·신규 항목)가 기준안과 다르면 인원이 그대로라 금액이 변하지 않을 수 있다(남는 공수로 소화). 이때 항상 right_size_team으로 범위에 맞는 팀의 견적도 계산해 비교하고, 금액이 그대로인 이유를 밝힌다.
- 예산이 주어지면 fit_to_budget으로 예산 안의 안을 찾고, 어떤 범위를 포기했는지 설명한다. 예산은 부가세 포함으로 본다.
- 기준 설계에 없는 단계·산출물 요청은 항목마다 estimate_extra_effort를 불러 받은 effort_pct와 reason을 extra_items에 넣는다. 도구가 실패하면 비슷한 기존 항목에 빗대 직접 추정하고 reason을 쓴다. 답변에서 '추정'이라고 밝힌다.
- 요청의 대학이 '규모 계수가 있는 대학'에 없으면 calculate_quote 전에 estimate_client_scale을 한 번 부르고, 결과의 factor와 rationale을 calculate_quote의 client_scale과 scale_note에 넣는다. 답변에서 그 계수가 'AI 추정'이라고 밝힌다. 도구가 실패하면 계수 없이 계산한다. 표에 있는 대학에는 부르지 않는다.
- 발주처가 정해지면 search_past_quotes를 한 번 불러 비슷한 과거 견적이 있는지 본다. 있으면 답변에 '과거 비슷한 견적 N건(수주 M건) 참고'처럼 건수와 수주 여부만 밝히고, 과거 금액은 쓰지 않는다. 없으면 언급하지 않는다.
- 요청 끝에 '[계획 에이전트의 계획]'이 붙어 있으면 그 계획의 안을 우선 계산하되, 도구 결과가 계획과 다르면 도구 결과를 따른다. 계획은 금액의 근거가 아니다.
- 도구로 반영할 수 없는 요구(예: 출장비, 워크숍 횟수)는 무시하지 말고 답변 끝에 '반영하지 못한 요구: ...'로 적는다.
- 최종 답변은 한국어 6문장 이내: 결론(권장안), 기준안 대비 주요 차이, 경고와 가정.
역할: {list(RATES)} / 단계: {list(MODULE_WEIGHT)} / 산출물: {list(DELIVERABLE_WEIGHT)} / 규모 계수가 있는 대학: {list(CLIENT_SCALE)}"""

ASK_RULE = ("- (되묻기 허용) 요청에 발주 대학·기간·인원이 모두 없어 기준안과 구별되는 견적을 낼 수 없으면, 계산 전에 ask_user를 한 번 불러 가장 중요한 1~2가지를 한 문장으로 묻는다. "
            "이 규칙은 위의 '조건이 거의 없으면 기준안을 계산한다'보다 우선한다. 대학·기간·인원 중 하나라도 있거나, 요청에 '추가 답변'이 있으면 묻지 말고 계산한다. "
            "ask_user를 부른 뒤에는 다른 도구를 부르지 않는다.")

_SCHEMA = QuoteRequest.model_json_schema()
_BUDGET_SCHEMA = {**_SCHEMA, "properties": {**_SCHEMA["properties"], "budget_total": {
    "type": "integer", "description": "예산 상한(원, 부가세 포함)"}}, "required": ["budget_total"]}
TOOLS = [
    {"name": "get_baseline", "description": "서울대 기준안 견적(항목별 금액·총액·필요 공수)을 조회한다.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "calculate_quote", "description": "조건에 맞는 견적을 계산하고 기준안 대비 항목별 차이를 돌려준다. 안 준 값은 기준안 값이 쓰인다.",
     "input_schema": _SCHEMA},
    {"name": "estimate_client_scale", "description": "가정값 표에 없는 대학의 규모 계수를 근거와 함께 추정한다(AI 제안, 확정 아님). 표에 있는 대학에는 쓰지 않는다.",
     "input_schema": {"type": "object", "properties": {
         "client": {"type": "string", "description": "대학 정식 명칭"},
         "scope": {"type": "string", "description": "요청에서 알 수 있는 사업 범위·규모 단서(없으면 빈 문자열)"}},
         "required": ["client"]}},
    {"name": "estimate_extra_effort", "description": "기준 설계에 없는 신규 단계·산출물의 공수 비율(서울대 전체 대비 %)을 기존 항목에 빗대어 추정한다(AI 제안, 확정 아님). 항목마다 한 번씩 부른다.",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "신규 항목 이름"},
         "detail": {"type": "string", "description": "요청에서 알 수 있는 항목 설명(없으면 빈 문자열)"}},
         "required": ["name"]}},
    {"name": "search_past_quotes", "description": "이력 DB에서 비슷한 과거 견적(같은 발주처 우선, 기간·인원이 가까운 순)을 최대 5건 찾는다. 수주 여부와 당시 조건을 참고하는 용도다.",
     "input_schema": {"type": "object", "properties": {
         "client": {"type": "string", "description": "발주 대학 정식 명칭(선택)"},
         "weeks": {"type": "integer", "description": "수행 기간(주, 선택)"},
         "headcount": {"type": "integer", "description": "총 투입 인원(선택)"}}}},
    {"name": "ask_user", "description": "견적에 꼭 필요한 정보가 없을 때 사용자에게 한 문장으로 되묻는다. 부르면 실행이 멈추고 사용자의 답을 받아 처음부터 다시 실행된다.",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string", "description": "사용자에게 할 질문 한 문장"}},
                      "required": ["question"]}},
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
    plan: str = ""                                       # 계획 에이전트가 세운 계획(한 줄 요약, 화면 표시용)
    question: str = ""                                   # 되묻기: 비어 있지 않으면 견적 대신 이 질문을 사용자에게 보여 준다
    revisions: List[str] = field(default_factory=list)  # 설명을 고친 이유(자기 수정 루프 기록)
    review: Optional[dict] = None                        # AI 교차검증 결과(참고용, 금액은 항상 엔진 값)


def _quote_payload(q: Quote) -> dict:
    return {"label": q.request.label, "lines": q.lines, "supply": q.supply, "vat": q.vat, "total": q.total,
            "required_mm": q.required_mm, "staffed_mm": q.staffed_mm, "capacity": q.capacity,
            "warnings": q.warnings, "request": q.request.model_dump()}


def _add(res: AgentResult, q: Quote) -> None:
    if all(q.request.model_dump() != o.request.model_dump() for o in res.quotes):   # 같은 조건 중복 방지
        q.request.label = unique_label(q.request.label, [o.request.label for o in res.quotes])
        res.quotes.append(q)


def unique_label(label: str, existing) -> str:
    """같은 이름의 시나리오가 표 열을 덮어쓰지 않도록 번호를 붙인다('견적', '견적 (2)', ...). '기준안' 이름도 피한다."""
    taken = {*existing, baseline_quote().request.label}
    if label not in taken:
        return label
    n = 2
    while f"{label} ({n})" in taken:
        n += 1
    return f"{label} ({n})"


def _with_diff(q: Quote) -> dict:
    return {**_quote_payload(q), "diff_vs_baseline": diff(baseline_quote(), q)}


def _run_tool(name: str, args: dict, res: AgentResult) -> str:
    if name == "get_baseline":
        return json.dumps(_quote_payload(baseline_quote()), ensure_ascii=False)
    if name == "search_past_quotes":
        def _int(v):
            return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None
        client = str(args.get("client", "")).strip() or None
        rows = history.similar(client, _int(args.get("weeks")), _int(args.get("headcount")))
        keep = ("ts", "label", "client", "weeks", "headcount", "assumptions_version", "outcome", "scale", "extras")
        return json.dumps({"count": len(rows), "quotes": [{k: r[k] for k in keep} for r in rows],
                           "note": "과거 금액은 당시 가정값 기준이라 인용하지 않는다. 건수·수주 여부·조건만 참고로 쓴다."}, ensure_ascii=False)
    if name == "ask_user":
        q = str(args.get("question", "")).strip()[:200]
        if not q:
            return "입력 오류: question이 비었습니다. 질문 한 문장을 쓰세요."
        res.question = q
        return "질문을 사용자에게 전달했습니다. 다른 도구를 부르지 말고 끝내세요."
    if name == "estimate_client_scale":
        client = str(args.get("client", "")).strip()
        if not client or client in CLIENT_SCALE:
            return json.dumps({"error": "가정값 표에 있는 대학이거나 이름이 없습니다. 추정하지 마세요."}, ensure_ascii=False)
        past = history.past_scales(client)
        est = scale.estimate(client, str(args.get("scope", ""))[:300], past=past)
        if est is None:
            return json.dumps({"error": "추정에 실패했습니다. client_scale 없이 calculate_quote를 부르세요."}, ensure_ascii=False)
        return json.dumps({**est, "past_refs": len(past), "note": "AI 추정(확정 아님). calculate_quote의 client_scale·scale_note에 넣으세요."}, ensure_ascii=False)
    if name == "estimate_extra_effort":
        item = str(args.get("name", "")).strip()
        past = history.past_extras(item) if item else []
        est = effort.estimate(item, str(args.get("detail", ""))[:300], past=past) if item else None
        if est is None:
            return json.dumps({"error": "추정에 실패했습니다. 비슷한 기존 항목에 빗대 직접 추정하세요."}, ensure_ascii=False)
        return json.dumps({**est, "past_refs": len(past), "note": "AI 추정(확정 아님). extra_items의 effort_pct·reason에 넣으세요."}, ensure_ascii=False)
    if name in ("calculate_quote", "right_size_team", "fit_to_budget"):
        args = dict(args)
        budget = args.pop("budget_total", None)
        base = BASELINE.model_dump()
        if "duration_months" in args and "weeks" not in args:
            base.pop("weeks")   # 개월로 받았으면 기준안의 주 값이 충돌하지 않게 뺀다
        try:
            req = QuoteRequest(**{**base, **args})
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


def _issues(res: AgentResult, critic) -> List[str]:
    """설명의 문제 목록: 도구 결과에 없는 금액(코드 검사) 먼저, 없으면 critic(AI 검증 등)의 의견. critic 실패는 문제로 보지 않는다."""
    if res.unverified:
        return ["설명에 도구 결과에 없는 금액이 있습니다: " + ", ".join(res.unverified)]
    if critic and res.quotes:
        try:
            return [str(x) for x in critic(res)][:3]
        except Exception:
            return []
    return []


def run(user_text: str, max_steps: int = MAX_STEPS, use_ai: bool = True, critic=None, allow_questions: bool = False, use_planner: bool = False) -> AgentResult:
    """critic(res) -> 문제 목록. 문제가 있으면 에이전트에게 돌려보내 설명을 다시 쓰게 한다(최대 MAX_REVISIONS회, 금액은 엔진 값 그대로)."""
    res = AgentResult(text="")
    if not use_ai:   # 요청 문장을 외부 AI로 보내지 않는 모드(민감한 건)
        return _mock(user_text, res, "AI 해석 사용 안 함")
    ask = allow_questions and "추가 답변" not in user_text      # 한 번 답을 받은 뒤에는 다시 묻지 않는다
    tools = TOOLS if ask else [t for t in TOOLS if t["name"] != "ask_user"]
    system = SYSTEM + chr(10) + ASK_RULE if ask else SYSTEM
    content = user_text
    if use_planner:
        p = planner.plan(user_text)
        if p:
            res.plan = planner.to_text(p)
            res.trace.append("plan: " + res.plan[:140])
            content = user_text + chr(10) * 2 + "[계획 에이전트의 계획(참고, 도구 결과가 우선)] " + res.plan
    messages = [{"role": "user", "content": content}]
    for step in range(1, max_steps + 1):
        try:
            resp = llm.create(messages=messages, system=system, tools=tools, max_tokens=1500, tag="quote-agent")
        except llm.LLMUnavailable as e:
            return _mock(user_text, res, str(e))
        res.steps = step
        calls = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not calls:
            res.text = llm.text_of(resp)
            res.unverified = unverified_amounts(res.text, res.quotes, res.budgets)
            issues = _issues(res, critic)
            if issues and len(res.revisions) < MAX_REVISIONS and step < max_steps:
                res.revisions.append(" / ".join(issues)[:200])
                res.trace.append("revise: " + res.revisions[-1][:120])
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": (
                    "검증에서 다음 문제가 나왔습니다. 도구 결과에 있는 금액과 사실만 써서 최종 답변을 처음부터 다시 쓰세요. "
                    "계산을 새로 하지 말고, 새 도구를 부를 필요도 없습니다.\n- " + "\n- ".join(issues))})
                continue
            return res
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for c in calls:
            out = _run_tool(c.name, dict(c.input), res)
            res.trace.append(f"{c.name}({json.dumps(dict(c.input), ensure_ascii=False)[:160]})")
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out})
        if res.question and not res.quotes:     # 되묻기: 계산 없이 질문만 돌려주고 멈춘다
            res.text = res.question
            return res
        messages.append({"role": "user", "content": results})
    res.text = "(반복 한도 도달) 계산된 시나리오까지만 표시합니다."
    return res


# ---- mock 폴백: API 없이도 데모가 죽지 않게 하는 규칙 기반 파서(정확도 낮음, 화면에 mock 표시) ----
_NEGATION = re.compile(r"{w}\s*(산출물|납품)?\s*(은|는|이|도)?\s*(필요)?\s*(하지\s*)?(없|불필요|아니|아님|제외|안\s|않|미포함|불가)")


def _wants(text: str, word: str) -> bool:
    """키워드가 있고 '비상주'·'상주 없음'·'영문 불필요'처럼 부정되지 않았을 때만 True(규칙 기반 mock 전용)."""
    if word not in text or f"비{word}" in text:
        return False
    return not re.search(_NEGATION.pattern.format(w=re.escape(word)), text)


class MockParseError(ValueError):
    """규칙 기반 해석이 조용히 틀린 값을 내는 대신, 이유를 알리고 멈춘다."""


_ALIASES = {"서울대학교": ("서울대",), "고려대학교": ("고려대", "고대"), "연세대학교": ("연세대", "연대"),
            "KAIST": ("카이스트", "kaist")}
MAX_MOCK_CHARS = 2000   # 이보다 긴 입력은 거부한다(정규식·정수 변환 폭주 방지)


def _mock_request(text: str) -> QuoteRequest:
    if len(text) > MAX_MOCK_CHARS:   # 잘라서 해석하면 뒤쪽 조건을 조용히 놓치므로 거부한다
        raise MockParseError(f"요청이 {MAX_MOCK_CHARS}자를 넘어 규칙 기반으로 해석할 수 없습니다")
    kw: dict = {"label": "요청(mock 해석)"}
    found = [c for c, names in _ALIASES.items() if any(n in text.lower() for n in names)]
    if len(found) > 1:
        raise MockParseError(f"여러 대학({', '.join(found)})이 함께 언급되어 한 번에 하나만 해석할 수 있습니다")
    if found:
        kw["client"] = found[0]
    durations = set()
    for m in re.finditer(r"(-?\d{1,5})\s*(개월|주)", text):
        n = int(m.group(1))
        weeks = round(n * 4.345) if m.group(2) == "개월" else n
        if n < 1 or not 1 <= weeks <= 104:
            raise MockParseError(f"기간 '{m.group(0)}'이 1주~104주(24개월) 범위를 벗어납니다")
        durations.add(weeks)
    if len(durations) > 1:
        raise MockParseError(f"기간이 서로 다르게 여러 번 나옵니다({sorted(durations)}주). 하나만 적어 주세요")
    if durations:
        kw["weeks"] = durations.pop()
    roles: dict = {}
    rest = text   # 긴 역할 이름부터 매칭하고 그 구간을 지운다('컨설턴트'가 '수석컨설턴트' 안에서 또 매칭되지 않게)
    for role in sorted(RATES, key=len, reverse=True):
        pat = rf"{re.escape(role)}\s*(\d{{1,5}})\s*명"
        found_n = [int(m.group(1)) for m in re.finditer(pat, rest)]
        if len(set(found_n)) > 1:
            raise MockParseError(f"'{role}' 인원이 서로 다르게 여러 번 나옵니다({found_n})")
        if found_n:
            roles[role] = found_n[0]
        rest = re.sub(pat, " ", rest)
    if roles and re.search(r"-?\d{1,5}\s*명", rest):
        raise MockParseError("총인원과 역할별 인원이 함께 있습니다. 둘 중 하나만 적어 주세요")
    if roles:
        if any(n > 20 for n in roles.values()) or sum(roles.values()) < 1:
            raise MockParseError(f"역할별 인원 {roles}은 역할당 0~20명, 합계 1명 이상이어야 합니다")
        kw["team"] = {r: n for r, n in roles.items() if n}
    elif m := re.search(r"(-?\d{1,5})\s*명", text):
        n = int(m.group(1))
        if not 1 <= n <= 20:
            raise MockParseError(f"인원 '{m.group(0)}'이 1~20명 범위를 벗어납니다")
        team = {"PM": 1}
        order = ("컨설턴트", "분석가", "수석컨설턴트", "분석가", "컨설턴트")  # 합계가 n과 정확히 같도록 순환 배분
        for i in range(n - 1):
            team[order[i % len(order)]] = team.get(order[i % len(order)], 0) + 1
        kw["team"] = team
    kw["onsite"] = _wants(text, "상주")
    kw["english_deliverables"] = _wants(text, "영문")
    return QuoteRequest(**{**BASELINE.model_dump(), **kw})


def _mock(user_text: str, res: AgentResult, err: str) -> AgentResult:
    try:
        q = calculate(_mock_request(user_text))
    except (MockParseError, ValidationError) as e:
        reason = str(e) if isinstance(e, MockParseError) else "; ".join(x["msg"] for x in e.errors())
        res.mock = True
        res.trace.append("mock: 해석 실패")
        res.text = (f"(mock) 요청을 해석하지 못했습니다: {reason[:150]}. 조건을 다시 적거나 AI 해석을 켜 주세요. "
                    f"원인: {err[:60]}")
        return res
    res.quotes.append(q)
    res.trace.append("mock: 규칙 기반 해석 → calculate_quote")
    d = diff(baseline_quote(), q)
    res.text = (f"(mock) API를 사용할 수 없어 규칙 기반으로 해석했습니다. {q.request.client}, {q.request.weeks}주, "
                f"{sum(q.request.team.values())}명 기준 총액 {q.total:,}원(기준안 대비 {d['합계(VAT 포함)']:+,}원). "
                f"경고: {'; '.join(q.warnings) or '없음'}. 원인: {err[:80]}")
    res.mock = True
    return res
