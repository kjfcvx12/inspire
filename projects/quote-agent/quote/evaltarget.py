"""골든셋 평가용 얇은 어댑터. 평가기가 비교하기 쉬운 평평한 dict로 바꿔 돌려준다."""
import copy
from functools import lru_cache

from pydantic import ValidationError

from quote import agent, assumptions, engine
from quote.engine import QuoteRequest, baseline_quote, calculate


def engine_case(**kw) -> dict:
    """엔진 평가(오프라인). 코드에 고정된 DEFAULTS로 계산하므로 운영 assumptions.json이 바뀌어도 골든셋이 깨지지 않는다.
    잘못된 입력은 죽지 않고 error를 돌려준다."""
    engine.apply_assumptions(copy.deepcopy(assumptions.DEFAULTS))
    try:
        q = calculate(QuoteRequest(**kw))
    except ValidationError as e:
        return {"error": str(e)[:300]}
    b = baseline_quote()
    return {"total": q.total, "delta": q.total - b.total, "ratio": round(q.total / b.total, 3),
            "capacity": q.capacity, "lines": " ".join(q.lines), "warnings": " ".join(q.warnings)}


@lru_cache(maxsize=64)
def _run(text: str) -> dict:
    r = agent.run(text)   # 같은 문장은 한 번만 호출한다(케이스마다 다른 항목을 검사하므로 비용·편차를 줄인다)
    out = {"text": r.text, "n_quotes": len(r.quotes), "mock": r.mock, "n_unverified": len(r.unverified)}
    if r.quotes:
        q = r.quotes[0]
        out.update(client=q.request.client, weeks=q.request.weeks, headcount=sum(q.request.team.values()),
                   n_modules=len(q.request.modules), n_extra=len(q.request.extra_items),
                   lines=" ".join(q.lines), warnings=" ".join(q.warnings),
                   delta=q.total - baseline_quote().total,
                   cheapest_total=min(x.total for x in r.quotes),
                   min_headcount=min(sum(x.request.team.values()) for x in r.quotes))
    return out


def agent_case(text: str) -> dict:
    """에이전트 평가(API 호출). 첫 번째로 계산된 시나리오를 요약한다."""
    return dict(_run(text))
