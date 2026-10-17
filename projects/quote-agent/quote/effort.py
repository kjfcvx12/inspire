"""신규 항목 공수 추정 에이전트. 기준 설계에 없는 단계·산출물의 공수 비율(서울대 전체 대비 %)을 AI가 기존 항목에 빗대어 제안한다.
제안값은 확정이 아니다: 견적에는 'LLM 추정'으로 남고, 값은 허용 범위로 잘라 쓰며, 실패하면 에이전트가 직접 추정하던 기존 방식으로 돌아간다."""
from typing import Optional

from pydantic import BaseModel, Field

from common import structured
from quote import engine

LOW, HIGH = 1.0, 60.0     # 한 항목이 기준안 전체의 60%를 넘는 추정은 의심스러워 잘라서 경고 대상으로 둔다


class AiEffort(BaseModel):
    effort_pct: float = Field(..., description="서울대 기준안 전체 공수 대비 비율(%)")
    confidence: str = Field(..., description="확신 정도: 높음/보통/낮음")
    reason: str = Field(..., description="어떤 기존 단계·산출물에 빗대어 그렇게 봤는지 한두 문장")


def _past_note(past) -> str:
    return f" 과거 견적에서 비슷한 항목에 쓴 값(참고, 최근 순): {'; '.join(past)}." if past else ""


def _prompt(name: str, detail: str) -> str:
    mods = ", ".join(f"{k} {v * 100:g}%" for k, v in engine.MODULE_WEIGHT.items())
    dels = ", ".join(f"{k} {v * 100:g}%" for k, v in engine.DELIVERABLE_WEIGHT.items())
    return (f"기준 설계(서울대 연구행정시스템 PI 용역) 전체 공수를 100%로 볼 때 기존 단계의 비중은 {mods}이고, "
            f"산출물 비중은 {dels}이다(단계 하나를 모든 산출물로 낼 때 그 단계 비중만큼의 공수).\n"
            f"신규 항목: {name}\n설명: {detail or '없음'}\n"
            f"이 항목의 공수가 기준 설계 전체의 몇 %인지 {LOW:g}~{HIGH:g} 사이로 답하고, 가장 비슷한 기존 단계나 산출물에 빗대어 근거를 써라. "
            f"항목이 모호하면 작게 잡고 확신을 '낮음'으로 하라.")


def estimate(name: str, detail: str = "", ask=structured.ask_structured, past=()) -> Optional[dict]:
    """성공하면 {effort_pct, confidence, reason}, 실패하면 None."""
    try:
        s = ask(_prompt(name, detail) + _past_note(past), AiEffort, system="당신은 견적 공수를 제안하는 보조 에이전트다. 확정이 아니라 제안만 한다.",
                tag="effort-estimate", max_tokens=600)
    except Exception:
        return None
    if s.data is None or s.mock:
        return None
    return {"effort_pct": round(min(HIGH, max(LOW, float(s.data.effort_pct))), 1), "confidence": s.data.confidence,
            "reason": s.data.reason[:150]}
