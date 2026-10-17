"""가정값 로더. 단가·비중·가산율·정책 임계값을 data/assumptions.json에서 읽고, 파일이 없거나 잘못되면 DEFAULTS를 쓴다.
실제 견적서를 받으면 이 파일의 값과 version/as_of/status만 바꾸면 된다(과거 견적은 Quote에 기록된 version으로 재현).
VAT(10%)는 법정 세율이라 가정값이 아니라 engine.py의 고정값이다."""
import copy
import json
import os
from pathlib import Path

PATH = Path(os.environ.get("QUOTE_ASSUMPTIONS") or Path(__file__).resolve().parents[1] / "data" / "assumptions.json")

DEFAULTS = {
    "version": "v1", "as_of": "2026-10-17", "status": "가정(공개 정보 없음)",
    "rates": {"PM": 18_000_000, "수석컨설턴트": 15_000_000, "컨설턴트": 11_000_000, "분석가": 7_000_000},   # 월 단가(원)
    "module_weight": {"연구기획": 0.20, "과제수주": 0.20, "연구비관리": 0.35, "성과활용": 0.25},            # 단계 공수 비중
    "deliverable_weight": {"구축 방향": 0.6, "실행 로드맵": 0.4},                                          # 산출물 공수 비중
    "client_scale": {"서울대학교": 1.0, "고려대학교": 0.8, "연세대학교": 0.85, "KAIST": 0.6},               # 규모 계수
    "client_aliases": {"서울대": "서울대학교", "고려대": "고려대학교", "고대": "고려대학교", "연세대": "연세대학교",
                       "연대": "연세대학교", "카이스트": "KAIST", "kaist": "KAIST"},                       # 줄임말 → 정식 명칭
    "baseline": {"weeks": 16, "team": {"PM": 1, "수석컨설턴트": 1, "컨설턴트": 2, "분석가": 2}},
    "onsite_uplift": 0.12, "english_uplift": 0.08, "rush_factor": 0.5,
    "overhead": 0.15, "profit": 0.10, "support_rate_ratio": 0.5,   # 사후 지원 = 컨설턴트 월 단가 × 이 비율 × 개월
    "max_discount_pct": 15.0, "low_margin": 0.05, "extra_warn_pct": 50.0,
    "capacity_low": 0.85, "capacity_high": 1.3,                    # 필요 공수 대비 투입 경고 구간
    "right_size_min": 0.95, "right_size_target": 1.05, "fit_min_capacity": 0.9,
    "fit_weeks": [4, 52, 2],                                       # 예산 맞추기 탐색 기간(주): 시작, 끝, 간격
}


def _validate(cfg: dict) -> None:
    for key in ("rates", "module_weight", "deliverable_weight", "client_scale"):
        if not cfg[key] or any(v <= 0 for v in cfg[key].values()):
            raise ValueError(f"{key}는 비어 있지 않고 모든 값이 양수여야 합니다")
    for key in ("module_weight", "deliverable_weight"):
        if abs(sum(cfg[key].values()) - 1.0) > 0.01:
            raise ValueError(f"{key}의 합이 1이어야 합니다(현재 {sum(cfg[key].values()):.3f})")
    aliases = cfg["client_aliases"]
    if not isinstance(aliases, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v.strip()
                                            for k, v in aliases.items()):
        raise ValueError("client_aliases는 {줄임말: 정식 명칭} 형태의 문자열 사전이어야 합니다")
    base = cfg["baseline"]
    if base["weeks"] < 1 or not base["team"] or any(r not in cfg["rates"] for r in base["team"]):
        raise ValueError("baseline의 기간/팀(역할은 rates에 있어야 함)이 올바르지 않습니다")


def load(path=None) -> dict:
    """DEFAULTS 위에 파일 값을 덮어쓴다. 파일이 없으면 DEFAULTS, 오류가 있으면 DEFAULTS + status에 사유."""
    cfg = copy.deepcopy(DEFAULTS)
    p = Path(path) if path else PATH
    if not p.exists():
        return cfg
    try:
        cfg.update(json.loads(p.read_text(encoding="utf-8")))
        _validate(cfg)
    except (ValueError, KeyError, TypeError) as e:
        cfg = copy.deepcopy(DEFAULTS)
        cfg["status"] = f"기본값 사용(assumptions.json 오류: {str(e)[:80]})"
    return cfg
