"""견적 엔진. 금액은 LLM이 아니라 이 모듈이 계산한다(재현 가능).
단가·가산율·기준안은 공개 정보가 없어 모두 '가정값'이다(docs/decisions.md 참고)."""
from itertools import product
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

WEEKS_PER_MONTH = 4.345
RATES: Dict[str, int] = {"PM": 18_000_000, "수석컨설턴트": 15_000_000, "컨설턴트": 11_000_000, "분석가": 7_000_000}  # 월 단가(가정)
MODULE_WEIGHT: Dict[str, float] = {"연구기획": 0.20, "과제수주": 0.20, "연구비관리": 0.35, "성과활용": 0.25}  # 단계 공수 비중(가정)
DELIVERABLE_WEIGHT: Dict[str, float] = {"구축 방향": 0.6, "실행 로드맵": 0.4}  # 산출물 공수 비중(가정)
CLIENT_SCALE: Dict[str, float] = {"서울대학교": 1.0, "고려대학교": 0.8, "연세대학교": 0.85, "KAIST": 0.6}  # 규모 계수(가정)
ONSITE_UPLIFT, ENGLISH_UPLIFT, RUSH_FACTOR = 0.12, 0.08, 0.5
OVERHEAD, PROFIT, VAT, MAX_DISCOUNT = 0.15, 0.10, 0.10, 15.0
LOW_MARGIN = 0.05            # 원가 대비 이윤율이 이보다 낮으면 경고
EXTRA_WARN_PCT = 50.0        # 신규 항목 하나가 서울대 전체 공수의 이 비율을 넘으면 경고


class ExtraItem(BaseModel):
    name: str = Field(..., min_length=1, description="기준 설계에 없는 신규 단계/산출물 이름")
    effort_pct: float = Field(..., gt=0, le=100, description="서울대 기준안 전체 공수 대비 추정 비율(%)")
    reason: str = Field("", description="추정 근거(어떤 기존 항목과 비슷한지)")


class QuoteRequest(BaseModel):
    label: str = Field("견적", description="시나리오 이름")
    client: str = Field("서울대학교", description="발주 대학 정식 명칭")
    weeks: int = Field(16, ge=1, le=104, description="수행 기간(주)")
    duration_months: Optional[float] = Field(None, gt=0, le=24, description="기간을 개월로 받았을 때. 주 환산은 엔진이 한다")
    team: Dict[str, int] = Field(default_factory=lambda: {"PM": 1, "수석컨설턴트": 1, "컨설턴트": 2, "분석가": 2},
                                 description="역할별 투입 인원. 역할은 PM/수석컨설턴트/컨설턴트/분석가")
    modules: List[str] = Field(default_factory=lambda: list(MODULE_WEIGHT),
                               description="범위 단계: 연구기획/과제수주/연구비관리/성과활용")
    deliverables: List[str] = Field(default_factory=lambda: list(DELIVERABLE_WEIGHT),
                                    description="산출물: 구축 방향/실행 로드맵")
    extra_items: List[ExtraItem] = Field(default_factory=list, description="기준 설계에 없는 신규 항목(추정 공수)")
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
            raise ValueError(f"단계는 {list(MODULE_WEIGHT)} 중에서 1개 이상이어야 합니다 (잘못된 단계: {bad})")
        return v

    @field_validator("deliverables")
    @classmethod
    def _deliverables(cls, v):
        bad = [d for d in v if d not in DELIVERABLE_WEIGHT]
        if bad or not v:
            raise ValueError(f"산출물은 {list(DELIVERABLE_WEIGHT)} 중에서 1개 이상이어야 합니다 (잘못된 산출물: {bad})")
        return v

    @model_validator(mode="after")
    def _months_to_weeks(self):
        if self.duration_months is not None:
            self.weeks = max(1, min(104, round(self.duration_months * WEEKS_PER_MONTH)))
        return self


