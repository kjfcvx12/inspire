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
    assert abs(total - q.supply) <= 1000 * 12


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
