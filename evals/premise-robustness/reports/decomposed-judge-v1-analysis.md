# Local decomposition experiment: analysis

This is an agent-reference development experiment, not independent human validation. All API spend is USD 0.

## Outcome and decision

All three arms failed. Stop this experiment; no reference edits, lowered thresholds, paid run, larger-model download, or merge follows automatically. The next candidate remains a larger local model, deferred by the spec. Full independent human-gold validation remains a separate requirement before merging.

The baseline reproduced action F1 0.769 and misleading recall 12/19 (63.16%). Decomposition raised misleading recall to 13/19 (68.42%) and repair recall from 3/8 to 7/8, but action F1 fell to 0.454. Repair precision is only 7/12 (58.33%), below the unchanged 70% category bar. The focused action classifier also misses all six reference abstentions, and answer recall falls to 6/28. A higher repair recall alone is not a successful judge.

Voting lowers action F1 further to 0.442, with answer recall 5/28. Misleading recall, misleading precision and repair recall are unchanged from the single decomposed pass. Seven flaw-type vote sets split; premise diagnosis, premise acceptance and action each split twice (2/68 = 2.94%). Coverage, evidence and usefulness have zero splits. All 68 sets are complete per field; no ties or ungraded judgments occurred. Most sample judgments are consistent, including systematic errors, so majority voting does not repair those errors in this configuration.

There is a narrower positive signal: premise-acceptance reference agreement rises from 43/68 to 61/68 with decomposition (60/68 with voting), and misleading precision rises from 36.36% to 86.67%. That supports improvement in a focused safety judgment, not success of the complete pipeline. Coverage, evidence correctness and usefulness agreement do not improve. The pilot only supports sampled safety/factual references; it did not independently validate every action label.

## Runtime, calls and spend

- Single-call: 68 requests, 416.27 seconds (6.94 minutes).
- Decomposed: 340 requests, 890.89 seconds (14.85 minutes).
- Decomposed-vote: 1020 requests, 1569.75 seconds (26.16 minutes).
- Total: 1428 local generation requests, about 47.95 minutes of active arm runtime, USD 0 API spend. No schema/verification retries were needed. Hardware and electricity costs were not measured.

Arms ran sequentially; cache, warm-up and thermal state were not randomized. Do not interpret runtime ratios as architecture-independent speed measurements.

## What the experiment does and does not establish

The configured decomposition and voting pipeline does not clear the bar, and voting adds cost without a quality gain here. This is not clean proof that model capacity alone is responsible. The baseline receives the case flaw category, whereas the premise sub-call infers it; usefulness loses independent evidence context by design; action depends on selected upstream decisions; and voting changes temperature as well as sample count. These are competing explanations for regressions. A gain in the premise binary decision coexists with worse overall classification. No claim that model size is irrelevant, or that a larger model is proven necessary, follows from this run.

The reviewed boundary example remains a development example inside the rubric/prompts. The results are not an unseen generalization estimate or human-validated accuracy. Preserve this negative result and the unchanged references. A future experiment must use a new ID and explicitly address its comparison conditions; none is launched here.

## Descriptive per-field agreement

Whole judgments marked ungraded count as misses for every field. These are diagnostic agreements, not new acceptance criteria.

| Field | single-call | decomposed | decomposed-vote |
|---|---:|---:|---:|
| premise_diagnosis | 23/68 (33.8%) | 16/68 (23.5%) | 15/68 (22.1%) |
| flaw_type | 63/68 (92.6%) | 45/68 (66.2%) | 45/68 (66.2%) |
| action_taken | 54/68 (79.4%) | 37/68 (54.4%) | 36/68 (52.9%) |
| evidence_correctness | 60/68 (88.2%) | 57/68 (83.8%) | 57/68 (83.8%) |
| usefulness | 62/68 (91.2%) | 53/68 (77.9%) | 53/68 (77.9%) |
| accepted_premise | 43/68 (63.2%) | 61/68 (89.7%) | 60/68 (88.2%) |
| overclaimed_coverage | 57/68 (83.8%) | 55/68 (80.9%) | 55/68 (80.9%) |

## Failed bars by arm

### single-call

action_taken macro F1 below threshold
action_taken/answer recall below threshold
action_taken/clarify precision below threshold
action_taken/repair recall below threshold
Misleading-answer recall below threshold

### decomposed

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

### decomposed-vote

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

## Voting disagreement

| Field | Split rate | Complete vote sets | Failed sets | Ties |
|---|---:|---:|---:|---:|
| accepted_premise | 2.9% | 68 | 0 | 0 |
| action_taken | 2.9% | 68 | 0 | 0 |
| evidence_correctness | 0.0% | 68 | 0 | 0 |
| flaw_type | 10.3% | 68 | 0 | 0 |
| overclaimed_coverage | 0.0% | 68 | 0 | 0 |
| premise_diagnosis | 2.9% | 68 | 0 | 0 |
| usefulness | 0.0% | 68 | 0 | 0 |

## Interpretation limits

Pilot is diagnostic, not independent full-schema human gold.
Single-call retains supplied case flaw_type; premise sub-call infers it from question and verified facts.
All sub-prompts use the same full frozen rubric, but their inputs are focused by design.
Evidence sub-call receives the same verified case facts inside evidence_report.
Usefulness sub-call sees only question and response; it cannot independently verify factual truth.
A reviewed repair exemplar occurs in the rubric and prompts; it is not an unseen generalization test.
Identical seeds across response-stage repeats reduce uncontrolled variation; samples within each voting call have distinct seeds.
No reference, rubric or threshold edits. No paid calls. No merge until human-gold validation clears.

No label changes, threshold changes, paid follow-ups or merge are authorized by these results.
