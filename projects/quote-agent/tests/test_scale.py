"""규모 계수 추정. AI 호출은 가짜로 바꿔 시험한다(실제 API 없음)."""
from common.structured import Structured
from quote import agent, scale
from quote.engine import CLIENT_SCALE, QuoteRequest, calculate


def _ask(factor=1.2, conf="낮음", text="근거"):
    return lambda *a, **k: Structured(data=scale.AiScale(factor=factor, confidence=conf, rationale=text))


def test_estimate_returns_factor_and_clamps_to_allowed_range():
    assert scale.estimate("한양대학교", ask=_ask(1.2))["factor"] == 1.2
    assert scale.estimate("한양대학교", ask=_ask(5.0))["factor"] == scale.HIGH
    assert scale.estimate("한양대학교", ask=_ask(-3))["factor"] == scale.LOW


def test_estimate_failure_returns_none_not_exception():
    assert scale.estimate("x", ask=lambda *a, **k: Structured(data=None, mock=True, error="down")) is None

    def boom(*a, **k):
        raise RuntimeError("x")
    assert scale.estimate("x", ask=boom) is None


def test_prompt_has_reference_table_and_unknown_policy():
    seen = {}
    scale.estimate("한양대학교", "과제 많음", ask=lambda p, *a, **k: seen.setdefault("p", p) and _ask()())
    assert "서울대학교 1" in seen["p"] and "한양대학교" in seen["p"] and "낮음" in seen["p"]


def test_ai_scale_changes_required_work_only_for_unknown_client_and_is_flagged():
    plain = calculate(QuoteRequest(client="한양대학교"))
    est = calculate(QuoteRequest(client="한양대학교", client_scale=0.5, scale_note="소규모"))
    assert est.required_mm < plain.required_mm
    assert any("AI 추정" in w and "0.5" in w for w in est.warnings)
    assert not any("가정했습니다" in w for w in est.warnings)
    assert any("가정했습니다" in w for w in plain.warnings)


def test_known_client_cannot_be_overridden_by_ai_value():
    a = calculate(QuoteRequest(client="고려대학교"))
    b = calculate(QuoteRequest(client="고려대학교", client_scale=1.9))
    assert a.required_mm == b.required_mm and CLIENT_SCALE["고려대학교"] == 0.8
    assert not any("AI 추정" in w for w in b.warnings)


def test_tool_rejects_known_client_and_reports_failure(monkeypatch):
    res = agent.AgentResult(text="")
    assert "error" in agent._run_tool("estimate_client_scale", {"client": "고려대학교"}, res)
    monkeypatch.setattr(agent.scale, "estimate", lambda c, s="", past=(): None)
    assert "실패" in agent._run_tool("estimate_client_scale", {"client": "한양대학교"}, res)
    monkeypatch.setattr(agent.scale, "estimate", lambda c, s="", past=(): {"factor": 1.1, "confidence": "낮음", "rationale": "r"})
    out = agent._run_tool("estimate_client_scale", {"client": "한양대학교", "scope": "x"}, res)
    assert '"factor": 1.1' in out and not res.quotes


def test_calculate_quote_tool_accepts_scale_fields():
    res = agent.AgentResult(text="")
    out = agent._run_tool("calculate_quote", {"client": "한양대학교", "client_scale": 0.7, "scale_note": "근거"}, res)
    assert "AI 추정" in out and res.quotes[0].request.client_scale == 0.7
