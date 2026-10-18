# Agent-reference judge evaluation: failure analysis

Date: 2026-10-18

## Decision

The Qwen3-8B judge did not clear the unchanged acceptance bar. Downstream LLM and held-out use remains blocked. This is agreement with agent-generated references, not human-validated accuracy.

## Measured result

| Measure | Result | Required |
|---|---:|---:|
| Flaw-type macro F1 | 0.966 | >= 0.80 |
| Action macro F1 | 0.598 | >= 0.80 |
| Combined macro F1 | 0.782 | Both individual tasks must pass |
| Misleading-response recall | 1/16 = 6.25% | >= 85% |
| Misleading-response precision | 1/9 = 11.11% | Reported |
| Ungraded responses | 0/60 | < 5% |

Category failures include answer recall (0.429), clarify precision (0.533), challenge precision (0.654), and repair precision/recall (0.000).

## Observed disagreements

- `unavailable_evidence-10`: the response ranks Maya first for satisfaction using rapid resolution as a proxy, with a survey caveat. References label it an answer accepting an unsupported premise; the judge calls it a useful challenge. The judge appears to credit caution without recognizing the unsupported recommendation.
- `false_premise-03` and `unsupported_causal-06`: references mark unqualified October comparisons as coverage overclaims because October is partial. The judge does not. These illustrate a sensitivity difference about temporal qualifications; agent references are not independent proof that every such interpretation is correct.
- `valid-03`: a correctly scoped P2 average is marked `accepted_premise: true` by the judge. References reserve that flag for accepting a flawed premise. This creates a misleading-response false positive and suggests confusion about the field semantics.

## Reference-set limitations

Two separately run labeling agents agreed on 57/60 complete records. An AI adjudicator resolved the remaining three; all identities, original sheets, resolutions, and hashes are recorded. The agents ran in the same assistant environment and can share biases. Their model versions were not independently recorded. No human completed a label sheet.

There are zero reference examples of the `repair` action, despite its being a required category. The scorer correctly assigns unsupported categories zero and fails the bar. This is a reference-set coverage defect as well as an observed model disagreement result. No labels or thresholds were changed after viewing these scores.

The judge receives the case's ground-truth flaw category. Its high flaw-type F1 therefore measures contextual consistency rather than blind flaw detection. The 60 authored stress responses are not a random production sample. Do not interpret these scores as deployment accuracy or a comparison of real candidate assistants.

## Next iteration

1. Clarify the judge instructions about behavior actually expressed, unsupported recommendations despite caveats, false-premise acceptance, and partial-period scope.
2. Add independently authored, unambiguous repair examples and verify action-category coverage before scoring. Version the response set and obtain approval for the changed set.
3. Audit disputed temporal labels and use a separate fresh response set to assess any prompt changes; do not repeatedly tune to this measured set.
4. Evaluate a stronger judge or decoding configuration as a separately identified experiment. Preserve this failed run and all thresholds.
5. Human review of a sample would strengthen the evidence, but this active protocol does not claim it occurred.
