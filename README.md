# Enterprise AI Platform

Building, evaluating, and shipping AI decision systems for B2B SaaS.

This repo collects working modules for the parts of enterprise AI that decide whether people can trust what the system tells them: evaluation, data foundations, and the operating processes around them. Every module runs locally on synthetic data with no API keys.

## Modules

| Module | What it does |
|---|---|
| [evals/text-to-sql](evals/text-to-sql) | An eval pipeline for BI chat bots that measures when they should stay quiet: a trap set with refuse and clarify cases, metamorphic tests that need no answer key, mutation testing of the semantic model, and a risk-coverage curve with a business-weighted cost model. |
