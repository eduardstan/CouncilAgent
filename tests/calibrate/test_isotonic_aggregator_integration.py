"""Integration tests — IsotonicCalibrator + W2 build_qbaf headline path.

Verifies that wiring IsotonicCalibrator (ADR-0018) into
``council.symbolic.argue.builders.build_qbaf`` via the calibrator hook
(W2/PR2, Approved Exception #1) replaces Propose-derived base scores
with the fitted monotone map's predictions, without disturbing
structural fields. Mirrors the JSD, MUSE, and Privileged-Knowledge
integration test patterns.
"""

from __future__ import annotations

import pytest

from council.calibrate import IdentityCalibrator, IsotonicCalibrator
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


class TestIsotonicCalibratorBuildsCleanly:
    """IsotonicCalibrator-fed build_qbaf shares structure with the no-calibrator path."""

    def test_perfectly_calibrated_training_data_preserves_base_scores(self) -> None:
        # Training data where raw == correctness rate makes isotonic
        # essentially the identity. Base scores after calibration should
        # be close to the raw confidences.
        # Build training pairs that respect monotone (raw, p_correct) where
        # p_correct ≈ raw exactly: alternate 0/1 around each raw level.
        train = []
        for raw_pct in range(10, 100, 10):
            raw = raw_pct / 100.0
            # `raw_pct` of every 10 samples are correct.
            for i in range(10):
                train.append((raw, 1 if i < raw_pct // 10 else 0))

        cal = IsotonicCalibrator(train)
        trace = Trace(
            (
                _propose("m0", agent_id="A", surface="x", confidence=0.5),
                _propose("m1", agent_id="B", surface="y", confidence=0.8),
            )
        )

        baseline = build_qbaf(trace, calibrator=IdentityCalibrator())
        calibrated = build_qbaf(trace, calibrator=cal)

        for base_arg, cal_arg in zip(
            baseline.arguments, calibrated.arguments, strict=True
        ):
            assert base_arg.arg_id == cal_arg.arg_id
            assert base_arg.claim_surface == cal_arg.claim_surface
            # Identity-ish map: calibrated within ~0.15 of raw.
            assert abs(base_arg.base_score - cal_arg.base_score) <= 0.15

    def test_overconfident_training_data_pulls_base_scores_down(self) -> None:
        # Training data where high-raw predictions are ~50% wrong → isotonic
        # pulls them down. Build training: raw=0.9, half correct;
        # raw=0.1, none correct (low confidence, all wrong — calibrated).
        train = [(0.9, 0)] * 5 + [(0.9, 1)] * 5 + [(0.1, 0)] * 10
        cal = IsotonicCalibrator(train)

        trace = Trace((_propose("m0", agent_id="A", surface="x", confidence=0.9),))
        calibrated = build_qbaf(trace, calibrator=cal)
        # raw=0.9 should be calibrated down toward 0.5.
        assert calibrated.arguments[0].base_score < 0.9
        assert calibrated.arguments[0].base_score == pytest.approx(0.5, abs=0.1)

    def test_structural_invariance(self) -> None:
        # Arg ids, attacks, supports must match between baseline and
        # isotonic-calibrated QBAFs — only base_score may differ.
        train = [(0.1, 0), (0.4, 0), (0.6, 1), (0.9, 1)] * 5
        cal = IsotonicCalibrator(train)

        trace = Trace(
            (
                _propose("m0", agent_id="A", surface="x", confidence=0.85),
                _propose("m1", agent_id="B", surface="y", confidence=0.55),
                _propose(
                    "m2", agent_id="C", surface="z", confidence=0.30, domain=ClaimDomain.ARITH
                ),
            )
        )

        baseline = build_qbaf(trace)
        calibrated = build_qbaf(trace, calibrator=cal)

        baseline_ids = tuple(a.arg_id for a in baseline.arguments)
        calibrated_ids = tuple(a.arg_id for a in calibrated.arguments)
        assert baseline_ids == calibrated_ids
        assert baseline.attacks == calibrated.attacks
        assert baseline.supports == calibrated.supports
