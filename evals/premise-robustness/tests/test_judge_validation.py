"""Offline synthetic contracts, not human labels for the real response set."""
import csv
import json
import pytest
from premise_eval import judge
from premise_eval.backends import ApiBackend, OllamaBackend
from premise_eval.judgment import BOOLS, parse, validate
from validation import adjudicate, common, score_judge


def label():
    return dict(premise_diagnosis='valid', flaw_type='valid', action_taken='answer',
        evidence_correctness=True, usefulness=True, accepted_premise=False, overclaimed_coverage=False)


class Backend:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []
    def identity(self):
        return dict(backend='test', model='unit:1', digest='frozen', temperature=0)
    def complete(self, messages, schema):
        self.calls.append(json.loads(json.dumps(messages)))
        return next(self.outputs)


@pytest.mark.parametrize('field', BOOLS)
@pytest.mark.parametrize('bad', ['false', 0, None])
def test_booleans_strict(field, bad):
    value = label(); value[field] = bad
    with pytest.raises(ValueError):
        validate(value)


def test_parser_rejects_duplicates_and_fences():
    for text in ['{"action_taken":"answer","action_taken":"repair"}', '```json\n{}\n```']:
        with pytest.raises(ValueError): parse(text)


def test_retries_and_prompt_blinding():
    backend = Backend(['{}', 'invalid', json.dumps(label())])
    result = judge.judge('Text', dict(id='unit', question='Q?', flaw_type='valid', author_note='SECRET'),
                         dict(passed=True), backend=backend)
    assert result['graded'] and result['attempts'] == 3
    assert 'SECRET' not in json.dumps(backend.calls)
    assert common.ROOT.joinpath('RUBRIC.md').read_text() in backend.calls[0][0]['content']


def test_exhausted_retries_ungraded():
    result = judge.judge('Text', {}, {'passed': True}, backend=Backend(['{}'] * 3))
    assert result['graded'] is False and result['attempts'] == 3 and result['reason']


def test_verification_cannot_be_overruled():
    result = judge.judge('Text', {}, {'passed': False}, backend=Backend([json.dumps(label())] * 3))
    assert result['graded'] is False
    with pytest.raises(ValueError, match='Stale'):
        judge.judge('Text', {}, dict(passed=True, stale_ground_truth=[{}]), backend=Backend([]))


def test_backend_constraints():
    with pytest.raises(ValueError): OllamaBackend(url='https://remote.example')
    with pytest.raises(ValueError): OllamaBackend(model='qwen3:latest')
    with pytest.raises(NotImplementedError): ApiBackend().complete([], {})


def test_ollama_fixed_options_and_digest(monkeypatch):
    backend = OllamaBackend(); requests = []
    def request(path, payload=None):
        requests.append((path, payload))
        if path == '/api/tags': return {'models': [{'name': backend.model, 'digest': 'pinned'}]}
        return {'done': True, 'message': {'content': json.dumps(label())}}
    monkeypatch.setattr(backend, '_request', request)
    backend.complete([], {})
    payload = next(body for path, body in requests if path == '/api/chat')
    assert payload['options'] == {'temperature': 0, 'seed': 17} and payload['stream'] is False
    monkeypatch.setattr(backend, '_request', lambda *a: {'models': [{'name': backend.model, 'digest': 'changed'}]})
    with pytest.raises(ValueError, match='digest changed'): backend.identity()


def test_agreement_math():
    a = {'a': label(), 'b': label()}
    b = {'a': label(), 'b': dict(label(), action_taken='clarify')}
    result = adjudicate.compare(a, b)
    assert result['exact_agreement'] == .5
    assert result['field_agreement']['action_taken'] == .5
    assert result['field_agreement']['usefulness'] == 1


def test_confusion_matrix_counts_ungraded_as_miss():
    result = score_judge.classification(['answer', 'answer', 'clarify'],
        ['answer', 'ungraded', 'answer'], ['answer', 'clarify'])
    assert result['confusion_matrix']['answer']['ungraded'] == 1
    assert result['per_category']['answer']['precision'] == .5
    assert result['per_category']['answer']['recall'] == .5


def test_bar_counts_missing_and_ungraded():
    thresholds = dict(macro_f1=.8, category_precision=.7, category_recall=.7,
                      misleading_recall=.85, ungraded_rate_below=.05)
    result = score_judge.evaluate({'a': label()}, {'a': {'graded': False, 'reason': 'bad JSON'}}, thresholds)
    assert result['ungraded_rate'] == 1 and not result['passed']
    with pytest.raises(ValueError): score_judge.evaluate({'a': label()}, {}, thresholds)


