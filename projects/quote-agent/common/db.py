"""SQLite 저장 헬퍼(표준 라이브러리만). 이벤트(질문·결과·피드백 등)와 키-값을 저장한다.

규칙(발표용): 모든 쿼리는 파라미터 바인딩만 쓴다(문자열 이어붙이기 금지). DB 파일은 처음 쓸 때 만든다.
기본 경로: <프로젝트 루트>/data/app.db (APP_DB_PATH로 변경). *.db는 .gitignore 대상이다.
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from .usage_log import ROOT

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind, id);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Store:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or os.environ.get("APP_DB_PATH") or ROOT / "data" / "app.db")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        con.executescript(_SCHEMA)
        return con

    def _rows(self, sql: str, args: tuple = ()) -> list:
        if not self.path.exists():  # 읽기만 할 때 빈 DB를 만들지 않는다
            return []
        con = self._connect()
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()

    def add(self, kind: str, data: Any) -> int:
        con = self._connect()
        try:
            with con:
                cur = con.execute("INSERT INTO events(ts, kind, data) VALUES (?, ?, ?)",
                                  (datetime.now().isoformat(timespec="seconds"), kind,
                                   json.dumps(data, ensure_ascii=False, default=str)))
            return cur.lastrowid
        finally:
            con.close()

    def list(self, kind: Optional[str] = None, limit: int = 50) -> List[dict]:
        """최신순. [{id, ts, kind, data}]"""
        sql = "SELECT id, ts, kind, data FROM events"
        args: tuple = ()
        if kind is not None:
            sql += " WHERE kind = ?"
            args = (kind,)
        sql += " ORDER BY id DESC LIMIT ?"
        rows = self._rows(sql, args + (int(limit),))
        return [{"id": i, "ts": ts, "kind": k, "data": json.loads(d)} for i, ts, k, d in rows]

    def count(self, kind: Optional[str] = None) -> int:
        if kind is None:
            rows = self._rows("SELECT COUNT(*) FROM events")
        else:
            rows = self._rows("SELECT COUNT(*) FROM events WHERE kind = ?", (kind,))
        return rows[0][0] if rows else 0

    def kv_set(self, key: str, value: Any) -> None:
        con = self._connect()
        try:
            with con:
                con.execute("INSERT INTO kv(key, value) VALUES (?, ?) "
                            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                            (key, json.dumps(value, ensure_ascii=False, default=str)))
        finally:
            con.close()

    def kv_get(self, key: str, default: Any = None) -> Any:
        rows = self._rows("SELECT value FROM kv WHERE key = ?", (key,))
        return json.loads(rows[0][0]) if rows else default

    def clear(self, kind: Optional[str] = None) -> None:
        if not self.path.exists():
            return
        con = self._connect()
        try:
            with con:
                if kind is None:
                    con.execute("DELETE FROM events")
                else:
                    con.execute("DELETE FROM events WHERE kind = ?", (kind,))
        finally:
            con.close()
