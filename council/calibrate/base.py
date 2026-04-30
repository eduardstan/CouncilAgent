"""L3 calibration — Calibrator ABC + IdentityCalibrator.

The Calibrator ABC is the L3 contract. W2's `build_qbaf(trace, calibrator)`
consumes it; W3 fills concrete subclasses (JSDCalibrator, MUSECalibrator,
PrivilegedKnowledgeCalibrator, IsotonicCalibrator).

Signature is frozen by `.claude/rules/architecture.md` §"Required contracts".
The location is justified in `docs/adr/0008-calibrator-abc-location.md`.

`IdentityCalibrator` ships in W2/PR1 to:
  - smoke-test the ABC without depending on numpy / scipy (W3 territory)
  - provide a non-None default for callers that want a calibrator object
    rather than `None` — `build_qbaf(trace, IdentityCalibrator())` is
    byte-equivalent to `build_qbaf(trace)`
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from council.dialect.moves import ClaimDomain


class Calibrator(ABC):
    """L3 calibration — map a raw confidence to a calibrated confidence.

    Concrete implementations:
      - JSDCalibrator (W3) — Jensen-Shannon divergence on response distributions
      - MUSECalibrator (W3) — subset-ensemble divergence (Kruse et al. 2025)
      - PrivilegedKnowledgeCalibrator (W3) — per-domain weights from TaskProfile
      - IsotonicCalibrator (W3) — temperature-scaled isotonic regression
    """

    @abstractmethod
    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float:
        """Return calibrated confidence in [0, 1] given the raw signal + context."""


class IdentityCalibrator(Calibrator):
    """No-op calibrator — returns raw_confidence unchanged.

    Useful as a default fallback and as the trivial baseline that concrete
    W3 calibrators must measure against (e.g., JSDCalibrator should improve
    expected calibration error vs IdentityCalibrator on GSM8K).
    """

    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float:
        return raw_confidence
