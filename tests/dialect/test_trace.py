"""Tests for council/dialect/trace.py — immutable Trace + to_events() bridge."""

from __future__ import annotations

import dataclasses

import pytest


def _make_propose(move_id: str = "p0", agent_id: str = "A", round_index: int = 0):
    from council.dialect.moves import Claim, ClaimDomain, Propose
    return Propose(
        move_id=move_id,
        agent_id=agent_id,
        round_index=round_index,
        claim=Claim(surface="42", domain=ClaimDomain.ARITH),
    )


def _make_challenge(move_id: str = "c0", agent_id: str = "B", round_index: int = 1):
    from council.dialect.moves import Challenge
    return Challenge(move_id=move_id, agent_id=agent_id, round_index=round_index)


def _make_vote(move_id: str = "v0", agent_id: str = "C", round_index: int = 2):
    from council.dialect.moves import Claim, Vote
    return Vote(move_id=move_id, agent_id=agent_id, round_index=round_index,
                option=Claim(surface="42"))


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_empty_trace_has_no_moves() -> None:
    from council.dialect.trace import Trace
    t = Trace()
    assert t.moves == ()


def test_trace_is_frozen() -> None:
    from council.dialect.trace import Trace
    t = Trace()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        t.moves = ()  # type: ignore[misc]


def test_trace_slots() -> None:
    from council.dialect.trace import Trace
    t = Trace()
    assert not hasattr(t, "__dict__")


# ---------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------


def test_append_returns_new_trace() -> None:
    from council.dialect.trace import Trace
    t0 = Trace()
    m = _make_propose()
    t1 = t0.append(m)
    assert t1 is not t0
    assert len(t1.moves) == 1
    assert t1.moves[0] is m


def test_append_is_immutable() -> None:
    from council.dialect.trace import Trace
    t0 = Trace()
    m = _make_propose()
    _ = t0.append(m)
    assert len(t0.moves) == 0


def test_append_multiple() -> None:
    from council.dialect.trace import Trace
    t = Trace()
    m0 = _make_propose("p0", "A", 0)
    m1 = _make_challenge("c0", "B", 1)
    m2 = _make_vote("v0", "C", 2)
    t = t.append(m0).append(m1).append(m2)
    assert len(t.moves) == 3
    assert t.moves[2] is m2


# ---------------------------------------------------------------------------
# by_id
# ---------------------------------------------------------------------------


def test_by_id_finds_correct_move() -> None:
    from council.dialect.trace import Trace
    m = _make_propose("find_me", "A", 0)
    t = Trace().append(m)
    assert t.by_id("find_me") is m


def test_by_id_raises_key_error_unknown() -> None:
    from council.dialect.trace import Trace
    t = Trace()
    with pytest.raises(KeyError):
        t.by_id("nonexistent")


# ---------------------------------------------------------------------------
# at_round
# ---------------------------------------------------------------------------


def test_at_round_filters_by_index() -> None:
    from council.dialect.trace import Trace
    m0 = _make_propose("p0", "A", 0)
    m1 = _make_challenge("c0", "B", 0)
    m2 = _make_vote("v0", "C", 1)
    t = Trace().append(m0).append(m1).append(m2)
    round0 = t.at_round(0)
    assert len(round0) == 2
    assert m0 in round0 and m1 in round0
    round1 = t.at_round(1)
    assert round1 == (m2,)


def test_at_round_empty_returns_empty_tuple() -> None:
    from council.dialect.trace import Trace
    t = Trace().append(_make_propose())
    assert t.at_round(99) == ()


# ---------------------------------------------------------------------------
# by_force
# ---------------------------------------------------------------------------


def test_by_force_filters_correctly() -> None:
    from council.dialect.moves import Force
    from council.dialect.trace import Trace
    m0 = _make_propose("p0", "A", 0)
    m1 = _make_challenge("c0", "B", 1)
    m2 = _make_propose("p1", "C", 1)
    t = Trace().append(m0).append(m1).append(m2)
    proposes = t.by_force(Force.PROPOSE)
    assert len(proposes) == 2
    challenges = t.by_force(Force.CHALLENGE)
    assert len(challenges) == 1 and challenges[0] is m1


def test_by_force_no_match_returns_empty() -> None:
    from council.dialect.moves import Force
    from council.dialect.trace import Trace
    t = Trace().append(_make_propose())
    assert t.by_force(Force.VOTE) == ()


# ---------------------------------------------------------------------------
# to_events — critical W1 contract
# ---------------------------------------------------------------------------


def test_to_events_returns_tuple_of_dicts() -> None:
    from council.dialect.trace import Trace
    t = Trace().append(_make_propose()).append(_make_challenge())
    events = t.to_events()
    assert isinstance(events, tuple)
    assert all(isinstance(e, dict) for e in events)


def test_to_events_required_keys() -> None:
    from council.dialect.trace import Trace
    t = Trace().append(_make_propose("p0", "A", 0))
    event = t.to_events()[0]
    for key in ("force", "agent_id", "round_index"):
        assert key in event, f"missing key: {key}"


def test_to_events_boolean_flags_for_all_forces() -> None:
    from council.dialect.moves import Force
    from council.dialect.trace import Trace
    t = Trace().append(_make_propose())
    event = t.to_events()[0]
    for force in Force:
        flag_key = f"is_{force.value}"
        assert flag_key in event, f"missing boolean flag: {flag_key}"
        assert isinstance(event[flag_key], bool)


def test_to_events_propose_flags() -> None:
    from council.dialect.trace import Trace
    t = Trace().append(_make_propose("p0", "A", 0))
    event = t.to_events()[0]
    assert event["force"] == "propose"
    assert event["agent_id"] == "A"
    assert event["round_index"] == 0
    assert event["is_propose"] is True
    assert event["is_challenge"] is False
    assert event["is_vote"] is False


def test_to_events_three_agent_two_round_sequence() -> None:
    """Positive trace fixture for W1 LTL_f monitor tests."""
    from council.dialect.trace import Trace
    moves = [
        _make_propose("p0", "A", 0),
        _make_propose("p1", "B", 0),
        _make_propose("p2", "C", 0),
        _make_challenge("ch0", "A", 1),
        _make_vote("v0", "B", 1),
        _make_vote("v1", "C", 1),
    ]
    t = Trace()
    for m in moves:
        t = t.append(m)
    events = t.to_events()
    assert len(events) == 6
    # Round 0: all proposes
    assert all(e["is_propose"] for e in events[:3])
    # Round 1: one challenge, two votes
    r1 = [e for e in events if e["round_index"] == 1]
    assert len(r1) == 3
    assert sum(1 for e in r1 if e["is_challenge"]) == 1
    assert sum(1 for e in r1 if e["is_vote"]) == 2
