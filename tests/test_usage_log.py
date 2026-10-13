import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "starters"))
from common import usage_log  # noqa: E402


def test_cost_sonnet_one_million_each():
    assert usage_log.cost_usd("claude-sonnet-5-5", 1_000_000, 1_000_000) == 12.0


def test_unknown_model_is_unpriced():
    assert usage_log.cost_usd("no-such-model", 10, 10) is None


def test_record_and_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("USAGE_LOG_PATH", str(tmp_path / "u.jsonl"))
    u = SimpleNamespace(input_tokens=1000, output_tokens=500,
                        cache_read_input_tokens=None, cache_creation_input_tokens=0)
    row = usage_log.record("claude-sonnet-5-5", u, tag="t", stop_reason="max_tokens")
    assert row["usd"] == pytest.approx(0.007)  # 1000*$2/1M + 500*$10/1M
    s = usage_log.summary()
    assert s["calls"] == 1 and s["output"] == 500 and s["truncated"] == 1
    assert s["usd"] == pytest.approx(0.007)
