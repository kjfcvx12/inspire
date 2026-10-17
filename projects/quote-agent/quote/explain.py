"""견적 금액이 어떻게 나왔는지 단계별 산식으로 풀어 쓴다. 금액은 Quote의 값을 그대로 옮기고, 산식 문장만 만든다(읽기 전용)."""
from typing import Dict, List, Optional

from quote import engine
from quote.engine import Quote


def _row(step: str, formula: str, amount: Optional[int]) -> Dict[str, object]:
    return {"단계": step, "산식": formula, "금액": amount}


def explain(q: Quote) -> List[Dict[str, object]]:
    r, a = q.request, engine._A
    months = r.weeks / engine.WEEKS_PER_MONTH
    team = " + ".join(f"{role} {engine.RATES[role]:,}원×{n}명" for role, n in r.team.items() if role in engine.RATES)
    rows = [_row("기본 인건비", f"({team}) × {months:.2f}개월({r.weeks}주 ÷ {engine.WEEKS_PER_MONTH})", q.lines["기본 인건비"])]
    if "상주 가산" in q.lines:
        rows.append(_row("상주 가산", f"인건비 × {a['onsite_uplift']:.0%}", q.lines["상주 가산"]))
    if "영문 산출물 가산" in q.lines:
        rows.append(_row("영문 산출물 가산", f"인건비 × {a['english_uplift']:.0%}", q.lines["영문 산출물 가산"]))
    if "단기 수행 가산" in q.lines:
        rush = (engine.BASELINE.weeks - r.weeks) / engine.BASELINE.weeks
        rows.append(_row("단기 수행 가산",
                         f"인건비 × 기준 {engine.BASELINE.weeks}주 대비 단축률 {rush:.1%} × {a['rush_factor']}", q.lines["단기 수행 가산"]))
    if "사후 지원" in q.lines:
        rows.append(_row("사후 지원",
                         f"컨설턴트 월 단가 {engine.RATES['컨설턴트']:,}원 × {a['support_rate_ratio']} × {r.support_months}개월",
                         q.lines["사후 지원"]))
    rows.append(_row("간접경비", f"(인건비 + 가산) × {a['overhead']:.0%}", q.lines["간접경비"]))
    rows.append(_row("기업이윤", f"(인건비 + 가산 + 간접경비) × {a['profit']:.0%}", q.lines["기업이윤"]))
    if "협약 할인" in q.lines:
        pct = min(r.discount_pct, a["max_discount_pct"])
        rows.append(_row("협약 할인", f"-(할인 전 합계) × {pct:g}%", q.lines["협약 할인"]))
    rows.append(_row("공급가액", "위 항목의 합(항목마다 천 원 단위 반올림)", q.supply))
    rows.append(_row("부가세", f"공급가액 × {engine.VAT:.0%}(법정 세율)", q.vat))
    rows.append(_row("합계(VAT 포함)", "공급가액 + 부가세", q.total))
    rows.append(_row("가정값 버전", f"{q.assumptions_version} ({q.assumptions_as_of}) — 공개 정보가 없는 가정 단가", None))
    return rows
