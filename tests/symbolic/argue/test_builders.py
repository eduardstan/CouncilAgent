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

import json
from pathlib import Path

import pytest

from council.calibrate import Calibrator, IdentityCalibrator
from council.dialect.moves import (
    Challenge,
    Claim,
    ClaimDomain,
    Concede,
    Propose,
    Retract,
    Vote,
)
from council.dialect.parsers import parse_move
from council.dialect.trace import Trace
from council.symbolic.argue.baf import QBAF, Argument, Attack, Support
from council.symbolic.argue.builders import build_qbaf

FIXTURES_DIR = Path(__file__).parent / "fixtures"

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


# ---------------------------------------------------------------------------
# Slice C — Challenge → Argument + Attack edge (ADR-0009)
# ---------------------------------------------------------------------------


def _challenge(
    move_id: str,
    *,
    agent_id: str = "B",
    round_index: int = 1,
    target: str = "p1",
    reason_surface: str = "bad reasoning",
    confidence: float = 0.5,
) -> Challenge:
    return Challenge(
        move_id=move_id,
        agent_id=agent_id,
        round_index=round_index,
        target=target,
        reason=Claim(surface=reason_surface),
        confidence=confidence,
    )


def _concede(
    move_id: str,
    *,
    agent_id: str = "C",
    round_index: int = 1,
    target: str = "p1",
) -> Concede:
    return Concede(
        move_id=move_id,
        agent_id=agent_id,
        round_index=round_index,
        target=target,
    )


def _retract(
    move_id: str,
    *,
    agent_id: str = "A",
    round_index: int = 1,
    own: str = "p1",
) -> Retract:
    return Retract(
        move_id=move_id,
        agent_id=agent_id,
        round_index=round_index,
        own=own,
    )


class TestChallengeToAttack:
    def test_challenge_with_known_target_produces_argument_and_attack(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X", confidence=0.6))
            .append(_challenge("c1", target="p1", confidence=0.7))
        )
        baf = build_qbaf(trace)
        # Two arguments: p1 (Propose-derived) + c1 (Challenge-derived)
        ids = {a.arg_id for a in baf.arguments}
        assert ids == {"p1", "c1"}
        # One attack: c1 -> p1
        assert len(baf.attacks) == 1
        assert baf.attacks[0].source == "c1"
        assert baf.attacks[0].target == "p1"

    def test_challenge_attack_weight_equals_challenge_confidence(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_challenge("c1", target="p1", confidence=0.83))
        )
        baf = build_qbaf(trace)
        assert baf.attacks[0].weight == pytest.approx(0.83)

    def test_challenge_argument_carries_reason_surface(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_challenge("c1", target="p1", reason_surface="cited paper retracted"))
        )
        baf = build_qbaf(trace)
        c_arg = next(a for a in baf.arguments if a.arg_id == "c1")
        assert c_arg.claim_surface == "cited paper retracted"

    def test_challenge_argument_base_score_equals_challenge_confidence(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_challenge("c1", target="p1", confidence=0.62))
        )
        baf = build_qbaf(trace)
        c_arg = next(a for a in baf.arguments if a.arg_id == "c1")
        assert c_arg.base_score == pytest.approx(0.62)

    def test_challenge_with_unknown_target_dropped(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_challenge("c1", target="ghost", confidence=0.7))
        )
        baf = build_qbaf(trace)
        # Drop entirely — no Argument, no Attack
        ids = {a.arg_id for a in baf.arguments}
        assert "c1" not in ids
        assert baf.attacks == ()

    def test_challenge_of_a_challenge_chains(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X", confidence=0.5))
            .append(_challenge("c1", target="p1", confidence=0.7))
            .append(_challenge("c2", target="c1", confidence=0.6))
        )
        baf = build_qbaf(trace)
        ids = {a.arg_id for a in baf.arguments}
        assert ids == {"p1", "c1", "c2"}
        # Two attacks: c1 -> p1, c2 -> c1
        attack_pairs = {(a.source, a.target) for a in baf.attacks}
        assert attack_pairs == {("c1", "p1"), ("c2", "c1")}


# ---------------------------------------------------------------------------
# Slice C — Concede → Argument + Support edge
# ---------------------------------------------------------------------------


