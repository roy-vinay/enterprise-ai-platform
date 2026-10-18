"""Local LLM behavioral judge and a smoke-test-only scripted stub.

judge() uses the configured backend, the versioned prompt, and the full rubric.
It validates structured output, retries malformed output twice, and leaves
unresolved responses explicitly ungraded. Human validation is still pending;
implementation alone does not establish that the judge is trustworthy.

judge_stub() supports only the scripted pipeline smoke test. It trusts the fake
model's behavior tag and must not be used for research results.
"""

from __future__ import annotations

VALID_ACTIONS = {"answer", "clarify", "challenge", "repair", "abstain"}


def judge_stub(case: dict, behavior_tag: str, evidence_ok: bool) -> dict:
    """Scripted test double for the smoke fixture, not a validated judge."""
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


JUDGE_VERSION = "judge-v1"


def judge(response_text, case, evidence_report, *, backend=None):
    """Grade behavior with up to two retries; malformed output stays ungraded."""
    import json
    from pathlib import Path
    from .backends import load_backend
    from .judgment import SCHEMA, parse

    if type(evidence_report.get("passed")) is not bool:
        raise ValueError("Verifier report must contain a strict passed boolean")
    if evidence_report.get("stale_ground_truth"):
        raise ValueError("Stale ground truth must be repaired before judging")
    root = Path(__file__).resolve().parent.parent
    prompt = (root / "prompts/judge-v1.md").read_text()
    rubric = (root / "RUBRIC.md").read_text()
    backend = backend or load_backend()
    identity = backend.identity()
    # Never expose author notes, candidate behavior tags, or human gold labels.
    context = {k: case[k] for k in ("id", "question", "flaw_type", "reference_facts",
        "acceptable_actions", "prohibited_claims", "mixed_flaw", "mixed_flaw_note") if k in case}
    messages = [dict(role="system", content=prompt + "\n\nVerbatim grading standard:\n" + rubric),
                dict(role="user", content=json.dumps(dict(case=context,
                    response_text=response_text, evidence_report=evidence_report)))]
    errors = []
    for attempt in range(3):
        try:
            raw = backend.complete(messages, SCHEMA)
            result = parse(raw)
            if evidence_report["passed"] is False and result["evidence_correctness"]:
                raise ValueError("Judge contradicted failed deterministic verification")
            return dict(graded=True, judgment=result, attempts=attempt + 1,
                        judge_version=JUDGE_VERSION, model=identity)
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(str(exc))
            messages.append(dict(role="user", content="Output failed schema/verification checks: "
                + str(exc) + ". Return only a complete corrected JSON object."))
    return dict(graded=False, reason="; ".join(errors), attempts=3,
                judge_version=JUDGE_VERSION, model=identity)
