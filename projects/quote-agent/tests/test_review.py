"""AI 계산·검증 에이전트. AI 호출은 가짜로 바꿔 시험한다(실제 API 없음). 화면 금액은 항상 엔진 값이다."""
from common.structured import Structured
from quote import review
from quote.agent import AgentResult
from quote.engine import QuoteRequest, baseline_quote, calculate
from quote.review import AiCalc, AiRecheck, AiVerdict


def _calc_from(q, **over):
    base = dict(labor=q.lines["기본 인건비"], onsite_add=0, english_add=0, rush_add=0, support_add=0,
                overhead=q.lines["간접경비"], profit=q.lines["기업이윤"], discount=0,
                supply=q.supply, vat=q.vat, total=q.total)
    base.update(over)
    return AiCalc(**base)


def test_calc_agent_matching_engine_is_reported_as_match():
    q = baseline_quote()
    r = review.ai_recompute(q, ask=lambda *a, **k: Structured(data=_calc_from(q)))
    assert r["status"] == "일치" and r["ai_total"] == q.total and r["diff"] == 0


def test_calc_agent_small_rounding_gap_is_still_a_match_but_big_gap_is_not():
    q = baseline_quote()
    small = review.ai_recompute(q, ask=lambda *a, **k: Structured(data=_calc_from(q, total=q.total + 1000)))
    big = review.ai_recompute(q, ask=lambda *a, **k: Structured(data=_calc_from(q, total=int(q.total * 1.05))))
    assert small["status"] == "일치" and big["status"] == "불일치" and big["diff"] == int(q.total * 1.05) - q.total


def test_calc_agent_failure_does_not_raise():
    q = baseline_quote()
    assert review.ai_recompute(q, ask=lambda *a, **k: Structured(data=None, mock=True, error="down"))["status"] == "불가"

    def boom(*a, **k):
        raise RuntimeError("x")
    assert review.ai_recompute(q, ask=boom)["status"] == "불가"


def test_verify_agent_reports_issues_or_consistency():
    q = baseline_quote()
    ok = review.ai_verify("총액 353,560,000원입니다.", [q], ask=lambda *a, **k: Structured(data=AiVerdict(consistent=True)))
    bad = review.ai_verify("경고가 없습니다.", [q], ask=lambda *a, **k: Structured(
        data=AiVerdict(consistent=False, issues=["설명은 경고 없음이라 했지만 엔진에는 경고가 있습니다"])))
    assert ok["status"] == "일치" and not ok["issues"]
    assert bad["status"] == "의견 있음" and "경고" in bad["issues"][0]
    assert review.ai_verify("x", [q], ask=lambda *a, **k: Structured(data=None, mock=True))["status"] == "불가"


def test_calc_prompt_contains_the_rules_but_not_the_engine_answer():
    q = calculate(QuoteRequest(weeks=13))
    seen = {}

    def fake(prompt, schema, **k):
        seen["prompt"] = prompt
        return Structured(data=_calc_from(q))
    review.ai_recompute(q, ask=fake)
    p = seen["prompt"]
    assert "4.345" in p and "15%" in p and "10%" in p and "18,000,000" in p      # 계산 규칙과 단가는 준다
    assert f"{q.total:,}" not in p and str(q.total) not in p                        # 엔진의 정답은 주지 않는다(독립 계산)


def test_run_review_skips_mock_results_and_runs_both_agents_otherwise():
    q = baseline_quote()
    ask = lambda *a, **k: Structured(data=_calc_from(q)) if a[1] is AiCalc else Structured(data=AiVerdict(consistent=True))
    assert review.run_review(AgentResult(text="x", quotes=[q], mock=True), ask=ask) is None
    assert review.run_review(AgentResult(text="x"), ask=ask) is None
    out = review.run_review(AgentResult(text="총액은 353,560,000원", quotes=[q]), ask=ask)
    assert out["calc"]["status"] == "일치" and out["verify"]["status"] == "일치"


