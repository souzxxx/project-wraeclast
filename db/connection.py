"""Neon Postgres connection helpers + a tiny migration runner.

Uses psycopg 3. The DB layer is sync (psycopg) and called from async code via
asyncio.to_thread in the collectors — Neon connections are short-lived per task and
this keeps the data layer simple and testable.

CLI:
    python -m db.connection ping       # verify NEON_DATABASE_URL connects
    python -m db.connection migrate    # apply every db/migrations/*.sql in order
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from collector.config import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Yield a Neon connection with dict rows. Raises if NEON_DATABASE_URL is unset."""
    dsn = get_settings().neon_database_url
    if not dsn:
        raise RuntimeError("NEON_DATABASE_URL is not set — cannot connect to the database.")
    conn = psycopg.connect(dsn, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(query: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchall()


def execute(query: str, params: tuple[Any, ...] | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
        conn.commit()


def ping() -> bool:
    rows = fetch_all("SELECT 1 AS ok")
    return bool(rows and rows[0].get("ok") == 1)


def migrate() -> list[str]:
    """Apply all .sql files in db/migrations in lexical order. Idempotent (uses IF NOT EXISTS)."""
    applied: list[str] = []
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with get_connection() as conn:
        for path in files:
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            applied.append(path.name)
    return applied


def _main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "ping"
    if cmd == "ping":
        print("OK" if ping() else "FAILED")
        return 0
    if cmd == "migrate":
        for name in migrate():
            print(f"applied {name}")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
