"""AI 계산·검증 에이전트. AI 호출은 가짜로 바꿔 시험한다(실제 API 없음). 화면 금액은 항상 엔진 값이다."""
from common.structured import Structured
from quote import review
from quote.agent import AgentResult
from quote.engine import QuoteRequest, baseline_quote, calculate
from quote.review import AiCalc, AiVerdict


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