def test_describe_lines_for_match_mismatch_and_failure():
    assert review.describe(None) == []
    ok = {"calc": {"status": "일치", "diff": 0}, "verify": {"status": "일치", "issues": []}}
    bad = {"calc": {"status": "불일치", "diff": 5_000_000}, "verify": {"status": "의견 있음", "issues": ["경고 누락"]}}
    off = {"calc": {"status": "불가", "diff": None}, "verify": {"status": "불가", "issues": []}}
    assert "일치" in review.describe(ok)[0] and "모순되지 않" in review.describe(ok)[1]
    assert "+5,000,000원" in review.describe(bad)[0] and "경고 누락" in review.describe(bad)[-1]
    assert all("못해" in x or "못했" in x for x in review.describe(off))


def _mismatch_calc(q):
    return review.ai_recompute(q, ask=lambda *a, **k: Structured(data=_calc_from(q, overhead=q.lines["간접경비"] + 9_000_000,
                                                                              total=int(q.total * 1.05))))


def test_reconcile_runs_only_on_mismatch_and_never_changes_amounts():
    q = baseline_quote()
    calls = []

    def ask(prompt, schema, **k):
        calls.append(schema.__name__)
        if schema is AiRecheck:
            return Structured(data=AiRecheck(ai_was_wrong=True, item="간접경비", explanation="규칙 7번은 직접비 기준"))
        return Structured(data=_calc_from(q, overhead=q.lines["간접경비"] + 9_000_000, total=int(q.total * 1.05))
                          if schema is AiCalc else AiVerdict(consistent=True))
    out = review.run_review(AgentResult(text="총액", quotes=[q]), ask=ask)
    assert out["calc"]["status"] == "불일치" and out["calc"]["recheck"]["verdict"] == "AI 정정"
    assert "AiRecheck" in calls and q.total == baseline_quote().total
    ok = review.run_review(AgentResult(text="총액", quotes=[q]), ask=lambda p, s, **k: Structured(
        data=_calc_from(q) if s is AiCalc else AiVerdict(consistent=True)))
    assert "recheck" not in ok["calc"]


def test_reconcile_prompt_shows_both_sides_and_failure_is_safe():
    q = baseline_quote()
    calc = _mismatch_calc(q)
    seen = {}

    def ask(prompt, schema, **k):
        seen["p"] = prompt
        return Structured(data=AiRecheck(ai_was_wrong=False, item="간접경비", explanation="엔진이 다름"))
    r = review.reconcile(q, calc, ask)
    assert r["verdict"] == "엔진 확인 필요" and "엔진" in seen["p"] and "AI" in seen["p"] and f"{q.total:,}" in seen["p"]
    assert review.reconcile(q, calc, lambda *a, **k: Structured(data=None, mock=True))["verdict"] == "불가"


def test_describe_mentions_recheck_verdict():
    base = {"verify": {"status": "일치", "issues": []}}
    wrong = {**base, "calc": {"status": "불일치", "diff": 100, "recheck": {"verdict": "AI 정정", "item": "간접경비", "explanation": "e"}}}
    eng = {**base, "calc": {"status": "불일치", "diff": 100, "recheck": {"verdict": "엔진 확인 필요", "item": "간접경비", "explanation": "e"}}}
    assert "엔진 값을 유지" in " ".join(review.describe(wrong)) and "담당자가 확인" in " ".join(review.describe(eng))


def test_run_review_reuses_a_given_verdict_instead_of_calling_verify_again():
    q = baseline_quote()
    seen = []

    def ask(prompt, schema, **k):
        seen.append(schema.__name__)
        return Structured(data=_calc_from(q))
    out = review.run_review(AgentResult(text="총액", quotes=[q]), ask=ask, verified={"status": "일치", "issues": []})
    assert seen == ["AiCalc"] and out["verify"] == {"status": "일치", "issues": []}
