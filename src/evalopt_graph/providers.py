"""LLM providers. Real SDKs are imported lazily *inside* the provider so importing this module
(and running unit tests) never requires ``anthropic`` / ``openai`` or any API key.

``MockProvider`` is fully deterministic and is the default for tests and offline smoke runs.
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete(self, system: str, prompt: str, *, tag: str | None = None, **kw) -> str:
        """Return a completion. ``tag`` lets deterministic providers branch by node intent."""
        ...


class MockProvider:
    """Deterministic provider. No network, no keys. Branches on ``tag``.

    ``score`` controls the evaluator verdict so tests can drive specific routing paths.
    """

    name = "mock"

    def __init__(self, score: float = 0.95, plan: list[str] | None = None) -> None:
        self.score = score
        self.plan = plan or [
            "Implement the smallest coherent slice toward the acceptance criteria.",
            "Add or adjust focused tests covering the new behavior.",
            "Run gates and fix the first failing one.",
        ]

    def complete(self, system: str, prompt: str, *, tag: str | None = None, **kw) -> str:
        if tag == "plan":
            return json.dumps(self.plan)
        if tag == "evaluate":
            return json.dumps(
                {"score": self.score, "feedback": f"Deterministic mock evaluation; score={self.score:.2f}."}
            )
        if tag == "reflect":
            return json.dumps(["Mock reflection: target the first failing gate; make the minimal fix."])
        return "OK (mock)"


class AnthropicProvider:
    """Anthropic Claude provider. Requires ``pip install anthropic`` and ANTHROPIC_API_KEY."""

    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8", api_key: str | None = None) -> None:
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    def _ensure(self):
        if self._client is None:
            try:
                import anthropic  # lazy import
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("anthropic SDK not installed. `uv pip install -e '.[llm]'`") from exc
            if not self._api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set.")
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(self, system: str, prompt: str, *, tag: str | None = None, **kw) -> str:
        client = self._ensure()
        msg = client.messages.create(
            model=self.model,
            max_tokens=kw.get("max_tokens", 2048),
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


class OpenAIProvider:
    """OpenAI provider. Requires ``pip install openai`` and OPENAI_API_KEY."""

    name = "openai"

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None) -> None:
        self.model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None

    def _ensure(self):
        if self._client is None:
            try:
                import openai  # lazy import
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("openai SDK not installed. `uv pip install -e '.[llm]'`") from exc
            if not self._api_key:
                raise RuntimeError("OPENAI_API_KEY is not set.")
            self._client = openai.OpenAI(api_key=self._api_key)
        return self._client

    def complete(self, system: str, prompt: str, *, tag: str | None = None, **kw) -> str:
        client = self._ensure()
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""


def get_provider(name: str = "mock", **kw) -> LLMProvider:
    """Factory. Defaults to the deterministic mock so nothing requires an API key by default."""
    name = (name or "mock").lower()
    if name == "mock":
        return MockProvider(**kw)
    if name == "anthropic":
        return AnthropicProvider(**kw)
    if name == "openai":
        return OpenAIProvider(**kw)
    raise ValueError(f"unknown provider: {name!r} (use mock|anthropic|openai)")


def parse_json_blob(text: str) -> dict | None:
    """Best-effort extraction of the first JSON object/array from model text."""
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None
    return None
