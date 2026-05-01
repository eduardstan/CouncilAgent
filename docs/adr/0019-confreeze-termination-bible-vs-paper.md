# ADR-0019: ConFreezeTermination ships the bible's multi-round JSD-streak interpretation, not the paper's round-0 unanimity gate

## Status

Accepted.

## Date

2026-05-01

## Context

W3/PR5 closes the L3 calibrated-disagreement layer with two
termination strategies:

- `JSDDivergenceTermination(threshold=0.05)`
- `ConFreezeTermination(window=5, threshold=0.05, confidence_floor=0.0)`

`JSDDivergenceTermination` is unambiguous: stop when inter-round JSD
falls below a threshold. `ConFreezeTermination` is not. Two distinct
interpretations exist in our source material:

1. **Anonymous 2026, *ConFreeze: Selective Multi-Model Debate through
   Consensus Freezing*** (OpenReview ``PrqXuAS4BZ``; under
   [`papers/2 --- calibration and disagreement/`](../../papers/)). The
   paper proposes a **selective execution gate** triggered by
   *unanimity in round 0*: each model independently produces a
   prediction, a unanimity flag is set if all predictions agree, and
   if true the consensus is "frozen" (subsequent rounds skipped). The
   paper's algorithm is *single-round* — it never looks past the
   initial vote.

2. **The bible** (``COUNCIL_NS_PLAN.md`` §6.4 lines 731-742) sketches
   ConFreeze as a different signal:

       class ConFreezeTermination(TerminationStrategy):
           """Stop when JSD < freeze_threshold AND confidence > confidence_floor."""

   This is a *continuous-uncertainty* condition over JSD and a
   confidence floor — closer in spirit to a multi-round termination
   strategy than a single-round selective-execution gate.

The user-resolved decisions in `specs/w3-calibration.md` cement the
bible's framing:

- **Q4** (default ``window=5``) — explicitly assumes a multi-round
  interpretation (a single-round gate has no "window" parameter).
- **Q5** (do not split PR5) — both `JSDDivergenceTermination` and
  `ConFreezeTermination` ship together as the same kind of
  inter-round signal.

We must pick one interpretation and document the reasoning so future
agents and reviewers understand why `ConFreezeTermination` does not
literally implement Anonymous 2026's Algorithm.

## Decision

**`ConFreezeTermination` ships the bible's interpretation: stop when
the inter-round JSD has remained strictly below ``threshold`` for
``window`` consecutive round transitions AND the latest round's mean
Propose confidence is at least ``confidence_floor``. The Anonymous
2026 paper provides the *concept* and the *name*; the bible provides
the *operationalisation*. Defaults: ``window=5`` (spec Q4),
``threshold=0.05`` (matches `JSDDivergenceTermination`'s default),
``confidence_floor=0.0`` (default off — users can tune up to make
the freeze more conservative).**

The paper's exact algorithm is preserved as future work — see
§"Future work" — under a separate class
`UnanimityRoundZeroTermination` that bibled users do not need.

## Alternatives Considered

### Option A — Faithful paper algorithm (round-0 unanimity flag + freeze)

Implement Anonymous 2026's Algorithm exactly: at `round_index == 0`,
compute a unanimity flag over Propose claim surfaces. If all agents
agree, return `(True, "round-0 unanimity")`. Otherwise return
`(False, "")` and never fire again.

**Rejected.** Two reasons:

1. **The user's `window=5` default has no meaning under Option A.** A
   single-round gate has nothing to multiply by 5. Honouring spec Q4
   requires a multi-round interpretation.
2. **The bible's signal is different from the paper's signal.** The
   bible explicitly mentions "JSD < freeze_threshold AND confidence
   > confidence_floor" — neither of those conditions is in
   Anonymous 2026. Treating the bible as a paraphrase of the paper
   would be a false unification.

### Option B — Bible's signal, but no confidence-floor gate

Implement multi-round JSD streak detection but ignore the bible's
"AND confidence > confidence_floor" clause. Equivalent to firing on
streak length alone.

**Rejected.** The bible's confidence floor exists for a real reason:
when all agents agree at low confidence (e.g., everyone reports
0.2 confidence on the same surface), the apparent JSD-streak masks
genuine epistemic uncertainty — freezing would commit to a hedged
answer. The confidence floor lets the user demand both *agreement*
and *boldness* before terminating, which is the authentic ConFreeze
spirit ("freeze when consensus is reliable", not just when consensus
exists). Default `confidence_floor=0.0` reduces Option C to Option B
when the user wants permissive behaviour, so nothing is lost by
including the parameter.

### Option C (chosen) — Multi-round JSD streak + optional confidence floor

```
should_stop(trace, R) = True
    iff R >= window
    and inter_round_jsd(trace, r) < threshold for r ∈ [R-window+1, R]
    and round_mean_confidence(trace, R) >= confidence_floor
```

**Chosen.** Three properties:

1. **Honours the user's authorisations.** `window=5` (Q4),
   `threshold=0.05`, and the no-split PR ship (Q5) are all
   straightforward parameters of this formulation.
2. **Encodes the bible's signal exactly.** The "JSD < threshold AND
   confidence > floor" clause from `COUNCIL_NS_PLAN.md` §6.4 lifts
   verbatim into the implementation; the only addition is the
   multi-round dimension that `window` introduces.
3. **The paper's algorithm is a special case.** With `window=1`,
   `threshold=0` (strict zero JSD), and `confidence_floor=0`, the
   strategy approximates the paper's round-0 unanimity gate (zero
   JSD between rounds 0 and 1 is a tight proxy for unanimity in
   round 0). Future-Claude can wire the paper's exact algorithm by
   composing `ConFreezeTermination(window=1, threshold=0)` with a
   higher-level "skip subsequent rounds" mechanism.

