# Text-to-SQL evals: measuring when a BI bot should stay quiet

BI chat bots answer business questions in plain English, and people act on the answers. The dangerous failure is not the bot that crashes or says "I don't know." It is the bot that returns a clean, confident number for a slightly different question than the one asked, and nobody notices.

Most text-to-SQL evals ask one question: did the generated SQL match the expected result? This module asks the questions a team running a BI bot in production actually needs answered:

1. **Does the bot know when not to answer?** Refusing and asking for clarification are scored as first-class outcomes, not as failures.
2. **Can we find wrong answers without writing an answer key for every question?** Metamorphic tests check that answers are consistent with each other.
3. **Would the eval notice if someone broke the semantic model?** Mutation testing breaks it on purpose and checks.
4. **Where should the bot draw the line?** A risk-coverage curve and a business-weighted cost model turn "how accurate is it" into "how much run-to-run agreement should it need before it answers."
5. **Can we trust the grader?** The grader is itself measured against injected faults. Agreement with human labels is supported, but no independently reviewed label set is published yet.

Everything runs locally on a synthetic B2B SaaS warehouse in DuckDB, with no API keys. A simulated bot with labeled failure modes lets the whole pipeline run in CI; an Ollama adapter evaluates real open models.

![risk-coverage curve](reports/example/risk_coverage.png)

## Quickstart

```bash
cd evals/text-to-sql
pip install -r requirements.txt
python -m t2s_eval.cli build-data     # synthetic warehouse, seeded and reproducible
python -m t2s_eval.cli run            # full report in reports/latest/report.md
```

To evaluate a real model:

```bash
ollama pull qwen2.5-coder:7b
python -m t2s_eval.cli run --bot ollama --model qwen2.5-coder:7b --llm-judge
```

Real-model runs record every raw response (`responses-*.jsonl`), so a run can be re-graded later without calling the model again:

```bash
python -m t2s_eval.cli run --bot replay --responses reports/ollama/responses-ollama-qwen2.5-coder_7b.jsonl
```

Other commands: `python -m t2s_eval.cli lint` checks that every test case can actually catch its plausible wrong answer, and `python -m t2s_eval.cli gate` fails CI when a change to the semantic model breaks an answer that used to be right. The gate also fails when a previously passing case is deleted or a relation that held turns inconclusive; to accept that on purpose, update `baseline/baseline.json` so the change shows up in review. See the [example report](reports/example/report.md).

## How it works

```
trap_set/cases.yaml        question, expected behavior, reference SQL, tempting wrong SQL, cost
metamorphic/relations.yaml consistency relations that need no answer key
model/semantic_model.yaml  what the bot is told about the business
          |
          v
  bot adapter (simulated | ollama | yours)  ->  action + interpretation + SQL
          |
          v
  grade each run
    behavior   answered, asked or refused, compared with what was acceptable
    rules      structural SQL checks (substitution, missing filters, summed snapshots...)
    result     bot result vs reference result, recomputed at test time
          |
          v
  repeat N times -> majority vote on pass/fail (ties fail) + run-to-run agreement
          |
          v
  report: confident-wrong rate, owner routing, metamorphic violations,
          risk-coverage curve, grader recall, mutation score and blind spots
```

**Store queries, not answers.** Each case stores the SQL that produces the right answer, not the number. Numbers go stale as data changes; a query recomputes the truth at the moment of the test.

**Every failure has an owner.** A failed check is routed to the semantic model (add or fix a definition), the prompt (ask when a term does not match, refuse out-of-scope questions) or the app (message handling, truncation notices), so a failing eval turns into a ticket for the right person.

### The trap set

28 cases across totals, time windows, breakdowns, rankings, rates, metric definitions, traps and refusals. Each case can carry a `tempting_sql`: the plausible wrong query a confident bot would run. The linter verifies that every tempting answer actually fails its case. See the [dataset card](trap_set/README.md).

### Metamorphic tests

Writing reference SQL is the expensive part of any eval. Metamorphic relations need none:

| Relation | Example |
|---|---|
| equivalent | "MRR last month" and "MRR in September 2026" must match when today is 2026-10-01 |
| partition_sum | revenue by region must add up to total revenue |
| subset_bound | Enterprise churn cannot exceed total churn |
| monotonic | revenue January to September cannot be less than January to June |

The runner also generates surface paraphrases of every answerable case ("Quick question: ...", "... please?") and checks that the answer does not move.

A relation that holds shows consistency, not correctness: a bot can be consistently wrong. Each relation also rests on assumptions about the data, written next to it in `assumes`. Cumulative revenue only grows, for example, if refunds are a status rather than negative rows. Where an assumption can be checked in SQL (`assumes_sql`), a broken one turns the relation inconclusive instead of letting it be trusted.

### Mutation testing the semantic model

The semantic model is code, so it gets tested like code. The mutation tester applies one plausible human mistake at a time (drop a filter, change an aggregation, point a metric at the wrong date column, delete a global filter), reruns everything, and records whether any test noticed. Survivors are split into real blind spots (the metric changed and no test caught it) and mutations with no effect on today's data (a redundant filter, for example, which is harmless now and unprotected if the data shifts).

### Selective answering

Ask each question N times. Agreement is the share of runs that give the most common answer (row order counts for rankings). Sweep a threshold below which the bot abstains, from "answer everything" to "abstain on everything", and for each threshold measure coverage, accuracy of the answers it still gives, and a cost where each wrong answer costs its case's `cost_weight` (1 to 5) and each unnecessary abstention costs one analyst follow-up.

