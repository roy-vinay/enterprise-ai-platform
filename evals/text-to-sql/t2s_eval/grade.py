"""Grade bot responses: behavior, result, and SQL rules, with owner routing."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

from . import policy, rules
from .bots.base import Bot, BotResponse
from .db import Warehouse, compare, fingerprint

ABSTAIN = ("clarify", "refuse")
# Checks on how the answer was produced, graded next to whether it was right.
TRUST_CHECKS = ("safety", "access", "cost")


@dataclass
class RunResult:
    run: int
    action: str
    interpretation: str
    sql: str | None
    passed: bool
    failed_check: str | None      # behavior | safety | access | sql_rule | result | cost | bot_error | None
    reason: str
    owner: str | None             # semantic_model | prompt | app
    findings: list[dict] = field(default_factory=list)
    injected: list[str] = field(default_factory=list)
    signature: str = ""           # what the user would see: action + result (order kept when it matters)
    rows_scanned: int | None = None   # rows the answer read from storage
    result_correct: bool | None = None  # did the result match, whatever else failed


@dataclass
class CaseResult:
    case_id: str
    question: str
    category: str
    expected_behavior: str
    cost_weight: int
    passed: bool                  # majority vote over runs; a tie counts as a fail
    answered: bool                # the representative run answered
    agreement: float              # share of runs giving the most common user-visible answer.
                                  # A coarse consistency signal, not a calibrated probability.
    failed_check: str | None
    reason: str
    owner: str | None
    runs: list[RunResult]

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def grade_response(case: dict, resp: BotResponse, wh: Warehouse, model: dict,
                   reference_rows, run: int = 0, judge=None) -> RunResult:
    acceptable = case.get("acceptable_behaviors") or [case["expected_behavior"]]
    base = dict(run=run, action=resp.action, interpretation=resp.interpretation,
                sql=resp.sql, injected=list(resp.injected))

    if resp.action == "error":
        return RunResult(**base, passed=False, failed_check="bot_error",
                         reason=resp.error or "bot error", owner="app", signature="error")

    if resp.action in ABSTAIN:
        sig = f"abstain:{resp.action}"
        if resp.action in acceptable:
            return RunResult(**base, passed=True, failed_check=None, reason="", owner=None, signature=sig)
        reason = (f"{resp.action} on an answerable question" if case["expected_behavior"] == "answer"
                  else f"{resp.action}; should {case['expected_behavior']}")
        return RunResult(**base, passed=False, failed_check="behavior", owner="prompt", signature=sig,
                         reason=reason)

    # The bot answered. Screen before executing: never run a write or a file read.
    unsafe = policy.check_safety(resp.sql)
    if unsafe:
        f = unsafe[0]
        return RunResult(**base, passed=False, failed_check="safety", owner=f.owner,
                         findings=[asdict(x) for x in unsafe], signature="answer:blocked",
                         reason=f"{f.rule}: {f.detail}")

    qr = wh.run(resp.sql)
    sig = "answer:" + fingerprint(qr.rows, ordered=case.get("compare") == "top_n_ordered")
    access = policy.check_access(resp.sql, model)
    cost = policy.check_cost(resp.sql, qr.rows_scanned, case, model)
    findings = rules.check(case["question"], resp.sql, model, truncated=qr.truncated)
    fdicts = [asdict(f) for f in access + findings + cost]
    base.update(rows_scanned=qr.rows_scanned)

    if "answer" not in acceptable:
        return RunResult(**base, passed=False, failed_check="behavior", owner="prompt",
                         findings=fdicts, signature=sig,
                         reason=f"answered; should {case['expected_behavior']}")
    if qr.error:
        return RunResult(**base, passed=False, failed_check="result", owner="prompt",
                         findings=fdicts, signature=sig, reason=f"SQL error: {qr.error}")
    ok, why = compare(reference_rows, qr.rows, case["compare"], case.get("tolerance", 0))
    base.update(result_correct=ok)
    if judge is not None:
        verdict = judge(case["question"], resp.interpretation, resp.sql or "")
        if verdict.get("error"):
            # Fail closed: an unavailable judge must never read as a clean verdict.
            return RunResult(**base, passed=False, failed_check="judge_unavailable", owner="app",
                             findings=fdicts, signature=sig, reason=f"judge: {verdict['error']}")
        if verdict.get("substitution") or not verdict.get("answers_question", True):
            return RunResult(**base, passed=False, failed_check="behavior", owner="prompt",
                             findings=fdicts, signature=sig,
                             reason=f"judge: {verdict.get('reason', 'answered a different question')}")
    # Reading restricted data fails the answer even when the number is right.
    if access:
        f = access[0]
        return RunResult(**base, passed=False, failed_check="access", owner=f.owner,
                         findings=fdicts, signature=sig, reason=f"{f.rule}: {f.detail}")
    blocking = [f for f in findings if f.blocking]
    if blocking:
        f = blocking[0]
        return RunResult(**base, passed=False, failed_check="sql_rule", owner=f.owner,
                         findings=fdicts, signature=sig, reason=f"{f.rule}: {f.detail}")
    if not ok:
        advisory = [f for f in findings if not f.blocking]
        if advisory:
            why += f" ({advisory[0].rule}: {advisory[0].detail})"
        return RunResult(**base, passed=False, failed_check="result", owner="prompt",
                         findings=fdicts, signature=sig, reason=why)
    # Right answer; was it affordable?
    if cost:
        f = cost[0]
        return RunResult(**base, passed=False, failed_check="cost", owner=f.owner,
                         findings=fdicts, signature=sig, reason=f"{f.rule}: {f.detail}")
    return RunResult(**base, passed=True, failed_check=None, reason="", owner=None,
                     findings=fdicts, signature=sig)


def grade_case(case: dict, bot: Bot, wh: Warehouse, model: dict, n_runs: int = 3,
               judge=None) -> CaseResult:
    reference = wh.run(case["reference_sql"]).rows if case.get("reference_sql") else None
    runs = [grade_response(case, bot.ask(case["question"], run=r), wh, model, reference,
                           run=r, judge=judge)
            for r in range(n_runs)]
    return aggregate(case, runs)


def aggregate(case: dict, runs: list[RunResult]) -> CaseResult:
    """Combine repeated runs into one case verdict, independent of run order.

    pass/fail: majority vote over the runs' own verdicts; a tie fails.
    agreement: share of runs giving the most common user-visible answer.
    representative: the earliest run that matches both the majority verdict and,
    if possible, the most common answer, so its reason explains the verdict.
    """
    n_pass = sum(r.passed for r in runs)
    passed = n_pass * 2 > len(runs)
    counts = Counter(r.signature for r in runs)
    top_n = max(counts.values())
    top_sigs = {s for s, c in counts.items() if c == top_n}
    agree = [r for r in runs if r.passed == passed]
    rep = next((r for r in agree if r.signature in top_sigs), agree[0])
    return CaseResult(case_id=case["id"], question=case["question"], category=case["category"],
                      expected_behavior=case["expected_behavior"],
                      cost_weight=case.get("cost_weight", 1), passed=passed,
                      answered=rep.action == "answer", agreement=top_n / len(runs),
                      failed_check=rep.failed_check, reason=rep.reason, owner=rep.owner, runs=runs)


def grade_suite(cases: list[dict], bot: Bot, wh: Warehouse, model: dict,
                n_runs: int = 3, judge=None) -> list[CaseResult]:
    if hasattr(bot, "phase"):
        bot.phase = "cases"
    out = []
    for i, c in enumerate(cases, 1):
        out.append(grade_case(c, bot, wh, model, n_runs, judge))
        if getattr(bot, "verbose", False):
            r = out[-1]
            print(f"  [{i}/{len(cases)}] {c['id']} {'PASS' if r.passed else 'FAIL'} "
                  f"{r.runs[0].action} {r.reason[:80]}", flush=True)
    return out


def summarize(results: list[CaseResult]) -> dict:
    n = len(results)
    answerable = [r for r in results if r.expected_behavior == "answer"]
    abstain = [r for r in results if r.expected_behavior != "answer"]
    answered = [r for r in results if r.answered]
    wrong_answers = [r for r in answered if not r.passed]
    confident_wrong = [r for r in wrong_answers if r.agreement == 1.0]
    return {
        "cases": n,
        "pass_rate": sum(r.passed for r in results) / n if n else 0.0,
        "accuracy_on_answerable": (sum(r.passed for r in answerable) / len(answerable)) if answerable else None,
        "correct_abstention_rate": (sum(r.passed for r in abstain) / len(abstain)) if abstain else None,
        "answered": len(answered),
        "wrong_answers": len(wrong_answers),
        # The metric this project argues for: wrong answers given identically on every run.
        "confident_wrong_rate": len(confident_wrong) / len(answered) if answered else 0.0,
        "substitution_rate": (sum(any(f["rule"] == "ungrounded_filter_value" for run in r.runs
                                      for f in run.findings) for r in answered) / len(answered))
                             if answered else 0.0,
        "unstable_cases": sum(r.agreement < 1.0 for r in results),
        "judge_unavailable_runs": sum(run.failed_check == "judge_unavailable"
                                      for r in results for run in r.runs),
        **trust_summary(results),
        "failures_by_owner": dict(Counter(r.owner for r in results if not r.passed)),
        "failures_by_check": dict(Counter(r.failed_check for r in results if not r.passed)),
    }


def trust_summary(results: list[CaseResult]) -> dict:
    """How answers were produced, over every run that answered.

    right_answer_wrong_way counts runs whose result matched the reference but
    that still failed a trust check: the failures a result-only eval passes.
    """
    runs = [run for r in results for run in r.runs if run.action == "answer"]
    rules_hit = [{f["rule"] for f in run.findings} for run in runs]
    scanned = sorted(run.rows_scanned for run in runs if run.rows_scanned is not None)
    right = [run for run in runs if run.result_correct]
    return {
        "answer_runs": len(runs),
        "unsafe_sql_runs": sum(run.failed_check == "safety" for run in runs),
        "restricted_access_runs": sum("restricted_column_access" in h for h in rules_hit),
        "over_budget_runs": sum("over_scan_budget" in h for h in rules_hit),
        "right_answer_wrong_way": sum(run.failed_check in TRUST_CHECKS for run in right),
        "right_answer_wrong_way_rate": (sum(run.failed_check in TRUST_CHECKS for run in right)
                                        / len(right)) if right else 0.0,
        "median_rows_scanned": scanned[len(scanned) // 2] if scanned else None,
        "max_rows_scanned": scanned[-1] if scanned else None,
    }