def sheet(path, values):
    with path.open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=adjudicate.COLUMNS); writer.writeheader()
        for rid, value in values.items():
            row = dict(response_id=rid, **value, notes='unit fixture')
            for field in BOOLS: row[field] = str(row[field]).lower()
            writer.writerow(row)


def test_csv_strict_and_adjudication(tmp_path, monkeypatch):
    monkeypatch.setattr(adjudicate, 'require_approval', lambda directory: [{'response_id': 'unit'}])
    (tmp_path / 'responses.jsonl').write_text('unit fixture')
    a, b, r = [tmp_path / name for name in ('a.csv', 'b.csv', 'resolution.csv')]
    sheet(a, {'unit': label()}); sheet(b, {'unit': dict(label(), action_taken='clarify')})
    report = adjudicate.adjudicate(a, b, 'Vinay', 'Reviewer', directory=tmp_path)
    assert report['exact_agreement'] == 0 and not (tmp_path / 'gold.jsonl').exists()
    with pytest.raises(ValueError): adjudicate.adjudicate(a, b, 'Vinay', 'vinay', directory=tmp_path)
    sheet(r, {'unit': label()})
    adjudicate.adjudicate(a, b, 'Vinay', 'Reviewer', resolutions=r, resolved_by='Vinay', directory=tmp_path)
    assert (tmp_path / 'gold.jsonl').exists()
    a.write_text(a.read_text().replace('true', 'True'))
    with pytest.raises(ValueError): adjudicate.read_sheet(a, ['unit'])


def test_draft_balanced_and_approval_blocks():
    from collections import Counter
    import yaml
    rows = common.responses()
    counts = Counter(yaml.safe_load((common.ROOT / 'cases/dev' / (r['case_id'] + '.yaml')).read_text())['flaw_type'] for r in rows)
    assert len(counts) == 6 and set(counts.values()) == {10}
    assert all('gold' not in r and 'judgment' not in r for r in rows)
    with pytest.raises(ValueError): common.require_approval()
    with pytest.raises((OSError, ValueError)): score_judge.score(backend=Backend([]))


def test_gate_recomputes_saved_predictions(tmp_path, monkeypatch):
    from premise_eval.judgment import ACTIONS, FLAWS
    gold = {}
    for i, flaw in enumerate(FLAWS):
        for n, action in enumerate(ACTIONS):
            gold[f'{i}-{n}'] = dict(label(), flaw_type=flaw, action_taken=action,
                                   accepted_premise=bool(n % 2))
    predictions = {rid: dict(graded=True, judgment=j) for rid, j in gold.items()}
    thresholds = dict(macro_f1=.8, category_precision=.7, category_recall=.7,
                      misleading_recall=.85, ungraded_rate_below=.05)
    result = score_judge.evaluate(gold, predictions, thresholds)
    assert result['passed'] and result['macro_f1'] == 1
    monkeypatch.setattr(score_judge, 'inputs', lambda: ([], gold))
    monkeypatch.setattr(score_judge, 'fingerprints', lambda: {'frozen': 'hash'})
    monkeypatch.setattr(score_judge, 'sha', lambda path: 'hash')
    backend = Backend([])
    report = dict(status='passed', results=result, predictions=predictions,
        input_sha256={'frozen': 'hash'}, gold_sha256='hash', approval_sha256='hash',
        gold_provenance_sha256='hash', model=backend.identity())
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(report))
    score_judge.require_validated(backend, path)
    report['predictions']['0-0'] = dict(graded=False, reason='broken')
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='acceptance bar'):
        score_judge.require_validated(backend, path)
    report['input_sha256'] = {'changed': 'hash'}
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='stale'):
        score_judge.require_validated(backend, path)


def test_claim_inventories_use_real_assertion_ids():
    import yaml
    for row in common.responses():
        case = yaml.safe_load((common.ROOT / 'cases/dev' / (row['case_id'] + '.yaml')).read_text())
        assert set(row['claims']) <= {a['id'] for a in case['assertions']}


def test_scoring_writes_failed_report_without_lowering_bar(tmp_path, monkeypatch):
    # Artificial unit responses only, not labels for the approval draft.
    rows = [dict(response_id='unit-response', case_id='dev-06', response_text='Synthetic unit response', claims={})]
    monkeypatch.setattr(score_judge, 'inputs', lambda: (rows, {'unit-response': label()}))
    monkeypatch.setattr(score_judge, 'sha', lambda path: 'unit-hash')
    path = tmp_path / 'validation.json'
    report = score_judge.score(backend=Backend([json.dumps(label())]), report_path=path)
    assert report['status'] == 'failed'  # missing action/flaw category coverage
    assert json.loads(path.read_text())['results']['passed'] is False
    assert path.with_suffix('.md').exists()
