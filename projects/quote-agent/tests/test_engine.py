import pytest
from pydantic import ValidationError

from quote.engine import BASELINE, QuoteRequest, baseline_quote, calculate, diff


def test_baseline_is_consistent():
    q = baseline_quote()
    assert q.capacity == 1.0 and not q.warnings
    assert q.total == q.supply + q.vat
    assert q.supply == sum(q.lines.values())


def test_korea_univ_cheaper_but_flags_overstaffing():
    q = calculate(QuoteRequest(client="고려대학교", weeks=12, team={"PM": 1, "컨설턴트": 2, "분석가": 1}))
    b = baseline_quote()
    assert q.total < b.total
    assert diff(b, q)["합계(VAT 포함)"] == q.total - b.total


def test_rush_and_understaffed():
    q = calculate(QuoteRequest(weeks=8, team={"PM": 1, "분석가": 1}))
    assert "단기 수행 가산" in q.lines
    assert any("부족" in w for w in q.warnings)


def test_unknown_client_and_discount_cap():
    q = calculate(QuoteRequest(client="한양대학교", discount_pct=40))
    assert any("규모 계수" in w for w in q.warnings) and any("상한" in w for w in q.warnings)
    assert q.lines["협약 할인"] < 0


def test_onsite_english_support_add_lines():
    q = calculate(BASELINE.model_copy(update={"onsite": True, "english_deliverables": True, "support_months": 3}))
    assert {"상주 가산", "영문 산출물 가산", "사후 지원"} <= set(q.lines)
    assert q.total > baseline_quote().total


@pytest.mark.parametrize("bad", [{"weeks": 0}, {"team": {"CEO": 1}}, {"team": {"PM": 0}}, {"modules": []},
                                  {"modules": ["없는모듈"]}, {"discount_pct": -1}])
def test_invalid_requests_rejected(bad):
    with pytest.raises(ValidationError):
        QuoteRequest(**bad)
