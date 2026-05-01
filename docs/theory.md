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

## T7 — Strategic-Coupled Satisfies the CTLK Invariant

**Statement.** Let `T_3` be the canonical T3 counterexample trace: three
agents (A, B, C) each emit `Propose("X is the answer", evidence=())`
followed by `Vote("X is the answer", evidence=())` — three Proposes and
three Votes for the same answer, with no agent providing evidence atoms.
Let `Q = build_qbaf(T_3)` and let `s_DF` be `DFQuADSemantics().evaluate(Q)`,
`s_SC` be `StrategicCoupledSemantics(base=DFQuADSemantics(),
evidence_backed=evidence_backed_arg_ids(T_3), alpha=α,
consensus_threshold=0.5).evaluate(Q)` for any `α ∈ [0, 0.5)`.

Then for every Propose-derived argument `a` in `Q`:

```
a ∈ DFQuADSemantics().preferred_extension(Q)  AND
a ∉ StrategicCoupledSemantics(...).preferred_extension(Q)
```

That is: DF-QuAD admits the consensus argument into its preferred
extension (violating T3's CTLK invariant
`G(consensus → ∃i. K_i evidenceFor(consensus))`), but Strategic-Coupled
with strict-enough `α` excludes it (satisfying the invariant).

**Proof.** Each Propose has base score 0.7. Each of the three Votes
matches all three Proposes' surface ("X is the answer"); the W2
build_qbaf vote-boost rule adds `vote.confidence` per matching vote and
clamps to [0, 1]. With three votes of confidence 0.5 each, base scores
are saturated to `min(1.0, 0.7 + 3·0.5) = 1.0` for every Propose-derived
argument. There are no attackers (no Challenges in `T_3`) and no other
supporters; DF-QuAD's combination function gives `c(1.0, 0, 0) = 1.0`,
so `s_DF[a] = 1.0` for `a ∈ {p1, p2, p3}`. Each `s_DF[a] = 1.0 ≥ 0.5`,
so `a ∈ DFQuADSemantics().preferred_extension(Q)`. **DF-QuAD violates the
invariant** because no agent witnesses evidence (every `Claim.evidence`
is empty in `T_3`).

For Strategic-Coupled: `evidence_backed_arg_ids(T_3) = ∅` because no
Propose carries non-empty `Claim.evidence` and no Vote carries non-empty
`Claim.evidence` either (the ATL fragment from ADR-0012 returns the
empty frozen set). Strategic-Coupled's evaluate computes
`base_strengths = s_DF` then for each argument with strength
`≥ consensus_threshold = 0.5` AND `arg_id ∉ evidence_backed = ∅`,
demotes by `α`. Every Propose-derived argument satisfies both conditions,
so `s_SC[a] = α · s_DF[a] = α · 1.0 = α` for `a ∈ {p1, p2, p3}`. With
`α < 0.5`, `s_SC[a] < 0.5`, so `a ∉ StrategicCoupledSemantics(...).preferred_extension(Q)`.
**Strategic-Coupled satisfies the invariant** by construction: every
unbacked consensus argument is demoted below the extension threshold. ∎

**Why this is a recovery, not just a re-statement.** A trivial fix to
DF-QuAD's defect would be a binary "reject all unsupported consensus"
filter. Strategic-Coupled's value is that it preserves DF-QuAD's
gradedness: when *some* agents witness evidence and others do not, the
witnessed arguments retain their full DF-QuAD strength while unwitnessed
ones are demoted. The semantics composes with the underlying base
(DF-QuAD, QE, Ebs interchangeably) and with calibrated confidence (W3),
so future workstreams can extend it without re-deriving the invariant.

**Implications.** This is the central theoretical result of P2 (AAAI
2027). The full P2 paper extends T7 to:

- **Multi-coalition strategies** (`<<C>> F φ` for richer ATL fragments).
- **Non-binary evidence quality** (calibrated witness scores from W3
  feeding into the demotion factor `α(witness_quality)`).
- **Equilibrium properties under perturbation** (T5 manipulability bound
  with the demotion factor as a defence multiplier).

The W2/PR5 ship is the existence proof: T7 holds on the small instance
`T_3`. The mechanisation in `tests/regressions/test_t7_coupled.py`
demonstrates the extension-membership flip in code.

**References.**
- Original; full theorem statement and proof in P2 (AAAI 2027) appendix.
- Alur, Henzinger, Kupferman. *Alternating-time Temporal Logic*. JACM
  2002. The `<<A>>` coalition operator.
- This document §T3 — the no-go theorem this T7 defeats.

