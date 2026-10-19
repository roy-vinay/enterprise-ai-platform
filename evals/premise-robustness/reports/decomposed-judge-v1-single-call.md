# decomposed-judge-v1: single-call

Status: failed
Human-validated: false. Agent-generated reference dry run only.
Local API spend: USD 0. Hardware/electricity costs not measured.
Wall-clock runtime: 416.27 seconds; model requests: 68.
Runtime sums active process segments; interrupted downtime is excluded.

Responses: 68; ungraded: 0; macro F1: 0.849

## Acceptance failures

action_taken macro F1 below threshold
action_taken/answer recall below threshold
action_taken/clarify precision below threshold
action_taken/repair recall below threshold
Misleading-answer recall below threshold

## flaw_type

| Category | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| valid | 1.000 | 0.900 | 0.947 | 10 |
| false_premise | 0.800 | 1.000 | 0.889 | 12 |
| ambiguity | 1.000 | 0.833 | 0.909 | 12 |
| unavailable_evidence | 1.000 | 1.000 | 1.000 | 10 |
| undefined_metric | 0.857 | 1.000 | 0.923 | 12 |
| unsupported_causal | 1.000 | 0.833 | 0.909 | 12 |

Confusion matrix, reference rows and prediction columns:

```json
{
  "valid": {
    "valid": 9,
    "false_premise": 1,
    "ambiguity": 0,
    "unavailable_evidence": 0,
    "undefined_metric": 0,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "false_premise": {
    "valid": 0,
    "false_premise": 12,
    "ambiguity": 0,
    "unavailable_evidence": 0,
    "undefined_metric": 0,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "ambiguity": {
    "valid": 0,
    "false_premise": 0,
    "ambiguity": 10,
    "unavailable_evidence": 0,
    "undefined_metric": 2,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "unavailable_evidence": {
    "valid": 0,
    "false_premise": 0,
    "ambiguity": 0,
    "unavailable_evidence": 10,
    "undefined_metric": 0,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "undefined_metric": {
    "valid": 0,
    "false_premise": 0,
    "ambiguity": 0,
    "unavailable_evidence": 0,
    "undefined_metric": 12,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "unsupported_causal": {
    "valid": 0,
    "false_premise": 2,
    "ambiguity": 0,
    "unavailable_evidence": 0,
    "undefined_metric": 0,
    "unsupported_causal": 10,
    "ungraded": 0
  }
}
```

## action_taken

| Category | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| answer | 0.950 | 0.679 | 0.792 | 28 |
| clarify | 0.571 | 1.000 | 0.727 | 8 |
| challenge | 0.750 | 1.000 | 0.857 | 18 |
| repair | 1.000 | 0.375 | 0.545 | 8 |
| abstain | 0.857 | 1.000 | 0.923 | 6 |

Confusion matrix, reference rows and prediction columns:

```json
{
  "answer": {
    "answer": 19,
    "clarify": 4,
    "challenge": 4,
    "repair": 0,
    "abstain": 1,
    "ungraded": 0
  },
  "clarify": {
    "answer": 0,
    "clarify": 8,
    "challenge": 0,
    "repair": 0,
    "abstain": 0,
    "ungraded": 0
  },
  "challenge": {
    "answer": 0,
    "clarify": 0,
    "challenge": 18,
    "repair": 0,
    "abstain": 0,
    "ungraded": 0
  },
  "repair": {
    "answer": 1,
    "clarify": 2,
    "challenge": 2,
    "repair": 3,
    "abstain": 0,
    "ungraded": 0
  },
  "abstain": {
    "answer": 0,
    "clarify": 0,
    "challenge": 0,
    "repair": 0,
    "abstain": 6,
    "ungraded": 0
  }
}
```

## misleading

| Category | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| misleading | 0.364 | 0.632 | 0.462 | 19 |
| not_misleading | 0.800 | 0.571 | 0.667 | 49 |

Confusion matrix, reference rows and prediction columns:

```json
{
  "misleading": {
    "misleading": 12,
    "not_misleading": 7,
    "ungraded": 0
  },
  "not_misleading": {
    "misleading": 21,
    "not_misleading": 28,
    "ungraded": 0
  }
}
```

Per-response JSON includes field-level prompt versions/hashes, sample values, settings, attempts, input hashes and vote decisions.

Pilot is diagnostic, not independent full-schema human gold.
Single-call retains supplied case flaw_type; premise sub-call infers it from question and verified facts.
All sub-prompts use the same full frozen rubric, but their inputs are focused by design.
Evidence sub-call receives the same verified case facts inside evidence_report.
Usefulness sub-call sees only question and response; it cannot independently verify factual truth.
A reviewed repair exemplar occurs in the rubric and prompts; it is not an unseen generalization test.
Identical seeds across response-stage repeats reduce uncontrolled variation; samples within each voting call have distinct seeds.
No reference, rubric or threshold edits. No paid calls. No merge until human-gold validation clears.
