"""Offline tests for db.connection — the Neon helpers + migration runner.

No live DB: psycopg.connect and get_settings are faked, so we exercise the dispatch
(DSN guard, cursor/commit/close wiring, the migration loop, ping, and the CLI) without
a network. Mirrors the offline-coverage approach used for the collector clients."""

from __future__ import annotations

import db.connection as dbc


class FakeCursor:
    def __init__(self, conn: FakeConn) -> None:
        self._conn = conn

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def execute(self, query: str, params: object = None) -> None:
        self._conn.executed.append((query, params))

    def fetchall(self) -> list[dict[str, object]]:
        return list(self._conn.rows)


class FakeConn:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[tuple[str, object]] = []
        self.commits = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closed = True


def _patch(monkeypatch, conn: FakeConn, dsn: str | None = "postgres://x") -> dict:
    """Wire psycopg.connect + get_settings to a fake conn; capture connect kwargs."""
    captured: dict = {}

    def fake_connect(dsn_arg: str, **kwargs: object) -> FakeConn:
        captured["dsn"] = dsn_arg
        captured["kwargs"] = kwargs
        return conn

    monkeypatch.setattr(dbc.psycopg, "connect", fake_connect)
    monkeypatch.setattr(dbc, "get_settings", lambda: type("S", (), {"neon_database_url": dsn})())
    return captured


# ── get_connection ───────────────────────────────────────────────────────────────

def test_get_connection_raises_without_dsn(monkeypatch):
    _patch(monkeypatch, FakeConn(), dsn=None)
    try:
        with dbc.get_connection():
            pass
    except RuntimeError as exc:
        assert "NEON_DATABASE_URL" in str(exc)
    else:  # pragma: no cover - the guard must fire
        raise AssertionError("expected RuntimeError when DSN unset")


def test_get_connection_yields_and_closes(monkeypatch):
    conn = FakeConn()
    captured = _patch(monkeypatch, conn, dsn="postgres://neon")
    with dbc.get_connection() as yielded:
        assert yielded is conn
        assert not conn.closed
    assert conn.closed  # closed in finally
    assert captured["dsn"] == "postgres://neon"
    assert captured["kwargs"]["row_factory"] is dbc.dict_row


def test_get_connection_closes_on_exception(monkeypatch):
    conn = FakeConn()
    _patch(monkeypatch, conn)
    try:
        with dbc.get_connection():
            raise ValueError("boom")
    except ValueError:
        pass
    assert conn.closed


# ── fetch_all / execute ──────────────────────────────────────────────────────────

def test_fetch_all_runs_query_and_returns_rows(monkeypatch):
    conn = FakeConn(rows=[{"ok": 1}])
    _patch(monkeypatch, conn)
    rows = dbc.fetch_all("SELECT 1 AS ok", ("a",))
    assert rows == [{"ok": 1}]
    assert conn.executed == [("SELECT 1 AS ok", ("a",))]


def test_fetch_all_defaults_params_to_empty_tuple(monkeypatch):
    conn = FakeConn(rows=[])
    _patch(monkeypatch, conn)
    assert dbc.fetch_all("SELECT 1") == []
    assert conn.executed == [("SELECT 1", ())]


def test_execute_commits(monkeypatch):
    conn = FakeConn()
    _patch(monkeypatch, conn)
    dbc.execute("INSERT INTO t VALUES (%s)", (1,))
    assert conn.executed == [("INSERT INTO t VALUES (%s)", (1,))]
    assert conn.commits == 1
    assert conn.closed


def test_execute_defaults_params(monkeypatch):
    conn = FakeConn()
    _patch(monkeypatch, conn)
    dbc.execute("DELETE FROM t")
    assert conn.executed == [("DELETE FROM t", ())]


# ── ping ─────────────────────────────────────────────────────────────────────────

def test_ping_true_when_select_one(monkeypatch):
    _patch(monkeypatch, FakeConn(rows=[{"ok": 1}]))
    assert dbc.ping() is True


def test_ping_false_when_no_rows(monkeypatch):
    _patch(monkeypatch, FakeConn(rows=[]))
    assert dbc.ping() is False


def test_ping_false_when_wrong_value(monkeypatch):
    _patch(monkeypatch, FakeConn(rows=[{"ok": 0}]))
    assert dbc.ping() is False


# ── migrate ──────────────────────────────────────────────────────────────────────

def test_migrate_applies_every_sql_file_in_order(monkeypatch):
    conn = FakeConn()
    _patch(monkeypatch, conn)
    applied = dbc.migrate()
    expected = [p.name for p in sorted(dbc.MIGRATIONS_DIR.glob("*.sql"))]
    assert applied == expected
    assert expected  # the repo ships migrations
    # one execute + one commit per migration file, in lexical order
    assert [q for q, _ in conn.executed] != []
    assert len(conn.executed) == len(expected)
    assert conn.commits == len(expected)


def test_migrate_uses_a_tmp_dir(monkeypatch, tmp_path):
    (tmp_path / "0002_b.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "0001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    conn = FakeConn()
    _patch(monkeypatch, conn)
    monkeypatch.setattr(dbc, "MIGRATIONS_DIR", tmp_path)
    assert dbc.migrate() == ["0001_a.sql", "0002_b.sql"]
    assert [q for q, _ in conn.executed] == ["SELECT 1;", "SELECT 2;"]


# ── _main dispatch ───────────────────────────────────────────────────────────────

def test_main_ping_ok(monkeypatch, capsys):
    monkeypatch.setattr(dbc, "ping", lambda: True)
    assert dbc._main(["prog", "ping"]) == 0
    assert capsys.readouterr().out.strip() == "OK"


def test_main_ping_failed(monkeypatch, capsys):
    monkeypatch.setattr(dbc, "ping", lambda: False)
    assert dbc._main(["prog", "ping"]) == 0
    assert capsys.readouterr().out.strip() == "FAILED"


def test_main_defaults_to_ping(monkeypatch, capsys):
    monkeypatch.setattr(dbc, "ping", lambda: True)
    assert dbc._main(["prog"]) == 0
    assert capsys.readouterr().out.strip() == "OK"


def test_main_migrate_prints_each(monkeypatch, capsys):
    monkeypatch.setattr(dbc, "migrate", lambda: ["0001_init.sql", "0002_x.sql"])
    assert dbc._main(["prog", "migrate"]) == 0
    out = capsys.readouterr().out
    assert "applied 0001_init.sql" in out
    assert "applied 0002_x.sql" in out


def test_main_unknown_command(monkeypatch, capsys):
    assert dbc._main(["prog", "bogus"]) == 2
    assert "unknown command: bogus" in capsys.readouterr().err
