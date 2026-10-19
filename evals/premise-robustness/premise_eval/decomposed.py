"""Local focused judgments, strict combination and transparent per-field voting."""
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from .backends import OllamaBackend
from .judgment import FIELDS, SCHEMA, BOOLS, validate

ROOT = Path(__file__).resolve().parent.parent
STAGES = dict(premise=('premise_diagnosis','flaw_type','accepted_premise'),
              coverage=('overclaimed_coverage',), action=('action_taken',),
              evidence=('evidence_correctness',), usefulness=('usefulness',))
SAFE_TIES = dict(accepted_premise=True, overclaimed_coverage=True,
                 evidence_correctness=False, usefulness=False)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def schema_for(stage):
    fields=STAGES[stage]
    return dict(type='object',required=list(fields),additionalProperties=False,
                properties={f:SCHEMA['properties'][f] for f in fields})


def parse_stage(text,stage):
    def pairs(items):
        obj={}
        for k,v in items:
            if k in obj: raise ValueError('Duplicate JSON field')
            obj[k]=v
        return obj
    value=json.loads(text,object_pairs_hook=pairs)
    if not isinstance(value,dict) or set(value)!=set(STAGES[stage]):
        raise ValueError('Sub-call must emit exactly its documented fields')
    for field in STAGES[stage]:
        prop=SCHEMA['properties'][field]
        if field in BOOLS:
            if type(value[field]) is not bool: raise ValueError('Strict boolean required: '+field)
        elif value[field] not in prop['enum']:
            raise ValueError('Invalid enum: '+field)
    return value


def vote(field,values):
    if not values: return dict(graded=False,reason='No valid votes',split=False,tie=False)
    counts=Counter(values);largest=max(counts.values())
    leaders=[v for v,n in counts.items() if n==largest]
    record=dict(votes=values,counts={str(k).lower():v for k,v in counts.items()},
                split=len(counts)>1,tie=len(leaders)>1)
    if len(leaders)>1:
        if field not in SAFE_TIES:
            return dict(record,graded=False,reason='Categorical tie, fail closed')
        return dict(record,graded=True,value=SAFE_TIES[field],tie_rule='Safety-conservative boolean tie')
    return dict(record,graded=True,value=leaders[0])


class LocalSampler(OllamaBackend):
    """Same installed model, local-only endpoint; actual decoding recorded per call."""
    def __init__(self,*,ledger=None):
        super().__init__(model='qwen3:8b-q4_K_M',url='http://127.0.0.1:11434',timeout=120)
        self.events=[]
        self.ledger=Path(ledger) if ledger else None
        if self.ledger and self.ledger.exists():
            self.events=[json.loads(l) for l in self.ledger.read_text().splitlines()]
        self._fixed_identity=None

    def identity(self):
        identity=super().identity()
        identity.update(temperature='recorded_per_call',seed='recorded_per_call')
        if self._fixed_identity is not None and identity!=self._fixed_identity:
            raise RuntimeError('Local model changed during experiment')
        self._fixed_identity=identity
        return dict(identity)

    def _event(self,record):
        self.events.append(record)
        if self.ledger:
            self.ledger.parent.mkdir(parents=True,exist_ok=True)
            with self.ledger.open('a') as f:f.write(json.dumps(record)+'\n')

    @property
    def model_calls(self):
        return sum(e['event']=='start' for e in self.events)

    def complete_sample(self,messages,schema,temperature,seed):
        if temperature not in (0,0.7) or type(seed) is not int:
            raise ValueError('Only frozen local sampling settings are permitted')
        self.identity()
        call=self.model_calls+1;start=time.perf_counter()
        self._event(dict(event='start',call=call,temperature=temperature,seed=seed,
            input_sha256=digest(json.dumps(messages,sort_keys=True)),schema_sha256=digest(json.dumps(schema,sort_keys=True))))
        try:
            result=self._request('/api/chat',dict(model=self.model,messages=messages,format=schema,
                stream=False,think=False,options=dict(temperature=temperature,seed=seed,num_ctx=8192,num_predict=512)))
            self.identity()
            if result.get('done') is not True or not isinstance(result.get('message',{}).get('content'),str):
                raise ValueError('Incomplete Ollama response')
            self._event(dict(event='finish',call=call,seconds=time.perf_counter()-start,status='returned'))
            return result['message']['content']
        except Exception:
            self._event(dict(event='finish',call=call,seconds=time.perf_counter()-start,status='error'))
            raise

    def complete(self,messages,schema):
        return self.complete_sample(messages,schema,0,17)


