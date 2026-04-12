"""Shapley value computation for CouncilAgent model contribution analysis.

Computes how much each model in the council contributes to the overall
accuracy. Uses exact enumeration for n_models ≤ 6, Monte Carlo approximation
for larger sets.

Three Shapley axioms must hold (verified by test suite):
- Efficiency: Σ φ(i) = v(grand_coalition)
- Symmetry:   interchangeable models get equal Shapley values
- Null player: a model that never contributes gets φ = 0

The value_fn is always injected — never called internally — so this module
has zero model calls (Constitution §1).
"""

from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True, slots=True)
class ShapleyConfig:
    """Configuration for Shapley value computation."""

    n_permutations: int = 512
    seed: int = 0


def shapley_values(
    model_ids: list[str],
    value_fn: Callable[[frozenset[str]], float],
    config: ShapleyConfig | None = None,
) -> dict[str, float]:
    """Compute Shapley values for each model.

    model_ids: List of model identifier strings.
    value_fn:  Coalition → scalar value (accuracy on task set for that subset).
               Must return 0.0 for the empty set.
    config:    Computation parameters. Defaults to ShapleyConfig().

    Returns a dict mapping each model_id to its Shapley value.

    Algorithm:
    - n_models ≤ 6: exact permutation enumeration (n! permutations).
    - n_models > 6: Monte Carlo approximation (config.n_permutations samples).
    """
    cfg = config if config is not None else ShapleyConfig()
    n = len(model_ids)

    if n == 0:
        return {}
    if n == 1:
        return {model_ids[0]: value_fn(frozenset(model_ids))}

    if n <= 6:
        return _exact_shapley(model_ids, value_fn)
    return _monte_carlo_shapley(model_ids, value_fn, cfg)


def _exact_shapley(
    model_ids: list[str],
    value_fn: Callable[[frozenset[str]], float],
) -> dict[str, float]:
    """Exact Shapley via full permutation enumeration."""
    n = len(model_ids)
    phi: dict[str, float] = {m: 0.0 for m in model_ids}

    for perm in itertools.permutations(model_ids):
        for i, model in enumerate(perm):
            coalition_with = frozenset(perm[: i + 1])
            coalition_without = frozenset(perm[:i])
            marginal = value_fn(coalition_with) - value_fn(coalition_without)
            phi[model] += marginal

    n_fact = math.factorial(n)
    return {m: phi[m] / n_fact for m in model_ids}


def _monte_carlo_shapley(
    model_ids: list[str],
    value_fn: Callable[[frozenset[str]], float],
    cfg: ShapleyConfig,
) -> dict[str, float]:
    """Monte Carlo Shapley approximation via random permutation sampling."""
    phi: dict[str, float] = {m: 0.0 for m in model_ids}
    rng = random.Random(cfg.seed)

    for _ in range(cfg.n_permutations):
        perm = list(model_ids)
        rng.shuffle(perm)
        for i, model in enumerate(perm):
            coalition_with = frozenset(perm[: i + 1])
            coalition_without = frozenset(perm[:i])
            marginal = value_fn(coalition_with) - value_fn(coalition_without)
            phi[model] += marginal

    return {m: phi[m] / cfg.n_permutations for m in model_ids}
