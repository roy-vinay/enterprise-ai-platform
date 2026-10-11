"""Grade bot responses: behavior, result, and SQL rules, with owner routing."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

from . import rules
from .bots.base import Bot, BotResponse
from .db import Warehouse, compare, fingerprint

ABSTAIN = ("clarify", "refuse")


@dataclass
class RunResult:
    run: int
    action: str
    interpretation: str
    sql: str | None
    passed: bool
    failed_check: str | None      # behavior | sql_rule | result | bot_error | None
    reason: str
    owner: str | None             # semantic_model | prompt | app
    findings: list[dict] = field(default_factory=list)
    injected: list[str] = field(default_factory=list)
    signature: str = ""           # (action, result) fingerprint for agreement


@dataclass
class CaseResult:
    case_id: str
    question: str
    category: str
    expected_behavior: str
    cost_weight: int
    passed: bool                  # majority-vote outcome
    answered: bool                # majority action was an answer
    confidence: float             # share of runs that agree with the majority
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
        return RunResult(**base, passed=False, failed_check="behavior", owner="prompt", signature=sig,
                         reason=f"{resp.action} on an answerable question")

    # The bot answered.
    qr = wh.run(resp.sql)
    sig = "answer:" + fingerprint(qr.rows)
    findings = rules.check(case["question"], resp.sql, model, truncated=qr.truncated)
    fdicts = [asdict(f) for f in findings]

    if "answer" not in acceptable:
        return RunResult(**base, passed=False, failed_check="behavior", owner="prompt",
                         findings=fdicts, signature=sig,
                         reason=f"answered; should {case['expected_behavior']}")
    if qr.error:
        return RunResult(**base, passed=False, failed_check="result", owner="prompt",
                         findings=fdicts, signature=sig, reason=f"SQL error: {qr.error}")
    if judge is not None:
        verdict = judge(case["question"], resp.interpretation, resp.sql or "")
        if verdict.get("substitution") or not verdict.get("answers_question", True):
            return RunResult(**base, passed=False, failed_check="behavior", owner="prompt",
                             findings=fdicts, signature=sig,
                             reason=f"judge: {verdict.get('reason', 'answered a different question')}")
    if findings:
        f = findings[0]
        return RunResult(**base, passed=False, failed_check="sql_rule", owner=f.owner,
                         findings=fdicts, signature=sig, reason=f"{f.rule}: {f.detail}")
    ok, why = compare(reference_rows, qr.rows, case["compare"], case.get("tolerance", 0))
    if not ok:
        return RunResult(**base, passed=False, failed_check="result", owner="prompt",
                         findings=fdicts, signature=sig, reason=why)
    return RunResult(**base, passed=True, failed_check=None, reason="", owner=None,
                     findings=fdicts, signature=sig)


def grade_case(case: dict, bot: Bot, wh: Warehouse, model: dict, n_runs: int = 3,
               judge=None) -> CaseResult:
    reference = wh.run(case["reference_sql"]).rows if case.get("reference_sql") else None
    runs = [grade_response(case, bot.ask(case["question"], run=r), wh, model, reference,
                           run=r, judge=judge)
            for r in range(n_runs)]
    counts = Counter(r.signature for r in runs)
    top_sig, top_n = counts.most_common(1)[0]
    rep = next(r for r in runs if r.signature == top_sig)  # representative of the majority
    return CaseResult(case_id=case["id"], question=case["question"], category=case["category"],
                      expected_behavior=case["expected_behavior"],
                      cost_weight=case.get("cost_weight", 1), passed=rep.passed,
                      answered=rep.action == "answer", confidence=top_n / n_runs,
                      failed_check=rep.failed_check, reason=rep.reason, owner=rep.owner, runs=runs)


def grade_suite(cases: list[dict], bot: Bot, wh: Warehouse, model: dict,
                n_runs: int = 3, judge=None) -> list[CaseResult]:
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
    confident_wrong = [r for r in wrong_answers if r.confidence == 1.0]
    return {
        "cases": n,
        "pass_rate": sum(r.passed for r in results) / n if n else 0.0,
        "accuracy_on_answerable": (sum(r.passed for r in answerable) / len(answerable)) if answerable else None,
        "correct_abstention_rate": (sum(r.passed for r in abstain) / len(abstain)) if abstain else None,
        "answered": len(answered),
        "wrong_answers": len(wrong_answers),
        # The metric this project argues for: wrong answers delivered with full self-agreement.
        "confident_wrong_rate": len(confident_wrong) / len(answered) if answered else 0.0,
        "substitution_rate": (sum(any(f["rule"] == "ungrounded_filter_value" for run in r.runs
                                      for f in run.findings) for r in answered) / len(answered))
                             if answered else 0.0,
        "unstable_cases": sum(r.confidence < 1.0 for r in results),
        "failures_by_owner": dict(Counter(r.owner for r in results if not r.passed)),
        "failures_by_check": dict(Counter(r.failed_check for r in results if not r.passed)),
    }
