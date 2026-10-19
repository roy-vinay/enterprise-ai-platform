# decomposed-judge-v1: decomposed-vote

Status: failed
Human-validated: false. Agent-generated reference dry run only.
Local API spend: USD 0. Hardware/electricity costs not measured.
Wall-clock runtime: 1569.75 seconds; model requests: 1020.
Runtime sums active process segments; interrupted downtime is excluded.

Responses: 68; ungraded: 0; macro F1: 0.545

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
| valid | 1.000 | 0.300 | 0.462 | 10 |
| false_premise | 0.600 | 1.000 | 0.750 | 12 |
| ambiguity | 0.667 | 0.667 | 0.667 | 12 |
| unavailable_evidence | 0.833 | 0.500 | 0.625 | 10 |
| undefined_metric | 0.444 | 0.667 | 0.533 | 12 |
| unsupported_causal | 1.000 | 0.750 | 0.857 | 12 |

Confusion matrix, reference rows and prediction columns:

```json
{
  "valid": {
    "valid": 3,
    "false_premise": 1,
    "ambiguity": 0,
    "unavailable_evidence": 0,
    "undefined_metric": 6,
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
    "ambiguity": 8,
    "unavailable_evidence": 1,
    "undefined_metric": 3,
    "unsupported_causal": 0,
    "ungraded": 0
  },
  "unavailable_evidence": {
    "valid": 0,
    "false_premise": 4,
    "ambiguity": 0,
    "unavailable_evidence": 5,
    "undefined_metric": 1,
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
| answer | 1.000 | 0.179 | 0.303 | 28 |
| clarify | 0.389 | 0.875 | 0.538 | 8 |
| challenge | 0.515 | 0.944 | 0.667 | 18 |
| repair | 0.583 | 0.875 | 0.700 | 8 |
| abstain | 0.000 | 0.000 | 0.000 | 6 |

Confusion matrix, reference rows and prediction columns:

```json
{
  "answer": {
    "answer": 5,
    "clarify": 7,
    "challenge": 11,
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

## Per-field vote disagreement

Split rate uses complete three-sample sets as denominator; failed sets remain separately visible.

| Field | Complete sets | Failed sets | Splits | Split rate | Ties |
|---|---:|---:|---:|---:|---:|
| premise_diagnosis | 68 | 0 | 2 | 0.029 | 0 |
| flaw_type | 68 | 0 | 7 | 0.103 | 0 |
| action_taken | 68 | 0 | 2 | 0.029 | 0 |
| evidence_correctness | 68 | 0 | 0 | 0.000 | 0 |
| usefulness | 68 | 0 | 0 | 0.000 | 0 |
| accepted_premise | 68 | 0 | 2 | 0.029 | 0 |
| overclaimed_coverage | 68 | 0 | 0 | 0.000 | 0 |

Per-response JSON includes field-level prompt versions/hashes, sample values, settings, attempts, input hashes and vote decisions.

Pilot is diagnostic, not independent full-schema human gold.
Single-call retains supplied case flaw_type; premise sub-call infers it from question and verified facts.
All sub-prompts use the same full frozen rubric, but their inputs are focused by design.
Evidence sub-call receives the same verified case facts inside evidence_report.
Usefulness sub-call sees only question and response; it cannot independently verify factual truth.
A reviewed repair exemplar occurs in the rubric and prompts; it is not an unseen generalization test.
Identical seeds across response-stage repeats reduce uncontrolled variation; samples within each voting call have distinct seeds.
No reference, rubric or threshold edits. No paid calls. No merge until human-gold validation clears.
