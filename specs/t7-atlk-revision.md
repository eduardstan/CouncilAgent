# Spec: T7 — ATLK Revision

**Branch:** `council-ns` → `feature/theorem-t7-atlk-revision`
**Status:** READY TO START — three open questions all resolved by the user (2026-05-01).
**Paper coupling:** P2 *Strategic Gradual Argumentation* (AAAI 2027 ≈ Aug 1 2026 ≈ 13 weeks). T7 is named in `COUNCILAGENT_NS_MASTER_PLAN.md` §9 P2 line 917 as a P2 headline theorem.
**Predecessor:** v0.2.2 (W3 calibration) shipped on `council-ns`. The current T7 statement at `docs/theory.md:174-262` is flagged NEEDS-REVISION by the theorem-audit-v2 (`~/.claude/projects/-home-eduard-Dropbox-Projects-CouncilAgent/memory/project_theorem_audit_v2.md`).

---

## Objective

Revise theorem T7 from a single-instance trace witness claim to a genuine ATLK (Alternating-time Temporal Logic with epistemic operator K_i) statement, model-checked by MCMAS over a real concurrent game structure derived from a `ProtocolAutomaton`. Preserve the trace-level `evidence_backed_arg_ids` fast path as a *sound under-approximation* (not a replacement) of the strategic-witness predicate.

This is theorem-revision work, not a W-numbered workstream. It is independent of W3 / W4 / W5 / W6 and predates W7 empirics; AAAI P2 needs the theorem section to land before empirical numbers can be reported.

**Why this matters.** The existing T7 (`docs/theory.md:174-262`) names "Alternating-time Temporal Logic" as the strategic logic, but the implementation `council/symbolic/argue/coupled_atl.py` is candid that *"the ATL fragment we need is mathematically trivial on finite traces — observable directly from Move metadata"* (lines 1-32). The constitution-reviewer audit (W3 closeout) and the theorem-checker v2 audit both confirm: no actual ATL machinery exists. AAAI 2027 argumentation+verification reviewers will notice. **Workarounds are not admissible** (user, 2026-05-01).

**Users:**
- The W2 `StrategicCoupledSemantics` (consumer of `evidence_backed_arg_ids`)
- The future P2 paper appendix (T7 statement + proof + mechanisation citation)
- The §11 ProvenanceReceipt story (the ATL verdict becomes a first-class receipt artefact)

**Success:**
- Every success criterion in §8 is met
- `theorem-checker` agent re-audit reduces T7 from `NEEDS-REVISION` to `READY`
- mypy strict + ruff clean across `council/symbolic/verify/`
- Trace-level fast path (`coupled_atl.py`) tests still pass — the new theorem subsumes, does not invalidate, the existing W2 work

---

## The math (precise statement)

Let `P` be a `ProtocolAutomaton` over a finite set `Π = {1, …, n}` of council agents (n ≥ 2). Let `Θ` be the bounded set of distinguishable claim surfaces in scope (one for each `Propose.claim.surface` value the protocol may produce).

Define the **deliberation concurrent game structure** `M(P, Π, Θ, R)`, parameterised by maximum rounds `R`, as the interpreted system (per MCMAS manual §3.4, page 29):

```
M = ⟨ (L_i, Act_i, P_i, t_i)_{i ∈ Π}, (L_E, Act_E, P_E, t_E), I, V ⟩
```

where:

| Symbol | Council interpretation |
|---|---|
| `L_i` | Per-agent local state: pending Force, last claim surface proposed/voted, per-arg evidence flags |
| `Act_i` | Force enum: `{Propose, Challenge, Concede, Retract, Question, Clarify, Vote, Abstain}` (full set encoded structurally) |
| `P_i: L_i → 2^{Act_i}` | `ProtocolAutomaton.legal_forces(trace, agent_id)` — the L0 protocol function (already implemented in W0) |
| `t_i` | Trace evolution under joint move (already implemented as `Trace.append`) |
| `L_E^P` (env *public*) | Round counter, partial trace history (Propose surfaces, Vote tally per round) — observable to all agents |
| `L_E^p` (env *private*) | Moderator/intervention state — invisible to council agents (used by L1 `LTLfMonitorTermination` only) |
| `V` | Atomic propositions: `consensus(c)` for c ∈ Θ; `evidence(a, i)` for arg-id a, agent i; `votes(i, c)` |

