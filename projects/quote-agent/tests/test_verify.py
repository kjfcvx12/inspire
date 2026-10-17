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


def test_abbreviated_amounts_are_checked_within_rounding():
    q = baseline_quote()                      # 합계 353,560,000
    assert unverified_amounts("총액은 3.5억원입니다", [q]) == []            # 반올림 범위 안(±0.05억)
    assert unverified_amounts("총액은 5억원입니다", [q]) == ["5억원"]       # 어떤 금액과도 안 맞음
    assert unverified_amounts("공급가는 32,142만원", [q]) == []             # 321,418,000 ≈ 32,142만
    assert unverified_amounts("차이는 9,999만원", [q]) == ["9,999만원"]
    assert unverified_amounts("예산 2.5억", [], extra=[250_000_000]) == []


def test_budget_headroom_is_known_but_other_numbers_are_not():
    q = calculate(QuoteRequest(weeks=12))
    budget = 400_000_000
    assert unverified_amounts(f"예산이 {budget - q.total:,}원 남습니다", [q], extra=[budget]) == []
    assert unverified_amounts(f"예산이 {budget - q.total + 1:,}원 남습니다", [q], extra=[budget]) != []


def test_integer_eok_and_cheon_man_are_not_waved_through():
    q = baseline_quote()                                                       # 합계 353,560,000
    assert unverified_amounts("총액은 4억원", [q]) == ["4억원"]
    assert unverified_amounts("총액은 3억 9천만원", [q]) == ["3억 9천만원"]
    assert unverified_amounts("총액은 3.5억원", [q]) == []


def test_huge_text_is_fast():
    import time
    t = time.time()
    unverified_amounts("억 " * 300_000 + "1," * 300_000, [baseline_quote()])
    assert time.time() - t < 3