class TestConcedeToSupport:
    def test_concede_with_known_target_produces_argument_and_support(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X", confidence=0.5))
            .append(_concede("co1", target="p1"))
        )
        baf = build_qbaf(trace)
        ids = {a.arg_id for a in baf.arguments}
        assert ids == {"p1", "co1"}
        assert len(baf.supports) == 1
        assert baf.supports[0].source == "co1"
        assert baf.supports[0].target == "p1"

    def test_concede_argument_base_score_is_one(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_concede("co1", target="p1"))
        )
        baf = build_qbaf(trace)
        co_arg = next(a for a in baf.arguments if a.arg_id == "co1")
        assert co_arg.base_score == 1.0  # unconditional endorsement

    def test_concede_argument_surface_mentions_target(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_concede("co1", target="p1"))
        )
        baf = build_qbaf(trace)
        co_arg = next(a for a in baf.arguments if a.arg_id == "co1")
        # Synthetic: must reference the target so the visualiser shows context
        assert "p1" in co_arg.claim_surface

    def test_concede_support_weight_is_one(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_concede("co1", target="p1"))
        )
        baf = build_qbaf(trace)
        assert baf.supports[0].weight == 1.0

    def test_concede_with_unknown_target_dropped(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_concede("co1", target="ghost"))
        )
        baf = build_qbaf(trace)
        ids = {a.arg_id for a in baf.arguments}
        assert "co1" not in ids
        assert baf.supports == ()


# ---------------------------------------------------------------------------
# Slice C — Retract → mark withdrawn
# ---------------------------------------------------------------------------


class TestRetractMarksWithdrawn:
    def test_retract_marks_target_argument_withdrawn(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X", confidence=0.5))
            .append(_retract("r1", own="p1"))
        )
        baf = build_qbaf(trace)
        p1_arg = next(a for a in baf.arguments if a.arg_id == "p1")
        assert p1_arg.withdrawn is True

    def test_retract_does_not_add_argument(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_retract("r1", own="p1"))
        )
        baf = build_qbaf(trace)
        ids = {a.arg_id for a in baf.arguments}
        # Retract does NOT itself become an Argument node
        assert "r1" not in ids

    def test_retract_with_unknown_own_is_noop(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_retract("r1", own="ghost"))
        )
        baf = build_qbaf(trace)
        # All Propose-derived args remain unwithdrawn
        assert all(not a.withdrawn for a in baf.arguments if a.arg_id == "p1")

    def test_retract_idempotent_on_already_withdrawn(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_retract("r1", own="p1"))
            .append(_retract("r2", own="p1"))
        )
        baf = build_qbaf(trace)
        p1_arg = next(a for a in baf.arguments if a.arg_id == "p1")
        assert p1_arg.withdrawn is True

    def test_retract_can_withdraw_a_challenge(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_challenge("c1", target="p1"))
            .append(_retract("r1", own="c1"))
        )
        baf = build_qbaf(trace)
        c_arg = next(a for a in baf.arguments if a.arg_id == "c1")
        assert c_arg.withdrawn is True
        # The Attack edge is still present — withdrawal is on the node only.
        # (Gradual semantics will weight withdrawn arguments at 0; that is
        # the semantics' concern, not the builder's.)
        assert any(att.source == "c1" for att in baf.attacks)


# ---------------------------------------------------------------------------
# Slice D — Walton-Krabbe canonical golden fixture
# ---------------------------------------------------------------------------


def _load_walton_krabbe() -> tuple[Trace, QBAF]:
    """Build the trace and expected QBAF from the committed JSON fixture."""
    raw = (FIXTURES_DIR / "walton_krabbe.json").read_text()
    fixture = json.loads(raw)
    trace = Trace()
    for entry in fixture["trace"]:
        move = parse_move(
            json.dumps(entry["json"]),
            agent_id=entry["agent_id"],
            round_index=entry["round_index"],
            move_id=entry["move_id"],
        )
        trace = trace.append(move)
    expected = QBAF(
        arguments=tuple(
            Argument(
                arg_id=a["arg_id"],
                claim_surface=a["claim_surface"],
                base_score=a["base_score"],
                withdrawn=a["withdrawn"],
            )
            for a in fixture["expected_qbaf"]["arguments"]
        ),
        attacks=tuple(
            Attack(source=e["source"], target=e["target"], weight=e["weight"])
            for e in fixture["expected_qbaf"]["attacks"]
        ),
        supports=tuple(
            Support(source=e["source"], target=e["target"], weight=e["weight"])
            for e in fixture["expected_qbaf"]["supports"]
        ),
    )
    return trace, expected