The Kripke model `M_IS = (W, R_t, ~_1, …, ~_n, V)` is constructed per manual §3.4 page 30:
- `W = G` reachable global states
- `R_t` temporal relation by joint actions
- `~_i` epistemic accessibility: `w ~_i w' iff l_i(w) = l_i(w') ∧ l_{E_P}(w) = l_{E_P}(w')` — i.e., agent `i` cannot distinguish two worlds with the same local state and the same public environment

**ATLK semantics is `-atlk 2`** (partial observability + uniform strategies) per Busard-Pecheur-Qu-Raimondi 2013 (now in `papers/4 --- verification and model-checking/`). User authorisation: `specs/t7-atlk-revision.md` Resolved Decisions Q1.

### Strategically-Witnessable predicate

Define for any reachable state `q ∈ W`:

```
Strategically-Witnessable(q) :=
  { a ∈ consensus_args(q) :
      ∃ i ∈ Π. (M_IS, q) ⊨ ⟨⟨{i}⟩⟩ F K_i evidence(a, i) }
```

(Spec form, in MCMAS ASCII syntax: `<g_i> F K(agent_i, evidence_a_i)`.)

Read: "argument `a` is strategically-witnessable at `q`" iff some single agent `i` has a uniform strategy under `-atlk 2` to (i) reach a future state where (ii) `i` knows that there exists evidence for `a` produced by `i`.

### T7 (revised)

> **T7 (Strategically-Coupled Demotion under ATLK).** Let `M = M(P, Π, Θ, R)` be a deliberation CGS, `q ∈ W` any reachable state, and `sem ∈ {DF-QuAD, QE, Ebs}` any base gradual semantics. Define:
> ```
> σ_min(q) := min { sem(Q(q))[a] : a ∈ consensus_args(q) }
> ```
> where `Q(q) = build_qbaf(trace(q))`. For any `α ∈ [0, threshold/σ_min(q))`:
> ```
> StrategicCoupledSemantics(
>     base=sem,
>     evidence_backed=Strategically-Witnessable(q),
>     α=α,
> ).preferred_extension(Q(q))
> ```
> excludes every `a ∈ consensus_args(q) ∖ Strategically-Witnessable(q)` from the preferred extension, while `sem(Q(q)).preferred_extension(Q(q))` includes them.
>
> **Corollary T7.0 (T3 recovery, instance form).** When `Strategically-Witnessable(q) = ∅` (no single agent has a strategy to come to know evidence for any consensus argument — the strongest no-go), `StrategicCoupledSemantics` excludes every consensus argument. The canonical `T_3` of W2/PR5 is one such instance.

### Headline-projection scope (for the model-checked instance)

The headline T7 instance verified by MCMAS is the canonical **T_3-like instance**:

- `n = 3` agents (Alice, Bob, Carol)
- `R = 3` maximum rounds
- Force projection in the headline: `{Propose, Vote, Abstain}` (the minimal set that produces a non-trivial extension flip)
- Full Force set `{Propose, Challenge, Concede, Retract, Question, Clarify, Vote, Abstain}` is **encoded structurally** in the CGS — the projection only restricts which Forces appear in the headline formulas, not what the CGS supports
- Bounded evidence: per `(agent, arg_id)` pair a single boolean `has_evidence` flag

**Corollary T7.* (richer-Force projections).** Deferred. Future work will extend the headline result to projections that enable `Challenge` / `Concede` / `Retract`. The CGS structurally supporting these moves from day 1 means no encoding rework is needed for the corollaries.

### Lemma (trace-level fast path is sound under-approximation)

> **Lemma.** For any trace `T` reachable in `M`, with `q(T)` the corresponding state:
> ```
> evidence_backed_arg_ids(T)  ⊆  Strategically-Witnessable(q(T))
> ```
> (Every arg already witnessed in the trace was strategically reachable by the witnessing agent.)

The lemma justifies keeping `coupled_atl.py:evidence_backed_arg_ids` as a *fast pure-Python path* used by the W2 `ArgumentationAggregator`. The MCMAS-verified `Strategically-Witnessable` is the *publishable* predicate for the P2 theorem; the trace-level version is operationally equivalent on the headline instance and dominates in cost-conscious settings.

