"""Integration tests — IsotonicCalibrator on a real OpenRouter SLM
predictions cached at tests/calibrate/fixtures/gsm8k_subset.json.

Gated by ``@pytest.mark.integration`` and ``RUN_INTEGRATION=1``. Per
ADR-0018, the fixture is *committed JSON* (not pickled), generated
offline by ``experiments/fixtures/gen_gsm8k_calibration.py`` against
the OpenRouter SLM slate (gemma-3-27b-it:free,
llama-3.1-8b-instruct:free, qwen-2.5-7b-instruct:free) per the user's
resolution to ``specs/w3-calibration.md`` Q3.

The ECE-drop assertion mirrors the synthetic acceptance test in
``tests/calibrate/test_isotonic.py``; the calibrator class is the same.
The two-tier strategy (synthetic in unit tests, real-LLM here) is the
justification documented in ADR-0018.

Until the fixture is generated, this test SKIPs gracefully — it is a
scaffold for future runs, not a blocker for the PR.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

import pytest

from council.calibrate import IsotonicCalibrator, expected_calibration_error

pytestmark = pytest.mark.integration

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "calibrate"
    / "fixtures"
    / "gsm8k_subset.json"
)


def _require_run_integration() -> None:
    if os.environ.get("RUN_INTEGRATION") != "1":
        pytest.skip("set RUN_INTEGRATION=1 to enable real-model integration tests")


def _require_fixture() -> dict[str, object]:
    if not FIXTURE_PATH.exists():
        pytest.skip(
            f"fixture not generated yet — run "
            f"`uv run python experiments/fixtures/gen_gsm8k_calibration.py` "
            f"with OPENROUTER_API_KEY to materialise {FIXTURE_PATH}."
        )
    with FIXTURE_PATH.open("r") as f:
        data: dict[str, object] = json.load(f)
    return data


def _train_test_split(
    samples: list[dict[str, object]], *, seed: int = 0
) -> tuple[list[tuple[float, int]], list[float], list[int]]:
    rng = random.Random(seed)
    shuffled = list(samples)
    rng.shuffle(shuffled)
    midpoint = len(shuffled) // 2
    train_pairs: list[tuple[float, int]] = [
        (float(s["raw_confidence"]), int(s["gold_correct"])) for s in shuffled[:midpoint]
    ]
    test_raw: list[float] = [float(s["raw_confidence"]) for s in shuffled[midpoint:]]
    test_correct: list[int] = [int(s["gold_correct"]) for s in shuffled[midpoint:]]
    return train_pairs, test_raw, test_correct


def test_isotonic_drops_ece_below_005_on_real_gsm8k_subset() -> None:
    _require_run_integration()
    data = _require_fixture()
    samples = data["samples"]
    assert isinstance(samples, list)
    assert len(samples) >= 32, "fixture must contain at least 32 samples"

    train_pairs, test_raw, test_correct = _train_test_split(
        samples,  # type: ignore[arg-type]
        seed=0,
    )

    ece_before = expected_calibration_error(test_raw, test_correct, n_bins=10)

    cal = IsotonicCalibrator(train_pairs)
    test_predicted = [cal.calibrate(r, "agent", "free") for r in test_raw]  # type: ignore[arg-type]
    ece_after = expected_calibration_error(test_predicted, test_correct, n_bins=10)

    # Acceptance: master plan §7 W3 line 769.
    assert ece_after < 0.05, f"ECE after calibration is {ece_after}, expected < 0.05"
    # Sanity: the raw fixture should be miscalibrated enough to make the
    # drop meaningful. If this fails, the SLM-slate predictions were
    # already well-calibrated — no harm, just adjust the assertion.
    assert ece_before > ece_after
