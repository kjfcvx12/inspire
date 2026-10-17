"""견적 엔진. 금액은 LLM이 아니라 이 모듈이 계산한다(재현 가능).
단가·가산율·기준안은 공개 정보가 없어 모두 '가정값'이다(docs/decisions.md 참고)."""
from itertools import product
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from quote import assumptions

WEEKS_PER_MONTH = 4.345   # 365/12/7 근사: 환산 규칙(가정값 아님)
VAT = 0.10                # 법정 세율(가정값 아님)

# 가정값은 data/assumptions.json에서 읽는다. 아래 dict들은 apply_assumptions가 제자리에서 갱신하므로 import한 쪽도 최신 값을 본다.
_A: dict = assumptions.load()
RATES: Dict[str, int] = dict(_A["rates"])
MODULE_WEIGHT: Dict[str, float] = dict(_A["module_weight"])
DELIVERABLE_WEIGHT: Dict[str, float] = dict(_A["deliverable_weight"])
CLIENT_SCALE: Dict[str, float] = dict(_A["client_scale"])


class ExtraItem(BaseModel):
    name: str = Field(..., min_length=1, description="기준 설계에 없는 신규 단계/산출물 이름")
    effort_pct: float = Field(..., gt=0, le=100, description="서울대 기준안 전체 공수 대비 추정 비율(%)")
    reason: str = Field("", description="추정 근거(어떤 기존 항목과 비슷한지)")


