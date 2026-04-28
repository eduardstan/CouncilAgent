---
name: new-semantics
description: Scaffolds a new gradual-semantics subclass in council/symbolic/argue/semantics/<slug>.py plus tests. Use when the user says "add a new semantics" or "/new-semantics <Name>". Tests determinism, monotonicity in base scores, and Walton-Krabbe canonical agreement.
---

# new-semantics

Scaffold a `GradualSemantics` (W2 / L2) for the BAF/QBAF aggregator.

## Inputs
- `<Name>` — PascalCase, ending in `Semantics`. Examples: `DFQuADSemantics`, `QuadraticEnergySemantics`, `EulerSemantics`, `CoupledSemantics`.

## Procedure

1. **Prerequisite check.** `council/symbolic/argue/{baf,builders}.py` must exist; the `GradualSemantics` ABC must be defined. If not, stop.
2. Read `council/symbolic/argue/semantics/df_quad.py` as the reference.
3. **Append the subclass** to `council/symbolic/argue/semantics/<slug>.py`:
   ```python
   from council.symbolic.argue.baf import QBAF
   from council.symbolic.argue.semantics.base import GradualSemantics

   class <Name>(GradualSemantics):
       """<one-line description>."""
       def evaluate(self, baf: QBAF) -> dict[str, float]:
           raise NotImplementedError
   ```
4. **Create test file** `tests/symbolic/argue/semantics/test_<slug>.py` with:
   - **Determinism.** Same QBAF, called 10 times, returns identical strengths.
   - **Monotonicity in base scores.** Increase one argument's base score by ε; that argument's strength must (weakly) increase.
   - **Range.** All output strengths are in [0, 1].
   - **Walton-Krabbe canonical agreement.** On the canonical fixture, the strength ordering matches the reference (with documented allowed deviation if not equivalent under your semantics).
5. Branch `feature/ns-w2-semantics-<slug>`.

## Invariants enforced
- Determinism (no PRNG without a seed; no time-dependent behaviour).
- Monotonicity in base scores.
- No model calls, no I/O.
- Output range bounded.

## Reject criteria
- Non-deterministic implementation.
- Monotonicity violated for any test case.
- Imports from `council/dialect/`, `council/calibrate/`, or `council/symbolic/verify/` (peer-layer cross-imports forbidden).
