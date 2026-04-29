"""Tests for LTLfMonitorTermination + run_council() intervention loop (W1 PR8)."""

from typing import ClassVar

import pytest

from council.context import CouncilContext, ProvenanceReceipt
from council.core import run_council
from council.dialect.moves import Claim, Concede, Propose, Vote
from council.dialect.trace import Trace
from council.models import FakeModelClient
from council.symbolic.verify.interventions import (
    INTERVENTION_AGENT_ID,
    ForceChallenge,
    FreezeAndAccept,
    ReprompCorrective,
)
from council.symbolic.verify.ltlf import parse
from council.symbolic.verify.monitor import LTL3Monitor, Property, PurePythonLTL3Monitor
from council.symbolic.verify.properties import (
    EventuallyDecide,
    NoSycophancyCascade,
    ProvenanceCompleteness,
)
from council.termination import (
    CompositeTermination,
    FixedRounds,
    LTLfMonitorTermination,
    MonitorVerdict,
)
from council.topology import CompleteGraphTopology

# ---------------------------------------------------------------------------
# MonitorVerdict dataclass
# ---------------------------------------------------------------------------

def test_monitor_verdict_is_frozen() -> None:
    import dataclasses
    v = MonitorVerdict(property_name="X", verdict="top", round_index=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.verdict = "bottom"  # type: ignore[misc]


def test_provenance_receipt_accepts_monitor_verdicts() -> None:
    receipt = ProvenanceReceipt(
        trace=Trace(),
        monitor_verdicts=(MonitorVerdict("X", "top", 0),),
    )
    assert receipt.monitor_verdicts[0].property_name == "X"


# ---------------------------------------------------------------------------
# LTLfMonitorTermination — should_stop semantics
# ---------------------------------------------------------------------------

def test_ltlf_termination_no_violation_returns_false() -> None:
    """Empty trace, no violations → should_stop returns (False, "")."""
    term = LTLfMonitorTermination([EventuallyDecide()])
    assert term.should_stop(Trace(), 0) == (False, "")


def test_ltlf_termination_violation_returns_property_name() -> None:
    """Vote without prior challenge violates NoPrematureConsensus."""
    from council.symbolic.verify.properties import NoPrematureConsensus
    term = LTLfMonitorTermination([NoPrematureConsensus()])
    trace = Trace().append(
        Vote(move_id="v0", agent_id="A", round_index=0,
             option=Claim(surface="yes")),
    )
    stop, reason = term.should_stop(trace, 0)
    assert stop is True
    assert reason == "NoPrematureConsensus"


def test_ltlf_termination_collects_verdicts() -> None:
    """consume_verdicts() drains the per-step verdict accumulator."""
    term = LTLfMonitorTermination([EventuallyDecide()])
    trace = Trace().append(Propose(move_id="p", agent_id="A", round_index=0,
                                   claim=Claim(surface="x")))
    term.should_stop(trace, 0)
    verdicts = term.consume_verdicts()
    assert len(verdicts) == 1
    assert verdicts[0].property_name == "EventuallyDecide"
    assert verdicts[0].round_index == 0
    # Drained: subsequent call returns empty
    assert term.consume_verdicts() == ()


def test_ltlf_termination_pending_intervention() -> None:
    """On violation, pending_intervention() returns the configured intervention."""
    intervention = ForceChallenge()
    term = LTLfMonitorTermination([NoSycophancyCascade()], on_violation=intervention)
    # Build a trace with 3 same-agent concedes
    trace = Trace()
    for i in range(3):
        trace = trace.append(Concede(move_id=f"c{i}", agent_id="A", round_index=i))
    stop, reason = term.should_stop(trace, 0)
    assert stop is True
    assert reason == "NoSycophancyCascade"
    pending = term.pending_intervention()
    assert pending is intervention
    # Drained: subsequent call returns None
    assert term.pending_intervention() is None


def test_ltlf_termination_max_interventions_exhausted() -> None:
    """After max_interventions, should_stop returns max-interventions-exhausted."""
    term = LTLfMonitorTermination([EventuallyDecide()], max_interventions=2)
    # Manually exhaust the counter
    term.acknowledge_intervention()
    term.acknowledge_intervention()
    stop, reason = term.should_stop(Trace(), 5)
    assert stop is True
    assert reason == "max-interventions-exhausted"


def test_ltlf_termination_only_steps_new_events() -> None:
    """Subsequent should_stop calls don't re-step events seen before."""
    term = LTLfMonitorTermination([EventuallyDecide()])
    trace = Trace().append(
        Propose(move_id="p", agent_id="A", round_index=0,
                claim=Claim(surface="x")),
    )
    term.should_stop(trace, 0)
    v1 = term.consume_verdicts()
    assert len(v1) == 1

    # Same trace passed again: no new events → no new verdicts
    term.should_stop(trace, 1)
    v2 = term.consume_verdicts()
    assert len(v2) == 0


def test_ltlf_termination_resets_correctly() -> None:
    """reset() restores the initial state for monitor + counters + accumulator."""
    term = LTLfMonitorTermination([EventuallyDecide()], max_interventions=1)
    term.acknowledge_intervention()
    term.should_stop(Trace().append(Vote(move_id="v", agent_id="A", round_index=0,
                                         option=Claim(surface="y"))), 0)
    term.reset()
    assert term._intervention_count == 0
    assert term._last_event_idx == 0
    assert term._verdicts == []
    # After reset, can run again from scratch
    stop, _ = term.should_stop(Trace(), 0)
    assert stop is False


# ---------------------------------------------------------------------------
# CompositeTermination integration
# ---------------------------------------------------------------------------

def test_ltlf_termination_in_composite() -> None:
    """LTLfMonitorTermination plugs into CompositeTermination."""
    composite = CompositeTermination([
        LTLfMonitorTermination([EventuallyDecide()]),
        FixedRounds(max_rounds=2),
    ])
    # Round 0: no violation, no FixedRounds yet
    assert composite.should_stop(Trace(), 0)[0] is False
    # Round 2: FixedRounds fires
    assert composite.should_stop(Trace(), 2) == (True, "FixedRounds(2)")


# ---------------------------------------------------------------------------
# End-to-end run_council() with active monitor
# ---------------------------------------------------------------------------

def _build_ctx(termination: LTLfMonitorTermination | CompositeTermination) -> CouncilContext:
    return CouncilContext(
        agents=("A", "B"),
        model_client=FakeModelClient(),
        protocol=object(),
        topology=CompleteGraphTopology(2),
        termination=termination,
    )


@pytest.mark.asyncio
async def test_run_council_populates_monitor_verdicts() -> None:
    """ProvenanceReceipt.monitor_verdicts is populated when a monitor is active."""
    term = CompositeTermination([
        LTLfMonitorTermination([EventuallyDecide()]),
        FixedRounds(max_rounds=2),
    ])
    ctx = _build_ctx(term)
    response = await run_council("test", context=ctx)
    # Monitors stepped over each move from each round; expect non-empty verdicts
    assert len(response.receipt.monitor_verdicts) > 0
    for v in response.receipt.monitor_verdicts:
        assert v.property_name == "EventuallyDecide"
        assert v.verdict in ("top", "bottom", "unknown")


@pytest.mark.asyncio
async def test_run_council_no_monitor_verdicts_without_ltlf_termination() -> None:
    """Without LTLfMonitorTermination, monitor_verdicts stays empty (no regression)."""
    ctx = CouncilContext(
        agents=("A",),
        model_client=FakeModelClient(),
        protocol=object(),
        topology=CompleteGraphTopology(1),
        termination=FixedRounds(max_rounds=1),
    )
    response = await run_council("test", context=ctx)
    assert response.receipt.monitor_verdicts == ()


@pytest.mark.asyncio
async def test_run_council_fires_intervention_on_violation() -> None:
    """A trace that violates NoPrematureConsensus → intervention fires; trace contains
    an intervention move from the synthetic moderator agent."""
    from council.symbolic.verify.properties import NoPrematureConsensus

    # FakeModelClient always returns a Vote-shaped JSON, so the very first move
    # will be a Vote without prior Challenge → NoPrematureConsensus violated
    keyed: dict[str, str] = {}
    client = FakeModelClient(
        response_content='{"force": "vote", "option": {"surface": "yes"}}',
        keyed_responses=keyed,
    )
    term = CompositeTermination([
        LTLfMonitorTermination(
            [NoPrematureConsensus()],
            on_violation=ForceChallenge(),
            max_interventions=1,
        ),
        FixedRounds(max_rounds=4),
    ])
    ctx = CouncilContext(
        agents=("A",),
        model_client=client,
        protocol=object(),
        topology=CompleteGraphTopology(1),
        termination=term,
    )
    response = await run_council("test", context=ctx)
    # The intervention must have produced a move with the synthetic moderator agent
    intervention_moves = [m for m in response.receipt.trace.moves
                          if m.agent_id == INTERVENTION_AGENT_ID]
    assert len(intervention_moves) >= 1, (
        f"Expected at least one intervention move; got moves: "
        f"{[(m.agent_id, m.force.value) for m in response.receipt.trace.moves]}"
    )


@pytest.mark.asyncio
async def test_run_council_max_interventions_caps_loop() -> None:
    """An intervention that itself triggers further violations is capped."""
    from council.symbolic.verify.properties import NoPrematureConsensus

    client = FakeModelClient(
        response_content='{"force": "vote", "option": {"surface": "yes"}}',
    )
    term = CompositeTermination([
        LTLfMonitorTermination(
            [NoPrematureConsensus()],
            on_violation=FreezeAndAccept(),  # identity — won't make violation go away
            max_interventions=3,
        ),
        FixedRounds(max_rounds=20),
    ])
    ctx = CouncilContext(
        agents=("A",),
        model_client=client,
        protocol=object(),
        topology=CompleteGraphTopology(1),
        termination=term,
    )
    # Should not loop forever: max_interventions=3 caps the intervention applications
    response = await run_council("test", context=ctx)
    # The run completed (didn't hang)
    assert response is not None


@pytest.mark.asyncio
async def test_run_council_intervention_with_repromp_corrective() -> None:
    """ReprompCorrective injects a Question move from the moderator."""
    from council.symbolic.verify.properties import NoPrematureConsensus

    client = FakeModelClient(
        response_content='{"force": "vote", "option": {"surface": "yes"}}',
    )
    term = CompositeTermination([
        LTLfMonitorTermination(
            [NoPrematureConsensus()],
            on_violation=ReprompCorrective(),
            max_interventions=1,
        ),
        FixedRounds(max_rounds=3),
    ])
    ctx = CouncilContext(
        agents=("A",),
        model_client=client,
        protocol=object(),
        topology=CompleteGraphTopology(1),
        termination=term,
    )
    response = await run_council("test", context=ctx)
    intervention_moves = [m for m in response.receipt.trace.moves
                          if m.agent_id == INTERVENTION_AGENT_ID]
    assert len(intervention_moves) == 1
    # ReprompCorrective injects a Question
    assert intervention_moves[0].force.value == "question"


# ---------------------------------------------------------------------------
# Multi-property edge cases
# ---------------------------------------------------------------------------

def test_ltlf_termination_with_multiple_properties() -> None:
    """Two simultaneously-active monitors: each appears in collected verdicts."""
    term = LTLfMonitorTermination([EventuallyDecide(), ProvenanceCompleteness()])
    trace = Trace().append(
        Propose(move_id="p", agent_id="A", round_index=0,
                claim=Claim(surface="x", evidence=("e1",))),
    )
    term.should_stop(trace, 0)
    verdicts = term.consume_verdicts()
    names = {v.property_name for v in verdicts}
    assert names == {"EventuallyDecide", "ProvenanceCompleteness"}


def test_ltlf_termination_first_violation_wins() -> None:
    """When two monitors fire, the property name of the first BOTTOM is reported."""
    class AlwaysBottom(Property):
        name: ClassVar[str] = "AlwaysBottom"
        formula: ClassVar[str] = "G(missing_ap)"

        def compile(self) -> LTL3Monitor:
            return PurePythonLTL3Monitor(parse(self.formula))

    term = LTLfMonitorTermination([AlwaysBottom(), EventuallyDecide()])
    trace = Trace().append(
        Propose(move_id="p", agent_id="A", round_index=0,
                claim=Claim(surface="x")),
    )
    stop, reason = term.should_stop(trace, 0)
    assert stop is True
    # AlwaysBottom is checked first (and immediately violates because
    # missing_ap is False)
    assert reason == "AlwaysBottom"
