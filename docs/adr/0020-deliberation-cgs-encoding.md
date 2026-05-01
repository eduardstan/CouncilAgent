# ADR-0020: Deliberation CGS encoding for MCMAS — observability split, AP set, bounded evidence, round counter, SingleAssignment semantics

## Status

Accepted.

## Date

2026-05-01

## Context

Stage 2 of the T7 ATLK revision (`specs/t7-atlk-revision.md`)
introduced `council/symbolic/verify/cgs.py` with the `DeliberationCGS`
data model and the `canonical_t3_cgs(...)` factory; Stage 3 added the
`cgs_to_ispl` emitter that produces MCMAS-parseable ISPL (verified by
4 gated integration tests at
`tests/integration/test_t7_atlk_emitter.py`).

Translating the spec's mathematical statement
`M(P, Π, Θ, R) = ⟨ (L_i, Act_i, P_i, t_i)_{i ∈ Π}, (L_E, Act_E, P_E, t_E), I, V ⟩`
(per MCMAS manual §3.4 page 29) into ISPL involves several encoding
choices that are subtle but consequential. This ADR documents seven
of them so future readers (and reviewers) understand *why* the CGS
has the shape it has, and not another. Resolves
`specs/t7-atlk-revision.md` §"Open Questions" OQ-1, OQ-2, OQ-3, OQ-4,
OQ-6.

The decisions are listed in dependency order — earlier decisions
enable or constrain later ones.

## Decisions

### Decision 1 — `Semantics = SingleAssignment;` (NOT MultiAssignment)

The MCMAS manual §3.2.4 page 16 distinguishes two evolution semantics:

- **MultiAssignment** (the default): all evolution items in the same
  function are *mutually excluded* — if multiple items are enabled,
  exactly one fires per step, chosen non-deterministically. The
  manual's worked example on page 16 shows three successor states
  for one initial state, each picking a different item.
- **SingleAssignment**: evolution items are partitioned by the target
  variable; one item per partition fires per step, so multiple
  variables update *simultaneously*.

For our deliberation CGS, multiple variables MUST update simultaneously
per joint action. In a single step, alice's `propose_with_witness`
must flip `disclosed_p1_alice = true` *and* the round counter must
advance *and* (if bob simultaneously votes) `voted_p1_bob` must flip.
Under MultiAssignment these would be three mutually-exclusive choices
producing three successor states — none of which faithfully represents
our Moore-synchronous joint-action semantics.

Three alternatives evaluated:

- **A. MultiAssignment (default)** — rejected. The Moore-synchronous
  spec at §3.4 page 29 ("agents evolve simultaneously") cannot be
  encoded under per-step mutual exclusion of evolution items.
- **B. SingleAssignment with explicit per-variable partitioning**
  (chosen). The emitter writes one set of evolution clauses per
  target variable; each set's enabling conditions are mutually
  exclusive (so at most one fires per step), and partitions are
  independent (so all target variables update in parallel).
- **C. Custom synchronisation via a dedicated moderator agent that
  serialises updates** — rejected. Over-engineering; departs from
  the standard MCMAS idiom; introduces a turn-taking artefact that
  is not in the deliberation semantics.

### Decision 2 — Observability split for `~_i` indistinguishability

MCMAS manual §3.4 page 30 defines
`w ~_i w' iff l_i(w) = l_i(w') ∧ l_{E_P}(w) = l_{E_P}(w')` —
agent `i`'s knowledge is determined by (its own local state) AND
(the public part of the environment).

The encoding splits state across four ISPL sections:

| Section | Contents | Visible to |
|---|---|---|
| `agent_i.Vars` | `has_witness_p1` (boolean) | Only agent `i` |
| `agent_i.Lobsvars` | round, all `disclosed_p1_*`, all `voted_p1_*` | Agent `i` (lifted from Environment.Obsvars) |
| `Environment.Obsvars` | round, per-agent disclosed/voted flags | All agents (the public component `L_E^P`) |
| `Environment.Vars` | empty for the headline | None |

`Environment.Vars` is omitted entirely from the emitted ISPL when
empty — the grammar at §3.2.4 page 19 makes `envvardef?` optional
and the explicit empty `Vars: end Vars` block is not parser-friendly.

Three alternatives evaluated:

- **A. All-public encoding (no `agent.Vars` at all)** — rejected.
  Trivialises `K_i`: every agent observes everything, so
  `K_i evidence(a, i)` collapses to `evidence(a, i)` and the
  K-flavoured T7 statement (`<<{i}>> F K_i evidence(a, i)`) becomes
  vacuously equivalent to its plain-ATL counterpart. The whole
  point of choosing ATLK over pure ATL (spec Q2) is to keep the
  epistemic operator load-bearing.
- **B. Mixed encoding (chosen)**. `has_witness_p1` is private to
  agent `i`; `disclosed_p1_i` is public. The
  `propose_with_witness` action transfers the private witness to
  public knowledge, which is the semantically meaningful event the
  T7 theorem reasons about.
