"""Selective answering: when should a BI bot stay quiet?

Accuracy alone hides the real trade-off. A bot can answer fewer questions and be
right far more often on the ones it answers. We use run-to-run agreement as the
abstention signal (ask N times; agreement is the share of runs that give the most
common answer), then sweep a threshold below which the bot abstains:

  coverage   share of all questions the bot still answers
  risk       share of those answers that are wrong
  cost       business-weighted cost of every outcome (see below)

Agreement is a coarse consistency signal, not a calibrated probability of being
right: with three runs it can only take the values 1/3, 2/3 and 1, and a bot that
is wrong the same way every time scores full agreement.

Cost model (per question)
  answered and right               0
  answered and wrong               cost_weight (1 to 5, set per case in the trap set)
  abstained, should have answered  abstain_cost (an analyst follows up)
  abstained, should have abstained 0

The sweep always includes two endpoints: threshold 0 (answer whenever the bot
chose to answer) and ABSTAIN_ALL (never answer).

Choosing the threshold on the same cases it is reported on overstates how well
it works. `holdout()` picks the threshold on one half of the cases and reports
its cost on the other half, both ways round. With a trap set this small, treat
the result as exploratory.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .grade import CaseResult

ABSTAIN_ALL = float("inf")


@dataclass
class Point:
    threshold: float     # answer only if agreement >= threshold; inf = abstain on everything
    coverage: float
    risk: float          # wrong / answered
    accuracy: float      # right / answered
    answered: int
    wrong: int
    cost: float

    @property
    def label(self) -> str:
        return "abstain all" if self.threshold == ABSTAIN_ALL else f"{self.threshold:.2f}"


def _point(results: list[CaseResult], t: float, abstain_cost: float) -> Point:
    n = len(results)
    answered = [r for r in results if r.answered and r.agreement >= t]
    wrong = [r for r in answered if not r.passed]
    cost = sum(r.cost_weight for r in wrong)
    cost += sum(abstain_cost for r in results
                if not (r.answered and r.agreement >= t) and r.expected_behavior == "answer")
    a = len(answered)
    return Point(t, a / n if n else 0.0, len(wrong) / a if a else 0.0,
                 1 - len(wrong) / a if a else 1.0, a, len(wrong), cost)


def sweep(results: list[CaseResult], abstain_cost: float = 1.0) -> list[Point]:
    thresholds = sorted({0.0} | {r.agreement for r in results}) + [ABSTAIN_ALL]
    return [_point(results, t, abstain_cost) for t in thresholds]


def best(points: list[Point]) -> Point:
    """Lowest cost; ties go to higher coverage."""
    return min(points, key=lambda p: (p.cost, -p.coverage))


def split(results: list[CaseResult]) -> tuple[list[CaseResult], list[CaseResult]]:
    """Stable two-way split by hashed case id, stratified by expected behavior."""
    a, b = [], []
    for behavior in sorted({r.expected_behavior for r in results}):
        group = sorted((r for r in results if r.expected_behavior == behavior),
                       key=lambda r: hashlib.sha256(r.case_id.encode()).hexdigest())
        for i, r in enumerate(group):
            (a if i % 2 == 0 else b).append(r)
    return a, b


def holdout(results: list[CaseResult], abstain_cost: float = 1.0) -> list[dict]:
    """Pick the threshold on one half, report it on the other, both ways round."""
    a, b = split(results)
    out = []
    for name, dev, test in (("A->B", a, b), ("B->A", b, a)):
        chosen = best(sweep(dev, abstain_cost)).threshold
        on_test = _point(test, chosen, abstain_cost)
        baseline = _point(test, 0.0, abstain_cost)
        out.append({"fold": name, "dev_cases": len(dev), "test_cases": len(test),
                    "threshold": chosen, "test_cost": on_test.cost,
                    "test_cost_answer_all": baseline.cost,
                    "test_coverage": on_test.coverage, "test_wrong": on_test.wrong})
    return out


def plot(curves: dict[str, list[Point]], path: str) -> str:
    """Two panels: accuracy vs coverage, and expected cost vs threshold."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, ink, muted, grid = "#fcfcfb", "#1f1e1d", "#6b6a63", "#e6e5e0"
    series = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # fixed categorical order

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4), dpi=150, facecolor=surface)
    for ax in (ax1, ax2):
        ax.set_facecolor(surface)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(grid)
        ax.tick_params(colors=muted, labelsize=8)
        ax.grid(True, color=grid, linewidth=0.6)
        ax.set_axisbelow(True)

    x_all = 1.15  # where "abstain all" sits on the threshold axis
    for (name, pts), color in zip(curves.items(), series):
        answered = sorted((p for p in pts if p.answered), key=lambda p: p.coverage)
        ax1.plot([p.coverage * 100 for p in answered], [p.accuracy * 100 for p in answered],
                 color=color, linewidth=2, marker="o", markersize=5, label=name)
        pts_t = sorted(pts, key=lambda p: p.threshold)
        xs = [x_all if p.threshold == ABSTAIN_ALL else p.threshold for p in pts_t]
        ax2.plot(xs, [p.cost for p in pts_t], color=color, linewidth=2, marker="o",
                 markersize=5, label=name)
        b = best(pts)
        bx = x_all if b.threshold == ABSTAIN_ALL else b.threshold
        ax2.annotate("lowest", (bx, b.cost), textcoords="offset points", xytext=(0, 8),
                     ha="center", fontsize=7, color=ink)

    ax1.set_title("Accuracy of answers vs. share of questions answered", fontsize=9, color=ink, loc="left")
    ax1.set_xlabel("Coverage (% of questions answered)", fontsize=8, color=muted)
    ax1.set_ylabel("Accuracy of answers (%)", fontsize=8, color=muted)
    ax2.set_title("Business-weighted cost vs. agreement threshold (in-sample)", fontsize=9,
                  color=ink, loc="left")
    ax2.set_xlabel("Answer only if run-to-run agreement ≥ threshold", fontsize=8, color=muted)
    ax2.set_ylabel("Cost (weighted errors + follow-ups)", fontsize=8, color=muted)
    ticks = [0, 0.25, 0.5, 0.75, 1.0]
    ax2.set_xticks(ticks + [x_all])
    ax2.set_xticklabels([f"{t:g}" for t in ticks] + ["abstain\nall"])
    if len(curves) > 1:
        ax1.legend(frameon=False, fontsize=8, labelcolor=ink)
    fig.tight_layout()
    fig.savefig(path, facecolor=surface)
    plt.close(fig)
    return path
