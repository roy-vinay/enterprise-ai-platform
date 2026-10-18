"""SQLite access for the eval.

Two separate connection roles, kept deliberately apart (PRD 5.2 / 5.3):

- The *model under test* gets a read-only connection with a fixed query
  budget via ``ModelConnection``. It may only run SELECT/WITH.
- The *harness* (verification stage) uses ``verification_connection`` with
  no budget: running a case's ground-truth assertions is the harness's
  job, not the model's, and must never consume the model's tool budget.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_SQL = PKG_ROOT / "datasets" / "support" / "schema.sql"
SEED_SQL = PKG_ROOT / "datasets" / "support" / "seed.sql"
DEFAULT_DB_PATH = PKG_ROOT / "data" / "support.db"

_READ_ONLY_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE | re.DOTALL)


class QueryBudgetExceeded(Exception):
    pass


class ReadOnlyViolation(Exception):
    pass


def build_db(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    """(Re)build the deterministic support database from schema + seed."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
        con.executescript(SEED_SQL.read_text(encoding="utf-8"))
        con.commit()
    finally:
        con.close()
    return db_path


def verification_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Unbudgeted connection for the harness's verification stage."""
    return sqlite3.connect(db_path)


class QueryBudget:
    def __init__(self, limit: int = 10):
        self.limit = limit
        self.used = 0

    def spend(self) -> None:
        if self.used >= self.limit:
            raise QueryBudgetExceeded(
                f"query budget exhausted ({self.used}/{self.limit})"
            )
        self.used += 1


class ModelConnection:
    """What the model under test gets: read-only SQL + fixed tool budget."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH, budget: int = 10):
        self._con = sqlite3.connect(db_path)
        self._con.row_factory = sqlite3.Row
        self.budget = QueryBudget(budget)

    @staticmethod
    def _check_read_only(sql: str) -> None:
        # Strip leading SQL comments before checking the first keyword.
        stripped = re.sub(r"^\s*(--[^\n]*\n|/\*.*?\*/\s*)*", "", sql, flags=re.DOTALL)
        if not _READ_ONLY_RE.match(stripped):
            raise ReadOnlyViolation(
                "model connections may only run SELECT/WITH queries"
            )

    def query(self, sql: str):
        self._check_read_only(sql)
        self.budget.spend()
        return self._con.execute(sql).fetchall()

    def close(self) -> None:
        self._con.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build the support dataset.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()
    path = build_db(args.db)
    print(f"built {path}")


if __name__ == "__main__":
    main()
