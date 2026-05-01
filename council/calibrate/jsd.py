"""Jensen-Shannon divergence helper + JSDCalibrator (W3/PR1).

The headline pieces are:

  - ``jsd_divergence(distributions)`` — pure function returning a float in
    [0, 1] over a list of discrete probability distributions encoded as
    ``dict[str, float]``. For ``n == 2`` it is the squared scipy
    Jensen-Shannon distance with base-2 normalisation; for ``n >= 3`` it
    is the mean of all pairwise JSDs over the same union-support
    encoding. The base-2 normalisation makes ``[0, 1]`` semantically
    "no disagreement → maximum disagreement" with the closed form
    ``δ_a vs δ_b == 1.0`` for disjoint Diracs.

  - ``JSDCalibrator(distributions)`` — fills the L3 ``Calibrator`` ABC
    declared in ``council/calibrate/base.py`` (W2/PR1, ADR-0008). The
    JSD is precomputed at construction; ``calibrate(raw, agent_id,
    domain)`` returns ``raw * (1 - jsd)``, clamped to ``[0, 1]``.

Lin (1991) defines JSD over n distributions; for the W3 PR1 baseline
we use scipy's pairwise primitive plus mean-of-pairs because (a) it
is the exact formula scipy provides, (b) it is the simplest correct
choice that does not pre-empt PR2's MUSE subset-ensemble divergence
(Kruse et al. 2025; ``papers/2 --- calibration and disagreement/``).
PR2 will introduce a separate helper rather than redefine this one.

Approved Exception #1 in ``.claude/rules/architecture.md`` permits
``council/symbolic/argue/aggregator.py`` to import this module — the
import direction is L2 → L3, not the reverse.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from scipy.spatial.distance import jensenshannon

from council.calibrate.base import Calibrator
from council.dialect.moves import ClaimDomain

_PROBABILITY_TOLERANCE = 1e-9


def _validate_distribution(dist: dict[str, float]) -> None:
    if any(v < 0 for v in dist.values()):
        raise ValueError("probabilities must be non-negative")
    total = sum(dist.values())
    if abs(total - 1.0) > _PROBABILITY_TOLERANCE:
        raise ValueError(f"distribution must sum to 1 (got {total!r})")


def _to_array(dist: dict[str, float], keys: tuple[str, ...]) -> np.ndarray:
    return np.array([dist.get(k, 0.0) for k in keys], dtype=float)


def jsd_divergence(distributions: list[dict[str, float]]) -> float:
    """Return JSD ∈ [0, 1] over the given discrete distributions (base-2).

    For ``n == 2`` returns the squared scipy Jensen-Shannon distance
    (``jensenshannon(p, q, base=2) ** 2``). For ``n >= 3`` returns the
    mean of all ``C(n, 2)`` pairwise JSDs computed over the union-support
    encoding (missing keys treated as zero-weight).

    Raises ``ValueError`` for malformed inputs: distributions that do not
    sum to 1, contain negative probabilities, or fewer than two
    distributions.
    """
    if len(distributions) < 2:
        raise ValueError("jsd_divergence requires at least two distributions")
    for dist in distributions:
        _validate_distribution(dist)

    union_keys: tuple[str, ...] = tuple(
        sorted({k for dist in distributions for k in dist})
    )
    arrays = [_to_array(dist, union_keys) for dist in distributions]

    pair_values = [
        float(jensenshannon(a, b, base=2)) ** 2
        for a, b in combinations(arrays, 2)
    ]
    return float(sum(pair_values) / len(pair_values))


class JSDCalibrator(Calibrator):
    """Calibrator scaling raw confidence by ``(1 - JSD(distributions))``.

    Constructed once per aggregation pass with the per-agent response
    distributions captured at deliberation time; ``calibrate`` then
    returns the same penalty for every (agent, domain) pair — the JSD
    is a global disagreement signal, not a per-agent one.
    Per-domain refinement is the territory of
    ``PrivilegedKnowledgeCalibrator`` (PR3).
    """

    def __init__(self, distributions: list[dict[str, float]]) -> None:
        self._jsd = jsd_divergence(distributions)

    @property
    def jsd(self) -> float:
        return self._jsd

    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float:
        scaled = raw_confidence * (1.0 - self._jsd)
        return max(0.0, min(1.0, scaled))
