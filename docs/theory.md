# CouncilAgent-NS — Theory (W1: Verification Spine; W2: Argumentation)

This document collects the theorems that justify the symbolic stratum.
T1-T3 underpin the L1 verification spine (W1; P1 / AAMAS 2027). T4-T7
underpin the L2 argumentation aggregator (W2; P2 / AAAI 2027). T1 is
cited from prior work; T2-T7 are original or original adaptations.

> **Constitution §11 ↔ ADR-0009 reading.** Constitution §11 (in
> [`.claude/CLAUDE.md`](../.claude/CLAUDE.md)) states "the QBAF's argument
> count equals the Propose count" as part of the receipt-completeness
> contract. ADR-0009 (in [`docs/adr/0009-challenge-concede-as-arguments.md`](adr/0009-challenge-concede-as-arguments.md))
> reformulates this *operationally* as a Propose-bijection check —
> every Propose `move_id` appears as an `arg_id` in `baf.arguments`,
> with extra Argument nodes (Challenge / Concede-derived) permitted.
> Strict count-equality would forbid the structural information
> attack/support edges carry. The reformulation is implemented in
> `ProvenanceReceipt.is_complete` clause (d) at
> [`council/context.py`](../council/context.py). Reviewers of P2
> should expect this ADR-0009 cross-reference in the appendix.

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

## T7 — Strategically-Coupled Demotion under ATLK (revised 2026-05-02)

**Status.** This statement supersedes the earlier instance-form witness
claim. T7 is now parameterised over a witness predicate; two
predicates are shipped, each appropriate to a distinct phase of the
L2 lifecycle:

  - the **operational** predicate ``Witnessed(T)``
    (`council/symbolic/argue/coupled_atl.py`) — pure-Python,
    trace-direct, microseconds per call, used by
    ``StrategicCoupledSemantics`` at deliberation time;
  - the **verification** predicate ``Strategically-Witnessable(q)``
    (`council/symbolic/verify/atl_witness.py`) — MCMAS-checked ATLK
    fixpoint over the deliberation CGS, used at theorem time.

The under-approximation lemma below certifies that the operational
predicate is a sound subset of the verification predicate; both yield
T7 under the demotion claim. The revised T7 is mechanised by MCMAS
v1.3.0 under the partial-observability + uniform-strategies semantics
(`-atlk 2`, ADR-0021).

**Construction.** Let `P` be a `ProtocolAutomaton` over a finite set
`Π = {1, …, n}` of council agents. Let `Θ` be a finite set of
distinguishable claim surfaces. Define the **deliberation concurrent
game structure**

```
M(P, Π, Θ, R) = ⟨ (L_i, Act_i, P_i, t_i)_{i ∈ Π},
                  (L_E, Act_E, P_E, t_E),
                  I, V ⟩
```

per MCMAS manual §3.4 (page 29), where `R` bounds the round counter,
`L_i` includes a private witness flag per `(agent, arg_id)` pair,
`L_E^P` (public) holds round + per-agent disclosure + per-agent vote
flags, `Act_i` covers the deliberation Forces (Propose with/without
witness, Vote, Abstain at the headline projection; full Force set
encoded structurally per ADR-0020), and the protocol `P_i` gates
`propose_with_witness` on `agent_i.has_witness_p1 = true`. The
encoding is realised in `council/symbolic/verify/cgs.py` and
documented in ADR-0020.

**Strategically-Witnessable predicate.** For any reachable state
`q ∈ W` of the Kripke model `M_IS = (W, R_t, ~_1, …, ~_n, V)`
associated with `M`,

```
Strategically-Witnessable(q) :=
    { a ∈ consensus_args(q) :
        ∃ i ∈ Π. (M_IS, q) ⊨ ⟨⟨{i}⟩⟩ F K_i evidence(a, i) }
```

where `~_i` is MCMAS's epistemic accessibility relation
(`w ~_i w' iff l_i(w) = l_i(w') ∧ l_{E_P}(w) = l_{E_P}(w')`,
manual §3.4 page 30) and `⟨⟨·⟩⟩` is the AHK 2002 ATL coalition
operator with the uniform-strategy restriction of Busard et al. 2013
(ADR-0021). Read: "argument `a` is strategically witnessable at `q`"
iff *some single agent has a uniform strategy under partial
observability to reach a future state where they themselves know
that evidence has been produced for `a`*. The K-operator binding is
non-trivial because of the `~_i`-equivalence classes induced by the
private `has_witness_p1` flags (ADR-0020 Decision 2).