BASELINE = QuoteRequest(label="기준안(서울대 PI)")


class Quote(BaseModel):
    request: QuoteRequest
    lines: Dict[str, int]
    allocation: Dict[str, Dict[str, int]]   # 단계(또는 신규 항목) × 산출물별 공급가액 배분
    supply: int
    vat: int
    total: int
    required_mm: float
    staffed_mm: float
    capacity: float
    margin: float                            # 공급가액 / 원가(인건비+간접경비) - 1
    warnings: List[str]


def _round(x: float) -> int:
    return int(round(x / 1000.0)) * 1000


def _mm(team: Dict[str, int], weeks: int) -> float:
    return sum(team.values()) * weeks / WEEKS_PER_MONTH


def _required(req: QuoteRequest) -> float:
    """필요 공수(MM) = 기준 공수 × 규모 × (단계 비중합 × 산출물 비중합 + 신규 항목 비율합)."""
    core = sum(MODULE_WEIGHT[m] for m in set(req.modules)) * sum(DELIVERABLE_WEIGHT[d] for d in set(req.deliverables))
    extra = sum(e.effort_pct for e in req.extra_items) / 100
    return _mm(BASELINE.team, BASELINE.weeks) * CLIENT_SCALE.get(req.client, 1.0) * (core + extra)


def _allocation(req: QuoteRequest, supply: int) -> Dict[str, Dict[str, int]]:
    base = _mm(BASELINE.team, BASELINE.weeks) * CLIENT_SCALE.get(req.client, 1.0)
    required = _required(req)
    out: Dict[str, Dict[str, int]] = {}
    for m in req.modules:
        out[m] = {d: _round(supply * base * MODULE_WEIGHT[m] * DELIVERABLE_WEIGHT[d] / required)
                  for d in req.deliverables}
    for e in req.extra_items:
        out[f"신규: {e.name}"] = {"추정": _round(supply * base * e.effort_pct / 100 / required)}
    return out


def calculate(req: QuoteRequest) -> Quote:
    months = req.weeks / WEEKS_PER_MONTH
    required = _required(req)
    staffed = _mm(req.team, req.weeks)
    capacity = staffed / required
    warnings: List[str] = []
    if req.client not in CLIENT_SCALE:
        warnings.append(f"'{req.client}'은 규모 계수가 없어 1.0으로 가정했습니다")
    if capacity < 0.85:
        warnings.append(f"투입 공수가 필요 공수의 {capacity:.0%}로 부족합니다(일정 지연·품질 리스크)")
    elif capacity > 1.3:
        warnings.append(f"투입 공수가 필요 공수의 {capacity:.0%}로 과다합니다(원가 과다)")
    for e in req.extra_items:
        warnings.append(f"신규 항목 '{e.name}'은 서울대 실적이 없는 추정 공수({e.effort_pct:g}%)입니다")
        if e.effort_pct > EXTRA_WARN_PCT:
            warnings.append(f"신규 항목 '{e.name}'이 기준안 전체 공수의 50%를 넘습니다. 추정이 과한지 검토하세요")
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
    cost = direct + lines["간접경비"]
    lines["기업이윤"] = cost * PROFIT
    gross = sum(lines.values())
    if discount:
        lines["협약 할인"] = -gross * discount
    margin = sum(lines.values()) / cost - 1
    if margin < 0:
        warnings.append(f"공급가액이 원가(인건비+간접경비)보다 {-margin:.1%} 낮습니다. 손실 견적입니다")
    elif margin < LOW_MARGIN:
        warnings.append(f"원가 대비 이윤율이 {margin:.1%}로 낮습니다(권장 {LOW_MARGIN:.0%} 이상)")
    lines = {k: _round(v) for k, v in lines.items()}
    supply = sum(lines.values())
    vat = _round(supply * VAT)
    return Quote(request=req, lines=lines, allocation=_allocation(req, supply), supply=supply, vat=vat,
                 total=supply + vat, required_mm=round(required, 2), staffed_mm=round(staffed, 2),
                 capacity=round(capacity, 3), margin=round(margin, 4), warnings=warnings)


