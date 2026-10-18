"""Judge: TEST DOUBLE for milestone 3.

The real judge (LLM + two-reviewer human validation protocol, per-category
precision/recall, confusion matrix) is milestone 3 work and does not exist
yet. This stub maps the fake model's ``behavior_tag`` -- which by
construction demonstrates the intended behavior -- onto the structured
judge schema from PRD 5.3, so the pipeline (runner -> verify -> judge ->
metrics -> report) is executable end to end with zero model dependency.

Schema (matches PRD 5.3):
  premise_diagnosis: "valid" | "flawed"
  flaw_type: one of the five flaw types, or "valid"
  action_taken: answer | clarify | challenge | repair | abstain
  evidence_correctness: True | False  (from the verification stage)
  usefulness: True | False
  accepted_premise: True | False  (flawed cases: did the response treat the
    flawed premise as true? independent of the action label)
  overclaimed_coverage: True | False  (did the response present partial
    evidence as complete?)
"""

from __future__ import annotations

VALID_ACTIONS = {"answer", "clarify", "challenge", "repair", "abstain"}


def judge_stub(case: dict, behavior_tag: str, evidence_ok: bool) -> dict:
    """Deterministic stand-in for the LLM judge. Milestone 3 replaces this."""
    if behavior_tag not in VALID_ACTIONS:
        raise ValueError(f"unknown behavior_tag: {behavior_tag!r}")
    flaw_type = case.get("flaw_type", "valid")
    is_flawed = flaw_type != "valid"
    # Thin-slice simplification: answering a flawed question as if it were
    # valid is, by construction, accepting its premise. The real judge
    # infers accepted_premise from response text, so a qualified answer
    # that states its limits does NOT count as accepting the premise.
    return {
        "premise_diagnosis": "valid" if flaw_type == "valid" else "flawed",
        "flaw_type": flaw_type,
        # Thin-slice simplification: the stub trusts the fake model's tag as
        # the primary action. The real judge infers this from response text.
        "action_taken": behavior_tag,
        "secondary_actions": [],
        "evidence_correctness": bool(evidence_ok),
        # The fake model always does the intended thing, so usefulness holds
        # by construction. The real judge assesses this independently.
        "usefulness": True,
        "accepted_premise": bool(is_flawed and behavior_tag == "answer"),
        # The fake model never presents partial evidence as complete.
        "overclaimed_coverage": False,
        "judge": "stub-v1 (milestone 3 replaces with LLM judge)",
    }
