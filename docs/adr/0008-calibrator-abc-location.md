# ADR-0008: `Calibrator` ABC lives in `council/calibrate/base.py`, consumed by W2

## Status

Accepted.

## Date

2026-04-30

## Context

The L2 argumentation builder (`council/symbolic/argue/builders.build_qbaf`,
W2/PR2) accepts an optional `calibrator: Calibrator | None = None` argument
to compute argument base scores from `Propose.confidence`. The bible
specifies this in §6.3 (lines 627-643):

```python
def build_qbaf(trace: Trace, calibrator: Calibrator | None = None) -> QBAF:
    """
      - Every Propose → an argument node.
        Base score = calibrator(propose.confidence, propose.agent_id, claim.domain)
                     when calibrator is given; else propose.confidence.
    """
```

The `Calibrator` ABC is required by the W2 builder, but **W3 (Calibrated
disagreement, L3) has not started**. Without the ABC, `build_qbaf`'s
type hint would have to use `object | None` or a forward-string, which
both lose mypy --strict enforcement and would pollute downstream PRs.

The architecture rules (`.claude/rules/architecture.md` §"Required
contracts" → "L3 — calibration") prescribe the ABC signature exactly:

```python
class Calibrator(ABC):
    @abstractmethod
    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float: ...
```

The question is: **who owns this ABC, and where does it live in the
filesystem, given W2 needs it before W3 starts?**

Three options were evaluated.

## Decision

**Introduce `Calibrator` ABC in `council/calibrate/base.py` as part of W2/PR1.
W3 fills concrete subclasses (JSD, MUSE, Privileged-Knowledge, Isotonic) in
`council/calibrate/{jsd,muse,privileged,isotonic}.py` without changing the
ABC.**

The W2 builder imports the ABC via `from council.calibrate.base import
Calibrator`. The architecture rules' "Approved exceptions" list already
permits `argue/aggregator.py → calibrate/jsd.py` (#1), so an `argue/ →
calibrate/` import direction is sanctioned in spirit. We extend it to
`argue/builders.py → calibrate/base.py` for the W2 PR2 ship.

A concrete `IdentityCalibrator(Calibrator)` is shipped alongside the ABC.
It returns `raw_confidence` unchanged regardless of `agent_id` /
`claim_domain`. This serves two purposes:

1. **Smoke-test the ABC** without depending on numpy / scipy (which W3 needs).
2. **Provide a non-None default** for any caller that wants a calibrator
   object rather than `None` — e.g., `build_qbaf(trace, calibrator=
   IdentityCalibrator())` is byte-equivalent to `build_qbaf(trace)`, and
   makes call sites that wrap the calibrator easier to test.

## Alternatives Considered

### Option A — Put the ABC inside `council/symbolic/argue/`

Define `Calibrator` in `council/symbolic/argue/calibrator.py`. W3 would
then import the ABC from L2 and provide concretes in
`council/calibrate/`.

**Rejected.** The architecture rules row "L3 calibrate" says calibration
**is L3** — moving the ABC into L2 would mis-locate the layer's contract.
Future readers would look for `Calibrator` in `calibrate/`, not `argue/`.
And W7 / W8 / paper P2 will reference "the L3 Calibrator ABC at
`council/calibrate/`" — moving it now creates a citation liability.

### Option B — Defer the ABC; W2 ships with `calibrator: object | None`

Type-hint the parameter as `object | None`. When W3 lands, refactor every
W2 callsite to use the proper type.

**Rejected.** mypy --strict cannot enforce the calibrator interface on an
`object`; we'd lose the type-level fix that the architecture rules
promise. The refactor is a "remove once X" TODO that bit-rots, and the
intermediate W2 PRs would all need to use `cast()` to access calibrator
methods — exactly the `Any`/`cast` pattern the operating rules forbid
(see CLAUDE.md "When uncertain about a layering call... resist `Any`
and `cast`").

### Option C — Inline a Protocol class in the W2 builder

Define a structural `typing.Protocol` named `_CalibratorProto` inside
`builders.py`, then have W3's concrete classes happen to conform.

**Rejected.** Project convention (W0/W1 architecture rules) uses `abc.ABC +
@abstractmethod` for layer contracts, never `typing.Protocol`. Mixing the
two confuses agents reading the codebase and creates an inconsistent
contract that mypy enforces only structurally (not nominally) — a weaker
guarantee than the rest of the layer interfaces.

### Option D (chosen) — ABC stub in `council/calibrate/base.py` now; W3 fills concretes

The ABC's location matches the architecture rules. W2 imports cleanly. W3
extends without touching W2. The `IdentityCalibrator` concrete prevents
the ABC from being an empty stub that breaks `from council.calibrate
import Calibrator`-style smoke-imports.

## Consequences

**Positive:**

- W2 ships with full mypy --strict coverage on the calibrator parameter.
  No `Any`, no `cast`, no `# type: ignore`.
- W3 inherits a concrete starting point — `IdentityCalibrator` is the
  trivial baseline that `JSDCalibrator`, `MUSECalibrator`, etc. must
  measure against.
- The architecture rules' approved-exceptions list (`argue/aggregator.py →
  calibrate/jsd.py`) is naturally consistent with the new
  `argue/builders.py → calibrate/base.py` direction. We document the
  extension in §"References" below; no new exception line is needed
  because the import is into the L3 *base*, not into a concrete L3
  semantics module.
- Constitution §1 honoured: this is the council-as-agent path, not a
  benchmarking expedient.

**Neutral:**

- W3 must respect the frozen `Calibrator.calibrate` signature. The
  architecture rules already pin it; no new constraint.
- `council/calibrate/__init__.py` re-exports both `Calibrator` and
  `IdentityCalibrator`. Future W3 PRs add `JSDCalibrator`, etc. to the
  re-export list. No backward-compat hazard.

**Negative:**

- The `Calibrator` ABC briefly exists with only one concrete
  (`IdentityCalibrator`). Until W3 ships JSD, the calibrator parameter
  is "available but unused" on the headline path. This is not a defect
  — it is the price of letting W2 and W3 ship independently.

## References

- `council/calibrate/base.py` — implementation (W2/PR1)
- `council/calibrate/__init__.py` — re-export (W2/PR1)
- `council/symbolic/argue/builders.py` — consumer (W2/PR2)
- `COUNCIL_NS_PLAN.md §6.3` — bible specification of `build_qbaf(trace,
  calibrator)`
- `COUNCILAGENT_NS_MASTER_PLAN.md §7 W3` — concrete calibrator deliverables
  (JSD, MUSE, Privileged-Knowledge, Isotonic)
- `.claude/rules/architecture.md §"Required contracts"` — L3 Calibrator
  ABC signature freeze
- `.claude/rules/architecture.md §"Approved exceptions" #1` —
  `argue/aggregator.py → calibrate/jsd.py`; this ADR extends the spirit
  to `argue/builders.py → calibrate/base.py`
- `specs/w2-argumentation.md §"Risk register"` Risk 5 — the originating
  question this ADR resolves
