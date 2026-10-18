"""Every dev case's ground-truth assertions must pass against the seeded DB.

A failing test here means a broken case (wrong reference facts), not a
model failure -- fix the case or the seed, never weaken the assertion.
"""

from pathlib import Path

import pytest
import yaml

from premise_eval import db as db_mod
from premise_eval import verify as verify_mod

CASES_DIR = Path(__file__).resolve().parent.parent / "cases" / "dev"


@pytest.fixture()
def con(tmp_path):
    db_path = db_mod.build_db(tmp_path / "test.db")
    connection = db_mod.verification_connection(db_path)
    yield connection
    connection.close()


def _load_cases():
    cases = []
    for path in sorted(CASES_DIR.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            cases.append((path.name, yaml.safe_load(f)))
    assert cases, "no dev cases found"
    return cases


@pytest.mark.parametrize("name,case", _load_cases(), ids=lambda v: v if isinstance(v, str) else v["id"])
def test_case_assertions_pass(con, name, case):
    result = verify_mod.verify_ground_truth(case, con)
    assert result["passed"], f"{name}: assertion failures: {result['failures']}"


def test_case_schema():
    for name, case in _load_cases():
        assert case["flaw_type"] in {
            "false_premise", "ambiguity", "unavailable_evidence",
            "undefined_metric", "unsupported_causal", "valid",
        }, f"{name}: bad flaw_type"
        assert case["question"], f"{name}: missing question"
        assert case["assertions"], f"{name}: no assertions"
        assert case["acceptable_actions"], f"{name}: no acceptable_actions"
        for a in case["assertions"]:
            assert a["id"] and a["sql"] and "expected" in a, f"{name}: malformed assertion"
