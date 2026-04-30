# ADR-0012: Strategic-Coupled gradual semantics — DF-QuAD ⊕ ATL

## Status

Accepted.

## Date

2026-04-30

## Context

W2/PR5 ships **Strategic-Coupled gradual semantics**, the headline novelty
for P2 (AAAI 2027). The bible §6.3 (`COUNCIL_NS_PLAN.md`) names this
"Strategic gradual semantics" and describes it as "DF-QuAD ⊕ ATL coalition
reasoning".

The motivating goal is **T7** (master plan §10): construct a gradual
semantics that satisfies T3's CTLK invariant. Recall T3
(`docs/theory.md`):

> There exists a CTLK invariant — `G(consensus → ∃i. K_i evidenceFor(consensus))`
> — that no purely vote-counting aggregator satisfies.

The 3-agent unanimous-vote-without-evidence trace is the canonical
counterexample. Plain DF-QuAD (W2/PR3) accepts that trace's "X is true"
into the preferred extension because all three Proposes have non-trivial
base scores and there are no attackers — pure popularity wins. T7 demands
a semantics that *rejects* X in this scenario because no agent has
provided evidence.

The bible suggests "DF-QuAD ⊕ ATL" — couple the strength computation with
ATL coalition reasoning (Alur, Henzinger, Kupferman, JACM 2002). ATL's
operator `<<A>> φ` reads "the coalition A has a strategy to ensure φ".
The minimal ATL fragment we need for T3's invariant is the one-coalition
existential: `<<{i}>> X witness_evidence(arg)` for some agent i. On a
finite trace, this reduces to *direct observation*: did agent i's moves
witness evidence for the argument?

Three design questions arise.

## Decision

**Q1 — Where does the ATL fragment live?** Inline in
`council/symbolic/argue/coupled_atl.py`. The architecture rules forbid
`argue/ → verify/` imports; we do **not** reach into the W1 spine for ATL
machinery. The ATL fragment we need is mathematically trivial on finite
traces (existential check over `Move`s), so a self-contained ~30-line
helper module is appropriate.

The W2 ATL fragment exposes one function:

```python
def evidence_backed_arg_ids(trace: Trace) -> frozenset[str]:
    """Returns the set of arg_ids witnessed by at least one agent's evidence.

    For T7's `<<{i}>> X witness_evidence(arg)` ATL fragment: an arg is
    backed iff there exists an agent i and a Move m by i such that m's
    content materially corresponds to the argument and m's evidence is
    non-empty.
    """
```

Concretely: scan the trace once. For every `Propose` move whose
`Claim.evidence != ()`, add its `move_id` to the result. For every `Vote`
move whose `Claim.evidence != ()`, add the matching Propose's `move_id`
(found by claim-surface equality, mirroring `build_qbaf`'s vote-boost
matching rule). `Concede` and `Challenge` are not currently tracked as
witnesses; their evidence story is deferred to W6 / future ATL extension.

**Q2 — Where does Strategic-Coupled live in the API?** As a **wrapper
semantics** in `council/symbolic/argue/semantics/coupled.py`, with the
signature:

```python
class StrategicCoupledSemantics(GradualSemantics):
    def __init__(
        self,
        base: GradualSemantics = DFQuADSemantics(),
        evidence_backed: frozenset[str] = frozenset(),
        alpha: float = 0.5,
        consensus_threshold: float = 0.5,
    ) -> None:
        ...
```

The base semantics is **injected** (default DFQuAD). The
`evidence_backed: frozenset[str]` is **pre-computed** and passed at
construction; this preserves the GradualSemantics ABC signature
`evaluate(baf) → dict` exactly. The aggregator (PR6) is responsible for
calling `evidence_backed_arg_ids(trace)` and threading the result into
StrategicCoupledSemantics — clean separation between trace-aware
construction (PR6) and BAF-only evaluation (PR5).

**Q3 — What does coupling do operationally?** The semantics:

1. Computes base strengths via the underlying `base.evaluate(baf)`.
2. For each argument with strength ≥ `consensus_threshold` AND
   `arg_id ∉ evidence_backed`: demote `strength *= alpha`.
3. Returns adjusted strengths.

Default `alpha = 0.5` and `consensus_threshold = 0.5` (matches ADR-0010
Q4). With these defaults, an argument that reaches consensus (≥ 0.5)
but has no evidence backing falls to ≤ 0.25, dropping out of the preferred
extension.

The reduction to DF-QuAD: on traces where every consensus-strength
argument has evidence backing, demotion never triggers, and the result
equals the base semantics. The semantics is a *strict generalization*
of DF-QuAD that disagrees only when T3's invariant would be violated.

