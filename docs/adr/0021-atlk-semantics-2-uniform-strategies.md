# ADR-0021: T7 ATLK verification uses MCMAS `-atlk 2` (partial observability + uniform strategies)

## Status

Accepted.

## Date

2026-05-01

## Context

Stage 1 of the T7 ATLK revision (`specs/t7-atlk-revision.md`)
committed to **ATLK** — Alternating-time Temporal Logic combined
with the epistemic operator `K_i` — for the headline T7 theorem
(spec Q2). The user further locked the model-checking semantics to
`-atlk 2` (spec Q1). This ADR documents *why* partial observability
+ uniform strategies is the philosophically and technically correct
semantics for council deliberation, and what alternatives were
rejected. Sequel to ADR-0020 (CGS encoding).

MCMAS v1.3.0 supports three semantics for ATL with knowledge,
selected via the `-atlk` command-line flag (manual §3.1 page 11):

| `-atlk` | Observability | Strategy class | Reference |
|---|---|---|---|
| **0** (default) | Full | Perfect-recall positional | AHK 2002 |
| **1** | Full + LTL fairness | As 0 with fairness constraints | — |
| **2** | **Partial** | **Uniform** | Busard-Pecheur-Qu-Raimondi 2013 |

The encoding choices in ADR-0020 — particularly the observability
split (Decision 2: `agent_i.Vars` private to agent `i`,
`Environment.Obsvars` public to all) — only become meaningful under
a semantics that respects partial observability. Choosing the wrong
`-atlk` value would silently collapse the K-flavoured T7 statement
to a plain-ATL claim and erase the epistemic content.

## Decision

**Use `-atlk 2` (partial observability + uniform strategies, per
Busard-Pecheur-Qu-Raimondi 2013) for every MCMAS invocation that
verifies a T7 ATLK formula.**

A *uniform strategy* for agent `i` is a function from `i`'s
*observation history* (the sequence of `~_i`-equivalence classes
visited along the run) to actions. The MCMAS implementation enforces
**memoryless** uniformity: the strategy depends only on the current
observation class, not on the full history. This is positional
ATL_ir in the literature (Bulling-Jamroga 2014, Goranko-Jamroga
2015).

The integration test
`tests/integration/test_t7_atlk_emitter.py::test_atlk_formula_parses_under_semantics_2`
confirms that the canonical-T_3 ISPL with the headline ATLK formula
parses and is evaluated under `-atlk 2` on the local MCMAS v1.3.0
install. Stage 5 will tighten this from "parses" to "produces the
expected verdict".

## Alternatives Considered

### Option A — `-atlk 0` (full observability, perfect-recall positional)

The default and most permissive semantics. Every agent observes
every other agent's local state at every step. Strategies can branch
on the global state.

**Rejected.** Two reasons:

1. **Trivialises `K_i`**. The epistemic accessibility relation
   `w ~_i w'` (per MCMAS manual §3.4 page 30) is defined as
   `l_i(w) = l_i(w') ∧ l_{E_P}(w) = l_{E_P}(w')`. Under full
   observability, `l_i` includes every other agent's local state,
   so `~_i` reduces to the identity relation: every state is its
   own equivalence class. Therefore `M, w ⊨ K_i φ ⟺ M, w ⊨ φ` for
   every `i, φ`. The K operator collapses to plain truth, and the
   spec's headline ATLK formula
   `⟨⟨{i}⟩⟩ F K_i evidence(p1, i)` becomes equivalent to the pure
   ATL form `⟨⟨{i}⟩⟩ F evidence(p1, i)`. We chose ATLK over pure
   ATL (spec Q2) precisely to keep the epistemic content
   load-bearing — option A erases that choice.
2. **Operationally implausible**. Full observability assumes alice
   can base her action choice on bob's private `has_witness_p1`
   flag — but the encoding (ADR-0020 Decision 2) puts that flag in
   `agent_bob.Vars`, deliberately invisible to alice. A strategy
   that branches on data alice cannot observe is not a strategy
   alice can actually execute.

### Option B — `-atlk 1` (full observability + LTL fairness)

Same as Option A but adds LTL fairness constraints over transitions.
Useful when one wants to rule out infinite runs that get stuck in a
non-progress cycle.

**Rejected.** Fairness addresses a different concern (liveness under
infinite executions) and does not restore partial observability. The
`K_i`-trivialisation problem from Option A persists. T7's headline
is finite-horizon (bounded `max_rounds`); fairness is irrelevant
here.

### Option C (chosen) — `-atlk 2` (partial observability, uniform strategies)

