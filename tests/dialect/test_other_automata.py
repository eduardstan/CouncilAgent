"""Tests for persuasion, inquiry, socratic, and composite automata."""

from __future__ import annotations

import pytest

from council.dialect.moves import Claim, Force, Propose, Vote
from council.dialect.trace import Trace


def _propose(agent: str, rid: int) -> Propose:
    return Propose(move_id=f"p_{agent}_{rid}", agent_id=agent, round_index=rid,
                   claim=Claim(surface="42"))


def _vote(agent: str, rid: int) -> Vote:
    return Vote(move_id=f"v_{agent}_{rid}", agent_id=agent, round_index=rid,
                option=Claim(surface="42"))


# ---------------------------------------------------------------------------
# Shared contract: every automaton is a ProtocolAutomaton
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls_name,kwargs", [
    ("PersuasionAutomaton", {"max_rounds": 2, "agents": ["A", "B", "C"]}),
    ("InquiryAutomaton",    {"max_rounds": 2, "agents": ["A", "B", "C"]}),
    ("SocraticAutomaton",   {"max_rounds": 3, "agents": ["A", "B", "C"]}),
])
def test_is_protocol_automaton(cls_name: str, kwargs: dict) -> None:
    import importlib
    mod_map = {
        "PersuasionAutomaton": "council.dialect.protocols.persuasion",
        "InquiryAutomaton":    "council.dialect.protocols.inquiry",
        "SocraticAutomaton":   "council.dialect.protocols.socratic",
    }
    from council.dialect.protocols.base import ProtocolAutomaton
    mod = importlib.import_module(mod_map[cls_name])
    cls = getattr(mod, cls_name)
    assert issubclass(cls, ProtocolAutomaton)


@pytest.mark.parametrize("cls_name,kwargs", [
    ("PersuasionAutomaton", {"max_rounds": 2, "agents": ["A", "B", "C"]}),
    ("InquiryAutomaton",    {"max_rounds": 2, "agents": ["A", "B", "C"]}),
    ("SocraticAutomaton",   {"max_rounds": 3, "agents": ["A", "B", "C"]}),
])
def test_empty_trace_not_terminal(cls_name: str, kwargs: dict) -> None:
    import importlib
    mod_map = {
        "PersuasionAutomaton": "council.dialect.protocols.persuasion",
        "InquiryAutomaton":    "council.dialect.protocols.inquiry",
        "SocraticAutomaton":   "council.dialect.protocols.socratic",
    }
    mod = importlib.import_module(mod_map[cls_name])
    cls = getattr(mod, cls_name)
    a = cls(**kwargs)
    assert a.is_terminal(Trace()) is False


@pytest.mark.parametrize("cls_name,kwargs", [
    ("PersuasionAutomaton", {"max_rounds": 2, "agents": ["A", "B", "C"]}),
    ("InquiryAutomaton",    {"max_rounds": 2, "agents": ["A", "B", "C"]}),
    ("SocraticAutomaton",   {"max_rounds": 3, "agents": ["A", "B", "C"]}),
])
def test_legal_forces_returns_frozenset(cls_name: str, kwargs: dict) -> None:
    import importlib
    mod_map = {
        "PersuasionAutomaton": "council.dialect.protocols.persuasion",
        "InquiryAutomaton":    "council.dialect.protocols.inquiry",
        "SocraticAutomaton":   "council.dialect.protocols.socratic",
    }
    mod = importlib.import_module(mod_map[cls_name])
    cls = getattr(mod, cls_name)
    a = cls(**kwargs)
    result = a.legal_forces(Trace(), "A")
    assert isinstance(result, frozenset)
    # immutable — §3
    with pytest.raises((TypeError, AttributeError)):
        result.add(Force.CHALLENGE)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# PersuasionAutomaton
# ---------------------------------------------------------------------------

def test_persuasion_propose_legal_at_start() -> None:
    from council.dialect.protocols.persuasion import PersuasionAutomaton
    p = PersuasionAutomaton(max_rounds=2, agents=["A", "B", "C"])
    assert Force.PROPOSE in p.legal_forces(Trace(), "A")


