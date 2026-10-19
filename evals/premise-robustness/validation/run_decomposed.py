"""Frozen, local-only factoring experiment with checkpoints and honest arm reports."""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

import yaml
from premise_eval import db, judge, verify
from premise_eval.decomposed import LocalSampler, judge_decomposed, vote_statistics
from premise_eval.judgment import FIELDS
from .common import ROOT, HERE, fingerprints, sha
from .score_judge import dry_run_inputs, evaluate

DIRECTORY=HERE/'experiments/decomposed-judge-v1'
ARMS=('single-call','decomposed','decomposed-vote')
CHECKPOINTS=ROOT.parents[1]/'outputs/decomposed-judge-v1-checkpoints'


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,separators=(',',':'),sort_keys=True)+'\n')
    temp.replace(path)


def input_hashes(directory=DIRECTORY):
    files=[ROOT/'premise_eval/decomposed.py',HERE/'run_decomposed.py',
           *sorted((ROOT/'prompts/judge-decomposed').glob('*.md')),
           *[Path(directory)/(arm+'.yaml') for arm in ARMS]]
    return dict(fingerprints(),**{str(f.relative_to(ROOT)):sha(f) for f in files})


def freeze(directory=DIRECTORY):
    directory=Path(directory)
    if (directory/'manifest.json').exists():raise ValueError('Experiment already frozen; do not replace it')
    rows,_=dry_run_inputs();backend=LocalSampler();model=backend.identity()
    record=dict(experiment='decomposed-judge-v1',input_sha256=input_hashes(directory),model=model,
        response_ids=[r['response_id'] for r in rows],n_responses=len(rows),
        reference_type='agent_generated_reference',human_validated=False,local_only=True,api_spend_usd=0,
        rationale='Diagnostic human pilot supports sampled factual/coverage references; test factoring without editing labels.',
        limitations=['Pilot is diagnostic, not independent full-schema human gold.',
            'Single-call retains supplied case flaw_type; premise sub-call infers it from question and verified facts.',
            'All sub-prompts use the same full frozen rubric, but their inputs are focused by design.',
            'Evidence sub-call receives the same verified case facts inside evidence_report.',
            'Usefulness sub-call sees only question and response; it cannot independently verify factual truth.',
            'A reviewed repair exemplar occurs in the rubric and prompts; it is not an unseen generalization test.',
            'Identical seeds across response-stage repeats reduce uncontrolled variation; samples within each voting call have distinct seeds.',
            'No reference, rubric or threshold edits. No paid calls. No merge until human-gold validation clears.'])
    write(directory/'manifest.json',record);return record


def frozen(directory=DIRECTORY):
    directory=Path(directory);record=json.loads((directory/'manifest.json').read_text())
    if record['input_sha256']!=input_hashes(directory):raise ValueError('Frozen input hashes changed')
    rows,_=dry_run_inputs()
    if [r['response_id'] for r in rows]!=record['response_ids']:raise ValueError('Frozen response membership/order changed')
    return record


def path_for(arm,directory=DIRECTORY):
    if arm not in ARMS:raise ValueError('Unknown local arm')
    return ROOT/'reports'/(Path(directory).name+'-'+arm+'.json')


def verify_report(report,manifest,arm,directory=DIRECTORY):
    if (report.get('input_sha256')!=manifest['input_sha256'] or
        report.get('model')!=manifest['model'] or report.get('arm')!=arm or
        report.get('human_validated') is not False or report.get('dry_run') is not True or
        set(report.get('predictions',{}))!=set(manifest['response_ids'])):
        raise ValueError('Saved arm is incomplete, stale or from another model')
    _,refs=dry_run_inputs();thresholds=yaml.safe_load((HERE/'thresholds.yaml').read_text())
    if report['results']!=evaluate(refs,report['predictions'],thresholds):raise ValueError('Saved metrics disagree with predictions')


