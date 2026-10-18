"""Verification stage: deterministic, no LLM involved.

Two jobs, both grounded in executed SQL against the seeded database:

1. ``verify_ground_truth`` -- runs a case's own assertions to confirm the
   case is well-formed (the reference facts actually hold). Used by
   ``make test``: a case whose assertions fail is a broken case, not a
   model failure.
2. ``verify_response_claims`` -- checks the data claims in a model
   response against executed results. A claim is a ``{assertion_id: value}``
   pair; the verifier re-runs that assertion's SQL against the LIVE database
   and compares the claim to the actual result. The fixture's expected value
   is never trusted at eval time: if the live result diverges from the
   fixture, the divergence is reported as ``stale_ground_truth`` (a case
   bug, caught by ``make test`` at CI time) while the claim itself is still
   graded against reality. Unknown claim ids fail closed: a claim that maps
   to no ground-truth assertion cannot be checked, so it is
   evidence-incorrect by construction.
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


def _run_rows(con: sqlite3.Connection, sql: str) -> list:
    return [list(r) for r in con.execute(sql).fetchall()]


def _values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=FLOAT_TOL, abs_tol=FLOAT_TOL)
        except (TypeError, ValueError):
            return False
    return actual == expected


def _rows_equal(actual: list, expected: list) -> bool:
    """Multiset comparison of result rows, with float tolerance per cell.

    A scalar verifier (row[0] only) cannot pin membership facts: e.g.
    SELECT DISTINCT customer_id ... still returns the expected first row after
    a second customer appears. expected_rows compares the whole set.
    """
    if len(actual) != len(expected):
        return False
    unmatched = [list(r) for r in expected]
    for arow in actual:
        for i, erow in enumerate(unmatched):
            if len(arow) == len(erow) and all(
                _values_equal(a, e) for a, e in zip(arow, erow)
            ):
                del unmatched[i]
                break
        else:
            return False
    return True


def _check_assertion(a: dict, con: sqlite3.Connection) -> tuple:
    """Run one assertion. Returns (passed: bool, actual: Any)."""
    if "expected_rows" in a:
        actual = _run_rows(con, a["sql"])
        return _rows_equal(actual, a["expected_rows"]), actual
    actual = _run_scalar(con, a["sql"])
    return _values_equal(actual, a["expected"]), actual


def verify_ground_truth(case: dict, con: sqlite3.Connection) -> dict:
    """Check every assertion in the case against the database."""
    failures = []
    for a in case.get("assertions", []):
        try:
            passed, actual = _check_assertion(a, con)
        except Exception as exc:  # noqa: BLE001 -- report, don't crash
            failures.append({"id": a.get("id"), "error": str(exc)})
            continue
        if not passed:
            failures.append(
                {
                    "id": a.get("id"),
                    "expected": a.get("expected", a.get("expected_rows")),
                    "actual": actual,
                }
            )
    return {"passed": not failures, "failures": failures}


def verify_response_claims(case: dict, claims: dict, con: sqlite3.Connection) -> dict:
    """Check a response's data claims against live executed assertion SQL.

    Each claim is compared to the ACTUAL query result, never to the
    fixture's expected value. Fixture/live divergence is reported
    separately as stale ground truth.
    """
    by_id = {a.get("id"): a for a in case.get("assertions", [])}
    failures = []
    stale = []
    for claim_id, claimed_value in claims.items():
        assertion = by_id.get(claim_id)
        if assertion is None:
            failures.append(
                {"id": claim_id, "error": "claim maps to no ground-truth assertion"}
            )
            continue
        try:
            passed_vs_fixture, actual = _check_assertion(assertion, con)
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": claim_id, "error": str(exc)})
            continue
        if not passed_vs_fixture:
            stale.append(
                {
                    "id": claim_id,
                    "fixture": assertion.get("expected", assertion.get("expected_rows")),
                    "live": actual,
                }
            )
        if "expected_rows" in assertion:
            claimed_rows = [list(r) for r in claimed_value]
            if not _rows_equal(claimed_rows, actual):
                failures.append(
                    {"id": claim_id, "claimed": claimed_value, "actual": actual}
                )
        elif not _values_equal(actual, claimed_value):
            failures.append(
                {"id": claim_id, "claimed": claimed_value, "actual": actual}
            )
    return {"passed": not failures, "failures": failures, "stale_ground_truth": stale}
