"""L3 calibrated disagreement — JSD, MUSE, privileged-knowledge calibration.

W2/PR1 shipped the Calibrator ABC + IdentityCalibrator. W3/PR1 adds
JSDCalibrator + jsd_divergence; W3/PR2 adds MUSECalibrator + muse_greedy
(Kruse et al. 2025); remaining concretes (Privileged, Isotonic) follow
in W3/PR3-PR4.
"""

from council.calibrate.base import Calibrator, IdentityCalibrator
from council.calibrate.jsd import JSDCalibrator, jsd_divergence
from council.calibrate.muse import MUSECalibrator, MUSEResult, muse_greedy

__all__ = [
    "Calibrator",
    "IdentityCalibrator",
    "JSDCalibrator",
    "MUSECalibrator",
    "MUSEResult",
    "jsd_divergence",
    "muse_greedy",
]
