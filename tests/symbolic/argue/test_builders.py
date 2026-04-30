"""Tests for council/symbolic/argue/builders.build_qbaf.

build_qbaf is a deterministic pure function: Trace → QBAF. Tests are organised
by the bible §6.3 construction rules:

  - Every Propose → an argument node (arg_id == Propose.move_id).
  - Every Challenge → attack edge (Slice C).
  - Every Concede → support edge (Slice C).
  - Every Retract → mark argument withdrawn (Slice C).
  - Every Vote → base-score boost on matching Propose (clamped to [0, 1]).

This file is grown across slices B, C, D. Slice B covers Propose, Vote, the
calibrator hook, and determinism over Propose-only traces. Slice C extends
with Challenge / Concede / Retract. Slice D adds the Walton-Krabbe golden
fixture and the full multi-move determinism round-trip.
"""

from __future__ import annotations

import pytest

from council.calibrate import Calibrator, IdentityCalibrator
from council.dialect.moves import Claim, ClaimDomain, Propose, Vote
from council.dialect.trace import Trace
from council.symbolic.argue.baf import QBAF
from council.symbolic.argue.builders import build_qbaf

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _propose(
    move_id: str,
    *,
    agent_id: str = "A",
    round_index: int = 0,
    surface: str = "claim",
    domain: ClaimDomain = ClaimDomain.FREE,
    confidence: float = 0.5,
) -> Propose:
    return Propose(
        move_id=move_id,
        agent_id=agent_id,
        round_index=round_index,
        claim=Claim(surface=surface, domain=domain),
        confidence=confidence,
    )


def _vote(
    move_id: str,
    *,
    agent_id: str = "A",
    round_index: int = 0,
    surface: str = "claim",
    confidence: float = 0.5,
) -> Vote:
    return Vote(
        move_id=move_id,
        agent_id=agent_id,
        round_index=round_index,
        option=Claim(surface=surface),
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Empty / minimal cases
# ---------------------------------------------------------------------------


class TestBuildQBAFEmpty:
    def test_empty_trace_produces_empty_qbaf(self) -> None:
        baf = build_qbaf(Trace())
        assert baf == QBAF(arguments=(), attacks=(), supports=())

    def test_returns_qbaf_instance(self) -> None:
        baf = build_qbaf(Trace())
        assert isinstance(baf, QBAF)

    def test_calibrator_none_default(self) -> None:
        # Signature: build_qbaf(trace, calibrator=None) — calibrator is optional
        baf = build_qbaf(Trace(), calibrator=None)
        assert baf.arguments == ()


# ---------------------------------------------------------------------------
# Propose → Argument
# ---------------------------------------------------------------------------


class TestProposeToArgument:
    def test_single_propose_yields_single_argument(self) -> None:
        trace = Trace().append(_propose("p1"))
        baf = build_qbaf(trace)
        assert len(baf.arguments) == 1

    def test_argument_id_equals_propose_move_id(self) -> None:
        trace = Trace().append(_propose("p1-uuid"))
        baf = build_qbaf(trace)
        assert baf.arguments[0].arg_id == "p1-uuid"

    def test_argument_claim_surface_copied_from_propose(self) -> None:
        trace = Trace().append(_propose("p1", surface="The answer is 42"))
        baf = build_qbaf(trace)
        assert baf.arguments[0].claim_surface == "The answer is 42"

    def test_argument_base_score_equals_propose_confidence(self) -> None:
        trace = Trace().append(_propose("p1", confidence=0.7))
        baf = build_qbaf(trace)
        assert baf.arguments[0].base_score == 0.7

    def test_argument_not_withdrawn_initially(self) -> None:
        trace = Trace().append(_propose("p1"))
        baf = build_qbaf(trace)
        assert baf.arguments[0].withdrawn is False

    def test_multiple_proposes_yield_multiple_arguments(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="A"))
            .append(_propose("p2", surface="B"))
            .append(_propose("p3", surface="C"))
        )
        baf = build_qbaf(trace)
        assert len(baf.arguments) == 3

    def test_argument_order_matches_propose_order(self) -> None:
        trace = (
            Trace()
            .append(_propose("p3", surface="third"))
            .append(_propose("p1", surface="first"))
            .append(_propose("p2", surface="second"))
        )
        baf = build_qbaf(trace)
        assert [a.arg_id for a in baf.arguments] == ["p3", "p1", "p2"]


