# Text-to-SQL eval report

## Headline

| Bot | Pass rate | Accuracy (answerable) | Correct abstention | Confident-wrong rate | Unstable cases | Judge unavailable |
|---|---|---|---|---|---|---|
| ollama-qwen2.5-coder:3b | 31% | 17% | 58% | 22% | 15 | 0 |

*Confident-wrong rate*: share of the bot's answers that were wrong even though every repeated run gave the same answer. These are the answers users act on, because nothing looks off. *Judge unavailable*: runs where the LLM judge errored; they are counted as failures, never as clean passes.

## Right answer, wrong way

A correct number is not the whole job. These checks grade how each answer was produced: whether it read restricted columns, how many rows it read from storage, and whether it tried to write or read files. Unsafe SQL is never executed.

| Bot | Answers | Right but failed a trust check | Restricted access | Over scan budget | Unsafe SQL | Median rows read | Max rows read |
|---|---|---|---|---|---|---|---|
| ollama-qwen2.5-coder:3b | 67 | 0 (0%) | 0 | 0 | 0 | 8,899 | 156,800 |

*Right but failed a trust check*: runs whose result matched the reference and still failed on access or cost. Counts are over runs, not cases.

## Confident wrong answers (ollama-qwen2.5-coder:3b)

| Case | Question | Cost | Why it failed | Owner |
|---|---|---|---|---|
| c02 | What was MRR last month? | 5 | SQL error: ParserException: Parser Error: Wrong number of arguments provided to DATE function | prompt |
| c06 | Revenue by region in September 2026 | 4 | SQL error: CatalogException: Catalog Error: Table with name regions does not exist! | prompt |
| c10 | How many customers did we lose to competitors in 2026? | 4 | expected 10, got 0 | prompt |
| c24 | What will MRR be in December 2026? | 4 | answered; should refuse | prompt |
| c15 | What was average CSAT for urgent tickets in Q3 2026? | 2 | missing_test_exclusion: query does not exclude internal test accounts | prompt |

## Failures by owner (ollama-qwen2.5-coder:3b)

| Owner | Failures | Typical fix |
|---|---|---|
| prompt | 25 | ask when a term does not match; refuse out-of-scope questions |

## Metamorphic checks (ollama-qwen2.5-coder:3b)

34 relations checked (10 hand-written, 24 generated paraphrase sets), **28 violated**. None of these checks uses a reference answer. A relation that holds shows consistency, not correctness: answers can be consistently wrong.

| Relation | Type | Why it should hold | What broke |
|---|---|---|---|
| m01 | equivalent | three phrasings of the same metric and month | a phrasing produced a failing query |
| m02 | equivalent | relative and absolute dates must agree (today is 2026-10-01) | a phrasing produced a failing query |
| m03 | equivalent | relative and absolute year-to-date must agree | 'How much revenue did we collect from January through September 2026?' disagrees: expected 26,148,451, got 11,374,482 |
| m04 | partition_sum | regional revenue must add up to total revenue (assumes regions are mutually exclusive and every account has exactly one region) | parts sum to 0 but total is 3,990,565 |
| m06 | partition_sum | MRR by plan must add up to total MRR (assumes each MRR row carries exactly one plan) | could not read total or parts |
| m08 | subset_bound | voluntary churn is a subset of all cancellations (assumes voluntary churn is defined as a subset of all cancellations) | subset 18 exceeds superset 7 |
| m10 | equivalent | synonyms from the semantic model must resolve to the same metric | 'How many lost customers did we have in Q3 2026?' disagrees: expected 0, got 7 |
| p-c01 | equivalent | surface paraphrases of c01 | a phrasing produced a failing query |
| p-c03 | equivalent | surface paraphrases of c03 | 'What is our current ARR please?' disagrees: expected 345,085,803, got no value (NULL) |
| p-c04 | equivalent | surface paraphrases of c04 | 'Quick question: How much revenue did we collect in Q3 2026?' disagrees: expected 3,990,565, got 8,011,864 |
| p-c11 | equivalent | surface paraphrases of c11 | 'Hey bot, how many new customers did we sign in Q2 2026?' disagrees: expected 52, got 45 |
| p-c12 | equivalent | surface paraphrases of c12 | 'Quick question: How many paying accounts did we have in September 2026?' disagrees: expected 405, got 418 |
| p-c19 | equivalent | surface paraphrases of c19 | a phrasing produced a failing query |
| p-c02 | equivalent | surface paraphrases of c02 | a phrasing produced a failing query |
| p-c05 | equivalent | surface paraphrases of c05 | a phrasing produced a failing query |
| p-c06 | equivalent | surface paraphrases of c06 | a phrasing produced a failing query |
| p-c14 | equivalent | surface paraphrases of c14 | a phrasing produced a failing query |
| p-c16 | equivalent | surface paraphrases of c16 | mixed behavior across phrasings: ['answer', 'clarify'] |
| p-c07 | equivalent | surface paraphrases of c07 | mixed behavior across phrasings: ['answer', 'clarify'] |
| p-c15 | equivalent | surface paraphrases of c15 | mixed behavior across phrasings: ['answer', 'clarify'] |
| p-c18 | equivalent | surface paraphrases of c18 | a phrasing produced a failing query |
| p-c08 | equivalent | surface paraphrases of c08 | 'Quick question: How many customers churned in Q3 2026?' disagrees: expected 1, got 17 |
| p-c28 | equivalent | surface paraphrases of c28 | 'Quick question: How many customers canceled in Q3 2026, including nonpayment?' disagrees: expected 7, got 25 |
| p-c10 | equivalent | surface paraphrases of c10 | 'Quick question: How many customers did we lose to competitors in 2026?' disagrees: expected 10, got 0 |
| p-a01 | equivalent | surface paraphrases of a01 | mixed behavior across phrasings: ['answer', 'clarify'] |
| p-a02 | equivalent | surface paraphrases of a02 | mixed behavior across phrasings: ['answer', 'clarify'] |
| p-k01 | equivalent | surface paraphrases of k01 | a phrasing produced a failing query |
| p-k02 | equivalent | surface paraphrases of k02 | a phrasing produced a failing query |

## When should the bot stay quiet? (ollama-qwen2.5-coder:3b)

![risk-coverage](risk_coverage.png)

The bot answers only when its runs agree at least this often. Agreement is a coarse consistency signal, not a calibrated probability of being right.

| Agreement threshold | Coverage | Accuracy of answers | Wrong answers | Cost |
|---|---|---|---|---|
| 0.00 | 64% | 17% | 19 | 72 |
| 0.33 | 64% | 17% | 19 | 72 |
| 0.67 | 44% | 25% | 12 | 52 |
| 1.00 | 25% | 44% | 5 | 35 |
| abstain all | 0% | n/a | 0 | 24 (lowest, in-sample) |

**Held-out check.** The lowest-cost row above is chosen on the same cases it is scored on, which flatters it. Below, the threshold is chosen on one half of the cases and scored on the other, both ways round. With this few cases, treat it as exploratory.

| Fold | Threshold chosen on dev | Test cost | Test cost if it always answered | Test coverage |
|---|---|---|---|---|
| A->B (19/17) | abstain all | 12 | 35 | 0% |
| B->A (17/19) | abstain all | 12 | 37 | 0% |

Agreement catches unstable answers. It cannot catch a bot that is wrong the same way every time; those need the trap set and the rule checks.