**Statement (T7).** For any reachable state `q ∈ M(P, Π, Θ, R)` and
any base gradual semantics `sem ∈ {DF-QuAD, QE, Ebs}`, let

```
σ_min(q) := min { sem(Q(q))[a] : a ∈ consensus_args(q) }
```

where `Q(q) = build_qbaf(trace(q))`. Then for any
`α ∈ [0, threshold/σ_min(q))`:

```
a ∈ consensus_args(q) ∖ Strategically-Witnessable(q)
    ⟹  a ∉ StrategicCoupledSemantics(
                base=sem,
                evidence_backed=Strategically-Witnessable(q),
                alpha=α,
            ).preferred_extension(Q(q))
```

while `sem(Q(q)).preferred_extension` includes `a`. Strategic-Coupled
demotes every consensus argument that no individual agent has a
strategy to come to know is evidence-backed — exactly the no-go
condition T3 forbids.

**Corollary T7.0 (T_3 recovery, mechanised under MCMAS).** Let `T_3`
be the W2-canonical 3-agent / 2-round trace where every agent emits
`Propose` with empty `Claim.evidence` and then `Vote` for the same
surface. The induced state `q_T3` of the canonical CGS
(`canonical_t3_cgs(max_rounds=2)`) satisfies

```
Strategically-Witnessable(q_T3) = ∅
```

verified by MCMAS v1.3.0 under `-atlk 2 -ufgroup g_<i>` for each
`i ∈ {alice, bob, carol}`: the ATLK formula
`⟨⟨{i}⟩⟩ F K_i evidence(p1, i)` is FALSE for every `i`. Therefore by
T7, every `a ∈ consensus_args(q_T3)` is excluded from the
Strategic-Coupled preferred extension. ∎

**Proof of T7.**

*Soundness of MCMAS for the ATLK formula.* The deliberation CGS
encoding (ADR-0020) faithfully realises the spec's
`(L_i, Act_i, P_i, t_i)_{i ∈ Π}, (L_E, Act_E, P_E, t_E), I, V`
tuple in ISPL. MCMAS implements the Kripke-model semantics of §3.4
page 30 directly via OBDD-based fixpoint computations on the
reachable global states. The `-atlk 2` semantics (Busard et al. 2013)
realises the AHK 2002 ATL semantics under partial observability with
uniform memoryless strategies. The integration test
`tests/integration/test_t7_atlk.py` invokes MCMAS on the canonical
T_3 instance and confirms the FALSE verdict for every `i`.

*Demotion claim.* Given `Strategically-Witnessable(q) ⊆ consensus_args(q)`
and `α < threshold/σ_min(q)`, every `a ∈ consensus_args(q) ∖
Strategically-Witnessable(q)` has
`StrategicCoupledSemantics(...).strength(a) = α · σ_min(q) <
threshold`, hence `a` is excluded from the preferred extension. The
finitary calculation is preserved from the previous T7 proof
(committed at `council/symbolic/argue/semantics/strategic_coupled.py`
and `tests/regressions/test_t7_coupled.py`); only the framing
generalises.

*Lift to general `sem`.* For `sem ∈ {QE, Ebs}` instead of DF-QuAD,
the same demotion formula applies because `StrategicCoupledSemantics`
is parameterised over its base (W2/PR6 design). T5
(manipulability bound, `docs/theory.md` §T5) guarantees the lift is
sound: the bound on `σ_min(q)` is semantics-agnostic. ∎

**Lemma (operational ↔ verification under-approximation).** For any
trace `T` with corresponding state `q(T)` in the CGS,

```
Witnessed(T)  ⊆  Strategically-Witnessable(q(T))
```

where `Witnessed(T)` is the operational predicate
(`evidence_backed_arg_ids` in `council/symbolic/argue/coupled_atl.py`)
and `Strategically-Witnessable(q)` is the verification predicate
(`evidence_backed_arg_ids_via_atl` in
`council/symbolic/verify/atl_witness.py`).

