"""Tests for council/dialect/moves.py — typed Move ADT."""

from __future__ import annotations

import dataclasses
import json
from typing import get_args

import pytest


def test_force_is_str_enum() -> None:
    from council.dialect.moves import Force
    for member in Force:
        assert isinstance(member.value, str)
        assert str(member) == member.value


def test_force_has_nine_values() -> None:
    from council.dialect.moves import Force
    assert len(Force) == 9


def test_force_pass_exists() -> None:
    from council.dialect.moves import Force
    assert Force.PASS == "pass"


def test_force_all_expected_names() -> None:
    from council.dialect.moves import Force
    expected = {
        "PROPOSE", "CHALLENGE", "CONCEDE", "RETRACT",
        "QUESTION", "CLARIFY", "VOTE", "ABSTAIN", "PASS",
    }
    assert {m.name for m in Force} == expected


def test_claim_domain_values() -> None:
    from council.dialect.moves import ClaimDomain
    expected = {"FOL", "LTLF", "ARITH", "CODE", "FREE"}
    assert {m.name for m in ClaimDomain} == expected


def test_claim_frozen() -> None:
    from council.dialect.moves import Claim, ClaimDomain
    c = Claim(surface="x = 42", domain=ClaimDomain.ARITH)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        c.surface = "mutated"  # type: ignore[misc]


def test_claim_slots() -> None:
    from council.dialect.moves import Claim
    c = Claim(surface="hello")
    assert not hasattr(c, "__dict__"), "slots=True means no __dict__"


def test_claim_round_trip_json() -> None:
    from council.dialect.moves import Claim, ClaimDomain
    c = Claim(
        surface="x + y = 72",
        formula="x + y = 72",
        domain=ClaimDomain.ARITH,
        evidence=("step1", "step2"),
    )
    as_dict = dataclasses.asdict(c)
    as_json = json.dumps(as_dict)
    restored = json.loads(as_json)
    assert restored["surface"] == c.surface
    assert restored["domain"] == "arith"
    assert restored["evidence"] == ["step1", "step2"]


def test_claim_defaults() -> None:
    from council.dialect.moves import Claim, ClaimDomain
    c = Claim(surface="hello")
    assert c.formula is None
    assert c.domain == ClaimDomain.FREE
    assert c.evidence == ()


@pytest.mark.parametrize(
    "move_cls,kwargs",
    [
        ("Propose",   {"move_id": "m1", "agent_id": "A", "round_index": 0}),
        ("Challenge", {"move_id": "m2", "agent_id": "B", "round_index": 1}),
        ("Concede",   {"move_id": "m3", "agent_id": "C", "round_index": 1}),
        ("Retract",   {"move_id": "m4", "agent_id": "A", "round_index": 2}),
        ("Question",  {"move_id": "m5", "agent_id": "B", "round_index": 0}),
        ("Clarify",   {"move_id": "m6", "agent_id": "C", "round_index": 1}),
        ("Vote",      {"move_id": "m7", "agent_id": "A", "round_index": 2}),
        ("Abstain",   {"move_id": "m8", "agent_id": "B", "round_index": 2}),
    ],
)
def test_move_variant_is_frozen(move_cls: str, kwargs: dict) -> None:
    import council.dialect.moves as m
    cls = getattr(m, move_cls)
    instance = cls(**kwargs)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        instance.agent_id = "mutated"  # type: ignore[misc]


@pytest.mark.parametrize(
    "move_cls,kwargs",
    [
        ("Propose",   {"move_id": "m1", "agent_id": "A", "round_index": 0}),
        ("Challenge", {"move_id": "m2", "agent_id": "B", "round_index": 1}),
        ("Concede",   {"move_id": "m3", "agent_id": "C", "round_index": 1}),
        ("Retract",   {"move_id": "m4", "agent_id": "A", "round_index": 2}),
        ("Question",  {"move_id": "m5", "agent_id": "B", "round_index": 0}),
        ("Clarify",   {"move_id": "m6", "agent_id": "C", "round_index": 1}),
        ("Vote",      {"move_id": "m7", "agent_id": "A", "round_index": 2}),
        ("Abstain",   {"move_id": "m8", "agent_id": "B", "round_index": 2}),
    ],
)
def test_move_variant_has_slots(move_cls: str, kwargs: dict) -> None:
    import council.dialect.moves as m
    cls = getattr(m, move_cls)
    instance = cls(**kwargs)
    assert not hasattr(instance, "__dict__"), f"{move_cls} must use __slots__"


def test_move_union_has_eight_members() -> None:
    from council.dialect.moves import Move
    assert len(get_args(Move)) == 8


def test_move_union_match_exhaustive() -> None:
    from council.dialect.moves import (
        Abstain,
        Challenge,
        Clarify,
        Concede,
        Move,
        Propose,
        Question,
        Retract,
        Vote,
    )

    def _dispatch(move: Move) -> str:
        match move:
            case Propose():
                return "propose"
            case Challenge():
                return "challenge"
            case Concede():
                return "concede"
            case Retract():
                return "retract"
            case Question():
                return "question"
            case Clarify():
                return "clarify"
            case Vote():
                return "vote"
            case Abstain():
                return "abstain"

    sample: list[Move] = [
        Propose(move_id="p", agent_id="A", round_index=0),
        Challenge(move_id="c", agent_id="B", round_index=0),
        Concede(move_id="cn", agent_id="C", round_index=1),
        Retract(move_id="r", agent_id="A", round_index=1),
        Question(move_id="q", agent_id="B", round_index=0),
        Clarify(move_id="cl", agent_id="C", round_index=1),
        Vote(move_id="v", agent_id="A", round_index=2),
        Abstain(move_id="ab", agent_id="B", round_index=2),
    ]
    results = {_dispatch(m) for m in sample}
    assert results == {
        "propose", "challenge", "concede", "retract",
        "question", "clarify", "vote", "abstain",
    }


def test_propose_default_force() -> None:
    from council.dialect.moves import Force, Propose
    m = Propose(move_id="x", agent_id="A", round_index=0)
    assert m.force == Force.PROPOSE


def test_vote_default_force() -> None:
    from council.dialect.moves import Force, Vote
    m = Vote(move_id="x", agent_id="A", round_index=0)
    assert m.force == Force.VOTE


def test_abstain_default_force() -> None:
    from council.dialect.moves import Abstain, Force
    m = Abstain(move_id="x", agent_id="A", round_index=0)
    assert m.force == Force.ABSTAIN


def test_propose_has_claim_and_confidence() -> None:
    from council.dialect.moves import Claim, ClaimDomain, Propose
    claim = Claim(surface="The answer is 42", domain=ClaimDomain.ARITH)
    p = Propose(move_id="p1", agent_id="agent_0", round_index=0, claim=claim, confidence=0.9)
    assert p.claim.surface == "The answer is 42"
    assert p.confidence == 0.9


def test_propose_default_confidence() -> None:
    from council.dialect.moves import Propose
    p = Propose(move_id="p1", agent_id="A", round_index=0)
    assert p.confidence == 0.5


def test_vote_confidence_default() -> None:
    from council.dialect.moves import Vote
    v = Vote(move_id="v1", agent_id="A", round_index=2)
    assert v.confidence == 0.5
