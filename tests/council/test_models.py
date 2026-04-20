"""Tests for council/models.py — ModelClient hierarchy.

No real network calls. LiteLLMClient is tested with mocked litellm.acompletion.
FakeModelClient is the canonical test double used throughout the project.

Single real backend: LiteLLMClient handles all providers (openai/*, anthropic/*,
openrouter/*, ollama/*, etc.) via LiteLLM's unified interface. No separate
OllamaClient or RoutingModelClient — those were removed as redundant.
"""

from __future__ import annotations

import pytest

from council.context import AgentResponse
from council.models import (
    FakeModelClient,
    LiteLLMClient,
    ModelFailure,
    ModelRequest,
)

# ---------------------------------------------------------------------------
# ModelRequest
# ---------------------------------------------------------------------------


class TestModelRequest:
    def test_required_fields(self) -> None:
        req = ModelRequest(model="openai/gpt-4o-mini", prompt="Hello")
        assert req.model == "openai/gpt-4o-mini"
        assert req.prompt == "Hello"

    def test_defaults(self) -> None:
        req = ModelRequest(model="m", prompt="p")
        assert req.response_format is None
        assert req.max_tokens == 2048
        assert req.temperature == 0.7

    def test_is_frozen(self) -> None:
        req = ModelRequest(model="m", prompt="p")
        with pytest.raises((AttributeError, TypeError)):
            req.prompt = "changed"  # type: ignore[misc]

    def test_response_format_accepts_nested_schema(self) -> None:
        schema: dict[str, object] = {
            "type": "json_schema",
            "schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
        }
        req = ModelRequest(model="m", prompt="p", response_format=schema)
        assert req.response_format == schema


# ---------------------------------------------------------------------------
# ModelFailure
# ---------------------------------------------------------------------------


class TestModelFailure:
    def test_fields(self) -> None:
        f = ModelFailure(model="m", error="timeout", retries=3)
        assert f.model == "m"
        assert f.error == "timeout"
        assert f.retries == 3

    def test_is_frozen(self) -> None:
        f = ModelFailure(model="m", error="e", retries=0)
        with pytest.raises((AttributeError, TypeError)):
            f.error = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FakeModelClient
# ---------------------------------------------------------------------------


class TestFakeModelClient:
    def _req(self, model: str = "fake/model") -> ModelRequest:
        return ModelRequest(model=model, prompt="What is 6x7?")

    async def test_returns_agent_response_for_known_key(self) -> None:
        client = FakeModelClient({("agent-0", 0): "42"})
        result = await client.complete(self._req(), agent_id="agent-0", round_index=0)
        assert isinstance(result, AgentResponse)
        assert result.content == "42"
        assert result.agent_id == "agent-0"
        assert result.round_index == 0

    async def test_returns_model_failure_for_unknown_key(self) -> None:
        client = FakeModelClient({})
        result = await client.complete(self._req(), agent_id="agent-0", round_index=0)
        assert isinstance(result, ModelFailure)
        assert "agent-0" in result.error or result.error != ""

    async def test_deterministic_token_counts(self) -> None:
        client = FakeModelClient({("a", 0): "hello world"})
        r1 = await client.complete(self._req(), agent_id="a", round_index=0)
        r2 = await client.complete(self._req(), agent_id="a", round_index=0)
        assert isinstance(r1, AgentResponse)
        assert isinstance(r2, AgentResponse)
        assert r1.tokens_in == r2.tokens_in
        assert r1.tokens_out == r2.tokens_out

    async def test_tokens_in_reflects_prompt_length(self) -> None:
        client = FakeModelClient({("a", 0): "answer"})
        result = await client.complete(self._req(), agent_id="a", round_index=0)
        assert isinstance(result, AgentResponse)
        assert result.tokens_in > 0

    async def test_tokens_out_reflects_response_length(self) -> None:
        client = FakeModelClient({("a", 0): "answer"})
        result = await client.complete(self._req(), agent_id="a", round_index=0)
        assert isinstance(result, AgentResponse)
        assert result.tokens_out > 0

    async def test_cost_is_zero_for_fake(self) -> None:
        client = FakeModelClient({("a", 0): "x"})
        result = await client.complete(self._req(), agent_id="a", round_index=0)
        assert isinstance(result, AgentResponse)
        assert result.cost == 0.0

    async def test_estimate_cost_returns_zero(self) -> None:
        client = FakeModelClient({})
        cost = await client.estimate_cost("any/model", prompt_tokens=100)
        assert cost == 0.0

    async def test_callable_response_factory(self) -> None:
        def factory(req: ModelRequest, agent_id: str, round_index: int) -> str:
            return f"round={round_index} agent={agent_id}"

        client = FakeModelClient(factory)
        result = await client.complete(self._req(), agent_id="agent-1", round_index=2)
        assert isinstance(result, AgentResponse)
        assert result.content == "round=2 agent=agent-1"

    async def test_different_rounds_keyed_separately(self) -> None:
        client = FakeModelClient({
            ("a", 0): "first",
            ("a", 1): "second",
        })
        r0 = await client.complete(self._req(), agent_id="a", round_index=0)
        r1 = await client.complete(self._req(), agent_id="a", round_index=1)
        assert isinstance(r0, AgentResponse)
        assert isinstance(r1, AgentResponse)
        assert r0.content == "first"
        assert r1.content == "second"


# ---------------------------------------------------------------------------
# LiteLLMClient — all providers via mocked litellm.acompletion
# ---------------------------------------------------------------------------


