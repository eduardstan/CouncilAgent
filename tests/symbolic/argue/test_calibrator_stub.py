"""Tests for council/calibrate/base.py — Calibrator ABC + IdentityCalibrator.

ADR-0008 places the Calibrator ABC in `council/calibrate/base.py`. W2 (this
PR) ships the ABC + IdentityCalibrator only; W3 fills concrete subclasses
(JSD, MUSE, Privileged, Isotonic).

These tests pin the ABC contract and the IdentityCalibrator behaviour. They
live under `tests/symbolic/argue/` because the ABC is consumed by W2's
builder, not because the implementation lives there.
"""

from __future__ import annotations

import inspect
import random

import pytest

from council.calibrate import Calibrator, IdentityCalibrator
from council.dialect.moves import ClaimDomain


class _MissingCalibrate(Calibrator):
    """Subclass missing `calibrate` — should fail to instantiate."""


class TestCalibratorABC:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            Calibrator()  # type: ignore[abstract]

    def test_subclass_missing_calibrate_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            _MissingCalibrate()  # type: ignore[abstract]

    def test_calibrate_is_sync(self) -> None:
        # Architecture rules freeze the signature as sync.
        assert not inspect.iscoroutinefunction(Calibrator.calibrate)

    def test_calibrate_signature_matches_architecture_rules(self) -> None:
        sig = inspect.signature(Calibrator.calibrate)
        params = list(sig.parameters.keys())
        # Order: self, raw_confidence, agent_id, claim_domain
        assert params == ["self", "raw_confidence", "agent_id", "claim_domain"]


class TestIdentityCalibrator:
    def test_returns_input_unchanged_on_one_value(self) -> None:
        calib = IdentityCalibrator()
        assert calib.calibrate(0.7, agent_id="a", claim_domain=ClaimDomain.ARITH) == 0.7

    def test_returns_input_unchanged_at_boundaries(self) -> None:
        calib = IdentityCalibrator()
        assert calib.calibrate(0.0, agent_id="a", claim_domain=ClaimDomain.FREE) == 0.0
        assert calib.calibrate(1.0, agent_id="b", claim_domain=ClaimDomain.FOL) == 1.0

    def test_independent_of_agent_and_domain(self) -> None:
        calib = IdentityCalibrator()
        for domain in ClaimDomain:
            for agent in ("a", "b", "synthetic-agent"):
                assert calib.calibrate(0.42, agent_id=agent, claim_domain=domain) == 0.42

    def test_property_random_inputs_returned_unchanged(self) -> None:
        rng = random.Random(0)
        calib = IdentityCalibrator()
        for _ in range(100):
            v = rng.random()
            assert calib.calibrate(v, agent_id="x", claim_domain=ClaimDomain.CODE) == v

    def test_is_concrete_subclass_of_calibrator(self) -> None:
        assert issubclass(IdentityCalibrator, Calibrator)
        # Constructor takes no args
        IdentityCalibrator()


class TestCalibratorPublicApi:
    def test_imports_via_calibrate_package(self) -> None:
        from council.calibrate import Calibrator as C
        from council.calibrate import IdentityCalibrator as I

        assert C is Calibrator
        assert I is IdentityCalibrator