def diff(base: Quote, new: Quote) -> Dict[str, int]:
    """항목별 금액 차이(new - base). 한쪽에만 있는 항목은 0으로 본다. '합계'는 부가세 포함 총액 차이."""
    keys = list(dict.fromkeys([*base.lines, *new.lines]))
    out = {k: new.lines.get(k, 0) - base.lines.get(k, 0) for k in keys}
    out["합계(VAT 포함)"] = new.total - base.total
    return out


def baseline_quote() -> Quote:
    return calculate(BASELINE)


# ---- 에이전트가 쓰는 탐색 도구: 팀 재설계 / 예산 맞추기 (둘 다 결정적 계산) ----
def _team_candidates():
    for chief, cons, ana in product(range(0, 3), range(0, 7), range(0, 7)):
        seniors = chief + cons
        if seniors == 0 or ana > seniors + 1 or (1 + chief + cons + ana >= 5 and chief == 0):
            continue  # 현실적인 구성만: 선임 없이 분석가만 두지 않고, 5명 이상이면 수석이 있어야 한다
        yield {"PM": 1, **{k: v for k, v in (("수석컨설턴트", chief), ("컨설턴트", cons), ("분석가", ana)) if v}}


def right_size_team(req: QuoteRequest, target: float = 1.05) -> QuoteRequest:
    """요청 범위에 필요한 공수에 맞는 팀 구성을 찾는다(같은 기간 기준, 필요 공수 대비 투입이 target에 가장 가깝고 저렴한 것)."""
    need = _required(req)
    best, best_key = None, None
    for team in _team_candidates():
        cap = _mm(team, req.weeks) / need
        if cap < 0.95:
            continue
        key = (round(abs(cap - target), 2), sum(RATES[r] * n for r, n in team.items()))
        if best_key is None or key < best_key:
            best, best_key = team, key
    if best is None:  # 가장 큰 팀으로도 모자라면 최대 구성을 돌려주고 경고는 calculate가 낸다
        best = max(_team_candidates(), key=lambda t: sum(t.values()))
    return req.model_copy(update={"team": best})


def fit_to_budget(req: QuoteRequest, budget_total: int, min_capacity: float = 0.9) -> List[Quote]:
    """예산(VAT 포함) 안에 드는 안을 최대 3개 찾는다. 범위를 최대한 유지하는 안부터, 기간은 요청에 가까운 순."""
    scopes = [(list(req.modules), list(req.deliverables), "범위 유지")]
    for m in req.modules:
        if len(req.modules) > 1:
            scopes.append(([x for x in req.modules if x != m], list(req.deliverables), f"{m} 제외"))
    for d in req.deliverables:
        if len(req.deliverables) > 1:
            scopes.append((list(req.modules), [x for x in req.deliverables if x != d], f"{d} 제외"))
    found = []
    for modules, delivs, tag in scopes:
        best = None
        for weeks in range(4, 53, 2):
            sized = right_size_team(req.model_copy(update={"modules": modules, "deliverables": delivs, "weeks": weeks,
                                                            "duration_months": None}))
            q = calculate(sized.model_copy(update={"label": f"{tag}·{weeks}주·{sum(sized.team.values())}명"}))
            if q.total <= budget_total and q.capacity >= min_capacity:
                key = abs(weeks - req.weeks)
                if best is None or key < best[0]:
                    best = (key, q)
        if best:
            weight = sum(MODULE_WEIGHT[m] for m in modules) * sum(DELIVERABLE_WEIGHT[d] for d in delivs)
            found.append((-weight, best[0], best[1]))
    found.sort(key=lambda t: (t[0], t[1]))
    return [q for _, _, q in found[:3]]
