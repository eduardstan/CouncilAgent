"""Tests for council.calibrate.muse — MUSE-Greedy helper + MUSECalibrator.

Pins the helper to Algorithm 1 of Kruse et al. 2025
("Simple Yet Effective: An Information-Theoretic Approach to Multi-LLM
Uncertainty Quantification", EMNLP; arXiv:2507.07236), under
``papers/2 --- calibration and disagreement/``.

Reference values are computed inline using scipy primitives so the
helper is verified against the paper's algorithm structure, not against
itself.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pytest
from scipy.spatial.distance import jensenshannon

from council.calibrate.muse import MUSEResult, muse_greedy


def _binary_entropy_bits(p_yes: float) -> float:
    """H(p) = -p log2 p - (1-p) log2 (1-p) — Kruse §3 aleatoric definition."""
    if p_yes <= 0.0 or p_yes >= 1.0:
        return 0.0
    return float(-p_yes * np.log2(p_yes) - (1.0 - p_yes) * np.log2(1.0 - p_yes))


def _js_squared(p: np.ndarray, q: np.ndarray) -> float:
    """JS(p||q)² in base-2 — what Kruse Algorithm 1 line 5 computes."""
    return float(jensenshannon(p, q, base=2) ** 2)


class _Step(NamedTuple):
    selected: tuple[str, ...]
    u_epis: float
    u_alea: float


def _reference_muse_greedy(
    distributions: list[dict[str, float]],
    agent_ids: list[str],
    *,
    yes_key: str,
    beta: float = 1.0,
    eps_tol: float = 0.04,
    m_min: int = 2,
) -> _Step:
    """Reproduce Kruse Algorithm 1 (binary case) line-by-line for assertions."""
    keys: tuple[str, ...] = tuple(
        sorted({k for d in distributions for k in d})
    )
    arrays = [np.array([d.get(k, 0.0) for k in keys]) for d in distributions]
    yes_index = keys.index(yes_key)

    confidences = [(aid, float(abs(arr[yes_index] - 0.5))) for aid, arr in zip(agent_ids, arrays, strict=True)]
    confidences.sort(key=lambda x: x[1], reverse=True)
    sorted_aids = [x[0] for x in confidences]
    aid_to_arr = dict(zip(agent_ids, arrays, strict=True))

    selected = [sorted_aids[0]]
    u_epis_prev = 0.0
    last_u_alea = _binary_entropy_bits(float(aid_to_arr[selected[0]][yes_index]))

    for candidate in sorted_aids[1:]:
        trial = selected + [candidate]
        trial_arrs = [aid_to_arr[a] for a in trial]
        p_bar = np.mean(trial_arrs, axis=0)
        u_epis = float(np.mean([_js_squared(arr, p_bar) for arr in trial_arrs]))
        u_alea = float(
            np.mean([_binary_entropy_bits(float(arr[yes_index])) for arr in trial_arrs])
        )
        if len(trial) >= m_min and (u_epis - u_epis_prev) > eps_tol:
            break
        selected = trial
        u_epis_prev = u_epis
        last_u_alea = u_alea

    return _Step(
        selected=tuple(selected), u_epis=u_epis_prev, u_alea=last_u_alea
    )


# ---------------------------------------------------------------------------
# Algorithm-fidelity tests
# ---------------------------------------------------------------------------


class TestMUSEGreedyAlgorithm:
    """Pin muse_greedy to Algorithm 1 of Kruse et al. 2025."""

    def test_n3_binary_matches_reference(self) -> None:
        # Three binary distributions with three different confidences.
        dists = [
            {"yes": 0.9, "no": 0.1},   # A: c=0.4 (highest)
            {"yes": 0.2, "no": 0.8},   # C: c=0.3
            {"yes": 0.55, "no": 0.45}, # B: c=0.05 (lowest)
        ]
        aids = ["A", "C", "B"]
        ref = _reference_muse_greedy(dists, aids, yes_key="yes")
        result = muse_greedy(dists, aids, yes_key="yes")

        assert isinstance(result, MUSEResult)
        assert result.selected_agent_ids == ref.selected
        assert result.u_epis == pytest.approx(ref.u_epis, abs=1e-12)
        assert result.u_alea == pytest.approx(ref.u_alea, abs=1e-12)

    def test_sort_uses_paper_confidence(self) -> None:
        # The selected subset must start with the highest-confidence agent.
        # c_A = 0.45, c_B = 0.30, c_C = 0.10 → selected[0] = A.
        dists = [
            {"yes": 0.95, "no": 0.05}, # A
            {"yes": 0.20, "no": 0.80}, # B
            {"yes": 0.40, "no": 0.60}, # C
        ]
        result = muse_greedy(dists, ["A", "B", "C"], yes_key="yes")
        assert result.selected_agent_ids[0] == "A"

    def test_m_min_forces_inclusion_past_natural_break(self) -> None:
        # Two highly-disagreeing agents (would normally trigger ε_tol break),
        # but m_min=3 forces inclusion of all 3.
        dists = [
            {"yes": 0.99, "no": 0.01},
            {"yes": 0.50, "no": 0.50},
            {"yes": 0.01, "no": 0.99},
        ]
        result = muse_greedy(
            dists, ["A", "B", "C"], yes_key="yes", m_min=3, eps_tol=0.001
        )
        assert len(result.selected_agent_ids) == 3

    def test_eps_tol_breaks_subset_extension(self) -> None:
        # With m_min=2 and very small ε_tol, the third (disagreeing)
        # candidate is rejected — selected subset stays at the first 2.
        dists = [
            {"yes": 0.95, "no": 0.05}, # A high yes
            {"yes": 0.90, "no": 0.10}, # B near A → low JS
            {"yes": 0.05, "no": 0.95}, # C disagrees → big JS jump
        ]
        result = muse_greedy(
            dists, ["A", "B", "C"], yes_key="yes", m_min=2, eps_tol=0.05
        )
        # The break is triggered before C is committed → C not in subset.
        assert "C" not in result.selected_agent_ids
        assert "A" in result.selected_agent_ids
        assert "B" in result.selected_agent_ids

    def test_single_agent_input(self) -> None:
        # No candidates to add; selected stays singleton.
        dists = [{"yes": 0.7, "no": 0.3}]
        result = muse_greedy(dists, ["solo"], yes_key="yes")
        assert result.selected_agent_ids == ("solo",)
        assert result.u_epis == pytest.approx(0.0, abs=1e-12)
        # Aleatoric uncertainty equals the binary entropy of solo's prediction.
        assert result.u_alea == pytest.approx(_binary_entropy_bits(0.7), abs=1e-12)
        assert result.p_hat_yes == pytest.approx(0.7)

    def test_all_identical_agents_yield_zero_disagreement(self) -> None:
        dists = [{"yes": 0.6, "no": 0.4}] * 3
        result = muse_greedy(dists, ["A", "B", "C"], yes_key="yes")
        assert len(result.selected_agent_ids) == 3
        assert result.u_epis == pytest.approx(0.0, abs=1e-12)
        assert result.p_hat_yes == pytest.approx(0.6)

    def test_p_hat_yes_is_subset_mean(self) -> None:
        dists = [
            {"yes": 0.9, "no": 0.1},
            {"yes": 0.7, "no": 0.3},
            {"yes": 0.6, "no": 0.4},
        ]
        result = muse_greedy(dists, ["A", "B", "C"], yes_key="yes")
        selected_yes = [
            dists[["A", "B", "C"].index(aid)]["yes"]
            for aid in result.selected_agent_ids
        ]
        assert result.p_hat_yes == pytest.approx(
            sum(selected_yes) / len(selected_yes), abs=1e-12
        )

    def test_u_total_combines_epis_and_alea(self) -> None:
        dists = [{"yes": 0.7, "no": 0.3}, {"yes": 0.65, "no": 0.35}]
        result = muse_greedy(
            dists, ["A", "B"], yes_key="yes", beta=1.0, m_min=2, eps_tol=0.5
        )
        assert result.u_total == pytest.approx(
            result.u_epis + 1.0 * result.u_alea, abs=1e-12
        )

    def test_deterministic_across_repeated_calls(self) -> None:
        dists = [
            {"yes": 0.8, "no": 0.2},
            {"yes": 0.4, "no": 0.6},
            {"yes": 0.65, "no": 0.35},
        ]
        first = muse_greedy(dists, ["A", "B", "C"], yes_key="yes")
        for _ in range(99):
            assert muse_greedy(dists, ["A", "B", "C"], yes_key="yes") == first


class TestMUSEGreedyMultiClass:
    """k≥3 generalisation — paper covers binary, we extend cleanly."""

    def test_three_class_uses_max_minus_uniform_for_sort(self) -> None:
        # k=3, uniform baseline = 1/3. Confidences:
        #   A: max=0.7 → c=0.7-1/3 ≈ 0.367 (highest)
        #   B: max=0.5 → c=0.167
        #   C: max=0.4 → c=0.067 (lowest)
        dists = [
            {"x": 0.7, "y": 0.2, "z": 0.1},
            {"x": 0.5, "y": 0.3, "z": 0.2},
            {"x": 0.4, "y": 0.3, "z": 0.3},
        ]
        # Without yes_key, helper uses k≥2 generalisation (max - 1/k).
        result = muse_greedy(dists, ["A", "B", "C"])
        assert result.selected_agent_ids[0] == "A"
        # p_hat_yes is None because no yes_key provided.
        assert result.p_hat_yes is None


class TestMUSEGreedyValidation:
    def test_empty_distributions_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            muse_greedy([], [], yes_key="yes")

    def test_mismatched_lengths_raise(self) -> None:
        with pytest.raises(ValueError, match="agent_ids"):
            muse_greedy(
                [{"yes": 1.0, "no": 0.0}, {"yes": 0.5, "no": 0.5}],
                ["only_one"],
                yes_key="yes",
            )

    def test_yes_key_missing_from_distribution_raises(self) -> None:
        with pytest.raises(ValueError, match="yes_key"):
            muse_greedy(
                [{"foo": 1.0}, {"foo": 0.5, "bar": 0.5}],
                ["A", "B"],
                yes_key="yes",
            )

    def test_invalid_distribution_raises(self) -> None:
        # jsd_divergence's validation should propagate when the algorithm
        # touches a bad distribution.
        with pytest.raises(ValueError):
            muse_greedy(
                [{"yes": 0.6, "no": 0.5}, {"yes": 0.3, "no": 0.7}],
                ["A", "B"],
                yes_key="yes",
            )
