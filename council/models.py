"""ModelClient hierarchy — route, meter, and abstract all model calls.

All LLM I/O flows through this module. No other council module imports
litellm, httpx, or any provider SDK (architecture.md, Constitution §8).

Cache: intentionally absent in Phase 1.
# TODO(phase-2): response cache keyed by (model, prompt_hash, temperature)

Retry: max_retries parameter accepted but Phase 1 makes one attempt only.
# TODO(phase-2): retry with exponential back-off inside each real backend
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from council.context import AgentResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / failure value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """Parameters for a single model call."""

    model: str
    prompt: str
    response_format: dict[str, str] | None = None
    max_tokens: int = 2048
    temperature: float = 0.7


@dataclass(frozen=True, slots=True)
class ModelFailure:
    """Returned (never raised) when a model call cannot be completed."""

    model: str
    error: str
    retries: int = 0


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class ModelClient(ABC):
    """Route a ModelRequest to the correct backend, return response or failure."""

    @abstractmethod
    async def complete(
        self,
        request: ModelRequest,
        agent_id: str,
        round_index: int,
    ) -> AgentResponse | ModelFailure: ...

    @abstractmethod
    async def estimate_cost(self, model: str, prompt_tokens: int) -> float: ...


# ---------------------------------------------------------------------------
# FakeModelClient — canonical test double (used project-wide)
# ---------------------------------------------------------------------------

_ResponseMap = dict[tuple[str, int], str]
_ResponseFactory = Callable[[ModelRequest, str, int], str]


class FakeModelClient(ModelClient):
    """Deterministic test double.

    Accepts either:
    - A dict keyed by (agent_id, round_index) → response string
    - A callable (request, agent_id, round_index) → response string

    Unknown (agent_id, round_index) pairs return a ModelFailure.
    Token counts are approximated from string lengths (deterministic).
    Cost is always 0.0.
    """

    def __init__(self, responses: _ResponseMap | _ResponseFactory) -> None:
        self._responses = responses

    async def complete(
        self,
        request: ModelRequest,
        agent_id: str,
        round_index: int,
    ) -> AgentResponse | ModelFailure:
        if callable(self._responses):
            content = self._responses(request, agent_id, round_index)
        else:
            key = (agent_id, round_index)
            if key not in self._responses:
                return ModelFailure(
                    model=request.model,
                    error=f"FakeModelClient: no response registered for key {key}",
                )
            content = self._responses[key]

        # Approximate token counts: 1 token ≈ 4 characters (deterministic).
        tokens_in = max(1, len(request.prompt) // 4)
        tokens_out = max(1, len(content) // 4)
        return AgentResponse(
            agent_id=agent_id,
            content=content,
            round_index=round_index,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=0.0,
        )

    async def estimate_cost(self, model: str, prompt_tokens: int) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# LiteLLMClient
# ---------------------------------------------------------------------------


class LiteLLMClient(ModelClient):
    """Routes to any LiteLLM-supported provider (OpenAI, Anthropic, Google, etc.).

    The model string is passed verbatim to litellm.acompletion, so callers use
    the litellm model naming convention (e.g. "openai/gpt-4o-mini").

    # TODO(phase-2): retry with exponential back-off
    # TODO(phase-2): response cache
    """

    def __init__(self, max_retries: int = 1) -> None:
        # max_retries stored for Phase 2; Phase 1 makes a single attempt.
        self._max_retries = max_retries  # TODO(phase-2): use for retry logic

    async def complete(
        self,
        request: ModelRequest,
        agent_id: str,
        round_index: int,
    ) -> AgentResponse | ModelFailure:
        import litellm  # local import keeps council/core.py framework-free

        kwargs: dict[str, object] = {
            "model": request.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.response_format:
            kwargs["response_format"] = request.response_format

        try:
            response = await litellm.acompletion(**kwargs)
            content: str = response.choices[0].message.content or ""
            tokens_in: int = response.usage.prompt_tokens or 0
            tokens_out: int = response.usage.completion_tokens or 0
            return AgentResponse(
                agent_id=agent_id,
                content=content,
                round_index=round_index,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=0.0,  # TODO(phase-2): parse cost from litellm response._hidden_params
            )
        except Exception as exc:
            logger.debug("LiteLLMClient failure for %s: %s", request.model, exc)
            return ModelFailure(model=request.model, error=str(exc).lower())

    async def estimate_cost(self, model: str, prompt_tokens: int) -> float:
        try:
            import litellm

            # Strip provider prefix if present (litellm.model_cost uses bare names).
            bare = model.split("/", 1)[-1] if "/" in model else model
            table: dict[str, dict[str, float]] = litellm.model_cost
            entry = table.get(bare, {})
            per_token: float = entry.get("input_cost_per_token", 0.0)
            return per_token * prompt_tokens
        except Exception:
            return 0.0


# ---------------------------------------------------------------------------
# OpenRouterClient
# ---------------------------------------------------------------------------


class OpenRouterClient(ModelClient):
    """Direct httpx calls to OpenRouter REST API.

    Auth: OPENROUTER_API_KEY env var (or passed at construction).
    Cost estimation: fetches /api/v1/models once on first call, caches in-process.

    # TODO(phase-2): retry with exponential back-off
    # TODO(phase-2): persist model-cost cache across instances (module-level)
    """

    _BASE_URL = "https://openrouter.ai/api/v1"
    _model_cost_cache: ClassVar[dict[str, float]] = {}
    _cache_populated: ClassVar[bool] = False

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def complete(
        self,
        request: ModelRequest,
        agent_id: str,
        round_index: int,
    ) -> AgentResponse | ModelFailure:
        import httpx

        # Strip the "openrouter/" prefix if callers pass it.
        model = request.model.removeprefix("openrouter/")
        body: dict[str, object] = {
            "model": model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.response_format:
            body["response_format"] = request.response_format

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._BASE_URL}/chat/completions",
                    headers=self._headers(),
                    json=body,
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"] or ""
                usage = data.get("usage", {})
                return AgentResponse(
                    agent_id=agent_id,
                    content=content,
                    round_index=round_index,
                    tokens_in=usage.get("prompt_tokens", 0),
                    tokens_out=usage.get("completion_tokens", 0),
                    cost=0.0,  # TODO(phase-2): parse from usage.cost if present
                )
        except Exception as exc:
            logger.debug("OpenRouterClient failure for %s: %s", request.model, exc)
            return ModelFailure(model=request.model, error=str(exc).lower())

    async def estimate_cost(self, model: str, prompt_tokens: int) -> float:
        await self._populate_cost_cache()
        bare = model.removeprefix("openrouter/")
        per_token = OpenRouterClient._model_cost_cache.get(bare, 0.0)
        return per_token * prompt_tokens

    async def _populate_cost_cache(self) -> None:
        if OpenRouterClient._cache_populated:
            return
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._BASE_URL}/models",
                    headers=self._headers(),
                    timeout=10.0,
                )
                resp.raise_for_status()
                for entry in resp.json().get("data", []):
                    mid = entry.get("id", "")
                    pricing = entry.get("pricing", {})
                    try:
                        per_token = float(pricing.get("prompt", 0))
                    except (TypeError, ValueError):
                        per_token = 0.0
                    OpenRouterClient._model_cost_cache[mid] = per_token
            OpenRouterClient._cache_populated = True
        except Exception as exc:
            logger.warning("OpenRouterClient: failed to fetch model pricing: %s", exc)


# ---------------------------------------------------------------------------
# OllamaClient
# ---------------------------------------------------------------------------


class OllamaClient(ModelClient):
    """Direct httpx calls to a local Ollama daemon.

    Cost is always 0.0 (local inference).

    # TODO(phase-2): retry on transient connection errors
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    async def complete(
        self,
        request: ModelRequest,
        agent_id: str,
        round_index: int,
    ) -> AgentResponse | ModelFailure:
        import httpx

        # Strip the "ollama/" prefix if callers pass it.
        model = request.model.removeprefix("ollama/")
        body: dict[str, object] = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
            "options": {"num_predict": request.max_tokens, "temperature": request.temperature},
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json=body,
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()
                content: str = data.get("response", "")
                tokens_in: int = data.get("prompt_eval_count", max(1, len(request.prompt) // 4))
                tokens_out: int = data.get("eval_count", max(1, len(content) // 4))
                return AgentResponse(
                    agent_id=agent_id,
                    content=content,
                    round_index=round_index,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost=0.0,
                )
        except Exception as exc:
            logger.debug("OllamaClient failure for %s: %s", request.model, exc)
            return ModelFailure(model=request.model, error=str(exc).lower())

    async def estimate_cost(self, model: str, prompt_tokens: int) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# RoutingModelClient
# ---------------------------------------------------------------------------


class RoutingModelClient(ModelClient):
    """Dispatches calls to the correct backend by model-name prefix.

    Routing rules:
    - "openrouter/*" → OpenRouterClient
    - "ollama/*"     → OllamaClient
    - anything else  → LiteLLMClient

    Construct with explicit backend instances to allow test injection.
    """

    def __init__(
        self,
        openrouter: ModelClient | None = None,
        litellm: ModelClient | None = None,
        ollama: ModelClient | None = None,
    ) -> None:
        self._openrouter: ModelClient = openrouter or OpenRouterClient()
        self._litellm: ModelClient = litellm or LiteLLMClient()
        self._ollama: ModelClient = ollama or OllamaClient()

    def _backend(self, model: str) -> ModelClient:
        if model.startswith("openrouter/"):
            return self._openrouter
        if model.startswith("ollama/"):
            return self._ollama
        return self._litellm

    async def complete(
        self,
        request: ModelRequest,
        agent_id: str,
        round_index: int,
    ) -> AgentResponse | ModelFailure:
        return await self._backend(request.model).complete(request, agent_id, round_index)

    async def estimate_cost(self, model: str, prompt_tokens: int) -> float:
        return await self._backend(model).estimate_cost(model, prompt_tokens)
