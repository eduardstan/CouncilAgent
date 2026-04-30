"""Tests for council/dialect/surface.py — Move → NL rendering."""

from __future__ import annotations


def _all_moves() -> list:
    from council.dialect.moves import (
        Abstain,
        Challenge,
        Clarify,
        Concede,
        Propose,
        Question,
        Retract,
        Vote,
    )
    return [
        Propose(move_id="p", agent_id="agent_0", round_index=0),
        Challenge(move_id="c", agent_id="agent_1", round_index=1),
        Concede(move_id="cn", agent_id="agent_2", round_index=1),
        Retract(move_id="r", agent_id="agent_0", round_index=2),
        Question(move_id="q", agent_id="agent_1", round_index=0),
        Clarify(move_id="cl", agent_id="agent_2", round_index=1),
        Vote(move_id="v", agent_id="agent_0", round_index=2),
        Abstain(move_id="ab", agent_id="agent_1", round_index=2),
    ]


def test_render_all_variants_produce_nonempty_string() -> None:
    from council.dialect.surface import render_move
    for move in _all_moves():
        result = render_move(move)
        assert isinstance(result, str)
        assert len(result.strip()) > 0, f"render_move({type(move).__name__}) returned empty"


def test_render_propose_contains_surface() -> None:
    from council.dialect.moves import Claim, ClaimDomain, Propose
    from council.dialect.surface import render_move
    claim = Claim(surface="The answer is 42", domain=ClaimDomain.ARITH)
    p = Propose(move_id="p0", agent_id="A", round_index=0, claim=claim)
    rendered = render_move(p)
    assert "42" in rendered


def test_anonymisation_strips_agent_id() -> None:
    from council.dialect.moves import Propose
    from council.dialect.surface import render_move
    m = Propose(move_id="p0", agent_id="secret_agent_007", round_index=0)
    rendered = render_move(m, anonymize=True)
    assert "secret_agent_007" not in rendered


def test_no_anonymisation_preserves_agent_id() -> None:
    from council.dialect.moves import Propose
    from council.dialect.surface import render_move
    m = Propose(move_id="p0", agent_id="known_agent", round_index=0)
    rendered = render_move(m, anonymize=False)
    assert "known_agent" in rendered


def test_render_vote_mentions_option() -> None:
    from council.dialect.moves import Claim, Vote
    from council.dialect.surface import render_move
    v = Vote(move_id="v0", agent_id="A", round_index=2, option=Claim(surface="42"))
    rendered = render_move(v)
    assert "42" in rendered


def test_render_challenge_mentions_target() -> None:
    from council.dialect.moves import Challenge
    from council.dialect.surface import render_move
    c = Challenge(move_id="c0", agent_id="B", round_index=1, target="p0")
    rendered = render_move(c)
    assert "p0" in rendered


def test_render_challenge_renders_confidence() -> None:
    """Patch C (ADR-0006): Challenge.confidence is rendered in the surface form."""
    from council.dialect.moves import Challenge
    from council.dialect.surface import render_move
    c = Challenge(
        move_id="c0", agent_id="B", round_index=1, target="p0", confidence=0.73
    )
    rendered = render_move(c)
    assert "0.73" in rendered


def test_render_challenge_default_confidence_appears() -> None:
    from council.dialect.moves import Challenge
    from council.dialect.surface import render_move
    c = Challenge(move_id="c0", agent_id="B", round_index=1, target="p0")
    rendered = render_move(c)
    # Default is 0.5; assert it surfaces in the rendered string
    assert "0.50" in rendered
