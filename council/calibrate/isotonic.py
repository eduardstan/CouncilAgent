"""IsotonicCalibrator + Expected Calibration Error (W3/PR4).

The L3 isotonic-regression calibrator and the ECE measurement helper
that grounds its acceptance criterion (master plan §7 W3: "ECE on a
held-out GSM8K split drops below 0.05").

ECE definition follows Guo et al. 2017 ("On Calibration of Modern
Neural Networks", ICML; arXiv:1706.04599). Inputs are bucketed into
``n_bins`` equal-width bins on ``[0, 1]``; each bin contributes
``|mean_confidence - accuracy| * (bin_size / N)`` to the total.

IsotonicCalibrator wraps ``sklearn.isotonic.IsotonicRegression``. It is
domain- and agent-agnostic — the per-domain axis is the
``PrivilegedKnowledgeCalibrator`` (W3/PR3) territory, and the
information-theoretic axis is the JSD/MUSE family
(W3/PR1, W3/PR2). Composition with the others is a future
``ChainedCalibrator`` slice (ADR-0017 §"Future work").

Architecture: under the ``[calibrate]`` extra (ADR-0015). No model
calls; pure numpy + scikit-learn.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
from sklearn.isotonic import IsotonicRegression

from council.calibrate.base import Calibrator
from council.dialect.moves import ClaimDomain


def expected_calibration_error(
    confidences: list[float],
    correct: list[int],
    *,
    n_bins: int = 10,
) -> float:
    """Standard equal-width-bin ECE (Guo et al. 2017).

    ``confidences`` is the model's predicted probability that each
    sample is correct; ``correct`` is the {0, 1} ground-truth label.
    Empty inputs are treated as vacuously well-calibrated (ECE = 0).
    """
    if n_bins <= 0:
        raise ValueError(f"n_bins must be positive (got {n_bins})")
    if len(confidences) != len(correct):
        raise ValueError(
            f"confidences and correct must have the same length "
            f"({len(confidences)} vs {len(correct)})"
        )
    if any(c not in (0, 1) for c in correct):
        raise ValueError("correct entries must be 0 or 1")
    n = len(confidences)
    if n == 0:
        return 0.0

    confs = np.asarray(confidences, dtype=float)
    labels = np.asarray(correct, dtype=float)
    edges = np.linspace(0.0, 1.0, num=n_bins + 1)
    ece = 0.0
    for lo, hi in pairwise(edges):
        # Right-closed bins; the first bin includes 0.
        mask = (
            (confs >= lo) & (confs <= hi)
            if lo == 0.0
            else (confs > lo) & (confs <= hi)
        )
        bin_size = int(mask.sum())
        if bin_size == 0:
            continue
        bin_conf = float(confs[mask].mean())
        bin_acc = float(labels[mask].mean())
        ece += abs(bin_conf - bin_acc) * bin_size / n
    return ece


class IsotonicCalibrator(Calibrator):
    """L3 calibrator wrapping sklearn's IsotonicRegression.

    Construct with a list of ``(raw_confidence, correct)`` training
    pairs; the calibrator fits the monotone non-decreasing map at
    construction. ``calibrate(raw, agent_id, claim_domain)`` returns
    the fitted prediction at ``raw``, clamped to ``[0, 1]``. Domain
    and agent_id are accepted for ABC compatibility but ignored.
    """

    def __init__(self, training_data: list[tuple[float, int]]) -> None:
        if not training_data:
            raise ValueError("training data must be non-empty")
        for raw, correct in training_data:
            if not 0.0 <= raw <= 1.0:
                raise ValueError(f"raw values must lie in [0, 1] (got {raw})")
            if correct not in (0, 1):
                raise ValueError(f"correct entries must be 0 or 1 (got {correct})")
        x = np.array([r for r, _ in training_data], dtype=float)
        y = np.array([c for _, c in training_data], dtype=float)
        self._model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self._model.fit(x, y)

    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float:
        clamped_input = max(0.0, min(1.0, raw_confidence))
        prediction = float(self._model.predict([clamped_input])[0])
        return max(0.0, min(1.0, prediction))
