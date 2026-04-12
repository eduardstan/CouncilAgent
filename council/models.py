"""ModelClient hierarchy — route, meter, and abstract all model calls.

All LLM I/O flows through this module. No other council module imports
litellm, httpx, or any provider SDK (architecture.md, Constitution §8).

LiteLLM natively supports the openrouter/* model prefix (routes to OpenRouter
via OPENROUTER_API_KEY), so a separate OpenRouterClient is not needed.

Cache: intentionally absent in Phase 1.
# TODO(phase-2): response cache keyed by (model, prompt_hash, temperature)

Retry: max_retries parameter accepted; Phase 2 adds exponential back-off.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

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
    """Routes to any LiteLLM-supported provider (OpenAI, Anthropic, Google, OpenRouter, etc.).

    The model string is passed verbatim to litellm.acompletion, so callers use
    LiteLLM model naming: "openai/gpt-4o-mini", "anthropic/claude-sonnet-4-5",
    "openrouter/anthropic/claude-sonnet-4-5", etc.

    Cost is parsed from response._hidden_params["response_cost"] when present.

    # TODO(phase-2): retry with exponential back-off
    # TODO(phase-2): response cache
    """

    def __init__(self, max_retries: int = 1) -> None:
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

            # Parse real cost from litellm hidden params (populated for most providers).
            cost: float = 0.0
            try:
                raw_cost = response._hidden_params.get("response_cost", 0.0)
                cost = float(raw_cost or 0.0)
            except (AttributeError, TypeError, ValueError):
                pass

            return AgentResponse(
                agent_id=agent_id,
                content=content,
                round_index=round_index,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=cost,
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
    - "ollama/*"     → OllamaClient (local inference, no API key needed)
    - anything else  → LiteLLMClient (handles openai/*, anthropic/*, openrouter/*, etc.)

    LiteLLM natively routes "openrouter/*" models to OpenRouter via
    OPENROUTER_API_KEY, so no separate OpenRouterClient is required.

    Construct with explicit backend instances to allow test injection.
    """

    def __init__(
        self,
        litellm: ModelClient | None = None,
        ollama: ModelClient | None = None,
    ) -> None:
        self._litellm: ModelClient = litellm or LiteLLMClient()
        self._ollama: ModelClient = ollama or OllamaClient()

    def _backend(self, model: str) -> ModelClient:
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
