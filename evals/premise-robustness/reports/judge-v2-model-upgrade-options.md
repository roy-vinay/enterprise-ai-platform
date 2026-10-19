# Judge v2: model-upgrade options

Planning estimates checked 2026-10-18. No larger model was downloaded and no paid API was called.

| Option | Cost and feasibility | Engineering effort estimate | Evaluation plan |
|---|---|---|---|
| Qwen3-30B-A3B via Ollama | Official Q4_K_M weights are about 19 GB, before runtime and KV-cache memory. The current Mac has 16 GB unified memory, so this is not a practical memory-resident option here. Use an existing host with at least 32 GB as a planning minimum, then measure memory with 8192 context. No per-request API charge; hardware/rental/electricity are not priced. | 2-4 hours to provision an existing suitable host, pull and pin the model, check context and schema behavior, then run. Download and inference duration depend on that host and are not benchmarked. | Same frozen 68 references, prompt, thresholds, verifier, and digest recording. A stronger related model can still share errors; it does not validate the references. |
| Frontier API judge, Claude Sonnet 5.5 example | Published rates: $2/million input tokens and $10/million output tokens. Planning 6000 input and 512 output tokens per response: 68 * (6000*2 + 512*10)/1,000,000 = $1.16416 per pass. At most 3 attempts per response gives about $3.49 under these assumptions; allow a $5 budget. Actual token usage and hidden reasoning may differ; set a hard output limit, record usage, and recheck rates before use. No caching discount assumed. | 0.5-1 engineering day to implement the currently unimplemented API backend, credentials, strict schema or equivalent validation, retry/error semantics, usage accounting, and offline transport tests. | Reserve implementation for milestone 5. Pin an available model version, keep references separate from model inputs, and report a distinct experiment. No assumption it will pass. |
| Ten-response human pilot | No API spend; plan 30-45 minutes of Vinay's time, including reading the rubric and discussing disagreements. This is an estimate. | Less setup than another prompt iteration; no labels are collected in this build. | Inspect 10 stratified disputed and control examples, including repairs, temporal scope, polite endorsements, and false corrections. Use it to audit reference quality; it is not the two-reviewer validation or a population accuracy estimate. |

## Recommendation if v2 fails

Audit a small set of disputed agent references before another prompt iteration. The eight repair references were authored with the responses and may encode the author's preferred interpretation. A ten-response human pilot can expose ambiguous labels at lower effort than provisioning a new local machine. If labels appear sound and model errors persist, use a separately budgeted frontier comparison in milestone 5, or Qwen3-30B on suitable existing hardware. Preserve v1 and v2 runs and all thresholds.

## Sources

- [Ollama Qwen3-30B-A3B model and weight details](https://ollama.com/library/qwen3:30b-a3b)
- [Anthropic official API pricing](https://platform.claude.com/docs/en/about-claude/pricing)

Hardware feasibility and engineering hours are planning judgments, not vendor guarantees. Model quality on this task has not been measured for either upgrade.
