"""L3 calibrated disagreement — JSD, MUSE, privileged-knowledge calibration.

W2/PR1 shipped the Calibrator ABC + IdentityCalibrator. W3/PR1 adds
JSDCalibrator + jsd_divergence; remaining concretes (MUSE, Privileged,
Isotonic) follow in W3/PR2-PR4.
"""

from council.calibrate.base import Calibrator, IdentityCalibrator
from council.calibrate.jsd import JSDCalibrator, jsd_divergence

__all__ = [
    "Calibrator",
    "IdentityCalibrator",
    "JSDCalibrator",
    "jsd_divergence",
]
