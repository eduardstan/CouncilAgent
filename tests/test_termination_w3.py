"""Tests for council.termination W3 additions:

  - ``JSDDivergenceTermination(threshold=0.05)`` — stops when JSD between
    consecutive-round confidence distributions drops below ``threshold``.
  - ``ConFreezeTermination(window=5, threshold=0.05, confidence_floor=0.0)``
    — stops when JSD has stayed below ``threshold`` for ``window``
    consecutive rounds AND mean Propose confidence ≥ ``confidence_floor``.

ADR-0019 documents the bible-vs-paper reconciliation: the Anonymous 2026
ConFreeze paper (OpenReview PrqXuAS4BZ) gates on unanimity in round 0;
the bible (`COUNCIL_NS_PLAN.md` §6.4) reinterprets this as a JSD-streak
condition with optional confidence floor, which is the operationalisation
PR5 ships under the same name.
"""

from __future__ import annotations

import pytest

from council.dialect.moves import Claim, ClaimDomain, Propose
from council.dialect.trace import Trace
from council.termination import (
    CompositeTermination,
    ConFreezeTermination,
    FixedRounds,
    JSDDivergenceTermination,
)


def _propose(
    move_id: str,
    *,
    agent_id: str,
    surface: str,
    round_index: int,
    confidence: float = 0.7,
    domain: ClaimDomain = ClaimDomain.FREE,
) -> Propose:
    return Propose(
        move_id=move_id,
        agent_id=agent_id,
        round_index=round_index,
        claim=Claim(surface=surface, domain=domain),
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# JSDDivergenceTermination
# ---------------------------------------------------------------------------


class TestJSDDivergenceTerminationBasic:
    def test_round_zero_never_fires(self) -> None:
        # No prior round → cannot compute inter-round JSD.
        term = JSDDivergenceTermination(threshold=0.05)
        trace = Trace((_propose("m0", agent_id="A", surface="x", round_index=0),))
        stop, _ = term.should_stop(trace, 0)
        assert stop is False

    def test_stops_when_consecutive_rounds_agree(self) -> None:
        # Round 0 and round 1 propose the same claim with the same agents
        # and same confidences → JSD = 0 → stop.
        trace = Trace(
            (
                _propose("m00", agent_id="A", surface="x", round_index=0),
                _propose("m01", agent_id="B", surface="x", round_index=0),
                _propose("m10", agent_id="A", surface="x", round_index=1),
                _propose("m11", agent_id="B", surface="x", round_index=1),
            )
        )
        term = JSDDivergenceTermination(threshold=0.05)
        stop, reason = term.should_stop(trace, 1)
        assert stop is True
        assert "jsd" in reason.lower()

    def test_continues_when_distributions_diverge(self) -> None:
        # Round 0 endorses x, round 1 flips to y → JSD = 1 → don't stop.
        trace = Trace(
            (
                _propose("m00", agent_id="A", surface="x", round_index=0),
                _propose("m01", agent_id="B", surface="x", round_index=0),
                _propose("m10", agent_id="A", surface="y", round_index=1),
                _propose("m11", agent_id="B", surface="y", round_index=1),
            )
        )
        term = JSDDivergenceTermination(threshold=0.05)
        stop, _ = term.should_stop(trace, 1)
        assert stop is False

    def test_threshold_is_strict_lower_bound(self) -> None:
        # JSD slightly above threshold → don't stop. A round with two
        # different claims at equal confidence yields JSD just below 0.5
        # against a unanimous prior round.
        trace = Trace(
            (
                _propose("m00", agent_id="A", surface="x", round_index=0),
                _propose("m01", agent_id="B", surface="x", round_index=0),
                _propose("m10", agent_id="A", surface="x", round_index=1),
                _propose("m11", agent_id="B", surface="y", round_index=1),
            )
        )
        # JSD between (1.0 mass on x) and (0.5/0.5 between x/y) is well
        # above 0.05 → don't stop.
        term = JSDDivergenceTermination(threshold=0.05)
        stop, _ = term.should_stop(trace, 1)
        assert stop is False

    def test_no_proposes_in_either_round_does_not_fire(self) -> None:
        # Only round 0 has proposes; round 1 is empty.
        trace = Trace((_propose("m00", agent_id="A", surface="x", round_index=0),))
        term = JSDDivergenceTermination(threshold=0.05)
        stop, _ = term.should_stop(trace, 1)
        assert stop is False

    def test_threshold_validation_rejects_invalid_values(self) -> None:
        with pytest.raises(ValueError):
            JSDDivergenceTermination(threshold=-0.1)
        with pytest.raises(ValueError):
            JSDDivergenceTermination(threshold=1.5)


# ---------------------------------------------------------------------------
# ConFreezeTermination
# ---------------------------------------------------------------------------


def _consensus_trace(rounds: int, *, surface: str = "x") -> Trace:
    """Trace with two agents agreeing on `surface` across `rounds` rounds."""
    moves: list = []
    for r in range(rounds):
        moves.append(
            _propose(f"m{r}A", agent_id="A", surface=surface, round_index=r, confidence=0.9)
        )
        moves.append(
            _propose(f"m{r}B", agent_id="B", surface=surface, round_index=r, confidence=0.85)
        )
    return Trace(tuple(moves))


class TestConFreezeTerminationBasic:
    def test_stops_after_window_of_low_jsd_rounds(self) -> None:
        # window=3, three consecutive low-JSD rounds → stop.
        # Need rounds 0, 1, 2, 3 (3 inter-round transitions all below threshold).
        trace = _consensus_trace(rounds=4)
        term = ConFreezeTermination(window=3, threshold=0.05)
        stop, reason = term.should_stop(trace, 3)
        assert stop is True
        assert "confreeze" in reason.lower()

    def test_does_not_stop_before_window_filled(self) -> None:
        # window=5, only 2 consensus rounds yet → don't stop.
        trace = _consensus_trace(rounds=2)
        term = ConFreezeTermination(window=5, threshold=0.05)
        stop, _ = term.should_stop(trace, 1)
        assert stop is False

    def test_streak_resets_on_disagreement(self) -> None:
        # Rounds 0, 1 agree (low JSD); round 2 flips; rounds 3, 4 agree again.
        # window=3 should NOT fire at round 4 because the streak only spans
        # rounds 3→4 (one transition). Need at least 3 consecutive transitions.
        moves: list = [
            _propose("m0A", agent_id="A", surface="x", round_index=0),
            _propose("m0B", agent_id="B", surface="x", round_index=0),
            _propose("m1A", agent_id="A", surface="x", round_index=1),
            _propose("m1B", agent_id="B", surface="x", round_index=1),
            # Disagreement at round 2 — JSD spike vs. round 1.
            _propose("m2A", agent_id="A", surface="y", round_index=2),
            _propose("m2B", agent_id="B", surface="y", round_index=2),
            _propose("m3A", agent_id="A", surface="y", round_index=3),
            _propose("m3B", agent_id="B", surface="y", round_index=3),
            _propose("m4A", agent_id="A", surface="y", round_index=4),
            _propose("m4B", agent_id="B", surface="y", round_index=4),
        ]
        trace = Trace(tuple(moves))
        # Transitions: 0→1 low, 1→2 high (reset), 2→3 low, 3→4 low.
        # Trailing streak length at round 4 = 2 (transitions 2→3 and 3→4).
        term = ConFreezeTermination(window=3, threshold=0.05)
        stop, _ = term.should_stop(trace, 4)
        assert stop is False

    def test_default_window_is_five(self) -> None:
        # Per spec Q4: ConFreezeTermination defaults to window=5.
        term = ConFreezeTermination()
        assert term.window == 5

    def test_confidence_floor_blocks_termination(self) -> None:
        # Even with low JSD across the window, if mean confidence is below
        # the floor we don't freeze.
        moves: list = []
        for r in range(4):
            moves.append(
                _propose(f"m{r}A", agent_id="A", surface="x", round_index=r, confidence=0.2)
            )
            moves.append(
                _propose(f"m{r}B", agent_id="B", surface="x", round_index=r, confidence=0.2)
            )
        trace = Trace(tuple(moves))
        # JSD = 0 across rounds (full agreement), but confidence = 0.2.
        term = ConFreezeTermination(window=3, threshold=0.05, confidence_floor=0.5)
        stop, _ = term.should_stop(trace, 3)
        assert stop is False

    def test_confidence_floor_zero_default_does_not_block(self) -> None:
        # Default floor=0.0 → any positive confidence passes the gate.
        term = ConFreezeTermination(window=3, threshold=0.05)
        assert term.confidence_floor == 0.0
        trace = _consensus_trace(rounds=4)
        stop, _ = term.should_stop(trace, 3)
        assert stop is True

    def test_window_validation_rejects_invalid_values(self) -> None:
        with pytest.raises(ValueError):
            ConFreezeTermination(window=0)
        with pytest.raises(ValueError):
            ConFreezeTermination(window=-1)

    def test_threshold_and_floor_validation(self) -> None:
        with pytest.raises(ValueError):
            ConFreezeTermination(window=5, threshold=-0.01)
        with pytest.raises(ValueError):
            ConFreezeTermination(window=5, threshold=1.01)
        with pytest.raises(ValueError):
            ConFreezeTermination(window=5, confidence_floor=-0.01)
        with pytest.raises(ValueError):
            ConFreezeTermination(window=5, confidence_floor=1.01)


# ---------------------------------------------------------------------------
# Composition with CompositeTermination
# ---------------------------------------------------------------------------


class TestCompositionWithFixedRounds:
    def test_jsd_termination_composes_into_composite(self) -> None:
        # Composite of {JSD, FixedRounds(10)} fires on JSD first.
        trace = _consensus_trace(rounds=2)
        comp = CompositeTermination(
            [JSDDivergenceTermination(threshold=0.05), FixedRounds(max_rounds=10)]
        )
        stop, reason = comp.should_stop(trace, 1)
        assert stop is True
        # First firing strategy wins; should be JSD, not FixedRounds.
        assert "jsd" in reason.lower()

    def test_confreeze_termination_composes_into_composite(self) -> None:
        trace = _consensus_trace(rounds=4)
        comp = CompositeTermination(
            [ConFreezeTermination(window=3, threshold=0.05), FixedRounds(max_rounds=10)]
        )
        stop, reason = comp.should_stop(trace, 3)
        assert stop is True
        assert "confreeze" in reason.lower()

    def test_composite_falls_through_to_fixed_rounds_when_jsd_does_not_fire(self) -> None:
        # Trace with no inter-round consensus — JSD doesn't fire, FixedRounds does.
        moves: list = []
        for r in range(4):
            # Alternate surfaces by round so JSD stays high.
            surface = "x" if r % 2 == 0 else "y"
            moves.append(
                _propose(f"m{r}A", agent_id="A", surface=surface, round_index=r)
            )
        trace = Trace(tuple(moves))
        comp = CompositeTermination(
            [JSDDivergenceTermination(threshold=0.05), FixedRounds(max_rounds=2)]
        )
        stop, reason = comp.should_stop(trace, 2)
        assert stop is True
        assert "fixedrounds" in reason.lower() or "2" in reason
