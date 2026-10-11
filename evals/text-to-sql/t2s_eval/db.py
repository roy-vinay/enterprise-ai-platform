"""Run queries against the warehouse and compare result sets."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import duckdb


@dataclass
class QueryResult:
    rows: list[tuple] | None
    error: str | None = None
    truncated: bool = False


_NOW = re.compile(r"\bcurrent_date\b|\bcurrent_timestamp\b|\bnow\s*\(\s*\)|\btoday\s*\(\s*\)",
                  re.IGNORECASE)


class Warehouse:
    def __init__(self, path: str, row_cap: int = 100, as_of: str = "2026-10-01"):
        self.con = duckdb.connect(path, read_only=True)
        self.row_cap = row_cap
        self.as_of = as_of

    def run(self, sql: str | None) -> QueryResult:
        if not sql:
            return QueryResult(None, "no sql")
        # The eval's "today" is frozen; a query that reads the wall clock gets that date,
        # so results do not change depending on when the eval runs.
        sql = _NOW.sub(f"DATE '{self.as_of}'", sql)
        try:
            rows = self.con.execute(sql).fetchmany(self.row_cap + 1)
        except Exception as e:
            return QueryResult(None, f"{type(e).__name__}: {str(e).splitlines()[0]}")
        truncated = len(rows) > self.row_cap
        return QueryResult(rows[: self.row_cap], truncated=truncated)


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        from decimal import Decimal
        if isinstance(v, Decimal):
            return float(v)
    except ImportError:
        pass
    return None


def _fmt(v) -> str:
    if v is None:
        return "null"
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.4g}"


def _close(a, b, tol: float) -> bool:
    na, nb = _num(a), _num(b)
    if na is None or nb is None:
        if a is None and b is None:
            return True
        return str(a).strip().lower() == str(b).strip().lower()
    if math.isnan(na) or math.isnan(nb):
        return False
    if na == nb:
        return True
    return abs(na - nb) <= tol * max(abs(na), abs(nb), 1e-9)


def _row_close(r1: tuple, r2: tuple, tol: float) -> bool:
    return len(r1) == len(r2) and all(_close(a, b, tol) for a, b in zip(r1, r2))


def _key(row: tuple) -> tuple:
    """Sort key using the non-numeric (label) columns, then numbers."""
    labels = tuple(str(v).lower() for v in row if _num(v) is None)
    nums = tuple(round(_num(v), 6) for v in row if _num(v) is not None)
    return labels + tuple(map(str, nums))


def scalar(rows: list[tuple] | None):
    """The single value of a one-row result, else None. Tolerates an extra label column."""
    if not rows or len(rows) != 1:
        return None
    nums = [_num(v) for v in rows[0] if _num(v) is not None]
    return nums[-1] if nums else None


def compare(expected: list[tuple], actual: list[tuple] | None, mode: str, tol: float) -> tuple[bool, str]:
    if actual is None:
        return False, "bot query failed"
    if mode == "scalar":
        e, a = scalar(expected), scalar(actual)
        if a is None:
            if len(actual) == 1:
                return False, f"expected {_fmt(e)}, got no value (NULL)"
            return False, f"expected one value, got {len(actual)} rows"
        ok = _close(e, a, tol)
        return ok, "" if ok else f"expected {_fmt(e)}, got {_fmt(a)}"
    if mode == "set":
        if len(expected) != len(actual):
            return False, f"expected {len(expected)} rows, got {len(actual)}"
        for e, a in zip(sorted(expected, key=_key), sorted(actual, key=_key)):
            if not _row_close(e, a, tol):
                return False, f"row mismatch: expected {e}, got {a}"
        return True, ""
    if mode == "top_n_ordered":
        if len(expected) != len(actual):
            return False, f"expected {len(expected)} rows, got {len(actual)}"
        for i, (e, a) in enumerate(zip(expected, actual)):
            if not _row_close(e, a, tol):
                return False, f"rank {i + 1}: expected {e}, got {a}"
        return True, ""
    raise ValueError(f"unknown compare mode {mode}")


def fingerprint(rows: list[tuple] | None, ordered: bool = False) -> str:
    """Stable signature of a result, for agreement across runs.

    Row order is ignored unless `ordered` is set; rankings must keep it, or a
    correctly ordered and a wrongly ordered top-N would look identical.
    """
    if rows is None:
        return "<error>"
    norm = [tuple(round(_num(v), 4) if _num(v) is not None else str(v).lower() for v in r)
            for r in rows]
    return repr(norm if ordered else sorted(norm, key=str))