---

## Resolved decisions (2026-05-01)

User-authorised, locked at session boundary.

| # | Question | Resolution | Source |
|---|---|---|---|
| Q1 | Which `-atlk` semantics? | **`-atlk 2`** (partial observability, uniform strategies). Busard et al. 2013 acquired into `papers/4 --- verification and model-checking/`. | User, 2026-05-01 |
| Q2 | Pure ATL `<<·>>` or ATLK `<<·>> + K_i`? | **ATLK.** Reviewer-grade epistemic-strategic claim; subsumes pure ATL and matches the bible's original formulation. | User, 2026-05-01 |
| Q3 | CGS scope? | **Full Force set encoded structurally; headline theorem on `{Propose, Vote, Abstain}` projection; corollary T7.\* deferred for richer projections.** | Senior judgement, user-acknowledged tradeoff |

---

## Tech Stack

- Python 3.11+, `mypy --strict`, `ruff`
- `pytest` + `pytest-asyncio` (mode = `auto`)
- **MCMAS v1.3.0** via subprocess (existing pattern: `tests/integration/test_mcmas_*.py`). MCMAS is a system binary at `/home/eduard/.local/bin/mcmas`; no Python package needed. The `[verify]` extra in `pyproject.toml` (currently `verify = []`) does not need additional Python pins for this work.
- Pure-Python CGS construction; subprocess invocation only in `tests/integration/`. Constitution §8 zero-framework-deps in core preserved.
- ATLK formulae use the MCMAS native syntax `<group_name> F K(agent_name, atomic_proposition)`.

---

## Commands

```bash
# Unit tests
uv run pytest tests/

# Integration tests (gated; runs real MCMAS subprocess)
RUN_INTEGRATION=1 uv run pytest tests/integration/test_t7_atlk.py -v

# Type-check + lint
uv run mypy council/
uv run ruff check council/ tests/

# Manual MCMAS smoke test (sanity check ISPL output)
uv run python -c "from council.symbolic.verify.cgs import DeliberationCGS, cgs_to_ispl; ..."
mcmas <generated.ispl>

# Theorem-checker re-audit (after T7 revision committed)
# (invoked via the theorem-checker subagent)
```

---

## Project Structure

Files created/modified by this revision (relative to repo root):

```
council/symbolic/verify/
├── cgs.py                    NEW   — DeliberationCGS dataclass + cgs_to_ispl emitter
├── ltlf.py                   MOD   — add CoalitionFinally, CoalitionGlobally, CoalitionUntil AST nodes
├── ispl.py                   MOD   — extend ltlf_to_ctl with ATL operators
└── atl_witness.py            NEW   — evidence_backed_arg_ids_via_atl(cgs) wrapper

council/symbolic/argue/
└── coupled_atl.py            MOD   — docstring update; cross-link the under-approximation lemma

tests/symbolic/verify/
├── test_cgs.py               NEW   — DeliberationCGS construction unit tests
└── test_atl_translator.py    NEW   — round-trip tests for the new ATL AST nodes

tests/integration/
└── test_t7_atlk.py           NEW   — gated MCMAS-backed regression for the headline theorem

tests/regressions/
└── test_t7_coupled.py        UNCHANGED — must still pass (under-approximation lemma)

docs/
├── theory.md                 MOD   — T7 statement + proof rewritten
└── adr/
    ├── 0020-deliberation-cgs-encoding.md       NEW   — observability split, AP set, bounded evidence
    └── 0021-atlk-semantics-2-uniform-strategies.md NEW — semantics choice + Busard 2013 cite

papers/4 --- verification and model-checking/
└── Busard et al. 2013 ...arXiv:1303.0793.pdf   ALREADY ACQUIRED (2026-05-01)
```

---

## Code Style

Follow `.claude/rules/code-style.md` (Python 3.11+, `from __future__ import annotations`, `@dataclass(frozen=True, slots=True)` for value objects, no mutable default args, mypy strict). Pure-Python CGS construction; subprocess to MCMAS lives only in `tests/integration/`.

