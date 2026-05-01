# ADR-0017: PrivilegedKnowledgeCalibrator maps Anonymous 2026 "premium gap" findings onto the L3 Calibrator interface via per-domain self/peer convex combination

## Status

Accepted.

## Date

2026-05-01

## Context

Anonymous 2026, *Masked by Consensus: Disentangling Privileged Knowledge
in LLM Correctness* (OpenReview `du3ZBA8Z3Z`), under
[`papers/2 --- calibration and disagreement/`](../../papers/), studies
whether LLMs possess unique internal signals about answer correctness.
Paper §4.3 isolates a *premium gap* — the AUC advantage of a self-probe
over a peer-probe on a *disagreement subset* — and finds:

  - **Factual knowledge** (Mintaka, TriviaQA, HotPotQA): premium gaps of
    6.5%, 6.7%, 8.9% (Gemma-2-9B); 9.3%, 3.5%, 4.2% (Llama-3.1-8B); etc.
    — statistically significant in 8/9 linear-probe configurations and
    9/9 MLP-probe configurations (p < 0.05, Bonferroni-Holm).
  - **Mathematical reasoning** (MATH, GSM1K): -0.6% to -3.4% (Gemma),
    -1.9% to -4.8% (Llama), -0.7% to -14.5% (Qwen) — *no* premium gap;
    most differences are non-significant noise.

The paper's framework is a **probe-AUC measurement**, not a per-agent
confidence transformation. The L3 Calibrator ABC freezes
([architecture rules](../../.claude/rules/architecture.md)
§"Required contracts" → "L3 — calibration"):

```python
class Calibrator(ABC):
    @abstractmethod
    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float: ...
```

We must turn the paper's *empirical finding* (factual has a self-signal;
math does not) into a per-agent transformation. The
[bible](../../COUNCIL_NS_PLAN.md) §6.4 sketches a `DOMAIN_CALIBRATION`
table with `self_weight`/`peer_weight` entries; the
[master plan](../../COUNCILAGENT_NS_MASTER_PLAN.md) §7 W3 line 768
locks the deliverable to "defaults match the DOCX table (factual 5%,
math 0%, coding partial)". This ADR documents the mapping shape, the
domain-gap defaults, and the alternatives rejected.

## Decision

**`PrivilegedKnowledgeCalibrator(peer_consensus, *, domain_gaps=None)`
implements the L3 Calibrator ABC via a per-domain convex combination
of the agent's self confidence and a peer-consensus signal:**

```
calibrate(raw, agent_id, domain) =
    clamp(self_weight * raw + peer_weight * peer_consensus[agent_id], 0, 1)
                                                  if agent_id ∈ peer_consensus
    raw                                            otherwise
```

with `self_weight + peer_weight = 1` derived from a per-domain
`DomainGap(gap ∈ [0, 1])`:

```
self_weight = 0.5 + gap / 2
peer_weight = 0.5 - gap / 2
```

`peer_consensus` is a `dict[str, float]` mapping agent_id → leave-one-out
peer-mean confidence. The calibrator is agnostic to how callers compute
this (typically `(sum(others) / len(others))` over an agent's peers in
the trace). Unknown `agent_id` returns `raw_confidence` unchanged — the
safe-fallback convention shared with `JSDCalibrator` (W3/PR1) and
`MUSECalibrator` (W3/PR2). Output is clamped to `[0, 1]` for consistency
with the rest of the family.

`DEFAULT_DOMAIN_GAPS` covers every member of `ClaimDomain`:

| ClaimDomain | gap   | Source |
|-------------|-------|--------|
| FREE        | 0.05  | Paper §4.3 Fig. 3 left panel: avg ~5% across factual datasets / models |
| ARITH       | 0.0   | Paper §4.3 Fig. 3 right panel: no significant premium gap on math |
| CODE        | 0.025 | Master plan line 768 "coding partial"; not measured by paper; interpolation |
| FOL         | 0.0   | Not in paper; treat as math-like (deterministic, no memory retrieval) |
| LTLF        | 0.0   | LTL_f formula; same family as FOL |