def test_persuasion_vote_phase_after_max_rounds() -> None:
    from council.dialect.protocols.persuasion import PersuasionAutomaton
    agents = ["A", "B", "C"]
    p = PersuasionAutomaton(max_rounds=1, agents=agents)
    # round_index=0 exists → rounds_elapsed=1 ≥ max_rounds=1
    t = Trace().append(_propose("A", 0))
    assert p.is_answer_phase(t) is True
    assert Force.VOTE in p.legal_forces(t, "A")


# ---------------------------------------------------------------------------
# InquiryAutomaton
# ---------------------------------------------------------------------------

def test_inquiry_question_legal_at_start() -> None:
    from council.dialect.protocols.inquiry import InquiryAutomaton
    i = InquiryAutomaton(max_rounds=2, agents=["A", "B"])
    assert Force.QUESTION in i.legal_forces(Trace(), "A")


def test_inquiry_terminal_after_votes() -> None:
    from council.dialect.protocols.inquiry import InquiryAutomaton
    agents = ["A", "B"]
    i = InquiryAutomaton(max_rounds=1, agents=agents)
    t = Trace().append(_propose("A", 0))
    for a in agents:
        t = t.append(_vote(a, 1))
    assert i.is_terminal(t) is True


# ---------------------------------------------------------------------------
# SocraticAutomaton
# ---------------------------------------------------------------------------

def test_socratic_question_and_clarify_legal_at_start() -> None:
    from council.dialect.protocols.socratic import SocraticAutomaton
    s = SocraticAutomaton(max_rounds=3, agents=["A", "B"])
    forces = s.legal_forces(Trace(), "A")
    assert Force.QUESTION in forces
    assert Force.CLARIFY in forces


def test_socratic_not_terminal_before_votes() -> None:
    from council.dialect.protocols.socratic import SocraticAutomaton
    agents = ["A", "B"]
    s = SocraticAutomaton(max_rounds=2, agents=agents)
    t = Trace().append(_propose("A", 0))
    assert s.is_terminal(t) is False


# ---------------------------------------------------------------------------
# CompositeAutomaton
# ---------------------------------------------------------------------------

def test_composite_requires_at_least_one_stage() -> None:
    from council.dialect.protocols.composite import CompositeAutomaton
    with pytest.raises(ValueError):
        CompositeAutomaton([])


def test_composite_delegates_to_first_active_stage() -> None:
    from council.dialect.protocols.composite import CompositeAutomaton
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    agents = ["A", "B"]
    stage1 = DeliberationAutomaton(max_phases=1, agents=agents)
    stage2 = DeliberationAutomaton(max_phases=1, agents=agents)
    comp = CompositeAutomaton([stage1, stage2])
    forces = comp.legal_forces(Trace(), "A")
    assert Force.PROPOSE in forces


def test_composite_transitions_to_second_stage() -> None:
    # stage1 needs 1*2=2 proposes; stage2 needs 3*2=6 proposes — different thresholds
    # so when stage1 is terminal (2 proposes+2 votes), stage2 is NOT terminal.
    from council.dialect.protocols.composite import CompositeAutomaton
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    agents2 = ["A", "B"]
    agents3 = ["A", "B", "C"]
    stage1 = DeliberationAutomaton(max_phases=1, agents=agents2)
    stage2 = DeliberationAutomaton(max_phases=3, agents=agents3)
    comp = CompositeAutomaton([stage1, stage2])

    # Complete stage1: 2 proposes + 2 votes
    t = Trace()
    for a in agents2:
        t = t.append(_propose(a, 0))
    for a in agents2:
        t = t.append(_vote(a, 1))
    # stage1 is terminal; stage2 needs 9 more proposes — not terminal
    assert not comp.is_terminal(t)
    forces = comp.legal_forces(t, "A")
    assert Force.PROPOSE in forces


def test_composite_is_terminal_when_last_stage_terminal() -> None:
    from council.dialect.protocols.composite import CompositeAutomaton
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    agents = ["A"]
    stage1 = DeliberationAutomaton(max_phases=1, agents=agents)
    stage2 = DeliberationAutomaton(max_phases=1, agents=agents)
    comp = CompositeAutomaton([stage1, stage2])

    # Both stages: propose + vote twice
    t = Trace()
    t = t.append(_propose("A", 0)).append(_vote("A", 1))
    t = t.append(_propose("A", 2)).append(_vote("A", 3))
    assert comp.is_terminal(t) is True
