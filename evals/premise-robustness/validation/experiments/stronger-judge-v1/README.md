# Controlled stronger-judge experiment

Status: integration implemented; consult the comparison report for measured arm status. This is an agent-reference development experiment, not human validation.

## Frozen conditions

- Same reviewed judge-v2 prompt and rubric, frozen by SHA-256.
- Same 68 responses, agent references, claim inventories, case facts, verifier and thresholds.
- Separate backend configurations recorded in manifest.json.
- Qwen3-8B: temperature 0, seed 17, no thinking, 8192 context, 512 output tokens.
- Claude Sonnet 5.5: provider-default sampling (non-default temperature unsupported), between_tools thinking, high effort, 512 output tokens, structured JSON schema. No tool use or caching requested.

This compares configured judges. It cannot isolate architecture from sampling or provider implementation. A reviewed repair example occurs in the prompt, so that item is development feedback, not unseen repair generalization. Full human-schema labeling remains incomplete.

## Commands

Run from evals/premise-robustness. The manifest has already been frozen; do not freeze it again or edit inputs under this experiment ID.

```bash
python3 -m validation.compare_judges --arm local
python3 -m validation.compare_judges
```

The paid arm additionally requires ANTHROPIC_API_KEY supplied securely to the process environment and explicit budget authorization. Do not paste credentials in chat, commit them, or include them in command arguments.

```bash
python3 -m validation.compare_judges --arm frontier --allow-paid
```

The frontier configuration caps the client budget at USD 5 and attempts at 204. Token counting is free per the provider; each generation is reserved before sending. Actual usage is recorded on all returned outputs, including refusals or truncation. Network failures retain their reservation because server-side completion is unknown. The local frontier-usage.json ledger is written before each request and survives process interruption. Do not delete or reset it to retry within the same authorized budget. A new budget requires a separately authorized experiment.

The guard is conservative client accounting at configured rates, not a provider-enforced billing ceiling. Configure an account limit separately if required. Usage/pricing anomalies stop further calls. No automatic transport retry occurs. HTTP error bodies and credentials are not exposed in reports. Run one frontier process at a time; the ledger is not a cross-process transaction service. The orchestrator reports arm statuses in its output; its process exit is not a validation gate. Inspect the comparison status and acceptance results.

## Outputs

Reports are under reports/stronger-judge-v1-local.json, -frontier.json, and -comparison.json, with Markdown counterparts. Historical individual reports cannot be overwritten. The comparison status remains incomplete until both full arms exist; blocked frontier scores are absent, not zero. Model metadata and per-call token costs are recorded for the frontier arm. Raw private request headers and keys are never recorded.

Changing a common input, config, or implementation after freezing requires a new experiment directory and report names. A passing dry run only triggers independent human validation. Keep PR #9 draft and do not merge until the required validation bar is cleared.

## Official sources checked 2026-10-18

- [Claude structured JSON output](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Claude Sonnet 5.5 capabilities and sampling restrictions](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)
- [Thinking configuration for Sonnet 5.5](https://platform.claude.com/docs/en/models/sonnet-5-5/whats-new-sonnet-5-5)
- [Token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)
- [API pricing](https://platform.claude.com/docs/en/about-claude/pricing): USD 2 per million input tokens, USD 10 per million output tokens. Recheck rates before enabling a future paid run.
