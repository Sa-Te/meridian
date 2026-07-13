"""A short-lived, in-process memoizing LLMProvider wrapper for eval/run_eval.py.

Wraps whichever real LLMProvider the eval harness is configured to use
(GeminiLLMProvider by default, see ADR-0013) so that two calls with the
exact same arguments within one `run()` invocation only hit the live API
once. Scoped to a single instance created fresh per eval run -- nothing
persists to disk, so this is purely an in-run duplicate-call guard, not a
golden-response fixture. See docs/adr/0016.

Only successful responses are cached: a call that raises is never stored,
so eval/run_eval.py's own retry/backoff wrapper (_with_retry) still retries
a real failed call for real, rather than replaying a cached exception.
"""

import hashlib
import json

from pydantic import BaseModel

from app.providers.llm.base import LLMMessage, LLMProvider, LLMResponse, SchemaT


def _cache_key(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


class CachingLLMProvider(LLMProvider):
    def __init__(self, wrapped: LLMProvider) -> None:
        self._wrapped = wrapped
        self._generate_cache: dict[str, LLMResponse] = {}
        self._structured_cache: dict[str, BaseModel] = {}

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        key = _cache_key(
            [(message.role, message.content) for message in messages],
            system,
            max_tokens,
            temperature,
        )
        cached = self._generate_cache.get(key)
        if cached is not None:
            return cached

        result = await self._wrapped.generate(
            messages, system=system, max_tokens=max_tokens, temperature=temperature
        )
        self._generate_cache[key] = result
        return result

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[SchemaT],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> SchemaT:
        key = _cache_key(prompt, response_model.__qualname__, system, max_tokens, temperature)
        cached = self._structured_cache.get(key)
        if cached is not None:
            assert isinstance(cached, response_model)
            return cached

        result = await self._wrapped.generate_structured(
            prompt, response_model, system=system, max_tokens=max_tokens, temperature=temperature
        )
        self._structured_cache[key] = result
        return result