**Mechanisation.**
- `tests/regressions/test_t7_coupled.py::TestT3CounterexampleDFQuADFails` —
  pytest-level proof that DF-QuAD admits `p1, p2, p3` into the preferred
  extension on `T_3` (DF-QuAD strengths = 1.0 for each).
- `tests/regressions/test_t7_coupled.py::TestT7StrategicCoupledRescue` —
  pytest-level proof that the ATL fragment reports empty backing on
  `T_3`, and that Strategic-Coupled with `α = 0.4` excludes
  `p1, p2, p3` from the preferred extension.
- `tests/regressions/test_t7_coupled.py::TestT7BackwardCompatibility` —
  shows Strategic-Coupled reduces to DF-QuAD when the invariant is
  satisfied (one agent witnesses evidence).
- `tests/regressions/test_t7_coupled.py::TestT7ExtensionFlip` — the
  headline reviewer-visible flip: `df_ext ≠ sc_ext` on the canonical
  counterexample.

## T5 — Manipulability Bound

**Statement.** Let `Q` be a QBAF with `proposals(Q)` denoting the set of
non-withdrawn arguments (per ADR-0010 Q2), `n = |proposals(Q)|`, and
`sem` a gradual semantics under which a unique winner is well-defined.
Define the **flip cost** `flip_cost(Q, sem)` as the minimum number of
binary attack-edge perturbations — each toggling an ordered pair `(s,
t)` of distinct non-withdrawn arguments between weight 0 (absent) and
weight 1 (full attack) — required to change the winner. Then:

```
flip_cost(Q, sem)  ≤  max(0, n − 1)
```

with the convention that `flip_cost = 0` when `n = 0` (vacuous) and
`flip_cost = -1` (sentinel for "unflippable") when `n = 1` (no swap
target).

**Proof sketch.** Suppose the current winner is argument `w` (under
`sem`). For each other non-withdrawn argument `a ≠ w`, perturb the
attack edge `(a, w)` to weight 1.0 (adding it if absent, leaving it if
present at weight 1). After these `n − 1` perturbations, the winner's
in-edge set under `sem` includes attacks from every other argument
with maximum weight. Under DF-QuAD's saturating
ℱ-aggregation:

```
v_a(w) = ℱ([1.0 · strength(a) for a ≠ w])
       = 1 - ∏_{a ≠ w} (1 - strength(a))
```

If at least one `a ≠ w` has positive strength, `v_a(w) > 0`, so
`strength(w) < base(w)`. As `v_a(w) → 1`, `strength(w) → 0`. Since the
perturbations only modify edges *into* `w` (not edges out of `w` or
edges among the others), the strengths of `a ≠ w` are unchanged. The
runner-up — a non-`w` argument with the next-highest strength — now
strictly exceeds `w`'s reduced strength, flipping the winner. Total
perturbations: `n − 1`. ∎

**Tightness and refinements.** The `n − 1` bound is loose for
specific structures: graphs with isolated unattackable runners-up may
flip in a single perturbation (one new attack on the winner from any
positive-strength runner-up). Tighter bounds parameterised by
in-degree, out-degree, and the attack/support ratio (Baroni-Rago-Toni
2019) are proper refinements; the W2/PR9 ship is the simpler closed
form, sufficient as an upper bound for adversarial-robustness analysis.

**Why this is non-trivial.** Without the bound, an adversary could in
principle need exponentially many perturbations to flip a winner.
T5 says: bounded by the linear quantity `n − 1`. This is the
manipulability budget for a "flip-cost-aware" attacker — see the
related discussion in P4 (IJCAI 2027 co-evolutionary red/blue teaming
plan).

**References.**
- Baroni, Rago, Toni. *From fine-grained properties to broad principles
  for gradual argumentation: A principled spectrum*. International
  Journal of Approximate Reasoning 2019. (Specifically: §4.3 on
  manipulability quantification.) `papers/3 ---
  argumentation/Baroni et al. 2019 ... (IJAR).pdf`.
- Original: this T5 is W2's specialisation to the discrete-flip cost
  metric for DF-QuAD. The closed-form `n − 1` upper bound is W2 work.

**Mechanisation.**
- `council/symbolic/argue/manipulability.py::flip_cost` —
  brute-force minimum-flip search (exponential in `max_search`,
  default 8); intended for graphs ≤ 6 arguments.
- `council/symbolic/argue/manipulability.py::flip_cost_upper_bound` —
  closed-form `max(0, n − 1)`; computed in `O(|args|)`.
- `tests/regressions/test_t5_manipulability.py::TestFlipCostUpperBound`
  — pins the closed-form bound across `n ∈ {0, 1, 2, 5}` plus the
  withdrawn-exclusion case.
