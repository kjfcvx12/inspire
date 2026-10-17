from types import SimpleNamespace as NS

from common import llm
from quote import agent
from quote.engine import QuoteRequest, calculate


def _block_tool(i, name, inp):
    return NS(type="tool_use", id=f"t{i}", name=name, input=inp)


def test_mock_fallback_when_api_down(monkeypatch):
    def boom(**kw):
        raise llm.LLMUnavailable("down")
    monkeypatch.setattr(llm, "create", boom)
    r = agent.run("고대에서 3개월, 5명, 상주로 견적 요청")
    assert r.mock and r.text.startswith("(mock)") and len(r.quotes) == 1
    assert r.quotes[0].request.client == "고려대학교" and r.quotes[0].request.onsite


def test_mock_understands_negation_of_options():
    r = agent._mock_request
    assert not r("고려대, 4개월, 6명, 상주 없음").onsite           # 앱 placeholder 문구
    assert not r("고려대 비상주로 진행").onsite
    assert not r("연세대 영문 산출물은 불필요").english_deliverables
    assert r("연세대 상주 필수").onsite and r("연세대 영문 산출물 포함").english_deliverables


def test_scenario_labels_are_unique():
    res = agent.AgentResult(text="")
    for weeks in (10, 12, 14):
        agent._add(res, calculate(QuoteRequest(weeks=weeks)))     # label은 모두 기본값 '견적'
    labels = [q.request.label for q in res.quotes]
    assert len(set(labels)) == 3


def test_mock_team_size_matches_request():
    for n in (1, 2, 5, 9, 20):
        assert sum(agent._mock_request(f"고대 {n}명").team.values()) == n


def test_tool_loop_uses_engine_and_stops(monkeypatch):
    seq = iter([
        NS(content=[_block_tool(1, "calculate_quote", {"client": "연세대학교", "weeks": 12})]),
        NS(content=[_block_tool(2, "calculate_quote", {"weeks": -5})]),   # 잘못된 입력 → 오류가 모델에 돌아가야 함
        NS(content=[NS(type="text", text="완료")]),
    ])
    seen = []
    monkeypatch.setattr(llm, "create", lambda **kw: (seen.append(kw["messages"][-1]), next(seq))[1])
    r = agent.run("연대 12주")
    assert r.text == "완료" and len(r.quotes) == 1 and r.quotes[0].request.client == "연세대학교"
    assert "입력 오류" in seen[-1]["content"][0]["content"]


def test_ai_off_never_calls_llm(monkeypatch):
    def boom(**kw):
        raise AssertionError("LLM이 호출되면 안 된다")
    monkeypatch.setattr(llm, "create", boom)
    r = agent.run("고대 3개월 5명", use_ai=False)
    assert r.mock and len(r.quotes) == 1


def test_budget_tool_adds_scenarios_and_records_budget(monkeypatch):
    seq = iter([NS(content=[_block_tool(1, "fit_to_budget", {"client": "고려대학교", "budget_total": 250_000_000})]),
                NS(content=[NS(type="text", text="완료")])])
    monkeypatch.setattr(llm, "create", lambda **kw: next(seq))
    r = agent.run("고려대 예산 2.5억")
    assert r.budgets == [250_000_000] and 1 <= len(r.quotes) <= 3
    assert all(q.total <= 250_000_000 for q in r.quotes)


def test_step_limit(monkeypatch):
    monkeypatch.setattr(llm, "create", lambda **kw: NS(content=[_block_tool(1, "get_baseline", {})]))
    r = agent.run("x", max_steps=3)
    assert r.steps == 3 and "한도" in r.text
