"""Tests for council/symbolic/verify/interventions.py — Intervention ABC + 5 impls."""

from typing import ClassVar

import pytest

from council.context import CouncilContext
from council.dialect.moves import (
    Abstain,
    Challenge,
    Claim,
    Clarify,
    Force,
    Propose,
    Question,
    Vote,
)
from council.dialect.trace import Trace
from council.models import FakeModelClient
from council.symbolic.verify.interventions import (
    INTERVENTION_AGENT_ID,
    EscalateModel,
    ForceChallenge,
    FreezeAndAccept,
    Intervention,
    ReprompCorrective,
    TriggerVerifier,
)
from council.symbolic.verify.monitor import LTL3Monitor, Property
from council.symbolic.verify.properties import EventuallyDecide, NoSycophancyCascade
from council.termination import FixedRounds
from council.tools import StubToolClient, ToolClient, ToolRequest, ToolResponse, ToolResult
from council.topology import CompleteGraphTopology

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_ctx(tool_client: ToolClient | None = None) -> CouncilContext:
    return CouncilContext(
        agents=("A", "B"),
        model_client=FakeModelClient(),
        protocol=object(),
        topology=CompleteGraphTopology(2),
        termination=FixedRounds(1),
        tool_client=tool_client,
    )


def _trace_with_propose(agent: str = "A") -> Trace:
    return Trace().append(
        Propose(move_id="p0", agent_id=agent, round_index=0,
                claim=Claim(surface="x")),
    )


# ---------------------------------------------------------------------------
# Intervention ABC
# ---------------------------------------------------------------------------

def test_intervention_is_abstract() -> None:
    with pytest.raises(TypeError):
        Intervention()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# ReprompCorrective
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repromp_corrective_injects_question() -> None:
    trace = _trace_with_propose("A")
    intervention = ReprompCorrective()
    result = await intervention.execute(trace, EventuallyDecide(), _make_ctx())
    assert len(result.moves) == len(trace.moves) + 1
    new_move = result.moves[-1]
    assert isinstance(new_move, Question)
    assert new_move.agent_id == INTERVENTION_AGENT_ID
    assert "EventuallyDecide" in new_move.query.surface


@pytest.mark.asyncio
async def test_repromp_corrective_targets_last_agent() -> None:
    trace = _trace_with_propose("BobAgent")
    result = await ReprompCorrective().execute(trace, EventuallyDecide(), _make_ctx())
    assert isinstance(result.moves[-1], Question)
    assert result.moves[-1].target == "BobAgent"


@pytest.mark.asyncio
async def test_repromp_corrective_empty_trace() -> None:
    """Empty trace: still injects a Question (with empty target)."""
    result = await ReprompCorrective().execute(Trace(), EventuallyDecide(), _make_ctx())
    assert len(result.moves) == 1
    assert isinstance(result.moves[0], Question)


# ---------------------------------------------------------------------------
# ForceChallenge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_force_challenge_injects_challenge() -> None:
    trace = _trace_with_propose()
    result = await ForceChallenge().execute(trace, EventuallyDecide(), _make_ctx())
    assert len(result.moves) == len(trace.moves) + 1
    new_move = result.moves[-1]
    assert isinstance(new_move, Challenge)
    assert new_move.agent_id == INTERVENTION_AGENT_ID


@pytest.mark.asyncio
async def test_force_challenge_reason_contains_property_name() -> None:
    trace = _trace_with_propose()
    result = await ForceChallenge().execute(trace, NoSycophancyCascade(), _make_ctx())
    assert isinstance(result.moves[-1], Challenge)
    assert "NoSycophancyCascade" in result.moves[-1].reason.surface


@pytest.mark.asyncio
async def test_force_challenge_targets_last_propose_move_id() -> None:
    trace = _trace_with_propose()
    result = await ForceChallenge().execute(trace, EventuallyDecide(), _make_ctx())
    assert isinstance(result.moves[-1], Challenge)
    assert result.moves[-1].target == "p0"


@pytest.mark.asyncio
async def test_force_challenge_empty_trace() -> None:
    """No Propose to challenge: target is empty but Challenge still injected."""
    result = await ForceChallenge().execute(Trace(), EventuallyDecide(), _make_ctx())
    assert len(result.moves) == 1
    assert isinstance(result.moves[0], Challenge)
    assert result.moves[0].target == ""


# ---------------------------------------------------------------------------
# TriggerVerifier
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_verifier_no_op_when_tool_client_none() -> None:
    """Without a tool_client, returns the trace unchanged."""
    trace = _trace_with_propose()
    result = await TriggerVerifier().execute(trace, EventuallyDecide(), _make_ctx(None))
    assert result == trace


@pytest.mark.asyncio
async def test_trigger_verifier_injects_clarify_with_tool_response() -> None:
    """With a tool_client returning a ToolResponse, injects a Clarify."""
    class StubResponseTool(ToolClient):
        async def call(self, request: ToolRequest) -> ToolResult:
            return ToolResponse(tool=request.tool, result="SAT", cost_usd=0.01)

    trace = _trace_with_propose()
    result = await TriggerVerifier(tool_name="z3").execute(
        trace, EventuallyDecide(), _make_ctx(StubResponseTool()),
    )
    assert len(result.moves) == len(trace.moves) + 1
    new_move = result.moves[-1]
    assert isinstance(new_move, Clarify)
    assert "z3" in new_move.restated.surface
    assert "SAT" in new_move.restated.surface


