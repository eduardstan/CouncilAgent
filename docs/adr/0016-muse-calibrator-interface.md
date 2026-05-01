# ADR-0016: MUSECalibrator maps Kruse et al. 2025 MUSE outputs onto the L3 Calibrator interface via per-agent JS²-against-consensus

## Status

Accepted.

## Date

2026-05-01

## Context

Kruse et al. 2025, *Simple Yet Effective: An Information-Theoretic
Approach to Multi-LLM Uncertainty Quantification* (EMNLP / arXiv
2507.07236; under [`papers/2 --- calibration and disagreement/`](../../papers/)),
introduces **MUSE — Multi-LLM Uncertainty via Subset Ensembles**. MUSE
takes a set of per-LLM predictive distributions and returns:

  - a *selected subset* `S` of LLMs,
  - the subset-mean prediction `p̂` (an aggregated probability),
  - and a total uncertainty scalar `u_total = u_epis + β · u_alea`.

The paper's Algorithm 1 (Greedy) and Algorithm 2 (Conservative) are
**subset-selection-and-aggregation** algorithms. They do not directly
produce a *per-agent calibrated confidence* — the artefact the
`COUNCILAGENT_NS_MASTER_PLAN.md §7 W3` deliverable demands and that
`.claude/rules/architecture.md §"Required contracts" → "L3 — calibration"`
freezes:

```python
class Calibrator(ABC):
    @abstractmethod
    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float: ...
```

The W3/PR2 ship requires a `MUSECalibrator(Calibrator)` whose
`calibrate(raw, agent_id, domain)` returns a meaningful per-agent
calibrated value. **How do we expose MUSE's subset-level outputs
through a per-agent interface?** This ADR documents the chosen mapping
and the alternatives rejected, so future agents and reviewers
understand why MUSECalibrator does what it does.

The constraints are:

- The Calibrator signature is frozen (architecture rules).
- The mapping must respect Kruse §3.2's thesis: *"disagreement among
  LLM predictive distributions signals epistemic uncertainty, while
  consensus indicates more reliable generalization."*
- The mapping must reduce cleanly to `JSDCalibrator` (W3/PR1) in the
  edge case where MUSE selects all agents (no subset rejection).
- Domain-agnostic: per-domain refinement is the
  `PrivilegedKnowledgeCalibrator` (W3/PR3) territory; MUSECalibrator
  must not pre-empt it.

## Decision

**`MUSECalibrator(distributions, agent_ids, ...)` precomputes the
`muse_greedy` result (selected subset `S` plus the subset-mean
consensus `p̄_S`), and stores `JS(p_i || p̄_S)²` for every agent_id
known at construction time. The `calibrate(raw, agent_id, domain)`
method returns:**

```
calibrate(raw, agent_id, domain) =
    clamp(raw * (1 - JS(p_agent_id || p̄_S)²), 0, 1)
                                   if agent_id ∈ known
    raw                            otherwise
```

The construction-time `muse_greedy` call performs Algorithm 1 of the
paper (Greedy variant); Algorithm 2 (Conservative) is deferred — see
§"Future work". The unknown-agent fallback is the safe behaviour for
callers who pass extra agents post-hoc; it is documented in the
docstring and tested in `tests/calibrate/test_muse.py`.