Architecture rules already permit the relevant import directions:
- Approved Exception #4 (`council/symbolic/verify/interventions.py → council/dialect/moves.py`) covers the interventions path; the new `cgs.py` follows the same pattern (verify → dialect).
- Approved Exception #7 (W3 PR5; `council/termination.py → council/calibrate/jsd.py`) is the most recent precedent for a *function-scope* import to keep the no-extras path working. The new `atl_witness.py` may need a similar pattern if it imports from `argue/`.

CGS construction must use `from council.dialect.protocols.base import ProtocolAutomaton` (not a private import).

---

## Testing Strategy

### Unit tests (no MCMAS subprocess)

`tests/symbolic/verify/test_cgs.py`:
- `DeliberationCGS` constructs from `(ProtocolAutomaton, agent_ids, max_rounds, ...)` deterministically
- State space size matches expected combinatorial bound (≤ |Π|^R · |Act|^|Π|·R · 2^|evidence atoms|)
- `cgs.transitions(q)` honours `legal_forces(trace_of(q), i)` for every agent `i`
- Observability split: `cgs.local_state(i, q)` and `cgs.public_env(q)` agree with the formal spec
- `cgs_to_ispl(cgs, formulae)` returns a non-empty string with required ISPL sections (`Agent`, `Evaluation`, `InitStates`, `Groups`, `Formulae`)

`tests/symbolic/verify/test_atl_translator.py`:
- `CoalitionFinally(group="g_alice", arg=Atom("evidence_p1_alice"))` translates to `<g_alice> F evidence_p1_alice`
- `CoalitionGlobally`, `CoalitionUntil` similarly
- Nested ATL+K: `CoalitionFinally(group="g_alice", arg=Knows(agent="agent_alice", arg=Atom("evidence")))` translates to `<g_alice> F K(agent_alice, evidence)`
- Pre-existing LTL_f → CTL tests must still pass

### Integration tests (gated by `RUN_INTEGRATION=1`)

`tests/integration/test_t7_atlk.py`:
- Build the canonical 3-agent T_3-like CGS
- Emit ISPL, write to a temp file
- Invoke `mcmas -atlk 2 <path>` via subprocess
- Parse output; assert per-formula verdicts match the rewritten T7 statement:
  - `<g_alice> F K(agent_alice, evidence_p1_alice)` → FALSE on T_3
  - same for `g_bob`, `g_carol` → all FALSE
  - corollary: `Strategically-Witnessable(q_T3) = ∅`
- Positive instance: same CGS but with one agent supplying evidence in their initial state → that agent's formula is TRUE
- Faithfulness: at least one property-based test compares CGS-simulated runs against `Trace.append` evolutions for k ≤ 3 random joint strategies

### Regression (pre-existing tests must still pass)

`tests/regressions/test_t7_coupled.py` — every test in the existing file passes unchanged. This is the under-approximation lemma in operational form: the trace-level `evidence_backed_arg_ids` is a sound (subset) approximation of the ATLK `Strategically-Witnessable`.

### Coverage targets

- ≥ 95% line coverage on `council/symbolic/verify/cgs.py`
- ≥ 90% on `atl_witness.py`
- 100% on the new ATL AST nodes in `ltlf.py`

---

## Boundaries

### Always do

- Encode all 6 (well, 8 — see Force enum) Forces in the CGS structurally, not just the headline projection.
- Verify ISPL output parses via `mcmas` *before* running formula checks (write a sentinel test with no `Formulae` block; assert MCMAS exits 0 on parse-only).
- Pass `-atlk 2` explicitly in every integration test invocation. Document deviations.
- Document every observability split decision (which Vars go into Environment.Obsvars vs Vars vs agent.Vars) in ADR-0020.
- Cite Busard et al. 2013 by file path in ADR-0021 and in `docs/theory.md` T7 references.
- Cite Lomuscio et al. 2017 (MCMAS STTT) for the model-checker tool itself.
- Cite AHK 2002 for ATL semantics; cite Fagin et al. 1995 for K_i semantics.

### Ask first

- Any change to the `Force` enum or the `ProtocolAutomaton` ABC. These are W0 substrate; T7 should consume them, not reshape them.
- Any addition to `council/calibrate/` (out of scope here — W3 territory).
- Any new optional-dependency in `pyproject.toml` beyond what `[verify]` already declares.
- If MCMAS state-explosion blocks the headline instance: scope reduction (max_rounds=2, etc.) requires explicit user approval with rationale.

### Never do