## Alternatives Considered

### Q1 alt — Reach into W1's `verify/` for full ATL evaluation

Add an approved exception `argue/coupled.py → symbolic/verify/...` and
call SPOT/MCMAS for full ATL semantics.

**Rejected.** SPOT supports LTL and ω-automata, not ATL directly. MCMAS
supports ATL but is an external binary — using it at evaluate-time would
make the headline aggregator depend on a subprocess (Constitution §8
violation: zero-framework path must work without optional extras). The
minimal one-coalition existential we need is observable on a finite
Trace; a self-contained Python implementation is correct and far simpler.

If a future workstream needs richer ATL (e.g., multi-coalition
reachability `<<C>> F φ`), it can either extend the inline fragment or
add an offline MCMAS verification step (similar to the existing
`tests/integration/test_mcmas_t3_counterexample.py` pattern from W1/T3).

### Q2 alt — Add `Argument.evidence: tuple[str, ...]` to QBAF

Modify `council/symbolic/argue/baf.py` to carry evidence per Argument;
have `build_qbaf` populate it; have semantics inspect it directly.

**Rejected.** This requires a Patch on the QBAF dataclass after PR1
froze its shape. It also bleeds W6 / W3 information (evidence atoms,
calibrated witness scores) into the L2 graph data structure prematurely.
The current design — separate `evidence_backed: frozenset[str]` parameter
— keeps the QBAF lean and lets future workstreams use the same hook
without touching PR1's dataclass.

### Q2 alt — Pass the Trace to GradualSemantics.evaluate

Change the ABC to `evaluate(baf, trace=None)`.

**Rejected.** Changes the W2/PR1 frozen ABC signature, breaking forward
contract. The construction-time `frozenset[str]` parameter is
type-checkable, immutable, and doesn't violate the BAF-only evaluation
contract.

### Q3 alt — Demote by strict zero-out (alpha = 0) instead of α < 1

`evidence_backed = ∅` ⟹ strength = 0 for any consensus-reaching
argument.

**Rejected.** Too aggressive: this loses the gradual nature of DF-QuAD
when T3's invariant is *partially* violated (e.g., 4 out of 5 supporters
have evidence). With `alpha = 0.5`, the demoted strength still preserves
ranking among demoted arguments. With `alpha = 0`, all evidence-less
arguments collapse to a single point, losing comparative information.

The default `alpha = 0.5` is configurable: a stricter caller can pass
`alpha = 0.0` for hard rejection.

## Consequences

**Positive:**

- T7 is mechanizable: build the T3 counterexample, run DF-QuAD vs
  Strategic-Coupled, observe the divergence on the consensus argument.
- The semantics composes cleanly with W3 (calibrators), W6 (ILP-mined
  evidence rules), and the W7 demo (visualisers can render demoted
  arguments dimmed).
- The default `evidence_backed = frozenset()` plus `consensus_threshold =
  0.5` makes the semantics safe to instantiate without a Trace — it
  behaves as "demote everything above 0.5", which is overly aggressive
  but never crashes. The aggregator (PR6) always passes the real
  `evidence_backed` set computed from the trace.
- Reduces to base DF-QuAD on traces with full evidence backing —
  backward-compatible.

**Neutral:**

- The one-coalition existential is the simplest ATL fragment that
  satisfies T7. Multi-coalition strategic reasoning (e.g., `<<{a, b}>>
  G φ`) is a stretch goal for future work and would mostly affect W6's
  ILP rule mining, not the W2 aggregator.

**Negative:**

- The `evidence_backed: frozenset[str]` parameter requires the aggregator
  (PR6) to know how to compute it from the trace. PR6 will use the
  `evidence_backed_arg_ids(trace)` helper — a small added responsibility
  on the aggregator's side. Documented in the spec.

## References

- `council/symbolic/argue/coupled_atl.py` — ATL fragment (W2/PR5)
- `council/symbolic/argue/semantics/coupled.py` — semantics (W2/PR5)
- `papers/4 --- verification and model-checking/Alur et al. 2002 ... (JACM).pdf` —
  ATL syntax/semantics; coalition operators `<<A>>` and the strategic
  fragment we ground our design in
- `docs/theory.md §T3` — the no-go theorem this semantics defeats
- `docs/theory.md §T7` — the recovery theorem this semantics provides
  (mechanised in PR5/Slice B)
- `docs/adr/0010-df-quad-design-choices.md` — DF-QuAD's threshold
  conventions, reused here
- `COUNCIL_NS_PLAN.md §6.3` — bible specification of L2
- `COUNCILAGENT_NS_MASTER_PLAN.md §10 T7` — theorem statement
