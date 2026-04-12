"""Tests for evaluation/shapley.py.

All tests use precomputed value_fn tables — no model calls.
Three Shapley axioms are verified: efficiency, symmetry, null player.
"""

from __future__ import annotations

import pytest

from evaluation.shapley import ShapleyConfig, shapley_values


# ---------------------------------------------------------------------------
# Fixture value functions
# ---------------------------------------------------------------------------


def _additive_value_fn(coalition: frozenset[str]) -> float:
    """Each model contributes its index as a score; value = sum of indices."""
    values = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0}
    return sum(values.get(m, 0.0) for m in coalition)


def _symmetric_value_fn(coalition: frozenset[str]) -> float:
    """All models are interchangeable — value = len(coalition)."""
    return float(len(coalition))


def _null_player_value_fn(coalition: frozenset[str]) -> float:
    """Model 'C' never contributes — value = 1 if A or B present, else 0."""
    if "A" in coalition or "B" in coalition:
        return 1.0
    return 0.0


def _binary_value_fn(coalition: frozenset[str]) -> float:
    """Grand coalition {A, B} = 1.0; any subset is 0.5; empty = 0."""
    if coalition == frozenset(["A", "B"]):
        return 1.0
    if coalition:
        return 0.5
    return 0.0


# ---------------------------------------------------------------------------
# Efficiency axiom: Σ φ(i) = v(grand_coalition)
# ---------------------------------------------------------------------------


class TestEfficiencyAxiom:
    def test_two_models_additive(self) -> None:
        phi = shapley_values(["A", "B"], _additive_value_fn)
        grand = _additive_value_fn(frozenset(["A", "B"]))
        assert sum(phi.values()) == pytest.approx(grand)

    def test_three_models_additive(self) -> None:
        phi = shapley_values(["A", "B", "C"], _additive_value_fn)
        grand = _additive_value_fn(frozenset(["A", "B", "C"]))
        assert sum(phi.values()) == pytest.approx(grand)

    def test_binary_game_efficiency(self) -> None:
        phi = shapley_values(["A", "B"], _binary_value_fn)
        grand = _binary_value_fn(frozenset(["A", "B"]))
        assert sum(phi.values()) == pytest.approx(grand)

    def test_monte_carlo_efficiency_approx(self) -> None:
        models = [f"m{i}" for i in range(8)]
        values = {m: float(i + 1) for i, m in enumerate(models)}

        def fn(coalition: frozenset[str]) -> float:
            return sum(values[m] for m in coalition)

        cfg = ShapleyConfig(n_permutations=1000, seed=0)
        phi = shapley_values(models, fn, config=cfg)
        grand = fn(frozenset(models))
        assert sum(phi.values()) == pytest.approx(grand, abs=0.1)


# ---------------------------------------------------------------------------
# Symmetry axiom: interchangeable models get equal values
# ---------------------------------------------------------------------------


class TestSymmetryAxiom:
    def test_symmetric_game_equal_values(self) -> None:
        phi = shapley_values(["A", "B", "C"], _symmetric_value_fn)
        assert phi["A"] == pytest.approx(phi["B"])
        assert phi["B"] == pytest.approx(phi["C"])

    def test_two_symmetric_models(self) -> None:
        phi = shapley_values(["A", "B"], _symmetric_value_fn)
        assert phi["A"] == pytest.approx(phi["B"])


# ---------------------------------------------------------------------------
# Null player axiom: model with zero marginal contribution gets φ = 0
# ---------------------------------------------------------------------------


class TestNullPlayerAxiom:
    def test_null_player_gets_zero(self) -> None:
        phi = shapley_values(["A", "B", "C"], _null_player_value_fn)
        assert phi["C"] == pytest.approx(0.0)

    def test_non_null_players_get_positive(self) -> None:
        phi = shapley_values(["A", "B", "C"], _null_player_value_fn)
        assert phi["A"] > 0.0
        assert phi["B"] > 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_model_list(self) -> None:
        assert shapley_values([], _additive_value_fn) == {}

    def test_single_model(self) -> None:
        phi = shapley_values(["A"], _additive_value_fn)
        assert phi["A"] == pytest.approx(_additive_value_fn(frozenset(["A"])))

    def test_returns_all_model_keys(self) -> None:
        models = ["A", "B", "C"]
        phi = shapley_values(models, _additive_value_fn)
        assert set(phi.keys()) == set(models)

    def test_monte_carlo_runs_for_large_n(self) -> None:
        # 7 models (> 6 → Monte Carlo path)
        models = list("ABCDEFG")

        def fn(coalition: frozenset[str]) -> float:
            return float(len(coalition)) / len(models)

        cfg = ShapleyConfig(n_permutations=500, seed=42)
        phi = shapley_values(models, fn, config=cfg)
        assert len(phi) == 7
        assert sum(phi.values()) == pytest.approx(1.0, abs=0.05)

    def test_shapley_config_default(self) -> None:
        cfg = ShapleyConfig()
        assert cfg.n_permutations == 512
        assert cfg.seed == 0
