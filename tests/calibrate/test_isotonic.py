"""Tests for council.calibrate.isotonic — IsotonicCalibrator + ECE helper.

The acceptance criterion (master plan §7 W3) is "ECE on a held-out GSM8K
split drops below 0.05". For unit tests we use a *synthetic miscalibrated
distribution* whose ground-truth calibration map is known, so the
algorithm's correctness is provable without any real-LLM calls.
ADR-0018 documents the fixture-strategy decision (synthetic for unit
tests, real-LLM via experiments/fixtures/gen_gsm8k_calibration.py for
the gated tests/integration/test_calibration_real_models.py).

Standard (Guo et al. 2017 "On Calibration of Modern Neural Networks")
ECE definition:
    ECE = sum_b |bin_acc_b - bin_conf_b| * |bin_b| / N
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from council.calibrate import Calibrator
from council.calibrate.isotonic import IsotonicCalibrator, expected_calibration_error
from council.dialect.moves import ClaimDomain


def _make_miscalibrated_dataset(
    n: int, *, seed: int = 0
) -> tuple[list[float], list[int]]:
    """Synthetic miscalibrated dataset whose true correctness rate
    follows a sigmoid of the raw confidence. raw_confidences are uniform
    on [0, 1]; the true probability of correctness is sigmoid(6*(raw - 0.5)).
    Naive ECE on the raw confidences is ~0.10-0.20, isotonic should drop
    well below 0.05.
    """
    rng = random.Random(seed)
    raws: list[float] = []
    correct: list[int] = []
    for _ in range(n):
        r = rng.random()
        true_prob = 1.0 / (1.0 + np.exp(-6.0 * (r - 0.5)))
        raws.append(r)
        correct.append(1 if rng.random() < true_prob else 0)
    return raws, correct


class TestExpectedCalibrationError:
    """ECE function on hand-computable inputs."""

    def test_perfect_calibration_yields_zero(self) -> None:
        # All confidences match their bin's true accuracy exactly.
        # 5 samples in two bins:
        #   bin (0.0, 0.1]: confidences = [0.05, 0.05] → mean 0.05; correctness = [0, 0] → acc 0; |diff|=0.05
        #   actually for true 0 ECE we'd need acc == conf bin-wise. Let's use:
        # Conf=0.5 with 1/2 correct → bin_acc=0.5, |diff|=0.
        confidences = [0.5, 0.5]
        correct = [1, 0]
        ece = expected_calibration_error(confidences, correct, n_bins=10)
        # Bin (0.4, 0.5]: mean conf 0.5, accuracy 0.5, |diff|=0 → ECE=0.
        assert ece == pytest.approx(0.0, abs=1e-12)

    def test_perfectly_miscalibrated_yields_max_one(self) -> None:
        # All conf=1.0 but accuracy=0.0 → ECE = 1.0.
        confidences = [1.0] * 10
        correct = [0] * 10
        ece = expected_calibration_error(confidences, correct, n_bins=10)
        assert ece == pytest.approx(1.0, abs=1e-12)

    def test_mismatched_lengths_raise(self) -> None:
        with pytest.raises(ValueError, match="length"):
            expected_calibration_error([0.5, 0.5], [1], n_bins=10)

    def test_correct_outside_zero_one_raises(self) -> None:
        with pytest.raises(ValueError, match="0 or 1"):
            expected_calibration_error([0.5], [2], n_bins=10)

    def test_n_bins_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="n_bins"):
            expected_calibration_error([0.5], [1], n_bins=0)

    def test_empty_inputs_yield_zero(self) -> None:
        # No predictions → vacuously well-calibrated.
        assert expected_calibration_error([], [], n_bins=10) == pytest.approx(0.0)

    def test_known_two_bin_value(self) -> None:
        # 4 samples: 2 in bin (0.0, 0.5] with confs [0.2, 0.4] (mean 0.3)
        # and labels [0, 0] (acc 0.0) → |0.3-0.0|=0.3, weight 2/4=0.5.
        # 2 samples in bin (0.5, 1.0] with confs [0.6, 0.8] (mean 0.7)
        # and labels [1, 1] (acc 1.0) → |0.7-1.0|=0.3, weight 2/4=0.5.
        # ECE = 0.5*0.3 + 0.5*0.3 = 0.3.
        confidences = [0.2, 0.4, 0.6, 0.8]
        correct = [0, 0, 1, 1]
        ece = expected_calibration_error(confidences, correct, n_bins=2)
        assert ece == pytest.approx(0.3, abs=1e-12)


class TestIsotonicCalibratorContract:
    """ABC compliance + signature handling."""

    def test_implements_calibrator_abc(self) -> None:
        train = [(0.1, 0), (0.5, 0), (0.9, 1)]
        cal = IsotonicCalibrator(train)
        assert isinstance(cal, Calibrator)

    def test_calibrate_returns_float_in_unit_interval(self) -> None:
        train = [(0.1, 0), (0.3, 0), (0.5, 1), (0.7, 1), (0.9, 1)]
        cal = IsotonicCalibrator(train)
        for raw in (0.0, 0.25, 0.5, 0.75, 1.0):
            v = cal.calibrate(raw, "agent_x", ClaimDomain.FREE)
            assert 0.0 <= v <= 1.0

    def test_domain_and_agent_id_are_ignored(self) -> None:
        # IsotonicCalibrator is domain- and agent-agnostic.
        train = [(0.1, 0), (0.5, 0), (0.9, 1)]
        cal = IsotonicCalibrator(train)
        v_free_a = cal.calibrate(0.5, "A", ClaimDomain.FREE)
        v_arith_b = cal.calibrate(0.5, "B", ClaimDomain.ARITH)
        assert v_free_a == pytest.approx(v_arith_b)


class TestIsotonicCalibratorBehaviour:
    """Algorithmic properties of the fitted isotonic map."""

    def test_monotone_non_decreasing(self) -> None:
        # IsotonicRegression must produce a monotone non-decreasing map.
        train = [(0.0, 0), (0.2, 0), (0.5, 1), (0.7, 1), (1.0, 1)]
        cal = IsotonicCalibrator(train)
        prev = -1.0
        for raw in np.linspace(0.0, 1.0, num=20):
            v = cal.calibrate(float(raw), "x", ClaimDomain.FREE)
            assert v >= prev - 1e-12
            prev = v

    def test_drops_ece_below_005_on_synthetic_miscalibrated_data(self) -> None:
        # Acceptance criterion (master plan §7 W3): ECE drops below 0.05.
        # Use synthetic mis-calibrated data with a known ground-truth
        # sigmoid relationship; train/test split.
        train_raws, train_correct = _make_miscalibrated_dataset(800, seed=0)
        test_raws, test_correct = _make_miscalibrated_dataset(800, seed=1)

        ece_before = expected_calibration_error(test_raws, test_correct, n_bins=10)

        cal = IsotonicCalibrator(list(zip(train_raws, train_correct, strict=True)))
        calibrated_test = [
            cal.calibrate(r, "agent", ClaimDomain.FREE) for r in test_raws
        ]
        ece_after = expected_calibration_error(calibrated_test, test_correct, n_bins=10)

        assert ece_before > 0.05  # the synthetic data IS miscalibrated
        assert ece_after < 0.05   # isotonic recovers calibration
        # And the improvement is substantial.
        assert ece_after < ece_before / 2.0

    def test_deterministic_across_repeated_calls(self) -> None:
        # Same training data → same fit → same output.
        train = [(0.1, 0), (0.4, 0), (0.6, 1), (0.9, 1)]
        cal_a = IsotonicCalibrator(train)
        cal_b = IsotonicCalibrator(train)
        for raw in (0.2, 0.5, 0.8):
            assert cal_a.calibrate(raw, "x", ClaimDomain.FREE) == pytest.approx(
                cal_b.calibrate(raw, "x", ClaimDomain.FREE)
            )

    def test_output_clamped_to_unit_interval(self) -> None:
        # Even if raw is wildly out of range, calibrate must return in [0,1].
        train = [(0.1, 0), (0.5, 1), (0.9, 1)]
        cal = IsotonicCalibrator(train)
        for raw in (-0.5, -0.001, 1.001, 1.5):
            v = cal.calibrate(raw, "x", ClaimDomain.FREE)
            assert 0.0 <= v <= 1.0


class TestIsotonicCalibratorValidation:
    """Boundary input validation."""

    def test_empty_training_data_raises(self) -> None:
        with pytest.raises(ValueError, match="training"):
            IsotonicCalibrator([])

    def test_correctness_outside_zero_one_raises(self) -> None:
        with pytest.raises(ValueError, match="0 or 1"):
            IsotonicCalibrator([(0.5, 2)])

    def test_raw_outside_zero_one_in_training_raises(self) -> None:
        with pytest.raises(ValueError, match="raw"):
            IsotonicCalibrator([(1.5, 1), (0.5, 0)])