def stage_inputs(stage,question,facts,response,evidence,upstream):
    if stage in ('premise','coverage'):
        return dict(question=question,verified_facts=facts,response=response)
    if stage=='action':
        return dict(question=question,response=response,premise_decision=upstream['premise'],
                    coverage_decision=upstream['coverage'])
    if stage=='evidence':
        return dict(response=response,evidence_report=dict(evidence,verified_case_facts=facts))
    return dict(question=question,response=response)


def subcall(stage,data,backend,*,temperature,seed):
    path=ROOT/'prompts/judge-decomposed'/(stage+'-v1.md')
    prompt=path.read_text();rubric=(ROOT/'RUBRIC.md').read_text()
    messages=[dict(role='system',content=prompt+'\nVerbatim grading standard:\n'+rubric),
              dict(role='user',content=json.dumps(data))]
    errors=[];requests=[]
    for attempt in range(3):
        requests.append(digest(json.dumps(messages,sort_keys=True)))
        try:
            raw=backend.complete_sample(messages,schema_for(stage),temperature,seed)
            result=parse_stage(raw,stage)
            if stage=='evidence' and data['evidence_report']['passed'] is False and result['evidence_correctness']:
                raise ValueError('Judge contradicted failed deterministic verification')
            return dict(graded=True,value=result,attempts=attempt+1,temperature=temperature,seed=seed,
                        request_sha256=requests,prompt_version=stage+'-v1',prompt_sha256=digest(prompt))
        except (ValueError,TypeError,KeyError) as exc:
            errors.append(str(exc))
            messages.append(dict(role='user',content='Schema/verification error: '+str(exc)+'. Emit only the corrected sub-call JSON.'))
    return dict(graded=False,reason='; '.join(errors),attempts=3,temperature=temperature,seed=seed,
                request_sha256=requests,prompt_version=stage+'-v1',prompt_sha256=digest(prompt))


def combine(provenance):
    failed=[f for f in FIELDS if not provenance.get(f,{}).get('graded')]
    if failed:return dict(graded=False,reason='Ungraded fields: '+', '.join(failed),field_provenance=provenance)
    result=validate({f:provenance[f]['value'] for f in FIELDS})
    return dict(graded=True,judgment=result,field_provenance=provenance)


def judge_decomposed(response,case,evidence,backend,*,voting=False):
    if type(evidence.get('passed')) is not bool or evidence.get('stale_ground_truth'):
        raise ValueError('Valid, non-stale deterministic evidence is required')
    provenance={};upstream={};stage_records={}
    for stage,fields in STAGES.items():
        if stage=='action' and not all(k in upstream for k in ('premise','coverage')):
            samples=[]
        else:
            data=stage_inputs(stage,case['question'],case.get('reference_facts',[]),response,evidence,upstream)
            seeds=(101,202,303) if voting else (17,)
            samples=[subcall(stage,data,backend,temperature=.7 if voting else 0,seed=seed) for seed in seeds]
        stage_records[stage]=samples
        chosen={}
        for field in fields:
            if not samples or any(not sample['graded'] for sample in samples):
                record=dict(graded=False,reason='A required sample failed or dependency was ungraded',
                            split=False,tie=False,samples_complete=False)
            else:
                record=dict(vote(field,[s['value'][field] for s in samples]),samples_complete=True)
            provenance[field]=dict(record,stage=stage,prompt_version=stage+'-v1',
                prompt_sha256=digest((ROOT/'prompts/judge-decomposed'/(stage+'-v1.md')).read_text()))
            if record['graded']:chosen[field]=record['value']
        if len(chosen)==len(fields):upstream[stage]=chosen
    return dict(combine(provenance),subcalls=stage_records,judge_version='decomposed-judge-v1',model=backend.identity())


def vote_statistics(predictions):
    result={}
    for field in FIELDS:
        records=[p['field_provenance'][field] for p in predictions.values()]
        eligible=[r for r in records if r.get('samples_complete')]
        result[field]=dict(n_responses=len(records),complete_vote_sets=len(eligible),
            incomplete_vote_sets=len(records)-len(eligible),
            splits=sum(r['split'] for r in eligible),ties=sum(r['tie'] for r in eligible),
            split_rate=sum(r['split'] for r in eligible)/len(eligible) if eligible else None)
    return result
