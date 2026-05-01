"""Integration tests — JSDCalibrator + W2 build_qbaf headline path.

Verifies that wiring JSDCalibrator into council.symbolic.argue.builders.
build_qbaf via the calibrator= hook (W2/PR2, Approved Exception #1)
changes Propose-derived argument base scores by the JSD penalty without
disturbing structural fields (arg ids, edges, withdrawn flags).

This test is the realisation of ADR-0008's promise: the L3 calibrator
plugs in cleanly, the L2 builder remains pure-Python and deterministic,
and the import direction (argue → calibrate) is sanctioned by
.claude/rules/architecture.md §"Approved exceptions" #1.
"""

from __future__ import annotations

import pytest

from council.calibrate import IdentityCalibrator, JSDCalibrator
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


class TestJSDCalibratorBuildsCleanly:
    """JSD-calibrator-fed build_qbaf shares structure with the no-calibrator path."""

    def test_jsd_zero_matches_identity_baseline(self) -> None:
        # When JSD == 0 (full agreement), JSDCalibrator should reproduce
        # IdentityCalibrator's base scores byte-for-byte.
        trace = Trace(
            (
                _propose("m0", agent_id="A", surface="answer-1", confidence=0.7),
                _propose("m1", agent_id="B", surface="answer-1", confidence=0.6),
            )
        )

        identical_dists = [{"answer-1": 1.0}, {"answer-1": 1.0}]
        jsd_cal = JSDCalibrator(identical_dists)
        assert jsd_cal.jsd == pytest.approx(0.0, abs=1e-12)

        baseline = build_qbaf(trace, calibrator=IdentityCalibrator())
        calibrated = build_qbaf(trace, calibrator=jsd_cal)

        for base_arg, cal_arg in zip(baseline.arguments, calibrated.arguments, strict=True):
            assert base_arg.arg_id == cal_arg.arg_id
            assert base_arg.claim_surface == cal_arg.claim_surface
            assert base_arg.base_score == pytest.approx(cal_arg.base_score, abs=1e-12)
        assert baseline.attacks == calibrated.attacks
        assert baseline.supports == calibrated.supports

    def test_jsd_penalises_propose_base_scores(self) -> None:
        # Two agents proposing different answers → genuine disagreement.
        trace = Trace(
            (
                _propose("m0", agent_id="A", surface="answer-1", confidence=0.8),
                _propose("m1", agent_id="B", surface="answer-2", confidence=0.6),
            )
        )

        # Distributions encode the disagreement: agent A places mass on
        # "answer-1", agent B on "answer-2". This is the disjoint-Diracs
        # case — JSD = 1, so calibrated base scores collapse to 0.
        disjoint_dists = [
            {"answer-1": 1.0, "answer-2": 0.0},
            {"answer-1": 0.0, "answer-2": 1.0},
        ]
        jsd_cal = JSDCalibrator(disjoint_dists)
        assert jsd_cal.jsd == pytest.approx(1.0, abs=1e-9)

        baseline = build_qbaf(trace)
        calibrated = build_qbaf(trace, calibrator=jsd_cal)

        # Structural fields preserved.
        baseline_ids = tuple(a.arg_id for a in baseline.arguments)
        calibrated_ids = tuple(a.arg_id for a in calibrated.arguments)
        assert baseline_ids == calibrated_ids

        # Base scores in the calibrated QBAF collapse to 0 (raw * (1 - 1)).
        for arg in calibrated.arguments:
            assert arg.base_score == pytest.approx(0.0, abs=1e-12)

        # Baseline preserves the raw confidences as base scores.
        baseline_scores = {a.arg_id: a.base_score for a in baseline.arguments}
        assert baseline_scores["m0"] == pytest.approx(0.8)
        assert baseline_scores["m1"] == pytest.approx(0.6)

    def test_partial_disagreement_scales_base_scores(self) -> None:
        # Closed form JSD ≈ 0.31127812 → calibrated = raw * (1 - 0.3113).
        trace = Trace(
            (
                _propose("m0", agent_id="A", surface="x", confidence=0.9),
                _propose("m1", agent_id="B", surface="y", confidence=0.4),
            )
        )

        partial_dists = [{"x": 0.5, "y": 0.5}, {"x": 1.0, "y": 0.0}]
        jsd_cal = JSDCalibrator(partial_dists)
        factor = 1.0 - jsd_cal.jsd

        calibrated = build_qbaf(trace, calibrator=jsd_cal)
        scores = {a.arg_id: a.base_score for a in calibrated.arguments}

        assert scores["m0"] == pytest.approx(0.9 * factor, abs=1e-12)
        assert scores["m1"] == pytest.approx(0.4 * factor, abs=1e-12)
