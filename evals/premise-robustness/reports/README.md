# Reading a smoke-test report

**A smoke test demonstrates pipeline behavior, not model performance.** The current model is scripted and the judge is a test double. Zero errors are expected fixture outcomes, not evidence of reliability.

| Field | Meaning |
|---|---|
| `run_kind` / `research_results` | Identifies the scripted run; research results are `false`. |
| `limitations` | What this run cannot establish. |
| `versions` | Named versions plus SHA-256 hashes of cases, prompts, dataset scripts, and scripted model. |
| `cases[].response_text` | Exact scripted answer retained for inspection. |
| `cases[].claim_verification` | Checks declared values against assertion SQL; does not verify all prose or query provenance. |
| `cases[].judgment` | Stub behavior assessment; uses ground truth and assumes usefulness. |
| `metrics` | Aggregate fixture checks. Rates are not validated research findings. |

The fake model does not execute the selected prompt or SQL tools. Reports from different arms are not experimental comparisons. The current fixtures do not exercise a successful repair; a zero repair rate is expected.

Generated `report-*.json` files remain local and ignored. Use `make run-dev` after seeding the database to create one.
