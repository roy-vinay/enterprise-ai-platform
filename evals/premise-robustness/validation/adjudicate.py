"""Import independent reviewer CSVs and explicitly resolve disagreements."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from premise_eval.judgment import BOOLS, FIELDS
from .common import HERE, labels_by_id, require_approval, sha, write_json

COLUMNS = ('response_id',) + FIELDS + ('notes',)


def read_sheet(path, expected):
    with Path(path).open(newline='') as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != list(COLUMNS):
            raise ValueError('CSV columns must match label-template.csv exactly')
        rows = list(reader)
    for row in rows:
        for field in BOOLS:
            text = row.get(field)
            if text not in ('true', 'false'):
                raise ValueError(f'{row.get("response_id")}: {field} must be true or false')
            row[field] = text == 'true'
    return labels_by_id(rows, expected)


def compare(first, second):
    if set(first) != set(second) or not first:
        raise ValueError('Both reviewers must label the same nonempty response set')
    agreements = sorted(k for k in first if first[k] == second[k])
    disagreements = {k: dict(reviewer_a=first[k], reviewer_b=second[k],
        differing_fields=[f for f in FIELDS if first[k][f] != second[k][f]])
        for k in sorted(first) if first[k] != second[k]}
    return dict(n=len(first), exact_agreement=len(agreements) / len(first),
        field_agreement={f: sum(first[k][f] == second[k][f] for k in first) / len(first)
                         for f in FIELDS}, agreements=agreements, disagreements=disagreements)


def adjudicate(a, b, reviewer_a, reviewer_b, *, resolutions=None, resolved_by=None, directory=HERE):
    directory = Path(directory)
    # Re-running comparison must not leave old gold usable.
    (directory / 'gold.jsonl').unlink(missing_ok=True)
    (directory / 'gold-provenance.json').unlink(missing_ok=True)
    ids = [r['response_id'] for r in require_approval(directory)]
    if not reviewer_a.strip() or not reviewer_b.strip() or reviewer_a.strip().casefold() == reviewer_b.strip().casefold():
        raise ValueError('Two distinct named independent reviewers are required')
    if 'vinay' not in {reviewer_a.strip().casefold(), reviewer_b.strip().casefold()}:
        raise ValueError('One independent reviewer must be Vinay')
    first, second = read_sheet(a, ids), read_sheet(b, ids)
    report = compare(first, second)
    report['reviewers'] = [reviewer_a, reviewer_b]
    write_json(directory / 'adjudication.json', report)
    pending = set(report['disagreements'])
    if pending and resolutions is None:
        return report
    if pending and (not resolved_by or resolved_by.strip().casefold() != 'vinay'):
        raise ValueError('Vinay must explicitly adjudicate disagreements')
    resolved = read_sheet(resolutions, pending) if resolutions else {}
    if set(resolved) != pending:
        raise ValueError('Resolution sheet must cover exactly the disagreements')
    gold = {k: resolved[k] if k in pending else first[k] for k in ids}
    path = directory / 'gold.jsonl'
    path.write_text(''.join(json.dumps(dict(response_id=k, **gold[k]), sort_keys=True) + '\n' for k in ids))
    write_json(directory / 'gold-provenance.json', dict(
        responses_sha256=sha(directory / 'responses.jsonl'), gold_sha256=sha(path),
        rubric_sha256=sha(HERE.parent / 'RUBRIC.md'),
        reviewer_a=reviewer_a, reviewer_b=reviewer_b,
        reviewer_a_sha256=sha(a), reviewer_b_sha256=sha(b),
        resolutions_sha256=sha(resolutions) if resolutions else None,
        resolved_by=resolved_by, adjudication_sha256=sha(directory / 'adjudication.json')))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reviewer_a_sheet')
    parser.add_argument('reviewer_b_sheet')
    parser.add_argument('--reviewer-a', required=True)
    parser.add_argument('--reviewer-b', required=True)
    parser.add_argument('--resolutions')
    parser.add_argument('--resolved-by')
    args = parser.parse_args()
    try:
        report = adjudicate(args.reviewer_a_sheet, args.reviewer_b_sheet,
            args.reviewer_a, args.reviewer_b, resolutions=args.resolutions, resolved_by=args.resolved_by)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'Adjudication blocked: {exc}\n')
    print(json.dumps(report, indent=2))
    if report['disagreements'] and not args.resolutions:
        parser.exit(2, 'Disagreements remain. Gold was not created.\n')


if __name__ == '__main__':
    main()
