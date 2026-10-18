"""Frozen response sets, approval checks, and reproducible input identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from premise_eval.judgment import FIELDS, validate

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / 'validation'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def responses(directory=HERE):
    rows = read_jsonl(Path(directory) / 'responses.jsonl')
    manifest = Path(directory) / 'responses-v2-manifest.json'
    expected = json.loads(manifest.read_text())['count'] if manifest.exists() else 60
    if len(rows) != expected or len({r['response_id'] for r in rows}) != expected:
        raise ValueError('Response count and unique IDs must match the versioned manifest')
    for row in rows:
        if not all(isinstance(row.get(k), str) and row[k].strip()
                   for k in ('response_id', 'case_id', 'response_text', 'author_note')):
            raise ValueError('Every response needs ID, case ID, text, and author note')
        if not isinstance(row.get('claims', {}), dict):
            raise ValueError('Response claims must be an object')
    return rows


def require_approval(directory=HERE):
    directory = Path(directory)
    rows = responses(directory)
    approval = json.loads((directory / 'approval.json').read_text())
    if (approval.get('status') != 'approved' or not approval.get('approved_by') or
            approval.get('responses_sha256') != sha(directory / 'responses.jsonl')):
        raise ValueError('Vinay must approve the exact response set before labeling or scoring')
    return rows


def fingerprints():
    files = [ROOT / 'prompts/judge-v1.md', ROOT / 'prompts/judge-v2.md', ROOT / 'RUBRIC.md',
             HERE / 'responses-v2-manifest.json', HERE / 'agent-reference-v2.jsonl',
             HERE / 'agent-reference-v2-provenance.json', HERE / 'approval.json',
             HERE / 'archive-v1/responses.jsonl', HERE / 'archive-v1/gold.jsonl',
             ROOT / 'reports/judge-validation-v1.json',
             HERE / 'protocol.yaml', HERE / 'responses.jsonl', HERE / 'judge-config.yaml', HERE / 'thresholds.yaml',
             HERE / 'score_judge.py', HERE / 'common.py', HERE / 'adjudicate.py',
             ROOT / 'premise_eval/judge.py', ROOT / 'premise_eval/judgment.py',
             ROOT / 'premise_eval/backends.py', ROOT / 'premise_eval/verify.py',
             ROOT / 'datasets/support/schema.sql', ROOT / 'datasets/support/seed.sql',
             *sorted((ROOT / 'cases/dev').glob('*.yaml'))]
    files += sorted((HERE / 'ai-drafts').glob('*.csv'))
    files += sorted((HERE / 'agent-reference').glob('*.csv'))
    return {str(p.relative_to(ROOT)): sha(p) for p in files}


def labels_by_id(rows, expected):
    by_id = {}
    for row in rows:
        rid = row['response_id']
        if rid in by_id:
            raise ValueError('Duplicate label response ID: ' + rid)
        by_id[rid] = validate({k: row[k] for k in FIELDS})
    if set(by_id) != set(expected):
        raise ValueError('Labels must cover the approved response IDs exactly')
    return by_id