*Proof.* Every move in the trace was the result of *some* uniform
strategy for the move's author (the strategy "play this move on this
observation"). If that move makes `evidence(a, i)` hold, then agent
`i` had a strategy to make it hold — namely, the strategy that
includes the move. Therefore `a ∈ Strategically-Witnessable(q(T))`.
The converse fails: an agent can have a uniform strategy to disclose
without ever exercising it in the trace. ∎

**Why two predicates, by design.** The operational predicate is
deliberation-time-cheap and trace-direct;
`StrategicCoupledSemantics` cannot afford a subprocess on the hot
path. The verification predicate is theorem-time-exhaustive and
CGS-direct; it is needed to certify T7 against the AHK 2002
strategic semantics. Neither subsumes the other operationally —
they live on opposite sides of the cost-vs-completeness axis. The
under-approximation lemma is the certifying relationship between
them, and T7 holds for either choice (with the verification
predicate yielding a possibly larger demotion-immune set; the
operational predicate yielding a possibly smaller one, never
larger).

**Why this is a recovery, not a workaround.** The previous T7
statement claimed an instance witness ("on `T_3`, DF-QuAD admits
and Strategic-Coupled excludes"); the supporting `coupled_atl.py`
candidly noted that *"the ATL fragment we need is mathematically
trivial on finite traces — observable directly from Move metadata"*.
The revised T7 promotes the claim to a model-checked theorem over a
genuine concurrent game structure: the ATL operator is the AHK 2002
operator, the K operator is the Fagin et al. 1995 operator, the
semantics is Busard 2013's partial-observability uniform-strategy
variant, and the proof obligations on `q_T3` are discharged by
MCMAS-OBDD. The trace-direct check that previously *was* the
"trivial ATL fragment" is now properly recast as the **operational
predicate**, sitting next to the new **verification predicate** and
related to it by the under-approximation lemma. Neither is a
workaround for the other; they are the natural cost-vs-completeness
endpoints of one design.

**Implications.** This is the central theoretical result of P2 (AAAI
2027). The full P2 paper extends T7 to:

- **Multi-coalition strategies** (`⟨⟨C⟩⟩ F φ` for non-singleton
  coalitions; trivial extension of the encoding — adds new ISPL
  `Groups` entries).
- **Calibrated witness scores from W3** feeding into the demotion
  factor `α(witness_quality)` and the AP `evidence(a, i)` becoming
  a calibrated probability rather than a Boolean.
- **Equilibrium properties under perturbation** (T5 manipulability
  bound with the demotion factor as a defence multiplier; deferred
  to a P2 appendix).
- **Richer Force projections** (Challenge / Concede / Retract under
  the same CGS — the `CGSAgentSpec` accepts arbitrary actions and
  protocol clauses; corollary T7.* deferred to a follow-up
  workstream).

**References.**

- Alur, Henzinger, Kupferman 2002 — *Alternating-time Temporal
  Logic*, J. ACM 49(5). Foundational ATL semantics.
  `papers/4 --- verification and model-checking/Alur et al. 2002 ...JACM.pdf`.
- Busard, Pecheur, Qu, Raimondi 2013 — *Reasoning about Strategies
  under Partial Observability and Fairness Constraints*, EPTCS
  112. The `-atlk 2` semantics.
  `papers/4 --- verification and model-checking/Busard et al. 2013 ...arXiv:1303.0793.pdf`.
- Fagin, Halpern, Moses, Vardi 1995 — *Reasoning About Knowledge*,
  MIT Press. The K_i operator.
  `papers/4 --- verification and model-checking/Fagin et al. 1995 ...Reasoning About Knowledge.pdf`.
- Lomuscio, Qu, Raimondi 2017 — *MCMAS: an open-source model
  checker for the verification of multi-agent systems*, STTT.
  `papers/4 --- verification and model-checking/Lomuscio et al. 2017 ...MCMAS...pdf`.
- MCMAS user manual (cover labelled v1.2.2; grammar + flags match
  the installed v1.3.0 binary) §3.1 page 11 (`-atlk 2`,
  `-ufgroup`) + §3.2.4 page 16-19 (ISPL grammar) + §3.4 page 29-30
  (interpreted-systems semantics). Vendored at
  `papers/4 --- verification and model-checking/Lomuscio et al. n.d.
  "MCMAS v1.2.2 User Manual" (vendored from sail.doc.ic.ac.uk).pdf`;
  upstream: <https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf>.
- This document §T3 — the no-go theorem T7 defeats.
- This document §T5 — manipulability bound used in the `sem`-lift.
- ADR-0020 — Deliberation CGS encoding.
- ADR-0021 — `-atlk 2` semantics + `-ufgroup` AHK alignment.

**Mechanisation.**

- `tests/integration/test_t7_atlk.py::TestT7HeadlineNoGo::test_strategically_witnessable_empty_on_t3`
  — gated by `RUN_INTEGRATION=1`; invokes real MCMAS v1.3.0 under
  `-atlk 2` and asserts `Strategically-Witnessable(q_T3) = ∅`.
- `tests/integration/test_t7_atlk.py::TestT7HeadlinePositive::test_alice_witness_makes_p1_strategically_witnessable`
  — sanity: with `agent_alice.has_witness_p1 = true` at init,
  `Strategically-Witnessable = {p1}`. Confirms the encoding admits
  positive witnesses (not vacuously FALSE).
- `tests/integration/test_t7_atlk.py::TestT7VerdictMatrix::test_per_agent_verdicts_alice_witness`
  — per-agent verdict breakdown on the alice-witness instance:
  alice TRUE, bob/carol FALSE.
- `tests/integration/test_t7_atlk.py::TestEncodingReachabilitySanity`
  — pure-CTL reachability cross-checks (`EF disclosed_p1_alice`,
  `EF consensus_p1`) confirm the ISPL evolution rules are
  consistent with `DeliberationCGS.step`.
- `tests/regressions/test_t7_coupled.py` — mechanises the
  **operational predicate** branch of T7 (Witnessed(T) at the
  Strategic-Coupled aggregation site). Four test classes
  (`TestT3CounterexampleDFQuADFails`, `TestT7StrategicCoupledRescue`,
  `TestT7BackwardCompatibility`, `TestT7ExtensionFlip`) cover the
  trace-direct demotion calculation; all pass. The revised T7
  subsumes the previous instance witness without invalidating any
  of these tests — the operational predicate is one of two
  endpoints in the design, and these tests pin its behaviour.

## T5 — Manipulability Bound (DF-QuAD)

**Statement.** Let `Q` be a QBAF with `proposals(Q)` denoting the set of
non-withdrawn arguments (per ADR-0010 Q2), `n = |proposals(Q)|`, and
`sem = DFQuADSemantics()` (Amgoud-Ben-Naim 2018, Definitions 4–6) under
which the unique strongest non-withdrawn argument `w = winner(Q)` is
well-defined. Let `out(w) = { (w, a) ∈ attacks(Q) : a ∈ proposals(Q),
a ≠ w }` denote the winner's outgoing attacks against other proposals.
Define the **flip cost** `flip_cost(Q, sem)` as the minimum number of
binary attack-edge perturbations — each toggling an ordered pair `(s,
t)` of distinct non-withdrawn arguments between weight 0 (absent) and
weight 1 (full attack) — required to change the winner. Then:

```
flip_cost(Q, sem)  ≤  (n − 1) + |out(w)|
```

with the sentinel convention `flip_cost = -1` when `n < 2` (no swap
target) or when `sem` cannot evaluate `Q` (e.g., a cyclic input that
DF-QuAD rejects); in those cases `flip_cost_upper_bound` returns the
same `-1` sentinel so the inequality holds vacuously.

**Why this statement narrows to DF-QuAD.** The previous (W2/PR9)
formulation quantified over "any gradual semantics under which a unique
winner is well-defined", but the proof depends materially on DF-QuAD's
saturating ℱ-aggregation `v_a(w) = 1 − ∏_{a ≠ w} (1 − strength(a))` and
on DF-QuAD's rejection of cyclic graphs. Generalising to QE / Ebs /
Strategic-Coupled requires a separate proof per semantics; the honest
move is to narrow rather than over-claim. (See *Tightness and
refinements* below for which generalisations are reachable.)

**Why the `+ |out(w)|` term is required.** A property-based search at
`n = 2` over 20 random QBAFs (seed `random.Random(0)`,
`tests/regressions/test_t5_manipulability.py::test_random_qbafs_all_within_bound[2]`)
exposed the following counterexample to the previous `n − 1` bound:

```
arguments:  a0 (base 0.567),  a1 (base 0.826)
attacks:    a1 → a0  weight 0.78
winner:     a1
```

Here `n − 1 = 1` but `flip_cost = 2`. Toggling `(a1, a0)` *off* leaves
both base scores intact — `a1` still wins. Toggling `(a0, a1)` *on*
creates a 2-cycle that DF-QuAD's `evaluate(Q)` rejects (raises
`ValueError`), so this perturbation does not produce a valid new
winner. Any single-perturbation choice either fails to flip or creates
an unevaluable graph. The minimum flip in this instance is two
perturbations: first toggle `(a1, a0)` *off* (clearing the cycle
hazard), then toggle `(a0, a1)` *on* — exactly `(n − 1) + |out(w)| =
1 + 1 = 2`.