class QuoteRequest(BaseModel):
    label: str = Field("견적", description="시나리오 이름")
    client: str = Field("서울대학교", description="발주 대학 정식 명칭")
    weeks: int = Field(default_factory=lambda: _A["baseline"]["weeks"], ge=1, le=104, description="수행 기간(주)")
    duration_months: Optional[float] = Field(None, gt=0, le=24, description="기간을 개월로 받았을 때. 주 환산은 엔진이 한다")
    team: Dict[str, int] = Field(default_factory=lambda: dict(_A["baseline"]["team"]),
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

    @field_validator("extra_items")
    @classmethod
    def _extras_unique(cls, v):
        names = [e.name.strip().casefold() for e in v]
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            raise ValueError(f"신규 항목 이름이 중복됩니다: {dup}. 하나로 합치거나 이름을 구분하세요")
        return v

    @model_validator(mode="after")
    def _months_to_weeks(self):
        if self.duration_months is not None:
            weeks = max(1, min(104, round(self.duration_months * WEEKS_PER_MONTH)))
            if "weeks" in self.model_fields_set and abs(self.weeks - weeks) > 1:
                raise ValueError(f"weeks({self.weeks})와 duration_months({self.duration_months:g}개월={weeks}주)가 충돌합니다. 하나만 주세요")
            self.weeks = weeks
        return self


BASELINE = QuoteRequest(label="기준안(서울대 PI)")


def apply_assumptions(cfg: dict) -> None:
    """가정값을 교체한다(제자리 갱신). 단가가 바뀌어도 Quote에 version이 남아 과거 견적을 구분할 수 있다."""
    global _A
    _A = cfg
    for target, key in ((RATES, "rates"), (MODULE_WEIGHT, "module_weight"), (DELIVERABLE_WEIGHT, "deliverable_weight"),
                        (CLIENT_SCALE, "client_scale")):
        target.clear()
        target.update(cfg[key])
    BASELINE.weeks = cfg["baseline"]["weeks"]
    BASELINE.team = dict(cfg["baseline"]["team"])
    BASELINE.modules = list(cfg["module_weight"])
    BASELINE.deliverables = list(cfg["deliverable_weight"])


def assumption_label() -> str:
    """화면·견적서 표기용: '단가 기준 v1 · 2026-10-17 · 가정(공개 정보 없음)'."""
    return f"단가 기준 {_A['version']} · {_A['as_of']} · {_A['status']}"


def assumption_text() -> str:
    """사이드바용 요약. 값이 파일에서 바뀌어도 화면 문구가 어긋나지 않도록 설정에서 만든다."""
    a, team = _A, _A["baseline"]["team"]
    return (f"간접경비 {a['overhead']:.0%} · 이윤 {a['profit']:.0%} · VAT {VAT:.0%}(법정) · 상주 +{a['onsite_uplift']:.0%} · "
            f"영문 +{a['english_uplift']:.0%} · 단기 가산 계수 {a['rush_factor']:g} · 사후 지원 컨설턴트 단가의 {a['support_rate_ratio']:.0%}/월 · "
            f"할인 상한 {a['max_discount_pct']:g}%. 기준안 {a['baseline']['weeks']}주, "
            + "·".join(f"{r}{n}" for r, n in team.items()))


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
    assumptions_version: str = ""            # 이 견적을 계산한 가정값 버전(과거 견적 재현용)
    assumptions_as_of: str = ""


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
    last = out[list(out)[-1]]                      # 천 원 반올림 잔차를 마지막 칸에 붙여 합계가 공급가액과 정확히 같게 한다
    key = list(last)[-1]
    last[key] += supply - sum(v for row in out.values() for v in row.values())
    return out


def calculate(req: QuoteRequest) -> Quote:
    months = req.weeks / WEEKS_PER_MONTH
    required = _required(req)
    staffed = _mm(req.team, req.weeks)
    capacity = staffed / required
    warnings: List[str] = []
    if req.client not in CLIENT_SCALE:
        warnings.append(f"'{req.client}'은 규모 계수가 없어 1.0으로 가정했습니다")
    if capacity < _A["capacity_low"]:
        warnings.append(f"투입 공수가 필요 공수의 {capacity:.0%}로 부족합니다(일정 지연·품질 리스크)")
    elif capacity > _A["capacity_high"]:
        warnings.append(f"투입 공수가 필요 공수의 {capacity:.0%}로 과다합니다(원가 과다)")
    for e in req.extra_items:
        warnings.append(f"신규 항목 '{e.name}'은 서울대 실적이 없는 추정 공수({e.effort_pct:g}%)입니다")
        if e.effort_pct > _A["extra_warn_pct"]:
            warnings.append(f"신규 항목 '{e.name}'이 기준안 전체 공수의 {_A['extra_warn_pct']:g}%를 넘습니다. 추정이 과한지 검토하세요")
    max_discount = _A["max_discount_pct"]
    if req.discount_pct > max_discount:
        warnings.append(f"할인율 {req.discount_pct:g}%는 상한 {max_discount:g}%로 제한했습니다")
    discount = min(req.discount_pct, max_discount) / 100

    labor = sum(RATES[r] * n * months for r, n in req.team.items())
    lines = {"기본 인건비": labor}
    if req.onsite:
        lines["상주 가산"] = labor * _A["onsite_uplift"]
    if req.english_deliverables:
        lines["영문 산출물 가산"] = labor * _A["english_uplift"]
    rush = max(0.0, (BASELINE.weeks - req.weeks) / BASELINE.weeks)
    if rush:
        lines["단기 수행 가산"] = labor * rush * _A["rush_factor"]
    if req.support_months:
        lines["사후 지원"] = req.support_months * RATES["컨설턴트"] * _A["support_rate_ratio"]
    direct = sum(lines.values())
    lines["간접경비"] = direct * _A["overhead"]
    cost = direct + lines["간접경비"]
    lines["기업이윤"] = cost * _A["profit"]
    gross = sum(lines.values())
    if discount:
        lines["협약 할인"] = -gross * discount
    margin = sum(lines.values()) / cost - 1
    if margin < 0:
        warnings.append(f"공급가액이 원가(인건비+간접경비)보다 {-margin:.1%} 낮습니다. 손실 견적입니다")
    elif margin < _A["low_margin"]:
        warnings.append(f"원가 대비 이윤율이 {margin:.1%}로 낮습니다(권장 {_A['low_margin']:.0%} 이상)")
    lines = {k: _round(v) for k, v in lines.items()}
    supply = sum(lines.values())
    vat = _round(supply * VAT)
    return Quote(request=req, lines=lines, allocation=_allocation(req, supply), supply=supply, vat=vat,
                 total=supply + vat, required_mm=round(required, 2), staffed_mm=round(staffed, 2),
                 capacity=round(capacity, 3), margin=round(margin, 4), warnings=warnings,
                 assumptions_version=_A["version"], assumptions_as_of=_A["as_of"])


def diff(base: Quote, new: Quote) -> Dict[str, int]:
    """항목별 금액 차이(new - base). 한쪽에만 있는 항목은 0으로 본다. '합계'는 부가세 포함 총액 차이."""
    keys = list(dict.fromkeys([*base.lines, *new.lines]))
    out = {k: new.lines.get(k, 0) - base.lines.get(k, 0) for k in keys}
    out["합계(VAT 포함)"] = new.total - base.total
    return out


def baseline_quote() -> Quote:
    return calculate(BASELINE)


def sensitivity(req: QuoteRequest, week_step: int = 2) -> List[Dict[str, object]]:
    """조건을 하나씩만 바꿨을 때 총액이 얼마나 변하는지(협상 자료). 인원은 역할별 ±1명, 기간은 ±week_step주.
    마지막 한 명이나 1주 미만으로 줄이는 변경은 만들지 않는다. 모든 숫자는 calculate 결과다."""
    base = calculate(req)
    variants = []
    for role in RATES:
        have = req.team.get(role, 0)
        for d in (1, -1):
            team = {**req.team, role: have + d}
            if have + d < 0 or have + d > 20 or sum(team.values()) < 1:
                continue
            variants.append((f"{role} {d:+d}명", {"team": {r: n for r, n in team.items() if n}}))
    for d in (week_step, -week_step):
        if 1 <= req.weeks + d <= 104:
            variants.append((f"기간 {d:+d}주", {"weeks": req.weeks + d, "duration_months": None}))
    rows = []
    for name, update in variants:
        q = calculate(req.model_copy(update=update))
        rows.append({"변경": name, "총액(VAT 포함)": q.total, "차이(VAT 포함)": q.total - base.total,
                     "필요 대비 투입(%)": round(q.capacity * 100), "경고 수": len(q.warnings)})
    return rows


# ---- 에이전트가 쓰는 탐색 도구: 팀 재설계 / 예산 맞추기 (둘 다 결정적 계산) ----
def _team_candidates():
    for chief, cons, ana in product(range(0, 3), range(0, 7), range(0, 7)):
        seniors = chief + cons
        if seniors == 0 or ana > seniors + 1 or (1 + chief + cons + ana >= 5 and chief == 0):
            continue  # 현실적인 구성만: 선임 없이 분석가만 두지 않고, 5명 이상이면 수석이 있어야 한다
        yield {"PM": 1, **{k: v for k, v in (("수석컨설턴트", chief), ("컨설턴트", cons), ("분석가", ana)) if v}}


def right_size_team(req: QuoteRequest, target: Optional[float] = None) -> QuoteRequest:
    """요청 범위에 필요한 공수에 맞는 팀 구성을 찾는다(같은 기간 기준, 필요 공수 대비 투입이 target에 가장 가깝고 저렴한 것)."""
    target = _A["right_size_target"] if target is None else target
    need = _required(req)
    best, best_key = None, None
    for team in _team_candidates():
        cap = _mm(team, req.weeks) / need
        if cap < _A["right_size_min"]:
            continue
        key = (round(abs(cap - target), 2), sum(RATES[r] * n for r, n in team.items()))
        if best_key is None or key < best_key:
            best, best_key = team, key
    if best is None:  # 가장 큰 팀으로도 모자라면 최대 구성을 돌려주고 경고는 calculate가 낸다
        best = max(_team_candidates(), key=lambda t: sum(t.values()))
    return req.model_copy(update={"team": best})


def fit_to_budget(req: QuoteRequest, budget_total: int, min_capacity: Optional[float] = None) -> List[Quote]:
    """예산(VAT 포함) 안에 드는 안을 최대 3개 찾는다. 범위를 최대한 유지하는 안부터, 기간은 요청에 가까운 순."""
    min_capacity = _A["fit_min_capacity"] if min_capacity is None else min_capacity
    first, last, step = _A["fit_weeks"]
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
        for weeks in range(first, last + 1, step):
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
