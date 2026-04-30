# ADR-0011: QE and Ebs design choices on the W2 QBAF

## Status

Accepted.

## Date

2026-04-30

## Context

W2/PR4 ships two more gradual semantics:

- **Quadratic Energy (QE)** — Potyka 2018, "Continuous dynamical systems for
  weighted bipolar argumentation" (KR).
- **Ebs (Euler-based / Exponent-based restricted semantics)** —
  Amgoud-Ben-Naim 2018, "Evaluation of arguments in weighted bipolar graphs"
  (IJAR), Definition 19. The bible refers to this as "Euler-based"; the
  paper itself calls it "Exponent-based" because of the `2^E` term. The
  W2 class name keeps the bible's `EulerBasedSemantics` for traceability,
  with the docstring explaining the equivalence.

Both papers define their semantics on *acyclic* weighted bipolar
argumentation graphs (Potyka 2018 §5 Proposition 16; Amgoud-Ben-Naim 2018
Definition 16-17 explicitly restrict to acyclic non-maximal graphs).

The W2 generalisation is identical in shape to ADR-0010's DF-QuAD
generalisation: weighted edges multiply source strength; withdrawn arguments
contribute 0 and have strength 0; preferred extension threshold 0.5.

Two new questions arise that are **not** covered by ADR-0010:

1. **Cycle policy for QE.** Potyka 2018 defines QE as the *equilibrium* of
   a system of ODEs. The differential equations are well-defined for
   cyclic graphs too (the dynamics still flow), but a closed-form
   equilibrium is only guaranteed for acyclic BAGs (Proposition 16). For
   general BAGs, one must integrate numerically (Euler / RK4).
2. **Boundary degeneracy in Ebs.** When `w(a) = 0` or `w(a) = 1`, Ebs's
   formula `f(a) = 1 - (1 - w(a)²) / (1 + w(a)·2^E)` is fixed at 0 or 1
   regardless of the energy `E`. The paper's "non-maximal" restriction
   (Def 16) excludes `w(a) = 1`; the boundary `w(a) = 0` is implicitly
   excluded because it sets `f(a) = 0` always.

## Decision

**Q1 — Cycle policy for QE.** PR4's QE implementation requires acyclic
QBAFs and raises `ValueError` on cycle, identical to DF-QuAD (ADR-0010 Q3).

The closed-form acyclic case is computed via topological-order pass:

```
s_j* = w(j) + (1 - w(j)) * h(E_j) - w(j) * h(-E_j)
```

where `h(x) = max(x, 0)^2 / (1 + max(x, 0)^2)` and `E_j` is the
weighted-energy sum.

**Numerical integration for cyclic QE is deferred.** When a future
workstream needs cyclic QE (likely in W5 QD descriptors for behavioural
cycles, or W6 ILP rule discovery on cyclic argument structures), the
implementation will add a `numeric=True` parameter that triggers a
fixed-point iteration with configurable tolerance and max-iterations.
The PR4 `QESemantics` class is forward-compatible with that extension.

**Q2 — Cycle policy for Ebs.** Same — `ValueError` on cycle. The paper
mathematically requires acyclicity; there is no fixed-point analogue for
Ebs.

**Q3 — Boundary degeneracy in Ebs.** PR4's Ebs implementation **does NOT
reject** `w(a) = 0` or `w(a) = 1`. It computes the formula directly:

- `w(a) = 0` → `f(a) = 1 - 1/(1 + 0) = 0` (frozen at 0)
- `w(a) = 1` → `f(a) = 1 - 0/(1 + 2^E) = 1` (frozen at 1)

This matches the paper's formula (Definition 19) verbatim. The frozen
behaviour is mathematically correct given the formula — it is not a
defect, it is a consequence. The "Restricted semantics" terminology in
Definition 17 is a *paper-level* restriction (the principles in
Proposition 8 hold only on `w(a) < 1`), not a runtime restriction. A
caller who feeds w=0 or w=1 to Ebs will get a defensible (if degenerate)
answer.

**Documented implication.** When a user picks Ebs and a Propose has
`confidence = 1.0`, the resulting argument's strength will be 1.0
regardless of any attackers. This is rarely what a council would want;
the appropriate Aggregator (PR6) defaults to DF-QuAD (which has no
boundary degeneracy) for that reason.