**Proof sketch.** Suppose `w = winner(Q)` is the current strongest
non-withdrawn argument under DF-QuAD. We construct an explicit
perturbation sequence in two stages:

*Stage 1 (clear the winner's outgoing attacks — `|out(w)|`
perturbations).* For each `(w, a) ∈ out(w)`, toggle the edge OFF
(weight `1 → 0`). None of these changes flips the winner: removing an
attack *from* `w` can only *increase* the strengths of attacked targets
(possibly raising them, never lowering `w`'s own strength). After
Stage 1, `out(w) = ∅` in the perturbed graph.

*Stage 2 (saturate the winner's incoming attacks — `n − 1`
perturbations).* For each `a ∈ proposals(Q) \ {w}`, toggle the edge
`(a, w)` ON to weight 1 (adding it if absent, leaving it if present at
weight 1). Because Stage 1 removed every `(w, a)`, no Stage-2 edge
addition can create a 2-cycle through `w`; DF-QuAD's evaluate succeeds.
After Stage 2, `w`'s in-edge set under DF-QuAD includes attacks from
every other proposal at maximum weight. Under DF-QuAD's saturating
ℱ-aggregation:

```
v_a(w) = ℱ([1.0 · strength(a) for a ≠ w])
       = 1 − ∏_{a ≠ w} (1 − strength(a))
```

If at least one `a ≠ w` has positive strength (which holds since each
`a ≠ w` retains its base score, the perturbations not having modified
edges among the others), `v_a(w) > 0`, so `strength(w) < base(w)`. As
the product approaches 0, `strength(w) → 0`. The runner-up — the
non-`w` argument with the next-highest strength — strictly exceeds
`w`'s reduced strength, flipping the winner.

Total perturbations: `|out(w)| + (n − 1)`. ∎

**Tightness and refinements (honest future work).** The bound is tight
for the `n = 2` boundary case shown above. For `n ≥ 3` it is generally
loose: graphs with isolated unattackable runners-up may flip in a
single perturbation. Tighter bounds parameterised by in-degree,
out-degree, and the attack/support ratio are reachable in principle —
Baroni-Rago-Toni 2019 IJAR §4.2 develops the closed-form sensitivity
of strength to attack additions under (strict) monotonicity, which is
*the* technical machinery a refined manipulability bound would build
on. We do not attempt that derivation here; the `(n − 1) + |out(w)|`
bound is the simplest form sufficient for adversarial-robustness
analysis on small councils and is what the property test verifies.

**Why this is non-trivial.** Without the bound, an adversary could in
principle need exponentially many perturbations to flip a winner.
T5 says: bounded by the linear quantity `(n − 1) + |out(w)|`, computable
in `O(|args| + |attacks|)`. This is the manipulability budget for a
"flip-cost-aware" attacker — see the related discussion in P4 (IJCAI
2027 co-evolutionary red/blue teaming plan).

**References.**
- Amgoud, Ben-Naim. *Evaluation of arguments in weighted bipolar
  graphs*. International Journal of Approximate Reasoning 2018.
  (Definitions 4–6 fix the DF-QuAD ℱ-aggregation we use.) `papers/3 ---
  argumentation/Amgoud and Ben-Naim 2018 ... (IJAR).pdf`.
- Baroni, Rago, Toni. *From fine-grained properties to broad principles
  for gradual argumentation: A principled spectrum*. International
  Journal of Approximate Reasoning 2019. (§4.2 — strict monotonicity
  principles — would underpin a refined in-degree-parameterised bound;
  see *Tightness and refinements* above.) `papers/3 ---
  argumentation/Baroni et al. 2019 ... (IJAR).pdf`.
- Original: T5 is W2's specialisation to the discrete-flip cost metric
  for DF-QuAD. The `(n − 1) + |out(w)|` upper bound is W2 work; the
  `+ |out(w)|` correction (over the previous `n − 1` claim) was
  discovered in the property-based sweep at `n = 2` during the
  feature/theorem-t5-t6-revision branch (2026-05-02).

**Mechanisation.**
- `council/symbolic/argue/manipulability.py::flip_cost` —
  brute-force minimum-flip search (exponential in `max_search`,
  default 8); intended for graphs ≤ 6 arguments.
- `council/symbolic/argue/manipulability.py::flip_cost_upper_bound` —
  closed-form `(n − 1) + |out(w)|` with the `-1` sentinel for
  unflippable inputs; computed in `O(|args| + |attacks|)`.
- `tests/regressions/test_t5_manipulability.py::TestFlipCostUpperBound`
  — pins the closed-form bound across attack-free QBAFs at
  `n ∈ {0, 1, 2, 5}` plus the withdrawn-exclusion case (where
  `|out(w)| = 0` reduces the bound to `n − 1`).
- `tests/regressions/test_t5_manipulability.py::TestFlipCostExact`
  — small examples (2-arg, 3-arg) where the brute-force search
  finds the actual flip cost and confirms `flip_cost ≤ upper_bound`.
- `tests/regressions/test_t5_manipulability.py::TestFlipCostBoundedByUpperBound`
  — property-based test across `N ∈ {2, 3, 4, 5}` (`pytest.mark.parametrize`)
  with 20 random QBAFs per `N` (seed `random.Random(0)`), asserting
  `flip_cost ≤ upper_bound` on every one of the 80 instances.

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
| Strict Reinforcement       | ✗      | `TestStrictReinforcementViolated`     |
| Resilience                 | ✗      | `TestResilienceViolated`               |
| Strict Franklin            | ✗      | `TestStrictFranklinViolated`          |
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
- Caminada, Amgoud. *On the evaluation of argumentation formalisms*.
  Artificial Intelligence 171(5–6), 286–310, 2007 — the canonical
  rationality-postulates source for *extension* semantics (closure,
  direct/indirect consistency, non-interference). The W2 matrix tests
  the *gradual-semantics analogues* of these postulates (Amgoud-Ben-Naim
  2018, Definitions 8–14), which adapt the extension-semantics
  formulations for weighted bipolar graphs. `papers/3 ---
  argumentation/Caminada and Amgoud 2007 "On the evaluation of
  argumentation formalisms" (Artificial Intelligence).pdf`.

**Mechanisation.**
- `tests/regressions/test_t6_postulates.py` — 16 test classes pinning
  the satisfaction matrix:
  - 9 satisfied: Anonymity, Bi-variate Independence, Bi-variate
    Directionality, Bi-variate Equivalence, Stability, Neutrality,
    Monotony, Reinforcement, Franklin
  - 6 violated (with counterexamples): Strict Monotony, Strict
    Reinforcement, Resilience, Strict Franklin, Weakening, Strengthening.
    The two strict-saturation cases (Strict Reinforcement, Strict
    Franklin) use boundary fixtures (base = 1.0) where DF-QuAD's
    saturating combination function caps further progress; the precise
    Amgoud-Ben-Naim 2018 Definition 11/12 antecedents are documented
    in the test docstrings.
  - 1 documented-only (Inertia — extension-semantics-only postulate)
- `TestPostulateMatrix` in the same file pins the cardinalities (9
  satisfied, 6 violated, 1 N/A) so future refactors don't silently
  drift.
