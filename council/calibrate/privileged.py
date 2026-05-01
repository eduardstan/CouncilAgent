"""PrivilegedKnowledgeCalibrator (W3/PR3).

Per-domain calibration grounded in Anonymous 2026,
*Masked by Consensus: Disentangling Privileged Knowledge in LLM
Correctness* (OpenReview ``du3ZBA8Z3Z``), under
``papers/2 --- calibration and disagreement/``.

Paper §4.3 finding: on disagreement subsets, factual tasks exhibit a
~5% premium gap (self-probe AUC > peer-probe AUC, statistically
significant across Mintaka, TriviaQA, HotPotQA), while mathematical
reasoning shows no premium gap (paper Figure 3 right panel).
``COUNCILAGENT_NS_MASTER_PLAN.md`` line 768 extends the empirical
table with "coding partial" (master-plan-derived; the paper does not
measure coding).

The Calibrator interface freezes ``calibrate(raw, agent_id,
claim_domain) -> float``. ADR-0017 (sibling commit) documents the
mixing-model interpretation of "privileged knowledge" within this
interface; in short:

    calibrated = self_weight * raw + peer_weight * peer_consensus[agent]

with weights derived from a per-domain ``DomainGap`` (gap ∈ [0, 1]):

    self_weight = 0.5 + gap/2
    peer_weight = 0.5 - gap/2

For an agent_id not present in ``peer_consensus``, the calibrator
returns ``raw_confidence`` unchanged — safe fallback for callers that
pass extra agents post-hoc.
"""

from __future__ import annotations

from dataclasses import dataclass

from council.calibrate.base import Calibrator
from council.dialect.moves import ClaimDomain


@dataclass(frozen=True, slots=True)
class DomainGap:
    """Privileged-knowledge gap for a claim domain.

    ``gap`` is the empirical premium gap from Anonymous 2026 (or our
    master-plan-grounded extension for unmeasured domains). Bounded to
    ``[0, 1]``: the paper's findings only support non-negative gaps,
    and a gap above 1 would yield negative ``peer_weight``.
    """

    gap: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.gap <= 1.0:
            raise ValueError(f"gap must lie in [0, 1] (got {self.gap!r})")

    @property
    def self_weight(self) -> float:
        return 0.5 + self.gap / 2.0

    @property
    def peer_weight(self) -> float:
        return 0.5 - self.gap / 2.0


#: Default per-domain gaps grounded in Anonymous 2026 §4.3 (Figure 3) and
#: ``COUNCILAGENT_NS_MASTER_PLAN.md`` line 768. ADR-0017 explains the
#: extension to formal-symbolic domains.
DEFAULT_DOMAIN_GAPS: dict[ClaimDomain, DomainGap] = {
    ClaimDomain.FREE: DomainGap(0.05),    # factual: ~5% premium gap (paper)
    ClaimDomain.ARITH: DomainGap(0.0),    # math: no premium gap (paper)
    ClaimDomain.CODE: DomainGap(0.025),   # coding: master plan "partial"
    ClaimDomain.FOL: DomainGap(0.0),      # formal logic: math-like (no paper data)
    ClaimDomain.LTLF: DomainGap(0.0),     # LTL_f formula: formal-symbolic
}


class PrivilegedKnowledgeCalibrator(Calibrator):
    """Per-domain self/peer mixing calibrator.

    ``peer_consensus[agent_id]`` should be a leave-one-out peer mean
    confidence (the calibrator is agnostic to how it is computed). The
    domain dispatch reads ``DEFAULT_DOMAIN_GAPS`` unless overridden via
    ``domain_gaps``. Domain-agnostic refinement (JSD-based) is the
    JSDCalibrator (W3/PR1) territory; this calibrator is the *domain*
    axis.
    """

    def __init__(
        self,
        peer_consensus: dict[str, float],
        *,
        domain_gaps: dict[ClaimDomain, DomainGap] | None = None,
    ) -> None:
        self._peer = dict(peer_consensus)
        self._gaps = dict(domain_gaps) if domain_gaps is not None else dict(DEFAULT_DOMAIN_GAPS)

    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float:
        if agent_id not in self._peer:
            return raw_confidence
        gap = self._gaps[claim_domain]
        mixed = gap.self_weight * raw_confidence + gap.peer_weight * self._peer[agent_id]
        return max(0.0, min(1.0, mixed))
