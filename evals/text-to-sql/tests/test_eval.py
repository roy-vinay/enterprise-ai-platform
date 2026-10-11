"""Tests for the eval itself. An eval that is wrong is worse than no eval."""
import copy

import pytest

from t2s_eval import config, lint, metamorphic, mutation, rules, selective, semantic
from t2s_eval.bots.base import BotResponse
from t2s_eval.bots.simulated import SimulatedBot, normalize
from t2s_eval.db import Warehouse, compare
from t2s_eval.grade import grade_response, grade_suite, summarize


@pytest.fixture(scope="session")
def env():
    model = semantic.load(config.MODEL)
    cases = config.load_cases()
    wh = Warehouse(str(config.ensure_warehouse()), model["row_cap"])
    return model, cases, config.load_relations(), wh


def case(cases, cid):
    return next(c for c in cases if c["id"] == cid)


# ------------------------------------------------------------- the dataset

def test_case_ids_unique(env):
    _, cases, _, _ = env
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))


def test_every_reference_query_runs(env):
    _, cases, _, wh = env
    for c in cases:
        if c.get("reference_sql"):
            assert wh.run(c["reference_sql"]).error is None, c["id"]


def test_trap_set_lints_clean(env):
    _, cases, _, wh = env
    assert lint.lint(cases, wh) == []


def test_lint_flags_a_window_insensitive_case(env):
    _, cases, _, wh = env
    loose = copy.deepcopy(case(cases, "c01"))
    loose["tolerance"] = 0.001  # MRR barely moves month to month
    assert any(i["issue"] == "window_insensitive" for i in lint.lint([loose], wh))


# --------------------------------------------------------------- grading

def test_perfect_bot_passes_everything(env):
    model, cases, relations, wh = env
    bot = SimulatedBot(model, cases, "perfect")
    results = grade_suite(cases, bot, wh, model, n_runs=2)
    assert all(r.passed for r in results), [(r.case_id, r.reason) for r in results if not r.passed]
    assert all(r.status == "holds" for r in metamorphic.run_all(relations, cases, bot, wh))


def test_overanswer_on_refusal_fails(env):
    model, cases, _, wh = env
    c = case(cases, "c21")
    r = grade_response(c, BotResponse("answer", sql=c["tempting_sql"]), wh, model, None)
    assert not r.passed and r.failed_check == "behavior"


def test_refusal_on_answerable_fails(env):
    model, cases, _, wh = env
    c = case(cases, "c01")
    ref = wh.run(c["reference_sql"]).rows
    r = grade_response(c, BotResponse("refuse"), wh, model, ref)
    assert not r.passed and r.failed_check == "behavior"


def test_clarify_accepted_where_allowed(env):
    model, cases, _, wh = env
    c = case(cases, "c13")
    ref = wh.run(c["reference_sql"]).rows
    assert grade_response(c, BotResponse("clarify"), wh, model, ref).passed


def test_every_tempting_answer_fails(env):
    model, cases, _, wh = env
    for c in cases:
        if not c.get("tempting_sql"):
            continue
        ref = wh.run(c["reference_sql"]).rows if c.get("reference_sql") else None
        r = grade_response(c, BotResponse("answer", sql=c["tempting_sql"]), wh, model, ref)
        assert not r.passed, f"{c['id']} tempting answer passed"


def test_confident_wrong_rate_counts_only_unanimous_errors(env):
    model, cases, _, wh = env
    results = grade_suite(cases, SimulatedBot(model, cases, "overconfident"), wh, model, n_runs=5)
    s = summarize(results)
    cw = [r for r in results if r.answered and not r.passed and r.confidence == 1.0]
    assert s["confident_wrong_rate"] == pytest.approx(len(cw) / s["answered"])


# ------------------------------------------------------------------ rules

def test_substitution_detected(env):
    model, cases, _, _ = env
    c = case(cases, "c25")
    f = rules.check(c["question"], c["tempting_sql"], model)
    assert any(x.rule == "ungrounded_filter_value" for x in f)


