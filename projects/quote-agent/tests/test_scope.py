"""단계·산출물·신규 항목·원가 하한·팀 재설계·예산 맞추기 (기대값은 구조에서 도출: 공수 = 기준 × 단계 비중합 × 산출물 비중합)."""
import pytest
from pydantic import ValidationError

from quote.engine import (BASELINE, ExtraItem, QuoteRequest, baseline_quote, calculate, fit_to_budget,
                          right_size_team)


def test_dropping_a_deliverable_cuts_required_effort():
    q = calculate(QuoteRequest(deliverables=["구축 방향"]))
    assert q.capacity == pytest.approx(1 / 0.6, abs=0.01)


def test_extra_item_adds_effort_and_shows_in_allocation():
    q = calculate(QuoteRequest(extra_items=[ExtraItem(name="데이터 이관 계획", effort_pct=15, reason="로드맵과 유사")]))
    assert q.capacity == pytest.approx(1 / 1.15, abs=0.01)
    assert "신규: 데이터 이관 계획" in q.allocation


def test_extra_item_limits():
    with pytest.raises(ValidationError):
        ExtraItem(name="x", effort_pct=101)
    q = calculate(QuoteRequest(extra_items=[ExtraItem(name="큰 항목", effort_pct=60)]))
    assert any("50%" in w for w in q.warnings)


def test_allocation_sums_to_supply():
    q = calculate(QuoteRequest(extra_items=[ExtraItem(name="교육", effort_pct=10)]))
    total = sum(v for row in q.allocation.values() for v in row.values())
    assert total == q.supply


def test_selling_below_cost_is_flagged():
    q = calculate(QuoteRequest(discount_pct=15))
    assert any("원가" in w for w in q.warnings)
    assert not any("원가" in w for w in baseline_quote().warnings)


def test_months_converted_by_engine():
    assert QuoteRequest(duration_months=3).weeks == 13


def test_right_size_after_scope_cut():
    req = QuoteRequest(modules=["연구기획", "과제수주", "성과활용"])
    fixed = right_size_team(req)
    q = calculate(fixed)
    assert sum(fixed.team.values()) < sum(BASELINE.team.values())
    assert 0.95 <= q.capacity <= 1.2


def test_fit_to_budget_respects_budget():
    opts = fit_to_budget(QuoteRequest(), 250_000_000)
    assert opts and all(o.total <= 250_000_000 for o in opts)
    assert all(o.capacity >= 0.9 for o in opts)
    assert fit_to_budget(QuoteRequest(), 10_000_000) == []


def test_duplicate_extra_item_names_rejected():
    with pytest.raises(ValidationError):
        QuoteRequest(extra_items=[ExtraItem(name="AI", effort_pct=10), ExtraItem(name="ai", effort_pct=10)])


def test_weeks_and_months_conflict_rejected_but_months_alone_ok():
    with pytest.raises(ValidationError):
        QuoteRequest(weeks=52, duration_months=1)
    assert QuoteRequest(weeks=13, duration_months=3).weeks == 13


@pytest.mark.parametrize("kw", [{}, {"weeks": 8}, {"modules": ["연구기획"]}, {"deliverables": ["구축 방향"]},
                                 {"extra_items": [ExtraItem(name="a", effort_pct=30), ExtraItem(name="b", effort_pct=20)]}])
def test_allocation_always_sums_to_supply(kw):
    q = calculate(QuoteRequest(**kw))
    cells = [v for row in q.allocation.values() for v in row.values()]
    assert sum(cells) == q.supply          # 천 원 반올림 잔차는 마지막 칸에 붙여 합계가 공급가액과 정확히 같다


@pytest.mark.parametrize("given,canonical", [
    ("고대", "고려대학교"), ("연대", "연세대학교"), ("카이스트", "KAIST"), ("kaist", "KAIST"), (" 서울대 ", "서울대학교"),
    ("고려대", "고려대학교"), ("고려대학교", "고려대학교"), ("한양대학교", "한양대학교"),
])
def test_client_aliases_are_normalized_before_calculation(given, canonical):
    assert QuoteRequest(client=given).client == canonical


def test_alias_changes_scale_but_unknown_name_still_warns():
    assert calculate(QuoteRequest(client="고대")).required_mm == calculate(QuoteRequest(client="고려대학교")).required_mm
    assert any("규모 계수" in w for w in calculate(QuoteRequest(client="한양대")).warnings)


def test_aliases_come_from_config():
    import copy

    from quote.assumptions import DEFAULTS
    from quote.engine import apply_assumptions
    cfg = copy.deepcopy(DEFAULTS)
    cfg["client_aliases"] = {**cfg["client_aliases"], "한대": "한양대학교"}
    apply_assumptions(cfg)
    assert QuoteRequest(client="한대").client == "한양대학교"
