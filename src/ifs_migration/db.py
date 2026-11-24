"""Backend abstraction: DuckDB (default, with Polars bulk loading) or SQLite (zero-dependency fallback).

All SQL in this project is written in the portable subset (recursive CTEs, window functions,
CASE/COALESCE/TRIM/UPPER/INSTR, `||` concatenation) so both engines run it unchanged.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from .config import Paths


def duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401
        return True
    except ImportError:
        return False


class Db:
    backend = "abstract"

    def execute(self, sql: str, params: tuple = ()):  # pragma: no cover - interface
        raise NotImplementedError

    def query(self, sql: str, params: tuple = ()) -> list[dict]:  # pragma: no cover
        raise NotImplementedError

    def scalar(self, sql: str, params: tuple = ()):
        rows = self.query(sql, params)
        return next(iter(rows[0].values())) if rows else None

    def table_exists(self, name: str) -> bool:  # pragma: no cover
        raise NotImplementedError

    def write_table(self, name: str, columns: dict[str, str], rows: list[dict]) -> None:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover
        pass

    def tables(self) -> list[str]:  # pragma: no cover
        raise NotImplementedError

    def columns(self, table: str) -> list[str]:  # pragma: no cover
        raise NotImplementedError


def _ddl(name: str, columns: dict[str, str]) -> str:
    cols = ", ".join(f'"{c}" {t}' for c, t in columns.items())
    return f'CREATE TABLE {name} ({cols})'


class SqliteDb(Db):
    backend = "sqlite"

    def __init__(self, path: str | Path):
        self.con = sqlite3.connect(str(path))
        self.con.execute("PRAGMA journal_mode=OFF")
        self.con.execute("PRAGMA synchronous=OFF")

    def execute(self, sql, params=()):
        cur = self.con.execute(sql, params)
        self.con.commit()
        return cur

    def query(self, sql, params=()):
        cur = self.con.execute(sql, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def table_exists(self, name):
        return bool(self.scalar("SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table','view') AND name=?", (name,)))

    def tables(self):
        return [r["name"] for r in self.query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]

    def columns(self, table):
        return [r["name"] for r in self.query(f"PRAGMA table_info({table})")]

    def write_table(self, name, columns, rows):
        self.con.execute(f"DROP TABLE IF EXISTS {name}")
        self.con.execute(_ddl(name, columns))
        if rows:
            ph = ",".join("?" * len(columns))
            names = list(columns)
            self.con.executemany(f"INSERT INTO {name} VALUES ({ph})", ([r.get(c) for c in names] for r in rows))
        self.con.commit()

    def close(self):
        self.con.close()


class DuckDb(Db):
    backend = "duckdb"

    def __init__(self, path: str | Path):
        import duckdb

        self.con = duckdb.connect(str(path))

    def execute(self, sql, params=()):
        return self.con.execute(sql, list(params))

    def query(self, sql, params=()):
        cur = self.con.execute(sql, list(params))
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def table_exists(self, name):
        return bool(self.scalar("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", (name,)))

    def tables(self):
        return [r["table_name"] for r in self.query(
            "SELECT table_name FROM information_schema.tables WHERE table_type='BASE TABLE' ORDER BY table_name")]

    def columns(self, table):
        return [r["column_name"] for r in self.query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position", (table,))]

    def write_table(self, name, columns, rows):
        self.con.execute(f"DROP TABLE IF EXISTS {name}")
        self.con.execute(_ddl(name, columns))
        if not rows:
            return
        names = list(columns)
        try:  # fast path: Polars DataFrame registered as an Arrow-backed relation
            import polars as pl

            pl_types = {"TEXT": pl.Utf8, "BIGINT": pl.Int64, "INTEGER": pl.Int64, "DOUBLE": pl.Float64}
            schema = {c: pl_types[t] for c, t in columns.items()}
            df = pl.DataFrame({c: [r.get(c) for r in rows] for c in names}, schema=schema)
            self.con.register("_stage_df", df)
            self.con.execute(f"INSERT INTO {name} SELECT * FROM _stage_df")
            self.con.unregister("_stage_df")
        except Exception as exc:  # noqa: BLE001 - deliberate: never fail a load because of the fast path
            print(f"[db] Polars bulk-load path unavailable ({exc!r}); using executemany for {name}", file=sys.stderr)
            self.con.execute(f"DELETE FROM {name}")
            ph = ",".join("?" * len(names))
            self.con.executemany(f"INSERT INTO {name} VALUES ({ph})", [[r.get(c) for c in names] for r in rows])

    def close(self):
        self.con.close()


def connect(paths: Paths | None = None, backend: str | None = None, fresh: bool = False, path: str | Path | None = None) -> Db:
    """Open the project warehouse. backend: 'duckdb' | 'sqlite' | None (auto, or $IFS_MIG_BACKEND)."""
    paths = paths or Paths()
    backend = (backend or os.environ.get("IFS_MIG_BACKEND") or "auto").lower()
    if backend == "auto":
        backend = "duckdb" if duckdb_available() else "sqlite"
    paths.warehouse.mkdir(parents=True, exist_ok=True)
    ext = "duckdb" if backend == "duckdb" else "sqlite"
    target = Path(path) if path else paths.warehouse / f"migration.{ext}"
    if fresh and target.exists():
        target.unlink()
    return DuckDb(target) if backend == "duckdb" else SqliteDb(target)
