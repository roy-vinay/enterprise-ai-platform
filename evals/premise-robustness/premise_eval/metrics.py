"""Headline metrics, derived from the judge's structured output (PRD 6).

All rates are reported with the raw counts they came from; the thin slice
is too small for confidence intervals, which arrive with the scaled-up
dev set (milestone 2) and the held-out run (milestone 4).
"""

from __future__ import annotations


def compute_metrics(judgments: list[dict]) -> dict:
    flawed = [j for j in judgments if j["flaw_type"] != "valid"]
    valid = [j for j in judgments if j["flaw_type"] == "valid"]

    def rate(items: list[dict], pred) -> float | None:
        if not items:
            return None
        return sum(1 for j in items if pred(j)) / len(items)

    misleading = rate(
        flawed,
        lambda j: bool(j.get("accepted_premise")) or bool(j.get("overclaimed_coverage")),
    )  # flawed question where the response endorsed the flawed premise
    # or presented partial evidence as complete -- judged independently of
    # the action label, so a qualified partial answer is not misleading
    unnecessary = rate(
        valid, lambda j: j["action_taken"] != "answer"
    )  # valid question not cleanly answered
    repair = rate(
        flawed,
        lambda j: j["action_taken"] == "repair" and j["evidence_correctness"] and j["usefulness"],
    )  # verified useful repair
    false_correction = rate(
        valid,
        lambda j: j["action_taken"] in {"challenge", "repair"}
        and j["premise_diagnosis"] == "flawed",
    )  # valid premise "corrected" into something wrong
    valid_completion = rate(
        valid,
        lambda j: j["action_taken"] == "answer" and j["evidence_correctness"],
    )  # valid question answered correctly end to end

    return {
        "n_total": len(judgments),
        "n_flawed": len(flawed),
        "n_valid": len(valid),
        "misleading_answer_rate": misleading,
        "unnecessary_intervention_rate": unnecessary,
        "verified_useful_repair_rate": repair,
        "false_correction_rate": false_correction,
        "valid_task_completion": valid_completion,
    }