- **C. Full opacity (every var per-agent only)** — rejected. The
  spec's `consensus(c)` AP requires public access to all agents'
  votes; without a public `voted_p1_*` channel, consensus cannot be
  evaluated as a propositional fact.

### Decision 3 — Atomic proposition set

Three families of APs are emitted into the ISPL `Evaluation` block:

- **`consensus_p1`** ≔ `voted_p1_alice = true and voted_p1_bob = true and voted_p1_carol = true`
- **`evidence_p1_<id>`** for each agent `<id>` ≔ `Environment.disclosed_p1_<id> = true`
- **`voted_p1_<id>`** for each agent `<id>` ≔ `Environment.voted_p1_<id> = true`

This is the minimum AP set that lets us (a) state the T7 headline
formula `⟨⟨{i}⟩⟩ F K_i evidence(p1, i)`, (b) state the T7 corollary
about consensus, and (c) compose with future T3-style consensus
formulas in the P2 paper.

Three alternatives evaluated:

- **A. Minimal: `consensus_p1` + `evidence_p1_<id>` only** —
  rejected. Compositional formulas of the bible's form
  `consensus → ∃i. K_i evidence` need a separable `voted_p1_<id>`
  to expose the consensus structure.
- **B. Comprehensive (chosen)**: consensus + evidence + voted per
  agent. Three families, ~7 APs at the headline scale.
- **C. Per-claim-surface APs (multiple `p1`, `p2`, ...)** —
  deferred. The headline theorem uses one claim by design; richer
  multi-claim variants are future-work T7.* corollaries.

### Decision 4 — Bounded evidence encoding

The Move type's `Claim.evidence: tuple[str, ...]` is unbounded in
principle. For ISPL (which requires finite domains for BDD-based
model checking) we bound it to one boolean per `(agent, arg_id)`
pair: `agent_i.has_witness_p1` represents "agent `i` has at least
one evidence atom for argument `p1`". This is a sound abstraction
for the T7 *existence* claim: if any actual move with non-empty
`Claim.evidence` would correspond to a state where `has_witness=true`
+ `propose_with_witness` action, the encoding captures it.

