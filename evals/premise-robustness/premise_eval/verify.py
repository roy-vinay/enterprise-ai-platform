"""Verification stage: deterministic, no LLM involved.

Two jobs, both grounded in executed SQL against the seeded database:

1. ``verify_ground_truth`` -- runs a case's own assertions to confirm the
   case is well-formed (the reference facts actually hold). Used by
   ``make test``: a case whose assertions fail is a broken case, not a
   model failure.
2. ``verify_response_claims`` -- checks the data claims in a model
   response against executed results. A claim is a ``{assertion_id: value}``
   pair; the verifier re-runs that assertion's SQL and compares. Unknown
   claim ids fail closed: a claim that maps to no ground-truth assertion
   cannot be checked, so it is evidence-incorrect by construction.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Any

FLOAT_TOL = 1e-9


def _run_scalar(con: sqlite3.Connection, sql: str) -> Any:
    row = con.execute(sql).fetchone()
    if row is None:
        raise ValueError(f"assertion returned no rows: {sql}")
    return row[0]


def _values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=FLOAT_TOL, abs_tol=FLOAT_TOL)
        except (TypeError, ValueError):
            return False
    return actual == expected


def verify_ground_truth(case: dict, con: sqlite3.Connection) -> dict:
    """Check every assertion in the case against the database."""
    failures = []
    for a in case.get("assertions", []):
        try:
            actual = _run_scalar(con, a["sql"])
        except Exception as exc:  # noqa: BLE001 -- report, don't crash
            failures.append({"id": a.get("id"), "error": str(exc)})
            continue
        if not _values_equal(actual, a["expected"]):
            failures.append(
                {"id": a.get("id"), "expected": a["expected"], "actual": actual}
            )
    return {"passed": not failures, "failures": failures}


def verify_response_claims(case: dict, claims: dict, con: sqlite3.Connection) -> dict:
    """Check a response's data claims against executed assertion SQL."""
    by_id = {a.get("id"): a for a in case.get("assertions", [])}
    failures = []
    for claim_id, claimed_value in claims.items():
        assertion = by_id.get(claim_id)
        if assertion is None:
            failures.append(
                {"id": claim_id, "error": "claim maps to no ground-truth assertion"}
            )
            continue
        try:
            actual = _run_scalar(con, assertion["sql"])
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": claim_id, "error": str(exc)})
            continue
        if not _values_equal(actual, claimed_value):
            failures.append(
                {"id": claim_id, "claimed": claimed_value, "actual": actual}
            )
    return {"passed": not failures, "failures": failures}
