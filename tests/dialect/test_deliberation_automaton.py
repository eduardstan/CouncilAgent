"""Tests for DeliberationAutomaton — Walton 2010 deliberation dialogue."""

from __future__ import annotations

import pytest

from council.dialect.moves import Claim, ClaimDomain, Force, Propose, Vote
from council.dialect.trace import Trace


def _propose(agent: str, rid: int, mid: str | None = None) -> Propose:
    return Propose(
        move_id=mid or f"p_{agent}_{rid}",
        agent_id=agent,
        round_index=rid,
        claim=Claim(surface="42", domain=ClaimDomain.ARITH),
    )


def _vote(agent: str, rid: int) -> Vote:
    return Vote(
        move_id=f"v_{agent}_{rid}",
        agent_id=agent,
        round_index=rid,
        option=Claim(surface="42"),
    )


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------


def test_deliberation_automaton_instantiates() -> None:
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    d = DeliberationAutomaton(max_phases=3, agents=["A", "B", "C"])
    assert d is not None


def test_is_protocol_automaton() -> None:
    from council.dialect.protocols.base import ProtocolAutomaton
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    assert issubclass(DeliberationAutomaton, ProtocolAutomaton)


# ---------------------------------------------------------------------------
# Empty trace
# ---------------------------------------------------------------------------


def test_empty_trace_state_is_open() -> None:
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    d = DeliberationAutomaton(max_phases=3, agents=["A", "B", "C"])
    name, phase = d.state(Trace())
    assert isinstance(name, str) and isinstance(phase, str)


def test_empty_trace_legal_forces_include_propose() -> None:
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    d = DeliberationAutomaton(max_phases=3, agents=["A", "B", "C"])
    forces = d.legal_forces(Trace(), "A")
    assert Force.PROPOSE in forces


def test_empty_trace_not_terminal() -> None:
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    d = DeliberationAutomaton(max_phases=3, agents=["A", "B", "C"])
    assert d.is_terminal(Trace()) is False


def test_empty_trace_not_answer_phase() -> None:
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    d = DeliberationAutomaton(max_phases=3, agents=["A", "B", "C"])
    assert d.is_answer_phase(Trace()) is False


# ---------------------------------------------------------------------------
# Answer phase derivation — NO round_index % 2
# ---------------------------------------------------------------------------


def test_answer_phase_after_max_phases_proposes() -> None:
    """After max_phases*n_agents Propose moves, we enter the answer phase."""
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    agents = ["A", "B", "C"]
    d = DeliberationAutomaton(max_phases=1, agents=agents)
    t = Trace()
    for agent in agents:
        t = t.append(_propose(agent, 0))
    assert d.is_answer_phase(t) is True


def test_answer_phase_is_not_based_on_round_parity() -> None:
    """Prove is_answer_phase is NOT just round_index % 2.

    With max_phases=2, after round 0 proposes and round 1 challenges,
    the answer phase should NOT be active — but round_index=1 % 2 would
    incorrectly say it is.
    """
    from council.dialect.moves import Challenge
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    agents = ["A", "B", "C"]
    d = DeliberationAutomaton(max_phases=2, agents=agents)
    t = Trace()
    for agent in agents:
        t = t.append(_propose(agent, 0))
    # Add a Challenge in round 1 — answer phase should still be False
    t = t.append(Challenge(move_id="ch", agent_id="B", round_index=1))
    # round_index=1 is odd, so %2 would say NOT answer — but max_phases=2
    # means we need 2 full propose rounds before votes.
    assert d.is_answer_phase(t) is False


# ---------------------------------------------------------------------------
# Terminal detection
# ---------------------------------------------------------------------------


def test_terminal_after_all_vote() -> None:
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    agents = ["A", "B", "C"]
    d = DeliberationAutomaton(max_phases=1, agents=agents)
    t = Trace()
    for agent in agents:
        t = t.append(_propose(agent, 0))
    for agent in agents:
        t = t.append(_vote(agent, 1))
    assert d.is_terminal(t) is True


def test_not_terminal_before_votes() -> None:
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    agents = ["A", "B", "C"]
    d = DeliberationAutomaton(max_phases=1, agents=agents)
    t = Trace()
    for agent in agents:
        t = t.append(_propose(agent, 0))
    assert d.is_terminal(t) is False


# ---------------------------------------------------------------------------
# legal_forces immutability (Constitution §3)
# ---------------------------------------------------------------------------


def test_legal_forces_immutable() -> None:
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    d = DeliberationAutomaton(max_phases=2, agents=["A", "B"])
    result = d.legal_forces(Trace(), "A")
    assert isinstance(result, frozenset)
    with pytest.raises((TypeError, AttributeError)):
        result.add(Force.ABSTAIN)  # type: ignore[attr-defined]
