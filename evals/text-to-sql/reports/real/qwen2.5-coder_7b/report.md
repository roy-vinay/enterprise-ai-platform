# Text-to-SQL eval report

## Headline

| Bot | Pass rate | Accuracy (answerable) | Correct abstention | Confident-wrong rate | Unstable cases | Judge unavailable |
|---|---|---|---|---|---|---|
| ollama-qwen2.5-coder:7b | 43% | 35% | 62% | 36% | 9 | 0 |

*Confident-wrong rate*: share of the bot's answers that were wrong even though every repeated run gave the same answer. These are the answers users act on, because nothing looks off. *Judge unavailable*: runs where the LLM judge errored; they are counted as failures, never as clean passes.

## Confident wrong answers (ollama-qwen2.5-coder:7b)

| Case | Question | Cost | Why it failed | Owner |
|---|---|---|---|---|
| c20 | What was total MRR in 2025? | 5 | snapshot_summed_across_time: MRR summed over a range of months | prompt |
| c06 | Revenue by region in September 2026 | 4 | SQL error: BinderException: Binder Error: Referenced column "region" not found in FROM clause! | prompt |
| c14 | What was MRR by plan in September 2026? | 4 | missing_test_exclusion: query does not exclude internal test accounts | prompt |
| c07 | Top 5 accounts by revenue in 2025 | 3 | rank 1: expected ('Account 0464', 456495.81), got (464, 456495.81) | prompt |
| c09 | How many accounts were canceled for nonpayment in 2025? | 3 | missing_time_filter: question names a period but SQL has no date filter | prompt |
| c13 | How many active accounts do we have? | 3 | expected 405, got 581 | prompt |
| c17 | How many invoices were refunded in 2025? | 2 | missing_time_filter: question names a period but SQL has no date filter | prompt |
| c19 | How many API calls did EMEA accounts make in Q2 2026? | 2 | missing_test_exclusion: query does not exclude internal test accounts | prompt |

## Failures by owner (ollama-qwen2.5-coder:7b)

| Owner | Failures | Typical fix |
|---|---|---|
| prompt | 16 | ask when a term does not match; refuse out-of-scope questions |

## Metamorphic checks (ollama-qwen2.5-coder:7b)

30 relations checked (10 hand-written, 20 generated paraphrase sets), **15 violated**. None of these checks uses a reference answer. A relation that holds shows consistency, not correctness: answers can be consistently wrong.

| Relation | Type | Why it should hold | What broke |
|---|---|---|---|
| m01 | equivalent | three phrasings of the same metric and month | 'What was monthly recurring revenue for Sep 2026?' disagrees: expected 1,462,243, got 1,503,794 |
| m02 | equivalent | relative and absolute dates must agree (today is 2026-10-01) | 'What was MRR in September 2026?' disagrees: expected 1,503,794, got 1,462,243 |
| m04 | partition_sum | regional revenue must add up to total revenue (assumes regions are mutually exclusive and every account has exactly one region) | parts sum to 0 but total is 3,944,075 |
| m05 | partition_sum | tickets by segment must add up to all tickets (assumes segments are mutually exclusive and every account has exactly one segment) | parts sum to 0 but total is 2,283 |
| m06 | partition_sum | MRR by plan must add up to total MRR (assumes each MRR row carries exactly one plan) | parts sum to 1,503,794 but total is 1,462,243 |
| m08 | subset_bound | voluntary churn is a subset of all cancellations (assumes voluntary churn is defined as a subset of all cancellations) | could not read values |
| m10 | equivalent | synonyms from the semantic model must resolve to the same metric | 'How many lost customers did we have in Q3 2026?' disagrees: expected 17, got 18 |
| p-c03 | equivalent | surface paraphrases of c03 | 'Quick question: What is our current ARR?' disagrees: expected one value, got 1 rows |
| p-c19 | equivalent | surface paraphrases of c19 | 'Hey bot, how many API calls did EMEA accounts make in Q2 2026?' disagrees: expected 12,623,638, got 12,145,663 |
| p-c02 | equivalent | surface paraphrases of c02 | 'Hey bot, what was MRR last month?' disagrees: expected 1,503,794, got 1,462,243 |
| p-c06 | equivalent | surface paraphrases of c06 | a phrasing produced a failing query |
| p-c16 | equivalent | surface paraphrases of c16 | a phrasing produced a failing query |
| p-c15 | equivalent | surface paraphrases of c15 | 'Hey bot, what was average CSAT for urgent tickets in Q3 2026?' disagrees: expected 3.706, got 3.778 |
| p-c28 | equivalent | surface paraphrases of c28 | a phrasing produced a failing query |
| p-c13 | equivalent | surface paraphrases of c13 | 'How many active accounts do we have please?' disagrees: expected 581, got 0 |

## When should the bot stay quiet? (ollama-qwen2.5-coder:7b)

![risk-coverage](risk_coverage.png)

The bot answers only when its runs agree at least this often. Agreement is a coarse consistency signal, not a calibrated probability of being right.

| Agreement threshold | Coverage | Accuracy of answers | Wrong answers | Cost |
|---|---|---|---|---|
| 0.00 | 79% | 32% | 15 | 52 |
| 0.33 | 79% | 32% | 15 | 52 |
| 0.67 | 71% | 35% | 13 | 45 |
| 1.00 | 50% | 43% | 8 | 33 |
| abstain all | 0% | n/a | 0 | 20 (lowest, in-sample) |

**Held-out check.** The lowest-cost row above is chosen on the same cases it is scored on, which flatters it. Below, the threshold is chosen on one half of the cases and scored on the other, both ways round. With this few cases, treat it as exploratory.

| Fold | Threshold chosen on dev | Test cost | Test cost if it always answered | Test coverage |
|---|---|---|---|---|
| A->B (14/14) | abstain all | 10 | 26 | 0% |
| B->A (14/14) | abstain all | 10 | 26 | 0% |

Agreement catches unstable answers. It cannot catch a bot that is wrong the same way every time; those need the trap set and the rule checks.
