---
name: new-calibrator
description: Scaffolds a new Calibrator subclass in council/calibrate/<slug>.py plus tests. Use when the user says "add a new calibrator" or "/new-calibrator <Name>". Enforces NS Constitution §5 (calibrated confidence) — calibrator output must feed a typed Confidence value.
---

# new-calibrator

Scaffold a `Calibrator` (W3 / L3) for the calibrated-disagreement layer.

## Inputs
- `<Name>` — PascalCase, ending in `Calibrator`. Examples: `JSDCalibrator`, `MUSECalibrator`, `PrivilegedKnowledgeCalibrator`, `IsotonicCalibrator`.

## Procedure

1. **Prerequisite check.** `council/calibrate/__init__.py` must exist. If not, stop.
2. Read `council/calibrate/jsd.py` as the reference (when it exists; W3 prereq).
3. **Append the subclass** to `council/calibrate/<slug>.py`:
   ```python
   from council.calibrate.base import Calibrator
   from council.dialect.moves import ClaimDomain

   class <Name>(Calibrator):
       """<one-line description>."""
       def calibrate(self, raw_confidence: float, agent_id: str,
                     claim_domain: ClaimDomain) -> float:
           raise NotImplementedError
   ```
4. **Create test file** `tests/calibrate/test_<slug>.py` with:
   - Closed-form test on a synthetic distribution with known calibration value.
   - Domain-conditional behaviour test (e.g. higher self-weight on factual than on math).
   - ECE measurement on a held-out toy split (must improve over `IdentityCalibrator`).
5. Branch `feature/ns-w3-calibrator-<slug>`.

## Invariants enforced
- No model calls (calibrators read existing distributions or token logprobs).
- Output is a float in [0, 1].
- Domain-conditional behaviour is testable.

## Reject criteria
- Calibrator imports from `council/dialect/`, `council/symbolic/argue/`, or `council/cascade/`.
- Calibrator returns out-of-range values.
