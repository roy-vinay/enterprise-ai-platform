"""Score a local judge against explicitly typed adjudicated reference labels."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import yaml

from premise_eval import db, judge, verify, versions
from premise_eval.backends import load_backend
from premise_eval.judgment import ACTIONS, FLAWS, validate
from .common import HERE, ROOT, fingerprints, labels_by_id, read_jsonl, require_approval, responses, sha, write_json

REPORT = ROOT / 'reports/judge-validation-v2.json'


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
        raise ValueError('validation/gold.jsonl is absent; approved reference labels and adjudication are required')
    rows = require_approval(directory)
    provenance = json.loads((directory / 'gold-provenance.json').read_text())
    protocol = yaml.safe_load((directory / 'protocol.yaml').read_text())
    if provenance.get('reference_protocol') != protocol['mode']:
        raise ValueError('Reference protocol changed; re-adjudicate before scoring')
    if (provenance.get('rubric_sha256') != sha(ROOT / 'RUBRIC.md') or
            provenance.get('gold_sha256') != sha(directory / 'gold.jsonl') or
            provenance.get('responses_sha256') != sha(directory / 'responses.jsonl') or
            provenance.get('adjudication_sha256') != sha(directory / 'adjudication.json') or
            not provenance.get('reviewer_a') or not provenance.get('reviewer_b') or
            provenance['reviewer_a'].casefold() == provenance['reviewer_b'].casefold()):
        raise ValueError('Gold provenance does not match the approved independent reviews')
    gold = labels_by_id(read_jsonl(directory / 'gold.jsonl'), [r['response_id'] for r in rows])
    return rows, gold


def dry_run_inputs(directory=HERE):
    """Load explicitly agent-authored references without passing human approval."""
    directory = Path(directory)
    rows = responses(directory)
    provenance = json.loads((directory / 'agent-reference-v2-provenance.json').read_text())
    if (provenance.get('reference_type') != 'agent_generated_reference' or
            provenance.get('human_validated') is not False or
            provenance.get('dry_run_only') is not True or
            provenance.get('responses_sha256') != sha(directory / 'responses.jsonl') or
            provenance.get('references_sha256') != sha(directory / 'agent-reference-v2.jsonl') or
            provenance.get('original_references_sha256') != sha(directory / 'archive-v1/gold.jsonl')):
        raise ValueError('Agent dry-run provenance is absent, stale, or incorrectly typed')
    manifest = json.loads((directory / 'responses-v2-manifest.json').read_text())
    original = (directory / 'archive-v1/responses.jsonl').read_bytes()
    if (sha(directory / 'archive-v1/responses.jsonl') != manifest['original_sha256'] or
            not (directory / 'responses.jsonl').read_bytes().startswith(original)):
        raise ValueError('Original 60 responses changed')
    reference_rows = read_jsonl(directory / 'agent-reference-v2.jsonl')
    original_refs = read_jsonl(directory / 'archive-v1/gold.jsonl')
    if reference_rows[:len(original_refs)] != original_refs:
        raise ValueError('Original references changed')
    gold = labels_by_id(reference_rows, [r['response_id'] for r in rows])
    missing = set(ACTIONS) - {r['action_taken'] for r in gold.values()}
    if missing:
        raise ValueError('Reference action coverage missing: ' + ', '.join(sorted(missing)))
    return rows, gold


def comparison_table(baseline, current, matched):
    """Historical v1, same-60 v2, and expanded v2; denominators stay explicit."""
    lines = ['## V1 versus V2 comparison', '',
        'V1 is the preserved historical 60-response run. V2 same-60 uses unchanged',
        'references and the same response IDs. Expanded V2 includes 8 repair additions.',
        'There is no V1 measurement of the new repair rows. This is not held-out validation.', '',
        '| Task/category | V1 P (n=60) | V1 R | V2 P (same 60) | V2 R | V2 P (n=68) | V2 R |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for task in ('action_taken', 'misleading'):
        for category, values in current[task]['per_category'].items():
            old = baseline[task]['per_category'][category]
            same = matched[task]['per_category'][category]
            def fmt(row, key):
                return f"{row[key]:.3f}" if row['support'] else 'N/A (no support)'
            lines.append('| ' + task + '/' + category + ' | ' + ' | '.join(
                fmt(row, key) for row in (old, same, values) for key in ('precision', 'recall')) + ' |')
    return '\n'.join(lines)


def score(*, config=None, report_path=None, backend=None, dry_run=False):
    version = judge.prompt_version(config)
    report_path = Path(report_path or ROOT / "reports" / ("judge-validation-" + version.removeprefix("judge-") + ".json"))
    if report_path.resolve() == (ROOT / "reports/judge-validation-v1.json").resolve():
        raise ValueError("The historical v1 report is immutable; select a new output path")
    rows, gold = dry_run_inputs() if dry_run else inputs()
    backend = backend or load_backend(config)
    identity = backend.identity()
    predictions = {}
    hashes = fingerprints()
    if config:
        hashes["selected_config"] = sha(config)
    with tempfile.TemporaryDirectory() as tmp:
        path = db.build_db(Path(tmp) / 'validation.db')
        con = db.verification_connection(path)
        try:
            for index, response in enumerate(rows, 1):
                case_path = ROOT / 'cases/dev' / (response['case_id'] + '.yaml')
                case = yaml.safe_load(case_path.read_text())
                facts = verify.verify_ground_truth(case, con)
                if not facts['passed']:
                    raise ValueError('Case ground truth failed: ' + case['id'])
                claims = response.get('claims', {})
                evidence = verify.verify_response_claims(case, claims, con)
                evidence['declared_claims'] = claims
                predictions[response['response_id']] = judge.judge(response['response_text'], case, evidence, backend=backend, version=version)
                print(f"Judged {index}/{len(rows)}: {response['response_id']}", flush=True)
        finally:
            con.close()
    final_hashes = fingerprints()
    if config:
        final_hashes['selected_config'] = sha(config)
    if final_hashes != hashes or backend.identity() != identity:
        raise ValueError('Inputs or model changed during validation; discard run')
    thresholds = yaml.safe_load((HERE / 'thresholds.yaml').read_text())
    result = evaluate(gold, predictions, thresholds)
    protocol = yaml.safe_load((HERE / 'protocol.yaml').read_text())
    report = dict(dry_run=dry_run, eligible_for_downstream=not dry_run,
        reference_type='agent_generated_reference' if dry_run else protocol.get('reference_type'),
        reference_protocol=protocol, human_validated=False if dry_run else protocol['mode'] == 'human',
        interpretation=protocol.get('meaning', 'Agreement with adjudicated references'),
        status='passed' if result['passed'] else 'failed', judge_version=version,
        versions=dict(dataset=versions.DATASET_VERSION, case_set=versions.CASE_SET_VERSION,
                      judge_prompt=version, response_set='validation-v2'),
        model=identity, input_sha256=hashes, gold_sha256=sha(HERE / 'gold.jsonl'),
        approval_sha256=sha(HERE / 'approval.json'),
        gold_provenance_sha256=sha(HERE / 'gold-provenance.json'),
        thresholds=thresholds, results=result, predictions=predictions)
    if dry_run:
        provenance_path = HERE / 'agent-reference-v2-provenance.json'
        report['reference_provenance'] = json.loads(provenance_path.read_text())
        report['gold_sha256'] = sha(HERE / 'agent-reference-v2.jsonl')
        report['gold_provenance_sha256'] = sha(provenance_path)
        report['interpretation'] = 'Development dry run against agent-generated references, not human-validated accuracy.'
        baseline = json.loads((ROOT / 'reports/judge-validation-v1.json').read_text())
        matched_ids = set(baseline['predictions'])
        if not matched_ids <= set(gold):
            raise ValueError('V1 comparison IDs are absent from revised set')
        matched = evaluate({rid: gold[rid] for rid in matched_ids},
                           {rid: predictions[rid] for rid in matched_ids}, thresholds)
        report['comparison'] = dict(baseline_sha256=sha(ROOT / 'reports/judge-validation-v1.json'),
            v1_n=baseline['results']['n_total'], v2_n=len(gold),
            v1_results=baseline['results'], v2_same_60_results=matched,
            table=comparison_table(baseline['results'], result, matched))
    write_json(report_path, report)
    lines = ['# Judge agreement evaluation ' + version, '', report['interpretation'], '',
        'Human-validated: ' + str(report['human_validated']).lower(), '',
        'Status: ' + report['status'],
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
    if dry_run:
        lines += ['', report['comparison']['table'], '',
                  'Dry run only: pending human approval remains unchanged. No downstream authorization.']
    Path(report_path).with_suffix('.md').write_text('\n'.join(lines) + '\n')
    return report


def require_validated(backend, report_path=REPORT, *, config=None):
    """Reject absent, stale, failed, or forged-pass summaries before downstream use."""
    report = json.loads(Path(report_path).read_text())
    if report.get('dry_run') is True:
        raise ValueError('Agent dry-run reports cannot authorize downstream use')
    _, gold = inputs()
    thresholds = yaml.safe_load((HERE / 'thresholds.yaml').read_text())
    expected_hashes = fingerprints()
    if config:
        expected_hashes['selected_config'] = sha(config)
    expected = dict(input_sha256=expected_hashes, judge_version=judge.prompt_version(config), gold_sha256=sha(HERE / 'gold.jsonl'),
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
    parser.add_argument('--dry-run', action='store_true', help='Agent references only; cannot satisfy the human gate')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        report = score(config=args.config, dry_run=args.dry_run, report_path=args.report)
    except (OSError, ValueError, KeyError, NotImplementedError) as exc:
        parser.exit(2, f'Judge validation blocked: {exc}\n')
    print(json.dumps(report['results'], indent=2))
    if not report['results']['passed']:
        parser.exit(1, 'Acceptance bar not cleared. Read the report and failure analysis.\n')


if __name__ == '__main__':
    main()
