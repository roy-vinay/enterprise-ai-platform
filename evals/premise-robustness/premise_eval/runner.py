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


# The thin-slice fake model is scripted for exactly these six cases; it is a
# pipeline fixture, not a research model. Fake-model runs default to this set
# so the scripted smoke test stays pinned to the original 6 cases even as the
# dev set grows. Real-model runs (milestone 5) pass case_ids explicitly or run
# the full split.
FAKE_MODEL_CASE_IDS = [f"dev-{i:02d}" for i in range(1, 7)]


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
    if manifest.get("status") != "frozen" or not manifest.get("cases"):
        raise HeldoutNotReadyError(
            "held-out set is not frozen and nonempty: author it separately, "
            "review the case hashes, then freeze the manifest"
        )
    root = (CASES_ROOT / "heldout").resolve()
    actual = {p.name for p in root.glob("*.yaml")}
    listed = set()
    ids = set()
    for entry in manifest["cases"]:
        if not isinstance(entry, dict):
            raise HeldoutNotReadyError("manifest cases must contain path, id, and sha256")
        name = entry.get("path", "")
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".yaml"):
            raise HeldoutNotReadyError("manifest paths must be local YAML filenames")
        path = root / name
        if name in listed or not path.is_file() or path.is_symlink():
            raise HeldoutNotReadyError("manifest contains duplicate, missing, or linked cases")
        listed.add(name)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        case = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(case, dict) or not case.get("id") or case["id"] in ids:
            raise HeldoutNotReadyError("held-out case IDs must be present and unique")
        ids.add(case["id"])
        if digest != entry.get("sha256") or case["id"] != entry.get("id"):
            raise HeldoutNotReadyError(f"held-out case differs from frozen manifest: {name}")
    if listed != actual:
        raise HeldoutNotReadyError("manifest must cover every held-out YAML case exactly once")


def run(
    split: str,
    model_name: str,
    arm: str,
    db_path: Path | str,
    case_ids: list[str] | None = None,
    judge_name: str = "stub",
    judge_config: str | None = None,
) -> dict:
    if split == "heldout":
        check_heldout_ready()
    if judge_name not in {"stub", "llm"}:
        raise ValueError("judge must be stub or llm")
    backend = None
    if judge_name == "llm":
        from .backends import load_backend
        from validation.score_judge import require_validated
        backend = load_backend(judge_config)
        require_validated(backend)
    if split == "heldout" and judge_name != "llm":
        raise ValueError("Held-out runs require a validated LLM judge")
    if model_name != "fake":
        raise ValueError(f"thin slice supports only the fake model, got {model_name!r}")
    if arm not in versions.PROMPT_VERSIONS:
        raise ValueError(f"unknown arm: {arm!r}")
    if case_ids is None and model_name == "fake":
        # Pin the scripted fixture to its six cases; the dev set may be larger.
        case_ids = FAKE_MODEL_CASE_IDS

    # Local import so premise_eval stays importable without the models dir.
    sys.path.insert(0, str(PKG_ROOT / "models"))
    import fake_model  # noqa: E402

    cases = load_cases(split)
    if case_ids is not None:
        wanted = set(case_ids)
        cases = [c for c in cases if c["id"] in wanted]
        missing = wanted - {c["id"] for c in cases}
        if missing:
            raise ValueError(f"case ids not found in {split} split: {sorted(missing)}")
    con = db_mod.verification_connection(db_path)
    judgments = []
    case_results = []
    try:
        for case in cases:
            response = fake_model.respond(case["id"])
            claims = response.get("claims", {})
            claim_check = verify_mod.verify_response_claims(case, claims, con)
            if judge_name == "stub":
                judgment = judge_mod.judge_stub(case, response["behavior_tag"], claim_check["passed"])
            else:
                evidence = dict(claim_check, declared_claims=claims)
                result = judge_mod.judge(response["response_text"], case, evidence, backend=backend)
                if not result["graded"]:
                    raise ValueError("Ungraded judge output: " + result["reason"])
                judgment = result["judgment"]
            judgment["case_id"] = case["id"]
            judgments.append(judgment)
            case_results.append(
                {
                    "case_id": case["id"],
                    "flaw_type": case["flaw_type"],
                    "response_text": response["response_text"],
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
        "run_kind": "scripted_smoke_test",
        "research_results": False,
        "limitations": [
            "Scripted responses and a stub judge; metrics are pipeline checks only.",
            "Prompt arms are labels only; the fake model does not execute prompts or SQL tools.",
            "Assertion checks validate declared claims, not every claim in response text or model provenance.",
        ],
        "versions": {
            "dataset": versions.DATASET_VERSION,
            "dataset_seed": versions.DATASET_SEED_NOTE,
            "prompt_arm": arm,
            "prompt_version": versions.PROMPT_VERSIONS[arm],
            "model": model_name,
            "model_version": versions.MODEL_VERSION,
            "judge_version": judge_mod.JUDGE_VERSION if judge_name == "llm" else "stub-v1",
            "judge_model": backend.identity() if backend else "scripted-stub",
            "judge_prompt_sha256": hashlib.sha256((PKG_ROOT / "prompts/judge-v1.md").read_bytes()).hexdigest(),
            "case_set": versions.CASE_SET_VERSION,
            "heldout_manifest_sha256": manifest_sha256(),
            "harness": "premise_eval v0.1",
            "input_sha256": {
                str(p.relative_to(PKG_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted([
                    * (CASES_ROOT / split).glob("*.yaml"),
                    * (PKG_ROOT / "prompts").glob("*.md"),
                    db_mod.SCHEMA_SQL, db_mod.SEED_SQL,
                    PKG_ROOT / "models" / "fake_model.py",
                ])
            },
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
    parser.add_argument("--judge", choices=["llm", "stub"], default="stub")
    parser.add_argument("--judge-config")
    parser.add_argument("--case-ids", nargs="+")
    parser.add_argument("--out", default=None, help="report path (default: reports/report-<ts>.json)")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"database not found at {db_path}; run `make seed-db` first", file=sys.stderr)
        sys.exit(2)

    try:
        report = run(args.split, args.model, args.arm, db_path, case_ids=args.case_ids,
                     judge_name=args.judge, judge_config=args.judge_config)
    except (HeldoutNotReadyError, ValueError, OSError) as exc:
        print(f"refusing evaluation run: {exc}", file=sys.stderr)
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
