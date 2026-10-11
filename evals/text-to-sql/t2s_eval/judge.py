"""Judges, and how much to trust them.

Most eval repos trust their judge blindly. Here the judge is itself evaluated:

* Against injected faults. The simulated bot records exactly which fault it put
  into each answer, so we can measure, per fault type, how often the grader
  catches it (recall) and how often it fails a clean answer (false alarms).
* Against human labels. For a real bot, label a sample of runs by hand
  (trap_set/human_labels.csv) and measure agreement and Cohen's kappa. This is
  a capability: no independently reviewed label set is published yet, so the
  grader is not claimed to be validated against humans.

An optional LLM judge (local, via Ollama) checks the one thing rules cannot:
whether the bot's interpretation actually matches the question asked.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request
from collections import defaultdict
from pathlib import Path

from .grade import CaseResult


def fault_detection(results: list[CaseResult]) -> dict:
    """Recall per injected fault type and false-alarm rate on clean runs."""
    caught, total = defaultdict(int), defaultdict(int)
    clean = clean_failed = 0
    for r in results:
        for run in r.runs:
            if run.injected:
                for f in run.injected:
                    total[f] += 1
                    caught[f] += (not run.passed)
            else:
                clean += 1
                clean_failed += (not run.passed)
    return {
        "recall_by_fault": {f: {"caught": caught[f], "injected": total[f],
                                "recall": caught[f] / total[f]} for f in sorted(total)},
        "clean_runs": clean,
        "false_alarms": clean_failed,
        "false_alarm_rate": clean_failed / clean if clean else 0.0,
    }


def cohens_kappa(a: list[bool], b: list[bool]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def human_agreement(results: list[CaseResult], labels_csv: str | Path) -> dict | None:
    """labels_csv columns: case_id, run, label (pass|fail)."""
    path = Path(labels_csv)
    if not path.exists():
        return None
    graded = {(r.case_id, run.run): run.passed for r in results for run in r.runs}
    human, judge = [], []
    with path.open() as fh:
        for row in csv.DictReader(fh):
            key = (row["case_id"], int(row["run"]))
            if key in graded and row["label"].strip().lower() in ("pass", "fail"):
                human.append(row["label"].strip().lower() == "pass")
                judge.append(graded[key])
    if not human:
        return None
    return {"labeled": len(human),
            "agreement": sum(h == j for h, j in zip(human, judge)) / len(human),
            "kappa": cohens_kappa(human, judge)}


class LLMJudge:
    """Asks a local model whether the bot answered the question that was asked."""

    PROMPT = """Question from a business user: {question}
The BI bot's interpretation: {interpretation}
The bot's SQL: {sql}

Did the bot answer exactly the question asked, or did it silently substitute a different
metric, filter value, entity or time window? Respond with JSON only:
{{"answers_question": true|false, "substitution": true|false, "reason": "..."}}"""

    def __init__(self, model: str = "qwen2.5-coder:7b", host: str | None = None):
        self.model = model
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def __call__(self, question: str, interpretation: str, sql: str) -> dict:
        body = {"model": self.model, "stream": False, "format": "json",
                "options": {"temperature": 0},
                "messages": [{"role": "user", "content": self.PROMPT.format(
                    question=question, interpretation=interpretation, sql=sql)}]}
        req = urllib.request.Request(f"{self.host}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.loads(json.loads(r.read())["message"]["content"])
        except Exception as e:
            # Never return a favorable default: the grader fails the run as judge_unavailable.
            return {"error": f"{type(e).__name__}: {e}"}
        if not isinstance(out, dict) or not isinstance(out.get("answers_question"), bool) \
                or not isinstance(out.get("substitution"), bool):
            return {"error": f"malformed verdict: {str(out)[:120]}"}
        return out