- Hide CGS state-explosion behind a sentinel or magic constant; if `R = 3` is too large, reduce explicitly with documented numbers.
- Reuse `trace_to_ispl` (the trace-fixing emitter) for CGS work. The two emitters serve semantically distinct artefacts (trace-as-Kripke vs. protocol-as-CGS); a single function would conflate them.
- Claim "real ATL" without an MCMAS-verified test backing the claim. The whole point of this revision is to *eliminate* that overclaim.
- Rename `evidence_backed_arg_ids` (the trace-level public API). The under-approximation lemma keeps it valid; the `_via_atl` variant is an *additional* function, not a replacement.
- Use `Any`, `cast`, or `# type: ignore` to make mypy happy. The previous W2/PR5 audit reaffirmed this rule.

---

## Success Criteria (precise, testable)

1. **`docs/theory.md` T7** is rewritten using `⟨⟨·⟩⟩` and `K_i` operators per the formal statement above. The proof is restructured to (a) construct `M(P, Π, Θ, R)`, (b) cite the MCMAS-verified `Strategically-Witnessable(q_T3) = ∅` result, (c) prove the demotion under DF-QuAD by the existing finitary calculation, (d) lift to general `sem` by appeal to the manipulability bound (T5).
2. **`council/symbolic/verify/cgs.py`** exists. `DeliberationCGS(protocol, agent_ids, max_rounds=3)` is constructible from a `ProtocolAutomaton`. `cgs_to_ispl(cgs, formulae)` returns a string that `mcmas -atlk 2 <file>` parses without errors.
3. **`tests/integration/test_t7_atlk.py`** passes when gated. MCMAS verdicts for the headline T_3 instance match the theorem: every singleton-coalition `<g_i> F K(agent_i, evidence_*)` is FALSE.
4. **Trace-level `coupled_atl.py` tests** in `tests/regressions/test_t7_coupled.py` still pass — the under-approximation lemma holds operationally.
5. **mypy --strict** 0 errors on all new + modified `council/` files.
6. **ruff** clean across `council/symbolic/verify/`, `tests/symbolic/verify/`, `tests/integration/`.
7. **Theorem-checker re-audit** reduces T7 from `NEEDS-REVISION (overclaim)` to `READY` (or to `NEEDS-MINOR-REVISION` with no architectural concerns).
8. **ADR-0020** and **ADR-0021** committed, cross-linked from `docs/theory.md` T7 references.

---

## Open Questions (slice-level, resolve inside ADRs)

| # | Question | Where to resolve |
|---|---|---|
| OQ-1 | Exact AP set: minimal AP for the headline theorem vs. richer AP for follow-up T7.* | ADR-0020 |
| OQ-2 | Bounded evidence encoding: per-(agent, arg_id) boolean vs. per-(agent, claim_surface) | ADR-0020 |
| OQ-3 | Round counter: bounded integer in Environment.Obsvars vs. derived from history | ADR-0020 |
| OQ-4 | Joint vs. interleaved move semantics: MCMAS is Moore-synchronous, but our deliberation is naturally turn-based — choose encoding | ADR-0020 |
| OQ-5 | `<g> F K(...)` vs. `<g> F evidence(...)`: ATLK headline vs. pure-ATL fallback if ATLK proves intractable on the canonical instance | ADR-0021 |
| OQ-6 | What does "agent i's local state" include for `~_i` indistinguishability? | ADR-0020 |

These are encoding-level questions raised by translating the formal spec into ISPL. They will be resolved during the slice plan (next phase) and locked in the corresponding ADR before code lands.

---

## Cross-chat handoff context

A fresh session resuming this work should know:

