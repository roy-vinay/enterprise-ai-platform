"""Selective answering: when should a BI bot stay quiet?

Accuracy alone hides the real trade-off. A bot can answer fewer questions and be
right far more often on the ones it answers. We estimate confidence from
self-consistency (ask N times; confidence is the share of runs that agree with
the majority result), then sweep an abstention threshold:

  coverage   share of all questions the bot still answers
  risk       share of those answers that are wrong
  cost       business-weighted cost of every outcome (see below)

Cost model (per question)
  answered and right             0
  answered and wrong             cost_weight (1 to 5, set per case in the trap set)
  abstained, should have answered abstain_cost (an analyst follows up)
  abstained, should have abstained 0
"""
from __future__ import annotations

from dataclasses import dataclass

from .grade import CaseResult


@dataclass
class Point:
    threshold: float
    coverage: float
    risk: float          # wrong / answered
    accuracy: float      # right / answered
    answered: int
    wrong: int
    cost: float


def sweep(results: list[CaseResult], abstain_cost: float = 1.0) -> list[Point]:
    thresholds = sorted({0.0} | {r.confidence for r in results})
    n = len(results)
    points = []
    for t in thresholds:
        answered = [r for r in results if r.answered and r.confidence >= t]
        wrong = [r for r in answered if not r.passed]
        cost = sum(r.cost_weight for r in wrong)
        for r in results:
            kept = r.answered and r.confidence >= t
            if not kept and r.expected_behavior == "answer":
                cost += abstain_cost
        a = len(answered)
        points.append(Point(t, a / n if n else 0.0, len(wrong) / a if a else 0.0,
                            1 - len(wrong) / a if a else 1.0, a, len(wrong), cost))
    return points


def best(points: list[Point]) -> Point:
    """Lowest cost; ties go to higher coverage."""
    return min(points, key=lambda p: (p.cost, -p.coverage))


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

    for (name, pts), color in zip(curves.items(), series):
        pts_c = sorted(pts, key=lambda p: p.coverage)
        ax1.plot([p.coverage * 100 for p in pts_c], [p.accuracy * 100 for p in pts_c],
                 color=color, linewidth=2, marker="o", markersize=5, label=name)
        pts_t = sorted(pts, key=lambda p: p.threshold)
        ax2.plot([p.threshold for p in pts_t], [p.cost for p in pts_t],
                 color=color, linewidth=2, marker="o", markersize=5, label=name)
        b = best(pts)
        ax2.annotate(f"best {b.threshold:.1f}", (b.threshold, b.cost), textcoords="offset points",
                     xytext=(0, 8), ha="center", fontsize=7, color=ink)

    ax1.set_title("Accuracy of answers vs. share of questions answered", fontsize=9, color=ink, loc="left")
    ax1.set_xlabel("Coverage (% of questions answered)", fontsize=8, color=muted)
    ax1.set_ylabel("Accuracy of answers (%)", fontsize=8, color=muted)
    ax2.set_title("Business-weighted cost vs. abstention threshold", fontsize=9, color=ink, loc="left")
    ax2.set_xlabel("Answer only if self-consistency ≥ threshold", fontsize=8, color=muted)
    ax2.set_ylabel("Expected cost (weighted errors + follow-ups)", fontsize=8, color=muted)
    if len(curves) > 1:
        ax1.legend(frameon=False, fontsize=8, labelcolor=ink)
    fig.tight_layout()
    fig.savefig(path, facecolor=surface)
    plt.close(fig)
    return path
