import copy
import json

from quote import assumptions
from quote.assumptions import DEFAULTS
from quote.engine import ExtraItem, QuoteRequest, apply_assumptions, baseline_quote, calculate


def _cfg(**over):
    cfg = copy.deepcopy(DEFAULTS)
    cfg.update(over)
    return cfg


def test_shipped_file_equals_defaults():
    assert assumptions.load() == DEFAULTS


def test_missing_file_falls_back(tmp_path):
    assert assumptions.load(tmp_path / "none.json") == DEFAULTS


def test_bad_file_falls_back_with_reason(tmp_path):
    bad = tmp_path / "a.json"
    bad.write_text(json.dumps({"module_weight": {"연구기획": 1.0, "과제수주": 1.0}}), encoding="utf-8")
    cfg = assumptions.load(bad)
    assert cfg["rates"] == DEFAULTS["rates"] and cfg["status"].startswith("기본값 사용")


def test_changing_rates_changes_amounts_but_not_structure():
    req = QuoteRequest(client="고려대학교", weeks=8, onsite=True, discount_pct=15)
    before = calculate(req)
    rates = {**DEFAULTS["rates"], "PM": DEFAULTS["rates"]["PM"] * 2}
    apply_assumptions(_cfg(rates=rates, version="v2"))
    after = calculate(req)
    assert after.total > before.total
    assert list(after.lines) == list(before.lines) and after.warnings == before.warnings
    assert (before.assumptions_version, after.assumptions_version) == ("v1", "v2")


def test_capacity_threshold_comes_from_config():
    assert not baseline_quote().warnings
    apply_assumptions(_cfg(capacity_low=1.5))
    assert any("부족" in w for w in baseline_quote().warnings)


def test_extra_warning_text_follows_threshold():
    apply_assumptions(_cfg(extra_warn_pct=20.0))
    q = calculate(QuoteRequest(extra_items=[ExtraItem(name="x", effort_pct=25)]))
    assert any("20%를 넘" in w for w in q.warnings)


def test_support_rate_comes_from_config():
    a = calculate(QuoteRequest(support_months=2)).lines["사후 지원"]
    apply_assumptions(_cfg(support_rate_ratio=1.0))
    assert calculate(QuoteRequest(support_months=2)).lines["사후 지원"] == 2 * a
