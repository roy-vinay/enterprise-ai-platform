"""Focused-call contracts and local-only experimental safeguards, no live models."""
import json
import pytest
from premise_eval import decomposed as d
from premise_eval.judgment import FIELDS
from validation import run_decomposed as run

VALUES=dict(premise_diagnosis='flawed',flaw_type='false_premise',accepted_premise=False,
            overclaimed_coverage=False,action_taken='repair',evidence_correctness=True,usefulness=True)
CASE=dict(question='Why did volume spike?',reference_facts=['Volume fell from 8 to 7.'])


class Fake:
    def __init__(self,handler=None):self.calls=[];self.handler=handler
    def identity(self):return dict(model='offline-unit')
    def complete_sample(self,messages,schema,temperature,seed):
        keys=schema['required'];self.calls.append(dict(keys=keys,temperature=temperature,seed=seed,messages=messages))
        value={k:VALUES[k] for k in keys}
        return self.handler(value,seed) if self.handler else json.dumps(value)


def test_combiner_requires_every_field():
    p={f:dict(graded=True,value=VALUES[f]) for f in FIELDS}
    assert d.combine(p)['graded']
    p['evidence_correctness']['graded']=False
    r=d.combine(p)
    assert not r['graded'] and 'judgment' not in r and 'evidence_correctness' in r['reason']
    del p['usefulness']
    assert not d.combine(p)['graded']


def test_five_calls_provenance_and_action_dependencies():
    backend=Fake();r=d.judge_decomposed('A reframed answer',CASE,dict(passed=True),backend)
    assert r['graded'] and len(backend.calls)==5
    assert set(r['field_provenance'])==set(FIELDS)
    for field,p in r['field_provenance'].items():
        assert p['prompt_version'].endswith('-v1') and len(p['prompt_sha256'])==64
        assert p['value']==VALUES[field]
    action=next(c for c in backend.calls if c['keys']==['action_taken'])
    data=json.loads(action['messages'][1]['content'])
    assert data['premise_decision']['accepted_premise'] is False
    assert data['coverage_decision']['overclaimed_coverage'] is False
    assert set(data)=={'question','response','premise_decision','coverage_decision'}
    evidence=next(c for c in backend.calls if c['keys']==['evidence_correctness'])
    assert json.loads(evidence['messages'][1]['content'])['evidence_report']['verified_case_facts']==CASE['reference_facts']
    usefulness=next(c for c in backend.calls if c['keys']==['usefulness'])
    assert set(json.loads(usefulness['messages'][1]['content']))=={'question','response'}
    assert all(c['temperature']==0 and c['seed']==17 for c in backend.calls)


def test_failed_sample_retries_then_whole_judgment_ungraded():
    def handler(value,seed):return '{}' if 'premise_diagnosis' in value else json.dumps(value)
    backend=Fake(handler);r=d.judge_decomposed('Unit',CASE,dict(passed=True),backend)
    assert not r['graded'] and 'judgment' not in r
    assert r['subcalls']['premise'][0]['attempts']==3
    assert not r['subcalls']['action']
    assert r['field_provenance']['action_taken']['graded'] is False
    assert r['field_provenance']['usefulness']['graded'] is True


def test_sampling_diversity_vote_splits_and_categorical_tie():
    def handler(value,seed):
        if 'accepted_premise' in value:value['accepted_premise']=seed==101
        if 'action_taken' in value:value['action_taken']={101:'answer',202:'challenge',303:'repair'}[seed]
        return json.dumps(value)
    backend=Fake(handler);r=d.judge_decomposed('Unit',CASE,dict(passed=True),backend,voting=True)
    assert len(backend.calls)==15 and not r['graded']
    assert all(c['temperature']==.7 for c in backend.calls)
    assert {c['seed'] for c in backend.calls}=={101,202,303}
    assert r['field_provenance']['accepted_premise']['value'] is False
    stats=d.vote_statistics({'unit':r})
    assert stats['accepted_premise']['split_rate']==1
    assert stats['overclaimed_coverage']['split_rate']==0
    assert stats['action_taken']['ties']==1 and stats['action_taken']['complete_vote_sets']==1


@pytest.mark.parametrize('field,value',[('accepted_premise',True),('overclaimed_coverage',True),
    ('evidence_correctness',False),('usefulness',False)])
def test_safety_conservative_boolean_ties(field,value):
    r=d.vote(field,[True,False]);assert r['graded'] and r['tie'] and r['value'] is value


def test_categorical_tie_fails_closed():
    r=d.vote('action_taken',['answer','challenge','repair'])
    assert not r['graded'] and r['tie'] and 'value' not in r


def test_evidence_cannot_contradict_failed_verifier():
    backend=Fake();r=d.judge_decomposed('Unit',CASE,dict(passed=False),backend)
    assert not r['graded']
    assert r['subcalls']['evidence'][0]['attempts']==3
    assert not r['field_provenance']['evidence_correctness']['graded']


@pytest.mark.parametrize('raw',['{"overclaimed_coverage":"false"}',
    '{"overclaimed_coverage":false,"extra":true}',
    '{"overclaimed_coverage":false,"overclaimed_coverage":true}'])
def test_strict_subcall_json(raw):
    with pytest.raises(ValueError):d.parse_stage(raw,'coverage')


def test_frozen_input_verification(tmp_path,monkeypatch):
    (tmp_path/'manifest.json').write_text(json.dumps(dict(input_sha256={'prompt':'old'},response_ids=['unit'])))
    monkeypatch.setattr(run,'input_hashes',lambda directory:{'prompt':'old'})
    monkeypatch.setattr(run,'dry_run_inputs',lambda:([dict(response_id='unit')],{}))
    assert run.frozen(tmp_path)['response_ids']==['unit']
    monkeypatch.setattr(run,'input_hashes',lambda directory:{'prompt':'changed'})
    with pytest.raises(ValueError,match='Frozen input hashes'):run.frozen(tmp_path)


def test_local_sampler_records_actual_options_and_call_count(tmp_path,monkeypatch):
    backend=d.LocalSampler(ledger=tmp_path/'calls.jsonl');requests=[]
    def request(path,payload=None):
        requests.append((path,payload))
        if path=='/api/tags':return dict(models=[dict(name=backend.model,digest='unit-digest')])
        return dict(done=True,message=dict(content='{"usefulness":true}'))
    monkeypatch.setattr(backend,'_request',request)
    backend.complete_sample([dict(role='user',content='Unit')],d.schema_for('usefulness'),.7,202)
    payload=next(v for k,v in requests if k=='/api/chat')
    assert payload['options']==dict(temperature=.7,seed=202,num_ctx=8192,num_predict=512)
    assert backend.model_calls==1
    assert backend.url=='http://127.0.0.1:11434' and 'api.anthropic.com' not in json.dumps(requests)
    assert d.LocalSampler(ledger=tmp_path/'calls.jsonl').model_calls==1


def test_split_denominator_keeps_failures_visible():
    provenance={f:dict(samples_complete=False,graded=False,split=False,tie=False) for f in FIELDS}
    stats=d.vote_statistics({'unit':dict(field_provenance=provenance)})
    assert all(r['incomplete_vote_sets']==1 and r['split_rate'] is None for r in stats.values())