Two cautions are built into the report. Agreement is a coarse consistency signal, not a calibrated probability of being right: with three runs it takes only three values, and a bot that is wrong the same way every time scores full agreement. And the lowest-cost threshold is chosen in-sample, so the report also picks the threshold on one half of the cases and scores it on the other. With 28 cases that check is exploratory, not a result.

The headline metric is the **confident-wrong rate**: wrong answers given with full self-agreement. These are the answers users act on, because nothing about them looks uncertain.

## Real-model results

Two local models, qwen2.5-coder 3B and 7B, on all 28 cases with 3 runs each, run on CPU-only GitHub runners. Every raw response is in [`reports/real/`](reports/real), so these numbers can be re-graded with `--bot replay`.

| | 3B | 7B |
|---|---:|---:|
| Accuracy on answerable questions | 15% | 50% |
| Correct clarify or refuse | 50% | 62% |
| Cases where runs disagreed | 17 of 28 | 9 of 28 |
| Wrong answers that were unanimous across runs | 20% | 42% |
| Lowest-cost agreement threshold (hand-off cost 1) | abstain on everything | abstain on everything |

The bigger model is right far more often and far more stable, but more of its mistakes are unanimous, so run-to-run agreement catches less of what is left. Three of those unanimous mistakes: summing twelve monthly MRR snapshots into one "2025 MRR" (about 10x too high), counting every account that ever paid as "active" (581 instead of 405), and dropping the test-account filter (MRR about 3% too high). Comparing agreement against a single run with the deterministic SQL checks (in-sample, since the checks were built on this trap set) is written up in [D-003](https://github.com/roy-vinay/ai-decision-log/blob/main/decisions/D-003-when-should-a-bi-bot-stay-quiet.md).

Grading the first real run also caught five bugs in this harness, all fixed with tests: a time-filter rule that missed `YEAR()`/`QUARTER()`, a filter-value rule that read function arguments as filters, `CURRENT_DATE` reading the runner's clock instead of the eval's fixed date, a ranking compare that failed an account returned by id instead of name, and two misleading error messages. A simulated bot only finds the failures you imagined; a real one finds the ones in your grader.

## What building this surfaced

These came out of running the pipeline against its own simulator, and they apply to any BI bot eval.

- **Tolerance can hide a wrong time window.** MRR moves a fraction of a percent month to month, so under a 0.1% tolerance an answer for August passed a question about September. Fault injection caught it (the grader's recall on date-window faults was 36% before the fix). The linter now shifts every reference query by one month and fails any case that cannot tell the difference.
- **One test per metric can pass by coincidence.** A mutation that dated nonpayment cancellations by start date instead of end date survived, because the single test for that metric happened to produce the same count either way.
- **"Abstain on everything" is a real baseline.** Once the sweep included it, never answering came within one point of the best threshold for the overconfident simulated bot, and one held-out fold chose it outright. A bot that guesses on refusal and trap questions can be worth less than no bot at all under a cost model like this one.
- **Many semantic model filters are redundant on today's data.** Dropping `csat_score IS NOT NULL` changes nothing because `AVG` already skips nulls; dropping `status = 'canceled'` changes nothing while `canceled_by` is only set on canceled rows. Fine today, silently wrong the day the data changes.
- **Agreement is not enough.** It catches answers that wobble between runs. It cannot catch a bot that is wrong the same way every time, which is exactly the confident failure that hurts. That is what the trap set and rule checks are for.

## Plug in your own bot

Implement one method and return a `BotResponse`:

```python
from t2s_eval.bots.base import BotResponse

class MyBot:
    name = "my-bot"
    def ask(self, question: str, run: int = 0) -> BotResponse:
        out = call_my_bot(question)              # your API
        return BotResponse(action=out.action,    # answer | clarify | refuse
                           interpretation=out.restatement,
                           sql=out.sql)
```

For a bot built on a warehouse-native text-to-SQL service, call its API directly rather than going through the chat app: it returns the interpretation and SQL with no UI in the loop, which makes runs fast and repeatable. Keep a small separate smoke test through the chat app itself for app-layer issues.

## Layout

```
evals/text-to-sql/
  model/semantic_model.yaml   metrics, filters, dimensions, what is out of scope
  trap_set/                   cases.yaml, dataset card, human-label template
  metamorphic/relations.yaml  consistency relations
  t2s_eval/
    data.py                   synthetic warehouse generator
    semantic.py               model rendering and mutation operators
    bots/                     simulated bot (+ oracle), Ollama adapter, record/replay, interface
    grade.py rules.py db.py   grading, SQL rules, result comparison
    metamorphic.py            relation checks and generated paraphrases
    selective.py              risk-coverage sweep, cost model, chart
    mutation.py               mutation testing and coverage map
    judge.py                  grader validation, optional LLM judge (fails closed on errors)
    lint.py                   can each case catch a wrong answer?
    report.py cli.py
  tests/                      tests for the eval itself
  reports/example/            a committed example run
```

## Limits

- Numbers in the example report come from the simulated bot and describe the simulator, not any real system. Real-model numbers are in [`reports/real/`](reports/real): two small local models on 28 cases, so they are directional.
- The rule checks are tuned to this warehouse's conventions (test accounts, soft deletes, snapshot metrics). The idea transfers; the specific rules need adapting.
- Measuring agreement needs several runs per question, which multiplies cost for hosted models. Local models make that cheap.