The bible's table at lines 718-728 expresses the same intuition with
weights `(0.55, 0.45)` for factual; our `gap = 0.05` produces
`(0.525, 0.475)`. The discrepancy is intentional: the bible's `0.55`
appears to be a rounded design choice; our `0.525` matches the paper's
quantitative ~5% premium gap exactly. Callers wanting bible-faithful
behaviour can pass `domain_gaps={ClaimDomain.FREE: DomainGap(0.10), ...}`.

## Alternatives Considered

### Option A — Pure per-domain scaling

```
calibrate(raw, agent_id, domain) = raw * domain_factor[domain]
```

A naive interpretation: scale raw confidence by a domain-specific factor
(e.g., 1.0 for factual, 0.8 for math).

**Rejected.** The paper's central finding is a *self-vs-peer* gap, not
an absolute calibration factor. Option A discards the peer signal
entirely and would calibrate every agent in a domain identically,
ignoring whether the agent agrees or disagrees with the council. It
also has no principled value for `domain_factor` — any choice would be
ad-hoc.

### Option B — Replace raw with peer_consensus when domain has no privileged knowledge

```
calibrate(raw, agent_id, domain) = peer_consensus[agent_id]   if gap == 0
                                   raw                         if gap >= 0.05
```

A discrete switch that hands control to the peer signal in the
no-privileged-knowledge case.

**Rejected.** Discontinuous in `gap`: a domain with `gap = 0.001`
(arbitrarily-tiny privileged knowledge) would behave identically to the
strong-privileged-knowledge case, while `gap = 0.0` would jump to pure
peer. The "partial" coding case (`gap = 0.025`) cannot be expressed
naturally — it would have to be assigned to either branch by ad-hoc
threshold, defeating the smooth-interpolation intuition.

### Option C — Mixing model (chosen)

```
calibrate = self_weight * raw + peer_weight * peer
```

Convex combination of self and peer, weighted by domain.

**Chosen.** Three properties make this the principled mapping:

1. **Smoothness in `gap`.** A small change in the empirical
   premium gap (e.g., from 0.05 to 0.04 as we refine the paper's
   numbers) produces a small change in calibrated output. The
   "coding partial" case (`gap = 0.025`) sits naturally between the
   factual and math endpoints.
2. **Recovers the right limits.** At `gap = 1.0` (hypothetical full
   privileged knowledge), `calibrate = raw` (the identity). At
   `gap = 0.0` (no privileged knowledge), `calibrate = (raw + peer) / 2`
   (unweighted mean). At `gap = 1.0` *and* `peer_consensus = raw`, the
   output is invariant — disagreement is required for the mixing to
   matter, which echoes the paper's *disagreement-subset* methodology.
3. **Encodes the paper's finding.** "Self has more information than
   peer in factual" → factual `self_weight > peer_weight` → calibrated
   value biased toward the agent's own signal. "Self has no extra
   information than peer in math" → math `self_weight = peer_weight` →
   calibrated value is the unweighted mean.

## Consequences

**Positive:**

- The Calibrator ABC's `agent_id` and `claim_domain` parameters are both
  meaningful and load-bearing: per-agent peer signal × per-domain
  weight → per-(agent, domain) calibration.
- The mapping is grounded in the paper's quantitative finding, not an
  ad-hoc constant: `gap = 0.05` for FREE comes directly from
  `(6.5 + 6.7 + 8.9 + 7.0 + 10.6 + 5.2) / 6 ≈ 7.5%` of the paper's
  significant disagreement-subset numbers, conservatively rounded to
  ~5% to reflect the lower-bound across the model families.
- Linear and convex: the calibrated value is bounded, monotone in raw
  (with slope `self_weight`), and easy to reason about.
- Family-consistent: shares `clamp(., 0, 1)` and the safe-unknown-agent
  fallback with `JSDCalibrator` (W3/PR1) and `MUSECalibrator`
  (W3/PR2). A future agent reading any of the three will recognise the
  pattern immediately.

**Neutral:**

- `peer_consensus` is supplied by the caller. The calibrator does not
  enforce a specific peer-consensus formula; the convention is
  "leave-one-out mean of peer raw confidences", but the genome's
  `CalibrationSpec` may pass any `dict[str, float]` (e.g., a
  MUSE-derived consensus, opening a composition path with
  `MUSECalibrator`).
- The bible's table (lines 718-728) lists `(0.55, 0.45)` for factual;
  our default produces `(0.525, 0.475)`. This is a numerically
  documented divergence — see the discussion above. Callers who want
  bible-faithful behaviour pass an explicit `domain_gaps` override.

