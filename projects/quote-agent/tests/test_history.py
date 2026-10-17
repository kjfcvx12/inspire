"""견적 이력(sqlite): tmp_path에서만 동작하고, 수주 결과는 정해진 값만 받는다."""
import pytest

from quote import history
from quote.engine import QuoteRequest, calculate


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "quotes.db")


def test_save_list_and_restore_request(db):
    req = QuoteRequest(label="고대 안", client="고려대학교", weeks=13, team={"PM": 1, "컨설턴트": 2, "분석가": 2})
    q = calculate(req)
    qid = history.save_quote(q, db_path=db)
    rows = history.list_quotes(db_path=db)
    assert len(rows) == 1 and rows[0]["id"] == qid
    r = rows[0]
    assert (r["label"], r["client"], r["weeks"], r["headcount"], r["total"]) == ("고대 안", "고려대학교", 13, 5, q.total)
    assert r["assumptions_version"] == q.assumptions_version and r["outcome"] is None and r["final_amount"] is None
    assert calculate(history.get_request(qid, db_path=db)).total == q.total


def test_list_is_newest_first_and_limited(db):
    ids = [history.save_quote(calculate(QuoteRequest(weeks=w)), db_path=db) for w in (10, 12, 14)]
    rows = history.list_quotes(limit=2, db_path=db)
    assert [r["id"] for r in rows] == [ids[2], ids[1]]


def test_set_outcome_validates(db):
    qid = history.save_quote(calculate(QuoteRequest()), db_path=db)
    history.set_outcome(qid, "수주", final_amount=300_000_000, db_path=db)
    row = history.list_quotes(db_path=db)[0]
    assert row["outcome"] == "수주" and row["final_amount"] == 300_000_000
    with pytest.raises(ValueError):
        history.set_outcome(qid, "성공", db_path=db)
    with pytest.raises(ValueError):
        history.set_outcome(999, "탈락", db_path=db)
    with pytest.raises(ValueError):
        history.get_request(999, db_path=db)


def test_env_path_and_injection_safe(tmp_path, monkeypatch):
    path = tmp_path / "env.db"
    monkeypatch.setenv("QUOTE_DB_PATH", str(path))
    q = calculate(QuoteRequest(label="x'); DROP TABLE quotes;--"))
    history.save_quote(q)
    assert path.exists() and history.list_quotes()[0]["label"] == "x'); DROP TABLE quotes;--"
    assert len(history.list_quotes()) == 1
