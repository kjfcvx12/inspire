"""산식 설명: 화면에 보이는 금액은 Quote의 값과 정확히 같아야 하고, 없는 가산·할인 행은 만들지 않는다."""
from quote.engine import QuoteRequest, baseline_quote, calculate
from quote.explain import explain

ADDONS = ["상주 가산", "영문 산출물 가산", "단기 수행 가산", "사후 지원", "협약 할인"]


def _by_step(rows):
    return {r["단계"]: r for r in rows}


def test_amounts_match_quote_exactly():
    q = calculate(QuoteRequest(client="연세대학교", weeks=12, onsite=True, english_deliverables=True,
                               support_months=2, discount_pct=5))
    rows = _by_step(explain(q))
    for name, amount in q.lines.items():
        assert rows[name]["금액"] == amount, name
    assert rows["공급가액"]["금액"] == q.supply
    assert rows["부가세"]["금액"] == q.vat
    assert [r["금액"] for r in explain(q) if r["단계"].startswith("합계")] == [q.total]


def test_rows_for_absent_addons_are_not_created():
    rows = _by_step(explain(baseline_quote()))
    for name in ADDONS:
        assert name not in rows
    assert {"기본 인건비", "간접경비", "기업이윤", "공급가액", "부가세"} <= set(rows)


def test_total_row_and_version_row():
    q = calculate(QuoteRequest(weeks=10))
    rows = explain(q)
    total_rows = [r for r in rows if r["단계"].startswith("합계")]
    assert len(total_rows) == 1 and total_rows[0]["금액"] == q.total
    assert rows[-1]["금액"] is None and q.assumptions_version in rows[-1]["산식"]
    assert all(isinstance(r["산식"], str) and r["산식"] for r in rows)


def test_rush_and_discount_rows_appear_when_applicable():
    rows = _by_step(explain(calculate(QuoteRequest(weeks=8, discount_pct=10))))
    assert "단기 수행 가산" in rows and "협약 할인" in rows
    assert rows["협약 할인"]["금액"] < 0
