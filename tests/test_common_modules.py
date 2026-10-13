"""starters/common 모듈 테스트. 실제 API는 호출하지 않고 가짜 클라이언트로 재시도·폴백·기록을 검증한다."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "starters"))
from common import db, edgecases, evalkit, llm, structured, usage_log  # noqa: E402


# ---- 가짜 SDK ---------------------------------------------------------------
def _req():
    return httpx2.Request("POST", "http://test.invalid/v1/messages")


def status_error(code):
    cls = {401: anthropic.AuthenticationError, 429: anthropic.RateLimitError,
           500: anthropic.InternalServerError, 400: anthropic.BadRequestError}[code]
    return cls("boom", response=httpx2.Response(code, request=_req()), body=None)


def reply(text="안녕", stop="end_turn", parsed=None, inp=100, out=20, cache_read=0):
    u = SimpleNamespace(input_tokens=inp, output_tokens=out, cache_read_input_tokens=cache_read,
                        cache_creation_input_tokens=0)
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=u,
                           stop_reason=stop, parsed_output=parsed)


class FakeStream:
    def __init__(self, chunks, final, fail_after=None):
        self.chunks, self.final, self.fail_after = chunks, final, fail_after

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @property
    def text_stream(self):
        for i, c in enumerate(self.chunks):
            if self.fail_after is not None and i == self.fail_after:
                raise status_error(500)
            yield c

    def get_final_message(self):
        return self.final


class FakeClient:
    """script: 호출 순서대로 꺼내 쓰는 응답/예외 목록. 호출 인자는 calls에 쌓는다."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.messages = SimpleNamespace(create=self._next("create"), parse=self._next("parse"),
                                        stream=self._stream)

    def _next(self, name):
        def fn(**kw):
            self.calls.append((name, kw))
            item = self.script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        return fn

    def _stream(self, **kw):
        self.calls.append(("stream", kw))
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setenv("USAGE_LOG_PATH", str(tmp_path / "usage.jsonl"))
    monkeypatch.setattr(llm, "WAIT_BASE", 0)
    monkeypatch.setattr(llm, "WAIT_MAX", 0)

    def install(script):
        c = FakeClient(script)
        monkeypatch.setattr(llm, "get_client", lambda: c)
        return c
    return install


# ---- llm: 재시도·폴백·캐싱·기록 ------------------------------------------------
def test_retries_transient_errors_then_succeeds_and_records(fake):
    c = fake([status_error(429), status_error(500), reply("ok")])
    r = llm.create(messages=[{"role": "user", "content": "hi"}], tag="t")
    assert llm.text_of(r) == "ok"
    assert len(c.calls) == 3
    assert usage_log.summary()["calls"] == 1  # 성공한 호출만 기록


def test_non_retryable_error_gives_up_immediately(fake):
    c = fake([status_error(401), reply("never")])
    with pytest.raises(llm.LLMUnavailable):
        llm.create(messages=[{"role": "user", "content": "hi"}])
    assert len(c.calls) == 1


def test_retry_exhausted_raises_after_max_attempts(fake):
    c = fake([status_error(500)] * 5)
    with pytest.raises(llm.LLMUnavailable):
        llm.create(messages=[{"role": "user", "content": "hi"}])
    assert len(c.calls) == llm.MAX_ATTEMPTS


def test_ask_falls_back_to_mock_instead_of_raising(fake):
    fake([status_error(401)])
    r = llm.ask("질문", fallback=lambda p: f"mock:{p}")
    assert r.mock and r.text == "mock:질문" and "AuthenticationError" in r.error
    fake([status_error(401)])
    assert llm.ask("질문").text.startswith("(mock)")


def test_ask_reports_truncation(fake):
    fake([reply("잘린 답", stop="max_tokens")])
    r = llm.ask("q")
    assert not r.mock and r.truncated


def test_refusal_becomes_fallback_not_a_real_answer(fake):
    fake([reply("", stop="refusal")])
    r = llm.ask("q", fallback="거절됨")
    assert r.mock and r.text == "거절됨"


