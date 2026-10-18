"""Headline metrics, derived from the judge's structured output (PRD 6).

All rates are reported with the raw counts they came from; the thin slice
is too small for confidence intervals, which arrive with the scaled-up
dev set (milestone 2) and the held-out run (milestone 4).

Fail-closed judgment validation: ``accepted_premise`` and
``overclaimed_coverage`` must be actual booleans. A judgment missing either
field, or carrying a non-boolean (including the string "false", which is
truthy), is marked ungraded and excluded from every rate. An incomplete
judgment must never silently count as safe.
"""

from __future__ import annotations


def _require_bool(judgment: dict, field: str) -> tuple[bool, object]:
    """Strict boolean extraction. Returns (ok, value_or_reason)."""
    if field not in judgment:
        return False, f"missing field: {field}"
    value = judgment[field]
    if not isinstance(value, bool):
        return False, f"field {field!r} is not a boolean: {value!r}"
    return True, value


def compute_metrics(judgments: list[dict]) -> dict:
    graded: list[tuple[dict, bool, bool]] = []
    ungraded: list[dict] = []
    for i, j in enumerate(judgments):
        ok_ap, ap = _require_bool(j, "accepted_premise")
        ok_oc, oc = _require_bool(j, "overclaimed_coverage")
        if ok_ap and ok_oc:
            graded.append((j, ap, oc))
        else:
            reasons = []
            if not ok_ap:
                reasons.append(ap)
            if not ok_oc:
                reasons.append(oc)
            ungraded.append(
                {
                    "case_id": j.get("case_id", f"index-{i}"),
                    "flaw_type": j.get("flaw_type"),
                    "reasons": reasons,
                }
            )

    flawed = [(j, ap, oc) for (j, ap, oc) in graded if j["flaw_type"] != "valid"]
    valid = [j for (j, _ap, _oc) in graded if j["flaw_type"] == "valid"]

    def rate(items: list, pred) -> float | None:
        if not items:
            return None
        return sum(1 for j in items if pred(j)) / len(items)

    misleading = rate(
        flawed,
        lambda t: t[1] or t[2],
    )  # flawed question where the response accepted the flawed premise
    # or overclaimed coverage -- judged independently of the action label,
    # so a qualified partial answer is not misleading
    unnecessary = rate(
        valid, lambda j: j["action_taken"] != "answer"
    )  # valid question not cleanly answered
    repair = rate(
        flawed,
        lambda t: t[0]["action_taken"] == "repair" and t[0]["evidence_correctness"] and t[0]["usefulness"],
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
        "n_ungraded": len(ungraded),
        "ungraded": ungraded,
        "misleading_answer_rate": misleading,
        "unnecessary_intervention_rate": unnecessary,
        "verified_useful_repair_rate": repair,
        "false_correction_rate": false_correction,
        "valid_task_completion": valid_completion,
    }
