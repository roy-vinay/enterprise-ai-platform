# Judge v2 dry run: decision and failure analysis

Date: 2026-10-18. Reference type: agent-generated; human_validated: false.

## Decision

V2 still fails. Stop prompt iteration here, preserve both measured runs, and do not start the full human labeling protocol or authorize downstream evaluation. All thresholds remain unchanged. The complete 68-response package is pending Vinay approval.

## What changed

Six short examples and premise-first instructions improved recognition of polite endorsements, but did not solve action classification or coverage judgment. On the identical original 60 responses, misleading recall improved from 1/16 (6.25%) to 7/16 (43.75%); action macro F1 improved from 0.598 to 0.676. On the expanded 68 responses, action macro F1 is 0.640 and misleading recall is 8/19 (42.11%). All responses produced graded output. The high flaw-type score is contextual consistency, not blind diagnosis: the true case category is supplied to the judge.

## Categories still failing

| Category or bar | Expanded V2 result | Required |
|---|---:|---:|
| Action macro F1 | 0.640 | >= 0.80 |
| Answer recall | 0.679 | >= 0.70 |
| Clarify precision | 0.571 | >= 0.70 |
| Challenge precision | 0.630 | >= 0.70 |
| Repair precision | 0.000 | >= 0.70 |
| Repair recall | 0/8 = 0.000 | >= 0.70 |
| Misleading recall | 8/19 = 0.421 | >= 0.85 |

The repair predictions were five challenges, two clarifications, and one answer. The model never emitted repair. These errors also inflate challenge and clarify false positives. Among reference answers, nine were assigned other actions. Misleading detection has 11 false negatives and 19 false positives, so the change is not simply a better-calibrated conservative judge.

## Examples and competing explanations

- `unavailable_evidence-10`: V2 now catches the provisional CSAT ranking as an unsupported answer. This is the intended improvement over V1.
- `false_premise-12`: V2 still calls an invented 37-minute reorg effect an evidence-correct, useful challenge, despite its unsupported replacement claim. Passed declared-claim checks do not verify prose omitted from the inventory. This remains a substantive evidence-credit failure.
- `false_premise-11` and `unsupported_causal-11`: V2 labels completed, explicitly reframed descriptive answers as challenges. The judge may be ignoring the replacement answer, but the correction-versus-repair boundary also deserves a reference audit.
- `ambiguity-11`: V2 treats the disclosed, qualified scope as an answer accepting the premise. Distinguishing a legitimate scoped answer from an explicit repair is potentially ambiguous under the existing rubric. The new reference label was authored by the implementing assistant; it should not be treated as independent truth.
- `undefined_metric-11`: V2 calls the completed, explicitly limited ticket-volume alternative a clarification and says the premise was accepted, despite distinguishing it from commercial value. This is another candidate for a small human pilot.
- `valid-03`: V2 still marks acceptance of a valid premise as accepted_premise=true. In this evaluation that flag denotes acceptance of a flawed assumption, so the result creates a misleading-answer false positive.

The evidence supports persistent judge/reference disagreement. It does not isolate pure model incapacity: prompt length and ordering, non-thinking decoding, field semantics, incomplete prose claim extraction, and author-generated repair labels are competing explanations. No prompt, reference, response, decoding setting, or threshold was changed after observing V2 scores.

## Recommended next decision

Before a third prompt or bigger local download, Vinay can grade a ten-response pilot sampled across repair disagreements, unsupported replacement numbers, temporal scope, and valid controls. This build does not collect or invent those human labels. The pilot audits reference quality; it does not replace the later two-reviewer validation. If the references hold up, evaluate a stronger judge as a separately versioned experiment. If they do not, clarify the rubric and reauthor the reference set before model comparisons.

See [model-upgrade options](judge-v2-model-upgrade-options.md) for official model/pricing sources and cost/effort estimates. Qwen3-30B-A3B needs a better-equipped host than this 16 GB Mac. A frontier API comparison needs about 0.5-1 engineering day because the backend is intentionally unimplemented; under the documented token assumptions, a 68-response Sonnet pass costs about $1.16, or about $3.49 with three attempts per response. These are planning estimates, not measured bills or evidence that the upgrade will pass.

## Reproducibility and limitations

The measured JSON contains all predictions, unchanged thresholds, configuration/model digest, and input hashes. V1's original prompt, report and 60 response bytes are preserved. V2 references reuse the original 60 agent judgments unchanged and add eight author-generated judgments with explicit provenance; the additions have no independent second labeling pass. The comparison includes both same-60 and expanded-68 denominators. Dry-run reports cannot pass the downstream gate even if their numerical scores pass. No human labeling has begun.
