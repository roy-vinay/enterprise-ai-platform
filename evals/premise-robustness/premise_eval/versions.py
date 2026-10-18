"""Dataset, prompt, model, and case-set versions.

Every report records these so a number can always be traced back to the
exact inputs that produced it (PRD acceptance criterion: reports carry
dataset, prompt, model, and case-set versions, including the held-out
manifest hash).
"""

DATASET_VERSION = "support-v1"          # datasets/support/{schema,seed}.sql
DATASET_SEED_NOTE = "deterministic"     # fixed dates, no randomness

PROMPT_VERSIONS = {
    "ordinary": "arm-ordinary-v1",
    "critique": "arm-critique-v1",
    "evidence": "arm-evidence-v1",
}

MODEL_VERSION = "fake-model-v1"         # models/fake_model.py (test double)
CASE_SET_VERSION = "dev-thinslice-v1"   # 6 representative pairs
