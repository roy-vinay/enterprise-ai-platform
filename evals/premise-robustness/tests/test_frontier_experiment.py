"""Offline transport/budget tests; no real API requests or human labels."""
import json
from pathlib import Path
import pytest
from premise_eval.frontier import AnthropicBackend, FrontierBlocked
from premise_eval import judge
from premise_eval.judgment import SCHEMA
from validation import compare_judges, score_judge, common
from test_judge_validation import label, Backend


def configured(tmp_path, monkeypatch, budget=5):
    monkeypatch.setenv('ANTHROPIC_API_KEY','unit-secret-never-exported')
    b=AnthropicBackend(allow_paid=True, budget_usd=budget, ledger_path=tmp_path/'usage.json')
    requests=[]
    def request(path,payload=None):
        requests.append((path,payload))
        if path.startswith('models/'):
            return dict(id=b.model,created_at='2026-09-28T00:00:00Z')
        if path=='messages/count_tokens': return dict(input_tokens=1000)
        return dict(model=b.model,stop_reason='end_turn',usage=dict(input_tokens=1000,output_tokens=100),
                    content=[dict(type='text',text=json.dumps(label()))])
    monkeypatch.setattr(b,'_request',request)
    return b,requests


def test_frontier_requires_approval_and_key_before_network(monkeypatch):
    b=AnthropicBackend()
    with pytest.raises(FrontierBlocked,match='allow-paid'): b.identity()
    b.allow_paid=True;monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    with pytest.raises(FrontierBlocked,match='not available'): b.identity()


def test_frontier_payload_usage_and_secret_exclusion(tmp_path,monkeypatch):
    b,requests=configured(tmp_path,monkeypatch)
    result=judge.judge('Synthetic answer',{},dict(passed=True),backend=b)
    assert result['graded']
    payload=next(v for k,v in requests if k=='messages')
    assert payload['thinking']=={'type':'between_tools'} and 'temperature' not in payload
    assert payload['output_config']['format']['schema']==SCHEMA
    assert payload['max_tokens']==512 and payload['output_config']['effort']=='high'
    assert b.statistics()['actual_cost_usd']==.003
    assert 'unit-secret' not in json.dumps(result)+json.dumps(b.statistics())
    ledger=json.loads((tmp_path/'usage.json').read_text())
    assert ledger['calls'][0]['status']=='received'
    restored=AnthropicBackend(allow_paid=True,ledger_path=tmp_path/'usage.json')
    assert restored.statistics()['actual_cost_usd']==.003


def test_budget_rejects_before_generation(tmp_path,monkeypatch):
    b,requests=configured(tmp_path,monkeypatch,budget=.001)
    with pytest.raises(FrontierBlocked,match='budget would be exceeded'):
        b.complete([dict(role='system',content='Unit'),dict(role='user',content='Unit')],SCHEMA)
    assert not any(k=='messages' for k,v in requests)


def test_unknown_transport_charge_keeps_reservation(tmp_path,monkeypatch):
    b,requests=configured(tmp_path,monkeypatch)
    original=b._request
    def request(path,payload=None):
        if path=='messages': raise FrontierBlocked('Unit timeout')
        return original(path,payload)
    monkeypatch.setattr(b,'_request',request)
    with pytest.raises(FrontierBlocked): b.complete([dict(role='system',content='Unit')],SCHEMA)
    data=json.loads((tmp_path/'usage.json').read_text())
    assert data['charged_or_reserved_usd']>0 and data['actual_cost_usd']==0
    assert data['calls'][0]['status']=='reserved'


def test_refusal_is_metered_but_not_graded(tmp_path,monkeypatch):
    b,_=configured(tmp_path,monkeypatch)
    original=b._request
    def request(path,payload=None):
        value=original(path,payload)
        if path=='messages': value['stop_reason']='refusal'
        return value
    monkeypatch.setattr(b,'_request',request)
    r=judge.judge('Unit',{},dict(passed=True),backend=b)
    assert not r['graded'] and len(b.calls)==3
    assert b.statistics()['actual_cost_usd']==.009


def test_models_cannot_silently_switch(tmp_path,monkeypatch):
    b,_=configured(tmp_path,monkeypatch)
    b.identity()
    monkeypatch.setattr(b,'_request',lambda *a:dict(id='other-model',created_at='x'))
    with pytest.raises(FrontierBlocked,match='identity'): b.identity()


def test_freeze_detects_prompt_or_config_drift(tmp_path,monkeypatch):
    monkeypatch.setattr(compare_judges,'fingerprints',lambda:{'prompt':'a'})
    monkeypatch.setattr(compare_judges,'dry_run_inputs',lambda:([dict(response_id='unit')],{}))
    for arm in compare_judges.ARMS:
        (tmp_path/(arm+'.yaml')).write_text('judge-prompt: judge-v2\n')
    compare_judges.freeze(tmp_path)
    compare_judges.verify_manifest(tmp_path)
    with pytest.raises(ValueError,match='frozen'): compare_judges.freeze(tmp_path)
    (tmp_path/'frontier.yaml').write_text('judge-prompt: judge-v1\n')
    with pytest.raises(ValueError,match='configuration'): compare_judges.verify_manifest(tmp_path)


def test_existing_report_cannot_be_overwritten(tmp_path):
    path=tmp_path/'existing.json';path.write_text('historical')
    with pytest.raises(ValueError,match='already exists'): score_judge.score(report_path=path)
    assert path.read_text()=='historical'


def test_incomplete_comparison_has_no_invented_scores(tmp_path,monkeypatch):
    monkeypatch.setattr(compare_judges,'ROOT',tmp_path)
    monkeypatch.setattr(compare_judges,'verify_manifest',lambda d:dict(experiment='unit',limitations=[]))
    (tmp_path/'manifest.json').write_text('{}')
    (tmp_path/'frontier-blocked.json').write_text('{"status":"blocked","reason":"No API key"}')
    summary=compare_judges.summarize(tmp_path)
    assert summary['status']=='incomplete'
    assert 'results' not in summary['arms']['frontier']
    text=(tmp_path/'reports'/(tmp_path.name+'-comparison.md')).read_text()
    assert 'blocked' in text and 'No model-improvement claim' in text