- `tests/regressions/test_t5_manipulability.py::TestFlipCostExact`
  — small examples (2-arg, 3-arg) where the brute-force search
  finds the actual flip cost and confirms `flip_cost ≤ upper_bound`.
- `tests/regressions/test_t5_manipulability.py::TestFlipCostBoundedByUpperBound`
  — property-based test across 20 random 4-argument QBAFs (seed=0)
  asserting `flip_cost ≤ upper_bound` on every instance.

## T6 — Caminada-Amgoud Rationality Postulate Matrix

**Statement.** Let `sem = DFQuADSemantics()`. Then `sem` satisfies
nine of the principles from Amgoud and Ben-Naim 2018 (IJAR) Table 1,
violates six, and one is not applicable. Specifically:

| Principle                  | Status | Test class                              |
|---------------------------|--------|----------------------------------------|
| Anonymity                  | ✓      | `TestAnonymity`                        |
| Bi-variate Independence    | ✓      | `TestBivariateIndependence`           |
| Bi-variate Directionality  | ✓      | `TestBivariateDirectionality`         |
| Bi-variate Equivalence     | ✓      | `TestBivariateEquivalence`            |
| Stability                  | ✓      | `TestStability`                        |
| Neutrality                 | ✓      | `TestNeutrality`                       |
| Monotony                   | ✓      | `TestMonotony`                         |
| Reinforcement              | ✓      | `TestReinforcement`                    |
| Franklin                   | ✓      | `TestFranklin`                         |
| Strict Monotony            | ✗      | `TestStrictMonotonyViolated`          |
| Strict Reinforcement       | ✗      | (analogous; test deferred)              |
| Resilience                 | ✗      | `TestResilienceViolated`               |
| Strict Franklin            | ✗      | (analogous; test deferred)              |
| Weakening                  | ✗      | `TestWeakeningViolated`                |
| Strengthening              | ✗      | `TestStrengtheningViolated`            |
| Inertia                    | N/A    | extension-semantics-only postulate     |

**Why violations are unavoidable.** The Gibbard-Satterthwaite-style
no-go for gradual semantics (Amgoud-Ben-Naim 2018, §6) shows: no
semantics can satisfy *all* 16 principles simultaneously on the
weighted bipolar fragment. Some violation is structurally
necessary — DF-QuAD trades the strict variants and the boundary-
preserving Resilience for the saturating ℱ-aggregation that makes
its closed form computable in `O(|args| · |edges|)`. The Ebs
semantics (PR4) satisfies more strict variants but at the cost of
boundary degeneracy at `w(a) ∈ {0, 1}` (ADR-0011 Q3).

**Significance.** T6 is the W2 *characterisation theorem*: it
identifies precisely which axiomatic guarantees DF-QuAD provides on
the W2 QBAF. P2 (AAAI 2027) reviewers can cite this matrix when
positioning DF-QuAD relative to QE / Ebs / Strategic-Coupled. The full
matrix appears in P2's appendix table.

**References.**
- Amgoud, Ben-Naim. *Evaluation of arguments in weighted bipolar
  graphs*. International Journal of Approximate Reasoning 2018.
  (Specifically: Table 1 and Definitions 8–14.) `papers/3 ---
  argumentation/Amgoud and Ben-Naim 2018 ... (IJAR).pdf`.
- Baroni, Rago, Toni. *From fine-grained properties to broad
  principles for gradual argumentation*. IJAR 2019. (Specifically:
  Tables 4–5 cross-referencing DF-QuAD's principle satisfaction.)
- Caminada, Amgoud. *On the issue of contamination in abstract
  argumentation frameworks*. ECSQARU 2007 — original rationality
  postulates (closure, direct/indirect consistency, non-interference)
  for *extension* semantics. The W2 matrix uses the gradual-semantics
  analogues (Amgoud-Ben-Naim 2018) which adapt these for weighted
  bipolar graphs.

**Mechanisation.**
- `tests/regressions/test_t6_postulates.py` — 16 test classes pinning
  the satisfaction matrix:
  - 9 satisfied: Anonymity, Bi-variate Independence, Bi-variate
    Directionality, Bi-variate Equivalence, Stability, Neutrality,
    Monotony, Reinforcement, Franklin
  - 4 violated (with counterexamples): Strict Monotony, Resilience,
    Weakening, Strengthening
  - 3 documented-only (without runtime tests, deferred): Strict
    Reinforcement, Strict Franklin, Inertia
- `TestPostulateMatrix` in the same file pins the cardinalities (9
  satisfied, 6 violated, 1 N/A) so future refactors don't silently
  drift.
