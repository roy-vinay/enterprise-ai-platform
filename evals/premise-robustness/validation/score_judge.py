"""Score the local judge against adjudicated human gold, never self-label."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import yaml

from premise_eval import db, judge, verify, versions
from premise_eval.backends import load_backend
from premise_eval.judgment import ACTIONS, FLAWS, validate
from .common import HERE, ROOT, fingerprints, labels_by_id, read_jsonl, require_approval, sha, write_json

REPORT = ROOT / 'reports/judge-validation-v1.json'


def classification(actual, predicted, categories):
    if len(actual) != len(predicted) or not actual:
        raise ValueError('Classification needs equal nonempty vectors')
    columns = list(categories) + ['ungraded']
    matrix = {a: {b: 0 for b in columns} for a in categories}
    for a, b in zip(actual, predicted):
        if a not in matrix or b not in columns:
            raise ValueError('Unknown classification category')
        matrix[a][b] += 1
    scores = {}
    for label in categories:
        tp = matrix[label][label]
        support = sum(matrix[label].values())
        n_pred = sum(matrix[a][label] for a in categories)
        precision = tp / n_pred if n_pred else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        scores[label] = dict(precision=precision, recall=recall, f1=f1, support=support)
    return dict(categories=list(categories), predicted_columns=columns, confusion_matrix=matrix,
                per_category=scores, macro_f1=sum(s['f1'] for s in scores.values()) / len(categories))


def evaluate(gold, predictions, thresholds):
    if not gold or set(gold) != set(predictions):
        raise ValueError('Predictions and gold must cover the same complete response set')
    valid = {}
    ungraded = []
    for rid, prediction in predictions.items():
        if prediction.get('graded') is False and prediction.get('reason'):
            ungraded.append(rid)
        else:
            valid[rid] = validate(prediction['judgment'])
    ids = sorted(gold)
    result = dict(n_total=len(ids), n_ungraded=len(ungraded),
                  ungraded_rate=len(ungraded) / len(ids), ungraded_ids=ungraded)
    for field, categories in [('flaw_type', FLAWS), ('action_taken', ACTIONS)]:
        result[field] = classification([gold[r][field] for r in ids],
            [valid[r][field] if r in valid else 'ungraded' for r in ids], categories)
    def misleading(j):
        return 'misleading' if j['accepted_premise'] or j['overclaimed_coverage'] else 'not_misleading'
    result['misleading'] = classification([misleading(gold[r]) for r in ids],
        [misleading(valid[r]) if r in valid else 'ungraded' for r in ids],
        ('misleading', 'not_misleading'))
    result['macro_f1'] = (result['flaw_type']['macro_f1'] + result['action_taken']['macro_f1']) / 2
    failures = []
    # Require the bar on each task as well as the combined headline.
    for field in ('flaw_type', 'action_taken'):
        if result[field]['macro_f1'] < thresholds['macro_f1']:
            failures.append(f'{field} macro F1 below threshold')
        for label, values in result[field]['per_category'].items():
            for measure in ('precision', 'recall'):
                if values[measure] < thresholds['category_' + measure]:
                    failures.append(f'{field}/{label} {measure} below threshold')
    if result['misleading']['per_category']['misleading']['recall'] < thresholds['misleading_recall']:
        failures.append('Misleading-answer recall below threshold')
    if result['ungraded_rate'] >= thresholds['ungraded_rate_below']:
        failures.append('Ungraded rate must be strictly below threshold')
    result.update(passed=not failures, failures=failures)
    return result


def inputs(directory=HERE):
    directory = Path(directory)
    if not (directory / 'gold.jsonl').exists():
        raise ValueError('validation/gold.jsonl is absent; two independent reviews and adjudication are required')
    rows = require_approval(directory)
    provenance = json.loads((directory / 'gold-provenance.json').read_text())
    if (provenance.get('rubric_sha256') != sha(ROOT / 'RUBRIC.md') or
            provenance.get('gold_sha256') != sha(directory / 'gold.jsonl') or
            provenance.get('responses_sha256') != sha(directory / 'responses.jsonl') or
            provenance.get('adjudication_sha256') != sha(directory / 'adjudication.json') or
            not provenance.get('reviewer_a') or not provenance.get('reviewer_b') or
            provenance['reviewer_a'].casefold() == provenance['reviewer_b'].casefold()):
        raise ValueError('Gold provenance does not match the approved independent reviews')
    gold = labels_by_id(read_jsonl(directory / 'gold.jsonl'), [r['response_id'] for r in rows])
    return rows, gold


def score(*, config=None, report_path=REPORT, backend=None):
    rows, gold = inputs()
    backend = backend or load_backend(config)
    identity = backend.identity()
    predictions = {}
    hashes = fingerprints()
    with tempfile.TemporaryDirectory() as tmp:
        path = db.build_db(Path(tmp) / 'validation.db')
        con = db.verification_connection(path)
        try:
            for response in rows:
                case_path = ROOT / 'cases/dev' / (response['case_id'] + '.yaml')
                case = yaml.safe_load(case_path.read_text())
                facts = verify.verify_ground_truth(case, con)
                if not facts['passed']:
                    raise ValueError('Case ground truth failed: ' + case['id'])
                claims = response.get('claims', {})
                evidence = verify.verify_response_claims(case, claims, con)
                evidence['declared_claims'] = claims
                predictions[response['response_id']] = judge.judge(response['response_text'], case, evidence, backend=backend)
        finally:
            con.close()
    if fingerprints() != hashes or backend.identity() != identity:
        raise ValueError('Inputs or model changed during validation; discard run')
    thresholds = yaml.safe_load((HERE / 'thresholds.yaml').read_text())
    result = evaluate(gold, predictions, thresholds)
    report = dict(status='passed' if result['passed'] else 'failed', judge_version=judge.JUDGE_VERSION,
        versions=dict(dataset=versions.DATASET_VERSION, case_set=versions.CASE_SET_VERSION,
                      judge_prompt='judge-v1', response_set='validation-v1'),
        model=identity, input_sha256=hashes, gold_sha256=sha(HERE / 'gold.jsonl'),
        approval_sha256=sha(HERE / 'approval.json'),
        gold_provenance_sha256=sha(HERE / 'gold-provenance.json'),
        thresholds=thresholds, results=result, predictions=predictions)
    write_json(report_path, report)
    lines = ['# Judge validation v1', '', 'Status: ' + report['status'],
        f"Responses: {result['n_total']}; ungraded: {result['n_ungraded']}",
        f"Macro F1: {result['macro_f1']:.3f}", '',
        '## Failure analysis', '', *(result['failures'] or ['All configured bars cleared.'])]
    for field in ('flaw_type', 'action_taken'):
        lines += ['', '## ' + field, '', '| Category | Precision | Recall | F1 |', '|---|---:|---:|---:|']
        for label, s in result[field]['per_category'].items():
            lines.append(f"| {label} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} |")
        lines += ['', 'Confusion matrix (rows: gold, columns: prediction):', '',
                  '```json', json.dumps(result[field]['confusion_matrix'], indent=2), '```']
    lines += ['', 'Misleading-answer precision/recall:',
              json.dumps(result['misleading']['per_category']['misleading']), '',
              'Inspect disagreements in the JSON predictions; do not lower thresholds to pass.']
    Path(report_path).with_suffix('.md').write_text('\n'.join(lines) + '\n')
    return report


def require_validated(backend, report_path=REPORT):
    """Reject absent, stale, failed, or forged-pass summaries before downstream use."""
    _, gold = inputs()
    report = json.loads(Path(report_path).read_text())
    thresholds = yaml.safe_load((HERE / 'thresholds.yaml').read_text())
    expected = dict(input_sha256=fingerprints(), gold_sha256=sha(HERE / 'gold.jsonl'),
                    approval_sha256=sha(HERE / 'approval.json'),
                    gold_provenance_sha256=sha(HERE / 'gold-provenance.json'), model=backend.identity())
    if any(report.get(k) != v for k, v in expected.items()):
        raise ValueError('Judge validation is stale for these inputs or this model')
    recomputed = evaluate(gold, report['predictions'], thresholds)
    if not recomputed['passed'] or report.get('status') != 'passed' or report.get('results') != recomputed:
        raise ValueError('Judge has not cleared the acceptance bar')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    args = parser.parse_args()
    try:
        report = score(config=args.config)
    except (OSError, ValueError, KeyError, NotImplementedError) as exc:
        parser.exit(2, f'Judge validation blocked: {exc}\n')
    print(json.dumps(report['results'], indent=2))
    if not report['results']['passed']:
        parser.exit(1, 'Acceptance bar not cleared. Read the report and failure analysis.\n')


if __name__ == '__main__':
    main()
