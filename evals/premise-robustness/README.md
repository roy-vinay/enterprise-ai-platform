# Premise-robustness eval

> **Research question:** Can evidence-backed premise checking reduce misleading BI answers without making the assistant frustratingly cautious?

Text-to-SQL benchmarks measure whether the SQL is correct. They don't measure whether the *question* deserved an answer. This eval measures what happens when a BI assistant is asked a question with a flawed premise -- a false claim, an ambiguity, missing evidence, an undefined metric, or an assumed causal conclusion -- and whether it answers, clarifies, challenges, repairs, or abstains.

## Current state (milestone 3 implementation, validation pending)

An executable end-to-end pipeline on a small deterministic synthetic
customer-support dataset (24 tickets, Aug-Oct 2026). Candidate responses remain scripted;
the new local LLM judge is implemented but not yet human-validated:

- `datasets/support/` -- schema + deterministic seed (monthly volumes are deliberate: Aug 8, Sep 7, Oct 9)
- `cases/dev/` -- **90 cases** as YAML: 40 flawed questions (8 per flaw type), each with a
  **valid control** (`pair_id` links both directions, matched/related labels), plus 10
  standalone valid questions. Every case carries reference facts, acceptable/prohibited
  claims, and executable SQL assertions
- `RUBRIC.md` -- grading principles: the disclosed-assumption rule for ambiguity, partial-evidence
  grading, mixed-flaw labeling, and time semantics (reference date 2026-10-18)
- `premise_eval/` -- runner, read-only model connections with query budgets, a **verification**
  stage (deterministic SQL assertions, including result-set comparison) kept separate from a
  **judging** stage (local LLM backend plus a smoke-test-only stub)
- `models/fake_model.py` -- scripted test double demonstrating the intended behavior per case
- `prompts/` -- the three experimental arms (ordinary / critique / evidence-backed), versioned
- `cases/heldout/` -- placeholder manifest; held-out runs are refused until the set is authored
  in a separate pass and the manifest is frozen

> **Evaluation scope:** only the 6 thin-slice cases (dev-01 through dev-06) run end to end
> through the fake-model smoke test. All other cases currently receive **assertion checks
> only** (their ground truth is verified against the seeded DB); they are not run through
> any real candidate assistant until milestone 5. The smoke metrics in `reports/` therefore
> describe the 6-case smoke run, not the full set.

## Quickstart

```bash
cd evals/premise-robustness
make setup     # pip install -r requirements.txt
make seed-db   # build data/support.db from datasets/support/
make test      # pytest: case assertions + end-to-end smoke run
make run-dev   # fake-model run over cases/dev, JSON report to reports/
```

`make run-heldout` refuses while the held-out manifest is a placeholder.
`make judge-validate` requires approved responses and human gold labels.
`make report` remains a milestone 7 placeholder.

## What this defers

- AdventureWorks as a second dataset (milestone 6 -- after the harness is proven)
- A measured judge agreement result under the active agent-reference protocol
- Held-out authoring (milestone 4)
- Real model runs: Qwen3-8B via Ollama, then frontier APIs (milestone 5)
- The cost-framework report (milestone 7)

## Layout

```
evals/premise-robustness/
  README.md  PRD.md  RUBRIC.md  Makefile  requirements.txt
  datasets/support/      schema.sql, seed.sql (deterministic)
                         customers, agents, support_tickets, ticket_messages,
                         org_events (documented business events: headcount,
                         product, pricing, policy, expansion)
  cases/dev/             90 YAML cases: 40 flawed + 40 valid controls
                         (pair_id, bidirectional; control_type matched/related)
                         + 10 standalone valid
  cases/heldout/         README + placeholder manifest.json
  prompts/               arm-ordinary/critique/evidence.md (versioned)
  premise_eval/          db, runner, verify, local judge, stub, metrics, versions
  validation/            draft responses, reviewer templates, adjudication, scoring
  models/                fake_model.py (test double)
  tests/                 test_assertions.py, test_smoke.py, test_regressions.py
  reports/               smoke outputs (ignored), validation status/results (versioned); reports record
                         dataset, prompt, model, and case-set versions
```

See `PRD.md` (versioned snapshot; the canonical PRD collection is the source of truth) for the full design.


## Milestone 3: local judge with agent-generated references

**Active protocol: agent-reference agreement.** On 2026-10-18, Vinay authorized
replacing the two-human-reviewer requirement with two separately run labeling
agents and an AI adjudicator. This experiment measures agreement with those
agent-generated labels. It does not establish human-validated accuracy.

