"""Record a real bot's responses, and replay them later.

Real-model runs are slow and not perfectly reproducible. Recording every raw
response means a fix to the grader can be re-applied to an old run without
calling the model again, and anyone can re-grade a published run themselves.

The same question can be asked more than once with the same run number (the
graded cases and the metamorphic relations both ask it), and a live model can
answer differently each time. So every call is recorded with its phase and a
sequence number, and replay hands back each recorded response exactly once,
in the order it was recorded. Nothing is overwritten.
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import asdict
from pathlib import Path

from .base import BotResponse


class RecordingBot:
    def __init__(self, inner, path: str | Path):
        self.inner = inner
        self.name = inner.name
        self.verbose = getattr(inner, "verbose", False)
        self.phase = ""
        self.seq = 0
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")

    def ask(self, question: str, run: int = 0) -> BotResponse:
        resp = self.inner.ask(question, run=run)
        with self.path.open("a") as fh:
            fh.write(json.dumps({"seq": self.seq, "phase": self.phase, "bot": self.name,
                                 "question": question, "run": run, **asdict(resp)}) + "\n")
        self.seq += 1
        return resp


class ReplayBot:
    def __init__(self, path: str | Path):
        self.phase = ""
        self.name = "replay"
        self.queues: dict[tuple, deque] = defaultdict(deque)
        rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
        rows.sort(key=lambda d: d.get("seq", 0))
        for d in rows:
            self.name = d.pop("bot", self.name)
            d.pop("seq", None)
            phase = d.pop("phase", "")
            self.queues[(phase, d.pop("question"), d.pop("run"))].append(BotResponse(**d))
        self.name = f"{self.name} (replayed)"

    def ask(self, question: str, run: int = 0) -> BotResponse:
        # Older recordings have no phase; fall back to the phase-less queue.
        for key in ((self.phase, question, run), ("", question, run)):
            q = self.queues.get(key)
            if q:
                return q.popleft()
        return BotResponse("error", error="no unused recorded response for this question and run")

    def unused(self) -> int:
        return sum(len(q) for q in self.queues.values())
