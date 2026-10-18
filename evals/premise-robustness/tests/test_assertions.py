"""Every dev case's ground-truth assertions must pass against the seeded DB.

A failing test here means a broken case (wrong reference facts), not a
model failure -- fix the case or the seed, never weaken the assertion.

Also enforces the matched-pairs structure: every flawed case has exactly one
valid control with a bidirectional pair_id link, and vice versa.
"""

from pathlib import Path

import pytest
import yaml

from premise_eval import db as db_mod
from premise_eval import verify as verify_mod

CASES_DIR = Path(__file__).resolve().parent.parent / "cases" / "dev"

FLAW_TYPES = {
    "false_premise", "ambiguity", "unavailable_evidence",
    "undefined_metric", "unsupported_causal", "valid",
}


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
        assert case["flaw_type"] in FLAW_TYPES, f"{name}: bad flaw_type"
        assert case["question"], f"{name}: missing question"
        assert case["assertions"], f"{name}: no assertions"
        assert case["acceptable_actions"], f"{name}: no acceptable_actions"
        for a in case["assertions"]:
            assert a["id"] and a["sql"], f"{name}: malformed assertion"
            assert ("expected" in a) != ("expected_rows" in a), (
                f"{name}/{a['id']}: exactly one of expected / expected_rows required"
            )
        if "mixed_flaw" in case:
            assert case["mixed_flaw"] is True, f"{name}: mixed_flaw must be true when present"
            assert case.get("mixed_flaw_note"), f"{name}: mixed_flaw requires mixed_flaw_note"


def test_matched_pairs():
    by_id = {case["id"]: (name, case) for name, case in _load_cases()}
    flawed = [cid for cid, (_, c) in by_id.items() if c["flaw_type"] != "valid"]
    assert len(flawed) == 40, f"expected 40 flawed cases, found {len(flawed)}"
    for cid in flawed:
        name, case = by_id[cid]
        pid = case.get("pair_id")
        assert pid, f"{name}: flawed case has no pair_id"
        assert pid in by_id, f"{name}: pair_id {pid} does not exist"
        pname, pcase = by_id[pid]
        assert pcase["flaw_type"] == "valid", f"{name}: control {pname} is not valid"
        assert pcase.get("pair_id") == cid, (
            f"{name}: pair link not bidirectional ({pname} -> {pcase.get('pair_id')})"
        )
    controls = [cid for cid, (_, c) in by_id.items()
                if c["flaw_type"] == "valid" and "pair_id" in c]
    assert len(controls) == 40, f"expected 40 controls, found {len(controls)}"
    for cid in controls:
        name, case = by_id[cid]
        ctype = case.get("control_type")
        assert ctype in {"matched", "related"}, (
            f"{name}: control_type must be 'matched' or 'related', got {ctype!r}"
        )
        if ctype == "related":
            assert case.get("control_note"), f"{name}: related control needs control_note"
    matched = [cid for cid in controls if by_id[cid][1]["control_type"] == "matched"]
    assert matched, "no matched controls: pair-based metrics would be empty"
    standalone = [cid for cid, (_, c) in by_id.items()
                  if c["flaw_type"] == "valid" and "pair_id" not in c]
    assert len(standalone) == 10, f"expected 10 standalone valid, found {len(standalone)}"
