"""Freeze common inputs and run independently recorded local/frontier dry-run arms."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common import ROOT, HERE, fingerprints, sha, write_json
from .score_judge import score, dry_run_inputs, evaluate
from premise_eval.backends import load_backend
from premise_eval.judge import prompt_version

EXPERIMENT = HERE / 'experiments/stronger-judge-v1'
ARMS = ('local', 'frontier')


def freeze(directory=EXPERIMENT):
    directory = Path(directory)
    manifest = directory / 'manifest.json'
    if manifest.exists():
        raise ValueError('Experiment is frozen; create a new experiment directory instead of replacing it')
    rows, _ = dry_run_inputs()
    configs = {arm: sha(directory / (arm + '.yaml')) for arm in ARMS}
    if any(prompt_version(directory / (arm + '.yaml')) != 'judge-v2' for arm in ARMS):
        raise ValueError('Both arms must select the reviewed judge-v2 prompt')
    record = dict(experiment='stronger-judge-v1', human_validated=False, dry_run=True,
        n_responses=len(rows), common_input_sha256=fingerprints(), config_sha256=configs,
        response_ids=[r['response_id'] for r in rows],
        limitations=['Author-generated repair references, not independent human gold.',
                    'One repair example is in the prompt; that item is not an unseen test.',
                    'Same prompt, rubric, rows and thresholds; provider sampling differs.',
                    'No automatic reference edits or threshold changes.'])
    write_json(manifest, record)
    return record


def verify_manifest(directory=EXPERIMENT):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['common_input_sha256'] != fingerprints():
        raise ValueError('Frozen common inputs changed; create a new experiment')
    if any(manifest['config_sha256'][arm] != sha(directory / (arm + '.yaml')) for arm in ARMS):
        raise ValueError('Frozen arm configuration changed')
    rows, _ = dry_run_inputs()
    if manifest['response_ids'] != [r['response_id'] for r in rows]:
        raise ValueError('Frozen response membership or ordering changed')
    return manifest


def report_path(arm, directory=EXPERIMENT):
    if arm not in ARMS:
        raise ValueError('Unknown experiment arm')
    return ROOT / 'reports' / (Path(directory).name + '-' + arm + '.json')


def validate_arm(report, manifest, config, arm):
    expected_hashes = dict(manifest['common_input_sha256'], selected_config=sha(config))
    if (report.get('input_sha256') != expected_hashes or report.get('dry_run') is not True or
            report.get('human_validated') is not False or
            set(report.get('predictions', {})) != set(manifest['response_ids'])):
        raise ValueError('Saved arm is stale, incomplete or not an agent dry run')
    expected_backend = 'ollama' if arm == 'local' else 'anthropic'
    import yaml
    settings = yaml.safe_load(Path(config).read_text())
    if report.get('model', {}).get('backend') != expected_backend or report['model'].get('model') != settings['model']:
        raise ValueError('Saved arm model differs from the frozen configuration')
    _, refs = dry_run_inputs()
    thresholds = yaml.safe_load((HERE / 'thresholds.yaml').read_text())
    if report['results'] != evaluate(refs, report['predictions'], thresholds):
        raise ValueError('Saved arm scores do not match saved predictions')


def summarize(directory=EXPERIMENT):
    directory = Path(directory)
    manifest = verify_manifest(directory)
    summary = dict(experiment=manifest['experiment'], human_validated=False, dry_run=True,
        eligible_for_downstream=False, manifest_sha256=sha(directory / 'manifest.json'), arms={})
    for arm in ARMS:
        path = report_path(arm, directory)
        if path.exists():
            report = json.loads(path.read_text())
            validate_arm(report, manifest, directory / (arm + '.yaml'), arm)
            summary['arms'][arm] = dict(status=report['status'], report=path.name,
                report_sha256=sha(path), results=report['results'], model=report['model'],
                usage_cost=report.get('usage_cost'))
        else:
            blocked = directory / (arm + '-blocked.json')
            summary['arms'][arm] = json.loads(blocked.read_text()) if blocked.exists() else dict(status='not_run')
    complete = all('results' in summary['arms'][a] for a in ARMS)
    summary['status'] = 'complete' if complete else 'incomplete'
    path = ROOT / 'reports' / (directory.name + '-comparison.json')
    write_json(path, summary)
    lines = ['# Controlled stronger-judge comparison', '',
        'Status: ' + summary['status'], 'Human-validated: false. Agent-reference development dry run only.', '',
        '| Measure | Local 8B | Frontier |', '|---|---:|---:|']
    def value(arm, task, key):
        record = summary['arms'][arm]
        if 'results' not in record:
            return record['status']
        values = record['results']
        if key == 'misleading_recall': return f"{values['misleading']['per_category']['misleading']['recall']:.3f}"
        if key == 'repair_recall': return f"{values['action_taken']['per_category']['repair']['recall']:.3f}"
        return f"{values[task][key]:.3f}" if task else str(values[key])
    for label, task, key in [('Action macro F1','action_taken','macro_f1'),
        ('Flaw macro F1','flaw_type','macro_f1'),('Misleading recall',None,'misleading_recall'),
        ('Repair recall',None,'repair_recall'),('Ungraded',None,'n_ungraded')]:
        lines.append('| ' + label + ' | ' + ' | '.join(value(a,task,key) for a in ARMS) + ' |')
    if complete:
        lines += ['', '## Per-category comparison', '',
            '| Task/category | Local P | Local R | Frontier P | Frontier R |', '|---|---:|---:|---:|---:|']
        for task in ('action_taken','misleading'):
            for category in summary['arms']['local']['results'][task]['per_category']:
                nums=[summary['arms'][a]['results'][task]['per_category'][category][k] for a in ARMS for k in ('precision','recall')]
                lines.append('| '+task+'/'+category+' | '+' | '.join(f'{n:.3f}' for n in nums)+' |')
    else:
        lines += ['', 'No model-improvement claim is possible until both arms are measured.']
    lines += ['', '## Arm status and cost', '']
    for arm, record in summary['arms'].items():
        lines.append(arm + ': ' + record['status'])
        if 'reason' in record: lines.append(record['reason'])
        if record.get('usage_cost'): lines.append(json.dumps(record['usage_cost'], sort_keys=True))
    lines += ['', '## Interpretation', '', *manifest['limitations'], '',
        'A numerical pass only triggers the separate human-validation step. No merge authorization.']
    path.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    return summary


def run_arm(arm, *, directory=EXPERIMENT, allow_paid=False):
    directory = Path(directory)
    manifest = verify_manifest(directory)
    path = report_path(arm, directory)
    if path.exists():
        report = json.loads(path.read_text())
        validate_arm(report, manifest, directory / (arm + '.yaml'), arm)
        return summarize(directory)
    backend = None
    try:
        config = directory / (arm + '.yaml')
        backend = load_backend(config, allow_paid=allow_paid)
        score(config=config, backend=backend, dry_run=True, report_path=path, allow_paid=allow_paid)
    except (RuntimeError, ValueError, OSError) as exc:
        status = dict(status='blocked', reason=str(exc), human_validated=False,
                      manifest_sha256=sha(directory/'manifest.json'))
        if backend is not None and hasattr(backend, 'statistics'):
            status['usage_cost'] = backend.statistics()
        write_json(directory/(arm+'-blocked.json'), status)
    # A budget/transport outage cannot become a passing partial report.
    return summarize(directory)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, default=EXPERIMENT)
    p.add_argument('--freeze', action='store_true')
    p.add_argument('--arm', choices=ARMS)
    p.add_argument('--allow-paid', action='store_true')
    args = p.parse_args()
    if args.freeze: freeze(args.directory)
    result = run_arm(args.arm,directory=args.directory,allow_paid=args.allow_paid) if args.arm else summarize(args.directory)
    print(json.dumps({a:r['status'] for a,r in result['arms'].items()}))


if __name__ == '__main__': main()
