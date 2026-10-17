"""견적 이력과 수주 결과를 sqlite에 저장한다(견적 전용 테이블, 파라미터 바인딩만 사용).
기본 경로 data/quotes.db, 환경변수 QUOTE_DB_PATH로 바꾼다. *.db는 .gitignore 대상이다."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from quote.engine import Quote, QuoteRequest

OUTCOMES = ("수주", "탈락", "보류")
_SCHEMA = """CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, label TEXT, client TEXT, weeks INTEGER, headcount INTEGER,
    total INTEGER, capacity REAL, assumptions_version TEXT, request_json TEXT NOT NULL, outcome TEXT, final_amount INTEGER)"""
_COLS = "id, ts, label, client, weeks, headcount, total, capacity, assumptions_version, outcome, final_amount"


def _path(db_path) -> Path:
    p = Path(db_path or os.environ.get("QUOTE_DB_PATH") or Path(__file__).resolve().parents[1] / "data" / "quotes.db")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect(db_path) -> sqlite3.Connection:
    con = sqlite3.connect(_path(db_path))
    con.execute(_SCHEMA)
    return con


def save_quote(q: Quote, db_path=None) -> int:
    r = q.request
    with closing(_connect(db_path)) as con, con:
        cur = con.execute(
            "INSERT INTO quotes (ts, label, client, weeks, headcount, total, capacity, assumptions_version, request_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), r.label, r.client, r.weeks, sum(r.team.values()), q.total,
             q.capacity, q.assumptions_version, r.model_dump_json()))
        return int(cur.lastrowid)


def list_quotes(limit: int = 20, db_path=None) -> List[Dict[str, object]]:
    with closing(_connect(db_path)) as con:
        cur = con.execute(f"SELECT {_COLS} FROM quotes ORDER BY id DESC LIMIT ?", (int(limit),))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


def set_outcome(quote_id: int, outcome: str, final_amount: Optional[int] = None, db_path=None) -> None:
    if outcome not in OUTCOMES:
        raise ValueError(f"결과는 {list(OUTCOMES)} 중 하나여야 합니다: {outcome!r}")
    with closing(_connect(db_path)) as con, con:
        cur = con.execute("UPDATE quotes SET outcome = ?, final_amount = ? WHERE id = ?", (outcome, final_amount, quote_id))
        if cur.rowcount == 0:
            raise ValueError(f"없는 견적 id: {quote_id}")


def get_request(quote_id: int, db_path=None) -> QuoteRequest:
    with closing(_connect(db_path)) as con:
        row = con.execute("SELECT request_json FROM quotes WHERE id = ?", (quote_id,)).fetchone()
    if row is None:
        raise ValueError(f"없는 견적 id: {quote_id}")
    return QuoteRequest.model_validate_json(row[0])
