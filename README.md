<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/assets/masthead-dark.svg">
  <img src=".github/assets/masthead-light.svg" width="100%" alt="Enterprise AI Platform: building, evaluating, and shipping AI decision systems for B2B SaaS. By Vinay Roy.">
</picture>

In enterprise software, the hard part of AI usually isn't getting a model to produce an answer. It's knowing whether people can safely act on that answer. This repo is organized around that question. It starts with evaluation, because every later piece (the data foundations, the delivery surface, the controls around who can ask what) is only as trustworthy as your ability to tell when it is wrong.

Every module runs locally on synthetic data with no API keys, so anything here can be reproduced and checked.

## Modules

| Module | Status | What it does |
|---|---|---|
| [evals/text-to-sql](evals/text-to-sql) | working | An eval pipeline for BI chat bots that measures when they should stay quiet: a trap set with refuse and clarify cases, metamorphic tests that need no answer key, mutation testing of the semantic model, a risk-coverage analysis with a business-weighted cost model and a held-out threshold check, and trust checks that fail right answers produced the wrong way (restricted columns, unpruned scans, writes and file reads). |

## How the modules relate

The eval module defines what "a right answer to the business question" means: metric definitions in a semantic model, reference queries, expected behavior when the question can't or shouldn't be answered, and the cost of getting it wrong. Later modules reuse that harness rather than inventing their own notion of correctness, so any new way of delivering answers can be measured on the same footing.
