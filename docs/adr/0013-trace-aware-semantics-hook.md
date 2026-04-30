# ADR-0013: Trace-aware semantics via the `prepare(trace)` hook

## Status

Accepted.

## Date

2026-04-30

## Context

W2/PR5 introduced `StrategicCoupledSemantics` (ADR-0012), which takes
`evidence_backed: frozenset[str]` at construction time. The set is
computed from a `Trace` via `evidence_backed_arg_ids(trace)` (the inline
ATL fragment).

This works fine when the caller has the trace in hand at construction
time. But the `ArgumentationAggregator` (W2/PR6) takes a `GradualSemantics`
*instance* at construction and runs aggregation per-trace. With
`StrategicCoupledSemantics`, the aggregator must somehow rebuild the
semantics with each trace's `evidence_backed`. Three options were
evaluated.

**Option A — `isinstance` check inside aggregator.** The aggregator
checks `isinstance(self._sem, StrategicCoupledSemantics)`; if so,
constructs a new instance with current `evidence_backed`. Otherwise
uses the semantics as-is.

**Option B — Per-call factory parameter.** `ArgumentationAggregator`
takes `semantics_factory: Callable[[Trace], GradualSemantics]` instead
of a `GradualSemantics` instance.

**Option C — `prepare(trace)` hook on `GradualSemantics` ABC.** The
ABC gains a default `prepare(trace) -> GradualSemantics` method that
returns `self`. Trace-aware semantics override to return a new instance
with updated trace-derived state. The aggregator always calls
`sem.prepare(trace)` before `sem.evaluate(baf)`.

## Decision

**Option C — `prepare(trace)` hook on `GradualSemantics`.** The ABC's
new default-provided method is:

```python
def prepare(self, trace: Trace) -> "GradualSemantics":
    """Trace-aware refresh hook. Default: no-op (returns self).

    Trace-aware semantics override this to return a new instance with
    updated trace-derived state. The aggregator calls `sem.prepare(trace)`
    before `sem.evaluate(baf)` so the returned instance evaluates against
    the same Trace that produced the BAF.
    """
    return self
```

`StrategicCoupledSemantics` overrides:

```python
def prepare(self, trace: Trace) -> GradualSemantics:
    return StrategicCoupledSemantics(
        base=self._base,
        evidence_backed=evidence_backed_arg_ids(trace),
        alpha=self._alpha,
        consensus_threshold=self._threshold,
    )
```

`DFQuADSemantics`, `QESemantics`, `EulerBasedSemantics` inherit the
default no-op (they are stateless functional semantics; trace-aware
behavior is moot).

The aggregator uses `sem = self._sem.prepare(trace); strengths =
sem.evaluate(baf); ext = sem.preferred_extension(baf)`. No `isinstance`
check, no per-instance type sniffing.

## Alternatives Considered

### Option A — `isinstance` dispatch inside aggregator

Rejected. Adds a brittle runtime type check inside `argue/aggregator.py`
that knows about `argue/semantics/coupled.py`. Future trace-aware
semantics (W3 calibrators with per-trace privileged knowledge; W6 ILP
rules learned per-trace) would each need their own isinstance branch in
the aggregator — every new trace-aware semantics adds aggregator-side
churn. The `prepare()` hook is the polymorphism done right.

### Option B — Factory parameter

Rejected. Forces callers (CouncilPolicy in PR6, future Genome-based
constructors in W5) to wrap every semantics instance in a `lambda
trace: SomeSemantics(...)`. Stateless semantics (DF-QuAD, QE, Ebs)
become `lambda _: DFQuADSemantics()` — verbose and awkward. The hook
makes the trace-aware case the special case, not the common case.

### Option C-prime — Make the hook abstract (force every subclass to override)

Rejected. Stateless semantics have nothing to do; a forced override is
boilerplate. The default `return self` makes stateless semantics zero-
effort and trace-aware semantics one-method-override.

## Consequences

**Positive:**

- The `GradualSemantics` ABC stays small (3 methods: `evaluate`,
  `preferred_extension`, `prepare`). The aggregator's contract is
  clean: always call `prepare(trace)` before `evaluate(baf)`.
- Future trace-aware semantics — W3's MUSE / privileged-knowledge
  calibrators, W6's ILP-mined rule semantics — get the hook for free.
- Existing PR1-PR4 concrete classes need *no* changes; they inherit
  the default no-op.
- The aggregator works with any `GradualSemantics` without isinstance
  checks.

**Neutral:**

- The `prepare(trace)` hook adds a `Trace` import to
  `council/symbolic/argue/semantics/base.py`. This is an L0 → L2 dep
  that's already pervasive throughout `argue/` (build_qbaf, the ATL
  fragment, etc.); no new layer-rule violation.
- `StrategicCoupledSemantics.prepare` constructs a new instance per
  call. Since the construction is O(|trace|) — one pass to compute
  `evidence_backed_arg_ids` — this is negligible vs. the aggregator
  pipeline cost.

**Negative:**

- Subclasses that *do* override `prepare` are responsible for returning
  a *fresh* instance, not mutating self. Documented in the ABC
  docstring; tests pin the immutability convention.

## References

- `council/symbolic/argue/semantics/base.py` — ABC with `prepare`
  default (W2/PR6 Slice A)
- `council/symbolic/argue/semantics/coupled.py` — override (W2/PR6
  Slice A)
- `council/symbolic/argue/aggregator.py` — consumer of the hook
  (W2/PR6 Slice B)
- `docs/adr/0012-strategic-coupled-design.md` — sister ADR; this
  resolves Q2 alt with the cleaner hook design
