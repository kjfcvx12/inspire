"""골든셋 평가용 얇은 어댑터. 평가기가 비교하기 쉬운 평평한 dict로 바꿔 돌려준다."""
from pydantic import ValidationError

from quote import agent
from quote.engine import QuoteRequest, baseline_quote, calculate


def engine_case(**kw) -> dict:
    """엔진 평가(오프라인). 잘못된 입력은 죽지 않고 error를 돌려준다."""
    try:
        q = calculate(QuoteRequest(**kw))
    except ValidationError as e:
        return {"error": str(e)[:300]}
    b = baseline_quote()
    return {"total": q.total, "delta": q.total - b.total, "ratio": round(q.total / b.total, 3),
            "capacity": q.capacity, "lines": " ".join(q.lines), "warnings": " ".join(q.warnings)}


def agent_case(text: str) -> dict:
    """에이전트 평가(API 호출). 첫 번째로 계산된 시나리오를 요약한다."""
    r = agent.run(text)
    out = {"text": r.text, "n_quotes": len(r.quotes), "mock": r.mock}
    if r.quotes:
        q = r.quotes[0]
        out.update(client=q.request.client, weeks=q.request.weeks, headcount=sum(q.request.team.values()),
                   lines=" ".join(q.lines), warnings=" ".join(q.warnings),
                   delta=q.total - baseline_quote().total)
    return out
