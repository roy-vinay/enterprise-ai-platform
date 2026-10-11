# BI bot trap set (v0.1)

A small, labeled set of business questions for evaluating BI chat bots and text-to-SQL systems, built around the failures that matter in production: answering when the bot should ask or refuse, silently substituting a term, using the wrong time window, and ignoring definitions the business has agreed on.

## What is in a case

| Field | Meaning |
|---|---|
| `question` | what a business user types |
| `expected_behavior` | `answer`, `clarify` or `refuse` |
| `acceptable_behaviors` | every behavior that should pass (some questions can reasonably be answered or clarified) |
| `reference_sql` | the query that produces the right answer, recomputed at test time |
| `tempting_sql` | the plausible wrong query a confident bot would run |
| `compare` | `scalar`, `set` (any row order) or `top_n_ordered` |
| `tolerance` | relative tolerance for numbers |
| `cost_weight` | 1 to 5, the business cost of a confident wrong answer |
| `metrics` | semantic model metrics the case exercises, used for coverage |
| `trap` | one line on what makes the case hard |

## Categories

| Category | Cases | What it tests |
|---|---|---|
| totals | 7 | the basics, plus hidden filters (test accounts, soft deletes, paid-only revenue) |
| time_windows | 2 | relative dates against a fixed "today" |
| breakdowns | 3 | grouped results, compared as sets |
| rankings | 1 | ordered top-N |
| rates | 2 | averages over the right denominator, growth rates |
| definitions | 5 | churn vs. nonpayment, "active", explicit widening of a definition |
| traps | 4 | snapshot metrics summed over time, undefined metrics, terms with no match in the data |
| refusals | 4 | data the warehouse does not have, forecasts |

## Design rules

- **Every tempting answer must fail.** `python -m t2s_eval.cli lint` checks it.
- **Every case must be window sensitive.** Shifting the reference query by one month must change the result beyond tolerance, or the case cannot catch an off-by-one window.
- **Refusing is sometimes the right answer.** A bot that answers "what's our NPS" with CSAT times two fails, even though its SQL runs.

## Using it with your own data

The questions and traps are written against the synthetic warehouse in this repo, but the categories and the shape of each trap transfer directly. To adapt it, rewrite `reference_sql` and `tempting_sql` against your schema, keep the `expected_behavior` labels, and run the linter.
