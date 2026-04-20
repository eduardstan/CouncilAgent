"""ModelClient hierarchy — route, meter, and abstract all model calls.

All LLM I/O flows through this module. No other council module imports
litellm, httpx, or any provider SDK (architecture.md, Constitution §8).

LiteLLM is the single backend. It natively handles:
  - openrouter/* → OpenRouter via OPENROUTER_API_KEY
  - openai/*     → OpenAI via OPENAI_API_KEY
  - anthropic/*  → Anthropic via ANTHROPIC_API_KEY
  - ollama/*     → Local Ollama daemon
  - … and every other provider it supports

No separate OpenRouterClient, OllamaClient, or RoutingModelClient is needed.

Cache: intentionally absent in Phase 1.
# TODO(phase-2): response cache keyed by (model, prompt_hash, temperature)

Retry: max_retries parameter accepted; Phase 2 adds exponential back-off.
"""

from __future__ import annotations

import logging
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
    response_format: dict[str, object] | None = None
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
# LiteLLMClient — the single real backend
# ---------------------------------------------------------------------------


class LiteLLMClient(ModelClient):
    """Routes to any LiteLLM-supported provider via a single litellm.acompletion call.

    Pass model strings verbatim:
      "openai/gpt-4o-mini"
      "anthropic/claude-sonnet-4-5"
      "openrouter/openai/gpt-oss-20b:free"
      "openrouter/google/gemma-3-27b-it:free"
      "ollama/llama3.2"

    LiteLLM reads the appropriate API key from the environment automatically.
    Cost is parsed from response._hidden_params["response_cost"] when present.

    # TODO(phase-2): retry with exponential back-off
    # TODO(phase-2): response cache
    """

    def __init__(self, max_retries: int = 3, timeout: float = 60.0) -> None:
        self._max_retries = max_retries
        self._timeout = timeout
        # Load .env so OPENROUTER_API_KEY and other provider keys are available
        # to LiteLLM without requiring the caller to set them manually.
        try:
            from dotenv import load_dotenv  # type: ignore[import-untyped]
            load_dotenv(override=False)  # don't override already-set env vars
        except ImportError:
            pass  # python-dotenv not installed; assume env is already set

        # Suppress litellm's verbose "Provider List" error banners — they are
        # printed for any exception including rate limits and add no signal.
        try:
            import litellm as _litellm  # type: ignore[import-untyped]
            _litellm.suppress_debug_info = True
            _litellm.set_verbose = False
        except Exception as exc:
            logger.debug("litellm debug-suppression setup skipped: %s", exc)

    async def complete(
        self,
        request: ModelRequest,
        agent_id: str,
        round_index: int,
    ) -> AgentResponse | ModelFailure:
        import asyncio

        import litellm  # local import keeps council/core.py framework-free

        kwargs: dict[str, object] = {
            "model": request.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.response_format:
            kwargs["response_format"] = request.response_format

        last_error = ""
        for attempt in range(max(1, self._max_retries)):
            try:
                response = await asyncio.wait_for(
                    litellm.acompletion(**kwargs),
                    timeout=self._timeout,
                )
                msg = response.choices[0].message
                # Some thinking models (e.g. lfm-2.5-1.2b-thinking) return
                # content=None with the answer only in reasoning_content.
                # Fall back to reasoning_content when content is absent.
                content: str = (
                    msg.content
                    or getattr(msg, "reasoning_content", None)
                    or ""
                )
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
            except asyncio.TimeoutError:
                last_error = f"timeout after {self._timeout}s"
                logger.warning("LiteLLMClient: %s timed out (attempt %d/%d)",
                               request.model, attempt + 1, self._max_retries)
                break  # timeouts are not retryable
            except litellm.RateLimitError as exc:
                last_error = str(exc)
                if attempt < self._max_retries - 1:
                    backoff = 2.0 ** attempt  # 1s, 2s, 4s ...
                    logger.warning("LiteLLMClient: rate limit on %s, retrying in %.1fs (attempt %d/%d)",
                                   request.model, backoff, attempt + 1, self._max_retries)
                    await asyncio.sleep(backoff)
                else:
                    logger.warning("LiteLLMClient: rate limit on %s, all retries exhausted",
                                   request.model)
            except Exception as exc:
                last_error = str(exc)
                logger.debug("LiteLLMClient failure for %s: %s", request.model, exc)
                break  # non-retryable errors

        return ModelFailure(model=request.model, error=last_error)

    async def estimate_cost(self, model: str, prompt_tokens: int) -> float:
        try:
            import litellm

            # Strip provider prefix if present (litellm.model_cost uses bare names).
            bare = model.split("/", 1)[-1] if "/" in model else model
            table: dict[str, dict[str, float]] = litellm.model_cost
            entry = table.get(bare, {})
            per_token: float = entry.get("input_cost_per_token", 0.0)
            return per_token * prompt_tokens
        except Exception as exc:
            logger.debug("estimate_cost failed for %s: %s", model, exc)
            return 0.0
