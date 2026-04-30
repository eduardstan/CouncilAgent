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
  external-tool level. See [`docs/adr/0005-mcmas-resolved.md`](adr/0005-mcmas-resolved.md).

The full ablation row against `MajorityVote`, `BordaCount`, and
`CondorcetAggregation` requires the L2 aggregator (W2) and remains W2/P1
work; the counterexample half of T3 is now mechanised.

## T4 — Recovery-of-Borda Lemma

**Statement.** Let an N-candidate, K-voter Borda election be encoded as a
"Borda BAF" `Q = (A, ∅, ∅)` where `A = {a_c | c is a candidate}`,
`base_score(a_c) = Borda_count(c) / (K · (N-1))`, and there are no
attack/support edges. Then DF-QuAD on `Q` produces strengths
`s(a_c) = base_score(a_c) = Borda_count(c) / (K · (N-1))` — a strict
monotone re-scaling of Borda counts.

**Proof.** By the recursive definition of DF-QuAD's score function (Rago
2016, Definition 3) on a no-edge graph:

- For every argument `a` in `Q`: `R⁻(a) = ∅` and `R⁺(a) = ∅`.
- Therefore `SEQ_𝒮ℱ₂(R⁻(a)) = ()` and `SEQ_𝒮ℱ₂(R⁺(a)) = ()`.
- Lemma 1 gives `ℱ(()) = 0`, so `v_a = 0` and `v_s = 0`.
- The combination function (Equation 19, since `v_a = v_s`) gives
  `c(v_0, 0, 0) = v_0 - v_0 · |0 - 0| = v_0`.

So `𝒮ℱ₂(a_c) = base_score(a_c) = Borda_count(c) / (K · (N-1))`. The map
`f(x) = x / (K · (N-1))` is strictly monotone on `[0, K · (N-1)]`, and
`s(a_c) = f(Borda_count(c))`. ∎

**Why the richer encoding fails.** A natural alternative encodes per-voter
preference as Support edges with weight `points_v(c) / (N-1)`. Under that
encoding `v_s(c) = ℱ([points_v(c)/(N-1) for v in voters]) = 1 - ∏(1 - x_v)`.
This saturating product is *not* monotone in `Σ x_v`: e.g., with two
candidates each receiving total points 1.5 (N=3, K=2) but distributed as
(1.0, 0.5) vs (0.75, 0.75), `ℱ` returns 1.0 vs 0.9375 — the same sum
yields different aggregated strengths. So T4 holds *only* under the
no-edge encoding; this is the precise meaning of "up to monotone
re-scaling".

**Implications.** DF-QuAD is consistent with classical Borda voting on
the vote-only fragment of deliberation. This is a sanity check, not a
strength claim; the value of L2 over plain Borda comes from non-trivial
QBAF structure (Challenges, Concedes, calibrated base scores).

**References.**
- Rago, Toni, Aurisicchio, Baroni. *Discontinuity-Free Decision Support
  with Quantitative Argumentation Debates*. KR 2016, Lemma 1
  (closed-form ℱ), Equations 19–20 (combination function).
- Borda, J.-C. *Mémoire sur les élections au scrutin*, 1781 — the
  original positional voting rule.

**Mechanisation.**
- `tests/regressions/test_t4_borda.py::TestT4ClosedForm3Candidate` —
  hand-derived 3-candidate election with closed-form expected
  strengths (committed in
  `tests/symbolic/argue/fixtures/borda_3candidate.json`).
- `tests/regressions/test_t4_borda.py::TestT4PropertyRandomElections` —
  property-based check across (N=2..6, K=3..10), seed 0; asserts that
  the Borda equivalence-class structure equals the DF-QuAD
  equivalence-class structure (handles ties correctly).
- `tests/regressions/test_t4_borda.py::TestBordaBAFWellFormed` — sanity
  invariants of the Borda BAF construction.