A strategy `σ_i` is a function from `i`'s observation classes to
actions; states that are `~_i`-indistinguishable to agent `i` MUST
yield the same action choice (the *uniformity constraint*).

**Chosen.** Three properties make this the right semantics:

1. **`K_i` is meaningful**. Non-singleton `~_i` classes are
   preserved: alice cannot distinguish two states that differ only
   in `agent_bob.has_witness_p1`. Therefore
   `M, w ⊨ K_i evidence(p1, j)` actually constrains agent `i`'s
   knowledge; it doesn't collapse to plain truth.
2. **Strategies are operationally executable**. Uniformity ensures
   that alice's strategy never branches on data she cannot
   observe. The model-check verdict `⟨⟨{i}⟩⟩ F φ = TRUE` means
   "there is a strategy `i` could actually deploy to reach φ" —
   not "there is a strategy in some hypothetical full-information
   universe".
3. **Matches the deliberation intuition**. Council agents in
   practice plan based on what they see in the public deliberation
   record + their own private state. Option C is the formal
   counterpart of that.

## Consequences

**Positive:**

- The headline T7 statement
  `Strategically-Witnessable(q) := { a : ∃ i ∈ Π. (M, q) ⊨ ⟨⟨{i}⟩⟩ F K_i evidence(a, i) }`
  has its intended epistemic-strategic content. The K operator
  binds non-trivially.
- The verification verdicts MCMAS produces under `-atlk 2` are
  semantically aligned with the deliberation operational reality:
  no "ghost strategies" that depend on inaccessible state.
- Reviewer-grade: AAAI 2027 P2 reviewers in the argumentation +
  verification cross-track can verify the encoding against the
  Busard 2013 reference and the AHK 2002 baseline. The choice is
  citation-grounded, not ad-hoc.

**Neutral:**

- `-atlk 2` requires a uniform-strategy enumeration that is more
  expensive than the default Option A. For the canonical T_3
  instance (3 agents, `max_rounds ≤ 3`, bounded evidence) this is
  not a problem; Stage 3 integration tests confirm sub-second
  parse + load times. For larger CGS instances (paper-grade
  empirics), state-space cost will need separate analysis.
- The `-uniform` flag and the `-atlk 2` flag are equivalent under
  MCMAS for our purposes (manual §3.1 page 11: `-uniform`
  "subsumes the option `-atlk`"). The integration test uses
  `-atlk 2` for explicitness.

### Addendum (2026-05-02) — `-ufgroup` semantic correction (Stage 5.3 finding)

The default behaviour of `-atlk 2` makes **every** agent's
strategies uniform. For singleton-coalition formulas like
`⟨⟨{i}⟩⟩ F φ`, the AHK 2002 ATL semantics demands only
that the coalition's strategies be uniform — the opponents are
treated as **full-information adversaries** (any strategy, not
necessarily uniform). The two semantics differ on whether the
opponents' strategy space is restricted; the default conflates
them.

The `-ufgroup <name>` flag (manual §3.1 page 11) restricts
uniform-strategy generation to the named coalition only. For our
T7 integration tests we pass `-ufgroup g_<short>` (one per agent)
when checking each agent's `⟨⟨{i}⟩⟩` formula. This yields:

