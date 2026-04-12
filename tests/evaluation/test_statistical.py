"""Tests for evaluation/statistical.py.

bootstrap_ci and core AIPW logic are pure Python — always run.
wilcoxon_test and MixedEffectsModel require benchmark extras (scipy, statsmodels)
and are skipped if not installed.
"""

from __future__ import annotations

import pytest

from evaluation.statistical import (
    AIPWEstimator,
    AIPWResult,
    MixedEffectsModel,
    ObservationRow,
    bootstrap_ci,
    wilcoxon_test,
)


# ---------------------------------------------------------------------------
# bootstrap_ci
# ---------------------------------------------------------------------------


class TestBootstrapCI:
    def test_returns_two_floats(self) -> None:
        lo, hi = bootstrap_ci([0.7, 0.8, 0.9, 0.6, 0.75], seed=0)
        assert isinstance(lo, float) and isinstance(hi, float)

    def test_lower_le_upper(self) -> None:
        lo, hi = bootstrap_ci([0.5, 0.6, 0.7], seed=42)
        assert lo <= hi

    def test_ci_width_shrinks_with_n(self) -> None:
        import random
        rng = random.Random(0)
        small = [rng.gauss(0.7, 0.1) for _ in range(20)]
        large = [rng.gauss(0.7, 0.1) for _ in range(200)]
        lo_s, hi_s = bootstrap_ci(small, seed=0)
        lo_l, hi_l = bootstrap_ci(large, seed=0)
        assert (hi_s - lo_s) > (hi_l - lo_l)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            bootstrap_ci([])

    def test_deterministic_with_seed(self) -> None:
        values = [0.1, 0.5, 0.9, 0.4, 0.6]
        r1 = bootstrap_ci(values, seed=7)
        r2 = bootstrap_ci(values, seed=7)
        assert r1 == r2

    def test_all_same_value(self) -> None:
        lo, hi = bootstrap_ci([0.5, 0.5, 0.5], seed=0)
        assert lo == pytest.approx(0.5)
        assert hi == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# wilcoxon_test
# ---------------------------------------------------------------------------


class TestWilcoxonTest:
    def test_identical_series_high_p(self) -> None:
        pytest.importorskip("scipy")
        a = [0.5, 0.6, 0.7, 0.8, 0.9]
        stat, p = wilcoxon_test(a, a)
        assert p > 0.05  # no significant difference between identical series

    def test_very_different_series_low_p(self) -> None:
        pytest.importorskip("scipy")
        a = [0.9] * 20
        b = [0.1] * 20
        stat, p = wilcoxon_test(a, b)
        assert p < 0.05

    def test_different_length_raises(self) -> None:
        pytest.importorskip("scipy")
        with pytest.raises(ValueError, match="same length"):
            wilcoxon_test([0.5, 0.6], [0.5])

    def test_too_few_raises(self) -> None:
        pytest.importorskip("scipy")
        with pytest.raises(ValueError, match="at least 2"):
            wilcoxon_test([0.5], [0.5])

    def test_returns_statistic_and_pvalue(self) -> None:
        pytest.importorskip("scipy")
        stat, p = wilcoxon_test([0.5, 0.6, 0.7], [0.4, 0.5, 0.6])
        assert isinstance(stat, float)
        assert 0.0 <= p <= 1.0


# ---------------------------------------------------------------------------
# AIPWEstimator
# ---------------------------------------------------------------------------


class TestAIPWEstimator:
    def test_aipw_result_is_frozen(self) -> None:
        r = AIPWResult(ate=0.1, se=0.05, ci_lower=0.0, ci_upper=0.2)
        with pytest.raises((AttributeError, TypeError)):
            r.ate = 0.5  # type: ignore[misc]

    def test_ipw_uniform_propensity_ate_close_to_diff_of_means(self) -> None:
        pytest.importorskip("numpy")
        # With uniform propensity (0.5) and no outcome model,
        # IPW ATE ≈ mean(treated outcomes) - mean(control outcomes).
        treated = [1.0] * 10
        control = [0.0] * 10
        treatment = [1] * 10 + [0] * 10
        outcomes = treated + control
        propensities = [0.5] * 20

        est = AIPWEstimator()
        result = est.estimate(treatment, outcomes, propensities)
        assert result.ate == pytest.approx(1.0, abs=0.01)

    def test_ate_ci_contains_ate(self) -> None:
        pytest.importorskip("numpy")
        treatment = [1, 0, 1, 0, 1, 0]
        outcomes = [0.8, 0.6, 0.9, 0.5, 0.7, 0.6]
        propensities = [0.5] * 6
        est = AIPWEstimator()
        result = est.estimate(treatment, outcomes, propensities)
        assert result.ci_lower <= result.ate <= result.ci_upper

    def test_length_mismatch_raises(self) -> None:
        # Length check happens before numpy import — no importorskip needed.
        est = AIPWEstimator()
        with pytest.raises(ValueError):
            est.estimate([1, 0], [0.5], [0.5, 0.5])

    def test_fit_estimate_runs_with_sklearn(self) -> None:
        pytest.importorskip("sklearn")
        configs = [{"max_rounds": 1.0}] * 5 + [{"max_rounds": 2.0}] * 5
        outcomes = [0.7, 0.8, 0.75, 0.72, 0.68, 0.85, 0.9, 0.88, 0.82, 0.87]
        propensities = [0.5] * 10
        est = AIPWEstimator()
        est.fit(configs, outcomes, propensities)
        treatment = [0] * 5 + [1] * 5
        result = est.estimate(treatment, outcomes, propensities)
        assert isinstance(result.ate, float)
        assert result.ci_lower <= result.ci_upper


# ---------------------------------------------------------------------------
# MixedEffectsModel
# ---------------------------------------------------------------------------


class TestMixedEffectsModel:
    def _make_data(self) -> list[ObservationRow]:
        rows = []
        for config in ["council", "baseline"]:
            for domain in ["math", "factual"]:
                for _ in range(5):
                    rows.append(
                        ObservationRow(
                            accuracy=0.8 if config == "council" else 0.6,
                            config_hash=config,
                            domain=domain,
                        )
                    )
        return rows

    def test_fit_returns_result(self) -> None:
        pytest.importorskip("statsmodels")
        pytest.importorskip("pandas")
        data = self._make_data()
        model = MixedEffectsModel()
        result = model.fit(data)
        assert isinstance(result.fixed_effects, dict)
        assert isinstance(result.random_effects, dict)
        assert isinstance(result.aic, float)

    def test_empty_data_raises(self) -> None:
        pytest.importorskip("statsmodels")
        with pytest.raises(ValueError, match="non-empty"):
            MixedEffectsModel().fit([])

    def test_single_domain_raises(self) -> None:
        pytest.importorskip("statsmodels")
        pytest.importorskip("pandas")
        data = [
            ObservationRow(accuracy=0.8, config_hash="council", domain="math"),
            ObservationRow(accuracy=0.7, config_hash="baseline", domain="math"),
        ]
        with pytest.raises(ValueError, match="2 distinct domains"):
            MixedEffectsModel().fit(data)

    def test_observation_row_is_frozen(self) -> None:
        row = ObservationRow(accuracy=0.8, config_hash="x", domain="math")
        with pytest.raises((AttributeError, TypeError)):
            row.accuracy = 0.9  # type: ignore[misc]
