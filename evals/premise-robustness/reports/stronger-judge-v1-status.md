# Stronger-judge experiment status

The frontier integration is implemented and offline-tested, but the paid arm is not measured. ANTHROPIC_API_KEY is absent from this execution environment, and paid enablement is off. Claude chat access and a Codex session do not automatically provide a billable Claude API credential. No paid API request has been made.

The frozen experiment contains 68 unchanged responses and agent references, the reviewed judge-v2 prompt/rubric, unchanged thresholds, and separate local/frontier configurations. See [comparison](stronger-judge-v1-comparison.md) for current arm measurements and [experiment instructions](../validation/experiments/stronger-judge-v1/README.md) for reproducible commands and accounting limits.

The adapter uses the documented Messages API JSON output schema, Models API identity confirmation, between_tools thinking and high effort. Sonnet 5.5 rejects non-default temperature, so the request omits temperature and seed. These decoding differences are recorded; the comparison is not a pure model-size experiment. Real API compatibility is not verified until a credentialed call succeeds. Mocked tests are not model-validation results.

Paid calls require secure environment configuration and explicit --allow-paid authorization. The configured client reservation budget is USD 5, with a persistent ledger and a maximum of 204 generation attempts; it is not a provider-side billing guarantee. A stronger-model numerical pass would still require the separate human validation. No merge is authorized; PR #9 stays draft.

## Measured local arm

All 68 responses were graded. The reviewed-prompt local arm still fails: action
macro F1 is 0.769 (bar 0.80), misleading recall is 12/19 = 63.16% (bar 85%),
and repair recall is 3/8 = 37.5% (bar 70%). Answer recall and clarify precision
also fail their category bars. The revised prompt improves on the historical
V2 dry run, but this comparison changes prompt/rubric instructions, not model.
No stronger-model improvement claim is possible until the frontier arm is run.

The frozen common-input hashes were unchanged throughout the measured local run.
Historical v1 and v2 reports remain intact. The matching frontier arm can use
this manifest once credentials and paid-call enablement are available. Do not
change the experiment's inputs or implementation in place; create a new experiment
ID if any frozen condition needs to change.

## Remaining errors

The reviewed volume-comparison exemplar (`false_premise-11`) is now correctly
recognized as repair, but it is also in the prompt and is not an unseen test.
The invented 37-minute effect in `false_premise-12` now triggers premise acceptance
and coverage flags, yet the model still calls its evidence correct and useful.
The invented 18-hour effect in `unsupported_causal-12` still receives evidence
credit and is not flagged as misleading. `false_premise-03` still lacks an
explicit partial-October qualification, but the model does not flag coverage.
`valid-03` still receives accepted_premise=true despite a valid question. These
are persistent evidence/safety errors, beyond the repair-label confusion.
