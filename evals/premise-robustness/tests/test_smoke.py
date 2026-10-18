"""End-to-end smoke test: seed -> fake model -> verify -> judge stub -> metrics.

The fake model is scripted to do the intended thing on every case, so the
expected metric values are exact: zero failures, full valid completion.
If these drift, the pipeline (not the model) is broken.
"""

from pathlib import Path

import pytest

from premise_eval import db as db_mod
from premise_eval import runner as runner_mod


@pytest.fixture()
def db_path(tmp_path):
    return db_mod.build_db(tmp_path / "smoke.db")


def test_smoke_run_metrics(db_path):
    report = runner_mod.run(split="dev", model_name="fake", arm="ordinary", db_path=db_path)
    m = report["metrics"]
    assert m["n_total"] == 6
    assert m["n_flawed"] == 5
    assert m["n_valid"] == 1
    assert m["misleading_answer_rate"] == 0.0
    assert m["unnecessary_intervention_rate"] == 0.0
    assert m["verified_useful_repair_rate"] == 0.0
    assert m["false_correction_rate"] == 0.0
    assert m["valid_task_completion"] == 1.0


def test_report_carries_versions(db_path):
    report = runner_mod.run(split="dev", model_name="fake", arm="ordinary", db_path=db_path)
    v = report["versions"]
    for key in ("dataset", "prompt_version", "model_version", "case_set", "heldout_manifest_sha256"):
        assert v[key], f"report missing version: {key}"


def test_heldout_refuses_while_placeholder(db_path):
    with pytest.raises(runner_mod.HeldoutNotReadyError):
        runner_mod.run(split="heldout", model_name="fake", arm="ordinary", db_path=db_path)


def test_model_connection_is_read_only_and_budgeted(db_path):
    con = db_mod.ModelConnection(db_path, budget=2)
    try:
        rows = con.query("SELECT COUNT(*) FROM support_tickets")
        assert rows[0][0] == 24
        with pytest.raises(db_mod.ReadOnlyViolation):
            con.query("DELETE FROM support_tickets")
        con.query("SELECT 1")
        with pytest.raises(db_mod.QueryBudgetExceeded):
            con.query("SELECT 1")
    finally:
        con.close()