@pytest.mark.asyncio
async def test_trigger_verifier_handles_tool_failure() -> None:
    """ToolFailure result: injects Clarify with failure message."""
    trace = _trace_with_propose()
    result = await TriggerVerifier().execute(
        trace, EventuallyDecide(), _make_ctx(StubToolClient()),
    )
    assert len(result.moves) == len(trace.moves) + 1
    new_move = result.moves[-1]
    assert isinstance(new_move, Clarify)
    assert "failed" in new_move.restated.surface


# ---------------------------------------------------------------------------
# EscalateModel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_escalate_model_injects_abstain_and_propose() -> None:
    trace = _trace_with_propose("A")
    result = await EscalateModel(upgraded_model="test/upgraded-model").execute(trace, EventuallyDecide(), _make_ctx())
    assert len(result.moves) == len(trace.moves) + 2
    abstain = result.moves[-2]
    upgraded_propose = result.moves[-1]
    assert isinstance(abstain, Abstain)
    assert abstain.agent_id == "A"  # offender
    assert isinstance(upgraded_propose, Propose)
    assert upgraded_propose.agent_id == INTERVENTION_AGENT_ID


@pytest.mark.asyncio
async def test_escalate_model_propose_surface_contains_upgraded_model() -> None:
    trace = _trace_with_propose("A")
    result = await EscalateModel(upgraded_model="anthropic/claude-3.5-sonnet").execute(
        trace, EventuallyDecide(), _make_ctx(),
    )
    upgraded = result.moves[-1]
    assert isinstance(upgraded, Propose)
    assert "claude-3.5-sonnet" in upgraded.claim.surface


def test_escalate_model_requires_upgraded_model_argument() -> None:
    """EscalateModel must NOT default to a hardcoded model name.

    Per code-style.md "No hardcoded model names anywhere outside `configs/`
    and tests" — the upgraded model must be supplied explicitly so the
    decision is auditable and configurable.
    """
    with pytest.raises(TypeError):
        EscalateModel()  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_escalate_model_preserves_explicit_model_name() -> None:
    """Explicit upgraded_model is round-tripped to the injected Propose surface."""
    trace = _trace_with_propose("A")
    result = await EscalateModel(upgraded_model="openrouter/some/exotic-model").execute(
        trace, EventuallyDecide(), _make_ctx(),
    )
    upgraded = result.moves[-1]
    assert isinstance(upgraded, Propose)
    assert "openrouter/some/exotic-model" in upgraded.claim.surface


@pytest.mark.asyncio
async def test_escalate_model_empty_trace() -> None:
    """No moves: still injects Abstain + Propose with empty offender."""
    result = await EscalateModel(upgraded_model="test/upgraded-model").execute(Trace(), EventuallyDecide(), _make_ctx())
    assert len(result.moves) == 2


@pytest.mark.asyncio
async def test_escalate_model_falls_back_to_last_move_when_no_propose() -> None:
    """If no Propose exists, offender is the last move's author."""
    trace = Trace().append(Vote(move_id="v0", agent_id="X", round_index=0,
                                option=Claim(surface="yes")))
    result = await EscalateModel(upgraded_model="test/upgraded-model").execute(trace, EventuallyDecide(), _make_ctx())
    abstain = result.moves[-2]
    assert isinstance(abstain, Abstain)
    assert abstain.agent_id == "X"


# ---------------------------------------------------------------------------
# FreezeAndAccept
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_freeze_and_accept_returns_unchanged_trace() -> None:
    trace = _trace_with_propose()
    result = await FreezeAndAccept().execute(trace, EventuallyDecide(), _make_ctx())
    assert result == trace
    assert result.moves == trace.moves


@pytest.mark.asyncio
async def test_freeze_and_accept_empty_trace() -> None:
    result = await FreezeAndAccept().execute(Trace(), EventuallyDecide(), _make_ctx())
    assert result.moves == ()


# ---------------------------------------------------------------------------
# Determinism: same trace + property → same intervention move IDs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_intervention_move_id_is_deterministic() -> None:
    """Running the same intervention twice on the same input produces the same move_id."""
    trace = _trace_with_propose()
    a = await ForceChallenge().execute(trace, EventuallyDecide(), _make_ctx())
    b = await ForceChallenge().execute(trace, EventuallyDecide(), _make_ctx())
    assert a.moves[-1].move_id == b.moves[-1].move_id


# ---------------------------------------------------------------------------
# All injected moves are typed Move subclasses (Constitution §4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_interventions_inject_typed_moves_only() -> None:
    """Constitution §4: injected moves are typed, never raw text."""
    trace = _trace_with_propose()

    class StubProperty(Property):
        name: ClassVar[str] = "Stub"
        formula: ClassVar[str] = "F(p)"

        def compile(self) -> LTL3Monitor:
            from council.symbolic.verify.ltlf import parse
            from council.symbolic.verify.monitor import PurePythonLTL3Monitor
            return PurePythonLTL3Monitor(parse(self.formula))

    interventions: list[Intervention] = [
        ReprompCorrective(),
        ForceChallenge(),
        EscalateModel(upgraded_model="test/upgraded-model"),
        FreezeAndAccept(),
    ]
    for iv in interventions:
        result = await iv.execute(trace, StubProperty(), _make_ctx())
        for move in result.moves:
            assert move.force in {f for f in Force}, f"unknown force {move.force}"
