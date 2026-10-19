# Local decomposed judge experiment

All inference is local through 127.0.0.1:11434 using the existing qwen3:8b-q4_K_M model. No keys, paid calls, new model downloads, or external model endpoints are used. Existing frontier code is not invoked. The 16 GB Mac and larger-model alternatives are outside this experiment's scope.

## Arms and frozen conditions

| Arm | Calls per response before retries | Temperature | Seeds |
|---|---:|---:|---|
| single-call | 1 | 0 | 17 |
| decomposed | 5 | 0 | 17 |
| decomposed-vote | 15 | 0.7 | 101, 202, 303 for each sub-call |

All arms use the same 68 response rows, agent references, rubric, unchanged thresholds, installed-model digest, and deterministic database/verifier. Common and new implementation hashes, five sub-prompts and three configs are frozen in manifest.json. Every arm verifies them before running and again before publishing results. Do not modify frozen inputs or this experiment ID to tune results.

Expected request counts without retries: 68, 340, and 1020. Schema/verification retries can increase counts; action calls are skipped when premise/coverage dependencies fail. Reports record actual request counts and active wall-clock time, not estimates. Model requests count HTTP generation attempts, not local identity checks. All arms have USD 0 API spend; hardware and electricity costs are not measured.

## Five focused calls

1. Premise: question, verified case facts and response. Outputs premise_diagnosis, flaw_type and accepted_premise.
2. Coverage: question, verified facts and response. Outputs overclaimed_coverage.
3. Action: question, response, and the already selected premise/coverage outputs as data. Outputs action_taken. It cannot revise those earlier decisions.
4. Evidence: response and verifier report, enriched with the same verified case facts available to the baseline. Failed deterministic checks cannot earn evidence credit. Passed checks cover declared claims only, not all prose.
5. Usefulness: question and response only. Outputs usefulness. This sub-call has no independent fact-verification input, a limitation reported explicitly.

The same full frozen RUBRIC.md is appended to each focused prompt. The deterministic combiner validates all seven full-schema fields. Every response records which sub-prompt version/hash produced each field, all sample judgments, attempts, decoding settings and request-input hashes. Author notes, reference labels, and human pilot judgments are never sent to the model.

The baseline retains its existing case context, including the supplied flaw_type. The premise sub-call instead infers flaw_type from the specified question and verified facts. Its flaw-type score is therefore not directly equivalent to the baseline's contextual-consistency score. Report that distinction when interpreting the experiment.

## Voting and failure policy

Every focused sub-call uses three samples at temperature 0.7 with distinct seeds. Vote separately for each output field. These are not repeated temperature-0 calls. Action samples receive the aggregated premise/coverage decisions, not individual earlier samples.

Every sample may retry twice after a strict schema or verification error. A required sample still failing makes that field ungraded; no sample is silently discarded. Any ungraded field makes the whole response ungraded. Premise/coverage failure skips dependent action classification while preserving other independent sub-call traces.

Boolean ties choose the safety-conservative value: accepted_premise and overclaimed_coverage true; evidence_correctness and usefulness false. With three complete boolean votes there is no tie, but the rule is defined and tested. A three-way categorical tie is ungraded, never an arbitrary label. Reports show split rates among complete vote sets, plus incomplete sets and tie counts separately. Ungraded responses remain misses under unchanged scoring.

## Running and resuming

Run from evals/premise-robustness:

```bash
python3 -m validation.run_decomposed --freeze --all
# If interrupted after freezing, retain checkpoints and resume without --freeze:
python3 -m validation.run_decomposed --all
# Or run a specific arm:
python3 -m validation.run_decomposed --arm decomposed-vote
```

Reports use reports/decomposed-judge-v1-<arm>.json and .md, plus -comparison files. Completed arm reports are never overwritten. Per-response checkpoints and local call-event logs are under the repository's outputs/decomposed-judge-v1-checkpoints directory. Do not delete them to resume. A local backend outage raises and exits nonzero; no partial run becomes a passing report. Do not run two copies of the same arm concurrently.

The runner stops if an arm clears every configured agent-reference bar. That is only a handoff to Vinay and Ben Gibson for independent human labeling and adjudication. No automatic human labels, no reference edits, no threshold changes and no merge. If all arms fail, report the deltas honestly and stop. Larger local models remain deferred.

## Interpretation

The ten-item diagnostic pilot supports sampled factual and coverage references; it is not exhaustive, blind, independent full-schema gold. New repair references were authored with their responses. The reviewed repair boundary example also occurs in prompts/rubric, so it is not an unseen generalization test. A decomposition gain supports better factoring; it does not prove model size irrelevant. Voting gains must be assessed alongside extra calls, runtime, disagreements and ungraded categorical ties. The final milestone requires the judge to clear validation against human gold before merging.
