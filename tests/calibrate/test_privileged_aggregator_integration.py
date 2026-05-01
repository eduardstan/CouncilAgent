"""Integration tests — PrivilegedKnowledgeCalibrator + W2 build_qbaf.

Verifies that wiring PrivilegedKnowledgeCalibrator (Anonymous 2026;
ADR-0017) into ``council.symbolic.argue.builders.build_qbaf`` via the
calibrator hook (W2/PR2, Approved Exception #1) changes Propose-derived
argument base scores by the per-domain self/peer mix without disturbing
structural fields. Mirrors the JSD and MUSE integration test patterns.
"""

from __future__ import annotations

import pytest

from council.calibrate import (
    DEFAULT_DOMAIN_GAPS,
    DomainGap,
    IdentityCalibrator,
    PrivilegedKnowledgeCalibrator,
)
from council.dialect.moves import Claim, ClaimDomain, Propose
from council.dialect.trace import Trace
from council.symbolic.argue.builders import build_qbaf


def _propose(
    move_id: str,
    *,
    agent_id: str,
    surface: str,
    confidence: float,
    domain: ClaimDomain = ClaimDomain.FREE,
    round_index: int = 0,
) -> Propose:
    return Propose(
        move_id=move_id,
        agent_id=agent_id,
        round_index=round_index,
        claim=Claim(surface=surface, domain=domain),
        confidence=confidence,
    )


class TestPrivilegedKnowledgeCalibratorBuildsCleanly:
    """PrivilegedKnowledge-fed build_qbaf shares structure with the no-calibrator path."""

    def test_self_equals_peer_matches_identity_baseline(self) -> None:
        # When raw == peer for every agent, the convex combination is
        # the identity → calibrated base scores equal IdentityCalibrator's.
        trace = Trace(
            (
                _propose("m0", agent_id="A", surface="x", confidence=0.6),
                _propose("m1", agent_id="B", surface="x", confidence=0.6),
            )
        )
        peer_consensus = {"A": 0.6, "B": 0.6}
        cal = PrivilegedKnowledgeCalibrator(peer_consensus=peer_consensus)

        baseline = build_qbaf(trace, calibrator=IdentityCalibrator())
        calibrated = build_qbaf(trace, calibrator=cal)

        for base_arg, cal_arg in zip(baseline.arguments, calibrated.arguments, strict=True):
            assert base_arg.arg_id == cal_arg.arg_id
            assert base_arg.claim_surface == cal_arg.claim_surface
            assert base_arg.base_score == pytest.approx(cal_arg.base_score, abs=1e-12)
        assert baseline.attacks == calibrated.attacks
        assert baseline.supports == calibrated.supports

    def test_factual_domain_biases_toward_self(self) -> None:
        # Factual claim with raw=0.9, peer=0.3 → calibrated =
        # 0.525*0.9 + 0.475*0.3 = 0.6075. Compared to math (0.5*0.9 +
        # 0.5*0.3 = 0.6), factual sits slightly above the unweighted mean.
        trace = Trace(
            (_propose("m0", agent_id="A", surface="x", confidence=0.9, domain=ClaimDomain.FREE),)
        )
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": 0.3})
        calibrated = build_qbaf(trace, calibrator=cal)

        gap = DEFAULT_DOMAIN_GAPS[ClaimDomain.FREE]
        expected = gap.self_weight * 0.9 + gap.peer_weight * 0.3
        assert calibrated.arguments[0].base_score == pytest.approx(expected, abs=1e-12)

    def test_math_domain_uses_unweighted_mean(self) -> None:
        # Math has gap=0 → calibrated = (raw + peer) / 2 = 0.6.
        trace = Trace(
            (_propose("m0", agent_id="A", surface="42", confidence=0.9, domain=ClaimDomain.ARITH),)
        )
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": 0.3})
        calibrated = build_qbaf(trace, calibrator=cal)
        assert calibrated.arguments[0].base_score == pytest.approx(0.6, abs=1e-12)

    def test_structural_invariance(self) -> None:
        # Arg ids, attacks, supports must match between baseline and
        # PrivilegedKnowledge-calibrated QBAFs — only base_score should differ.
        trace = Trace(
            (
                _propose("m0", agent_id="A", surface="x", confidence=0.8, domain=ClaimDomain.FREE),
                _propose("m1", agent_id="B", surface="y", confidence=0.4, domain=ClaimDomain.ARITH),
                _propose("m2", agent_id="C", surface="z", confidence=0.6, domain=ClaimDomain.CODE),
            )
        )
        peer_consensus = {"A": 0.5, "B": 0.6, "C": 0.5}
        cal = PrivilegedKnowledgeCalibrator(peer_consensus=peer_consensus)

        baseline = build_qbaf(trace)
        calibrated = build_qbaf(trace, calibrator=cal)

        baseline_ids = tuple(a.arg_id for a in baseline.arguments)
        calibrated_ids = tuple(a.arg_id for a in calibrated.arguments)
        assert baseline_ids == calibrated_ids
        assert baseline.attacks == calibrated.attacks
        assert baseline.supports == calibrated.supports

    def test_custom_gaps_override_default_per_domain(self) -> None:
        # Force factual to behave like math by supplying gap=0 for FREE.
        trace = Trace(
            (_propose("m0", agent_id="A", surface="x", confidence=0.9, domain=ClaimDomain.FREE),)
        )
        custom = {**DEFAULT_DOMAIN_GAPS, ClaimDomain.FREE: DomainGap(0.0)}
        cal = PrivilegedKnowledgeCalibrator(
            peer_consensus={"A": 0.3},
            domain_gaps=custom,
        )
        calibrated = build_qbaf(trace, calibrator=cal)
        # gap=0 → unweighted mean.
        assert calibrated.arguments[0].base_score == pytest.approx(0.6, abs=1e-12)
