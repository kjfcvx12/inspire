"""시연 저장본: 예시 문장과 정확히 일치할 때만 돌려주고, 파일이 없거나 깨져도 예외 없이 빈 결과."""
import json

from quote.agent import AgentResult
from quote.engine import QuoteRequest, calculate
from quote.examples import EXAMPLES
from quote.replay import load_cache, lookup, save_cache


def _result(text="설명", mock=False):
    q = calculate(QuoteRequest(client="고려대학교", weeks=13))
    return AgentResult(text=text, quotes=[q], trace=["calculate_quote({})"], budgets=[250_000_000], mock=mock, steps=2)


def test_roundtrip_keeps_quotes_and_fields(tmp_path):
    p = tmp_path / "cache.json"
    r = _result()
    save_cache({EXAMPLES[0]: r}, p)
    got = load_cache(p)[EXAMPLES[0]]
    assert got.text == "설명" and got.steps == 2 and got.budgets == [250_000_000] and got.mock is False
    assert got.quotes[0].total == r.quotes[0].total and got.quotes[0].request.client == "고려대학교"
    meta = json.loads(p.read_text(encoding="utf-8"))
    assert {"generated_at", "model", "assumptions_version"} <= set(meta)


def test_mock_results_are_not_saved(tmp_path):
    p = tmp_path / "cache.json"
    save_cache({EXAMPLES[0]: _result(mock=True), EXAMPLES[1]: _result()}, p)
    assert list(load_cache(p)) == [EXAMPLES[1]]


def test_missing_or_broken_file_gives_empty(tmp_path):
    assert load_cache(tmp_path / "none.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_cache(bad) == {}
    bad.write_text(json.dumps({"results": {EXAMPLES[0]: {"text": 1}}}), encoding="utf-8")
    assert load_cache(bad) == {}


def test_lookup_matches_examples_exactly():
    cache = {EXAMPLES[0]: _result(), "임의 문장": _result()}
    assert lookup(EXAMPLES[0], cache) is cache[EXAMPLES[0]]
    assert lookup(EXAMPLES[0] + " ", cache) is None
    assert lookup("임의 문장", cache) is None      # 예시가 아니면 저장본이 있어도 쓰지 않는다
    assert lookup(EXAMPLES[1], cache) is None
