# ADR-0009: Challenge and Concede produce Argument nodes (not just edges)

## Status

Accepted.

## Date

2026-04-30

## Context

`council/symbolic/argue/builders.build_qbaf` (W2/PR2) maps trace moves to
QBAF structure per the bible §6.3:

```
- Every Propose → an argument node.
  Base score = ... ; arg_id = Propose.move_id.
- Every Challenge(target, reason) → attack edge (reason → target),
  with attack weight = LLM-emitted certainty of the challenge.
- Every Concede(target) → support edge (concession_node → target).
- Every Retract(own) → mark own_node as withdrawn, recompute strengths.
- Every Vote(option, conf) → base-score boost on the matching Propose's
  argument (clamped to [0, 1]).
```

The bible is explicit about Propose creating an argument node, and silent
about whether Challenge / Concede do. The phrasing "(reason → target)" and
"(concession_node → target)" implies *some* source node exists for each
edge, but does not specify what it is.

The `QBAF.__post_init__` invariant (W2/PR1) rejects edges whose source or
target does not reference a declared argument. So whatever the design,
attack and support sources must point at *some* argument — they cannot be
free-floating string IDs.

Three options were evaluated.

## Decision

**Each Challenge and each Concede produces both:**

1. **An Argument node:**
   - `arg_id = Challenge.move_id` / `Concede.move_id` (parallel to
     Propose's `arg_id = Propose.move_id`)
   - For Challenge: `claim_surface = reason.surface`,
     `base_score = Challenge.confidence` (Patch C, ADR-0006)
   - For Concede: `claim_surface = "(concession to {target})"`,
     `base_score = 1.0` (a concession is an unconditional endorsement)
2. **A directed edge:**
   - For Challenge: `Attack(source=Challenge.move_id, target=Challenge.target,
     weight=Challenge.confidence)`
   - For Concede: `Support(source=Concede.move_id, target=Concede.target,
     weight=1.0)`

**Targets that do not reference an existing argument cause the move to be
dropped** (no node, no edge). This handles early-round Challenges that
target a non-existent Propose — the QBAF preserves only structurally
valid edges.

**Retract(own) marks the targeted Argument's `withdrawn=True`** if `own`
references an existing argument. No new node, no new edge.

The implementation is a single forward pass over `trace.moves`. Argument
accumulation happens before any later move can attack/support it, which
naturally supports challenge-of-a-challenge chains.

### Reformulation of Constitution §11's "argument count equals Propose count"

Constitution §11 states:
> the QBAF's argument count equals the Propose count

In the chosen design, total `len(baf.arguments)` is `propose_count +
challenge_count + concede_count`, not `propose_count`. The Constitution's
clause is therefore reformulated *operationally* as:

> Every Propose move in the trace has exactly one corresponding Argument
> with `arg_id == Propose.move_id` in `baf.arguments`. (Bijection between
> the Propose moves and the Propose-derived arguments.)

Patch E (W2/PR6) implements this exact check in
`ProvenanceReceipt.is_complete()`. The Constitution itself is not edited
(it is immutable per CLAUDE.md); the operational reading is captured in
this ADR and in the spec.

## Alternatives Considered

### Option A — Edges only; sources are non-Argument string IDs

Allow Attack.source / Support.source to be any string, not just an arg_id.
Relax `QBAF.__post_init__` to skip the dangling-edge check.

**Rejected.** The structural-invariants check is the QBAF's main correctness
guarantee — relaxing it loses one of the only two type-level fixes the
spec promises. Downstream gradual semantics (DF-QuAD, QE, Euler) iterate
over edges and call `strength(source)`; if `source` is a non-Argument
string, `strength()` is undefined. Either every semantics has to add a
"unknown-source" branch (code duplication across PR3-PR5), or we tolerate
runtime KeyErrors. Both are worse than encoding the source as a real
argument.

### Option B — Attack.source = challenger's most-recent prior Propose

Walk back through the trace to find the challenger's last Propose;
`Attack.source = that_propose.move_id`.

**Rejected.** This loses the `Challenge.reason.surface` content from the
graph (the Challenge's *propositional content* is silently dropped, only
its agent's prior position is recorded). Gradual semantics then cannot
distinguish "agent_a challenges Y because counterexample C" from "agent_a
challenges Y because mathematical error E" — both reduce to the same
edge. P2 reviewers will check the BAF reflects the LLM's stated reasoning.

It also fails on the very first round, when challengers have no prior
Propose. We'd have to drop the Challenge silently — losing visible attack
edges that the LLM clearly emitted.

### Option C (chosen) — Challenge/Concede produce nodes + edges

Each Challenge and Concede's `move_id` becomes an Argument's `arg_id`. The
Attack/Support source is that argument. Constitution §11 is reformulated
operationally as a Propose-bijection check.

**Chosen** for these reasons:

- The Challenge.reason and Concede content reaches the graph faithfully.
- Challenge-of-a-challenge chains form naturally without special cases.
- Edge sources always reference real arguments → QBAF invariants hold.
- `QBAF.proposals()` (W2/PR1) already filters arguments to candidate
  *winners* (i.e., Propose-derived non-withdrawn). The aggregator
  (W2/PR6) iterates `baf.proposals()` to pick the answer, so non-Propose
  Arguments do not contaminate the answer-selection path.

## Consequences

**Positive:**

- The QBAF is a faithful structural reflection of the Trace. Reviewers can
  read off agent argumentation from the graph.
- Challenge.reason.surface and Concede metadata reach gradual semantics
  via the standard `strength(source) * weight(edge)` aggregation
  formulae.
- Challenge-of-a-challenge chains "just work" because the source argument
  is accumulated before later moves try to reference it.
- `QBAF.proposals()` is the right query to feed the aggregator — Propose
  is the only force whose arguments are answer candidates.

**Neutral:**

- `len(baf.arguments)` is no longer equal to `propose_count`. The
  Constitution's §11 clause is reformulated *operationally* (Patch E),
  not edited textually. The spec captures this reformulation.
- Concede's synthetic surface (`"(concession to {target})"`) is a UX
  choice. The visualiser (W2/PR7) may render it differently.

**Negative:**

- Challenges/Concedes whose target is not a known argument are dropped
  silently. This is a deliberate trade-off: dangling edges are the
  alternative, and they break QBAF invariants. The drop is logged at
  `DEBUG` level for observability. If a future workstream needs a
  "rejected-moves" view of the Trace, that's a separate `Trace.invalid()`
  query at L0.
- `Concede.base_score = 1.0` is a hard-coded "concessions are
  unconditional" choice. A future calibrator hook for concessions could
  vary this; for W2 it is fixed.

## References

- `council/symbolic/argue/builders.py` — implementation (W2/PR2 Slice C)
- `council/symbolic/argue/baf.py` — QBAF invariants enforced
  (W2/PR1)
- `COUNCIL_NS_PLAN.md §6.3` — bible specification
- `.claude/CLAUDE.md §11` — Constitution clause being reformulated
  operationally
- `specs/w2-argumentation.md §"Patch E"` — receipt-completeness QBAF
  clause; will reference this ADR when authored in PR6
- `docs/adr/0006-challenge-confidence.md` — Challenge.confidence field
  this slice consumes
