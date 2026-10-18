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
- Human response-set approval, two independent reviews, and a measured judge-validation result
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


## Milestone 3: validate the judge before trusting it

The local LLM judge uses `validation/judge-config.yaml` (Ollama, an explicit
Qwen3-8B quantization tag, temperature 0, seed 17). Reports record the resolved
model digest. No API keys, paid calls, automatic downloads, or real candidate
model comparisons are included. The frontier backend deliberately raises an
unimplemented error. Fixed decoding settings reduce variation; they do not
promise bit-identical inference across hardware and runtime versions.

The judge receives `prompts/judge-v1.md` plus **RUBRIC.md verbatim**. It infers
behavior from response text, accepts deterministic verifier outcomes, and treats
unsupported prose as unverified. This is a behavioral judgment, not a replacement
for complete claim extraction and tool-provenance checks in later milestones.
All enum fields and all four boolean fields are validated strictly. Invalid JSON,
duplicate keys, missing fields, and contradictory verification retry twice, then
become explicitly ungraded. Backend outages stop validation with an error.

### Approval and independent labeling

1. Review the 60 authored candidates in [`validation/responses.jsonl`](validation/responses.jsonl).
   Ten responses cover each case category, including valid, with repeated cases
   used for contrasting responses. These are designed stress cases, not a random
   estimate of production prevalence. `make judge-validate-sample` prints the fixed
   stratified authoring set in seeded order. **No labels have been authored.**
2. Vinay must approve this exact response set before labeling. Only after explicit
   approval, change `validation/approval.json` to `status: approved` and set
   `approved_by: Vinay`, preserving the matching response SHA-256. Any response edit
   invalidates approval and all derived gold and reports.
3. Vinay selects a second reviewer. Each independently copies
   `validation/label-template.csv`, fills every field, and uses the blind
   `validation/reviewer-packet.jsonl`, the cases, database, and rubric. Do not share
   sheets or view `author_note` while labeling. CSV cannot enforce cell entry itself:
   the importer rejects blanks, string-like values other than literal lowercase
   `true`/`false`, invalid enums, missing IDs, duplicates, and extra IDs.
4. Compare both sheets, naming the reviewers:

   ```bash
   python3 -m validation.adjudicate reviewer-a.csv reviewer-b.csv \
     --reviewer-a Vinay --reviewer-b ReviewerName
   ```

   `validation/adjudication.json` contains exact-record and per-field agreement,
   disagreements, and differing fields. No gold is created while disagreements
   remain. Vinay resolves those responses in a CSV with the same columns, containing
   exactly the disagreement IDs, then reruns with
   `--resolutions resolved.csv --resolved-by Vinay`. Agreement-only sets can produce
   gold directly. Record independence honestly; software cannot prove reviewers did
   not confer. No model-generated labels are substituted for human labels.
5. Start your installed local Ollama model, then run `make judge-validate`.
   This fails if approval or adjudicated gold is absent, before contacting Ollama.
   The scorer creates a fresh temporary fixture and checks all reference assertions.
   Author notes and gold labels are never passed to the judge. Declared claim
   inventories accompany responses for verification; they do not cover all prose.

### Acceptance bar

[`validation/thresholds.yaml`](validation/thresholds.yaml) holds the reviewed bar:
macro F1 at least **0.80 on each task**, no flaw/action category precision or recall
below **0.70**, misleading-answer recall at least **0.85**, ungraded rate strictly
below **5%**. Missing category support scores zero and cannot pass. Ungraded
predictions remain explicit confusion-matrix misses, rather than disappearing
from recall. Rates here validate the judge; research metric definitions are unchanged.

The scorer writes `reports/judge-validation-v1.json` plus a Markdown summary,
including per-category scores, both confusion matrices, macro F1, misleading
precision/recall, and ungraded IDs. A failed bar exits nonzero and records the
failing categories; investigate those failures without lowering the bar.

`--judge stub` remains the default for the six scripted smoke cases.
`--judge llm` requires a passing, current validation report. The gate recomputes
scores from saved predictions against gold and checks response, rubric, prompt,
case, dataset-script, implementation, configuration, threshold, approval, and model
identities. Held-out runs require this gate even if their manifest is frozen.
Real candidate-model execution remains unimplemented and cannot bypass it.

**Current status: awaiting Vinay's response-set approval and a second reviewer.**
The committed report is a pending-status artifact with null scores, not a passing
validation or an assertion that the judge is trustworthy. Human labeling, scoring,
and the acceptance-bar decision are intentionally pending.
