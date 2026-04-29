"""Tests for council/models.py — ModelClient, FakeModelClient, ModelRequest/Response/Failure."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

def test_model_request_is_frozen() -> None:
    import dataclasses

    from council.models import ModelRequest
    r = ModelRequest(model="openai/gpt-4o-mini", prompt="hello")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        r.prompt = "mutated"  # type: ignore[misc]


def test_model_request_defaults() -> None:
    from council.models import ModelRequest
    r = ModelRequest(model="openai/gpt-4o-mini", prompt="hello")
    assert r.max_tokens == 2048
    assert r.temperature == 0.7
    assert r.system_prompt is None


def test_model_response_is_frozen() -> None:
    import dataclasses

    from council.models import ModelResponse
    r = ModelResponse(model="x", content="hi", input_tokens=5, output_tokens=3, cost_usd=0.0)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        r.content = "mutated"  # type: ignore[misc]


def test_model_failure_is_frozen() -> None:
    import dataclasses

    from council.models import ModelFailure
    f = ModelFailure(model="x", error="timeout")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        f.error = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FakeModelClient — deterministic, no real model calls
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fake_client_returns_model_response() -> None:
    from council.models import FakeModelClient, ModelRequest, ModelResponse
    client = FakeModelClient(response_content="The answer is 42.")
    req = ModelRequest(model="fake/model", prompt="What is 6*7?")
    result = await client.complete(req)
    assert isinstance(result, ModelResponse)
    assert result.content == "The answer is 42."
    assert result.cost_usd >= 0.0


@pytest.mark.asyncio
async def test_fake_client_deterministic() -> None:
    from council.models import FakeModelClient, ModelRequest
    client = FakeModelClient(response_content="42")
    req = ModelRequest(model="fake/model", prompt="x")
    r1 = await client.complete(req)
    r2 = await client.complete(req)
    assert r1.content == r2.content


@pytest.mark.asyncio
async def test_fake_client_failure_mode() -> None:
    from council.models import FakeModelClient, ModelFailure, ModelRequest
    client = FakeModelClient(response_content="x", always_fail=True)
    req = ModelRequest(model="fake/model", prompt="y")
    result = await client.complete(req)
    assert isinstance(result, ModelFailure)


@pytest.mark.asyncio
async def test_fake_client_keyed_responses() -> None:
    from council.models import FakeModelClient, ModelRequest
    keyed = {"prompt_a": "response_a", "prompt_b": "response_b"}
    client = FakeModelClient(keyed_responses=keyed, response_content="default")
    r = await client.complete(ModelRequest(model="m", prompt="prompt_a"))
    assert r.content == "response_a"


# ---------------------------------------------------------------------------
# ModelClient is abstract
# ---------------------------------------------------------------------------

def test_model_client_is_abstract() -> None:
    from council.models import ModelClient
    with pytest.raises(TypeError):
        ModelClient()  # type: ignore[abstract]