Default hyperparameters follow the paper's §4 + Figure 2 main-results
setting:

  - `β = 1.0` (aleatoric weight)
  - `ε_tol = 0.04` (subset-extension tolerance)
  - `m_min = 2` (minimum subset size; see §"Consequences" for why this
    differs from the paper's `m_min = 20`)

For multi-class supports (`k ≥ 3`), the algorithm's confidence sort
generalises from the paper's binary-only `c_i = |p_yes - 0.5|` to:

```
c_i = max(p_i) - 1/k
```

over the union support of size `k`. At `k = 2` this reduces to
`|p_yes - 0.5|` because `max(p) ∈ {p_yes, 1 - p_yes}`. The paper does
not address multi-class; this generalisation is ours and is flagged in
the module docstring.

## Alternatives Considered

### Option A — Binary subset flag

```
calibrate(raw, agent_id, domain) = raw   if agent_id ∈ S
                                   0     otherwise
```

A naive interpretation that treats MUSE's subset selection as a hard
in/out signal.

**Rejected.** Two reasons:

1. **Information loss.** MUSE excludes an agent because their
   prediction increases epistemic uncertainty past `ε_tol`, but the
   *amount* by which it does so carries information. An agent who is
   only marginally above the threshold is meaningfully different from
   an agent who diverges sharply; Option A erases that distinction.
2. **Contradicts the paper's thesis.** Kruse §3.2 frames MUSE as a
   continuous-uncertainty quantification method ("JSD offers a
   symmetric and bounded measure of divergence between probability
   distributions, making it well-suited for comparing predictions
   across multiple LLMs"). Reducing the output to a binary flag wastes
   the information-theoretic signal MUSE was designed to surface.

### Option B — Scalar `u_total` penalty

```
calibrate(raw, agent_id, domain) = clamp(raw * (1 - u_total), 0, 1)
```

Apply MUSE's total-uncertainty scalar as a uniform penalty across all
agents.

**Rejected for two reasons.** First, `u_total` is a property of the
subset `S`, not of any individual agent — it would calibrate every
agent identically. The Calibrator ABC's `agent_id` parameter would be
unused, which is a smell: a per-agent contract that doesn't depend on
the agent. Second, `u_total = u_epis + β · u_alea` mixes epistemic and
aleatoric uncertainty; the aleatoric term is an *intrinsic* property
of the predictions (binary entropy) and does not vary with the agent
in the way calibration ought to.

### Option C — No-op for excluded agents

```
calibrate(raw, agent_id, domain) = clamp(raw * (1 - JS²), 0, 1)
                                   if agent_id ∈ S
                                   raw   otherwise
```

Calibrate only included agents; pass excluded agents through unchanged.

**Rejected.** The signal is the wrong way around: an agent excluded by
MUSE has a *higher* JS distance from the subset consensus than an
included agent (that is *why* they were excluded). Letting them pass
through unchanged means we apply the lightest possible calibration to
the *least* trustworthy agents. Option D below is the inversion that
makes the right thing happen.

### Option D (chosen) — Per-agent JS²-against-consensus

```
calibrate(raw, agent_id, domain) = clamp(raw * (1 - JS(p_i || p̄_S)²), 0, 1)
                                   for every known agent_id
```

Score *every* known agent continuously by their JS distance to the
MUSE-selected subset's consensus. Excluded agents naturally see higher
penalties because that is precisely the geometric property that
caused MUSE to exclude them.

This option satisfies all three constraints stated in §"Context":

- **Frozen Calibrator signature** — yes, no signature change required.
- **Aligns with Kruse §3.2** — JS-distance-to-consensus is a direct
  per-agent realisation of the paper's epistemic-uncertainty thesis.
- **Reduces to JSDCalibrator at degenerate MUSE** — when `eps_tol` is
  large enough that MUSE selects all agents (no subset rejection),
  `p̄_S` equals the full subset mean, and the per-agent penalty
  reduces to the same JS²-against-mean signal that JSDCalibrator
  computes globally. At that limit MUSECalibrator is a per-agent
  refinement of JSDCalibrator: same physics, finer grain.

## Consequences

**Positive:**

- The Calibrator ABC's `agent_id` parameter is meaningful: different
  agents receive different calibrated values, depending on how far
  their predictions sit from the MUSE-trusted consensus.
- The mapping is principled rather than ad-hoc: it is the per-agent
  realisation of the same JSD signal that motivates the paper.
- `MUSECalibrator` and `JSDCalibrator` (W3/PR1) become a single family
  parameterised by the consensus they score against (full-set mean
  vs. MUSE-selected mean). Future calibrators in this family
  (`PrivilegedKnowledgeCalibrator`, PR3) extend cleanly.
- Clamping to `[0, 1]` preserves the Confidence-value invariants
  encoded in `council/context.py`.

**Neutral:**

- `selected_agent_ids` is exposed as a public property on
  `MUSECalibrator` for downstream metadata (Provenance Receipt §11
  may surface it in the future). This does not affect the Calibrator
  contract — clients that only call `calibrate(...)` see no
  difference.
- The default `m_min = 2` differs from the paper's `m_min = 20`. The
  paper uses 20 because their experimental ensembles are at the
  *dataset scale* (50+ stochastic decoding samples per LLM); our
  council-scale councils run with 3–5 agents per deliberation, so a
  20-agent minimum would always trigger full inclusion and silently
  defeat MUSE's diversity-aware selection. The module docstring and
  this ADR explain the choice; users who want paper-faithful behaviour
  pass `m_min=20` explicitly.

**Negative:**

- The mapping depends on a non-trivial structural fact (every agent
  is scored against the *same* consensus `p̄_S`, regardless of their
  inclusion in `S`). A future reader who has only skimmed the paper
  may expect Option A or Option C and be surprised. This ADR exists
  precisely to inoculate against that.
- `MUSECalibrator` must precompute `JS²` for every supplied
  `agent_id` at construction. For very large councils this is `O(n)`
  scipy calls; in practice negligible (n ≤ ~10) but worth flagging
  before any future scale-up that would push the council into
  paper-scale territory.

## Future work

- **MUSE-Conservative (Algorithm 2)**: defer to a follow-up PR
  (`feature/ns-w3-muse-conservative`). When implemented, ship it as a
  separate `MUSEConservativeCalibrator(Calibrator)` rather than a
  parameter on `MUSECalibrator`, to keep the W3/PR2 semantics
  frozen for any downstream user who has already wired
  `MUSECalibrator` into their genome's `CalibrationSpec`.
- **Per-agent `u_alea` and `u_epis` accessors**: useful for the
  Provenance Receipt (Constitution §11) once we wire MUSE outputs into
  `ProvenanceReceipt.calibration_metadata`. Out of scope for PR2.
- **Real-LLM ECE reproduction**: the paper's TruthfulQA / EHRShot
  numbers (Table 1, Table 6) require the full LLM-pipeline + dataset.
  Out of scope for PR2 unit tests; deferred to PR4's gated integration
  test infrastructure (see `specs/w3-calibration.md` Resolved
  decisions Q3 — OpenRouter SLM slate).

## Realised by

- `council/calibrate/muse.py` — the implementation (W3/PR2,
  `feature/ns-w3-muse`).
- `tests/calibrate/test_muse.py` — 24 tests covering the helper, the
  calibrator, multi-class generalisation, and validation.
- `tests/calibrate/test_muse_aggregator_integration.py` — W2
  `build_qbaf` integration (next slice in this PR).

## References

- `papers/2 --- calibration and disagreement/Kruse et al. 2025
  "Simple Yet Effective: An Information-Theoretic Approach to
  Multi-LLM Uncertainty Quantification" (EMNLP; arXiv:2507.07236).pdf`
  — the source paper. Algorithm 1 is on p. 30494; Algorithm 2 in
  Appendix A.1 (p. 30500).
- `specs/w3-calibration.md` §"Resolved decisions" Q2 — user
  authorisation to reproduce the paper's algorithm exactly.
- `COUNCILAGENT_NS_MASTER_PLAN.md §7 W3` — the workstream definition
  that names `MUSECalibrator` as a deliverable.
- `.claude/rules/architecture.md §"Required contracts" → "L3 —
  calibration"` — the frozen Calibrator ABC signature.
- `docs/adr/0008-calibrator-abc-location.md` — Calibrator ABC location
  decision (W2/PR1).
- `docs/adr/0015-calibrate-extra-split.md` — `[calibrate]` extra split
  (W3/PR1).
