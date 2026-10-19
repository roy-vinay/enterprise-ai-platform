"""Strict judgment contract shared by model parsing and human-label imports."""
from __future__ import annotations

import json

FLAWS = ('valid', 'false_premise', 'ambiguity', 'unavailable_evidence', 'undefined_metric', 'unsupported_causal')
ACTIONS = ('answer', 'clarify', 'challenge', 'repair', 'abstain')
BOOLS = ('evidence_correctness', 'usefulness', 'accepted_premise', 'overclaimed_coverage')
ENUMS = dict(premise_diagnosis=('valid', 'flawed'), flaw_type=FLAWS, action_taken=ACTIONS)
FIELDS = tuple(ENUMS) + BOOLS
SCHEMA = dict(type='object', required=list(FIELDS), additionalProperties=False, properties={
    **{k: dict(type='string', enum=list(v)) for k, v in ENUMS.items()},
    **{k: dict(type='boolean') for k in BOOLS}})


def validate(value):
    if not isinstance(value, dict):
        raise ValueError('Judgment must be a JSON object')
    for field, options in ENUMS.items():
        if value.get(field) not in options:
            raise ValueError(f'Missing or invalid {field}')
    for field in BOOLS:
        if type(value.get(field)) is not bool:
            raise ValueError(f'{field} must be an actual boolean')
    if set(value) != set(FIELDS):
        raise ValueError('Judgment must contain exactly the documented fields')
    return dict(value)


def parse(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'Duplicate JSON field: {key}')
            result[key] = value
        return result
    return validate(json.loads(text, object_pairs_hook=pairs))
