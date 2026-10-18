"""Version selection, real repair fixtures, and approval isolation."""
import json
import re
import pytest
import yaml
from premise_eval import judge, db, verify
from premise_eval.judgment import validate, ACTIONS
from validation import common, score_judge
from test_judge_validation import Backend, label


def test_v2_premise_first_and_examples():
    text = (common.ROOT / 'prompts/judge-v2.md').read_text()
    assert text.index('1. Identify') < text.index('2. Decide accepted_premise') < text.index('3. Decide overclaimed_coverage') < text.index('4. Only then choose action_taken')
    examples = [json.loads(s) for s in re.findall(r'```json\n(.*?)\n```', text, re.S)]
    assert len(examples) == 6
    assert [e['accepted_premise'] for e in examples] == [True, False, True, False, True, True]
    for e in examples:
        assert type(e['accepted_premise']) is bool
        assert type(e['overclaimed_coverage']) is bool
        assert e['action_taken'] in ACTIONS
    assert examples[-1] == dict(accepted_premise=True, overclaimed_coverage=True, action_taken='repair')
    assert 'Do not let surface quality lower accepted_premise to false.' in text


def test_prompt_version_selection_and_v1_retained(tmp_path):
    cfg = tmp_path / 'config.yaml'; cfg.write_text('judge-prompt: judge-v1\n')
    b = Backend([json.dumps(label())])
    r = judge.judge('Unit text', {}, {'passed': True}, backend=b, config=cfg)
    assert r['judge_version'] == 'judge-v1'
    assert b.calls[0][0]['content'].startswith('# Judge v1')
    assert judge.prompt_version() == 'judge-v2'
    cfg.write_text('judge-prompt: ../../unexpected\n')
    with pytest.raises(ValueError): judge.prompt_version(cfg)


def test_repairs_and_original_prefix(tmp_path):
    rows, references = score_judge.dry_run_inputs()
    original = (common.HERE / 'archive-v1/responses.jsonl').read_bytes()
    assert (common.HERE / 'responses.jsonl').read_bytes().startswith(original)
    assert len(rows) == 68 and len(rows[60:]) == 8
    assert len({references[r['response_id']]['flaw_type'] for r in rows[60:]}) >= 3
    con = db.verification_connection(db.build_db(tmp_path / 'support.db'))
    try:
        for row in rows[60:]:
            ref = validate({k:v for k,v in references[row['response_id']].items()})
            assert ref['action_taken'] == 'repair' and row['author_note']
            case = yaml.safe_load((common.ROOT / 'cases/dev' / (row['case_id']+'.yaml')).read_text())
            assert verify.verify_ground_truth(case, con)['passed']
            result = verify.verify_response_claims(case, row['claims'], con)
            if ref['evidence_correctness']:
                assert result['passed']
            if row['response_id'].startswith('ambiguity-'):
                assert 'July records are absent' in row['response_text']
    finally:
        con.close()
    assert set(ACTIONS) == {r['action_taken'] for r in references.values()}


def test_dry_run_does_not_pass_approval_or_downstream_gate(tmp_path):
    rows, _ = score_judge.dry_run_inputs()
    assert len(rows) == 68
    with pytest.raises(ValueError, match='approve'):
        common.require_approval()
    report = tmp_path / 'dry.json'; report.write_text('{"dry_run": true, "status": "passed"}')
    with pytest.raises(ValueError, match='cannot authorize'):
        score_judge.require_validated(Backend([]), report)


def test_comparison_renders_missing_repair_honestly():
    baseline = json.loads((common.ROOT / 'reports/judge-validation-v1.json').read_text())['results']
    table = score_judge.comparison_table(baseline, baseline, baseline)
    assert '| action_taken/repair | N/A (no support)' in table
    assert '| misleading/misleading |' in table
    assert 'same 60' in table and 'n=68' in table


def test_historical_report_cannot_be_overwritten():
    with pytest.raises(ValueError, match='immutable'):
        score_judge.score(report_path=common.ROOT / 'reports/judge-validation-v1.json')


def test_dry_run_rejects_stale_or_uncovered_references(tmp_path):
    import shutil
    import hashlib
    copied = tmp_path / 'validation'
    shutil.copytree(common.HERE, copied)
    refs = copied / 'agent-reference-v2.jsonl'
    refs.write_text(refs.read_text() + '\n')
    with pytest.raises(ValueError, match='provenance'):
        score_judge.dry_run_inputs(copied)
    # Re-pin the deliberate unit mutation, then exercise the category guard.
    rows = [json.loads(s) for s in refs.read_text().splitlines() if s]
    for row in rows[60:]: row['action_taken'] = 'answer'
    refs.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    provenance = copied / 'agent-reference-v2-provenance.json'
    value = json.loads(provenance.read_text())
    value['references_sha256'] = hashlib.sha256(refs.read_bytes()).hexdigest()
    provenance.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='coverage missing: repair'):
        score_judge.dry_run_inputs(copied)
