"""Read-only Postgres access shared by every tool."""
from __future__ import annotations

import datetime
import decimal
import sys
import threading
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row

STATEMENT_TIMEOUT_MS = 5000


class QueryError(Exception):
    """A problem the person asking should read as-is: unknown name, several matches, missing setup."""


class Reader(Protocol):
    def all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...

    def one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None: ...


def to_jsonable(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, datetime.date):  # datetime is a date subclass
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def like_tokens(text: str) -> list[str]:
    """ILIKE ALL patterns: every whitespace-separated word must appear (names are compared without spaces)."""
    tokens = text.split()
    if not tokens:
        raise QueryError("검색어를 입력해 주세요.")
    escaped = (t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") for t in tokens)
    return [f"%{t}%" for t in escaped]


class Db:
    """One lazily opened connection; every query runs in its own READ ONLY transaction."""

    def __init__(self, url: str | None, label: str, env_name: str):
        self._url = url
        self._label = label
        self._env_name = env_name
        self._conn: psycopg.Connection | None = None
        # MCPServer runs sync tools in worker threads; one psycopg connection must not run two transactions at once.
        self._lock = threading.Lock()

    def all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            with self._lock:
                return self._run_with_reconnect(sql, params)
        except psycopg.errors.QueryCanceled as e:
            raise QueryError(
                f"{self._label} 조회가 {STATEMENT_TIMEOUT_MS // 1000}초를 넘겨 중단됐습니다. 범위를 줄여 다시 물어봐 주세요."
            ) from e
        except psycopg.OperationalError as e:
            print(f"{self._label} DB unavailable: {type(e).__name__}", file=sys.stderr)
            raise QueryError(f"{self._label} DB에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요.") from e

    def one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _connection(self) -> psycopg.Connection:
        if not self._url:
            raise QueryError(
                f"{self._env_name}가 설정되지 않아 {self._label} 데이터를 읽을 수 없습니다. my-hub/.env를 확인해 주세요."
            )
        if self._conn is None or self._conn.closed:
            # autocommit so `transaction()` opens a real top-level transaction;
            # prepare_threshold=None because Supabase's pooler cannot keep prepared statements;
            # keepalives so a connection silently dropped by a NAT fails fast instead of hanging on TCP retries.
            self._conn = psycopg.connect(
                self._url,
                autocommit=True,
                prepare_threshold=None,
                row_factory=dict_row,
                connect_timeout=10,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3,
            )
        return self._conn

    def _run_with_reconnect(self, sql: str, params: dict[str, Any] | None) -> list[dict[str, Any]]:
        try:
            return self._run(sql, params)
        except psycopg.errors.QueryCanceled:
            raise  # a slow query would only be slow again
        except psycopg.OperationalError as first:
            # The pooler drops idle connections while a Claude session sits open; retry once on a fresh one.
            print(f"{self._label} DB reconnecting after: {type(first).__name__}", file=sys.stderr)
            self.close()
            return self._run(sql, params)

    def _run(self, sql: str, params: dict[str, Any] | None) -> list[dict[str, Any]]:
        conn = self._connection()
        with conn.transaction():
            conn.execute("set transaction read only")
            conn.execute(f"set local statement_timeout = {STATEMENT_TIMEOUT_MS}")
            rows = conn.execute(sql, params or {}).fetchall()
        return [to_jsonable(row) for row in rows]