def render_arm(report,path):
    r=report['results']
    lines=['# '+report['experiment']+': '+report['arm'],'',
        'Status: '+report['status'],'Human-validated: false. Agent-generated reference dry run only.',
        'Local API spend: USD 0. Hardware/electricity costs not measured.',
        f"Wall-clock runtime: {report['runtime_seconds']:.2f} seconds; model requests: {report['model_call_count']}.",
        'Runtime sums active process segments; interrupted downtime is excluded.', '',
        f"Responses: {r['n_total']}; ungraded: {r['n_ungraded']}; macro F1: {r['macro_f1']:.3f}",
        '', '## Acceptance failures','',*(r['failures'] or ['All unchanged agent-reference bars cleared; human validation still required.'])]
    for task in ('flaw_type','action_taken','misleading'):
        lines+=['','## '+task,'','| Category | Precision | Recall | F1 | Support |','|---|---:|---:|---:|---:|']
        for label,s in r[task]['per_category'].items():
            lines.append(f"| {label} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} | {s['support']} |")
        lines+=['','Confusion matrix, reference rows and prediction columns:','','```json',json.dumps(r[task]['confusion_matrix'],indent=2),'```']
    if report['vote_statistics']:
        lines+=['','## Per-field vote disagreement','','Split rate uses complete three-sample sets as denominator; failed sets remain separately visible.',
                '','| Field | Complete sets | Failed sets | Splits | Split rate | Ties |','|---|---:|---:|---:|---:|---:|']
        for field,s in report['vote_statistics'].items():
            rate='N/A' if s['split_rate'] is None else f"{s['split_rate']:.3f}"
            lines.append(f"| {field} | {s['complete_vote_sets']} | {s['incomplete_vote_sets']} | {s['splits']} | {rate} | {s['ties']} |")
    lines+=['','Per-response JSON includes field-level prompt versions/hashes, sample values, settings, attempts, input hashes and vote decisions.','',*report['limitations']]
    path.with_suffix('.md').write_text('\n'.join(lines)+'\n')


def run_arm(arm,directory=DIRECTORY):
    directory=Path(directory);manifest=frozen(directory);path=path_for(arm,directory)
    if path.exists():
        report=json.loads(path.read_text());verify_report(report,manifest,arm,directory);return report
    config=yaml.safe_load((directory/(arm+'.yaml')).read_text())
    expected={'single-call':dict(mode='single-call',temperature=0,seeds=[17]),
              'decomposed':dict(mode='decomposed',temperature=0,seeds=[17]),
              'decomposed-vote':dict(mode='decomposed-vote',temperature=.7,seeds=[101,202,303])}[arm]
    if config!=expected:raise ValueError('Arm configuration differs from the implemented frozen settings')
    CHECKPOINTS.mkdir(parents=True,exist_ok=True)
    cp=CHECKPOINTS/(directory.name+'-'+arm+'.json')
    ledger=CHECKPOINTS/(directory.name+'-'+arm+'-calls.jsonl')
    backend=LocalSampler(ledger=ledger)
    if backend.identity()!=manifest['model']:raise RuntimeError('Installed local model differs from frozen model')
    state=json.loads(cp.read_text()) if cp.exists() else dict(predictions={},runtime_seconds=0,manifest_sha256=sha(directory/'manifest.json'))
    if state['manifest_sha256']!=sha(directory/'manifest.json'):raise ValueError('Checkpoint manifest changed')
    rows,refs=dry_run_inputs();predictions=state['predictions']
    if not set(predictions)<=set(manifest['response_ids']):raise ValueError('Checkpoint contains unknown IDs')
    started=time.perf_counter();prior=state['runtime_seconds']
    with tempfile.TemporaryDirectory() as temp:
        con=db.verification_connection(db.build_db(Path(temp)/'fixture.db'))
        try:
            for row in rows:
                rid=row['response_id']
                if rid in predictions:continue
                case=yaml.safe_load((ROOT/'cases/dev'/(row['case_id']+'.yaml')).read_text())
                if not verify.verify_ground_truth(case,con)['passed']:raise ValueError('Case assertions failed')
                evidence=verify.verify_response_claims(case,row.get('claims',{}),con)
                evidence['declared_claims']=row.get('claims',{})
                if arm=='single-call':
                    before=len(backend.events)
                    result=judge.judge(row['response_text'],case,evidence,backend=backend,version='judge-v2')
                    starts=[e for e in backend.events[before:] if e['event']=='start']
                    result['field_provenance']={field:dict(prompt_version='judge-v2',
                        prompt_sha256=sha(ROOT/'prompts/judge-v2.md'),shared_full_judgment_call=True,
                        calls=starts) for field in FIELDS}
                else:
                    result=judge_decomposed(row['response_text'],case,evidence,backend,voting=arm=='decomposed-vote')
                predictions[rid]=result
                state.update(predictions=predictions,runtime_seconds=prior+time.perf_counter()-started,model_call_count=backend.model_calls)
                write(cp,state)
                print(f'{arm}: {len(predictions)}/{len(rows)}; model calls {backend.model_calls}',flush=True)
        finally:con.close()
    if frozen(directory)!=manifest or backend.identity()!=manifest['model']:raise RuntimeError('Frozen inputs or model changed during run')
    thresholds=yaml.safe_load((HERE/'thresholds.yaml').read_text());metrics=evaluate(refs,predictions,thresholds)
    report=dict(experiment=manifest['experiment'],arm=arm,status='passed' if metrics['passed'] else 'failed',
        human_validated=False,dry_run=True,eligible_for_downstream=False,reference_type='agent_generated_reference',
        input_sha256=manifest['input_sha256'],manifest_sha256=sha(directory/'manifest.json'),model=manifest['model'],
        runtime_seconds=prior+time.perf_counter()-started,model_call_count=backend.model_calls,
        api_spend_usd=0,local_only=True,sampling=config,thresholds=thresholds,results=metrics,
        vote_statistics=vote_statistics(predictions) if arm=='decomposed-vote' else {},
        predictions=predictions,limitations=manifest['limitations'],
        tie_policy='Boolean safety ties: acceptance/coverage true, evidence/usefulness false. Categorical ties ungraded. Any failed required sample makes its field ungraded.')
    write(path,report);render_arm(report,path);return report


