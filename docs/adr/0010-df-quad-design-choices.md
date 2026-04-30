# ADR-0010: DF-QuAD design choices on the W2 QBAF

## Status

Accepted.

## Date

2026-04-30

## Context

`council/symbolic/argue/semantics/df_quad.py` (W2/PR3) implements the
DF-QuAD gradual semantics from Rago, Toni, Aurisicchio, Baroni
(KR 2016, "Discontinuity-Free Decision Support with Quantitative
Argumentation Debates").

The paper defines DF-QuAD on a **QuAD framework** with three
disjoint argument sets (answer arguments, pro arguments, con arguments)
and two relations (R⁻ for attack, R⁺ for support) that are *unweighted*:
attacks and supports have no per-edge weight; all "weighting" comes from
each argument's base score. The framework is also assumed *acyclic*
(Atts ⊆ Args × Args is a DAG).

The CouncilAgent W2 QBAF (`council/symbolic/argue/baf.py`) generalises this:

1. **Edges are weighted.** `Attack.weight ∈ [0, 1]` (from
   `Challenge.confidence` via Patch C / ADR-0006); `Support.weight ∈ [0, 1]`
   (1.0 by default for Concede-derived edges per ADR-0009; calibratable in
   future work).
2. **Argument-kind taxonomy is implicit.** No three-set partition; instead
   `QBAF.proposals()` (PR1) filters non-withdrawn Propose-derived arguments
   as the answer set. Pro/con classification is derived dynamically from
   the edge structure.
3. **Withdrawn arguments are first-class.** `Argument.withdrawn=True` (set
   by Retract; ADR-0009). The DF-QuAD paper has no analogue; we must
   choose how withdrawal interacts with strength aggregation.
4. **Cycles are allowed in principle by the QBAF dataclass** (no
   acyclicity check in `__post_init__`). DF-QuAD as defined is undefined
   on cyclic graphs; the paper's strength-function recursion does not
   terminate.

Four design questions arise. The paper alone does not answer them; this
ADR records the choices and their justifications.

## Decision

**Q1 — Edge-weight handling.** In the recursive score computation, each
attacker/supporter contributes `weight(edge) × strength(source)` to the
aggregated attacker / supporter strength fed to ℱ. That is:

```
attacker_strengths = [att.weight * strength(att.source) for att in incoming_attacks(a)]
supporter_strengths = [sup.weight * strength(sup.source) for sup in incoming_supports(a)]
v_a = ℱ(attacker_strengths)
v_s = ℱ(supporter_strengths)
strength(a) = c(base_score(a), v_a, v_s)
```

When `Attack.weight = 1` for every edge, this reduces exactly to the
unweighted DF-QuAD from Rago 2016. When `Attack.weight < 1`, the attack's
contribution is dampened — a low-confidence challenge has less effect than
a high-confidence one, matching bible §6.3's "attack weight = LLM-emitted
certainty of the challenge" specification.

**Q2 — Withdrawn argument handling.** A withdrawn argument:

- **Has its own strength set to 0** in the result dict. The retract is a
  declared "I no longer assert this", not an "argue against".
- **Contributes 0 to other arguments' aggregations.** Withdrawn arguments
  do not attack or support anything in the strength computation, even if
  the edge structure formally points to/from them.

Implementation: a single recursion that returns 0 for `withdrawn=True`
arguments, before any further computation. Edges from withdrawn sources
contribute `weight × 0 = 0`.

**Q3 — Cycle policy.** DF-QuAD as defined in Rago 2016 is well-defined
only on acyclic graphs. On a cycle, the recursive score function does
not have a fixed point in general.

`evaluate` performs a topological sort on the directed graph
(attack-edges + support-edges, treating both as graph edges for the
purpose of acyclicity). If a cycle is found, it raises `ValueError(
"DF-QuAD requires an acyclic QBAF; cycle detected through {arg_ids}")`.

This is a deliberate restriction. PR4 (Quadratic Energy semantics, Potyka
2018) introduces *continuous dynamical systems* that converge to a unique
fixed point on cyclic graphs; that is the right tool for cyclic QBAFs.
DF-QuAD is the "sharp tool" for the acyclic case.

In the W2 deliberation pipeline, traces typically produce acyclic QBAFs:
Challenges and Concedes target prior moves (no forward references), so
the directed graph respects trace order. Cycles arise only from
non-monotone dialogue patterns (e.g., a Challenge later being Concede-d
by its target's author), and the build_qbaf in PR2 prevents these by
construction.

**Q4 — Preferred extension threshold.** The DF-QuAD paper (Corollary 1)
relates DF-QuAD strengths to grounded extension membership *only when the
graph is acyclic and base scores are uniform* (BS(a) = 1 for all answer
arguments). On the W2 QBAF — with non-uniform base scores derived from
Propose.confidence — there is no canonical mapping from strengths to
"acceptance".

`preferred_extension` returns:

```
{a.arg_id for a in baf.arguments if not a.withdrawn and strengths[a.arg_id] >= 0.5}
```

That is: **non-withdrawn arguments whose computed strength is at least
0.5 are in the preferred extension.** The threshold of 0.5 is the natural
neutral point on the [0, 1] scale; an argument whose strength has been
pushed below 0.5 by attackers is "rejected", and one pushed above 0.5 by
supporters (or with a high-enough base score) is "accepted".

This threshold is a configurable choice. PR3 ships it as a hardcoded
0.5; if a future workstream needs a calibratable threshold, the natural
extension is `DFQuADSemantics(extension_threshold=0.5)` — additive change.

## Alternatives Considered

### Q1 alt — Treat all edges as weight 1 (unweighted DF-QuAD)

Discard `Attack.weight` and `Support.weight` in the strength computation;
use only the source's strength.

**Rejected.** This silently drops the LLM-emitted certainty signal that
Patch C (ADR-0006) added precisely so that DF-QuAD could consume it. T5
(manipulability bound) becomes trivial because all edge weights are
constant. P2 reviewers will check that BAF construction faithfully
reflects challenge confidences; unweighted aggregation contradicts that.

### Q2 alt — Withdrawn arguments compute as if not withdrawn

Treat `withdrawn=True` as a UI flag only, with no semantic effect.

**Rejected.** This makes Retract a no-op in the BAF, removing all
information-theoretic content from the RETRACT speech-act. The
constitution makes Retract a typed Move with structural meaning; the
semantics must respect it. Bible §6.3 explicitly says "mark own_node as
withdrawn, recompute strengths" — recomputation must be visible in the
output.

### Q3 alt — Run DF-QuAD on cycles via an iterative fixed-point search

Iterate the strength recursion until convergence (or max iterations);
return the limit.

**Rejected for DF-QuAD.** The DF-QuAD recursion is non-monotone (the
combination function `c` is non-monotone in `v_a` and `v_s` when crossing
the v_a = v_s boundary). Fixed-point iteration is not guaranteed to
converge on cyclic graphs. The principled tool for cyclic settings is
Potyka 2018's continuous-dynamics QE framework, which is W2/PR4. Mixing
the two in PR3 would obscure the algorithmic identity of DF-QuAD and make
T4 (Borda recovery) harder to mechanise.

### Q4 alt — Preferred extension = arguments with strength > base score

Define accepted as "supporters net-positive": `strength(a) > base_score(a)`.

**Rejected.** This entangles the extension-membership question with the
priors. A high-base-score argument cannot be "accepted" unless its
supporters strictly outweigh its attackers (which sometimes is impossible
even when the argument is in fact strong). The 0.5 threshold is more
defensible because it matches the geometric centre of the [0, 1] strength
scale.

## Consequences

**Positive:**

- DF-QuAD reduces to the Rago 2016 algorithm exactly when edge weights
  are 1 and no arguments are withdrawn — the W2 generalisation is a
  strict superset.
- Withdrawn arguments are "soft retraction": their content remains in the
  graph for visualisation purposes (the visualiser, PR7, will render
  them dimmed) but their semantic effect is removed.
- The cycle policy (raise ValueError) is debuggable; downstream callers
  can catch it and re-route to QE (PR4) when continuous dynamics are
  needed.
- The 0.5 extension threshold is tunable in future PRs without breaking
  existing clients.

**Neutral:**

- T4 (Borda recovery) is mechanised against the *unweighted* edge case
  (all attack/support weights = 1) so the result reduces to standard
  Borda. The full weighted regime adds richness for P2 (AAAI 2027) but
  is not a T4 requirement.

**Negative:**

- DF-QuAD's cycle restriction means certain dialogue patterns
  (mutual-Concede chains) cannot be evaluated without falling back to
  PR4's QE semantics. Documented in `evaluate`'s docstring; W2's
  ArgumentationAggregator (PR6) catches the ValueError and falls back
  to a no-edge re-evaluation in that path.

## References

- `council/symbolic/argue/semantics/df_quad.py` — implementation (W2/PR3)
- `council/symbolic/argue/baf.py` — QBAF dataclasses (W2/PR1)
- `papers/3 --- argumentation/Rago et al. 2016 ... (KR).pdf` — Definition
  1 (ℱ), Equations 19/20 (combination function c), Theorem 1
  (discontinuity-freeness), Corollary 1 (AA-relationship)
- `papers/3 --- argumentation/Baroni et al. 2018 ... (AAAI).pdf` —
  property catalogue against which Slice B's monotonicity + continuity
  tests are calibrated
- `COUNCIL_NS_PLAN.md §6.3` — bible specification of the L2 layer
- `docs/adr/0006-challenge-confidence.md` — Challenge.confidence field
  this semantics consumes via Attack.weight
- `docs/adr/0009-challenge-concede-as-arguments.md` — withdrawn-argument
  semantics this ADR builds on
- `specs/w2-argumentation.md §"PR sequence"` PR3 — DF-QuAD + T4
