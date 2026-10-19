# Controlled stronger-judge comparison

Status: incomplete
Human-validated: false. Agent-reference development dry run only.

| Measure | Local 8B | Frontier |
|---|---:|---:|
| Action macro F1 | 0.769 | blocked |
| Flaw macro F1 | 0.930 | blocked |
| Misleading recall | 0.632 | blocked |
| Repair recall | 0.375 | blocked |
| Ungraded | 0 | blocked |

No model-improvement claim is possible until both arms are measured.

## Arm status and cost

local: failed
frontier: blocked
Paid API calls require explicit --allow-paid; ANTHROPIC_API_KEY is also unavailable
{"actual_cost_usd": 0.0, "budget_usd": 5.0, "calls": [], "charged_or_reserved_usd": 0.0, "cost_note": "Client reservation guard at configured prices, not a provider billing guarantee. Unknown transport costs retain full reservation. No cache discounts assumed."}

## Interpretation

Author-generated repair references, not independent human gold.
One repair example is in the prompt; that item is not an unseen test.
Same prompt, rubric, rows and thresholds; provider sampling differs.
No automatic reference edits or threshold changes.

A numerical pass only triggers the separate human-validation step. No merge authorization.
