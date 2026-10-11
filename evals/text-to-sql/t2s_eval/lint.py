"""Lint the trap set itself: can each case actually tell right from wrong?

A test case is only useful if a plausible wrong answer fails it. Two checks:

1. Tempting answer: the case's tempting_sql must produce a different result
   from reference_sql (beyond tolerance). Otherwise the trap catches nothing.
2. Window sensitivity: shifting the reference query's dates by one month must
   change the result beyond tolerance. Smooth metrics (MRR moves a fraction of
   a percent month to month) can pass a wrong month under a loose tolerance.
   Fault injection surfaced exactly this: an off-by-one-month MRR answer passed
   under a 0.1% tolerance.
3. Trust traps: a case whose tempting_fault names a trust check (restricted
   access, over-scan, write, external access) may return the right result on
   purpose. Its tempting query must instead trip that check, or the case
   protects nothing.
"""
from __future__ import annotations

from . import policy
from .bots.simulated import _shift_month_back
from .db import Warehouse, compare

TRUST_FAULTS = {"restricted_access", "over_scan", "write_attempt", "external_access"}


def trust_trap_fires(c: dict, wh: Warehouse, model: dict) -> bool:
    """Does the case's tempting query trip the check its tempting_fault names?"""
    sql, fault = c["tempting_sql"], c["tempting_fault"]
    if fault in ("write_attempt", "external_access"):
        return any(f.rule == fault for f in policy.check_safety(sql))
    if policy.check_safety(sql):
        return False  # never execute an unsafe query, even in the linter
    if fault == "restricted_access":
        return bool(policy.check_access(sql, model))
    if fault == "over_scan":
        return bool(policy.check_cost(sql, wh.run(sql).rows_scanned, c, model))
    return False


def lint(cases: list[dict], wh: Warehouse, model: dict | None = None) -> list[dict]:
    issues = []
    for c in cases:
        if c.get("tempting_fault") in TRUST_FAULTS:
            if model is None:
                issues.append({"case": c["id"], "issue": "no_model",
                               "detail": "trust traps need the semantic model to lint"})
            elif not trust_trap_fires(c, wh, model):
                issues.append({"case": c["id"], "issue": "trust_trap_silent",
                               "detail": f"the tempting query does not trip {c['tempting_fault']}"})
        ref_sql = c.get("reference_sql")
        if not ref_sql or c["compare"] == "none":
            continue
        ref = wh.run(ref_sql)
        if ref.error:
            issues.append({"case": c["id"], "issue": "reference_error", "detail": ref.error})
            continue
        tol = c.get("tolerance", 0)
        if c.get("tempting_sql") and c.get("tempting_fault") not in TRUST_FAULTS:
            t = wh.run(c["tempting_sql"])
            if t.rows is not None and compare(ref.rows, t.rows, c["compare"], tol)[0]:
                issues.append({"case": c["id"], "issue": "tempting_answer_passes",
                               "detail": "the tempting query returns the same result"})
        shifted_sql = _shift_month_back(ref_sql)
        if shifted_sql != ref_sql:
            s = wh.run(shifted_sql)
            if s.rows is not None and compare(ref.rows, s.rows, c["compare"], tol)[0]:
                issues.append({"case": c["id"], "issue": "window_insensitive",
                               "detail": f"a one-month-earlier window also passes at tolerance {tol}"})
    return issues
