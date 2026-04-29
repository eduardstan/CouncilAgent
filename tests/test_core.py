"""Tests for council/core.py — run_council pipeline.

Covers the full end-to-end contract from testing.md:
  - 3 agents, FakeModelClient, 2 rounds
  - all agents generated in round 0
  - adjacency matrix respected in round 1 (topology hook tested separately)
  - aggregation produced a non-null result
  - state token counts are non-zero
  - _build_visibility_context is the single anonymisation site (§10)
  - CouncilResponse.confidence is a tagged Confidence type
"""

from __future__ import annotations

import pytest

from council.dialect.moves import Claim, Force, Propose
from council.dialect.trace import Trace
from council.models import FakeModelClient


# ---------------------------------------------------------------------------
# FixedRounds + run_council — 3-agent 2-round happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_council_3agents_2rounds_returns_response() -> None:
    from council.context import (
        BAFMarginConfidence,
        Confidence,
        CopelandConfidence,
        CouncilContext,
        CouncilResponse,
        JSDConfidence,
        MonitorVerdictConfidence,
    )
    from council.core import run_council
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    from council.termination import FixedRounds
    from council.topology import CompleteGraphTopology

    agents = ("a1", "a2", "a3")
    fake_response = '{"force": "propose", "claim": {"surface": "42"}, "confidence": 0.9}'
    client = FakeModelClient(response_content=fake_response)

    ctx = CouncilContext(
        agents=agents,
        model_client=client,
        protocol=DeliberationAutomaton(max_phases=2, agents=list(agents)),
        topology=CompleteGraphTopology(n_agents=3),
        termination=FixedRounds(max_rounds=2),
        anonymize=True,
    )

    result = await run_council("What is 2+2?", context=ctx)

    assert isinstance(result, CouncilResponse)
    assert result.answer != ""
    assert isinstance(
        result.confidence,
        (JSDConfidence, BAFMarginConfidence, MonitorVerdictConfidence, CopelandConfidence),
    )
    assert result.receipt is not None
    assert result.receipt.trace is not None


@pytest.mark.asyncio
async def test_run_council_trace_accumulates_moves() -> None:
    from council.context import CouncilContext
    from council.core import run_council
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    from council.termination import FixedRounds
    from council.topology import CompleteGraphTopology

    agents = ("a1", "a2", "a3")
    fake_response = '{"force": "propose", "claim": {"surface": "42"}, "confidence": 0.8}'
    client = FakeModelClient(response_content=fake_response)

    ctx = CouncilContext(
        agents=agents,
        model_client=client,
        protocol=DeliberationAutomaton(max_phases=2, agents=list(agents)),
        topology=CompleteGraphTopology(n_agents=3),
        termination=FixedRounds(max_rounds=2),
        anonymize=True,
    )

    result = await run_council("Test prompt", context=ctx)

    # 3 agents × 2 rounds = 6 moves minimum
    assert len(result.receipt.trace.moves) >= 6


@pytest.mark.asyncio
async def test_run_council_token_counts_nonzero() -> None:
    from council.context import CouncilContext
    from council.core import run_council
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    from council.termination import FixedRounds
    from council.topology import CompleteGraphTopology

    agents = ("a1", "a2")
    fake_response = '{"force": "propose", "claim": {"surface": "result"}, "confidence": 0.7}'
    client = FakeModelClient(response_content=fake_response)

    ctx = CouncilContext(
        agents=agents,
        model_client=client,
        protocol=DeliberationAutomaton(max_phases=2, agents=list(agents)),
        topology=CompleteGraphTopology(n_agents=2),
        termination=FixedRounds(max_rounds=1),
        anonymize=True,
    )

    result = await run_council("Prompt", context=ctx)
    # FakeModelClient counts prompt words as input tokens
    assert result.receipt.total_input_tokens > 0


# ---------------------------------------------------------------------------
# _build_visibility_context — single anonymisation site (Constitution §10)
# ---------------------------------------------------------------------------

def test_build_visibility_context_anonymizes_when_requested() -> None:
    from council.context import CouncilContext
    from council.core import _build_visibility_context
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    from council.termination import FixedRounds
    from council.topology import CompleteGraphTopology

    agents = ("alice", "bob")
    trace = Trace().append(
        Propose(
            move_id="m0",
            agent_id="alice",
            round_index=0,
            claim=Claim(surface="42"),
        )
    )
    ctx = CouncilContext(
        agents=agents,
        model_client=FakeModelClient(),
        protocol=DeliberationAutomaton(max_phases=2, agents=list(agents)),
        topology=CompleteGraphTopology(n_agents=2),
        termination=FixedRounds(max_rounds=2),
        anonymize=True,
    )

    vis = _build_visibility_context(ctx, trace, round_index=1, agent_id="bob")
    # anonymize=True: real agent IDs must not appear in visible_moves agent_id
    # (they're stripped during rendering, not in the move itself; VisibilityContext carries flag)
    assert vis.anonymize is True
    assert vis.agent_id == "bob"


def test_build_visibility_context_no_anonymize() -> None:
    from council.context import CouncilContext
    from council.core import _build_visibility_context
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    from council.termination import FixedRounds
    from council.topology import CompleteGraphTopology

    agents = ("alice", "bob")
    ctx = CouncilContext(
        agents=agents,
        model_client=FakeModelClient(),
        protocol=DeliberationAutomaton(max_phases=2, agents=list(agents)),
        topology=CompleteGraphTopology(n_agents=2),
        termination=FixedRounds(max_rounds=2),
        anonymize=False,
    )

    vis = _build_visibility_context(ctx, Trace(), round_index=0, agent_id="alice")
    assert vis.anonymize is False


# ---------------------------------------------------------------------------
# Failure handling — agent failure → Abstain (graceful degradation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_council_handles_model_failure() -> None:
    from council.context import CouncilContext
    from council.core import run_council
    from council.dialect.moves import Abstain
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    from council.termination import FixedRounds
    from council.topology import CompleteGraphTopology

    agents = ("a1", "a2")
    client = FakeModelClient(always_fail=True)

    ctx = CouncilContext(
        agents=agents,
        model_client=client,
        protocol=DeliberationAutomaton(max_phases=2, agents=list(agents)),
        topology=CompleteGraphTopology(n_agents=2),
        termination=FixedRounds(max_rounds=1),
        anonymize=True,
    )

    result = await run_council("Prompt", context=ctx)
    # Should complete without raising; all moves are Abstain
    abstains = [m for m in result.receipt.trace.moves if isinstance(m, Abstain)]
    assert len(abstains) == 2  # 2 agents × 1 round
