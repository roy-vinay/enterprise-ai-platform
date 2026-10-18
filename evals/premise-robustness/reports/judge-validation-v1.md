# Judge agreement evaluation v1

Agreement with agent-generated labels, not human-validated accuracy.

Human-validated: false

Status: failed
Responses: 60; ungraded: 0
Macro F1: 0.782

## Failure analysis

action_taken macro F1 below threshold
action_taken/answer recall below threshold
action_taken/clarify precision below threshold
action_taken/challenge precision below threshold
action_taken/repair precision below threshold
action_taken/repair recall below threshold
Misleading-answer recall below threshold

## flaw_type

| Category | Precision | Recall | F1 |
|---|---:|---:|---:|
| valid | 1.000 | 0.800 | 0.889 |
| false_premise | 0.909 | 1.000 | 0.952 |
| ambiguity | 1.000 | 1.000 | 1.000 |
| unavailable_evidence | 1.000 | 1.000 | 1.000 |
| undefined_metric | 0.909 | 1.000 | 0.952 |
| unsupported_causal | 1.000 | 1.000 | 1.000 |

Confusion matrix (rows: gold, columns: prediction):

```json
{
  "valid": {
    "valid": 8,
    "false_premise": 1,
    "ambiguity": 0,
    "unavailable_evidence": 0,
    "undefined_metric": 1,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "false_premise": {
    "valid": 0,
    "false_premise": 10,
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
    "undefined_metric": 0,
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
    "undefined_metric": 10,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "unsupported_causal": {
    "valid": 0,
    "false_premise": 0,
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
| answer | 1.000 | 0.429 | 0.600 |
| clarify | 0.533 | 1.000 | 0.696 |
| challenge | 0.654 | 0.944 | 0.773 |
| repair | 0.000 | 0.000 | 0.000 |
| abstain | 0.857 | 1.000 | 0.923 |

Confusion matrix (rows: gold, columns: prediction):

```json
{
  "answer": {
    "answer": 12,
    "clarify": 6,
    "challenge": 9,
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
    "clarify": 1,
    "challenge": 17,
    "repair": 0,
    "abstain": 0,
    "ungraded": 0
  },
  "repair": {
    "answer": 0,
    "clarify": 0,
    "challenge": 0,
    "repair": 0,
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
{"precision": 0.1111111111111111, "recall": 0.0625, "f1": 0.08, "support": 16}

Inspect disagreements in the JSON predictions; do not lower thresholds to pass.
