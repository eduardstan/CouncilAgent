"""MUSE-Greedy + MUSECalibrator (W3/PR2).

Implementation of MUSE (Multi-LLM Uncertainty via Subset Ensembles) from
Kruse et al. 2025, *Simple Yet Effective: An Information-Theoretic
Approach to Multi-LLM Uncertainty Quantification* (EMNLP / arXiv
2507.07236), under ``papers/2 --- calibration and disagreement/``.

This module ships only **MUSE-Greedy (Algorithm 1)**. The Conservative
variant (Algorithm 2) is a follow-up — see ADR-0016 §"Future work".

Algorithm 1 (binary case, paper §3.2):

  Require: P = {p_i}_{i=1}^N, c_i = |p_i_yes - 0.5|, β, ε_tol, m_min.
  1. Sort P by c_i descending; S ← {p_1}, u_epis_prev ← 0.
  2. for each p_j in sorted P \\ S:
  3.   S' ← S `union` {p_j}; p̄ ← mean(S').
  4.   u_epis ← (1/|S'|) Σ_{p ∈ S'} JS(p || p̄)².
  5.   u_alea ← (1/|S'|) Σ_{p ∈ S'} H(p).
  6.   if |S'| ≥ m_min and u_epis - u_epis_prev > ε_tol: break.
  7.   S ← S'; u_epis_prev ← u_epis.
  8. p̂_yes ← mean_{p ∈ S}(p_yes); u_total ← u_epis_prev + β · u_alea.

Defaults follow the paper's §4 + Figure 2 main-results setting:
  - ε_tol = 0.04
  - β     = 1.0
  - m_min = 2 (paper uses m_min=20 at dataset scale; ADR-0016 explains
    why the council-scale default is 2)

Multi-class generalisation: when ``yes_key`` is provided the sort
matches the paper exactly (binary task). When omitted, the sort uses
``c_i = max(p) - 1/k`` over the union support; this reduces to
``|p_yes - 0.5|`` at k=2 because ``max ∈ {p_yes, 1 - p_yes}``.

Architecture: pure Python + numpy/scipy (under the [calibrate] extra,
ADR-0015). Re-uses ``jsd_divergence`` from PR1 / W3 for the
``JS(p||p̄)²`` term. Approved Exception #1
(``argue/aggregator.py → calibrate/jsd.py``) extends naturally to
``argue/aggregator.py → calibrate/muse.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial.distance import jensenshannon

from council.calibrate.base import Calibrator
from council.calibrate.jsd import jsd_divergence
from council.dialect.moves import ClaimDomain

DEFAULT_BETA = 1.0
DEFAULT_EPS_TOL = 0.04
DEFAULT_M_MIN = 2


@dataclass(frozen=True, slots=True)
class MUSEResult:
    """Frozen output of ``muse_greedy``.

    ``selected_agent_ids`` is the subset chosen by Algorithm 1 in the
    order they were added (the highest-confidence agent first).
    ``consensus`` is the subset-mean distribution ``p̄_S`` over the
    union support — the calibrated reference all agents are scored
    against in MUSECalibrator. ``p_hat_yes`` is None when ``yes_key``
    was not supplied (multi-class case).
    """

    selected_agent_ids: tuple[str, ...]
    consensus: dict[str, float]
    u_epis: float
    u_alea: float
    u_total: float
    p_hat_yes: float | None


def _binary_entropy_bits(p_yes: float) -> float:
    """H(p) = -p log2 p - (1-p) log2 (1-p) (Kruse §3 aleatoric definition)."""
    if p_yes <= 0.0 or p_yes >= 1.0:
        return 0.0
    return float(-p_yes * np.log2(p_yes) - (1.0 - p_yes) * np.log2(1.0 - p_yes))


def _multiclass_entropy_bits(p: np.ndarray) -> float:
    """H(p) over the full support (multi-class generalisation of §3 H(p))."""
    nonzero = p[p > 0.0]
    return float(-np.sum(nonzero * np.log2(nonzero)))


def _validate_distribution(d: dict[str, float], *, tol: float = 1e-9) -> None:
    if any(v < 0 for v in d.values()):
        raise ValueError("probabilities must be non-negative")
    total = sum(d.values())
    if abs(total - 1.0) > tol:
        raise ValueError(f"distribution must sum to 1 (got {total!r})")


def muse_greedy(
    distributions: list[dict[str, float]],
    agent_ids: list[str],
    *,
    yes_key: str | None = None,
    beta: float = DEFAULT_BETA,
    eps_tol: float = DEFAULT_EPS_TOL,
    m_min: int = DEFAULT_M_MIN,
) -> MUSEResult:
    """Run MUSE-Greedy (Algorithm 1) on the given per-agent distributions."""
    if not distributions:
        raise ValueError("muse_greedy requires at least one distribution")
    if len(distributions) != len(agent_ids):
        raise ValueError("agent_ids length must match distributions length")
    if yes_key is not None and any(yes_key not in d for d in distributions):
        raise ValueError(f"yes_key {yes_key!r} missing from at least one distribution")
    for d in distributions:
        _validate_distribution(d)

    keys: tuple[str, ...] = tuple(sorted({k for d in distributions for k in d}))
    arrays: dict[str, np.ndarray] = {
        aid: np.array([d.get(k, 0.0) for k in keys], dtype=float)
        for aid, d in zip(agent_ids, distributions, strict=True)
    }

    if yes_key is not None:
        yes_index = keys.index(yes_key)
        confidences: list[tuple[str, float]] = [
            (aid, float(abs(arrays[aid][yes_index] - 0.5))) for aid in agent_ids
        ]
    else:
        k = len(keys)
        baseline = 1.0 / k if k > 0 else 0.0
        confidences = [
            (aid, float(np.max(arrays[aid]) - baseline)) for aid in agent_ids
        ]
    confidences.sort(key=lambda x: x[1], reverse=True)
    sorted_aids = [x[0] for x in confidences]

    selected: list[str] = [sorted_aids[0]]
    u_epis_prev = 0.0
    head_arr = arrays[sorted_aids[0]]
    if yes_key is not None:
        last_u_alea = _binary_entropy_bits(float(head_arr[keys.index(yes_key)]))
    else:
        last_u_alea = _multiclass_entropy_bits(head_arr)

    for candidate in sorted_aids[1:]:
        trial = [*selected, candidate]
        trial_arrs = [arrays[a] for a in trial]
        p_bar = np.mean(trial_arrs, axis=0)

        u_epis = float(
            np.mean([float(jensenshannon(arr, p_bar, base=2) ** 2) for arr in trial_arrs])
        )
        if yes_key is not None:
            yi = keys.index(yes_key)
            u_alea = float(
                np.mean([_binary_entropy_bits(float(arr[yi])) for arr in trial_arrs])
            )
        else:
            u_alea = float(np.mean([_multiclass_entropy_bits(arr) for arr in trial_arrs]))

        if len(trial) >= m_min and (u_epis - u_epis_prev) > eps_tol:
            break
        selected = trial
        u_epis_prev = u_epis
        last_u_alea = u_alea

    consensus_arr = np.mean([arrays[a] for a in selected], axis=0)
    consensus: dict[str, float] = {k: float(consensus_arr[i]) for i, k in enumerate(keys)}
    u_total = u_epis_prev + beta * last_u_alea
    p_hat_yes: float | None = None
    if yes_key is not None:
        p_hat_yes = float(consensus_arr[keys.index(yes_key)])

    return MUSEResult(
        selected_agent_ids=tuple(selected),
        consensus=consensus,
        u_epis=u_epis_prev,
        u_alea=last_u_alea,
        u_total=u_total,
        p_hat_yes=p_hat_yes,
    )


class MUSECalibrator(Calibrator):
    """Calibrator built around MUSE-Greedy's selected-subset consensus.

    Per ADR-0016, ``calibrate(raw, agent_id, domain)`` returns
    ``raw * (1 - JS(p_agent || p̄_S)²)`` clamped to [0, 1] for any
    agent_id known to the calibrator. Unknown agent_ids return
    ``raw_confidence`` unchanged (safe fallback for callers that pass
    extra agents post-hoc). ``selected_agent_ids`` is exposed for
    downstream metadata. Domain-agnostic — per-domain refinement is
    PrivilegedKnowledgeCalibrator (PR3) territory.
    """

    def __init__(
        self,
        distributions: list[dict[str, float]],
        agent_ids: list[str],
        *,
        yes_key: str | None = None,
        beta: float = DEFAULT_BETA,
        eps_tol: float = DEFAULT_EPS_TOL,
        m_min: int = DEFAULT_M_MIN,
    ) -> None:
        self._result = muse_greedy(
            distributions,
            agent_ids,
            yes_key=yes_key,
            beta=beta,
            eps_tol=eps_tol,
            m_min=m_min,
        )
        self._jsd_to_consensus: dict[str, float] = {
            aid: jsd_divergence([d, self._result.consensus])
            for aid, d in zip(agent_ids, distributions, strict=True)
        }

    @property
    def result(self) -> MUSEResult:
        return self._result

    @property
    def selected_agent_ids(self) -> tuple[str, ...]:
        return self._result.selected_agent_ids

    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float:
        if agent_id not in self._jsd_to_consensus:
            return raw_confidence
        penalty = self._jsd_to_consensus[agent_id]
        scaled = raw_confidence * (1.0 - penalty)
        return max(0.0, min(1.0, scaled))
