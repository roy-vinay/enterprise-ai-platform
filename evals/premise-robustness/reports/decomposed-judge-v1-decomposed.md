# decomposed-judge-v1: decomposed

Status: failed
Human-validated: false. Agent-generated reference dry run only.
Local API spend: USD 0. Hardware/electricity costs not measured.
Wall-clock runtime: 890.89 seconds; model requests: 340.
Runtime sums active process segments; interrupted downtime is excluded.

Responses: 68; ungraded: 0; macro F1: 0.554

## Acceptance failures

flaw_type macro F1 below threshold
flaw_type/valid recall below threshold
flaw_type/false_premise precision below threshold
flaw_type/ambiguity precision below threshold
flaw_type/ambiguity recall below threshold
flaw_type/unavailable_evidence recall below threshold
flaw_type/undefined_metric precision below threshold
flaw_type/undefined_metric recall below threshold
action_taken macro F1 below threshold
action_taken/answer recall below threshold
action_taken/clarify precision below threshold
action_taken/challenge precision below threshold
action_taken/repair precision below threshold
action_taken/abstain precision below threshold
action_taken/abstain recall below threshold
Misleading-answer recall below threshold

## flaw_type

| Category | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| valid | 1.000 | 0.400 | 0.571 | 10 |
| false_premise | 0.571 | 1.000 | 0.727 | 12 |
| ambiguity | 0.636 | 0.583 | 0.609 | 12 |
| unavailable_evidence | 0.714 | 0.500 | 0.588 | 10 |
| undefined_metric | 0.500 | 0.667 | 0.571 | 12 |
| unsupported_causal | 1.000 | 0.750 | 0.857 | 12 |

Confusion matrix, reference rows and prediction columns:

```json
{
  "valid": {
    "valid": 4,
    "false_premise": 1,
    "ambiguity": 0,
    "unavailable_evidence": 0,
    "undefined_metric": 5,
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
    "ambiguity": 7,
    "unavailable_evidence": 2,
    "undefined_metric": 3,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "unavailable_evidence": {
    "valid": 0,
    "false_premise": 5,
    "ambiguity": 0,
    "unavailable_evidence": 5,
    "undefined_metric": 0,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "undefined_metric": {
    "valid": 0,
    "false_premise": 0,
    "ambiguity": 4,
    "unavailable_evidence": 0,
    "undefined_metric": 8,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "unsupported_causal": {
    "valid": 0,
    "false_premise": 3,
    "ambiguity": 0,
    "unavailable_evidence": 0,
    "undefined_metric": 0,
    "unsupported_causal": 9,
    "ungraded": 0
  }
}
```

## action_taken

| Category | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| answer | 1.000 | 0.214 | 0.353 | 28 |
| clarify | 0.389 | 0.875 | 0.538 | 8 |
| challenge | 0.531 | 0.944 | 0.680 | 18 |
| repair | 0.583 | 0.875 | 0.700 | 8 |
| abstain | 0.000 | 0.000 | 0.000 | 6 |

Confusion matrix, reference rows and prediction columns:

```json
{
  "answer": {
    "answer": 6,
    "clarify": 7,
    "challenge": 10,
    "repair": 5,
    "abstain": 0,
    "ungraded": 0
  },
  "clarify": {
    "answer": 0,
    "clarify": 7,
    "challenge": 1,
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
    "clarify": 1,
    "challenge": 0,
    "repair": 7,
    "abstain": 0,
    "ungraded": 0
  },
  "abstain": {
    "answer": 0,
    "clarify": 2,
    "challenge": 4,
    "repair": 0,
    "abstain": 0,
    "ungraded": 0
  }
}
```

## misleading

| Category | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| misleading | 0.867 | 0.684 | 0.765 | 19 |
| not_misleading | 0.887 | 0.959 | 0.922 | 49 |

Confusion matrix, reference rows and prediction columns:

```json
{
  "misleading": {
    "misleading": 13,
    "not_misleading": 6,
    "ungraded": 0
  },
  "not_misleading": {
    "misleading": 2,
    "not_misleading": 47,
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
