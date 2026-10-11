"""Command line entry point.

  python -m t2s_eval.cli build-data
  python -m t2s_eval.cli run                         # simulated bots, full report
  python -m t2s_eval.cli run --bot ollama --model qwen2.5-coder:7b
  python -m t2s_eval.cli run --bot replay --responses reports/x/responses-ollama-qwen.jsonl
  python -m t2s_eval.cli lint                        # can every case catch a wrong answer?
  python -m t2s_eval.cli gate                        # CI regression gate on the semantic model
  python -m t2s_eval.cli gate --update-baseline
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import config, judge, lint, metamorphic, mutation, report, selective, semantic
from .bots.simulated import SimulatedBot
from .db import Warehouse
from .grade import grade_suite, summarize


def _make_bot(kind: str, model: dict, cases: list[dict], profile: str, llm: str,
              responses: str | None = None):
    if kind == "replay":
        from .bots.replay import ReplayBot
        return ReplayBot(responses)
    if kind == "simulated":
        return SimulatedBot(model, cases, profile)
    if kind == "ollama":
        from .bots.ollama import OllamaBot
        return OllamaBot(model, model=llm)
    raise SystemExit(f"unknown bot {kind}")


def cmd_build_data(_):
    from .data import build
    build(config.WAREHOUSE)
    print(f"built {config.WAREHOUSE}")


def cmd_run(a):
    model = semantic.load(a.semantic_model)
    cases, relations = config.load_cases(), config.load_relations()
    wh = Warehouse(str(config.ensure_warehouse()), model.get("row_cap", 100), str(model["as_of"]))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    llm_judge = judge.LLMJudge(a.model) if a.llm_judge else None

    if a.bot == "simulated":
        labels = [p.strip() for p in a.profiles.split(",")]
    elif a.bot == "replay":
        labels = [p.strip() for p in a.responses.split(",")]
    else:
        labels = [a.model]
    bot_runs = {}
    for label in labels:
        bot = _make_bot(a.bot, model, cases, label, a.model, responses=label)
        if a.bot == "ollama":
            from .bots.replay import RecordingBot
            bot = RecordingBot(bot, out / f"responses-{bot.name.replace(':', '_')}.jsonl")
        print(f"grading {bot.name} ({len(cases)} cases x {a.runs} runs)...", flush=True)
        results = grade_suite(cases, bot, wh, model, n_runs=a.runs, judge=llm_judge)
        rels = metamorphic.run_all(relations, cases, bot, wh)
        run = {"results": results, "summary": summarize(results), "relations": rels,
               "points": selective.sweep(results, a.abstain_cost),
               "holdout": selective.holdout(results, a.abstain_cost)}
        if a.bot == "simulated":
            run["judge"] = judge.fault_detection(results)
        run["human"] = judge.human_agreement(results, config.ROOT / "trap_set" / "human_labels.csv")
        bot_runs[bot.name] = run
        with (out / f"results-{bot.name.replace(':', '_')}.jsonl").open("w") as fh:
            for r in results:
                fh.write(json.dumps(r.to_dict(), default=str) + "\n")

    mutants = cov = None
    if not a.skip_mutation and a.bot != "replay":
        print("mutation testing the semantic model...", flush=True)
        factory = (lambda m: SimulatedBot(m, cases, "perfect")) if a.bot == "simulated" \
            else (lambda m: _make_bot(a.bot, m, cases, "", a.model))
        mutants = mutation.run(model, cases, relations, factory, wh)
        cov = mutation.coverage(model, cases, mutants)

    chart = selective.plot({k: v["points"] for k, v in bot_runs.items()},
                           str(out / "risk_coverage.png"))
    primary = next(iter(bot_runs))
    md = report.render(bot_runs, primary, mutants, cov, Path(chart).name, a.bot == "simulated",
                       holdout_info=True)
    (out / "report.md").write_text(md)
    summary = {k: {**v["summary"],
                   "in_sample_best_threshold": selective.best(v["points"]).label,
                   "holdout": v["holdout"],
                   "metamorphic_violations": sum(x.status == "violated" for x in v["relations"])}
               for k, v in bot_runs.items()}
    if mutants:
        summary["mutation"] = {"mutants": len(mutants), "killed": sum(m.killed for m in mutants),
                               "blind_spots": [m.id for m in mutants if m.verdict == "blind_spot"]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(md + "\n")
    print(f"report: {out / 'report.md'}")


def cmd_lint(_):
    """Fail if a trap-set case cannot tell a plausible wrong answer from the right one."""
    model = semantic.load(config.MODEL)
    wh = Warehouse(str(config.ensure_warehouse()), model.get("row_cap", 100), str(model["as_of"]))
    issues = lint.lint(config.load_cases(), wh, model)
    for i in issues:
        print(f"{i['case']}: {i['issue']} ({i['detail']})")
    print(f"{len(issues)} lint issues")
    sys.exit(1 if issues else 0)


def gate_regressions(base: dict, results: dict, rels: dict) -> list[str]:
    """Everything that was protected in the baseline and no longer is.

    A case that passed must still exist and still pass. A relation that held
    must still exist and still hold: "inconclusive" is not a pass, because a
    relation that can no longer be evaluated no longer protects anything.
    Deleting a test is a regression until the baseline is updated on purpose.
    """
    out = []
    for k, ok in sorted(base["cases"].items()):
        if not ok:
            continue
        if k not in results:
            out.append(f"{k}: case removed from the trap set")
        elif not results[k].passed:
            out.append(f"{k}: {results[k].question} -> {results[k].reason}")
    for k, st in sorted(base["relations"].items()):
        if st != "holds":
            continue
        if k not in rels:
            out.append(f"{k}: relation removed")
        elif rels[k].status != "holds":
            out.append(f"{k}: {rels[k].why} -> now {rels[k].status}: {rels[k].detail}")
    return out


def cmd_gate(a):
    """Fail if a case that passed in the baseline now fails.

    Uses a bot that executes the semantic model faithfully, so a failure means
    the model (or the data) changed in a way that breaks a known-good answer.
    Point it at your real bot by swapping the factory for your adapter.
    """
    model = semantic.load(a.semantic_model)
    cases, relations = config.load_cases(), config.load_relations()
    wh = Warehouse(str(config.ensure_warehouse()), model.get("row_cap", 100), str(model["as_of"]))
    bot = SimulatedBot(model, cases, "perfect")
    results = {r.case_id: r for r in grade_suite(cases, bot, wh, model, n_runs=1)}
    rels = {r.id: r for r in metamorphic.run_all(relations, cases, bot, wh)}
    current = {"cases": {k: r.passed for k, r in results.items()},
               "relations": {k: r.status for k, r in rels.items()}}

    if a.update_baseline:
        config.BASELINE.parent.mkdir(parents=True, exist_ok=True)
        config.BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True))
        print(f"baseline updated: {sum(current['cases'].values())}/{len(cases)} cases pass")
        return
    base = json.loads(config.BASELINE.read_text())
    regressions = gate_regressions(base, results, rels)
    lines = [f"## Semantic model gate", "",
             f"{sum(current['cases'].values())}/{len(cases)} cases pass, "
             f"{len(regressions)} regressions against baseline.", ""]
    lines += [f"- {r}" for r in regressions]
    if regressions:
        lines += ["", "If a removal or change is intentional, run `python -m t2s_eval.cli gate "
                  "--update-baseline` and commit baseline/baseline.json, so the change shows up "
                  "in review."]
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(text + "\n")
    sys.exit(1 if regressions else 0)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="t2s_eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build-data").set_defaults(fn=cmd_build_data)
    sub.add_parser("lint").set_defaults(fn=cmd_lint)

    r = sub.add_parser("run")
    r.add_argument("--bot", choices=["simulated", "ollama", "replay"], default="simulated")
    r.add_argument("--responses", default="",
                   help="replay: recorded responses-*.jsonl files, comma separated")
    r.add_argument("--profiles", default="overconfident,careful",
                   help="simulated bot profiles, comma separated; the first is the primary")
    r.add_argument("--model", default="qwen2.5-coder:7b", help="Ollama model name")
    r.add_argument("--runs", type=int, default=5, help="repeats per question (self-consistency)")
    r.add_argument("--abstain-cost", type=float, default=1.0)
    r.add_argument("--llm-judge", action="store_true", help="add the local LLM behavior judge")
    r.add_argument("--skip-mutation", action="store_true")
    r.add_argument("--semantic-model", default=str(config.MODEL))
    r.add_argument("--out", default=str(config.REPORTS / "latest"))
    r.set_defaults(fn=cmd_run)

    g = sub.add_parser("gate")
    g.add_argument("--semantic-model", default=str(config.MODEL))
    g.add_argument("--update-baseline", action="store_true")
    g.set_defaults(fn=cmd_gate)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