The abstraction is **NOT sound for cardinality claims** ("how much
evidence?", "is the evidence diverse?") — those are out of T7's
scope and would require a richer encoding.

Three alternatives evaluated:

- **A. Bounded integer (`0..MaxEvidence`) per (agent, arg_id)** —
  rejected. Over-engineering; T7 doesn't need cardinality. Would
  blow up the BDD state space without changing what is provable.
- **B. Single boolean per (agent, arg_id)** (chosen). The
  existence-witness abstraction; minimal sufficient state.
- **C. Atomic-level encoding (per evidence-atom string)** —
  rejected. Unbounded state space; ISPL cannot represent it.

### Decision 5 — Round counter representation

A bounded integer `round : 0..max_rounds` lives in
`Environment.Obsvars` (so all agents observe it). The evolution
rules increment by one per step:

```
round = 1 if round = 0;
round = 2 if round = 1;
...
round = max if round = max - 1;
-- (no rule for round = max → variable stays via SingleAssignment partition semantics)
```

Saturation at `max_rounds` is achieved by *omitting* the rule for the
top value: under SingleAssignment, when no rule in the round
partition fires, the variable preserves its current value.

Three alternatives evaluated:

- **A. Unbounded integer** — rejected. ISPL requires bounded
  ranges for finite-state BDD model checking.
- **B. Bounded integer with saturating evolution** (chosen).
- **C. Round derived from trace-history length** (no explicit
  counter) — rejected. Would require a more complex environment
  evolution and obscures the round structure that the protocol
  reasons about.

### Decision 6 — Joint (Moore-synchronous) vs. interleaved moves

**No alternatives — this is enforced by MCMAS.** The manual §3.4
page 29 states explicitly: *"agents evolve simultaneously (notice
that this requirement is similar to the definition of Moore
synchronous game structures)."*. Joint action `α ∈ Act = Act_1 × …
× Act_n × Act_E` per page 29.

This matches our deliberation intuition: in each round, every agent
speaks (or abstains) at the same logical instant; the next state is
the result of applying the joint move.

### Decision 7 — `max_rounds` default = 2; scales to 3

The headline T_3 instance requires 2 rounds (round 0 to attempt
witness disclosure, round 1 to vote). Stage 3's integration test
confirms `max_rounds=3` also parses cleanly under MCMAS v1.3.0
(`tests/integration/test_t7_atlk_emitter.py::test_max_rounds_3_parses`).
Production / corollary T7.* instances can scale higher; 3 is the
minimum that exercises a non-trivial multi-round deliberation
without changing the headline theorem's truth value.

State-space sanity: at `max_rounds=2`, the BDD-reachable space is
bounded by `(round: 3) × (per-agent has_witness: 2) × (per-agent
disclosed: 2) × (per-agent voted: 2) × (per-agent action enum: 4) ≈ 10^5`
states under the joint-action transition relation — well within
MCMAS's BDD capacity.

## Consequences

**Positive:**

- The encoding faithfully realises the spec's `M(P, Π, Θ, R)`. Each
  of `(L_i, Act_i, P_i, t_i)`, `(L_E, Act_E, P_E, t_E)`, `I`, `V`
  has a direct ISPL counterpart.
- The Python-side step simulator (`DeliberationCGS.step`) is
  designed to match the ISPL evolution semantics under
  SingleAssignment. Stage 5 adds a property-based faithfulness test
  to verify this empirically.
- ADR-0017's under-approximation lemma (trace-level
  `evidence_backed_arg_ids ⊆ Strategically-Witnessable`) holds at
  the encoding level: any actual move with non-empty
  `Claim.evidence` corresponds to a `propose_with_witness` action
  that fires the disclosure rule.
- Future T7.* corollaries (richer Force projections — Challenge,
  Concede, Retract) require *additive* changes only: the
  `CGSAgentSpec` already accepts arbitrary actions and protocol
  clauses, so the data model is structurally ready.

**Neutral:**

- The `canonical_t3_cgs` factory hardcodes the single-claim,
  3-agent encoding for the headline. A general
  `from_protocol_automaton(protocol, agent_ids, max_rounds)`
  builder is future work and will be added when the empirical
  pipeline (W7) needs CGS instances for arbitrary
  `ProtocolAutomaton`s.
- `Environment.Vars` is omitted entirely when the private
  moderator state is empty. If future encodings need private
  moderator state (e.g., for `LTLfMonitorTermination`-driven
  interventions in the CGS), the emitter will start emitting the
  `Vars` block — no API change required.

**Negative:**

- The bounded-evidence encoding (Decision 4) is a *deliberate
  abstraction* of the unbounded `Claim.evidence` tuple. Reviewers
  who read both the spec and the implementation may notice the
  abstraction; we acknowledge it explicitly in the T7 statement
  by saying the theorem is about *existence* of evidence, not
  cardinality.
- `Semantics = SingleAssignment` is the non-default MCMAS choice;
  any future agent reading `cgs.py` must understand why
  MultiAssignment was rejected. This ADR's Decision 1 is the
  reference.
- The `max_rounds=2` default works for the headline but truncates
  any deliberation that would naturally require more rounds.
  Production / paper-grade instances should pass `max_rounds=3` or
  higher explicitly. ADR-0021 will discuss why scaling further
  needs separate consideration of `-atlk 2` state-space growth.

## Future work

- **`from_protocol_automaton(...)` builder**: drives
  `DeliberationCGS` from an arbitrary `ProtocolAutomaton`. The
  W7 empirical pipeline will need this. Out of T7-revision scope.
- **Corollary T7.* (richer Force projections)**: extends the
  canonical CGS to enable `Challenge`, `Concede`, `Retract`. New
  ISPL actions per agent + new protocol clauses + (possibly) new
  APs. The CGSAgentSpec / cgs_to_ispl machinery is ready; only
  the factory needs extension.
- **Multi-claim CGS**: the headline encodes one claim (`p1`).
  Multi-claim deliberation requires `disclosed_p<k>_<id>` and
  `voted_p<k>_<id>` per claim. The general factory above will
  generalise this.

## Realised by

- `council/symbolic/verify/cgs.py` — the `DeliberationCGS` data
  model + `canonical_t3_cgs(...)` factory + `cgs_to_ispl(...)`
  emitter. ~400 lines.
- `tests/symbolic/verify/test_cgs.py` — 33 unit tests covering the
  data model, canonical T_3 structure, initial state, step
  simulator, AP evaluation.
- `tests/symbolic/verify/test_cgs_emitter.py` — 21 unit tests
  covering the ISPL emitter's structural output.
- `tests/integration/test_t7_atlk_emitter.py` — 4 gated integration
  tests confirming MCMAS v1.3.0 parses the emitted ISPL on the
  default T_3, the alice-witness positive instance, the headline
  ATLK formula under `-atlk 2`, and `max_rounds=3` scaling.

## References

- `papers/4 --- verification and model-checking/Lomuscio et al. 2017
  "MCMAS: an open-source model checker for the verification of
  multi-agent systems" (STTT).pdf`
- `papers/4 --- verification and model-checking/Alur et al. 2002
  "Alternating-time Temporal Logic" (Journal of ACM).pdf`
- `papers/4 --- verification and model-checking/Fagin et al. 1995
  "Reasoning About Knowledge" (MIT Press).pdf`
- MCMAS v1.3.0 manual §3.2.4 page 16-19 (ISPL grammar) + §3.4
  page 29-30 (semantics of interpreted systems): <https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf>
- `specs/t7-atlk-revision.md` §"The math (precise statement)" and
  §"Open Questions" OQ-1, OQ-2, OQ-3, OQ-4, OQ-6
- `docs/adr/0017-privileged-knowledge-calibrator-interface.md` —
  cross-reference for the under-approximation lemma framing
- `docs/adr/0008-calibrator-abc-location.md` through ADR-0019 —
  W3 ADR family sharing rationale conventions

## Sequel

ADR-0021 (`-atlk 2` semantics choice) addresses spec OQ-5 and
documents the model-checking semantics applied to the encoding
defined here.