def compare(directory=DIRECTORY):
    directory=Path(directory);manifest=frozen(directory);reports={}
    for arm in ARMS:
        path=path_for(arm,directory)
        if path.exists():
            report=json.loads(path.read_text());verify_report(report,manifest,arm,directory)
            reports[arm]=report
    passed=[a for a,r in reports.items() if r['status']=='passed']
    complete=len(reports)==len(ARMS)
    decision=('Agent-reference bar cleared by '+', '.join(passed)+'. Stop; hand off to independent human validation, no merge.') if passed else ('All arms failed. Report decomposition/voting deltas honestly; no larger model or paid follow-up in this experiment.' if complete else 'Experiment incomplete; no final capacity or factoring conclusion.')
    record=dict(experiment=manifest['experiment'],status='human_validation_pending' if passed else 'complete' if complete else 'incomplete',
        human_validated=False,api_spend_usd=0,eligible_for_downstream=False,decision=decision,
        arms={arm:dict(status=r['status'],results=r['results'],runtime_seconds=r['runtime_seconds'],
                      model_call_count=r['model_call_count'],report_sha256=sha(path_for(arm,directory)),
                      vote_statistics=r['vote_statistics']) for arm,r in reports.items()},limitations=manifest['limitations'])
    lines=['# Local decomposed-judge experiment comparison','',decision,'','API spend: USD 0 for every arm. Human-validated: false.',
        '','| Arm | Status | Action F1 | Misleading P | Misleading R | Repair R | Ungraded | Calls | Wall seconds |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        if arm not in reports:
            lines.append('| '+arm+' | not run | | | | | | | |');continue
        r=reports[arm];m=r['results'];s=m['misleading']['per_category']['misleading']
        lines.append(f"| {arm} | {r['status']} | {m['action_taken']['macro_f1']:.3f} | {s['precision']:.3f} | {s['recall']:.3f} | {m['action_taken']['per_category']['repair']['recall']:.3f} | {m['n_ungraded']} | {r['model_call_count']} | {r['runtime_seconds']:.2f} |")
    for first,second in [('single-call','decomposed'),('decomposed','decomposed-vote')]:
        if first in reports and second in reports:
            a=reports[first]['results'];b=reports[second]['results']
            delta=dict(action_macro_f1=b['action_taken']['macro_f1']-a['action_taken']['macro_f1'],
                misleading_recall=b['misleading']['per_category']['misleading']['recall']-a['misleading']['per_category']['misleading']['recall'])
            record.setdefault('deltas',{})[second+' minus '+first]=delta
            lines+=['',second+' minus '+first+': '+json.dumps(delta)]
    lines+=['','See each arm report for per-category precision/recall, all confusion matrices, per-field provenance and voting disagreement rates.','',*manifest['limitations']]
    path=ROOT/'reports'/(directory.name+'-comparison.json');write(path,record)
    path.with_suffix('.md').write_text('\n'.join(lines)+'\n');return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',action='store_true')
    p.add_argument('--arm',choices=ARMS);p.add_argument('--all',action='store_true');args=p.parse_args()
    try:
        if args.freeze:freeze()
        if args.all:
            for arm in ARMS:
                report=run_arm(arm);compare()
                if report['status']=='passed':break
        elif args.arm:run_arm(args.arm)
        result=compare();print(result['decision'])
    except (OSError,ValueError,RuntimeError) as exc:
        p.exit(2,'Local experiment stopped: '+str(exc)+'\n')
    if result['status']=='complete' and not any(r['status']=='passed' for r in result['arms'].values()):
        p.exit(1,'No arm cleared the unchanged bar.\n')


if __name__=='__main__':main()
