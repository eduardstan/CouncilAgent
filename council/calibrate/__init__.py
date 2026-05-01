"""L3 calibrated disagreement — JSD, MUSE, privileged-knowledge, isotonic.

W2/PR1 shipped the Calibrator ABC + IdentityCalibrator. W3/PR1 adds
JSDCalibrator + jsd_divergence; W3/PR2 adds MUSECalibrator + muse_greedy
(Kruse et al. 2025); W3/PR3 adds PrivilegedKnowledgeCalibrator (Anonymous
2026); W3/PR4 adds IsotonicCalibrator + expected_calibration_error
(Guo et al. 2017).
"""

from council.calibrate.base import Calibrator, IdentityCalibrator
from council.calibrate.isotonic import (
    IsotonicCalibrator,
    expected_calibration_error,
)
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
    "IsotonicCalibrator",
    "JSDCalibrator",
    "MUSECalibrator",
    "MUSEResult",
    "PrivilegedKnowledgeCalibrator",
    "expected_calibration_error",
    "jsd_divergence",
    "muse_greedy",
]
