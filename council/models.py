"""ModelClient — single gateway for all LLM calls.

Architecture rule: no other council/ module imports litellm or any provider SDK.
All model I/O flows through this module (Constitution §8).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ModelRequest:
    model: str
    prompt: str
    response_format: dict[str, object] | None = None
    max_tokens: int = 2048
    temperature: float = 0.7
    system_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class ModelResponse:
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    finish_reason: str = "stop"


@dataclass(frozen=True, slots=True)
class ModelFailure:
    model: str
    error: str
    retries: int = 0


ModelResult = ModelResponse | ModelFailure


class ModelClient(ABC):
    """Abstract base for all model backends."""

    @abstractmethod
    async def complete(self, request: ModelRequest) -> ModelResult: ...


class LiteLLMClient(ModelClient):
    """Production client — routes to LiteLLM. Never imported from core or dialect."""

    def __init__(self, *, default_temperature: float = 0.7, max_retries: int = 3) -> None:
        self._default_temperature = default_temperature
        self._max_retries = max_retries

    async def complete(self, request: ModelRequest) -> ModelResult:
        try:
            import litellm  # guarded import — LiteLLM is an optional dep in core path

            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})

            kwargs: dict[str, object] = {
                "model": request.model,
                "messages": messages,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "num_retries": self._max_retries,
            }
            if request.response_format:
                kwargs["response_format"] = request.response_format

            resp = await litellm.acompletion(**kwargs)
            content = str(resp.choices[0].message.content or "")
            usage = resp.usage
            cost = float(
                litellm.completion_cost(completion_response=resp)
                or 0.0
            )
            return ModelResponse(
                model=request.model,
                content=content,
                input_tokens=int(usage.prompt_tokens),
                output_tokens=int(usage.completion_tokens),
                cost_usd=cost,
                finish_reason=str(resp.choices[0].finish_reason or "stop"),
            )
        except Exception as exc:
            logger.warning("LiteLLMClient failure: %s", exc)
            return ModelFailure(model=request.model, error=str(exc))


class FakeModelClient(ModelClient):
    """Deterministic fake for tests — no real model calls ever."""

    def __init__(
        self,
        *,
        response_content: str = "fake response",
        always_fail: bool = False,
        keyed_responses: dict[str, str] | None = None,
    ) -> None:
        self._content = response_content
        self._always_fail = always_fail
        self._keyed = keyed_responses or {}

    async def complete(self, request: ModelRequest) -> ModelResult:
        if self._always_fail:
            return ModelFailure(model=request.model, error="simulated failure")
        content = self._keyed.get(request.prompt, self._content)
        return ModelResponse(
            model=request.model,
            content=content,
            input_tokens=len(request.prompt.split()),
            output_tokens=len(content.split()),
            cost_usd=0.0,
        )
