"""Eval runner: cases -> model -> verify -> judge (stub) -> metrics -> report.

Held-out guard (PRD 5.5): ``--split heldout`` refuses to run while the
held-out manifest is a placeholder, and dev runs structurally cannot see
``cases/heldout/`` (only ``cases/<split>/`` is ever globbed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import db as db_mod
from . import judge as judge_mod
from . import metrics as metrics_mod
from . import verify as verify_mod
from . import versions

PKG_ROOT = Path(__file__).resolve().parent.parent
CASES_ROOT = PKG_ROOT / "cases"
REPORTS_ROOT = PKG_ROOT / "reports"
MANIFEST_PATH = CASES_ROOT / "heldout" / "manifest.json"


class HeldoutNotReadyError(Exception):
    pass


def load_cases(split: str) -> list[dict]:
    if split not in {"dev", "heldout"}:
        raise ValueError(f"unknown split: {split!r}")
    case_dir = CASES_ROOT / split
    cases = []
    for path in sorted(case_dir.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            cases.append(yaml.safe_load(f))
    return cases


def manifest_sha256() -> str:
    return hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()


def check_heldout_ready() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("status") == "placeholder":
        raise HeldoutNotReadyError(
            "held-out set is a placeholder: author it in a separate pass, "
            "freeze the manifest, then run --split heldout"
        )


def run(split: str, model_name: str, arm: str, db_path: Path | str) -> dict:
    if split == "heldout":
        check_heldout_ready()
    if model_name != "fake":
        raise ValueError(f"thin slice supports only the fake model, got {model_name!r}")
    if arm not in versions.PROMPT_VERSIONS:
        raise ValueError(f"unknown arm: {arm!r}")

    # Local import so premise_eval stays importable without the models dir.
    sys.path.insert(0, str(PKG_ROOT / "models"))
    import fake_model  # noqa: E402

    cases = load_cases(split)
    con = db_mod.verification_connection(db_path)
    judgments = []
    case_results = []
    try:
        for case in cases:
            response = fake_model.respond(case["id"])
            claims = response.get("claims", {})
            claim_check = verify_mod.verify_response_claims(case, claims, con)
            judgment = judge_mod.judge_stub(
                case, response["behavior_tag"], claim_check["passed"]
            )
            judgments.append(judgment)
            case_results.append(
                {
                    "case_id": case["id"],
                    "flaw_type": case["flaw_type"],
                    "behavior_tag": response["behavior_tag"],
                    "claims": claims,
                    "claim_verification": claim_check,
                    "judgment": judgment,
                }
            )
    finally:
        con.close()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "versions": {
            "dataset": versions.DATASET_VERSION,
            "dataset_seed": versions.DATASET_SEED_NOTE,
            "prompt_arm": arm,
            "prompt_version": versions.PROMPT_VERSIONS[arm],
            "model": model_name,
            "model_version": versions.MODEL_VERSION,
            "case_set": versions.CASE_SET_VERSION,
            "heldout_manifest_sha256": manifest_sha256(),
            "harness": f"premise_eval {db_mod.__package__} v0.1",
        },
        "split": split,
        "metrics": metrics_mod.compute_metrics(judgments),
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the premise-robustness eval.")
    parser.add_argument("--split", default="dev", choices=["dev", "heldout"])
    parser.add_argument("--model", default="fake")
    parser.add_argument("--arm", default="ordinary", choices=["ordinary", "critique", "evidence"])
    parser.add_argument("--db", default=str(db_mod.DEFAULT_DB_PATH))
    parser.add_argument("--out", default=None, help="report path (default: reports/report-<ts>.json)")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"database not found at {db_path}; run `make seed-db` first", file=sys.stderr)
        sys.exit(2)

    try:
        report = run(args.split, args.model, args.arm, db_path)
    except HeldoutNotReadyError as exc:
        print(f"refusing held-out run: {exc}", file=sys.stderr)
        sys.exit(3)

    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else REPORTS_ROOT / (
        f"report-{args.split}-{args.model}-{args.arm}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