### Reference-label provenance

- Vinay approved the exact 60-response set, pinned in `validation/approval.json`.
- Two agents labeled all 60 responses separately using the reviewer packet,
  case facts, and rubric, without author notes or each other's labels.
- The agents drafted for Vinay and Ben, but neither human performed or endorsed
  these labels. Original human sheets remain blank. The labeling agents ran in
  the same assistant environment; shared biases are possible and their model
  versions were not independently recorded.
- The agents agreed on all fields for 57 of 60 responses. Three disagreements
  were resolved by an AI adjudicator with written reasoning in
  `validation/agent-reference/resolutions.csv`.
- `validation/gold.jsonl` is the historical filename for the resulting reference
  labels, **not a claim of human gold**. `gold-provenance.json` explicitly records
  `reference_type: agent_generated_reference` and `human_validated: false`.
- `validation/protocol.yaml` records the active method and limitations. It is
  included in the validation fingerprints. Changing the protocol invalidates
  prior reports rather than silently treating agent labels as human labels.

### Run and inspect

Ollama uses the official `qwen3:8b-q4_K_M` tag. The backend records the resolved
model digest, temperature 0, seed 17, an 8192-token context, disabled thinking,
and a 512-token output cap. These settings reduce variation, not promise
bit-identical results across hardware or runtime versions. No paid backend is wired.

The judge receives the versioned prompt plus **RUBRIC.md verbatim**. It validates
all enum and boolean fields, rejects duplicate keys, retries malformed output
at most twice, then marks it ungraded. Failed deterministic verification cannot
be overruled. Author notes and reference labels are not passed to the judge.

```bash
make test
make judge-validate-sample
make judge-validate
```

`make judge-validate` checks approval and reference provenance, builds a fresh
fixture, verifies case assertions, and scores the local judge. It writes JSON
and Markdown results under `reports/judge-validation-v1.*`. The report includes
flaw/action confusion matrices, per-category precision/recall, macro F1,
misleading-answer precision/recall, and the ungraded rate. In this protocol,
all such scores mean **agreement with agent references**.

The existing thresholds are unchanged: macro F1 at least 0.80 on each task,
all category precision and recall at least 0.70, misleading-answer recall at
least 0.85, and ungraded rate strictly below 5%. Missing category support cannot
pass. Ungraded predictions count as recall misses. A failed bar exits nonzero
and preserves failure analysis; do not lower thresholds to manufacture a pass.

`--judge stub` remains limited to the scripted smoke fixture. `--judge llm`
requires a passing, current report under the **active protocol**. The gate
recomputes scores and checks model, code, prompt, rubric, protocol, reference,
response, case, and dataset identities. A passing agent-agreement report never
becomes evidence of human accuracy. Held-out authoring and real candidate-model
comparisons remain separate milestones.

### Reproduce adjudication

```bash
python3 -m validation.adjudicate \
  validation/ai-drafts/labels-vinay-ai-draft.csv \
  validation/ai-drafts/labels-ben-gibson-ai-draft.csv \
  --reviewer-a "Agent A (drafting for Vinay)" \
  --reviewer-b "Agent B (drafting for Ben)" \
  --resolutions validation/agent-reference/resolutions.csv \
  --resolved-by "AI adjudicator" --protocol agent_reference
```

The original human protocol is still available with `--protocol human`; it
requires distinct named reviewers including Vinay and Vinay's adjudication.
Switching methods requires a matching protocol file and newly generated
provenance. AI sheets must not be relabeled as human review.

### Limits

These 60 authored stress responses are not a random production sample. Labels
may share systematic errors; the three AI-adjudicated decisions are judgments,
not external truth. With ten responses per case category, estimates are coarse.
Flaw type is supplied to the judge as case context, so its flaw-type score is
largely a schema/context consistency check, not evidence of blind flaw discovery.
Action agreement, misleading-answer recall, and error inspection are more
informative behavioral checks. Complete claim extraction and tool-provenance
verification remain outside this scaffold.

### Measured run: acceptance bar failed

The 2026-10-18 local Qwen3-8B run graded all 60 responses. Flaw-type macro F1
was 0.966, action macro F1 0.598, and misleading-answer recall 1/16 (6.25%).
There were no ungraded responses. No reference example was labeled `repair`,
so that required action category also cannot pass. Thresholds remain unchanged;
downstream LLM use remains blocked.

See the [measured report](reports/judge-validation-v1.md) and
[failure analysis](reports/judge-validation-v1-analysis.md). These measure
agent-reference agreement and do not establish human-validated accuracy.