## Consequences

**Positive:**

- The user's spec resolutions (Q4, Q5) are honoured directly without
  reinterpretation.
- The implementation is a pure function of `(Trace, round_index)` —
  no mutable state, no per-round bookkeeping, fully replayable. This
  matches the L0 architecture rule that termination strategies are
  pure where possible (`council/termination.py:`'s `FixedRounds` is
  the canonical example; `LTLfMonitorTermination` is the necessary
  exception because monitor stepping is sequential).
- `JSDDivergenceTermination` and `ConFreezeTermination` share the
  same `_inter_round_jsd` helper and the same threshold semantics —
  composing them into `CompositeTermination` produces predictable
  layered behaviour ("fire on first round of agreement OR after a
  window of agreement at high confidence").
- No new dependencies. Re-uses `jsd_divergence` from W3/PR1.

**Neutral:**

- Future paper-faithful behaviour is achievable via the future-work
  `UnanimityRoundZeroTermination` class — no breaking change to
  `ConFreezeTermination` is required.
- The helper functions (`_round_distribution`, `_inter_round_jsd`,
  `_round_mean_confidence`) are module-private. They are
  implementation details that callers should access via
  `JSDDivergenceTermination.should_stop` and
  `ConFreezeTermination.should_stop`. If a future caller needs them
  directly, the underscore prefix can be lifted with a follow-up PR
  and a small ADR amendment.
- Inter-round JSD definition: empirical distribution over Propose
  claim surfaces in round R, weighted by `Propose.confidence`,
  normalised to sum to 1. JSD between consecutive distributions via
  `jsd_divergence`. Sentinel `_JSD_UNDEFINED = -1.0` when either
  round has no Propose moves; treated as "no information; do not
  fire".

**Negative:**

- A reader who knows Anonymous 2026 well will be surprised that our
  `ConFreezeTermination` does not literally implement the paper's
  Algorithm. This ADR exists to inoculate against that surprise; the
  module docstring on `ConFreezeTermination` cross-references this
  ADR and the bible.
- The bible's "freeze" wording suggests a *terminal* state ("once
  frozen, never unfreeze"); our implementation is *re-evaluating*
  every round (a pure function). With monotone JSD streak detection
  this is observationally equivalent — once the streak fires, the
  pipeline halts and the strategy is never queried again — but a
  reader expecting persistent state will need to read the docstring.

## Future work

- **`UnanimityRoundZeroTermination(TerminationStrategy)`** — ships
  Anonymous 2026's exact Algorithm. Compute a unanimity flag over
  round-0 Propose surfaces; if true, return `(True, "round-0
  unanimity")` immediately. If false, return `(False, "")` and never
  fire again. Composes naturally into `CompositeTermination`. Not a
  superseder of `ConFreezeTermination` — a sibling for users who
  want paper-faithful selective execution.
- **Genome / `CalibrationSpec` integration**: surface the freeze
  parameters (`window`, `threshold`, `confidence_floor`) through the
  YAML runner schema (`experiments/run.py`). Out of scope for PR5;
  blocks on the W5 QD search consuming them as descriptors.

## Realised by

- `council/termination.py` — implementation of
  `JSDDivergenceTermination` and `ConFreezeTermination`, both
  `@dataclass(frozen=True, slots=True)`. Module-private helpers
  `_round_distribution`, `_inter_round_jsd`,
  `_round_mean_confidence`, plus the `_JSD_UNDEFINED` sentinel.
- `tests/test_termination_w3.py` — 17 unit tests covering both
  strategies and their composition with `CompositeTermination` and
  `FixedRounds`.

## References

- `papers/2 --- calibration and disagreement/Anonymous 2026
  "ConFreeze: Selective Multi-Model Debate through Consensus Freezing"
  (Preprint; OpenReview:PrqXuAS4BZ).pdf` — the source paper. §2.1
  Methodology + §2.2 Stage 1 (Initial Round Prediction and Consensus
  Detection) carry the round-0 unanimity-flag algorithm.
- `specs/w3-calibration.md` §"Resolved decisions" Q4 — the user's
  authorisation of `window=5` as the default.
- `specs/w3-calibration.md` §"Resolved decisions" Q5 — the user's
  decision not to split PR5; both terminations ship together.
- `COUNCIL_NS_PLAN.md` §6.4 lines 731-742 — the bible's
  `ConFreezeTermination` sketch ("Stop when JSD < freeze_threshold
  AND confidence > confidence_floor"), which this ADR
  operationalises.
- `COUNCILAGENT_NS_MASTER_PLAN.md` §7 W3 — the workstream
  definition that names both deliverables.
- `.claude/rules/architecture.md §"Required contracts" → "L0 —
  speech-act algebra"` — the frozen `TerminationStrategy.should_stop`
  signature both classes implement.
- `docs/adr/0008-calibrator-abc-location.md` — Calibrator ABC
  location (W2/PR1). Same family — L3 contracts.
- `docs/adr/0015-calibrate-extra-split.md`,
  `docs/adr/0016-muse-calibrator-interface.md`,
  `docs/adr/0017-privileged-knowledge-calibrator-interface.md`,
  `docs/adr/0018-isotonic-calibrator-fixture-strategy.md` — sibling
  W3 ADRs sharing the safe-fallback / clamping / paper-grounding
  conventions.
