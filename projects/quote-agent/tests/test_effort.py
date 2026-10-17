"""신규 항목 공수 추정. AI 호출은 가짜로 바꿔 시험한다(실제 API 없음)."""
from common.structured import Structured
from quote import agent, effort


def _ask(pct=15.0):
    return lambda *a, **k: Structured(data=effort.AiEffort(effort_pct=pct, confidence="보통", reason="로드맵과 유사"))


def test_estimate_clamps_and_rounds():
    assert effort.estimate("데이터 이관", ask=_ask(15.04))["effort_pct"] == 15.0
    assert effort.estimate("x", ask=_ask(500))["effort_pct"] == effort.HIGH
    assert effort.estimate("x", ask=_ask(0))["effort_pct"] == effort.LOW


def test_failure_is_none_and_prompt_has_anchors():
    assert effort.estimate("x", ask=lambda *a, **k: Structured(data=None, mock=True)) is None
    seen = {}
    effort.estimate("교육", "임직원 교육", ask=lambda p, *a, **k: seen.setdefault("p", p) and _ask()())
    assert "연구비관리 35%" in seen["p"] and "교육" in seen["p"] and "낮음" in seen["p"]


def test_tool_returns_estimate_or_error_and_creates_no_quote(monkeypatch):
    res = agent.AgentResult(text="")
    monkeypatch.setattr(agent.effort, "estimate", lambda n, d="", past=(): {"effort_pct": 12.0, "confidence": "보통", "reason": "r"})
    assert '"effort_pct": 12.0' in agent._run_tool("estimate_extra_effort", {"name": "교육"}, res) and not res.quotes
    monkeypatch.setattr(agent.effort, "estimate", lambda n, d="", past=(): None)
    assert "실패" in agent._run_tool("estimate_extra_effort", {"name": "교육"}, res)
    assert "실패" in agent._run_tool("estimate_extra_effort", {"name": " "}, res)