# ---------------------------------------------------------------------------
# Calibrator hook
# ---------------------------------------------------------------------------


class _ConstantCalibrator(Calibrator):
    """Test-only: every confidence is mapped to a constant."""

    def __init__(self, value: float) -> None:
        self._value = value

    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float:
        return self._value


class _PerDomainCalibrator(Calibrator):
    """Test-only: returns 1.0 for ARITH, 0.0 otherwise — exposes domain dispatch."""

    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float:
        return 1.0 if claim_domain == ClaimDomain.ARITH else 0.0


class TestCalibratorHook:
    def test_identity_calibrator_byte_equal_to_no_calibrator(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="A", confidence=0.42))
            .append(_propose("p2", surface="B", confidence=0.71))
        )
        baf_no_calib = build_qbaf(trace)
        baf_identity = build_qbaf(trace, calibrator=IdentityCalibrator())
        assert baf_no_calib == baf_identity

    def test_constant_calibrator_overrides_propose_confidence(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", confidence=0.1))
            .append(_propose("p2", confidence=0.9))
        )
        baf = build_qbaf(trace, calibrator=_ConstantCalibrator(0.42))
        for arg in baf.arguments:
            assert arg.base_score == 0.42

    def test_calibrator_receives_propose_metadata(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="2+2=4", domain=ClaimDomain.ARITH))
            .append(_propose("p2", surface="hello", domain=ClaimDomain.FREE))
        )
        baf = build_qbaf(trace, calibrator=_PerDomainCalibrator())
        scores = {a.arg_id: a.base_score for a in baf.arguments}
        assert scores["p1"] == 1.0  # ARITH
        assert scores["p2"] == 0.0  # FREE


# ---------------------------------------------------------------------------
# Vote → base-score boost
# ---------------------------------------------------------------------------


class TestVoteBoost:
    def test_vote_with_matching_surface_boosts_score(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="42", confidence=0.5))
            .append(_vote("v1", surface="42", confidence=0.4))
        )
        baf = build_qbaf(trace)
        # Boost: base_score + vote.confidence, clamped to [0, 1]
        assert baf.arguments[0].base_score == 0.9

    def test_vote_with_non_matching_surface_does_not_boost(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="42", confidence=0.5))
            .append(_vote("v1", surface="99", confidence=0.4))
        )
        baf = build_qbaf(trace)
        assert baf.arguments[0].base_score == 0.5  # no boost

    def test_vote_boost_clamped_to_one(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="42", confidence=0.7))
            .append(_vote("v1", surface="42", confidence=0.9))
        )
        baf = build_qbaf(trace)
        assert baf.arguments[0].base_score == 1.0  # 0.7 + 0.9 = 1.6 → clamped

    def test_multiple_matching_votes_sum_boosts(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="42", confidence=0.1))
            .append(_vote("v1", surface="42", confidence=0.2))
            .append(_vote("v2", surface="42", confidence=0.3))
        )
        baf = build_qbaf(trace)
        # 0.1 + 0.2 + 0.3 = 0.6
        assert baf.arguments[0].base_score == pytest.approx(0.6)

    def test_vote_with_no_propose_creates_no_argument(self) -> None:
        # Vote-only trace produces empty QBAF — votes only boost existing
        # Proposes; they don't create arguments themselves. This matches
        # bible §6.3 ("every Propose → an argument node").
        trace = Trace().append(_vote("v1", surface="42", confidence=0.5))
        baf = build_qbaf(trace)
        assert baf.arguments == ()

    def test_vote_boost_applies_after_calibrator(self) -> None:
        # The calibrator sets the base score; votes boost on top of that.
        trace = (
            Trace()
            .append(_propose("p1", surface="42", confidence=0.99))
            .append(_vote("v1", surface="42", confidence=0.3))
        )
        baf = build_qbaf(trace, calibrator=_ConstantCalibrator(0.2))
        # calibrated 0.2 + vote 0.3 = 0.5
        assert baf.arguments[0].base_score == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Determinism (Propose / Vote subset; full coverage in Slice D)
# ---------------------------------------------------------------------------


class TestDeterminismCore:
    def test_same_trace_yields_byte_equal_qbaf(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="A", confidence=0.4))
            .append(_propose("p2", surface="B", confidence=0.6))
            .append(_vote("v1", surface="A", confidence=0.2))
        )
        baf1 = build_qbaf(trace)
        for _ in range(10):
            assert build_qbaf(trace) == baf1
