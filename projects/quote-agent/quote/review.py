"""AI 계산·검증 에이전트. 엔진 값을 정답으로 두고, AI가 같은 조건을 독립적으로 계산(계산 에이전트)하고 설명이 숫자와
맞는지 판정(검증 에이전트)한다. 결과는 참고 표시이고 화면의 금액은 항상 엔진 값이다. AI 호출이 실패해도 결과를 막지 않는다.
주의: 계산 에이전트에는 단가와 계산 규칙을 보낸다(엔진의 정답은 보내지 않는다)."""
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from pydantic import BaseModel, Field

from common import structured
from quote import engine
from quote.engine import Quote

TOLERANCE = 0.001        # 총액 차이가 0.1% 이내(또는 1,000원 이내)면 반올림 차이로 보고 '일치'
MAX_TOKENS = 1500


class AiCalc(BaseModel):
    labor: int = Field(..., description="기본 인건비(원)")
    onsite_add: int = Field(0, description="상주 가산(원), 없으면 0")
    english_add: int = Field(0, description="영문 산출물 가산(원), 없으면 0")
    rush_add: int = Field(0, description="단기 수행 가산(원), 없으면 0")
    support_add: int = Field(0, description="사후 지원(원), 없으면 0")
    overhead: int = Field(..., description="간접경비(원)")
    profit: int = Field(..., description="기업이윤(원)")
    discount: int = Field(0, description="협약 할인(원, 할인이 있으면 음수), 없으면 0")
    supply: int = Field(..., description="공급가액(원, 부가세 별도)")
    vat: int = Field(..., description="부가세(원)")
    total: int = Field(..., description="합계(원, 부가세 포함)")


class AiVerdict(BaseModel):
    consistent: bool = Field(..., description="설명 문장이 엔진 결과와 모순되지 않으면 true")
    issues: List[str] = Field(default_factory=list, description="모순이나 근거 없는 주장, 없으면 빈 목록")


class AiRecheck(BaseModel):
    ai_was_wrong: bool = Field(..., description="규칙을 다시 읽어 보니 AI 자신의 계산이 틀렸으면 true, 엔진 계산이 규칙과 다르면 false")
    item: str = Field("", description="두 계산이 가장 크게 갈리는 항목 이름")
    explanation: str = Field(..., description="규칙의 몇 번 줄을 어떻게 읽었는지 한두 문장")


def calc_spec() -> str:
    """계산 에이전트에게 주는 계산 규칙. 현재 가정값에서 만들어 규칙이 바뀌어도 어긋나지 않는다."""
    a = engine._A
    rates = ", ".join(f"{r} {v:,}원" for r, v in engine.RATES.items())
    return (
        f"월 단가: {rates}\n"
        f"계산 규칙(순서대로, 금액은 모두 원 단위):\n"
        f"1. 개월 = 주 ÷ {engine.WEEKS_PER_MONTH}\n"
        f"2. 기본 인건비 = Σ(역할 월 단가 × 인원) × 개월\n"
        f"3. 상주면 상주 가산 = 기본 인건비 × {a['onsite_uplift']:.0%}, 영문 산출물이면 영문 가산 = 기본 인건비 × {a['english_uplift']:.0%}\n"
        f"4. 기준 기간({a['baseline']['weeks']}주)보다 짧으면 단기 가산 = 기본 인건비 × (({a['baseline']['weeks']} − 주) ÷ {a['baseline']['weeks']}) × {a['rush_factor']:g}\n"
        f"5. 사후 지원 개월이 있으면 사후 지원 = 개월수 × 컨설턴트 월 단가 × {a['support_rate_ratio']:g}\n"
        f"6. 직접비 = 기본 인건비 + 위 가산과 사후 지원의 합\n"
        f"7. 간접경비 = 직접비 × {a['overhead']:.0%}, 원가 = 직접비 + 간접경비, 기업이윤 = 원가 × {a['profit']:.0%}\n"
        f"8. 할인이 있으면(상한 {a['max_discount_pct']:g}%) 협약 할인 = −(직접비 + 간접경비 + 기업이윤) × 할인율\n"
        f"9. 각 항목을 천 원 단위로 반올림한 뒤 합해 공급가액을 구한다. 부가세 = 공급가액 × {engine.VAT:.0%}를 천 원 단위로 반올림, "
        f"합계 = 공급가액 + 부가세"
    )