class TestWaltonKrabbeGolden:
    def test_canonical_trace_matches_expected_qbaf(self) -> None:
        trace, expected = _load_walton_krabbe()
        actual = build_qbaf(trace)
        assert actual == expected

    def test_argument_ids_match_expected(self) -> None:
        trace, expected = _load_walton_krabbe()
        actual = build_qbaf(trace)
        assert [a.arg_id for a in actual.arguments] == [
            a.arg_id for a in expected.arguments
        ]

    def test_attack_chain_matches_expected(self) -> None:
        trace, expected = _load_walton_krabbe()
        actual = build_qbaf(trace)
        assert actual.attacks == expected.attacks

    def test_support_chain_matches_expected(self) -> None:
        trace, expected = _load_walton_krabbe()
        actual = build_qbaf(trace)
        assert actual.supports == expected.supports


# ---------------------------------------------------------------------------
# Slice D — Full multi-move determinism round-trip
# ---------------------------------------------------------------------------


class TestDeterminismFull:
    def test_walton_krabbe_byte_equal_over_100_invocations(self) -> None:
        trace, _ = _load_walton_krabbe()
        baf1 = build_qbaf(trace)
        for _ in range(100):
            assert build_qbaf(trace) == baf1

    def test_walton_krabbe_with_identity_calibrator_byte_equal(self) -> None:
        trace, _ = _load_walton_krabbe()
        baf_no = build_qbaf(trace)
        baf_id = build_qbaf(trace, calibrator=IdentityCalibrator())
        assert baf_no == baf_id

    def test_complex_trace_with_all_move_types_deterministic(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X", confidence=0.5))
            .append(_propose("p2", surface="Y", confidence=0.4))
            .append(_challenge("c1", target="p1", confidence=0.6))
            .append(_challenge("c2", target="c1", confidence=0.5))
            .append(_concede("co1", target="p2"))
            .append(_retract("r1", own="p1"))
            .append(_vote("v1", surface="Y", confidence=0.3))
        )
        baf1 = build_qbaf(trace)
        for _ in range(50):
            assert build_qbaf(trace) == baf1


# ---------------------------------------------------------------------------
# Slice D — Self-attack detection deferred to PR8 (ADR-0007)
# ---------------------------------------------------------------------------


class TestSelfAttackDeferred:
    """ADR-0007: build_qbaf does NOT detect self-attacks. PR8 adds them via
    a [argue-asp] tool_client path; until then a Propose whose surface
    contradicts its evidence enters the QBAF unattacked.
    """

    def test_arith_propose_contradicting_evidence_has_no_self_attack(self) -> None:
        contradictory = Propose(
            move_id="p1",
            agent_id="A",
            round_index=0,
            claim=Claim(
                surface="x = 5",
                domain=ClaimDomain.ARITH,
                evidence=("proof: x = 7",),
            ),
            confidence=0.9,
        )
        trace = Trace().append(contradictory)
        baf = build_qbaf(trace)
        # The argument enters the graph with its full base_score; no
        # self-attack edge is generated. PR8 (ADR-0007) will add one when
        # the [argue-asp] extra and tool_client are wired in.
        assert baf.arguments[0].base_score == 0.9
        assert baf.attacks == ()

    def test_fol_propose_contradicting_evidence_has_no_self_attack(self) -> None:
        # Same deferral applies to claim.domain == FOL
        contradictory = Propose(
            move_id="p1",
            agent_id="A",
            round_index=0,
            claim=Claim(
                surface="forall x. P(x)",
                domain=ClaimDomain.FOL,
                evidence=("counterexample: P(0) = false",),
            ),
            confidence=0.9,
        )
        trace = Trace().append(contradictory)
        baf = build_qbaf(trace)
        assert baf.attacks == ()
