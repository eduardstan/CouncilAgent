# ADR-0006: Extend `Challenge` Move with a `confidence: float` field

## Status

Accepted.

## Date

2026-04-30

## Context

`council/dialect/moves.py` defines the typed Move ADT (W0/PR2). The current
shape of `Challenge` ([moves.py:64-70](../../council/dialect/moves.py#L64-L70))
is:

```python
@dataclass(frozen=True, slots=True)
class Challenge:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.CHALLENGE
    target: str = ""
    reason: Claim = field(default_factory=lambda: Claim(surface=""))
```

The W2 builder (`council/symbolic/argue/builders.build_qbaf`, PR2) needs a
numeric weight for every `Attack` edge it creates from a `Challenge` move.
The bible specifies the weight in §6.3 (lines 633-634) of `COUNCIL_NS_PLAN.md`:

```
- Every Challenge(target, reason) → attack edge (reason → target),
  with attack weight = LLM-emitted certainty of the challenge.
```

There is no place on the current `Challenge` schema to carry that
LLM-emitted certainty. `Propose.confidence: float = 0.5` and
`Vote.confidence: float = 0.5` already exist for the same purpose on the
PROPOSE and VOTE forces; CHALLENGE is the only force that emits a graded
signal but has no numeric field.

The W0 spec (`specs/w0-substrate.md` §"Boundaries", lines 230-235) lists
`Move`-shape changes under "Ask first": **"Any change to the
`ProtocolAutomaton` ABC method signatures (all concrete automata and W1
hooks depend on them)"**. The bible's L0 spec is the authority on the Move
ADT's schema; it explicitly calls for this field. The user's instruction
(2026-04-30) to "solve the risks cross-checking again with the master plan
while optimizing the long-term maintainability and health of the repository"
authorises the necessary schema patch.

Three options were evaluated.

## Decision

**Add `confidence: float = 0.5` to `Challenge`, mirroring `Propose.confidence`
and `Vote.confidence`. Default 0.5.**

The default is intentional. The constitution does not prescribe a prior, and
0.5 keeps unparseable challenges from biasing the BAF in either direction.
W2/PR2's `build_qbaf` reads `Challenge.confidence` and clamps it into the
`Attack.weight` field (which `__post_init__` already clamps to [0, 1]).

Parser and surface support are added in the same commit:

- `parsers.py::_parse_single` reads `confidence` from JSON when present,
  defaults to `0.5` when absent (`float(str(obj.get("confidence", 0.5)))`,
  identical to the existing pattern for `Propose` and `Vote`).
- `surface.py::render_move` renders `(confidence=0.XX)` after the challenge
  clause, mirroring `Vote`'s rendering.

## Alternatives Considered

### Option A — Derive the weight from `Claim.evidence` length

Compute `Attack.weight = min(1.0, len(challenge.reason.evidence) / 5)` or a
similar heuristic on the `Claim.evidence` tuple already present in
`Challenge.reason`.

**Rejected.** Evidence-count-as-confidence conflates two distinct signals.
A challenge with five weak citations is not more confident than a challenge
with one strong citation — the count is a structural property, not a
calibration. P2 (AAAI 2027) reviewers will check the BAF construction
against the bible's stated rule ("LLM-emitted certainty"); using
evidence-count instead is a citation liability.

### Option B — Fix the weight to a constant

Hardcode `Attack.weight = 1.0` (or `0.5`) for every Challenge.

**Rejected.** This silently drops the LLM's calibrated certainty signal,
which is exactly what Constitution §5 (calibrated confidence is the
council's unique value) is designed to preserve. It also makes T5
(manipulability bound — Baroni-Rago-Toni 2019) trivially satisfied because
all weights are equal; the theorem becomes uninteresting.

### Option C — Carry the weight in `Challenge.reason.evidence` as a magic string

Encode the weight in `Claim.evidence` as `("weight=0.7",)` and parse it
back in `build_qbaf`.

**Rejected.** This is a backwards-compat hack of the worst kind: it pollutes
the `evidence` tuple's semantics (which is meant for citation atoms), it
requires string parsing in L2 (architecture rules forbid LLM-text
extraction in the headline path), and it creates a hidden coupling between
parser, surface, and builder that no future maintainer will spot.

### Option D (chosen) — Add `confidence: float = 0.5` to `Challenge`

The default-`0.5` field is parallel to `Propose.confidence` and
`Vote.confidence` — three forces, three confidence fields. The schema
becomes more uniform, not less. Existing `Challenge(...)` constructors
in 7 W0/W1 test fixtures and the W1 `Intervention.execute` callsites omit
`confidence` → default `0.5` applies, no migration required.

## Consequences

**Positive:**

- The bible's §6.3 BAF construction rule is implementable without any
  parser-side string-parsing or evidence-count heuristic.
- `Challenge.confidence` is now uniform with `Propose.confidence` and
  `Vote.confidence` — three confidence-bearing forces, three fields.
- T5 (manipulability bound) remains non-trivial because edge weights vary
  with LLM-emitted certainty.
- The default-`0.5` makes existing W0/W1 fixtures pass without churn.

**Neutral:**

- `to_events()` does not currently emit `Challenge.confidence` to L1
  monitors. If a future LTL_f property needs it, the appropriate fix is
  another `Trace.to_events()` extension (the ADR-0003 pattern), not a
  back-channel through `argue/`. No change required for W2.
- `Claim.formula` still defaults to `None` for Challenge reasons — Patch C
  does not affect that field.

**Negative:**

- Existing JSON outputs from agents that lacked a `confidence` key on
  CHALLENGE will silently default to `0.5`. This is consistent with the
  existing `Propose` and `Vote` fallback behaviour, but worth noting.
- ISPL/SMV emitter (W1/PR6) does not currently emit a `confidence` field
  for any Move; this remains true. If MCMAS-side reasoning needs to see
  challenge weights in the future, that's a separate W1-extension PR.

## References

- `council/dialect/moves.py` — implementation site (W2/PR2 Slice A)
- `council/dialect/parsers.py` — parser-side support (W2/PR2 Slice A)
- `council/dialect/surface.py` — surface-side support (W2/PR2 Slice A)
- `council/symbolic/argue/builders.py` — consumer (W2/PR2 Slice C)
- `COUNCIL_NS_PLAN.md §6.3` — bible specification of `build_qbaf`
- `COUNCILAGENT_NS_MASTER_PLAN.md §7 W2` — workstream acceptance criteria
- `specs/w2-argumentation.md §"Patch C"` — full migration plan
- `docs/adr/0003-to-events-w1-extension.md` — same pattern (W0 schema patch
  during a later workstream)