**Q4 — All other design choices match ADR-0010 verbatim.** Edge weights
multiply source strength; withdrawn arguments have strength 0 and
contribute 0; preferred extension threshold is 0.5. These are
*semantics-class invariants* shared across all three implementations
(DF-QuAD, QE, Ebs) so that downstream PRs (the aggregator, the
visualisers) can swap semantics without further protocol negotiation.

## Alternatives Considered

### Q1 alt — Implement cyclic QE via fixed-point iteration in PR4

Add iteration logic to `QESemantics.evaluate` so cycles converge to a
fixed point.

**Rejected for PR4.** The numerical-integration code path adds: a
tolerance parameter, a max-iteration parameter, convergence diagnostics,
and a "no convergence" failure mode. Each adds review surface that is
not justified by W2's headline path (deliberation traces produce acyclic
QBAFs by construction — Challenges and Concedes target prior moves).

PR4 ships the acyclic case correctly and signals the limitation
loudly via `ValueError`. A future PR (likely W5/PR3 if QD descriptors
need cyclic QE) adds the numerical path additively.

### Q3 alt — Reject `w(a) ∈ {0, 1}` for Ebs (strict paper-restricted semantics)

Raise on the boundary cases at the call site.

**Rejected.** The bible §6.3 names `w(a)` "the calibrated confidence" —
which can legitimately be exactly 0 (zero confidence) or exactly 1
(complete confidence) for some callers. Forcing `0 < w(a) < 1` would mean
silently nudging confidences (e.g., clamping to `[ε, 1-ε]`), which
violates the calibrator's contract (ADR-0008: identity calibrator returns
the input unchanged). Better to compute the paper formula faithfully and
let the user decide if Ebs is the right semantics for their use case.

The aggregator (PR6) will default to DF-QuAD, which does not exhibit
boundary degeneracy — the user opts into Ebs explicitly.

### Q3 alt — Numerically perturb boundary cases inside `EulerBasedSemantics`

Replace `w(a) = 0` with `w(a) = 1e-6` and `w(a) = 1` with `1 - 1e-6`
internally.

**Rejected.** Silent perturbation is the worst kind of fix — it
introduces non-reproducibility (results depend on the perturbation
constant), and it lies about the input. The faithful-to-paper behaviour
is more honest.

## Consequences

**Positive:**

- W2 ships three principal gradual semantics (DF-QuAD default + QE + Ebs)
  with parallel APIs. Users can pick at the semantics level without any
  protocol differences.
- Each semantics is faithful to its source paper. Reviewers checking
  Section 5 of Potyka 2018 against `qe.py`, or Definition 19 of
  Amgoud-Ben-Naim 2018 against `euler.py`, will see verbatim formulae.
- The cycle policy is uniform across all three semantics → predictable
  failure modes for downstream callers.

**Neutral:**

- QE and Ebs are useful for P2 (AAAI 2027) reviewer comparisons against
  DF-QuAD, but DF-QuAD remains the W2 default and the aggregator's only
  hardcoded choice (PR6).
- The cyclic-QE numerical path is open work; the `QESemantics` class
  signature reserves room for `numeric=True` without breaking changes.

**Negative:**

- Ebs's boundary degeneracy at `w(a) ∈ {0, 1}` is a sharp edge. The
  docstring documents it; the aggregator default avoids it; reviewers
  will notice. We chose faithfulness over magic.

## References

- `council/symbolic/argue/semantics/quad.py` — implementation (W2/PR4)
- `council/symbolic/argue/semantics/euler.py` — implementation (W2/PR4)
- `papers/3 --- argumentation/Potyka 2018 ... (KR).pdf` — Definition 2
  (QE energy + impact), Equation 3 (equilibrium), Proposition 16
  (acyclic convergence)
- `papers/3 --- argumentation/Amgoud and Ben-Naim 2018 ... (IJAR).pdf` —
  Definition 19 (Ebs), Proposition 8 (principles)
- `docs/adr/0010-df-quad-design-choices.md` — sister ADR; Q1, Q2, Q4 are
  unchanged here
