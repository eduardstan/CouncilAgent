"""L3 calibrated disagreement — JSD, MUSE, privileged-knowledge calibration.

W2/PR1 shipped the Calibrator ABC + IdentityCalibrator. W3/PR1 adds
JSDCalibrator + jsd_divergence; W3/PR2 adds MUSECalibrator + muse_greedy
(Kruse et al. 2025); W3/PR3 adds PrivilegedKnowledgeCalibrator (Anonymous
2026); IsotonicCalibrator follows in W3/PR4.
"""

from council.calibrate.base import Calibrator, IdentityCalibrator
from council.calibrate.jsd import JSDCalibrator, jsd_divergence
from council.calibrate.muse import MUSECalibrator, MUSEResult, muse_greedy
from council.calibrate.privileged import (
    DEFAULT_DOMAIN_GAPS,
    DomainGap,
    PrivilegedKnowledgeCalibrator,
)

__all__ = [
    "DEFAULT_DOMAIN_GAPS",
    "Calibrator",
    "DomainGap",
    "IdentityCalibrator",
    "JSDCalibrator",
    "MUSECalibrator",
    "MUSEResult",
    "PrivilegedKnowledgeCalibrator",
    "jsd_divergence",
    "muse_greedy",
]
