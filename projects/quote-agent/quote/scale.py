"""규모 계수 추정 에이전트. 가정값 표에 없는 대학의 규모 계수를 AI가 근거와 함께 제안한다.
제안값은 확정이 아니다: 견적 경고에 'AI 추정'으로 남고, 값은 허용 범위로 잘라서 쓰며, 실패하면 1.0 가정으로 되돌아간다."""
from typing import Optional

from pydantic import BaseModel, Field

from common import structured
from quote import engine

LOW, HIGH = 0.3, 2.0     # QuoteRequest.client_scale의 허용 범위와 같다


class AiScale(BaseModel):
    factor: float = Field(..., description="규모 계수(서울대학교를 1.0으로 한 상대값)")
    confidence: str = Field(..., description="확신 정도: 높음/보통/낮음")
    rationale: str = Field(..., description="그렇게 본 근거 한두 문장. 모르면 모른다고 쓴다")


def _past_note(past) -> str:
    return f" 과거 견적에서 같은 기관에 쓴 값(참고, 최근 순): {'; '.join(past)}." if past else ""


def _prompt(client: str, scope: str) -> str:
    known = ", ".join(f"{k} {v:g}" for k, v in engine.CLIENT_SCALE.items())
    return (f"규모 계수는 연구행정시스템 구축 용역에서 필요한 공수를 서울대학교(1.0) 대비 몇 배로 볼지 정하는 값이다. "
            f"대학의 연구비 규모, 연구자·과제 수, 조직 복잡도가 클수록 크다. 참고 값(가정값): {known}.\n"
            f"대상 기관: {client}\n사업 범위 메모: {scope or '없음'}\n"
            f"{LOW}~{HIGH} 사이의 값 하나와 근거를 답하라. 이 기관을 잘 모르면 1.0 근처로 두고 확신을 '낮음'으로 하라. "
            f"지어낸 통계나 수치를 근거로 쓰지 마라.")


def estimate(client: str, scope: str = "", ask=structured.ask_structured, past=()) -> Optional[dict]:
    """성공하면 {factor, confidence, rationale}, 실패하면 None(호출한 쪽이 1.0 가정으로 되돌린다)."""
    try:
        s = ask(_prompt(client, scope) + _past_note(past), AiScale, system="당신은 견적 가정값을 제안하는 보조 에이전트다. 확정이 아니라 제안만 한다.",
                tag="scale-estimate", max_tokens=600)
    except Exception:
        return None
    if s.data is None or s.mock:
        return None
    f = min(HIGH, max(LOW, float(s.data.factor)))
    return {"factor": round(f, 2), "confidence": s.data.confidence, "rationale": s.data.rationale[:150]}
