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


def test_mock_reads_kaist_alias_and_role_counts():
    r = agent._mock_request("카이스트 8주 PM 1명 분석가 1명")
    assert (r.client, r.weeks, r.team) == ("KAIST", 8, {"PM": 1, "분석가": 1})


def test_mock_rejects_instead_of_silently_misreading_or_crashing():
    for text in ["고대 1000주", "고대 -3주 6명", "고대 0명", "고대 50명", "연대 고대 비교", "고대 " + "9" * 5000 + "명"]:
        r = agent.run(text, use_ai=False)           # 죽으면 안 된다
        assert r.mock and r.quotes == [] and "해석하지 못" in r.text, text


def test_duration_months_tool_input_is_not_overridden_by_baseline_weeks():
    res = agent.AgentResult(text="")
    agent._run_tool("calculate_quote", {"duration_months": 3}, res)
    assert res.quotes[0].request.weeks == 13


def test_mock_rejects_ambiguous_or_repeated_conditions():
    for text in ["PM 1명 컨설턴트 2명 PM 2명 고대", "총 6명, PM 1명, 16주", "6명 중 PM 1명 8주",
                 "고대 4개월 6명. 고대 5개월 6명."]:
        r = agent.run(text, use_ai=False)
        assert r.mock and r.quotes == [] and "해석하지 못" in r.text, text
    assert agent._mock_request("PM 1명 컨설턴트 2명 고대 12주").team == {"PM": 1, "컨설턴트": 2}
    assert agent._mock_request("고대 12주 12주").weeks == 12            # 같은 값의 반복은 충돌이 아니다


def test_mock_role_names_do_not_match_inside_longer_role_names():
    r = agent._mock_request
    assert r("수석컨설턴트 1명 12주").team == {"수석컨설턴트": 1}
    assert r("수석컨설턴트 2명 PM 1명 12주").team == {"PM": 1, "수석컨설턴트": 2}
    full = r("PM 1명 수석컨설턴트 1명 컨설턴트 2명 분석가 2명 16주")      # 이 서비스의 대표 팀 구성 문장
    assert full.team == {"PM": 1, "수석컨설턴트": 1, "컨설턴트": 2, "분석가": 2}