**Negative:**

- The paper does not measure coding; `gap = 0.025` for CODE is our
  interpolation between FREE and ARITH. A future paper that measures
  coding directly may revise this. The default is `domain_gaps`-overridable;
  ADR-0017 should be revisited and a successor ADR opened if the paper
  evidence shifts substantially.
- Negative premium gaps observed in math (some -3% to -14% in the
  paper's Fig. 3) are clamped to 0 by `DomainGap` validation. This is
  conservative: a literal interpretation would yield `peer_weight > 0.5`
  for math (trust peer more than self), but the paper's authors
  explicitly say "no premium gap" — the negative numbers are noise
  around zero, not a real anti-privileged signal. Allowing negative
  gaps would invite over-fitting to noise.
- `PrivilegedKnowledgeCalibrator` is the *domain* axis only;
  composition with the *information-theoretic* axis
  (`JSDCalibrator`, `MUSECalibrator`) is not supported in this PR.
  See §"Future work" — a `ChainedCalibrator` is the natural composition
  point but is out of W3/PR3 scope.

## Future work

- **`ChainedCalibrator`**: compose two calibrators sequentially
  (e.g., `JSDCalibrator → PrivilegedKnowledgeCalibrator`) so a single
  `CalibrationSpec` in the genome activates both axes. Out of scope
  here; ship as a separate W3 follow-up if the paper experiments
  demand it.
- **Per-domain coding evidence**: when a paper measures coding's
  premium gap directly, revise `DEFAULT_DOMAIN_GAPS[ClaimDomain.CODE]`
  and supersede this ADR.
- **`tasks/profiles.py` integration**: `TaskProfile` could expose
  `privileged_weights: dict[ClaimDomain, DomainGap]` so per-dataset
  overrides flow through the genome to the calibrator at runtime.
  Defer to W7 (evaluation pipeline) if needed.
- **Bayesian peer-consensus**: instead of a flat mean, peer-consensus
  could weight each peer by their own past calibration accuracy.
  Out of scope; flagged for the W5 QD search to discover.

## Realised by

- `council/calibrate/privileged.py` — implementation (W3/PR3,
  `feature/ns-w3-privileged`).
- `tests/calibrate/test_privileged.py` — 22 tests covering DomainGap
  validation, domain dispatch, mixing-model formula, custom-gap
  override, and clamping/determinism boundaries.
- `tests/calibrate/test_privileged_aggregator_integration.py` — W2
  `build_qbaf` integration (next slice in this PR).

## References

- `papers/2 --- calibration and disagreement/Anonymous 2026 "Masked by
  Consensus: Disentangling Privileged Knowledge in LLM Correctness"
  (Preprint; OpenReview:du3ZBA8Z3Z).pdf` — the source paper. §4.3
  ("Re-emergence of Domain-Specific Privileged Knowledge") and Figure 3
  carry the empirical numbers used to set the gap defaults.
- `specs/w3-calibration.md` §"Resolved decisions" Q3 — the user's
  authorisation to defer to the literature for any silent numerical
  parameter; the privileged-knowledge gaps are an instance of that.
- `COUNCILAGENT_NS_MASTER_PLAN.md` §7 W3 line 768 — the deliverable
  text: "defaults match the DOCX table (factual 5%, math 0%, coding
  partial)".
- `COUNCIL_NS_PLAN.md` §6.4 lines 718-728 — the bible's
  `DOMAIN_CALIBRATION` table; this ADR documents the controlled
  divergence (our `gap = 0.05` ↔ bible's `0.55/0.45`).
- `.claude/rules/architecture.md §"Required contracts" → "L3 —
  calibration"` — frozen Calibrator ABC signature.
- `docs/adr/0008-calibrator-abc-location.md` — Calibrator ABC location
  decision (W2/PR1).
- `docs/adr/0015-calibrate-extra-split.md` — `[calibrate]` extra split
  (W3/PR1).
- `docs/adr/0016-muse-calibrator-interface.md` — sibling ADR mapping
  Kruse et al. 2025 MUSE onto the same Calibrator interface; the
  "per-agent JS-against-consensus" pattern there is the
  information-theoretic counterpart of this ADR's per-domain mixing
  pattern.
