"""Paths and loaders."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
MODEL = ROOT / "model" / "semantic_model.yaml"
CASES = ROOT / "trap_set" / "cases.yaml"
RELATIONS = ROOT / "metamorphic" / "relations.yaml"
BASELINE = ROOT / "baseline" / "baseline.json"
REPORTS = ROOT / "reports"


def load_cases(path: Path = CASES) -> list[dict]:
    return yaml.safe_load(Path(path).read_text())["cases"]


def load_relations(path: Path = RELATIONS) -> list[dict]:
    return yaml.safe_load(Path(path).read_text())["relations"]


def ensure_warehouse() -> Path:
    if not WAREHOUSE.exists():
        from .data import build
        build(WAREHOUSE)
    return WAREHOUSE
