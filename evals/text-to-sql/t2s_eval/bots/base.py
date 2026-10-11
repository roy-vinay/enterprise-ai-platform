"""The interface every bot adapter implements."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class BotResponse:
    action: str                      # answer | clarify | refuse
    interpretation: str = ""         # the bot's restatement of the question
    sql: str | None = None           # SQL it ran, when it answered
    message: str = ""                # clarifying question or refusal text
    injected: list[str] = field(default_factory=list)  # simulated bot only: ground-truth faults
    error: str | None = None


class Bot(Protocol):
    name: str

    def ask(self, question: str, run: int = 0) -> BotResponse:
        """Answer one question. `run` lets a bot vary across repeated runs."""
        ...
