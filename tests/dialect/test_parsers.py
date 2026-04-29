"""Tests for council/dialect/parsers.py — LLM output → Move."""

from __future__ import annotations

import json

import pytest


def _json_move(force: str, agent_id: str = "A", round_index: int = 0, **extra: object) -> str:
    base = {"force": force, "agent_id": agent_id, "round_index": round_index}
    base.update(extra)
    return json.dumps(base)


# ---------------------------------------------------------------------------
# Happy path — structured JSON
# ---------------------------------------------------------------------------


def test_parse_propose_from_json() -> None:
    from council.dialect.moves import Force, Propose
    from council.dialect.parsers import parse_move
    raw = _json_move("propose", claim_surface="The answer is 42", confidence=0.9)
    move = parse_move(raw, agent_id="A", round_index=0, move_id="m0")
    assert isinstance(move, Propose)
    assert move.force == Force.PROPOSE
    assert move.claim.surface == "The answer is 42"
    assert move.confidence == 0.9


def test_parse_challenge_from_json() -> None:
    from council.dialect.moves import Challenge, Force
    from council.dialect.parsers import parse_move
    raw = _json_move("challenge", target="m0", reason_surface="Incorrect reasoning")
    move = parse_move(raw, agent_id="B", round_index=1, move_id="m1")
    assert isinstance(move, Challenge)
    assert move.force == Force.CHALLENGE
    assert move.target == "m0"


def test_parse_vote_from_json() -> None:
    from council.dialect.moves import Force, Vote
    from council.dialect.parsers import parse_move
    raw = _json_move("vote", option_surface="42", confidence=0.8)
    move = parse_move(raw, agent_id="C", round_index=2, move_id="m2")
    assert isinstance(move, Vote)
    assert move.force == Force.VOTE
    assert move.confidence == 0.8


def test_parse_concede_from_json() -> None:
    from council.dialect.moves import Concede
    from council.dialect.parsers import parse_move
    raw = _json_move("concede", target="m0")
    move = parse_move(raw, agent_id="A", round_index=1, move_id="m3")
    assert isinstance(move, Concede)


def test_parse_abstain_from_json() -> None:
    from council.dialect.moves import Abstain
    from council.dialect.parsers import parse_move
    raw = _json_move("abstain", why="Insufficient context")
    move = parse_move(raw, agent_id="B", round_index=2, move_id="m4")
    assert isinstance(move, Abstain)
    assert move.why == "Insufficient context"


# ---------------------------------------------------------------------------
# Fallback path — malformed / unknown input → Propose FREE
# ---------------------------------------------------------------------------


def test_malformed_json_triggers_fallback() -> None:
    from council.dialect.moves import ClaimDomain, Force, Propose
    from council.dialect.parsers import parse_move
    move = parse_move("not valid json{{", agent_id="A", round_index=0, move_id="f0")
    assert isinstance(move, Propose)
    assert move.force == Force.PROPOSE
    assert move.claim.domain == ClaimDomain.FREE


def test_fallback_move_tagged_tier() -> None:
    from council.dialect.parsers import FALLBACK_TIER, parse_move
    move = parse_move("not json", agent_id="A", round_index=0, move_id="f1")
    assert move.claim.surface == FALLBACK_TIER or move.claim.evidence == (FALLBACK_TIER,)


def test_unknown_force_triggers_fallback() -> None:
    from council.dialect.moves import ClaimDomain, Propose
    from council.dialect.parsers import parse_move
    raw = _json_move("invent_a_new_force")
    move = parse_move(raw, agent_id="A", round_index=0, move_id="f2")
    assert isinstance(move, Propose)
    assert move.claim.domain == ClaimDomain.FREE


def test_empty_string_triggers_fallback() -> None:
    from council.dialect.moves import Propose
    from council.dialect.parsers import parse_move
    move = parse_move("", agent_id="A", round_index=0, move_id="f3")
    assert isinstance(move, Propose)


# ---------------------------------------------------------------------------
# parse_move_bundle — list of moves from one LLM turn
# ---------------------------------------------------------------------------


def test_parse_move_bundle_single() -> None:
    from council.dialect.parsers import parse_move_bundle
    raw = json.dumps([{"force": "propose", "claim_surface": "42"}])
    moves = parse_move_bundle(raw, agent_id="A", round_index=0)
    assert len(moves) == 1


def test_parse_move_bundle_empty_returns_fallback() -> None:
    from council.dialect.moves import Propose
    from council.dialect.parsers import parse_move_bundle
    moves = parse_move_bundle("[]", agent_id="A", round_index=0)
    assert len(moves) == 1
    assert isinstance(moves[0], Propose)


def test_parse_move_bundle_invalid_json_returns_fallback() -> None:
    from council.dialect.moves import Propose
    from council.dialect.parsers import parse_move_bundle
    moves = parse_move_bundle("{{bad", agent_id="A", round_index=0)
    assert len(moves) >= 1
    assert all(isinstance(m, Propose) for m in moves)
