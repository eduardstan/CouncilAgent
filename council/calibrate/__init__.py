"""L3 calibrated disagreement — JSD, MUSE, privileged-knowledge calibration.

W2/PR1 ships the Calibrator ABC + IdentityCalibrator only. W3 fills the
concrete subclasses (JSD, MUSE, Privileged, Isotonic).
"""

from council.calibrate.base import Calibrator, IdentityCalibrator

__all__ = ["Calibrator", "IdentityCalibrator"]