def test_grounded_synonym_not_flagged(env):
    model, cases, _, _ = env
    c = case(cases, "c10")  # "competitors" -> switched_competitor
    assert not any(x.rule == "ungrounded_filter_value"
                   for x in rules.check(c["question"], c["reference_sql"], model))


def test_snapshot_sum_detected(env):
    model, cases, _, _ = env
    c = case(cases, "c20")
    assert any(x.rule == "snapshot_summed_across_time"
               for x in rules.check(c["question"], c["tempting_sql"], model))


def test_missing_test_exclusion_detected(env):
    model, cases, _, _ = env
    c = case(cases, "c11")
    assert any(x.rule == "missing_test_exclusion"
               for x in rules.check(c["question"], c["tempting_sql"], model))


def test_reference_sql_passes_rules(env):
    model, cases, _, _ = env
    for c in cases:
        if c.get("reference_sql"):
            assert rules.check(c["question"], c["reference_sql"], model) == [], c["id"]


# ------------------------------------------------------------ comparison

def test_set_compare_ignores_row_order():
    assert compare([("a", 1.0), ("b", 2.0)], [("b", 2.0), ("a", 1.0)], "set", 0)[0]


def test_ranked_compare_respects_order():
    assert not compare([("a", 2.0), ("b", 1.0)], [("b", 1.0), ("a", 2.0)], "top_n_ordered", 0)[0]


# -------------------------------------------------------------- simulator

def test_normalize_strips_paraphrase_wrappers():
    assert normalize("Quick question: What was MRR last month? please") == "what was mrr last month"
    assert normalize("Hey bot, sept 2026 MRR?") == "sept 2026 mrr"


def test_simulator_is_deterministic(env):
    model, cases, _, _ = env
    a = SimulatedBot(model, cases, "overconfident").ask("What was MRR last month?", run=3)
    b = SimulatedBot(model, cases, "overconfident").ask("What was MRR last month?", run=3)
    assert a == b


def test_grader_catches_every_injected_fault(env):
    from t2s_eval.judge import fault_detection
    model, cases, _, wh = env
    results = grade_suite(cases, SimulatedBot(model, cases, "overconfident"), wh, model, n_runs=5)
    fd = fault_detection(results)
    assert fd["false_alarms"] == 0
    for fault, v in fd["recall_by_fault"].items():
        assert v["recall"] == 1.0, fault


# ---------------------------------------------------------- metamorphic

def test_partition_violation_detected(env):
    model, cases, _, wh = env

    class Inflated(SimulatedBot):
        def ask(self, q, run=0):
            r = super().ask(q, run)
            if q == "How much revenue did we collect in Q3 2026?":
                r.sql = r.sql.replace("status = 'paid' AND ", "")  # total includes unpaid
            return r

    rel = {"id": "t", "type": "partition_sum", "total": "How much revenue did we collect in Q3 2026?",
           "parts": "Revenue by region in Q3 2026"}
    assert metamorphic.check_relation(rel, Inflated(model, cases, "perfect"), wh).status == "violated"


# --------------------------------------------------------------- mutation

def test_mutation_catches_churn_definition_change(env):
    model, cases, relations, wh = env
    res = mutation.run(model, cases, relations, lambda m: SimulatedBot(m, cases, "perfect"), wh)
    by_id = {r.id: r for r in res}
    assert by_id["churned_accounts.drop_filter.1"].killed       # canceled_by = 'customer'
    assert by_id["global.drop.exclude_test_accounts"].killed
    assert by_id["avg_csat.drop_filter.0"].verdict == "equivalent_on_current_data"  # AVG skips NULLs


# ------------------------------------------------------------- selective

def test_threshold_one_never_has_more_errors_than_zero(env):
    model, cases, _, wh = env
    results = grade_suite(cases, SimulatedBot(model, cases, "overconfident"), wh, model, n_runs=5)
    pts = {p.threshold: p for p in selective.sweep(results)}
    assert pts[1.0].wrong <= pts[0.0].wrong
    assert pts[1.0].coverage <= pts[0.0].coverage
