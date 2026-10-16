import datetime
import decimal
import threading
import time
import types

import psycopg
import pytest

from hub_mcp.db import Db, QueryError, clamp, like_tokens, to_jsonable


def test_to_jsonable_converts_nested_values():
    value = {
        "n": decimal.Decimal("1.5"),
        "d": datetime.date(2026, 10, 14),
        "t": datetime.datetime(2026, 10, 14, 7, 0, tzinfo=datetime.timezone.utc),
        "list": [decimal.Decimal("2"), {"x": datetime.date(2026, 1, 1)}],
        "s": "text",
        "none": None,
    }
    assert to_jsonable(value) == {
        "n": 1.5,
        "d": "2026-10-14",
        "t": "2026-10-14T07:00:00+00:00",
        "list": [2.0, {"x": "2026-01-01"}],
        "s": "text",
        "none": None,
    }


def test_clamp():
    assert clamp(10000, 1, 250) == 250
    assert clamp(0, 1, 250) == 1
    assert clamp(20, 1, 250) == 20


def test_like_tokens_split_and_escape():
    assert like_tokens("  판교 테스트단지 ") == ["%판교%", "%테스트단지%"]
    assert like_tokens("50%_off") == [r"%50\%\_off%"]


def test_like_tokens_rejects_blank():
    with pytest.raises(QueryError, match="검색어"):
        like_tokens("   ")


def test_missing_url_names_the_env_variable():
    db = Db(None, "RichRich", "RICHRICH_DATABASE_URL")
    with pytest.raises(QueryError, match="RICHRICH_DATABASE_URL"):
        db.all("select 1")


class FlakyDb(Db):
    """Db whose first query fails the way a pooler-dropped connection does."""

    def __init__(self, failures: list[Exception]):
        super().__init__("postgresql://unused", "RichRich", "RICHRICH_DATABASE_URL")
        self.failures = failures
        self.closed_times = 0

    def _run(self, sql, params):
        if self.failures:
            raise self.failures.pop(0)
        return [{"ok": 1}]

    def close(self):
        self.closed_times += 1


def test_reconnects_once_after_dropped_connection():
    db = FlakyDb([psycopg.OperationalError("server closed the connection unexpectedly")])
    assert db.all("select 1") == [{"ok": 1}]
    assert db.closed_times == 1


def test_second_connection_failure_becomes_query_error_without_url():
    db = FlakyDb([psycopg.OperationalError("password=secret"), psycopg.OperationalError("password=secret")])
    with pytest.raises(QueryError) as info:
        db.all("select 1")
    assert "연결하지 못했습니다" in str(info.value)
    assert "secret" not in str(info.value)


def test_timeout_becomes_query_error():
    db = FlakyDb([psycopg.errors.QueryCanceled("canceling statement due to statement timeout")])
    with pytest.raises(QueryError, match="범위를 줄여"):
        db.all("select 1")


def test_live_select_runs_read_only(apt_db):
    assert apt_db.all("select 1 as x") == [{"x": 1}]
    assert apt_db.one("show transaction_read_only") == {"transaction_read_only": "on"}


def test_live_writes_are_rejected(apt_db):
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        apt_db.all("create temp table hub_probe (x int)")
    assert apt_db.all("select 2 as x") == [{"x": 2}]  # connection still usable afterwards


class SlowDb(Db):
    """Db whose queries take a moment, recording how many ran at once."""

    def __init__(self):
        super().__init__("postgresql://unused", "RichRich", "RICHRICH_DATABASE_URL")
        self.active = 0
        self.peak = 0

    def _run(self, sql, params):
        self.active += 1
        self.peak = max(self.peak, self.active)
        time.sleep(0.05)
        self.active -= 1
        return [{"ok": 1}]


def test_parallel_tool_calls_never_share_the_connection_at_once():
    # MCPServer runs sync tools in worker threads, so Claude's parallel calls hit one Db concurrently.
    db = SlowDb()
    threads = [threading.Thread(target=db.all, args=("select 1",)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert db.peak == 1


def test_connection_uses_tcp_keepalives(monkeypatch):
    captured = {}

    def fake_connect(url, **kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(closed=False)

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    Db("postgresql://unused", "RichRich", "RICHRICH_DATABASE_URL")._connection()
    assert captured["keepalives"] == 1
    assert captured["keepalives_idle"] == 30


def test_live_parallel_queries_leave_connection_idle(apt_db):
    errors = []

    def query():
        try:
            for _ in range(5):
                apt_db.all("select count(*) as n from apt.sgg")
        except Exception as e:  # collected and asserted below
            errors.append(e)

    threads = [threading.Thread(target=query) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert apt_db._conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE
