"""Load, render and mutate the semantic model."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

TABLES_WITH_ACCOUNT_ID = {"accounts", "subscriptions", "mrr_monthly", "invoices",
                          "usage_monthly", "support_tickets", "contacts", "events"}


def load(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def agg_sql(metric: dict) -> str:
    agg, col = metric["agg"].upper(), metric["column"]
    if agg == "COUNT DISTINCT":
        return f"COUNT(DISTINCT {col})"
    return f"{agg}({col})"


def where_sql(model: dict, name: str) -> str:
    m = model["metrics"][name]
    parts = list(m.get("filters", []))
    if m["table"] in TABLES_WITH_ACCOUNT_ID:
        parts += list(model.get("global_filters", {}).values())
    return " AND ".join(parts) if parts else "TRUE"


_PLACEHOLDER = re.compile(r"\{\{(agg|where|time|table|global):([a-z_]+)\}\}")


def render(template: str, model: dict) -> str:
    """Fill {{agg:x}}, {{where:x}}, {{time:x}}, {{table:x}}, {{global:all}} from the model."""
    def sub(match):
        kind, name = match.groups()
        if kind == "global":
            parts = list(model.get("global_filters", {}).values())
            return " AND ".join(parts) if parts else "TRUE"
        m = model["metrics"][name]
        return {"agg": lambda: agg_sql(m), "where": lambda: where_sql(model, name),
                "time": lambda: m["time_column"], "table": lambda: m["table"]}[kind]()
    return _PLACEHOLDER.sub(sub, template)


def metrics_in(template: str) -> set[str]:
    return {name for kind, name in _PLACEHOLDER.findall(template) if kind != "global"}


def prompt_context(model: dict, include_policies: bool = True) -> str:
    """Human-readable model description used in LLM prompts.

    include_policies=False leaves out the access and cost policies, for the
    ablation that measures what telling the bot the rules is worth.
    """
    lines = [f"Today is {model['as_of']} ({model['timezone']}). "
             f"Results are capped at {model['row_cap']} rows.", "", "Metrics:"]
    for name, m in model["metrics"].items():
        lines.append(f"- {name}: {m['description']} SQL: {agg_sql(m)} FROM {m['table']} "
                     f"WHERE {where_sql(model, name)}; time column {m['time_column']}. "
                     f"Also called: {', '.join(m.get('synonyms', []))}.")
    lines += ["", "Dimensions (join on account_id where needed):"]
    for name, d in model["dimensions"].items():
        lines.append(f"- {name} ({d['source']}): {', '.join(map(str, d['values']))}")
    lines += ["", "Not in the warehouse (refuse these):"]
    lines += [f"- {x}" for x in model.get("not_in_warehouse", [])]
    if not include_policies:
        return "\n".join(lines)
    policy = model.get("access_policy") or {}
    if policy:
        lines += ["", f"Access policy (you answer for the role '{policy.get('role', 'analyst')}'):"]
        if policy.get("read_only"):
            lines.append("- Read only: write a single SELECT. Never modify data or read files or URLs; "
                         "refuse requests that need that.")
        restricted = policy.get("restricted_columns") or {}
        if restricted:
            lines.append(f"- Never reference these columns, not even in COUNT: {', '.join(restricted)}. "
                         "Refuse requests that need them.")
    cost = model.get("cost_policy") or {}
    if cost.get("partition_columns"):
        parts = ", ".join(f"{t}.{c}" for t, c in cost["partition_columns"].items())
        lines += ["", f"Cost: large tables are stored in time order ({parts}). Filter those columns "
                  "with a plain range (col >= x AND col < y), never wrapped in a function, so the "
                  "warehouse can skip data. Do not export whole tables; ask what the user needs."]
    return "\n".join(lines)


# ---------------------------------------------------------------- mutation

@dataclass
class Mutant:
    id: str
    operator: str
    target: str
    description: str
    model: dict


_AGG_SWAP = {"SUM": "AVG", "AVG": "SUM", "COUNT DISTINCT": "COUNT"}


def mutants(model: dict) -> list[Mutant]:
    """Plausible human mistakes in a semantic model, one per mutant."""
    out: list[Mutant] = []
    for name, m in model["metrics"].items():
        for i, f in enumerate(m.get("filters", [])):
            mm = copy.deepcopy(model)
            del mm["metrics"][name]["filters"][i]
            out.append(Mutant(f"{name}.drop_filter.{i}", "drop_filter", name,
                              f"{name}: filter `{f}` removed", mm))
        new_agg = _AGG_SWAP.get(m["agg"].upper())
        if new_agg:
            mm = copy.deepcopy(model)
            mm["metrics"][name]["agg"] = new_agg
            out.append(Mutant(f"{name}.change_agg", "change_agg", name,
                              f"{name}: {m['agg']} changed to {new_agg}", mm))
        for alt in m.get("alt_time_columns", []):
            mm = copy.deepcopy(model)
            mm["metrics"][name]["time_column"] = alt
            out.append(Mutant(f"{name}.time_column.{alt}", "swap_time_column", name,
                              f"{name}: time column {m['time_column']} changed to {alt}", mm))
    for key, f in model.get("global_filters", {}).items():
        mm = copy.deepcopy(model)
        del mm["global_filters"][key]
        out.append(Mutant(f"global.drop.{key}", "drop_global_filter", "*",
                          f"global filter `{key}` removed", mm))
    return out
