"""Regression checks for review findings: isolation, metrics, and provenance."""
import hashlib
import json
import sqlite3

import pytest

from premise_eval import db, metrics, runner


def test_cte_cannot_write(tmp_path):
    path = db.build_db(tmp_path / 'support.db')
    con = db.ModelConnection(path)
    try:
        with pytest.raises(db.ReadOnlyViolation):
            con.query('WITH selected AS (SELECT ticket_id FROM support_tickets) DELETE FROM support_tickets')
        assert con.query('SELECT COUNT(*) FROM support_tickets')[0][0] == 24
    finally:
        con.close()
    verification = db.verification_connection(path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            verification.execute('DELETE FROM support_tickets')
    finally:
        verification.close()


def test_useless_repair_is_not_success():
    result = metrics.compute_metrics([dict(flaw_type='false_premise', action_taken='repair',
        evidence_correctness=True, usefulness=False, premise_diagnosis='flawed')])
    assert result['verified_useful_repair_rate'] == 0


def test_frozen_manifest_checks_contents_and_membership(tmp_path, monkeypatch):
    root = tmp_path / 'cases'
    heldout = root / 'heldout'
    heldout.mkdir(parents=True)
    case = heldout / 'test.yaml'
    case.write_text('id: test\nquestion: Test?\n')
    manifest = heldout / 'manifest.json'
    monkeypatch.setattr(runner, 'CASES_ROOT', root)
    monkeypatch.setattr(runner, 'MANIFEST_PATH', manifest)
    manifest.write_text(json.dumps(dict(status='frozen', cases=[dict(
        id='test', path='test.yaml', sha256=hashlib.sha256(case.read_bytes()).hexdigest())])))
    runner.check_heldout_ready()
    case.write_text('id: test\nquestion: Changed?\n')
    with pytest.raises(runner.HeldoutNotReadyError, match='differs'):
        runner.check_heldout_ready()
    manifest.write_text(json.dumps(dict(status='frozen', cases=[])))
    with pytest.raises(runner.HeldoutNotReadyError):
        runner.check_heldout_ready()


def test_report_identifies_demo_and_records_response(tmp_path):
    path = db.build_db(tmp_path / 'support.db')
    report = runner.run('dev', 'fake', 'ordinary', path)
    assert report['research_results'] is False
    assert report['run_kind'] == 'scripted_smoke_test'
    assert all(case['response_text'] for case in report['cases'])
    assert 'cases/dev/dev-01.yaml' in report['versions']['input_sha256']
