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


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """Identity-free response from a one-shot LLM call (e.g. MetaJudge synthesis).

    Distinct from AgentResponse because a synthesis/utility call is not
    "in" a deliberation round — there is no agent_id or round_index that
    would be semantically meaningful to stamp.
    """

    content: str
    tokens_in: int
    tokens_out: int
    cost: float


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class ModelClient(ABC):
    """Route a ModelRequest to the correct backend, return response or failure.

    Two entry points:
      - complete() — for per-round agent calls; stamps agent_id and round_index
        onto the returned AgentResponse. Used by council/core.py.
      - call()     — for one-shot synthesis/utility calls with no pipeline
        identity. Used by aggregation.MetaJudge.
    """

    @abstractmethod
    async def complete(
        self,
        request: ModelRequest,
        agent_id: str,
        round_index: int,
    ) -> AgentResponse | ModelFailure: ...

    @abstractmethod
    async def call(
        self,
        request: ModelRequest,
    ) -> ModelResponse | ModelFailure: ...

    @abstractmethod
    async def estimate_cost(self, model: str, prompt_tokens: int) -> float: ...


# ---------------------------------------------------------------------------
# FakeModelClient — canonical test double (used project-wide)
# ---------------------------------------------------------------------------

_ResponseMap = dict[tuple[str, int], str]
_ResponseFactory = Callable[[ModelRequest, str, int], str]
_CallHandler = Callable[[ModelRequest], str] | str


class FakeModelClient(ModelClient):
    """Deterministic test double.

    complete() dispatch — pass either:
    - A dict keyed by (agent_id, round_index) → response string
    - A callable (request, agent_id, round_index) → response string

    call() dispatch — pass call_handler:
    - A string (returned verbatim), or
    - A callable (request) → response string

    Unknown keys / missing handlers return ModelFailure.
    Token counts are approximated from string lengths. Cost is always 0.0.
    """

    def __init__(
        self,
        responses: _ResponseMap | _ResponseFactory,
        call_handler: _CallHandler | None = None,
    ) -> None:
        self._responses = responses
        self._call_handler = call_handler

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

    async def call(self, request: ModelRequest) -> ModelResponse | ModelFailure:
        if self._call_handler is None:
            return ModelFailure(
                model=request.model,
                error="FakeModelClient: no call_handler registered",
            )
        content = self._call_handler(request) if callable(self._call_handler) else self._call_handler
        tokens_in = max(1, len(request.prompt) // 4)
        tokens_out = max(1, len(content) // 4)
        return ModelResponse(
            content=content,
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
            from dotenv import load_dotenv
            load_dotenv(override=False)  # don't override already-set env vars
        except ImportError:
            pass  # python-dotenv not installed; assume env is already set

        # Suppress litellm's verbose "Provider List" error banners — they are
        # printed for any exception including rate limits and add no signal.
        try:
            import litellm as _litellm
            _litellm.suppress_debug_info = True
            _litellm.set_verbose = False  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("litellm debug-suppression setup skipped: %s", exc)

    async def _invoke(self, request: ModelRequest) -> ModelResponse | ModelFailure:
        """Shared litellm invocation — used by both complete() and call()."""
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
                content: str = (
                    msg.content
                    or getattr(msg, "reasoning_content", None)
                    or ""
                )
                tokens_in: int = response.usage.prompt_tokens or 0
                tokens_out: int = response.usage.completion_tokens or 0

                cost: float = 0.0
                try:
                    raw_cost = response._hidden_params.get("response_cost", 0.0)
                    cost = float(raw_cost or 0.0)
                except (AttributeError, TypeError, ValueError):
                    pass

                return ModelResponse(
                    content=content,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost=cost,
                )
            except TimeoutError:
                last_error = f"timeout after {self._timeout}s"
                logger.warning("LiteLLMClient: %s timed out (attempt %d/%d)",
                               request.model, attempt + 1, self._max_retries)
                break
            except litellm.RateLimitError as exc:  # type: ignore[attr-defined]
                last_error = str(exc)
                if attempt < self._max_retries - 1:
                    backoff = 2.0 ** attempt
                    logger.warning("LiteLLMClient: rate limit on %s, retrying in %.1fs (attempt %d/%d)",
                                   request.model, backoff, attempt + 1, self._max_retries)
                    await asyncio.sleep(backoff)
                else:
                    logger.warning("LiteLLMClient: rate limit on %s, all retries exhausted",
                                   request.model)
            except Exception as exc:
                last_error = str(exc)
                logger.debug("LiteLLMClient failure for %s: %s", request.model, exc)
                break

        return ModelFailure(model=request.model, error=last_error)

    async def complete(
        self,
        request: ModelRequest,
        agent_id: str,
        round_index: int,
    ) -> AgentResponse | ModelFailure:
        outcome = await self._invoke(request)
        if isinstance(outcome, ModelFailure):
            return outcome
        return AgentResponse(
            agent_id=agent_id,
            content=outcome.content,
            round_index=round_index,
            tokens_in=outcome.tokens_in,
            tokens_out=outcome.tokens_out,
            cost=outcome.cost,
        )

    async def call(self, request: ModelRequest) -> ModelResponse | ModelFailure:
        return await self._invoke(request)

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
