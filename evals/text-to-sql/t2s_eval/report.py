"""Render a run into a Markdown report."""
from __future__ import annotations

from .grade import CaseResult
from .metamorphic import RelationResult
from .mutation import MutantResult
from .selective import Point, best


def _pct(x):
    return "n/a" if x is None else f"{x * 100:.0f}%"


def render(bot_runs: dict[str, dict], primary: str, mutants: list[MutantResult] | None,
           coverage_rows: list[dict] | None, chart_file: str | None, simulated: bool) -> str:
    L = ["# Text-to-SQL eval report", ""]
    if simulated:
        L += ["> These numbers come from the **simulated bot**, which injects known faults so the",
              "> pipeline can be tested without a model. They describe the simulator, not a real",
              "> system. Run with `--bot ollama` for real measurements.", ""]

    # 1. Headline
    L += ["## Headline", "",
          "| Bot | Pass rate | Accuracy (answerable) | Correct abstention | Confident-wrong rate | Unstable cases |",
          "|---|---|---|---|---|---|"]
    for name, r in bot_runs.items():
        s = r["summary"]
        L.append(f"| {name} | {_pct(s['pass_rate'])} | {_pct(s['accuracy_on_answerable'])} | "
                 f"{_pct(s['correct_abstention_rate'])} | {_pct(s['confident_wrong_rate'])} | "
                 f"{s['unstable_cases']} |")
    L += ["", "*Confident-wrong rate*: share of the bot's answers that were wrong even though every "
          "repeated run agreed. These are the answers users act on, because nothing looks off.", ""]

    p = bot_runs[primary]
    results: list[CaseResult] = p["results"]

    # 2. Confident wrong answers
    cw = sorted([r for r in results if r.answered and not r.passed and r.confidence == 1.0],
                key=lambda r: -r.cost_weight)
    L += [f"## Confident wrong answers ({primary})", ""]
    if cw:
        L += ["| Case | Question | Cost | Why it failed | Owner |", "|---|---|---|---|---|"]
        for r in cw:
            L.append(f"| {r.case_id} | {r.question} | {r.cost_weight} | {r.reason} | {r.owner} |")
    else:
        L.append("None.")
    L.append("")

    # 3. Routing
    L += [f"## Failures by owner ({primary})", "",
          "| Owner | Failures | Typical fix |", "|---|---|---|"]
    fixes = {"semantic_model": "add or correct a metric definition, filter or verified query",
             "prompt": "ask when a term does not match; refuse out-of-scope questions",
             "app": "fix message handling, truncation notices, timeouts"}
    for owner, n in sorted(p["summary"]["failures_by_owner"].items(), key=lambda x: -x[1]):
        L.append(f"| {owner} | {n} | {fixes.get(owner, '')} |")
    L.append("")

    # 4. Metamorphic
    rels: list[RelationResult] = p["relations"]
    viol = [x for x in rels if x.status == "violated"]
    hand = [x for x in rels if not x.generated]
    L += [f"## Metamorphic checks ({primary})", "",
          f"{len(rels)} relations checked ({len(hand)} hand-written, {len(rels) - len(hand)} generated "
          f"paraphrase sets), **{len(viol)} violated**. None of these checks uses a reference answer.", ""]
    if viol:
        L += ["| Relation | Type | Why it should hold | What broke |", "|---|---|---|---|"]
        for x in viol:
            L.append(f"| {x.id} | {x.type} | {x.why} | {x.detail} |")
        L.append("")

    # 5. Selective answering
    pts: list[Point] = p["points"]
    b = best(pts)
    L += [f"## When should the bot stay quiet? ({primary})", ""]
    if chart_file:
        L += [f"![risk-coverage]({chart_file})", ""]
    L += ["| Threshold | Coverage | Accuracy of answers | Wrong answers | Expected cost |",
          "|---|---|---|---|---|"]
    for pt in sorted(pts, key=lambda x: x.threshold):
        mark = " **<- lowest cost**" if pt is b else ""
        L.append(f"| {pt.threshold:.1f} | {_pct(pt.coverage)} | {_pct(pt.accuracy)} | {pt.wrong} | "
                 f"{pt.cost:.0f}{mark} |")
    L += ["", "Self-consistency catches unstable answers. It cannot catch a bot that is wrong the same "
          "way every time; those need the trap set and the rule checks.", ""]

    # 6. Judge validation
    if p.get("judge"):
        j = p["judge"]
        L += [f"## How much to trust the grader ({primary})", "",
              "Measured against faults the simulator injected on purpose.", "",
              "| Injected fault | Caught | Injected | Recall |", "|---|---|---|---|"]
        for f, v in j["recall_by_fault"].items():
            L.append(f"| {f} | {v['caught']} | {v['injected']} | {_pct(v['recall'])} |")
        L += ["", f"False alarms on clean runs: {j['false_alarms']} of {j['clean_runs']} "
              f"({_pct(j['false_alarm_rate'])}).", ""]
    if p.get("human"):
        h = p["human"]
        L += [f"Human labels: {h['labeled']} runs, agreement {_pct(h['agreement'])}, "
              f"Cohen's kappa {h['kappa']:.2f}.", ""]

    # 7. Mutation testing
    if mutants:
        killed = sum(m.killed for m in mutants)
        blind = [m for m in mutants if m.verdict == "blind_spot"]
        equiv = [m for m in mutants if m.verdict == "equivalent_on_current_data"]
        L += ["## Does the eval protect the semantic model?", "",
              f"{len(mutants)} deliberate model mutations. **{killed} caught**, "
              f"{len(blind)} blind spots, {len(equiv)} with no effect on today's data.", ""]
        if blind:
            L += ["**Blind spots** (the metric changed and no test noticed):", ""]
            L += [f"- {m.description}" for m in blind]
            L.append("")
        if equiv:
            L += ["**No effect on current data** (redundant today, unprotected if the data changes):", ""]
            L += [f"- {m.description}" for m in equiv]
            L.append("")
        if coverage_rows:
            L += ["| Metric | Cases | Mutants | Caught | Blind spots |", "|---|---|---|---|---|"]
            for row in coverage_rows:
                L.append(f"| {row['metric']} | {row['cases']} | {row['mutants']} | {row['killed']} | "
                         f"{row['blind_spots']} |")
            L.append("")
    return "\n".join(L)
