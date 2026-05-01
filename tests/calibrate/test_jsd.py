"""Tests for council.calibrate.jsd — Jensen-Shannon divergence helper.

Acceptance criteria pinned by Task 3 of the PR1 plan (feature/ns-w3-jsd):
  - closed-form n=2 disjoint Diracs → JSD = 1.0 (base-2 normalised)
  - closed-form n=2 uniform-vs-Dirac → JSD ≈ 0.31127812... (base-2 normalised)
  - identical distributions → JSD = 0.0
  - symmetry, determinism, validation
  - n≥3 mixed-support: zero-pad over union of supports; the value is pinned
    to a scipy-derived inline computation so the helper's behaviour is
    documented by the test rather than copied blindly
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.spatial.distance import jensenshannon

from council.calibrate import Calibrator
from council.calibrate.jsd import JSDCalibrator, jsd_divergence
from council.dialect.moves import ClaimDomain


class TestJSDClosedForm:
    """Closed-form values that any correct JSD must produce (base-2)."""

    def test_disjoint_diracs_yield_one(self) -> None:
        # δ_a vs δ_b on disjoint singletons — the canonical JSD-maximising case.
        # Closed form base-2: H(M=(0.5,0.5)) - 0.5*H(δ_a) - 0.5*H(δ_b) = 1 - 0 - 0 = 1.
        result = jsd_divergence([{"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 1.0}])
        assert result == pytest.approx(1.0, abs=1e-9)

    def test_uniform_vs_dirac(self) -> None:
        # P=(0.5,0.5), Q=(1,0). Closed form base-2 ≈ 0.31127812445913283.
        result = jsd_divergence([{"a": 0.5, "b": 0.5}, {"a": 1.0, "b": 0.0}])
        expected = jensenshannon([0.5, 0.5], [1.0, 0.0], base=2) ** 2
        assert result == pytest.approx(float(expected), abs=1e-12)

    def test_identical_distributions_yield_zero(self) -> None:
        result = jsd_divergence(
            [{"a": 0.3, "b": 0.7}, {"a": 0.3, "b": 0.7}]
        )
        assert result == pytest.approx(0.0, abs=1e-12)


class TestJSDProperties:
    """Symmetry + determinism — properties any pairwise JSD must satisfy."""

    def test_symmetric_in_two_arguments(self) -> None:
        p = {"a": 0.6, "b": 0.4}
        q = {"a": 0.1, "b": 0.9}
        forward = jsd_divergence([p, q])
        reverse = jsd_divergence([q, p])
        assert forward == pytest.approx(reverse, abs=1e-10)

    def test_deterministic_across_repeated_calls(self) -> None:
        p = {"a": 0.5, "b": 0.3, "c": 0.2}
        q = {"a": 0.1, "b": 0.6, "c": 0.3}
        first = jsd_divergence([p, q])
        for _ in range(99):
            assert jsd_divergence([p, q]) == first


class TestJSDValidation:
    """Boundary input validation."""

    def test_distribution_not_summing_to_one_raises(self) -> None:
        with pytest.raises(ValueError, match="must sum to 1"):
            jsd_divergence([{"a": 0.6, "b": 0.5}, {"a": 1.0, "b": 0.0}])

    def test_negative_probability_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            jsd_divergence([{"a": 1.2, "b": -0.2}, {"a": 1.0, "b": 0.0}])

    def test_fewer_than_two_distributions_raises(self) -> None:
        with pytest.raises(ValueError, match="at least two distributions"):
            jsd_divergence([{"a": 1.0}])


class TestJSDMixedSupport:
    """N≥3 with sparse supports; value pinned to a scipy-derived computation."""

    def test_three_distributions_mixed_support_matches_pairwise_mean(self) -> None:
        # Distributions over disjoint-ish supports; helper must zero-pad.
        p = {"a": 0.7, "b": 0.2, "c": 0.1}
        q = {"b": 0.3, "c": 0.3, "d": 0.4}
        r = {"a": 0.4, "b": 0.4, "c": 0.2}

        # Reference: PR1 helper uses mean-of-pairwise scipy JSD over the union
        # support {a,b,c,d}. Compute the same here so the test pins behaviour.
        keys = ("a", "b", "c", "d")
        p_arr = np.array([p.get(k, 0.0) for k in keys])
        q_arr = np.array([q.get(k, 0.0) for k in keys])
        r_arr = np.array([r.get(k, 0.0) for k in keys])
        pairs = [
            jensenshannon(p_arr, q_arr, base=2) ** 2,
            jensenshannon(p_arr, r_arr, base=2) ** 2,
            jensenshannon(q_arr, r_arr, base=2) ** 2,
        ]
        expected = float(sum(pairs) / len(pairs))

        result = jsd_divergence([p, q, r])
        assert result == pytest.approx(expected, abs=1e-12)
        # Sanity: the value lies strictly inside (0, 1) for non-degenerate inputs.
        assert 0.0 < result < 1.0

    def test_output_in_unit_interval(self) -> None:
        # Maximum is hit only by disjoint Diracs (n=2) or fully-disjoint
        # singletons (n>=3). For random valid inputs the output stays in [0, 1].
        result = jsd_divergence(
            [{"a": 0.25, "b": 0.25, "c": 0.5}, {"a": 0.5, "b": 0.5}]
        )
        assert 0.0 <= result <= 1.0
        # And the mathematically pure value is finite.
        assert math.isfinite(result)


class TestJSDCalibrator:
    """Regression guard for the JSDCalibrator class wrapping jsd_divergence."""

    def test_implements_calibrator_abc(self) -> None:
        cal = JSDCalibrator([{"a": 1.0}, {"a": 1.0}])
        assert isinstance(cal, Calibrator)

    def test_full_agreement_returns_raw_unchanged(self) -> None:
        # Identical distributions → JSD = 0 → calibrate is the identity.
        cal = JSDCalibrator([{"a": 0.4, "b": 0.6}, {"a": 0.4, "b": 0.6}])
        assert cal.jsd == pytest.approx(0.0, abs=1e-12)
        assert cal.calibrate(0.8, "agent_x", ClaimDomain.ARITH) == pytest.approx(0.8)

    def test_full_disagreement_collapses_to_zero(self) -> None:
        # Disjoint Diracs → JSD = 1 → calibrate(...) = 0 regardless of raw.
        cal = JSDCalibrator([{"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 1.0}])
        assert cal.jsd == pytest.approx(1.0, abs=1e-9)
        assert cal.calibrate(0.95, "agent_x", ClaimDomain.FOL) == pytest.approx(0.0)

    def test_partial_disagreement_scales_linearly(self) -> None:
        # Closed form: P=(0.5,0.5) vs Q=(1,0) → JSD ≈ 0.31127812.
        # calibrate(raw, ...) = raw * (1 - 0.3113) ≈ raw * 0.6887.
        cal = JSDCalibrator([{"a": 0.5, "b": 0.5}, {"a": 1.0, "b": 0.0}])
        expected_factor = 1.0 - cal.jsd
        for raw in (0.1, 0.4, 0.8):
            assert cal.calibrate(raw, "agent_x", ClaimDomain.FREE) == pytest.approx(
                raw * expected_factor, abs=1e-12
            )

    def test_calibration_is_domain_agnostic(self) -> None:
        # JSDCalibrator does not vary by ClaimDomain — that is the
        # PrivilegedKnowledgeCalibrator's territory (PR3).
        cal = JSDCalibrator([{"a": 0.5, "b": 0.5}, {"a": 1.0, "b": 0.0}])
        results = {
            domain: cal.calibrate(0.5, "agent_x", domain) for domain in ClaimDomain
        }
        # All domains yield the same calibrated value.
        unique = set(results.values())
        assert len(unique) == 1

    def test_calibration_clamped_to_unit_interval(self) -> None:
        # raw can exceed 1.0 in malformed callers; calibrator must clamp.
        cal = JSDCalibrator([{"a": 0.5, "b": 0.5}, {"a": 0.5, "b": 0.5}])
        assert cal.calibrate(1.5, "agent_x", ClaimDomain.ARITH) == pytest.approx(1.0)
        assert cal.calibrate(-0.2, "agent_x", ClaimDomain.ARITH) == pytest.approx(0.0)

    def test_deterministic_across_repeated_calls(self) -> None:
        cal = JSDCalibrator([{"a": 0.5, "b": 0.5}, {"a": 1.0, "b": 0.0}])
        first = cal.calibrate(0.7, "agent_x", ClaimDomain.ARITH)
        for _ in range(99):
            assert cal.calibrate(0.7, "agent_x", ClaimDomain.ARITH) == first
