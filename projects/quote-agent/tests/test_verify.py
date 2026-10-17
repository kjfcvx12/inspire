from quote.engine import QuoteRequest, baseline_quote, calculate
from quote.verify import unverified_amounts


def test_engine_amounts_pass_and_invented_ones_are_flagged():
    q = calculate(QuoteRequest(client="고려대학교", weeks=12))
    ok = f"총액은 {q.total:,}원이고 공급가액은 {q.supply}원입니다. 기준안은 {baseline_quote().total:,}원입니다."
    assert unverified_amounts(ok, [q]) == []
    fake = f"총액은 {q.total + 123_000:,}원입니다. 기간은 12주, 2026년, 5명입니다."
    assert unverified_amounts(fake, [q]) == [f"{q.total + 123_000:,}"]


def test_difference_between_scenarios_is_known():
    a, b = calculate(QuoteRequest(weeks=12)), calculate(QuoteRequest(weeks=20))
    assert unverified_amounts(f"두 안은 {abs(a.total - b.total):,}원 차이", [a, b]) == []


def test_budget_given_by_user_is_known():
    assert unverified_amounts("예산 250,000,000원", [], extra=[250_000_000]) == []


def test_budget_headroom_is_known_but_other_numbers_are_not():
    q = calculate(QuoteRequest(weeks=12))
    budget = 400_000_000
    assert unverified_amounts(f"예산이 {budget - q.total:,}원 남습니다", [q], extra=[budget]) == []
    assert unverified_amounts(f"예산이 {budget - q.total + 1:,}원 남습니다", [q], extra=[budget]) != []
