# Premise-robustness eval

> **Research question:** Can evidence-backed premise checking reduce misleading BI answers without making the assistant frustratingly cautious?

Text-to-SQL benchmarks measure whether the SQL is correct. They don't measure whether the *question* deserved an answer. This eval measures what happens when a BI assistant is asked a question with a flawed premise -- a false claim, an ambiguity, missing evidence, an undefined metric, or an assumed causal conclusion -- and whether it answers, clarifies, challenges, repairs, or abstains.

## Thin slice (this PR)

An executable end-to-end pipeline on a small deterministic synthetic
customer-support dataset (24 tickets, Aug--Oct 2026), with **no real models**:

- `datasets/support/` -- schema + deterministic seed (monthly volumes are deliberate: Aug 8, Sep 7, Oct 9)
- `cases/dev/` -- 6 representative pairs as YAML, one per flaw type + one valid question, each with reference facts, acceptable/prohibited claims, and executable SQL assertions
- `premise_eval/` -- runner, read-only model connections with query budgets, a **verification** stage (deterministic SQL assertions) kept separate from a **judging** stage (behavioral assessment; currently a stub for milestone 3)
- `models/fake_model.py` -- scripted test double demonstrating the intended behavior per case
- `prompts/` -- the three experimental arms (ordinary / critique / evidence-backed), versioned
- `cases/heldout/` -- placeholder manifest; held-out runs are refused until the set is authored in a separate pass and the manifest is frozen

## Quickstart

```bash
cd evals/premise-robustness
make setup     # pip install -r requirements.txt
make seed-db   # build data/support.db from datasets/support/
make test      # pytest: case assertions + end-to-end smoke run
make run-dev   # fake-model run over cases/dev, JSON report to reports/
```

`make run-heldout` refuses while the held-out manifest is a placeholder.
`make judge-validate` and `make report` are milestone 3 / 7 placeholders.

## What this defers

- AdventureWorks as a second dataset (milestone 6 -- after the harness is proven)
- Scaling to 50 dev pairs (milestone 2)
- The LLM judge + two-reviewer validation protocol (milestone 3; `judge.py` is a clearly labeled stub)
- Held-out authoring (milestone 4)
- Real model runs: Qwen3-8B via Ollama, then frontier APIs (milestone 5)
- The cost-framework report (milestone 7)

## Layout

```
evals/premise-robustness/
  README.md  PRD.md  Makefile  requirements.txt
  datasets/support/      schema.sql, seed.sql (deterministic)
  cases/dev/             6 YAML cases (ground truth + assertions)
  cases/heldout/         README + placeholder manifest.json
  prompts/               arm-ordinary/critique/evidence.md (versioned)
  premise_eval/          db, runner, verify, judge (stub), metrics, versions
  models/                fake_model.py (test double)
  tests/                 test_assertions.py, test_smoke.py
  reports/               JSON run reports (gitignored); every report records
                         dataset, prompt, model, and case-set versions
```

See `PRD.md` (versioned snapshot; the canonical PRD collection is the source of truth) for the full design.