def _cond(q: Quote) -> str:
    r = q.request
    return (f"기간 {r.weeks}주, 인원 {dict(r.team)}, 상주 {'예' if r.onsite else '아니오'}, "
            f"영문 산출물 {'예' if r.english_deliverables else '아니오'}, 사후 지원 {r.support_months}개월, 할인율 {r.discount_pct:g}%")


def _calc_prompt(q: Quote) -> str:
    return f"{calc_spec()}\n\n조건: {_cond(q)}\n\n위 규칙대로 단계별로 신중하게 계산하고 결과 항목만 채워 답하라."


def ai_recompute(q: Quote, ask=structured.ask_structured) -> dict:
    """계산 에이전트: 같은 조건을 AI가 독립적으로 계산하고 엔진 값과 비교한다. 실패하면 '불가'(예외 없음)."""
    out = {"status": "불가", "ai_supply": None, "ai_vat": None, "ai_total": None, "engine_total": q.total, "diff": None}
    try:
        s = ask(_calc_prompt(q), AiCalc, system="당신은 견적 계산 에이전트다. 주어진 규칙으로만 독립적으로 계산한다.",
                tag="review-calc", max_tokens=MAX_TOKENS)
    except Exception as e:           # 네트워크·검증 오류 등: 결과를 막지 않는다
        out["note"] = f"{type(e).__name__}"
        return out
    if s.data is None:
        out["note"] = (s.error or "AI 응답 없음")[:80]
        return out
    d = s.data
    out.update(ai_supply=d.supply, ai_vat=d.vat, ai_total=d.total, diff=d.total - q.total, ai_data=d.model_dump())
    out["status"] = "일치" if abs(out["diff"]) <= max(1000, TOLERANCE * q.total) else "불일치"
    return out


_AI_TO_LINE = {"labor": "기본 인건비", "onsite_add": "상주 가산", "english_add": "영문 산출물 가산", "rush_add": "단기 수행 가산",
               "support_add": "사후 지원", "overhead": "간접경비", "profit": "기업이윤", "discount": "협약 할인"}


def reconcile(q: Quote, calc: dict, ask=structured.ask_structured) -> dict:
    """불일치 조정: AI에게 두 계산의 항목별 값을 나란히 보여 주고 규칙을 다시 읽게 한다. 금액은 바꾸지 않는다(엔진 값 유지).
    결과: 'AI 정정'(AI가 틀림) / '엔진 확인 필요'(규칙상 엔진이 틀렸을 수 있음, 담당자 확인) / '불가'."""
    out = {"verdict": "불가", "item": "", "explanation": ""}
    ai = calc.get("ai_data") or {}
    rows = "\n".join(f"- {name}: 엔진 {q.lines.get(name, 0):,}원 / AI {ai.get(key, 0):,}원" for key, name in _AI_TO_LINE.items())
    rows += f"\n- 합계: 엔진 {q.total:,}원 / AI {calc.get('ai_total', 0):,}원"
    prompt = (f"{calc_spec()}\n\n두 계산이 달라서 규칙을 다시 읽고 어느 쪽이 규칙대로인지 판단해 주세요.\n"
              f"조건: {_cond(q)}\n항목별 비교:\n{rows}")
    try:
        s = ask(prompt, AiRecheck, system="당신은 견적 조정 에이전트다. 규칙 문장만 근거로 어느 계산이 맞는지 판단한다.",
                tag="review-reconcile", max_tokens=800)
    except Exception:
        return out
    if s.data is None:
        return out
    out.update(verdict="AI 정정" if s.data.ai_was_wrong else "엔진 확인 필요", item=s.data.item[:40],
               explanation=s.data.explanation[:200])
    return out