- Faithful AHK 2002 semantics for the singleton-coalition formulas
  (only the coalition's strategies are required to be uniform).
- Significantly cheaper model-checking on the alice-witness
  positive instance: without `-ufgroup` MCMAS times out after
  180s on `max_rounds=2`; with `-ufgroup g_alice` it returns the
  TRUE verdict in ~60s on `max_rounds=1` and ~100s on
  `max_rounds=2`.

The realization: the `MCMASRunner` Protocol takes
`ufgroup: str | None = None`, and
`evidence_backed_arg_ids_via_atl` invokes the runner once per
(arg_id, agent_id), passing the agent's singleton-group name as
`ufgroup`. This costs three MCMAS subprocess calls per arg_id
(model rebuilt three times) but is the only way to obtain the
correct AHK semantics for singleton-coalition formulas under the
default MCMAS implementation.

**Negative:**

- Memorylessness limitation. MCMAS implements *positional* uniform
  strategies (the strategy depends only on the current observation
  class, not history). For our finite-horizon T_3 instance this is
  the right choice — there is no observation-history accumulation
  across rounds that matters for the headline formula. For richer
  T7.* corollaries that involve trace-history dependencies (e.g.,
  "if agent `i` saw bob disclose in round 0, then `i` should
  retract in round 1"), perfect-recall partial-obs ATL would be
  needed. That is undecidable in general (Bulling-Jamroga 2014,
  Theorem 4.1) and decidable only in restricted fragments. Out of
  T7-revision scope; flagged as future work.
- Complexity-class shift. Classical full-obs ATL model-checking is
  P-complete; partial-obs ATL_ir is PSPACE-complete (Schobbens
  2004; cited in Bulling-Jamroga 2014 §4). The T_3 instance is
  small enough that this matters in theory but not in practice.

## Future work

- **Strategy Logic with Knowledge (SLK)** via the MCMAS-SLK
  extension (Čermák-Lomuscio-Mogavero-Murano 2014, in
  `papers/4 --- verification and model-checking/`). SLK is
  strictly more expressive than ATL — it includes named strategy
  variables, strategy quantification, and recursive equilibria.
  Reserved for richer T7.* variants in the P2 future-work
  section.
- **Memoryless vs. perfect-recall partial-obs**: this ADR locks
  in the memoryless setting (MCMAS `-atlk 2`). If a future P2
  result needs strategies that depend on observation history,
  Bulling-Jamroga 2014 §3.2 catalogues the decidable fragments.
- **Out-of-band fairness**: if a future variant of T7 requires
  fairness (e.g., "every agent eventually moves"), the encoding
  can add an ISPL `Fairness` block; the `-atlk 2 -fairness ...`
  combination is supported by MCMAS but not exercised by the
  T7 headline.

## Realised by

- `tests/integration/test_t7_atlk_emitter.py::test_atlk_formula_parses_under_semantics_2`
  — confirms `mcmas -atlk 2 <ispl>` parses the headline ATLK
  formula on the canonical T_3 CGS without error.
- `tests/integration/test_t7_atlk.py` (Stage 5, forthcoming) —
  asserts the headline T7 verdict (`⟨⟨{i}⟩⟩ F K_i evidence(p1, i)`
  is FALSE on T_3 for every `i`).
- `council/symbolic/verify/atl_witness.py` (Stage 5,
  forthcoming) — the wrapper that constructs the right ATLK
  formulas, invokes `mcmas -atlk 2`, and parses results.
- `docs/theory.md` §T7 (Stage 6, forthcoming) — the rewritten
  theorem statement that cites `-atlk 2` as the operative
  semantics.

## References

- `papers/4 --- verification and model-checking/Alur et al. 2002
  "Alternating-time Temporal Logic" (Journal of ACM).pdf` — the
  foundational ATL paper; Option A baseline.
- `papers/4 --- verification and model-checking/Busard et al.
  2013 "Reasoning about Strategies under Partial Observability
  and Fairness Constraints" (arXiv:1303.0793).pdf` — the
  technical reference for `-atlk 2` semantics; uniform-strategy
  semantics for ATL_ir under partial observability.
- `papers/4 --- verification and model-checking/Fagin et al.
  1995 "Reasoning About Knowledge" (MIT Press).pdf` — the
  canonical reference for `K_i` semantics (Chapter 2 + 3 cover
  the interpreted-system construction MCMAS implements).
- `papers/4 --- verification and model-checking/Lomuscio et al.
  2017 "MCMAS: an open-source model checker for the verification
  of multi-agent systems" (STTT).pdf` — MCMAS implementation
  paper; covers the ATLK encoding into BDD-based model checking.
- `papers/4 --- verification and model-checking/Cermák et al.
  2014 "MCMAS-SLK: a model checker for the verification of
  strategy logic specifications" (CAV).pdf` — the SLK extension
  flagged for future work; strictly more expressive than ATLK.
- MCMAS user manual (cover labelled v1.2.2; grammar + flag set
  match the installed v1.3.0 binary), §3.1 page 11 (the
  `-atlk` flag, `-uniform`, `-ufgroup`) + §3.4 page 30 (`~_i`
  definition) + §3.4 page 32 (Figure 3.12, verification algorithm
  for `⟨⟨Γ⟩⟩X φ`). Vendored at
  `papers/4 --- verification and model-checking/Lomuscio et al. n.d.
  "MCMAS v1.2.2 User Manual" (vendored from sail.doc.ic.ac.uk).pdf`;
  upstream: <https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf>
- `specs/t7-atlk-revision.md` §"Resolved decisions" Q1
  (`-atlk 2`) and Q2 (ATLK headline).
- `docs/adr/0020-deliberation-cgs-encoding.md` — the encoding
  decisions whose semantics this ADR fixes.
- `docs/adr/0008-calibrator-abc-location.md` through ADR-0019 —
  W3 ADR family; sibling rationale conventions.
