"""Local judge transport. No keys, downloads, or paid calls."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parent.parent


class ModelBackend(ABC):
    @abstractmethod
    def complete(self, messages: list[dict], schema: dict) -> str:
        """Return the model's JSON text."""

    @abstractmethod
    def identity(self) -> dict:
        """Return the pinned model identity."""


class OllamaBackend(ModelBackend):
    def __init__(self, model='qwen3:8b-q4_K_M', url='http://127.0.0.1:11434', timeout=120):
        parsed = urlparse(url)
        if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Ollama must use a local HTTP endpoint')
        if ':' not in model or model.endswith(':latest'):
            raise ValueError('Use an explicit model tag, not latest')
        self.model, self.url, self.timeout = model, url.rstrip('/'), timeout
        self._identity = None

    def _request(self, path, payload=None):
        request = Request(self.url + path, data=None if payload is None else json.dumps(payload).encode(),
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def identity(self):
        matches = [m for m in self._request('/api/tags').get('models', [])
                   if m.get('name') == self.model or m.get('model') == self.model]
        if len(matches) != 1 or not matches[0].get('digest'):
            raise ValueError(f'Install and pin local model {self.model} before judging')
        identity = dict(backend='ollama', model=self.model, digest=matches[0]['digest'],
                        temperature=0, seed=17, num_ctx=8192, num_predict=512, think=False)
        if self._identity is not None and identity != self._identity:
            raise ValueError('Local model digest changed during the run')
        self._identity = identity
        return dict(identity)

    def complete(self, messages, schema):
        self.identity()
        result = self._request('/api/chat', dict(model=self.model, messages=messages,
            format=schema, stream=False, think=False,
            options=dict(temperature=0, seed=17, num_ctx=8192, num_predict=512)))
        if result.get('done') is not True or not isinstance(result.get('message', {}).get('content'), str):
            raise ValueError('Incomplete Ollama response')
        self.identity()
        return result['message']['content']


class ApiBackend(ModelBackend):
    def identity(self):
        raise NotImplementedError('Frontier API backend is reserved for milestone 5')

    def complete(self, messages, schema):
        raise NotImplementedError('No paid API backend is wired')


def load_backend(path=None):
    config = yaml.safe_load(Path(path or ROOT / 'validation/judge-config.yaml').read_text())
    if config['backend'] == 'ollama':
        return OllamaBackend(model=config['model'], url=config['url'], timeout=config['timeout'])
    if config['backend'] == 'api':
        return ApiBackend()
    raise ValueError('Unknown judge backend')