def test_system_is_sent_as_cached_block_unless_disabled(fake):
    c = fake([reply(), reply()])
    llm.create(messages=[{"role": "user", "content": "q"}], system="규칙", cache=True)
    llm.create(messages=[{"role": "user", "content": "q"}], system="규칙", cache=False)
    first, second = c.calls[0][1], c.calls[1][1]
    assert first["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert second["system"] == "규칙"
    assert first["model"] == llm.MODEL


def test_stream_yields_chunks_and_records_usage(fake):
    fake([FakeStream(["안", "녕"], reply("안녕", inp=50, out=2))])
    assert "".join(llm.stream_text("q", tag="s")) == "안녕"
    s = usage_log.summary()
    assert s["calls"] == 1 and s["input"] == 50


def test_stream_retries_before_first_chunk_only(fake):
    c = fake([status_error(500), FakeStream(["ok"], reply("ok"))])
    assert "".join(llm.stream_text("q")) == "ok"
    assert len(c.calls) == 2
    c2 = fake([FakeStream(["a", "b", "c"], reply(), fail_after=1), FakeStream(["x"], reply())])
    out = "".join(llm.stream_text("q"))
    assert out.startswith("a") and "끊겼습니다" in out
    assert len(c2.calls) == 1  # 이미 글자를 내보낸 뒤에는 재시도하지 않는다


def test_stream_falls_back_when_nothing_was_emitted(fake):
    fake([status_error(401)])
    assert "".join(llm.stream_text("q", fallback="오프라인")) == "오프라인"


# ---- structured --------------------------------------------------------------
class Item(BaseModel):
    name: str
    qty: int


def test_structured_returns_validated_instance(fake):
    c = fake([reply(parsed=Item(name="사과", qty=3))])
    r = structured.ask_structured("사과 3개", Item)
    assert r.data == Item(name="사과", qty=3) and not r.mock and r.attempts == 1
    assert c.calls[0][0] == "parse" and c.calls[0][1]["output_format"] is Item
    assert "tool_choice" not in c.calls[0][1]  # Sonnet 5.5는 강제 tool_choice가 400


def test_structured_retries_with_error_note_then_succeeds(fake):
    c = fake([reply(parsed=None), reply(parsed=Item(name="배", qty=1))])
    r = structured.ask_structured("배 1개", Item, max_attempts=2)
    assert r.data.name == "배" and r.attempts == 2
    assert "스키마를 만족하지 않았습니다" in c.calls[1][1]["messages"][0]["content"]


def test_structured_validation_error_is_retried(fake):
    try:
        Item(name="x", qty="not-int")
    except ValueError as e:
        err = e
    c = fake([err, reply(parsed=Item(name="귤", qty=2))])
    r = structured.ask_structured("귤 2개", Item)
    assert r.data.qty == 2 and r.attempts == 2 and len(c.calls) == 2


def test_structured_falls_back_when_schema_never_met(fake):
    fake([reply(parsed=None), reply(parsed=None)])
    default = Item(name="알 수 없음", qty=0)
    r = structured.ask_structured("???", Item, max_attempts=2, fallback=default)
    assert r.mock and r.data == default and r.attempts == 2 and r.error


def test_structured_api_down_is_not_asked_twice(fake):
    c = fake([status_error(401), reply(parsed=Item(name="x", qty=1))])
    r = structured.ask_structured("q", Item, max_attempts=3)
    assert r.mock and r.data is None and len(c.calls) == 1


# ---- db ----------------------------------------------------------------------
def test_store_roundtrip_and_injection_safety(tmp_path):
    s = db.Store(str(tmp_path / "t.db"))
    assert s.list() == [] and s.count() == 0 and not (tmp_path / "t.db").exists()  # 읽기만으로 파일 생성 안 함
    s.add("qa", {"q": "한글 😀", "a": "x"})
    s.add("qa", {"q": "'; DROP TABLE events; --"})
    s.add("fb", {"up": True})
    rows = s.list("qa")
    assert [r["data"]["q"] for r in rows] == ["'; DROP TABLE events; --", "한글 😀"]  # 최신순
    assert s.count() == 3 and s.count("fb") == 1
    assert s.list(kind="x'; --") == []
    s.kv_set("model", {"name": "rf"})
    s.kv_set("model", {"name": "lgbm"})
    assert s.kv_get("model") == {"name": "lgbm"} and s.kv_get("nope", 7) == 7
    s.clear("qa")
    assert s.count() == 1
    s.clear()
    assert s.count() == 0


# ---- evalkit ------------------------------------------------------------------
def test_check_rules():
    assert evalkit.check("환불은 7일 이내입니다", {"contains": ["7일"], "not_contains": ["30일"]}) == []
    assert evalkit.check("ABC", {"contains": ["abc"]}) == []  # 대소문자 무시
    assert evalkit.check("x", {"regex": r"\d+"})
    assert evalkit.check({"r2": 0.91}, {"key": "r2", "range": [0.8, 1.0]}) == []
    assert evalkit.check({"r2": 0.5}, {"key": "r2", "range": [0.8, 1.0]})
    assert evalkit.check(3.14, {"approx": [3.0, 0.2]}) == []
    assert evalkit.check({"a": 1}, {"key": "missing", "equals": 1})
    assert evalkit.check("abc", {"range": [0, 1]})  # 숫자가 아님


def test_run_eval_counts_errors_and_skips_judge(tmp_path):
    g = tmp_path / "g.jsonl"
    g.write_text("# 주석\n\n" + "\n".join(json.dumps(r, ensure_ascii=False) for r in [
        {"id": "a", "input": "사과", "expect": {"contains": ["사과"]}, "tags": ["t1"]},
        {"id": "b", "input": "배", "expect": {"contains": ["사과"]}, "tags": ["t1"]},
        {"id": "boom", "input": "x", "expect": {"contains": ["x"]}},
        {"id": "j", "input": "사과", "expect": {"contains": ["사과"], "judge": "친절한가"}},
    ]), encoding="utf-8")
    cases = evalkit.load_golden(g)

    def fn(x):
        if x == "x":
            raise RuntimeError("터짐")
        return f"{x} 맛있다"

    rep = evalkit.run_eval(fn, cases)
    st = {r.id: r.status for r in rep.results}
    assert st == {"a": "pass", "b": "fail", "boom": "error", "j": "skipped"}
    assert rep.passed == 1 and len(rep.graded) == 3 and rep.rate == pytest.approx(1 / 3)
    md = evalkit.to_markdown(rep)
    assert "1/3 통과" in md and "건너뜀 1건" in md and "boom" in md

    rep2 = evalkit.run_eval(fn, cases, judge=lambda out, rubric, ctx: (True, "ok"))
    assert {r.id: r.status for r in rep2.results}["j"] == "pass"


def test_load_golden_validates(tmp_path):
    p = tmp_path / "g.jsonl"
    p.write_text('{"input": "x"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        evalkit.load_golden(p)
    p.write_text('{"id":"a","input":"x","expect":{}}\n{"id":"a","input":"y","expect":{}}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="중복"):
        evalkit.load_golden(p)


def test_eval_cli_exit_codes(tmp_path):
    (tmp_path / "t.py").write_text("def f(x):\n    return 'ok ' + str(x)\n", encoding="utf-8")
    g = tmp_path / "g.jsonl"
    g.write_text('{"id":"a","input":"1","expect":{"contains":["ok 1"]}}\n'
                 '{"id":"b","input":"2","expect":{"contains":["nope"]}}\n', encoding="utf-8")
    base = [sys.executable, str(ROOT / "scripts" / "eval.py"), str(g), "--target", f"{tmp_path / 't.py'}:f"]
    run = lambda *extra: subprocess.run(base + list(extra), capture_output=True, text=True,  # noqa: E731
                                        encoding="utf-8", errors="replace", cwd=tmp_path)
    assert run().returncode == 1                       # 기본은 전부 통과해야 함
    r = run("--min-pass", "0.5")
    assert r.returncode == 0 and "1/2 통과" in r.stdout


# ---- edgecases ----------------------------------------------------------------
def test_edge_inputs_cover_the_nasty_cases():
    assert "" in edgecases.TEXT_EDGES and any(len(t) > 5000 for t in edgecases.TEXT_EDGES)
    assert float("nan") != float("nan") and any(x != x for x in edgecases.NUMBER_EDGES)  # NaN 포함
    import pandas as pd
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"], "y": [0, 1, 0]})
    v = edgecases.frame_edges(df, target="y")
    assert len(v["empty"]) == 0 and len(v["single_row"]) == 1
    assert v["first_col_all_nan"]["a"].isna().all() and "a" not in v["missing_col"].columns
    assert len(v["duplicated_rows"]) == 15
