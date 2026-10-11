# Text-to-SQL eval report

## Headline

| Bot | Pass rate | Accuracy (answerable) | Correct abstention | Confident-wrong rate | Unstable cases | Judge unavailable |
|---|---|---|---|---|---|---|
| ollama-qwen2.5-coder:3b | 21% | 10% | 50% | 17% | 17 | 0 |

*Confident-wrong rate*: share of the bot's answers that were wrong even though every repeated run gave the same answer. These are the answers users act on, because nothing looks off. *Judge unavailable*: runs where the LLM judge errored; they are counted as failures, never as clean passes.

## Confident wrong answers (ollama-qwen2.5-coder:3b)

| Case | Question | Cost | Why it failed | Owner |
|---|---|---|---|---|
| c18 | What was month-over-month MRR growth in September 2026, as a percent? | 4 | SQL error: BinderException: Binder Error: column "month" must appear in the GROUP BY clause or must be part of an aggregate function. | prompt |
| c24 | What will MRR be in December 2026? | 4 | answered; should refuse | prompt |
| c13 | How many active accounts do we have? | 3 | expected 405, got 581 | prompt |

## Failures by owner (ollama-qwen2.5-coder:3b)

| Owner | Failures | Typical fix |
|---|---|---|
| prompt | 22 | ask when a term does not match; refuse out-of-scope questions |

## Metamorphic checks (ollama-qwen2.5-coder:3b)

30 relations checked (10 hand-written, 20 generated paraphrase sets), **20 violated**. None of these checks uses a reference answer. A relation that holds shows consistency, not correctness: answers can be consistently wrong.

| Relation | Type | Why it should hold | What broke |
|---|---|---|---|
| m01 | equivalent | three phrasings of the same metric and month | 'What was monthly recurring revenue for Sep 2026?' disagrees: expected 464,931, got 1,462,243 |
| m02 | equivalent | relative and absolute dates must agree (today is 2026-10-01) | 'What was MRR in September 2026?' disagrees: expected 3,095,121, got 1,462,243 |
| m04 | partition_sum | regional revenue must add up to total revenue (assumes regions are mutually exclusive and every account has exactly one region) | could not read total or parts |
| m08 | subset_bound | voluntary churn is a subset of all cancellations (assumes voluntary churn is defined as a subset of all cancellations) | could not read values |
| m10 | equivalent | synonyms from the semantic model must resolve to the same metric | a phrasing produced a failing query |
| p-c03 | equivalent | surface paraphrases of c03 | a phrasing produced a failing query |
| p-c04 | equivalent | surface paraphrases of c04 | 'Quick question: How much revenue did we collect in Q3 2026?' disagrees: expected 3,944,075, got 3,990,565 |
| p-c19 | equivalent | surface paraphrases of c19 | a phrasing produced a failing query |
| p-c02 | equivalent | surface paraphrases of c02 | a phrasing produced a failing query |
| p-c05 | equivalent | surface paraphrases of c05 | 'Quick question: What's our year-to-date revenue?' disagrees: expected 10,890,880, got 26,148,451 |
| p-c06 | equivalent | surface paraphrases of c06 | mixed behavior across phrasings: ['answer', 'error'] |
| p-c14 | equivalent | surface paraphrases of c14 | 'Hey bot, what was MRR by plan in September 2026?' disagrees: expected 3 rows, got 0 |
| p-c16 | equivalent | surface paraphrases of c16 | mixed behavior across phrasings: ['answer', 'clarify'] |
| p-c07 | equivalent | surface paraphrases of c07 | mixed behavior across phrasings: ['answer', 'clarify'] |
| p-c15 | equivalent | surface paraphrases of c15 | mixed behavior across phrasings: ['answer', 'clarify'] |
| p-c18 | equivalent | surface paraphrases of c18 | a phrasing produced a failing query |
| p-c08 | equivalent | surface paraphrases of c08 | 'How many customers churned in Q3 2026 please?' disagrees: expected 17, got 0 |
| p-c28 | equivalent | surface paraphrases of c28 | a phrasing produced a failing query |
| p-c10 | equivalent | surface paraphrases of c10 | 'Hey bot, how many customers did we lose to competitors in 2026?' disagrees: expected 0, got 10 |
| p-c13 | equivalent | surface paraphrases of c13 | 'Quick question: How many active accounts do we have?' disagrees: expected 581, got 600 |

## When should the bot stay quiet? (ollama-qwen2.5-coder:3b)

![risk-coverage](risk_coverage.png)

The bot answers only when its runs agree at least this often. Agreement is a coarse consistency signal, not a calibrated probability of being right.

| Agreement threshold | Coverage | Accuracy of answers | Wrong answers | Cost |
|---|---|---|---|---|
| 0.00 | 64% | 11% | 16 | 70 |
| 0.33 | 64% | 11% | 16 | 70 |
| 0.67 | 32% | 22% | 7 | 39 |
| 1.00 | 14% | 25% | 3 | 28 |
| abstain all | 0% | n/a | 0 | 20 (lowest, in-sample) |

**Held-out check.** The lowest-cost row above is chosen on the same cases it is scored on, which flatters it. Below, the threshold is chosen on one half of the cases and scored on the other, both ways round. With this few cases, treat it as exploratory.

| Fold | Threshold chosen on dev | Test cost | Test cost if it always answered | Test coverage |
|---|---|---|---|---|
| A->B (14/14) | abstain all | 10 | 32 | 0% |
| B->A (14/14) | abstain all | 10 | 38 | 0% |

Agreement catches unstable answers. It cannot catch a bot that is wrong the same way every time; those need the trap set and the rule checks.
