"""Rule-based checks on the bot's SQL.

These catch structural mistakes even when the number happens to look right,
and they explain *why* a result is wrong, which tells you who should fix it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from .semantic import TABLES_WITH_ACCOUNT_ID

_MONTHS = ("january february march april may june july august september october "
           "november december jan feb mar apr jun jul aug sep sept oct nov dec").split()
_RELATIVE = ("last month", "this month", "this quarter", "last quarter", "year-to-date",
             "year to date", "ytd", "current", "today", "yesterday", "last year")


@dataclass
class Finding:
    rule: str
    detail: str
    owner: str  # who usually fixes it: semantic_model | prompt | app


def _literals(tree: exp.Expression) -> set[str]:
    """String literals used in WHERE comparisons (=, IN)."""
    out = set()
    for node in tree.find_all(exp.EQ, exp.In):
        for lit in node.find_all(exp.Literal):
            if lit.is_string and not re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", lit.this):
                out.add(lit.this)  # dates are checked by the result comparison instead
    return out


def _model_literals(model: dict) -> set[str]:
    lits = set()
    for m in model["metrics"].values():
        for f in m.get("filters", []):
            lits.update(re.findall(r"'([^']*)'", f))
    return lits


def _grounded(literal: str, question: str, model: dict) -> bool:
    q = question.lower()
    if literal in _model_literals(model):
        return True
    if literal.lower() in q:
        return True
    for d in model["dimensions"].values():
        for syn in (d.get("synonyms") or {}).get(literal, []):
            if syn.lower() in q:
                return True
    tokens = [t for t in re.split(r"[_\s-]+", literal.lower()) if len(t) >= 4]
    return any(t in q for t in tokens)


def check(question: str, sql: str | None, model: dict, truncated: bool = False) -> list[Finding]:
    if not sql:
        return []
    findings: list[Finding] = []
    low = sql.lower()
    try:
        tree = sqlglot.parse_one(sql, read="duckdb")
    except Exception as e:
        return [Finding("unparseable_sql", str(e).splitlines()[0], "prompt")]

    tables = {t.name.lower() for t in tree.find_all(exp.Table)}

    # 1. Silent substitution: a filter value the question never asked for.
    for lit in sorted(_literals(tree)):
        if not _grounded(lit, question, model):
            findings.append(Finding("ungrounded_filter_value",
                                    f"filters on '{lit}', which the question does not mention",
                                    "prompt"))

    # 2. Test accounts must be excluded everywhere.
    # Owner: if the model already defines the filter, the bot ignored it (prompt);
    # if it does not, the model needs it (semantic_model).
    model_text = str(model).lower()
    if tables & TABLES_WITH_ACCOUNT_ID and "is_test" not in low:
        findings.append(Finding("missing_test_exclusion",
                                "query does not exclude internal test accounts",
                                "prompt" if "is_test" in model_text else "semantic_model"))

    # 3. Soft-deleted invoices must be excluded.
    if "invoices" in tables and "is_deleted" not in low:
        findings.append(Finding("missing_soft_delete_filter",
                                "invoices queried without is_deleted filter",
                                "prompt" if "is_deleted" in model_text else "semantic_model"))

    # 4. SUM of a column that is also grouped by (double counting / nonsense totals).
    group_cols = {c.name.lower() for g in tree.find_all(exp.Group) for c in g.find_all(exp.Column)}
    for s in tree.find_all(exp.Sum):
        for c in s.find_all(exp.Column):
            if c.name.lower() in group_cols:
                findings.append(Finding("sum_of_grouped_column",
                                        f"SUM({c.name}) while also grouping by {c.name}",
                                        "semantic_model"))

    # 5. Summing a snapshot metric across months (MRR is point-in-time).
    if "mrr_monthly" in tables and re.search(r"sum\s*\(\s*mrr_usd", low):
        ranged = re.search(r"\bmonth\s*(>=|>|between)", low)
        grouped_by_month = "month" in group_cols
        if ranged and not grouped_by_month:
            findings.append(Finding("snapshot_summed_across_time",
                                    "MRR summed over a range of months",
                                    "prompt" if "never across months" in model_text else "semantic_model"))

    # 6. The question names a period but the SQL has no date filter.
    q = question.lower()
    mentions_time = bool(re.search(r"\b20\d\d\b|\bq[1-4]\b", q)) or \
        any(re.search(rf"\b{m}\b", q) for m in _MONTHS) or any(r in q for r in _RELATIVE)
    if mentions_time and not re.search(r"date\s*'|\d{4}-\d{2}-\d{2}|current_date|date_trunc", low):
        findings.append(Finding("missing_time_filter",
                                "question names a period but SQL has no date filter", "prompt"))

    # 7. Results cut off at the row cap without telling the user.
    if truncated:
        findings.append(Finding("silent_truncation", "result hit the row cap", "app"))

    return findings
