"""계획 에이전트. 계산 전에 요청을 읽고 어떤 시나리오를 어떤 순서로 계산할지 계획을 세워 실행 에이전트에게 넘긴다.
역할 분리: 계획(planner) → 실행(agent.run, 도구 호출) → 확인(review). 계획은 조언이고 금액이나 입력값을 정하지 않는다."""
from typing import List, Optional

from pydantic import BaseModel, Field

from common import structured
from quote import engine


class AiPlan(BaseModel):
    scenarios: List[str] = Field(default_factory=list, description="계산할 시나리오 1~3개. 각각 '무엇을 바꾼 안'인지 한 줄")
    assumptions: List[str] = Field(default_factory=list, description="요청에 없어서 기준안 값으로 두어야 하는 항목(최대 4개)")
    watch: List[str] = Field(default_factory=list, description="결과에서 특히 확인할 위험이나 경고(최대 3개)")


def _prompt(user_text: str) -> str:
    known = ", ".join(engine.CLIENT_SCALE)
    return (f"견적 에이전트가 쓸 수 있는 도구는 기준안 조회, 견적 계산, 팀 다시 짜기, 예산에 맞추기, 규모 계수 추정, 신규 항목 공수 추정, 과거 견적 검색이다. "
            f"규모 계수가 있는 대학: {known}. 그 밖의 대학은 계수를 추정해야 한다.{chr(10)}"
            f"다음 요청을 읽고 어떤 시나리오를 계산할지 계획을 세워라. 요청 그대로의 안이 항상 1번이다. 금액이나 계산 결과는 쓰지 마라. 각 항목은 40자 안팎으로 짧게 쓴다.{chr(10)}"
            f"요청: {user_text[:1500]}")


def plan(user_text: str, ask=structured.ask_structured) -> Optional[AiPlan]:
    try:
        s = ask(_prompt(user_text), AiPlan, system="당신은 견적 작업을 계획하는 에이전트다. 계획만 세우고 계산하지 않는다.",
                tag="planner", max_tokens=1200)
    except Exception:
        return None
    return None if s.data is None or s.mock or not s.data.scenarios else s.data


def to_text(p: AiPlan) -> str:
    """실행 에이전트와 화면에 보여 줄 한 줄 요약."""
    parts = ["계산할 안: " + " / ".join(f"{i + 1}) {x}" for i, x in enumerate(p.scenarios[:3]))]
    if p.assumptions:
        parts.append("기준안 값으로 둘 항목: " + ", ".join(p.assumptions[:4]))
    if p.watch:
        parts.append("확인할 위험: " + ", ".join(p.watch[:3]))
    return " | ".join(parts)
