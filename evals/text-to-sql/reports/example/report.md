# Text-to-SQL eval report

> These numbers come from the **simulated bot**, which injects known faults so the
> pipeline can be tested without a model. They describe the simulator, not a real
> system. Run with `--bot ollama` for real measurements.

## Headline

| Bot | Pass rate | Accuracy (answerable) | Correct abstention | Confident-wrong rate | Unstable cases |
|---|---|---|---|---|---|
| simulated-overconfident | 61% | 75% | 25% | 15% | 11 |
| simulated-careful | 93% | 90% | 100% | 0% | 2 |

*Confident-wrong rate*: share of the bot's answers that were wrong even though every repeated run agreed. These are the answers users act on, because nothing looks off.

## Confident wrong answers (simulated-overconfident)

| Case | Question | Cost | Why it failed | Owner |
|---|---|---|---|---|
| c22 | What was gross margin in Q3 2026? | 5 | answered; should refuse | prompt |
| c11 | How many new customers did we sign in Q2 2026? | 3 | missing_test_exclusion: query does not exclude internal test accounts | prompt |
| c23 | Which sales rep closed the most revenue in Q3 2026? | 3 | answered; should refuse | prompt |
| c26 | How are we doing this quarter? | 2 | answered; should clarify | prompt |

## Failures by owner (simulated-overconfident)

| Owner | Failures | Typical fix |
|---|---|---|
| prompt | 11 | ask when a term does not match; refuse out-of-scope questions |

## Metamorphic checks (simulated-overconfident)

30 relations checked (10 hand-written, 20 generated paraphrase sets), **7 violated**. None of these checks uses a reference answer.

| Relation | Type | Why it should hold | What broke |
|---|---|---|---|
| m01 | equivalent | three phrasings of the same metric and month | 'Sept 2026 MRR' disagrees: expected 1,462,243, got 1,503,794 |
| m02 | equivalent | relative and absolute dates must agree (today is 2026-10-01) | 'What was MRR in September 2026?' disagrees: expected 1,462,632, got 1,462,243 |
| p-c03 | equivalent | surface paraphrases of c03 | 'Hey bot, what is our current ARR?' disagrees: expected 17,551,584, got 17,546,922 |
| p-c04 | equivalent | surface paraphrases of c04 | 'Quick question: How much revenue did we collect in Q3 2026?' disagrees: expected 3,944,075, got 4,468,055 |
| p-c02 | equivalent | surface paraphrases of c02 | 'Quick question: What was MRR last month?' disagrees: expected 1,462,632, got 1,462,243 |
| p-c05 | equivalent | surface paraphrases of c05 | 'Hey bot, what's our year-to-date revenue?' disagrees: expected 10,890,880, got 10,632,575 |
| p-c13 | equivalent | surface paraphrases of c13 | 'Quick question: How many active accounts do we have?' disagrees: expected 401, got 409 |

## When should the bot stay quiet? (simulated-overconfident)

![risk-coverage](risk_coverage.png)

| Threshold | Coverage | Accuracy of answers | Wrong answers | Expected cost |
|---|---|---|---|---|
| 0.0 | 93% | 58% | 11 | 43 |
| 0.6 | 93% | 58% | 11 | 43 |
| 0.8 | 79% | 59% | 9 | 39 |
| 1.0 | 61% | 76% | 4 | 19 **<- lowest cost** |

Self-consistency catches unstable answers. It cannot catch a bot that is wrong the same way every time; those need the trap set and the rule checks.

## How much to trust the grader (simulated-overconfident)

Measured against faults the simulator injected on purpose.

| Injected fault | Caught | Injected | Recall |
|---|---|---|---|
| date_window | 11 | 11 | 100% |
| overanswer | 29 | 29 | 100% |
| substitution | 14 | 14 | 100% |

False alarms on clean runs: 0 of 86 (0%).

## Does the eval protect the semantic model?

24 deliberate model mutations. **13 caught**, 2 blind spots, 9 with no effect on today's data.

**Blind spots** (the metric changed and no test noticed):

- involuntary_churned_accounts: time column end_date changed to start_date
- monthly_active_users: SUM changed to AVG

**No effect on current data** (redundant today, unprotected if the data changes):

- churned_accounts: filter `status = 'canceled'` removed
- churned_accounts: COUNT DISTINCT changed to COUNT
- involuntary_churned_accounts: filter `status = 'canceled'` removed
- involuntary_churned_accounts: COUNT DISTINCT changed to COUNT
- new_accounts: filter `is_test = FALSE` removed
- new_accounts: COUNT DISTINCT changed to COUNT
- paying_accounts: filter `mrr_usd > 0` removed
- paying_accounts: COUNT DISTINCT changed to COUNT
- avg_csat: filter `csat_score IS NOT NULL` removed

| Metric | Cases | Mutants | Caught | Blind spots |
|---|---|---|---|---|
| mrr | 5 | 1 | 1 | 0 |
| arr | 1 | 1 | 1 | 0 |
| revenue | 4 | 3 | 3 | 0 |
| churned_accounts | 5 | 4 | 2 | 0 |
| involuntary_churned_accounts | 2 | 4 | 1 | 1 |
| new_accounts | 1 | 2 | 0 | 0 |
| paying_accounts | 2 | 2 | 0 | 0 |
| api_calls | 1 | 1 | 1 | 0 |
| monthly_active_users | 0 | 1 | 0 | 1 |
| support_tickets | 1 | 0 | 0 | 0 |
| avg_csat | 1 | 2 | 1 | 0 |
| refunded_invoices | 1 | 2 | 2 | 0 |
| (global filters) | 28 | 1 | 1 | 0 |
