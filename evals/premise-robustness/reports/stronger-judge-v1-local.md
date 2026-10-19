# Judge agreement evaluation judge-v2

Development dry run against agent-generated references, not human-validated accuracy.

Human-validated: false

Status: failed
Responses: 68; ungraded: 0
Macro F1: 0.849

## Failure analysis

action_taken macro F1 below threshold
action_taken/answer recall below threshold
action_taken/clarify precision below threshold
action_taken/repair recall below threshold
Misleading-answer recall below threshold

## flaw_type

| Category | Precision | Recall | F1 |
|---|---:|---:|---:|
| valid | 1.000 | 0.900 | 0.947 |
| false_premise | 0.800 | 1.000 | 0.889 |
| ambiguity | 1.000 | 0.833 | 0.909 |
| unavailable_evidence | 1.000 | 1.000 | 1.000 |
| undefined_metric | 0.857 | 1.000 | 0.923 |
| unsupported_causal | 1.000 | 0.833 | 0.909 |

Confusion matrix (rows: gold, columns: prediction):

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

| Category | Precision | Recall | F1 |
|---|---:|---:|---:|
| answer | 0.950 | 0.679 | 0.792 |
| clarify | 0.571 | 1.000 | 0.727 |
| challenge | 0.750 | 1.000 | 0.857 |
| repair | 1.000 | 0.375 | 0.545 |
| abstain | 0.857 | 1.000 | 0.923 |

Confusion matrix (rows: gold, columns: prediction):

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

Misleading-answer precision/recall:
{"precision": 0.36363636363636365, "recall": 0.631578947368421, "f1": 0.46153846153846156, "support": 19}

Inspect disagreements in the JSON predictions; do not lower thresholds to pass.

## V1 versus V2 comparison

V1 is the preserved historical 60-response run. V2 same-60 uses unchanged
references and the same response IDs. Expanded V2 includes 8 repair additions.
There is no V1 measurement of the new repair rows. This is not held-out validation.

| Task/category | V1 P (n=60) | V1 R | V2 P (same 60) | V2 R | V2 P (n=68) | V2 R |
|---|---:|---:|---:|---:|---:|---:|
| action_taken/answer | 1.000 | 0.429 | 1.000 | 0.679 | 0.950 | 0.679 |
| action_taken/clarify | 0.533 | 1.000 | 0.667 | 1.000 | 0.571 | 1.000 |
| action_taken/challenge | 0.654 | 0.944 | 0.818 | 1.000 | 0.750 | 1.000 |
| action_taken/repair | N/A (no support) | N/A (no support) | N/A (no support) | N/A (no support) | 1.000 | 0.375 |
| action_taken/abstain | 0.857 | 1.000 | 0.857 | 1.000 | 0.857 | 1.000 |
| misleading/misleading | 0.111 | 0.062 | 0.345 | 0.625 | 0.364 | 0.632 |
| misleading/not_misleading | 0.706 | 0.818 | 0.806 | 0.568 | 0.800 | 0.571 |

Dry run only: pending human approval remains unchanged. No downstream authorization.
