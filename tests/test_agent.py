"""Tests for council/agent.py — CouncilAgent.complete() drop-in interface."""

from __future__ import annotations

import pytest

from council.models import FakeModelClient


@pytest.mark.asyncio
async def test_council_agent_complete_returns_response() -> None:
    from council.agent import CouncilAgent
    from council.context import (
        BAFMarginConfidence,
        CopelandConfidence,
        CouncilResponse,
        JSDConfidence,
        MonitorVerdictConfidence,
    )

    fake_json = '{"force": "propose", "claim": {"surface": "4"}, "confidence": 0.85}'
    client = FakeModelClient(response_content=fake_json)

    agent = CouncilAgent(
        agents=("m1", "m2", "m3"),
        model_client=client,
        max_rounds=2,
    )

    result = await agent.complete("What is 2+2?")

    assert isinstance(result, CouncilResponse)
    assert isinstance(
        result.confidence,
        (JSDConfidence, BAFMarginConfidence, MonitorVerdictConfidence, CopelandConfidence),
    )
    assert result.receipt is not None


@pytest.mark.asyncio
async def test_council_agent_complete_nonempty_answer() -> None:
    from council.agent import CouncilAgent

    client = FakeModelClient(
        response_content='{"force": "propose", "claim": {"surface": "Paris"}, "confidence": 0.9}'
    )
    agent = CouncilAgent(agents=("a1", "a2"), model_client=client, max_rounds=1)
    result = await agent.complete("Capital of France?")
    assert result.answer != ""


@pytest.mark.asyncio
async def test_council_agent_default_agents_are_model_ids() -> None:
    """CouncilAgent injects model IDs as agent IDs into the context."""
    from council.agent import CouncilAgent

    client = FakeModelClient(response_content='{"force": "propose", "claim": {"surface": "ok"}}')
    agent = CouncilAgent(agents=("gpt-4o", "claude-3"), model_client=client, max_rounds=1)
    result = await agent.complete("Ping")
    assert result.receipt.trace.moves  # at least 1 move was generated
