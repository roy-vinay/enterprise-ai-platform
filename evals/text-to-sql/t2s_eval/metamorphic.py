"""Metamorphic testing: consistency checks that need no reference answers."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .bots.base import Bot
from .db import Warehouse, _num, compare, scalar

EPS = 1e-6


def _f(v: float) -> str:
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.4g}"


@dataclass
class RelationResult:
    id: str
    type: str
    why: str
    status: str            # holds | violated | inconclusive
    detail: str
    generated: bool = False

    def to_dict(self):
        return asdict(self)


def paraphrases(question: str) -> list[str]:
    """Surface rewrites that must not change the answer."""
    q = question.rstrip("?")
    lower_first = q[0].lower() + q[1:]
    return [f"Quick question: {question}", f"{q} please?", f"Hey bot, {lower_first}?"]


def generated_relations(cases: list[dict]) -> list[dict]:
    out = []
    for c in cases:
        if c["expected_behavior"] == "answer":
            out.append({"id": f"p-{c['id']}", "type": "equivalent", "generated": True,
                        "why": f"surface paraphrases of {c['id']}",
                        "questions": [c["question"], *paraphrases(c["question"])]})
    return out


def _sum_last_numeric(rows):
    total = 0.0
    for r in rows:
        nums = [_num(v) for v in r if _num(v) is not None]
        if not nums:
            return None
        total += nums[-1]
    return total


def check_relation(rel: dict, bot: Bot, wh: Warehouse, run: int = 0) -> RelationResult:
    def ask(q):
        resp = bot.ask(q, run=run)
        if resp.action != "answer":
            return resp.action, None
        return "answer", wh.run(resp.sql).rows

    mk = lambda status, detail: RelationResult(rel["id"], rel["type"], rel.get("why", ""),
                                               status, detail, rel.get("generated", False))
    t = rel["type"]

    if t in ("equivalent", "monotonic"):
        outs = [ask(q) for q in rel["questions"]]
        actions = {a for a, _ in outs}
        if t == "equivalent":
            if len(actions) > 1:
                return mk("violated", f"mixed behavior across phrasings: {sorted(actions)}")
            if actions != {"answer"}:
                return mk("holds", f"consistently {actions.pop()}")
            first = outs[0][1]
            mode = "scalar" if first is not None and len(first) == 1 else "set"
            for q, (_, rows) in zip(rel["questions"][1:], outs[1:]):
                if first is None or rows is None:
                    return mk("violated", "a phrasing produced a failing query")
                ok, why = compare(first, rows, mode, EPS)
                if not ok:
                    return mk("violated", f"'{q}' disagrees: {why}")
            return mk("holds", "")
        # monotonic
        if actions != {"answer"}:
            return mk("inconclusive", "bot did not answer every question")
        vals = [scalar(rows) for _, rows in outs]
        if any(v is None for v in vals):
            return mk("violated", "a question did not return a single value")
        for a, b in zip(vals, vals[1:]):
            if b < a - EPS * max(abs(a), 1):
                return mk("violated", f"decreased from {_f(a)} to {_f(b)}")
        return mk("holds", "")

    if t == "partition_sum":
        (ta, total), (pa, parts) = ask(rel["total"]), ask(rel["parts"])
        if ta != "answer" or pa != "answer":
            return mk("inconclusive", "bot did not answer both questions")
        tv, pv = scalar(total), _sum_last_numeric(parts or [])
        if tv is None or pv is None:
            return mk("violated", "could not read total or parts")
        if abs(tv - pv) > EPS * max(abs(tv), 1):
            return mk("violated", f"parts sum to {_f(pv)} but total is {_f(tv)}")
        return mk("holds", "")

    if t == "subset_bound":
        (sa, sub), (pa, sup) = ask(rel["subset"]), ask(rel["superset"])
        if sa != "answer" or pa != "answer":
            return mk("inconclusive", "bot did not answer both questions")
        sv, pv = scalar(sub), scalar(sup)
        if sv is None or pv is None:
            return mk("violated", "could not read values")
        if sv > pv + EPS * max(abs(pv), 1):
            return mk("violated", f"subset {_f(sv)} exceeds superset {_f(pv)}")
        return mk("holds", "")

    raise ValueError(f"unknown relation type {t}")


def run_all(relations: list[dict], cases: list[dict], bot: Bot, wh: Warehouse,
            include_generated: bool = True) -> list[RelationResult]:
    rels = list(relations) + (generated_relations(cases) if include_generated else [])
    return [check_relation(r, bot, wh) for r in rels]
