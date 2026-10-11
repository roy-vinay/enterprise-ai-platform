"""Semantic model mutation testing: does the eval actually protect you?

A passing eval only means something if it would fail when the semantic model
breaks. This module breaks the model on purpose, one plausible human mistake at
a time (drop a filter, change an aggregation, point a metric at the wrong date
column, remove a global filter), reruns the suite, and records whether any test
noticed. A mutant that no test notices is a blind spot.

The bot used here should behave perfectly on the original model, so that any
new failure is caused by the mutation and nothing else.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Callable

from . import metamorphic, semantic
from .db import Warehouse
from .grade import grade_suite


@dataclass
class MutantResult:
    id: str
    operator: str
    target: str
    description: str
    killed: bool
    killed_by_cases: list[str]
    killed_by_relations: list[str]
    # For survivors: "blind_spot" (the metric really changed and no test noticed)
    # or "equivalent_on_current_data" (the change makes no difference to today's
    # data, e.g. a redundant filter; harmless now, unprotected if the data shifts).
    verdict: str = "killed"

    def to_dict(self):
        return asdict(self)


def run(model: dict, cases: list[dict], relations: list[dict],
        bot_factory: Callable[[dict], object], wh: Warehouse) -> list[MutantResult]:
    base_bot = bot_factory(model)
    base_cases = {r.case_id: r.passed for r in grade_suite(cases, base_bot, wh, model, n_runs=1)}
    base_rels = {r.id: r.status for r in metamorphic.run_all(relations, cases, base_bot, wh,
                                                             include_generated=False)}
    out = []
    for m in semantic.mutants(model):
        bot = bot_factory(m.model)
        # Grade against the ORIGINAL model's rules: the reference is the truth, not the mutant.
        res = grade_suite(cases, bot, wh, model, n_runs=1)
        by_cases = [r.case_id for r in res if base_cases.get(r.case_id) and not r.passed]
        rels = metamorphic.run_all(relations, cases, bot, wh, include_generated=False)
        by_rels = [r.id for r in rels if base_rels.get(r.id) == "holds" and r.status == "violated"]
        killed = bool(by_cases or by_rels)
        verdict = "killed" if killed else (
            "equivalent_on_current_data" if _equivalent(model, m.model, m.target, wh) else "blind_spot")
        out.append(MutantResult(m.id, m.operator, m.target, m.description,
                                killed, by_cases, by_rels, verdict))
    return out


def _probe_sql(model: dict, name: str) -> str:
    met = model["metrics"][name]
    return (f"SELECT date_trunc('month', {met['time_column']}) AS m, {semantic.agg_sql(met)} "
            f"FROM {met['table']} WHERE {semantic.where_sql(model, name)} GROUP BY 1 ORDER BY 1")


def _equivalent(original: dict, mutant: dict, target: str, wh: Warehouse) -> bool:
    """Does the mutated metric give identical monthly values on the current data?"""
    names = list(original["metrics"]) if target == "*" else [target]
    for n in names:
        a, b = wh.run(_probe_sql(original, n)), wh.run(_probe_sql(mutant, n))
        if a.error or b.error or a.rows != b.rows:
            return False
    return True


def coverage(model: dict, cases: list[dict], mutants: list[MutantResult]) -> list[dict]:
    """Per metric: how many cases exercise it and how many of its mutants were caught."""
    n_cases = defaultdict(int)
    for c in cases:
        for m in c.get("metrics", []):
            n_cases[m] += 1
    killed, total, blind = defaultdict(int), defaultdict(int), defaultdict(int)
    for mu in mutants:
        total[mu.target] += 1
        killed[mu.target] += mu.killed
        blind[mu.target] += mu.verdict == "blind_spot"
    rows = []
    for name in list(model["metrics"]) + (["*"] if total.get("*") else []):
        rows.append({"metric": name if name != "*" else "(global filters)",
                     "cases": n_cases.get(name, 0) if name != "*" else len(cases),
                     "mutants": total.get(name, 0), "killed": killed.get(name, 0),
                     "blind_spots": blind.get(name, 0),
                     "mutation_score": (killed[name] / total[name]) if total.get(name) else None})
    return rows
