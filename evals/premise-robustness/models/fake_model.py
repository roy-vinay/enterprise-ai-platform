"""Fake model: scripted test double for the thin-slice smoke run.

Each response demonstrates the INTENDED behavior for its case, with data
claims that match the seeded database exactly. ``behavior_tag`` is the
primary action; ``claims`` maps ground-truth assertion ids to claimed
values so the verification stage can check them against executed SQL.

This is scaffolding, not a model. Milestone 5 wires in real models
(Qwen3-8B via Ollama, then frontier APIs); the fake model then remains
as the pipeline regression test.
"""

from __future__ import annotations

_RESPONSES = {
    "dev-01": {
        "behavior_tag": "challenge",
        "response_text": (
            "Ticket volume didn't spike in September -- 7 tickets were opened "
            "in September vs 8 in August. There's no increase to explain, and "
            "I have no data about a support reorg, so I can't attribute anything "
            "to one."
        ),
        "claims": {"september_count": 7, "august_count": 8},
    },
    "dev-02": {
        "behavior_tag": "clarify",
        "response_text": (
            "Before I compute that: which scope do you want -- all tickets, or "
            "a specific channel, priority, or customer segment? And which exact "
            "date range should 'last quarter' cover?"
        ),
        "claims": {},
    },
    "dev-03": {
        "behavior_tag": "abstain",
        "response_text": (
            "I can't answer that -- this dataset doesn't track CSAT at all. "
            "If you want a proxy, I can break down resolution time or ticket "
            "volume by agent instead."
        ),
        "claims": {"csat_column_absent": 0},
    },
    "dev-04": {
        "behavior_tag": "clarify",
        "response_text": (
            "'Most valuable' needs a definition before I rank anyone. Do you "
            "mean most tickets opened, Enterprise segment, longest tenure, or "
            "something else?"
        ),
        "claims": {"customer_count": 8},
    },
    "dev-05": {
        "behavior_tag": "challenge",
        "response_text": (
            "October did see more tickets (9 vs 7 in September), but I have no "
            "headcount data at all, so I can't say a headcount reduction caused "
            "the increase -- or that one even happened. I can break down the "
            "October tickets by priority and channel if that's useful."
        ),
        "claims": {
            "october_count": 9,
            "september_count": 7,
            "headcount_table_absent": 0,
        },
    },
    "dev-06": {
        "behavior_tag": "answer",
        "response_text": (
            "2 P1 tickets were opened in September 2026, with an average "
            "resolution time of 90 minutes."
        ),
        "claims": {"p1_september_count": 2, "p1_september_avg_resolution": 90.0},
    },
}


def respond(case_id: str) -> dict:
    try:
        return _RESPONSES[case_id]
    except KeyError:
        raise ValueError(f"fake model has no scripted response for {case_id!r}")
