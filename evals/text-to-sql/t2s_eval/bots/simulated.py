"""A simulated BI bot with realistic, labeled failure modes.

Why it exists: the pipeline (grading, metamorphic checks, mutation testing,
risk-coverage analysis) should be testable in CI with no model, no GPU and
no API key. The simulator also knows exactly which fault it injected into each
answer, which gives ground-truth labels for validating the judge.

Failure model. Real bots are not randomly wrong; they tend to be wrong on the
same questions again and again, which is why self-consistency alone cannot
catch everything. Each fault therefore combines a per-question tendency
(fixed across runs) with per-run noise:

    fault if  consistency * u_question + (1 - consistency) * u_run  <  p

Numbers produced with this bot describe the simulator, not any real system.
Use the Ollama adapter for real measurements.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from .. import semantic
from .base import BotResponse

ORACLE = Path(__file__).with_name("sim_oracle.yaml")

PROFILES = {
    # A bot that always produces a number: over-answers, substitutes, slips on dates.
    "overconfident": dict(p_overanswer=0.65, p_tempt=0.35, p_date=0.5,
                          p_drop_test=0.15, consistency=0.6, clarify_ambiguous=False),
    # A well-prompted bot: mostly asks or refuses when it should.
    "careful": dict(p_overanswer=0.12, p_tempt=0.10, p_date=0.08,
                    p_drop_test=0.03, consistency=0.75, clarify_ambiguous=True),
    # Perfect behavior; used in tests to prove the grader passes a correct bot.
    "perfect": dict(p_overanswer=0.0, p_tempt=0.0, p_date=0.0,
                    p_drop_test=0.0, consistency=0.0, clarify_ambiguous=False),
}

_PREFIXES = ("quick question:", "quick question", "can you tell me", "hey bot,",
             "hey bot", "i need to know", "please tell me")
_SUFFIXES = ("please", "thanks", "thank you")


def normalize(question: str) -> str:
    q = question.strip().lower().rstrip("?.! ")
    changed = True
    while changed:
        changed = False
        for p in _PREFIXES:
            if q.startswith(p):
                q, changed = q[len(p):].strip(" ,"), True
        for s in _SUFFIXES:
            if q.endswith(s):
                q, changed = q[: -len(s)].strip(" ,?"), True
    return re.sub(r"\s+", " ", q).rstrip("?.! ")


def _u(*parts) -> float:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:12], 16) / 16 ** 12


_DATE = re.compile(r"DATE '(\d{4})-(\d{2})-01'")


def _shift_month_back(sql: str) -> str:
    """Off-by-one window: every month boundary moves one month earlier."""
    def back(m):
        y, mo = int(m.group(1)), int(m.group(2))
        y, mo = (y - 1, 12) if mo == 1 else (y, mo - 1)
        return f"DATE '{y:04d}-{mo:02d}-01'"
    return _DATE.sub(back, sql)


class SimulatedBot:
    def __init__(self, model: dict, cases: list[dict], profile: str = "overconfident",
                 seed: int = 7):
        self.name = f"simulated-{profile}"
        self.model = model
        self.p = PROFILES[profile]
        self.seed = seed
        self.oracle = yaml.safe_load(ORACLE.read_text())["questions"]
        self.tempting = {c["id"]: c.get("tempting_sql") for c in cases}
        # What the case's tempting query gets wrong; the label the grader must catch.
        self.tempting_fault = {c["id"]: c.get("tempting_fault", "substitution") for c in cases}

    def _fault(self, kind: str, p: float, question: str, run: int) -> bool:
        c = self.p["consistency"]
        uq = _u(self.seed, kind, normalize(question))     # per-question tendency
        ur = _u(self.seed, kind, question, run)           # per-run noise (exact wording)
        return c * uq + (1 - c) * ur < p

    def ask(self, question: str, run: int = 0) -> BotResponse:
        entry = self.oracle.get(normalize(question))
        if entry is None:
            return BotResponse("clarify", message="I don't know how to answer that yet.")
        tempting = self.tempting.get(entry.get("case")) if entry.get("case") else None
        action = entry["action"]

        if action in ("clarify", "refuse"):
            if tempting and self._fault("overanswer", self.p["p_overanswer"], question, run):
                return BotResponse("answer", interpretation=f"(assumed) {question}",
                                   sql=tempting.strip(), injected=["overanswer"])
            return BotResponse(action, interpretation=entry["interpretation"],
                               message=entry["interpretation"])

        if entry.get("ambiguous") and self.p["clarify_ambiguous"]:
            return BotResponse("clarify", interpretation=entry["interpretation"],
                               message="Do you mean paying accounts or accounts using the product?")

        injected: list[str] = []
        if tempting and self._fault("tempt", self.p["p_tempt"], question, run):
            sql, injected = tempting.strip(), [self.tempting_fault[entry["case"]]]
        else:
            sql = semantic.render(entry["sql"], self.model)
            if entry.get("relative") and self._fault("date", self.p["p_date"], question, run):
                sql, injected = _shift_month_back(sql), injected + ["date_window"]
            if self._fault("drop_test", self.p["p_drop_test"], question, run):
                for f in self.model.get("global_filters", {}).values():
                    sql = sql.replace(f" AND {f}", "").replace(f"{f} AND ", "")
                injected.append("missing_test_filter")
        return BotResponse("answer", interpretation=entry["interpretation"], sql=sql,
                           injected=injected)
