# ADR-002: Freeze the Trace.to_events() atomic-proposition schema after W0/PR3

## Status
Accepted — schema FROZEN as of commit 3317072 (feat(w0/pr3))

## Date
2026-04-29

## Context

`Trace.to_events()` converts each `Move` in a `Trace` to a plain Python `dict` of
atomic propositions. W1 (verification spine) compiles LTL_f formulas using SPOT /
`ltl2mon` into DFA monitors, then steps each monitor over the sequence of dicts
emitted by `to_events()`. The variable names in the LTL_f formula (e.g.
`is_propose`, `is_challenge`, `is_vote`) must match the dict keys exactly — there is
no schema-discovery layer.

Any change to the dict keys after W1 properties are written breaks the monitor
compilation silently (SPOT compiles against new keys; old formula references become
vacuously false atomic propositions).

## Decision

The `to_events()` dict schema is **frozen** after PR3 (commit 3317072). The schema is:

```python
{
    "force":        str,   # Move.force.value
    "agent_id":     str,   # Move.agent_id
    "round_index":  int,   # Move.round_index
    # One boolean flag per Force value:
    "is_propose":   bool,
    "is_challenge": bool,
    "is_concede":   bool,
    "is_retract":   bool,
    "is_question":  bool,
    "is_clarify":   bool,
    "is_vote":      bool,
    "is_abstain":   bool,
    "is_pass":      bool,
}
```

**Modification requires an explicit migration step:**
1. Add new keys *alongside* old keys (backwards-compatible extension).
2. Update all W1 LTL_f property formulas to use the new keys.
3. Re-run the full W1 test suite to confirm no vacuous-truth regressions.
4. Remove old keys only after all formulas are migrated.
5. Write a new ADR (ADR-00N) documenting the migration.

## Alternatives Considered

### Dynamic schema discovery at monitor compilation time
- Have SPOT discover available atomic propositions from a sample trace at compile time.
- **Rejected:** SPOT's Python bindings don't support runtime AP discovery; formulas must
  be strings with explicit AP names. Dynamic discovery would require a custom
  LTL_f formula rewriter — significant complexity for no W0 benefit.

### Per-move-type event schema (polymorphic dicts)
- Emit different keys for `Propose` vs `Challenge` vs `Vote`.
- **Rejected:** LTL_f monitors are typically prefix-closed and step over a *uniform*
  event alphabet. Having `is_propose_claim` present only for Propose events and absent
  for Challenge events would require monitors to handle "missing AP = false" — this is
  the default in many LTL tools, but the boolean-flag design makes it explicit and
  avoids the ambiguity.

### Frozen boolean flags (chosen)
- Every event has *all* boolean flags; exactly one is `True` per event.
- Monitors write `is_propose & !is_vote` without needing to worry about absent keys.
- **Tradeoff:** Adding a new `Force` value requires adding a new flag and checking all
  existing LTL_f formulas. This is the right tradeoff: Force is designed to be stable
  (Walton-Krabbe deliberation typology has not added a new speech-act type since 1995).

## Consequences

- W1 LTL_f property formulas MUST reference only the keys listed above.
- Any new `Force` value added to `moves.py` requires: (1) updating `to_events()`,
  (2) updating all W1 LTL_f formulas, (3) a new ADR documenting the change.
- The boolean-flag schema makes each `to_events()` dict independently interpretable
  without needing to look up the Force enum (useful for MCMAS ISPL encoding in W1).
- Test `test_to_events_three_agent_two_round_sequence` in `tests/dialect/test_trace.py`
  serves as the canonical positive trace fixture for W1 monitor tests.