class TestLiteLLMClient:
    async def test_returns_agent_response_on_success(self, mocker: pytest.FixtureRequest) -> None:
        mock_resp = mocker.MagicMock()
        mock_resp.choices = [mocker.MagicMock()]
        mock_resp.choices[0].message.content = "litellm answer"
        mock_resp.usage.prompt_tokens = 8
        mock_resp.usage.completion_tokens = 4
        mock_resp._hidden_params = {"response_cost": 0.0}

        mocker.patch("litellm.acompletion", new_callable=mocker.AsyncMock, return_value=mock_resp)

        client = LiteLLMClient()
        req = ModelRequest(model="openai/gpt-4o-mini", prompt="hi")
        result = await client.complete(req, agent_id="a", round_index=0)
        assert isinstance(result, AgentResponse)
        assert result.content == "litellm answer"
        assert result.tokens_in == 8
        assert result.tokens_out == 4

    async def test_openrouter_free_model_passes_through(self, mocker: pytest.FixtureRequest) -> None:
        """openrouter/:free model slugs pass verbatim to litellm — no rewriting."""
        mock_resp = mocker.MagicMock()
        mock_resp.choices = [mocker.MagicMock()]
        mock_resp.choices[0].message.content = "free answer"
        mock_resp.usage.prompt_tokens = 5
        mock_resp.usage.completion_tokens = 3
        mock_resp._hidden_params = {"response_cost": 0.0}

        mock_acompletion = mocker.patch(
            "litellm.acompletion", new_callable=mocker.AsyncMock, return_value=mock_resp
        )

        client = LiteLLMClient()
        req = ModelRequest(model="openrouter/google/gemma-3-27b-it:free", prompt="hi")
        result = await client.complete(req, agent_id="a", round_index=0)
        assert isinstance(result, AgentResponse)
        # Confirm the model string was passed verbatim — no stripping of prefix
        call_kwargs = mock_acompletion.call_args.kwargs
        assert call_kwargs["model"] == "openrouter/google/gemma-3-27b-it:free"

    async def test_ollama_model_passes_through(self, mocker: pytest.FixtureRequest) -> None:
        """ollama/* models route via LiteLLM — OllamaClient is no longer needed."""
        mock_resp = mocker.MagicMock()
        mock_resp.choices = [mocker.MagicMock()]
        mock_resp.choices[0].message.content = "local answer"
        mock_resp.usage.prompt_tokens = 4
        mock_resp.usage.completion_tokens = 2
        mock_resp._hidden_params = {"response_cost": 0.0}

        mock_acompletion = mocker.patch(
            "litellm.acompletion", new_callable=mocker.AsyncMock, return_value=mock_resp
        )

        client = LiteLLMClient()
        req = ModelRequest(model="ollama/llama3.2", prompt="hi")
        result = await client.complete(req, agent_id="a", round_index=0)
        assert isinstance(result, AgentResponse)
        call_kwargs = mock_acompletion.call_args.kwargs
        assert call_kwargs["model"] == "ollama/llama3.2"

    async def test_cost_parsed_from_hidden_params(self, mocker: pytest.FixtureRequest) -> None:
        mock_resp = mocker.MagicMock()
        mock_resp.choices = [mocker.MagicMock()]
        mock_resp.choices[0].message.content = "answer"
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 5
        mock_resp._hidden_params = {"response_cost": 0.00042}

        mocker.patch("litellm.acompletion", new_callable=mocker.AsyncMock, return_value=mock_resp)

        client = LiteLLMClient()
        result = await client.complete(
            ModelRequest(model="openai/gpt-4o-mini", prompt="hi"), agent_id="a", round_index=0
        )
        assert isinstance(result, AgentResponse)
        assert result.cost == pytest.approx(0.00042)

    async def test_cost_defaults_to_zero_if_hidden_params_missing(self, mocker: pytest.FixtureRequest) -> None:
        mock_resp = mocker.MagicMock()
        mock_resp.choices = [mocker.MagicMock()]
        mock_resp.choices[0].message.content = "answer"
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 5
        del mock_resp._hidden_params

        mocker.patch("litellm.acompletion", new_callable=mocker.AsyncMock, return_value=mock_resp)

        client = LiteLLMClient()
        result = await client.complete(
            ModelRequest(model="openai/gpt-4o-mini", prompt="hi"), agent_id="a", round_index=0
        )
        assert isinstance(result, AgentResponse)
        assert result.cost == 0.0

    async def test_returns_model_failure_on_exception(self, mocker: pytest.FixtureRequest) -> None:
        mocker.patch("litellm.acompletion", side_effect=Exception("api error"))
        client = LiteLLMClient()
        result = await client.complete(
            ModelRequest(model="openai/gpt-4o-mini", prompt="hi"), agent_id="a", round_index=0
        )
        assert isinstance(result, ModelFailure)
        assert "api error" in result.error.lower()

    async def test_estimate_cost_returns_float(self, mocker: pytest.FixtureRequest) -> None:
        mocker.patch.dict("litellm.model_cost", {"gpt-4o-mini": {"input_cost_per_token": 0.00015}})
        client = LiteLLMClient()
        cost = await client.estimate_cost("openai/gpt-4o-mini", prompt_tokens=100)
        assert isinstance(cost, float)
        assert cost >= 0.0


# ---------------------------------------------------------------------------
# No cross-layer imports
# ---------------------------------------------------------------------------


def test_models_only_imports_context_from_council() -> None:
    import importlib.util

    spec = importlib.util.find_spec("council.models")
    assert spec is not None and spec.origin is not None

    with open(spec.origin) as f:
        source = f.read()

    bad_lines = [
        line
        for line in source.splitlines()
        if (
            ("from council." in line or "import council." in line)
            and "council.context" not in line
            and not line.strip().startswith("#")
        )
    ]
    assert bad_lines == [], f"council/models.py imports from non-context council module: {bad_lines}"
