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


def _recent(limit: int, db_path=None) -> List[tuple]:
    with closing(_connect(db_path)) as con:
        return con.execute(f"SELECT {_COLS}, request_json FROM quotes ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()


def similar(client: Optional[str] = None, weeks: Optional[int] = None, headcount: Optional[int] = None,
            limit: int = 5, db_path=None) -> List[Dict[str, object]]:
    """비슷한 과거 견적. 같은 발주처가 가장 먼저, 그다음 기간·인원이 가까운 순. 최근 200건에서 찾는다."""
    scored = []
    for row in _recent(200, db_path):
        d = dict(zip(_COLS.split(", "), row[:-1]))
        try:
            req = QuoteRequest.model_validate_json(row[-1])
        except ValueError:
            continue
        score = (100 if client and d["client"] == client else 0)
        score -= abs((d["weeks"] or 0) - weeks) if weeks else 0
        score -= 2 * abs((d["headcount"] or 0) - headcount) if headcount else 0
        d["scale"] = req.client_scale
        d["extras"] = [f"{e.name} {e.effort_pct:g}%" for e in req.extra_items]
        scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:limit]]


def past_scales(client: str, db_path=None) -> List[str]:
    """같은 발주처에 이전에 AI 추정 규모 계수를 썼던 기록(최근 5건, 날짜와 근거 포함)."""
    out = []
    for row in _recent(200, db_path):
        try:
            req = QuoteRequest.model_validate_json(row[-1])
        except ValueError:
            continue
        if req.client == client and req.client_scale is not None:
            out.append(f"{row[1][:10]} 계수 {req.client_scale:g} ({req.scale_note or '근거 없음'})")
    return out[:5]


def past_extras(name: str, db_path=None) -> List[str]:
    """이름이 비슷한 신규 항목에 이전에 쓴 공수 비율(최근 5건)."""
    out = []
    key = name.strip().casefold()
    for row in _recent(200, db_path):
        try:
            req = QuoteRequest.model_validate_json(row[-1])
        except ValueError:
            continue
        for e in req.extra_items:
            n = e.name.strip().casefold()
            if key and (key in n or n in key):
                out.append(f"{row[1][:10]} {e.name} {e.effort_pct:g}% ({e.reason or '근거 없음'})")
    return out[:5]
