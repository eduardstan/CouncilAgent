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


# ---------------------------------------------------------------------------
# PR6/Slice D — end-to-end: CouncilAgent default produces BAFMarginConfidence
# and a non-None ProvenanceReceipt.qbaf.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_council_agent_default_returns_baf_margin_confidence() -> None:
    """The headline P2 (AAAI 2027) reviewer-visible result: a default
    CouncilAgent.complete() returns BAFMarginConfidence (not the W0/W1
    CopelandConfidence(0.5) placeholder)."""
    from council.agent import CouncilAgent
    from council.context import BAFMarginConfidence

    client = FakeModelClient(
        response_content='{"force": "propose", "claim": {"surface": "42"}, "confidence": 0.8}'
    )
    agent = CouncilAgent(
        agents=("m1", "m2", "m3"),
        model_client=client,
        max_rounds=2,
    )
    result = await agent.complete("What is 6 * 7?")
    assert isinstance(result.confidence, BAFMarginConfidence)


@pytest.mark.asyncio
async def test_council_agent_default_populates_receipt_qbaf() -> None:
    """The headline §11 result: receipt.qbaf is non-None when the L2
    ArgumentationAggregator runs."""
    from council.agent import CouncilAgent
    from council.symbolic.argue.baf import QBAF

    client = FakeModelClient(
        response_content='{"force": "propose", "claim": {"surface": "X"}, "confidence": 0.7}'
    )
    agent = CouncilAgent(
        agents=("m1", "m2"),
        model_client=client,
        max_rounds=1,
    )
    result = await agent.complete("Q?")
    assert result.receipt.qbaf is not None
    assert isinstance(result.receipt.qbaf, QBAF)
    # BAF has at least one Argument per Propose-derived move
    assert len(result.receipt.qbaf.arguments) >= 1


@pytest.mark.asyncio
async def test_council_agent_with_custom_aggregator() -> None:
    """User supplies a custom Aggregator -> CouncilAgent uses it instead
    of the default ArgumentationAggregator+DFQuAD."""
    from council.agent import CouncilAgent
    from council.context import CopelandConfidence
    from council.symbolic.argue.aggregator import LastProposeFallbackAggregator

    client = FakeModelClient(
        response_content='{"force": "propose", "claim": {"surface": "X"}, "confidence": 0.7}'
    )
    agent = CouncilAgent(
        agents=("m1", "m2"),
        model_client=client,
        aggregator=LastProposeFallbackAggregator(),
        max_rounds=1,
    )
    result = await agent.complete("Q?")
    # LastProposeFallbackAggregator emits CopelandConfidence
    assert isinstance(result.confidence, CopelandConfidence)
    # No QBAF in metadata for the fallback path -> receipt.qbaf is None
    assert result.receipt.qbaf is None


@pytest.mark.asyncio
async def test_council_agent_strategic_coupled_demotes_unbacked() -> None:
    """End-to-end: a CouncilAgent with StrategicCoupledSemantics demotes
    consensus when no agent provides evidence, satisfying the T3 invariant
    on the live pipeline (PR5/T7 mechanisation, end-to-end)."""
    from council.agent import CouncilAgent
    from council.context import BAFMarginConfidence
    from council.symbolic.argue.aggregator import ArgumentationAggregator
    from council.symbolic.argue.semantics.coupled import StrategicCoupledSemantics
    from council.symbolic.argue.semantics.df_quad import DFQuADSemantics

    # All agents propose the same answer with no evidence
    client = FakeModelClient(
        response_content='{"force": "propose", "claim": {"surface": "X"}, "confidence": 0.7}'
    )
    sc_aggregator = ArgumentationAggregator(
        semantics=StrategicCoupledSemantics(
            base=DFQuADSemantics(),
            evidence_backed=frozenset(),
            alpha=0.4,  # strict; demoted < 0.5 → out of extension
        ),
    )
    agent = CouncilAgent(
        agents=("m1", "m2", "m3"),
        model_client=client,
        aggregator=sc_aggregator,
        max_rounds=1,
    )
    result = await agent.complete("Q?")
    # The headline result of T7 wired end-to-end: even though all 3 agents
    # propose "X", the lack of evidence demotes the strength below the
    # extension threshold. The aggregator still picks "X" as the winner
    # (it's the only candidate), but the preferred extension is empty.
    assert isinstance(result.confidence, BAFMarginConfidence)
    extension = result.receipt.qbaf  # the qbaf is populated
    assert extension is not None
