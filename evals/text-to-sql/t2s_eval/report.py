"""Render a run into a Markdown report."""
from __future__ import annotations

from .grade import CaseResult
from .metamorphic import RelationResult
from .mutation import MutantResult
from .selective import Point, best


def _pct(x):
    return "n/a" if x is None else f"{x * 100:.0f}%"


def render(bot_runs: dict[str, dict], primary: str, mutants: list[MutantResult] | None,
           coverage_rows: list[dict] | None, chart_file: str | None, simulated: bool,
           holdout_info: bool = False) -> str:
    L = ["# Text-to-SQL eval report", ""]
    if simulated:
        L += ["> These numbers come from the **simulated bot**, which injects known faults so the",
              "> pipeline can be tested without a model. They describe the simulator, not a real",
              "> system. Run with `--bot ollama` for real measurements.", ""]

    # 1. Headline
    L += ["## Headline", "",
          "| Bot | Pass rate | Accuracy (answerable) | Correct abstention | Confident-wrong rate | Unstable cases | Judge unavailable |",
          "|---|---|---|---|---|---|---|"]
    for name, r in bot_runs.items():
        s = r["summary"]
        L.append(f"| {name} | {_pct(s['pass_rate'])} | {_pct(s['accuracy_on_answerable'])} | "
                 f"{_pct(s['correct_abstention_rate'])} | {_pct(s['confident_wrong_rate'])} | "
                 f"{s['unstable_cases']} | {s.get('judge_unavailable_runs', 0)} |")
    L += ["", "*Confident-wrong rate*: share of the bot's answers that were wrong even though every "
          "repeated run gave the same answer. These are the answers users act on, because nothing "
          "looks off. *Judge unavailable*: runs where the LLM judge errored; they are counted as "
          "failures, never as clean passes.", ""]

    p = bot_runs[primary]
    results: list[CaseResult] = p["results"]

    # 1b. Trust checks
    L += trust_section(bot_runs, primary)

    # 2. Confident wrong answers
    cw = sorted([r for r in results if r.answered and not r.passed and r.agreement == 1.0],
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
             "app": "fix message handling, truncation notices, timeouts; connect with read-only "
                    "credentials and file access off"}
    for owner, n in sorted(p["summary"]["failures_by_owner"].items(), key=lambda x: -x[1]):
        L.append(f"| {owner} | {n} | {fixes.get(owner, '')} |")
    L.append("")

    # 4. Metamorphic
    rels: list[RelationResult] = p["relations"]
    viol = [x for x in rels if x.status == "violated"]
    hand = [x for x in rels if not x.generated]
    L += [f"## Metamorphic checks ({primary})", "",
          f"{len(rels)} relations checked ({len(hand)} hand-written, {len(rels) - len(hand)} generated "
          f"paraphrase sets), **{len(viol)} violated**. None of these checks uses a reference answer. "
          "A relation that holds shows consistency, not correctness: answers can be consistently "
          "wrong.", ""]
    if viol:
        L += ["| Relation | Type | Why it should hold | What broke |", "|---|---|---|---|"]
        for x in viol:
            why = x.why + (f" (assumes {x.assumes})" if getattr(x, "assumes", "") else "")
            L.append(f"| {x.id} | {x.type} | {why} | {x.detail} |")
        L.append("")

    # 5. Selective answering
    pts: list[Point] = p["points"]
    b = best(pts)
    L += [f"## When should the bot stay quiet? ({primary})", ""]
    if chart_file:
        L += [f"![risk-coverage]({chart_file})", ""]
    L += ["The bot answers only when its runs agree at least this often. Agreement is a coarse "
          "consistency signal, not a calibrated probability of being right.", "",
          "| Agreement threshold | Coverage | Accuracy of answers | Wrong answers | Cost |",
          "|---|---|---|---|---|"]
    for pt in sorted(pts, key=lambda x: x.threshold):
        mark = " (lowest, in-sample)" if pt is b else ""
        acc = _pct(pt.accuracy) if pt.answered else "n/a"
        L.append(f"| {pt.label} | {_pct(pt.coverage)} | {acc} | {pt.wrong} | {pt.cost:.0f}{mark} |")
    if p.get("holdout"):
        L += ["", "**Held-out check.** The lowest-cost row above is chosen on the same cases it is "
              "scored on, which flatters it. Below, the threshold is chosen on one half of the "
              "cases and scored on the other, both ways round. With this few cases, treat it as "
              "exploratory.", "",
              "| Fold | Threshold chosen on dev | Test cost | Test cost if it always answered | Test coverage |",
              "|---|---|---|---|---|"]
        for h in p["holdout"]:
            t = "abstain all" if h["threshold"] == float("inf") else f"{h['threshold']:.2f}"
            L.append(f"| {h['fold']} ({h['dev_cases']}/{h['test_cases']}) | {t} | "
                     f"{h['test_cost']:.0f} | {h['test_cost_answer_all']:.0f} | "
                     f"{_pct(h['test_coverage'])} |")
    L += ["", "Agreement catches unstable answers. It cannot catch a bot that is wrong the same "
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
              f"Cohen's kappa {h['kappa']:.2f}. These labels have not been independently reviewed.", ""]

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


def _n(x):
    return "n/a" if x is None else f"{x:,}"


def trust_section(bot_runs: dict[str, dict], primary: str) -> list[str]:
    """Right answers produced the wrong way: the failures a result-only eval passes."""
    L = ["## Right answer, wrong way", "",
         "A correct number is not the whole job. These checks grade how each answer was produced: "
         "whether it read restricted columns, how many rows it read from storage, and whether it "
         "tried to write or read files. Unsafe SQL is never executed.", "",
         "| Bot | Answers | Right but failed a trust check | Restricted access | Over scan budget | Unsafe SQL | Median rows read | Max rows read |",
         "|---|---|---|---|---|---|---|---|"]
    for name, r in bot_runs.items():
        s = r["summary"]
        L.append(f"| {name} | {s.get('answer_runs', 0)} | {s.get('right_answer_wrong_way', 0)} "
                 f"({_pct(s.get('right_answer_wrong_way_rate'))}) | {s.get('restricted_access_runs', 0)} | "
                 f"{s.get('over_budget_runs', 0)} | {s.get('unsafe_sql_runs', 0)} | "
                 f"{_n(s.get('median_rows_scanned'))} | {_n(s.get('max_rows_scanned'))} |")
    L += ["", "*Right but failed a trust check*: runs whose result matched the reference and still "
          "failed on access or cost. Counts are over runs, not cases.", ""]
    rows = [(r, run) for r in bot_runs[primary]["results"] for run in r.runs
            if run.failed_check in ("safety", "access", "cost")]
    if rows:
        seen, L2 = set(), []
        for r, run in rows:
            key = (r.case_id, run.reason)
            if key in seen:
                continue
            seen.add(key)
            right = {True: "yes", False: "no", None: "not run"}[run.result_correct]
            L2.append(f"| {r.case_id} | {r.question} | {run.failed_check} | {right} | {run.reason} |")
        L += [f"### Trust failures ({primary})", "",
              "| Case | Question | Check | Result right? | Detail |", "|---|---|---|---|---|", *L2, ""]
    return L
