"""Integration tests — MUSECalibrator + W2 build_qbaf headline path.

Verifies that wiring MUSECalibrator (Kruse et al. 2025; ADR-0016) into
``council.symbolic.argue.builders.build_qbaf`` via the calibrator hook
(W2/PR2, Approved Exception #1) changes Propose-derived argument base
scores by the MUSE-derived per-agent JS²-against-consensus penalty,
without disturbing structural fields (arg ids, edges, withdrawn flags).

Mirrors the JSD integration test pattern in
``test_jsd_aggregator_integration.py``.
"""

from __future__ import annotations

import pytest

from council.calibrate import IdentityCalibrator, MUSECalibrator
from council.dialect.moves import Claim, ClaimDomain, Propose
from council.dialect.trace import Trace
from council.symbolic.argue.builders import build_qbaf


def _propose(
    move_id: str,
    *,
    agent_id: str,
    surface: str,
    confidence: float,
    round_index: int = 0,
    domain: ClaimDomain = ClaimDomain.FREE,
) -> Propose:
    return Propose(
        move_id=move_id,
        agent_id=agent_id,
        round_index=round_index,
        claim=Claim(surface=surface, domain=domain),
        confidence=confidence,
    )


class TestMUSECalibratorBuildsCleanly:
    """MUSECalibrator-fed build_qbaf shares structure with the no-calibrator path."""

    def test_full_agreement_matches_identity_baseline(self) -> None:
        # When all agents predict identical distributions the consensus
        # equals each agent → JS² = 0 → MUSECalibrator is the identity.
        trace = Trace(
            (
                _propose("m0", agent_id="A", surface="answer-1", confidence=0.7),
                _propose("m1", agent_id="B", surface="answer-1", confidence=0.6),
            )
        )
        identical_dists = [{"answer-1": 1.0, "answer-2": 0.0}] * 2
        muse_cal = MUSECalibrator(
            identical_dists,
            ["A", "B"],
            yes_key="answer-1",
            eps_tol=1.0,
        )

        baseline = build_qbaf(trace, calibrator=IdentityCalibrator())
        calibrated = build_qbaf(trace, calibrator=muse_cal)

        for base_arg, cal_arg in zip(baseline.arguments, calibrated.arguments, strict=True):
            assert base_arg.arg_id == cal_arg.arg_id
            assert base_arg.claim_surface == cal_arg.claim_surface
            assert base_arg.base_score == pytest.approx(cal_arg.base_score, abs=1e-12)
        assert baseline.attacks == calibrated.attacks
        assert baseline.supports == calibrated.supports

    def test_disagreeing_agent_base_score_collapses(self) -> None:
        # Two strongly-disagreeing agents predicting opposite Diracs;
        # MUSE-Greedy with m_min=2 forces both into S → consensus is
        # the uniform (0.5, 0.5) → JS²-vs-consensus is the closed-form
        # uniform-vs-Dirac value ≈ 0.31127812 for both agents.
        trace = Trace(
            (
                _propose("m0", agent_id="A", surface="answer-1", confidence=0.9),
                _propose("m1", agent_id="B", surface="answer-2", confidence=0.8),
            )
        )
        disjoint_dists = [
            {"answer-1": 1.0, "answer-2": 0.0},
            {"answer-1": 0.0, "answer-2": 1.0},
        ]
        muse_cal = MUSECalibrator(
            disjoint_dists,
            ["A", "B"],
            yes_key="answer-1",
            m_min=2,
            eps_tol=1.0,
        )

        calibrated = build_qbaf(trace, calibrator=muse_cal)
        scores = {a.arg_id: a.base_score for a in calibrated.arguments}

        # Both Propose moves carry the same MUSE penalty factor (≈ 1 - 0.3113).
        expected_factor_floor = 1.0 - 0.32  # uniform-vs-Dirac upper bound on JS²
        expected_factor_ceil = 1.0 - 0.30
        for arg_id, raw in (("m0", 0.9), ("m1", 0.8)):
            assert scores[arg_id] == pytest.approx(
                raw * (1.0 - 0.3112781244591328), abs=1e-9
            )
            # Also check the value is in the expected envelope.
            assert (raw * expected_factor_floor) <= scores[arg_id] <= (raw * expected_factor_ceil)

    def test_structural_invariance(self) -> None:
        # Arg ids, attacks, supports must match between baseline and
        # MUSE-calibrated QBAFs — only base_score should differ.
        trace = Trace(
            (
                _propose("m0", agent_id="A", surface="x", confidence=0.9),
                _propose("m1", agent_id="B", surface="y", confidence=0.5),
                _propose("m2", agent_id="C", surface="z", confidence=0.4),
            )
        )
        dists = [
            {"x": 0.8, "y": 0.1, "z": 0.1},
            {"x": 0.1, "y": 0.8, "z": 0.1},
            {"x": 0.1, "y": 0.1, "z": 0.8},
        ]
        muse_cal = MUSECalibrator(dists, ["A", "B", "C"], eps_tol=1.0)

        baseline = build_qbaf(trace)
        calibrated = build_qbaf(trace, calibrator=muse_cal)

        baseline_ids = tuple(a.arg_id for a in baseline.arguments)
        calibrated_ids = tuple(a.arg_id for a in calibrated.arguments)
        assert baseline_ids == calibrated_ids
        assert baseline.attacks == calibrated.attacks
        assert baseline.supports == calibrated.supports