1. **Decisions are locked.** §"Resolved decisions (2026-05-01)" Q1-Q3 are not negotiable without the user's explicit re-authorisation. Workarounds are not admissible (user, 2026-05-01).
2. **Branch.** `feature/theorem-t7-atlk-revision`, branched from `council-ns` at v0.2.2 (commit `191b2d7`).
3. **MCMAS install.** v1.3.0 at `/home/eduard/.local/bin/mcmas`. Verified working on a 4-formula ATL smoke test (13 reachable states, 11ms). The smoke-test ISPL is at `/tmp/mcmas-tests/atl_smoke.ispl` if you want to re-run it.
4. **Existing infrastructure.** `council/symbolic/verify/ispl.py:200` explicitly anticipated this work; `coupled_atl.py:1-32` is candid about the current "ATL"-in-name-only state. Both are honest predecessors, not adversaries.
5. **Force enum.** `council/dialect/moves.py:Force` defines all 8 Forces. The CGS structural encoding must support all 8; the headline theorem uses only 3.
6. **W3 just shipped.** v0.2.2 includes Approved Exception #7 (`council/termination.py → council/calibrate/jsd.py`) — this is the function-scope-import precedent if `atl_witness.py` needs to import from `argue/`. Constitution-reviewer audit at v0.2.2: APPROVED.
7. **Reference docs to read first.**
   - `papers/4 --- verification and model-checking/Lomuscio et al. 2017 ...MCMAS...pdf` (the tool paper)
   - `papers/4 --- verification and model-checking/Alur et al. 2002 ...ATL...pdf` (foundational ATL semantics)
   - `papers/4 --- verification and model-checking/Busard et al. 2013 ...arXiv:1303.0793.pdf` (atlk=2 semantics — partial observability + uniform strategies)
   - `papers/4 --- verification and model-checking/Fagin et al. 1995 ...Reasoning About Knowledge.pdf` (K_i semantics)
   - `https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf` §3.4 pages 29-32 (formal interpreted-system semantics + ATL semantics)
   - `COUNCIL_NS_PLAN.md` §6.4 (the bible's strategic-coupled framing)
   - `COUNCILAGENT_NS_MASTER_PLAN.md` §9 P2 (the AAAI 2027 deadline + paper structure)
   - `.claude/rules/architecture.md` (Approved Exceptions #4 and #7)
   - `docs/adr/0008-calibrator-abc-location.md` through `docs/adr/0019-confreeze-termination-bible-vs-paper.md` (sibling ADRs sharing rationale conventions)
8. **Estimated effort.** 5-6 person-days, possibly 7-8 with thorough faithfulness testing. Priority #1 for AAAI P2.
9. **Out-of-scope flags.**
   - `JSDConfidence` emission to `CouncilResponse.confidence` (W3 follow-up; gated separately)
   - `ChainedCalibrator` composition (future work per ADR-0017)
   - Real-LLM ECE benchmarks (W7 territory)
   - Other open theorems: T1, T2, T3, T5-deeper, T6 (separate sessions per `theorem-audit-v2`)
   - MCMAS-SLK extension (Strategy Logic with Knowledge — Čermák et al. 2014). Out of scope: ATLK is sufficient for T7. SLK is reserved for a possible T7.* variant in P2's future work section.

---

## References

- `papers/4 --- verification and model-checking/Alur et al. 2002 "Alternating-time Temporal Logic" (Journal of ACM).pdf`
- `papers/4 --- verification and model-checking/Busard et al. 2013 "Reasoning about Strategies under Partial Observability and Fairness Constraints" (arXiv:1303.0793).pdf`
- `papers/4 --- verification and model-checking/Cermák et al. 2014 "MCMAS-SLK: ..." (CAV).pdf` (referenced for future T7.*; out of scope here)
- `papers/4 --- verification and model-checking/Fagin et al. 1995 "Reasoning About Knowledge" (MIT Press).pdf`
- `papers/4 --- verification and model-checking/Lomuscio et al. 2017 "MCMAS: an open-source model checker for the verification of multi-agent systems" (STTT).pdf`
- MCMAS v1.3.0 manual: <https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf>
- `COUNCIL_NS_PLAN.md` §6.4 (bible: Strategic-Coupled framing)
- `COUNCILAGENT_NS_MASTER_PLAN.md` §9 P2 (AAAI 2027 paper structure)
- `.claude/rules/architecture.md` (Approved Exceptions #4, #7)
- `docs/theory.md` §T7 lines 174-262 (current statement, to be revised)
- `tests/regressions/test_t7_coupled.py` (existing trace-level mechanisation; under-approximation post-revision)
- `~/.claude/projects/-home-eduard-Dropbox-Projects-CouncilAgent/memory/project_theorem_audit_v2.md` (audit verdict and effort estimate this revision closes)
- ADR-0008 (Calibrator ABC location — sibling rationale doc), ADR-0015 through ADR-0019 (W3 family — sibling rationale convention)
