"""Record a real bot's responses, and replay them later.

Real-model runs are slow and not perfectly reproducible. Recording every raw
response means a fix to the grader can be re-applied to an old run without
calling the model again, and anyone can re-grade a published run themselves.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .base import BotResponse


class RecordingBot:
    def __init__(self, inner, path: str | Path):
        self.inner = inner
        self.name = inner.name
        self.verbose = getattr(inner, "verbose", False)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")

    def ask(self, question: str, run: int = 0) -> BotResponse:
        resp = self.inner.ask(question, run=run)
        with self.path.open("a") as fh:
            fh.write(json.dumps({"bot": self.name, "question": question, "run": run,
                                 **asdict(resp)}) + "\n")
        return resp


class ReplayBot:
    def __init__(self, path: str | Path):
        self.responses: dict[tuple[str, int], BotResponse] = {}
        self.name = "replay"
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            self.name = d.pop("bot", self.name)
            key = (d.pop("question"), d.pop("run"))
            self.responses[key] = BotResponse(**d)
        self.name = f"{self.name} (replayed)"

    def ask(self, question: str, run: int = 0) -> BotResponse:
        resp = self.responses.get((question, run))
        if resp is None:
            return BotResponse("error", error="no recorded response for this question and run")
        return resp
