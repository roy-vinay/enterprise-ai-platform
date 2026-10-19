# Local decomposed-judge experiment comparison

All arms failed. Report decomposition/voting deltas honestly; no larger model or paid follow-up in this experiment.

API spend: USD 0 for every arm. Human-validated: false.

| Arm | Status | Action F1 | Misleading P | Misleading R | Repair R | Ungraded | Calls | Wall seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| single-call | failed | 0.769 | 0.364 | 0.632 | 0.375 | 0 | 68 | 416.27 |
| decomposed | failed | 0.454 | 0.867 | 0.684 | 0.875 | 0 | 340 | 890.89 |
| decomposed-vote | failed | 0.442 | 0.867 | 0.684 | 0.875 | 0 | 1020 | 1569.75 |

decomposed minus single-call: {"action_macro_f1": -0.31464220093631856, "misleading_recall": 0.052631578947368474}

decomposed-vote minus decomposed: {"action_macro_f1": -0.012648841354723772, "misleading_recall": 0.0}

See each arm report for per-category precision/recall, all confusion matrices, per-field provenance and voting disagreement rates.

Pilot is diagnostic, not independent full-schema human gold.
Single-call retains supplied case flaw_type; premise sub-call infers it from question and verified facts.
All sub-prompts use the same full frozen rubric, but their inputs are focused by design.
Evidence sub-call receives the same verified case facts inside evidence_report.
Usefulness sub-call sees only question and response; it cannot independently verify factual truth.
A reviewed repair exemplar occurs in the rubric and prompts; it is not an unseen generalization test.
Identical seeds across response-stage repeats reduce uncontrolled variation; samples within each voting call have distinct seeds.
No reference, rubric or threshold edits. No paid calls. No merge until human-gold validation clears.
