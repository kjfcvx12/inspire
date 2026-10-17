"""가정값 저장. 화면에서 고친 값을 검증한 뒤 data/assumptions.json에 안전하게(임시 파일 → 교체) 쓴다.
검증에 실패하면 파일은 그대로다. 저장 후 실행 중인 엔진에 반영하는 것은 호출자가 engine.apply_assumptions로 한다."""
import json
import os
import re
from pathlib import Path

from quote import assumptions


def next_version(version: str) -> str:
    """'v1' → 'v2'. 'v숫자' 형식이 아니면 '-2'를 붙인다."""
    m = re.fullmatch(r"v(\d+)", str(version).strip())
    return f"v{int(m.group(1)) + 1}" if m else f"{version}-2"


def _check(cfg: dict) -> None:
    missing = sorted(set(assumptions.DEFAULTS) - set(cfg))
    if missing:
        raise ValueError(f"가정값에 빠진 항목이 있습니다: {missing}")
    try:
        assumptions._validate(cfg)
    except (KeyError, TypeError) as e:
        raise ValueError(f"가정값 형식이 올바르지 않습니다: {e}") from e
    for key in ("overhead", "profit", "onsite_uplift", "english_uplift", "low_margin", "support_rate_ratio"):
        if not 0 <= cfg[key] <= 1:
            raise ValueError(f"{key}는 0~1 사이여야 합니다(현재 {cfg[key]})")
    if not 0 <= cfg["max_discount_pct"] <= 100:
        raise ValueError("max_discount_pct는 0~100 사이여야 합니다")
    if not 0 < cfg["capacity_low"] < cfg["capacity_high"]:
        raise ValueError("capacity_low는 0보다 크고 capacity_high보다 작아야 합니다")
    first, last, step = cfg["fit_weeks"]
    if not (1 <= first <= last <= 104 and step >= 1):
        raise ValueError("fit_weeks는 [시작, 끝, 간격]이고 1 ≤ 시작 ≤ 끝 ≤ 104, 간격 ≥ 1이어야 합니다")


def save_assumptions(cfg: dict, path=None) -> None:
    """검증 후 원자적으로 저장한다. 잘못된 값이면 ValueError이고 기존 파일은 바뀌지 않는다."""
    _check(cfg)
    p = Path(path) if path else assumptions.PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, p)
