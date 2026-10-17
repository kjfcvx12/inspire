import copy
import json

import pytest

from quote import assumptions
from quote.assumptions import DEFAULTS
from quote.assumptions_io import next_version, save_assumptions


def _cfg(**over):
    cfg = copy.deepcopy(DEFAULTS)
    cfg.update(over)
    return cfg


def test_saved_file_round_trips_through_loader(tmp_path):
    p = tmp_path / "a.json"
    cfg = _cfg(version="v2", status="실제(예시 출처)", rates={**DEFAULTS["rates"], "PM": 20_000_000})
    save_assumptions(cfg, p)
    assert assumptions.load(p) == cfg
    assert not list(tmp_path.glob("*.tmp"))                       # 임시 파일이 남지 않는다


@pytest.mark.parametrize("bad", [
    {"module_weight": {"연구기획": 0.5, "과제수주": 0.1}},          # 합이 1이 아님
    {"rates": {"PM": -1, "수석컨설턴트": 1, "컨설턴트": 1, "분석가": 1}},
    {"overhead": 1.5}, {"max_discount_pct": 120}, {"fit_weeks": [4, 2, 2]}, {"capacity_low": 2.0, "capacity_high": 1.0},
])
def test_invalid_config_is_rejected_and_file_untouched(tmp_path, bad):
    p = tmp_path / "a.json"
    save_assumptions(_cfg(), p)
    before = p.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        save_assumptions(_cfg(**bad), p)
    assert p.read_text(encoding="utf-8") == before


def test_missing_keys_rejected(tmp_path):
    cfg = _cfg()
    cfg.pop("profit")
    with pytest.raises(ValueError):
        save_assumptions(cfg, tmp_path / "a.json")


def test_next_version():
    assert next_version("v1") == "v2" and next_version("v9") == "v10" and next_version("초안") == "초안-2"


def test_file_is_valid_json_utf8(tmp_path):
    p = tmp_path / "a.json"
    save_assumptions(_cfg(), p)
    assert json.loads(p.read_text(encoding="utf-8"))["version"] == "v1"
