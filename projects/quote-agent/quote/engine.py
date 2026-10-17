"""견적 엔진. 금액은 LLM이 아니라 이 모듈이 계산한다(재현 가능).
단가·가산율·기준안은 공개 정보가 없어 모두 '가정값'이다(docs/decisions.md 참고)."""
from typing import Dict, List

from pydantic import BaseModel, Field, field_validator

WEEKS_PER_MONTH = 4.345
RATES: Dict[str, int] = {"PM": 18_000_000, "수석컨설턴트": 15_000_000, "컨설턴트": 11_000_000, "분석가": 7_000_000}  # 월 단가(가정)
MODULE_WEIGHT: Dict[str, float] = {"연구기획": 0.20, "과제수주": 0.20, "연구비관리": 0.35, "성과활용": 0.25}  # 공수 비중(가정)
CLIENT_SCALE: Dict[str, float] = {"서울대학교": 1.0, "고려대학교": 0.8, "연세대학교": 0.85, "KAIST": 0.6}  # 규모 계수(가정)
ONSITE_UPLIFT, ENGLISH_UPLIFT, RUSH_FACTOR = 0.12, 0.08, 0.5
OVERHEAD, PROFIT, VAT, MAX_DISCOUNT = 0.15, 0.10, 0.10, 15.0


class QuoteRequest(BaseModel):
    label: str = Field("견적", description="시나리오 이름")
    client: str = Field("서울대학교", description="발주 대학 정식 명칭")
    weeks: int = Field(16, ge=1, le=104, description="수행 기간(주)")
    team: Dict[str, int] = Field(default_factory=lambda: {"PM": 1, "수석컨설턴트": 1, "컨설턴트": 2, "분석가": 2},
                                 description="역할별 투입 인원. 역할은 PM/수석컨설턴트/컨설턴트/분석가")
    modules: List[str] = Field(default_factory=lambda: list(MODULE_WEIGHT),
                               description="범위 모듈: 연구기획/과제수주/연구비관리/성과활용")
    onsite: bool = Field(False, description="발주처 상주 여부")
    english_deliverables: bool = Field(False, description="영문 산출물 포함 여부")
    support_months: int = Field(0, ge=0, le=24, description="종료 후 사후 지원 개월 수")
    discount_pct: float = Field(0.0, ge=0, description="협약 할인율(%)")

    @field_validator("team")
    @classmethod
    def _team(cls, v):
        bad = [k for k in v if k not in RATES]
        if bad or any(n < 0 or n > 20 for n in v.values()) or sum(v.values()) < 1:
            raise ValueError(f"역할은 {list(RATES)} 중에서, 인원은 0~20, 합계 1명 이상이어야 합니다 (잘못된 역할: {bad})")
        return v

    @field_validator("modules")
    @classmethod
    def _modules(cls, v):
        bad = [m for m in v if m not in MODULE_WEIGHT]
        if bad or not v:
            raise ValueError(f"모듈은 {list(MODULE_WEIGHT)} 중에서 1개 이상이어야 합니다 (잘못된 모듈: {bad})")
        return v


BASELINE = QuoteRequest(label="기준안(서울대 PI)")


class Quote(BaseModel):
    request: QuoteRequest
    lines: Dict[str, int]
    supply: int
    vat: int
    total: int
    required_mm: float
    staffed_mm: float
    capacity: float
    warnings: List[str]


def _round(x: float) -> int:
    return int(round(x / 1000.0)) * 1000


def _mm(req: QuoteRequest) -> float:
    return sum(req.team.values()) * req.weeks / WEEKS_PER_MONTH


def calculate(req: QuoteRequest) -> Quote:
    months = req.weeks / WEEKS_PER_MONTH
    base_mm = _mm(BASELINE)
    scale = CLIENT_SCALE.get(req.client, 1.0)
    required = base_mm * sum(MODULE_WEIGHT[m] for m in set(req.modules)) * scale
    staffed = _mm(req)
    capacity = staffed / required
    warnings: List[str] = []
    if req.client not in CLIENT_SCALE:
        warnings.append(f"'{req.client}'은 규모 계수가 없어 1.0으로 가정했습니다")
    if capacity < 0.85:
        warnings.append(f"투입 공수가 필요 공수의 {capacity:.0%}로 부족합니다(일정 지연·품질 리스크)")
    elif capacity > 1.3:
        warnings.append(f"투입 공수가 필요 공수의 {capacity:.0%}로 과다합니다(원가 과다)")
    if req.discount_pct > MAX_DISCOUNT:
        warnings.append(f"할인율 {req.discount_pct:g}%는 상한 {MAX_DISCOUNT:g}%로 제한했습니다")
    discount = min(req.discount_pct, MAX_DISCOUNT) / 100

    labor = sum(RATES[r] * n * months for r, n in req.team.items())
    lines = {"기본 인건비": labor}
    if req.onsite:
        lines["상주 가산"] = labor * ONSITE_UPLIFT
    if req.english_deliverables:
        lines["영문 산출물 가산"] = labor * ENGLISH_UPLIFT
    rush = max(0.0, (BASELINE.weeks - req.weeks) / BASELINE.weeks)
    if rush:
        lines["단기 수행 가산"] = labor * rush * RUSH_FACTOR
    if req.support_months:
        lines["사후 지원"] = req.support_months * RATES["컨설턴트"] * 0.5
    direct = sum(lines.values())
    lines["간접경비"] = direct * OVERHEAD
    lines["기업이윤"] = (direct + lines["간접경비"]) * PROFIT
    gross = sum(lines.values())
    if discount:
        lines["협약 할인"] = -gross * discount
    lines = {k: _round(v) for k, v in lines.items()}
    supply = sum(lines.values())
    vat = _round(supply * VAT)
    return Quote(request=req, lines=lines, supply=supply, vat=vat, total=supply + vat,
                 required_mm=round(required, 2), staffed_mm=round(staffed, 2), capacity=round(capacity, 3),
                 warnings=warnings)


def diff(base: Quote, new: Quote) -> Dict[str, int]:
    """항목별 금액 차이(new - base). 한쪽에만 있는 항목은 0으로 본다. '합계'는 부가세 포함 총액 차이."""
    keys = list(dict.fromkeys([*base.lines, *new.lines]))
    out = {k: new.lines.get(k, 0) - base.lines.get(k, 0) for k in keys}
    out["합계(VAT 포함)"] = new.total - base.total
    return out


def baseline_quote() -> Quote:
    return calculate(BASELINE)
