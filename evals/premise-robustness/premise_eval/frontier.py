"""Explicitly enabled, metered Claude Messages transport for judge experiments."""
from __future__ import annotations

import json
import os
import math
from decimal import Decimal
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class FrontierBlocked(RuntimeError):
    """Credential, approval, budget or transport failure; never a grading retry."""


class AnthropicBackend:
    def __init__(self, model='claude-sonnet-5-5', timeout=120, *, allow_paid=False,
                 budget_usd=5, max_calls=204, ledger_path=None):
        if model != 'claude-sonnet-5-5':
            raise ValueError('This experiment prices and supports only claude-sonnet-5-5')
        self.model, self.timeout, self.allow_paid = model, timeout, allow_paid
        self.budget = Decimal(str(budget_usd))
        if not self.budget.is_finite() or not 0 < self.budget <= 5:
            raise ValueError('Budget must be positive and at most USD 5')
        if type(max_calls) is not int or not 1 <= max_calls <= 204:
            raise ValueError('Call limit must be an integer from 1 to 204')
        self.max_calls = max_calls
        self._identity = None
        self._charged = Decimal('0')
        self._actual = Decimal('0')
        self.calls = []
        self.ledger_path = Path(ledger_path) if ledger_path else None
        if self.ledger_path and self.ledger_path.exists():
            record = json.loads(self.ledger_path.read_text())
            if record.get('model') != self.model or Decimal(str(record['budget_usd'])) != self.budget:
                raise FrontierBlocked('Existing usage ledger has a different model or budget')
            self._charged = Decimal(str(record['charged_or_reserved_usd']))
            self._actual = Decimal(str(record['actual_cost_usd']))
            self.calls = record['calls']
            if not self._charged.is_finite() or not 0 <= self._charged <= self.budget:
                raise FrontierBlocked('Existing usage ledger is invalid')

    def _save_ledger(self):
        if self.ledger_path is None:
            raise FrontierBlocked('Persistent usage ledger is required before paid calls')
        self.ledger_path.parent.mkdir(parents=True,exist_ok=True)
        temporary = self.ledger_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(self.statistics(), model=self.model),indent=2)+'\n')
        temporary.chmod(0o600)
        temporary.replace(self.ledger_path)

    def _authorize(self):
        if not self.allow_paid:
            raise FrontierBlocked('Paid API calls require explicit --allow-paid; ' +
                ('API key is available' if os.environ.get('ANTHROPIC_API_KEY') else 'ANTHROPIC_API_KEY is also unavailable'))
        if not os.environ.get('ANTHROPIC_API_KEY'):
            raise FrontierBlocked('ANTHROPIC_API_KEY is not available; configure it securely, never in reports')

    def _request(self, path, payload=None):
        self._authorize()
        request = Request('https://api.anthropic.com/v1/' + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'anthropic-version': '2023-06-01',
                     'x-api-key': os.environ['ANTHROPIC_API_KEY']})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            # Never propagate provider bodies, headers or request objects containing secrets.
            raise FrontierBlocked('Claude API returned HTTP ' + str(exc.code)) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise FrontierBlocked('Claude API transport or JSON response failed; no automatic transport retry') from None

    def identity(self):
        self._authorize()
        metadata = self._request('models/' + self.model)
        if metadata.get('id') != self.model or not metadata.get('created_at'):
            raise FrontierBlocked('Claude Models API did not confirm the configured model identity')
        identity = dict(backend='anthropic', model=metadata['id'], created_at=metadata['created_at'],
            temperature='provider_default_only', seed=None, max_tokens=512,
            thinking='between_tools', effort='high', api_version='2023-06-01',
            input_usd_per_million=2, output_usd_per_million=10,
            identity_limit='Provider model ID and metadata, not an independently verifiable weights digest')
        if self._identity is not None and identity != self._identity:
            raise FrontierBlocked('Claude model identity changed during the experiment')
        self._identity = identity
        return dict(identity)

    def statistics(self):
        return dict(budget_usd=float(self.budget), actual_cost_usd=float(self._actual),
            charged_or_reserved_usd=float(self._charged), calls=self.calls,
            cost_note='Client reservation guard at configured prices, not a provider billing guarantee. '
                      'Unknown transport costs retain full reservation. No cache discounts assumed.')

    @staticmethod
    def _tokens(value):
        if type(value) is not int or value < 0:
            raise FrontierBlocked('Claude usage/token-count metadata is invalid')
        return value

    def complete(self, messages, schema):
        self._authorize()
        if self._identity is None:
            self.identity()
        if len(self.calls) >= self.max_calls:
            raise FrontierBlocked('Claude API call limit reached')
        if not messages or messages[0]['role'] != 'system':
            raise ValueError('Judge requires exactly one leading system message')
        if any(m['role'] not in {'user', 'assistant'} for m in messages[1:]):
            raise ValueError('Unexpected judge message role')
        body = dict(model=self.model, system=messages[0]['content'], messages=messages[1:],
            max_tokens=512, thinking={'type': 'between_tools'},
            output_config={'effort': 'high', 'format': {'type': 'json_schema', 'schema': schema}})
        counted = self._request('messages/count_tokens', {k:body[k] for k in ('model','system','messages')})
        tokens = self._tokens(counted.get('input_tokens'))
        # Count endpoint omits schema and can be approximate. Reserve margin plus schema bytes.
        reserve_input = math.ceil(tokens * 1.1) + len(json.dumps(schema).encode()) + 1024
        reserve = (Decimal(reserve_input)*2 + Decimal(512)*10) / Decimal(1000000)
        if self._charged + reserve > self.budget:
            raise FrontierBlocked('Claude API budget would be exceeded; no generation request sent')
        self._charged += reserve
        record = dict(attempt=len(self.calls)+1, reserved_usd=float(reserve), status='reserved')
        self.calls.append(record)
        self._save_ledger()
        result = self._request('messages', body)
        usage = result.get('usage', {})
        in_tokens = self._tokens(usage.get('input_tokens'))
        out_tokens = self._tokens(usage.get('output_tokens'))
        cache_write = self._tokens(usage.get('cache_creation_input_tokens', 0))
        cache_read = self._tokens(usage.get('cache_read_input_tokens', 0))
        # Full price for cache reads and maximum documented 1h-write multiplier; conservative.
        actual = (Decimal(in_tokens+cache_read)*2 + Decimal(cache_write)*4 + Decimal(out_tokens)*10) / Decimal(1000000)
        self._actual += actual
        self._charged += actual - reserve
        record.update(status='received', usage=dict(input_tokens=in_tokens,output_tokens=out_tokens,
            cache_creation_input_tokens=cache_write,cache_read_input_tokens=cache_read),
            cost_usd=float(actual), stop_reason=result.get('stop_reason'), model=result.get('model'))
        self._save_ledger()
        if self._charged > self.budget:
            raise FrontierBlocked('Usage exceeded reserved budget; stop and inspect accounting')
        if result.get('model') != self.model:
            raise FrontierBlocked('Claude response model differs from the confirmed model')
        if result.get('stop_reason') not in {'end_turn'}:
            raise ValueError('Claude did not complete a judgment: ' + str(result.get('stop_reason')))
        content = result.get('content', [])
        if not isinstance(content, list) or len(content) != 1 or content[0].get('type') != 'text':
            raise ValueError('Claude returned unexpected content blocks')
        if not isinstance(content[0].get('text'), str):
            raise ValueError('Claude returned no judgment text')
        return content[0]['text']
