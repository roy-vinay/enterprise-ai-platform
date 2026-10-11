"""Adapter for a real model served locally by Ollama (free, no API key).

    ollama pull qwen2.5-coder:7b
    python -m t2s_eval.cli run --bot ollama --model qwen2.5-coder:7b

Any bot with an HTTP API can be wrapped the same way: implement ask() and
return a BotResponse. For a hosted text-to-SQL service, call its API
and map its interpretation, SQL and suggestions onto these fields.
"""
from __future__ import annotations

import json
import os
import urllib.request

from .. import data, semantic
from .base import BotResponse

SYSTEM = """You are a BI assistant answering business questions over a DuckDB warehouse.
Use only the tables, metrics and dimensions described below. Follow metric definitions exactly.

{context}

Schema:
{ddl}

Decide one action:
- "answer": the question is answerable with this data. Write one DuckDB SELECT query.
- "clarify": the question is ambiguous or uses a term that does not match the data. Ask one question.
- "refuse": the data cannot answer it (see "Not in the warehouse"), or it asks for a forecast.

Never substitute a different metric, filter value or time window than the one asked for.
Respond with JSON only:
{{"action": "answer|clarify|refuse", "interpretation": "...", "sql": "... or null", "message": "..."}}"""


class OllamaBot:
    def __init__(self, model_def: dict, model: str = "qwen2.5-coder:7b",
                 host: str | None = None, temperature: float = 0.7, timeout: int = 180):
        self.name = f"ollama-{model}"
        self.llm = model
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.temperature = temperature  # >0 so repeated runs can disagree (self-consistency)
        self.timeout = timeout
        self.verbose = True  # print per-case progress; real models are slow
        self.system = SYSTEM.format(context=semantic.prompt_context(model_def),
                                    ddl=data.schema_ddl())

    def ask(self, question: str, run: int = 0) -> BotResponse:
        body = {"model": self.llm, "stream": False, "format": "json",
                "options": {"temperature": self.temperature, "seed": run},
                "messages": [{"role": "system", "content": self.system},
                             {"role": "user", "content": question}]}
        req = urllib.request.Request(f"{self.host}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                content = json.loads(r.read())["message"]["content"]
            out = json.loads(content)
        except Exception as e:  # network, timeout or malformed JSON
            return BotResponse("error", error=f"{type(e).__name__}: {e}")
        action = str(out.get("action", "")).lower().strip()
        if action not in ("answer", "clarify", "refuse"):
            return BotResponse("error", error=f"unknown action {action!r}")
        return BotResponse(action, interpretation=out.get("interpretation") or "",
                           sql=out.get("sql") if action == "answer" else None,
                           message=out.get("message") or "")
