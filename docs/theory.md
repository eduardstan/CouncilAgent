# CouncilAgent-NS — Theory (W1: Verification Spine)

This document collects the theorems that justify the L1 verification spine.
T1 is cited from prior work; T2 is an original adaptation; T3 motivates the
L2 argumentation aggregator (W2).

## T1 — Soundness of LTL3 Monitors

**Statement.** Let `phi` be an LTL_f formula and `M_phi` the LTL3 monitor
constructed from `phi` by either `PurePythonLTL3Monitor` (safety+reachability
fragment) or `ProgressionMonitor` (full fragment). For any finite event sequence
`w = e_1 e_2 ... e_n`:

- If after stepping `M_phi` on `w` the verdict is `TOP`, then every infinite
  extension `w · u` satisfies `phi` (`w · u |= phi`).
- If the verdict is `BOTTOM`, then no infinite extension satisfies `phi`.
- If `UNKNOWN`, both extensions exist.

**Proof sketch.** This is the Bauer-Leucker-Schallhart soundness theorem
(TOSEM 2011, Theorem 1). The progression-based realisation
(`ProgressionMonitor`) preserves this property by construction: each
`progression(phi, e)` step produces a residual `phi'` such that `e · u |= phi`
iff `u |= phi'`; the residual reduces to TRUE (BOTTOM-as-FALSE-residual) only
when the prefix decides the formula's truth value over all extensions. The
safety+reachability monitor is a special case with single-state residuals.

**References.**
- Bauer, Leucker, Schallhart. *Runtime verification for LTL and TLTL*. ACM TOSEM 2011.
- Bauer. *Monitorability of omega-regular languages*. arXiv:1006.3638, 2010.

**Mechanisation.** `tests/symbolic/verify/test_theorems.py::test_t1_soundness_*`

## T2 — Compositionality of Monitors (Assume-Guarantee)

**Statement.** Let `phi1, phi2` be LTL_f formulae with monitors `M1, M2`. Define
the AND-composed monitor `M_AND(phi1 ∧ phi2)` whose verdict at step `n` is the
Kleene three-valued minimum of `M1.verdict(n)` and `M2.verdict(n)` (where
`BOTTOM < UNKNOWN < TOP`). Then for every finite trace `w` and every step
`n ≤ |w|`:

```
verdict(M_AND, w_<=n) = min(verdict(M1, w_<=n), verdict(M2, w_<=n))
```

**Proof sketch.** Original adaptation of Pnueli's compositional verification
(1985). The proof proceeds by structural induction on the formula tree:
`PurePythonLTL3Monitor._AndMonitor.step()` (see [council/symbolic/verify/monitor.py](../council/symbolic/verify/monitor.py))
implements exactly the Kleene-min combinator; under finite-trace LTL3 semantics,
each child monitor's verdict is sound by T1, and the min preserves soundness
because `phi1 ∧ phi2` is satisfied iff both conjuncts are. Symmetric reasoning
applies to OR-composition with Kleene-max.

**References.**
- Pnueli. *In transition from global to modular temporal reasoning about programs*.
  In Logics and Models of Concurrent Systems, 1985.
- This adaptation is original; full proof to appear in P1 (AAMAS 2027) appendix.

**Mechanisation.** `tests/symbolic/verify/test_theorems.py::test_t2_compositionality_*`

## T3 — No-Go for Consensus-Only Aggregation

**Statement.** There exists a CTLK invariant — specifically:

```
G(consensus → ∃i. K_i evidenceFor(consensus))
```

(every consensus state must have at least one agent whose knowledge witnesses
evidence for the consensus) — that no purely vote-counting aggregator satisfies.

**Proof sketch (existence of a counterexample).** Consider a 3-agent trace
where all three agents emit `Vote(option="X")` with empty `evidence` tuples.
A simple-majority aggregator returns `"X"` with confidence 1.0 (3/3 votes).
However, the invariant `G(consensus → ∃i. K_i evidenceFor(consensus))` is
violated because no agent's vote carries evidence. The W1 property
`ProvenanceCompleteness = G(is_vote → has_evidence)` rejects this trace
(Verdict.BOTTOM). Therefore any aggregator that ignores evidence cannot
satisfy the CTLK invariant.

**Implications.** This motivates the L2 argumentation aggregator (W2): a
sound aggregator must consult the QBAF's evidence support edges, not just
the vote count.

**References.**
- Original; this argument appears in §3 of the planned P1 (AAMAS 2027) paper.
- For the broader "must beat MoA on at least one Pareto axis" requirement,
  see Constitution §6 in [`.claude/CLAUDE.md`](../.claude/CLAUDE.md).

**Mechanisation.**
- `tests/symbolic/verify/test_theorems.py::test_t3_no_go_*` — pytest-level
  counterexample on the W1 `ProvenanceCompleteness` monitor
  (`Verdict.BOTTOM`).
- `tests/integration/test_mcmas_t3_counterexample.py` — gated by
  `RUN_INTEGRATION=1` + `mcmas` on PATH; sends the same 3-agent
  unanimous-vote-without-evidence trace to MCMAS and asserts the model
  checker reports `AG(is_vote -> has_evidence) = FALSE` in the model.
  This **mechanically confirms** the W1 monitor's BOTTOM verdict at the
  external-tool level. See [`specs/adrs/0004-mcmas-resolved.md`](../specs/adrs/0004-mcmas-resolved.md).

The full ablation row against `MajorityVote`, `BordaCount`, and
`CondorcetAggregation` requires the L2 aggregator (W2) and remains W2/P1
work; the counterexample half of T3 is now mechanised.
