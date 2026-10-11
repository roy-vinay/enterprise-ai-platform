"""Lint the trap set itself: can each case actually tell right from wrong?

A test case is only useful if a plausible wrong answer fails it. Two checks:

1. Tempting answer: the case's tempting_sql must produce a different result
   from reference_sql (beyond tolerance). Otherwise the trap catches nothing.
2. Window sensitivity: shifting the reference query's dates by one month must
   change the result beyond tolerance. Smooth metrics (MRR moves a fraction of
   a percent month to month) can pass a wrong month under a loose tolerance.
   Fault injection surfaced exactly this: an off-by-one-month MRR answer passed
   under a 0.1% tolerance.
"""
from __future__ import annotations

from .bots.simulated import _shift_month_back
from .db import Warehouse, compare


def lint(cases: list[dict], wh: Warehouse) -> list[dict]:
    issues = []
    for c in cases:
        ref_sql = c.get("reference_sql")
        if not ref_sql or c["compare"] == "none":
            continue
        ref = wh.run(ref_sql)
        if ref.error:
            issues.append({"case": c["id"], "issue": "reference_error", "detail": ref.error})
            continue
        tol = c.get("tolerance", 0)
        if c.get("tempting_sql"):
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
