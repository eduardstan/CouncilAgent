# ADR-0003: Extend `Trace.to_events()` with Derived Boolean APs for LTL_f

## Status

Accepted — extends [ADR-0002](0002-to-events-schema-freeze.md) (the W0
freeze of the same schema). The W0 freeze applied during W0 development;
W1 needs additional derived APs for faithful LTL_f property encoding.

## Date

2026-04-29

## Context

`Trace.to_events()` (in `council/dialect/trace.py`) is the bridge between the L0
speech-act algebra and the L1 LTL_f monitor layer. Each `Move` in the trace is
serialised to an atomic-proposition dict; LTL_f monitors step over these dicts
without ever touching the `Trace` object directly (enforcing the L0/L1 boundary).

At the end of W0, the schema was documented as "frozen after W0/PR3" and contained
12 keys: `force`, `agent_id`, `round_index`, and one `is_<force>` boolean flag per
`Force` enum value (9 flags).

W1 requires a named-property library of ≥ 10 LTL_f properties (as specified in
`COUNCILAGENT_NS_MASTER_PLAN.md §7 W1`). Several properties in the bible spec cannot
be faithfully encoded with the 12-key schema alone:

| Property | Required AP not in W0 schema |
|---|---|
| `NoSycophancyCascade` | whether current + 2 prior same-agent moves are all Concede |
| `NoPrematureConsensus` | whether any Challenge precedes the current Vote in the trace |
| `ProvenanceCompleteness` | whether the move carries evidence (Vote/Propose with non-empty evidence) |

Two options were evaluated:

**Option A — Extend `to_events()` with derived booleans computed from trace context.**
The three new keys are computed in a single forward pass over `self.moves` with
per-agent running state (O(n), same asymptotic complexity as before). All computation
stays inside `trace.py` — the single L0 boundary file for this concern.

**Option B — Approximate the properties using only the existing 12-key schema.**
`NoSycophancyCascade` would become "3 consecutive Concedes by any agent" (losing
same-agent specificity); `NoPrematureConsensus` could not be expressed without
knowing trace history; `ProvenanceCompleteness` could not be expressed at all.

## Decision

**Option A.** Extend `Trace.to_events()` with three derived boolean APs:

| Key | Type | Semantics |
|---|---|---|
| `has_evidence` | `bool` | `True` for `Propose`/`Vote` moves where `claim`/`option.evidence != ()` |
| `has_prior_challenge` | `bool` | `True` if any `Challenge` appears at a strictly earlier index in the trace |
| `same_agent_concede_run_ge_3` | `bool` | `True` if this move is `Concede` and the two immediately preceding moves from the same `agent_id` are also `Concede` |

The "frozen after W0/PR3" docstring comment is updated to "extended in W1/PR1 — adds
`has_evidence`, `has_prior_challenge`, `same_agent_concede_run_ge_3`". The original
comment meant *frozen during W0 development* to prevent W0 PRs from racing on the
schema; it was never intended as a permanent contract. The schema evolves as higher
layers are built, provided all changes live in `trace.py`.

## Alternatives Considered

### Option B — Schema approximation

Properties would be silent approximations of the bible's formal spec. This creates
long-term maintenance debt: the property name suggests precision that the
implementation does not deliver. When properties are cited in P1 (AAMAS 2027),
reviewers will check the LTL_f formulae against the claimed semantics; an
approximation is a citation liability.

**Rejected:** silent divergence between spec and implementation is unacceptable at
publication quality.

### L1 monitors inspect `Trace` directly (bypass `to_events()`)

L1 monitors could call `Trace.by_force()`, `Trace.at_round()`, or walk `Trace.moves`
directly instead of only stepping over event dicts. This would allow arbitrary
trace-context queries at the monitor level.

**Rejected:** it violates the L0/L1 layer boundary (`architecture.md` §L1: "step
monitors over `Trace.to_events()`"). The boundary exists precisely so that the
monitor is a pure dict-consumer — stateless and composable. Allowing monitors to
reach into `Trace` objects makes them non-compositional and untestable in isolation.

### Add per-property helper functions in `council/symbolic/verify/properties.py`

Helper functions in L1 could compute derived values themselves before stepping the
monitor, re-implementing trace-context logic at the property level.

**Rejected:** logic duplication across properties (each needing its own
same-agent-concede-run computation). One place (`trace.py`) beats N places
(`properties.py`, one per property).

## Consequences

**Positive:**
- Named properties are faithful to the bible's formal specifications — no
  approximation debt.
- All derived-AP computation is in a single place (`trace.py`, L0 boundary). Adding
  future APs for W2+ properties follows the same pattern with no changes to monitors
  or properties.
- L1 monitors remain pure dict-consumers — easy to test in isolation with
  hand-crafted event sequences.

**Neutral:**
- `to_events()` now runs a single forward pass with per-agent state (a
  `dict[str, int]` for concede-run counts, one `bool` for `seen_challenge`). Same
  O(n) complexity; constant-factor overhead is negligible.

**Negative:**
- Schema has 15 keys (was 12). Any downstream code that iterates over all event
  keys (e.g., the ISPL emitter in PR6) must be aware of the three new boolean keys.
  This is documented in the `to_events()` docstring.

## References

- `council/dialect/trace.py` — implementation (W1 PR1)
- `council/symbolic/verify/properties.py` — consumer (W1 PR5)
- `COUNCILAGENT_NS_MASTER_PLAN.md §7 W1` — named-property acceptance criteria
- `specs/w1-verification-spine.md` — full W1 spec (Patch A section)
- `.claude/rules/architecture.md §L1` — layer boundary rule (monitors step over `to_events()`)