def _facts(quotes: List[Quote]) -> str:
    lines = []
    for q in quotes:
        r = q.request
        lines.append(f"- {r.label}: {r.client} {r.weeks}주 {sum(r.team.values())}명, 공급가액 {q.supply:,}원, 부가세 {q.vat:,}원, "
                     f"합계 {q.total:,}원, 필요 대비 투입 {q.capacity:.0%}, 경고 {q.warnings or '없음'}")
    return "\n".join(lines)


def ai_verify(text: str, quotes: List[Quote], ask=structured.ask_structured) -> dict:
    """검증 에이전트: 설명 문장이 엔진 결과(사실)와 모순되는지 AI가 판정한다. 실패하면 '불가'(예외 없음)."""
    out = {"status": "불가", "issues": []}
    prompt = (f"엔진 결과(사실):\n{_facts(quotes)}\n\n설명 문장:\n{text}\n\n"
              f"설명 문장이 위 사실과 모순되거나 근거 없는 숫자·주장을 하는지 판정하라. 표현이 다르거나 반올림했어도 "
              f"의미가 같으면 모순이 아니다. 문제는 각각 80자 안팎으로 짧게 쓴다.")
    try:
        s = ask(prompt, AiVerdict, system="당신은 견적 검증 에이전트다. 사실과 설명의 모순만 찾는다.",
                tag="review-verify", max_tokens=1200)
    except Exception as e:
        out["note"] = f"{type(e).__name__}"
        return out
    if s.data is None:
        return out
    out["issues"] = list(s.data.issues)
    out["status"] = "일치" if s.data.consistent and not out["issues"] else "의견 있음"
    return out


def run_review(res, ask=structured.ask_structured, verified: Optional[dict] = None) -> Optional[dict]:
    """계산 에이전트와 검증 에이전트를 함께 돌린다(병렬). AI 없이 동작한 결과(mock)나 시나리오 없는 결과에는 하지 않는다."""
    if res.mock or not res.quotes:
        return None
    first = res.quotes[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        calc = pool.submit(ai_recompute, first, ask)
        verify = pool.submit(lambda: verified if verified is not None else ai_verify(res.text, list(res.quotes), ask))
        out = {"calc": calc.result(), "verify": verify.result()}
    if out["calc"]["status"] == "불일치":
        out["calc"]["recheck"] = reconcile(first, out["calc"], ask)
    return out


def describe(rev: Optional[dict]) -> List[str]:
    """화면에 보여 줄 한국어 요약. 항목마다 한 줄(계산 에이전트, 검증 에이전트)."""
    if not rev:
        return []
    c, v = rev["calc"], rev["verify"]
    if c["status"] == "일치":
        lines = [f"AI 계산 에이전트: 규칙만 보고 다시 계산한 합계가 엔진과 일치합니다(차이 {c['diff']:+,}원)."]
    elif c["status"] == "불일치":
        lines = [f"AI 계산 에이전트: 다시 계산한 합계가 엔진과 {c['diff']:+,}원 다릅니다. 화면 금액은 엔진 값입니다."]
        r = c.get("recheck") or {}
        if r.get("verdict") == "AI 정정":
            lines.append(f"조정: 규칙을 다시 읽은 AI가 자기 계산이 틀렸다고 판단했습니다({r['item'] or '항목 미상'}: {r['explanation']}). 엔진 값을 유지합니다.")
        elif r.get("verdict") == "엔진 확인 필요":
            lines.append(f"조정: 규칙상 엔진 쪽이 다를 수 있다는 의견입니다({r['item'] or '항목 미상'}: {r['explanation']}). 담당자가 확인하세요. 화면 금액은 엔진 값입니다.")
        else:
            lines.append("조정: 재확인 응답을 받지 못했습니다. 담당자가 확인하세요.")
    else:
        lines = ["AI 계산 에이전트: 이번에는 응답을 받지 못해 비교하지 못했습니다."]
    if v["status"] == "일치":
        lines.append("AI 검증 에이전트: 설명 문장이 엔진 결과와 모순되지 않습니다.")
    elif v["status"] == "의견 있음":
        lines.append("AI 검증 에이전트 의견: " + " / ".join(v["issues"]))
    else:
        lines.append("AI 검증 에이전트: 이번에는 응답을 받지 못해 판정하지 못했습니다.")
    return lines
