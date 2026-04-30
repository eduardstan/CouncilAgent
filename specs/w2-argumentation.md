# Spec: W2 — Argumentation Aggregator (L2)

**Branch:** `council-ns` → feature branches `feature/ns-w2-*`
**Milestone:** M2 (end Jul 2026)
**Workstream:** W2 (L2 only — composes onto W0 substrate + W1 spine)
**Paper coupling:** P2 *Strategic Gradual Argumentation* (AAAI 2027 main, deadline ~Aug 1 2026; IJCAI 2027 backup ~Jan 2027). Headline aggregator for P3, P4, F.
**Status:** APPROVED — proceed to implementation

---

## Objective

Build the L2 argumentation-based aggregator for `CouncilAgent-NS`: a deterministic
`Trace → QBAF` builder, four gradual semantics (DF-QuAD, Quadratic Energy, Euler,
Strategic-Coupled), an `ArgumentationAggregator` that replaces the W0 last-propose
stub on the headline path, Mermaid + DOT visualisers (the demo gold), and four
mechanised theorems (T4–T7) that *sell* P2 to AAAI/IJCAI/KR reviewers.

W2 introduces three micro-patches against W0 files (mirroring W1's Patch A/B
pattern) before the main work begins:

- **Patch C** (`council/dialect/moves.py`, `council/dialect/parsers.py`,
  `council/dialect/surface.py`): add `Challenge.confidence: float = 0.5`. The
  bible §6.3 explicitly requires this field (challenge attack-weight = LLM-emitted
  certainty). Captured in **ADR-0006**.
- **Patch D** (`council/context.py`): tighten `ProvenanceReceipt.qbaf: object | None`
  to `QBAF | None` via a `TYPE_CHECKING`-guarded import — same pattern `core.py`
  already uses for `Property` ([core.py:31-32](../council/core.py#L31-L32)).
  Preserves Constitution §8 zero-framework rule and avoids circular imports while
  letting mypy enforce the type.
- **Patch E** (`council/context.py`): extend `ProvenanceReceipt.is_complete()`
  with the *Constitution §11* QBAF clause: when `qbaf is not None`, every
  `Propose` move in the trace corresponds to exactly one argument node in the
  QBAF (and vice versa). The clause is currently noted as deferred at
  [context.py:84-85](../council/context.py#L84-L85).

**Why this matters:** Constitution §5 makes calibrated confidence the council's
unique value, and `BAFMarginConfidence` is the headline confidence type. Until
W2 lands, `run_council()` returns a placeholder `CopelandConfidence(0.5)` — the
council has no signature confidence signal. Constitution §11 makes the QBAF a
required field of the `ProvenanceReceipt`, but `qbaf` is currently always
`None`. P2 (AAAI 2027) is built on T4–T7, none of which exist yet.

**Users:** the `run_council()` pipeline (runtime use); P2 reviewers
(theorem-mechanisation use); the Streamlit demo (`apps/streamlit_demo.py`,
W7) which needs `metadata.baf_mermaid` for live argument-graph rendering;
W5 QD descriptors (`qbaf_density`, `disagreement_persistence`) which depend
on a real QBAF to be meaningful.

**Success:** every W2 acceptance criterion from
`COUNCILAGENT_NS_MASTER_PLAN.md §7 W2` is checked off, `mypy --strict` passes
on `council/symbolic/argue/`, all four semantics have determinism +
monotonicity + Walton-Krabbe golden tests, T4–T7 are mechanised in
`tests/regressions/`, and an end-to-end `run_council()` test produces a
`CouncilResponse` whose `confidence` is `BAFMarginConfidence` and whose
`receipt.qbaf` is non-`None` and structurally complete.

---

## Tech Stack

- Python 3.11+, `asyncio`, `mypy --strict`, `ruff` — same as W0/W1
- `pytest` + `pytest-asyncio` (mode = `auto`)
- **No new core dependencies.** Pure-Python implementations of all four
  semantics. No `networkx`, no `numpy` in core (Constitution §8 zero-framework
  rule). `numpy` allowed only inside `tests/symbolic/argue/test_*.py` for
  property-based determinism checks if it shortens fixtures.
- **Optional `[argue-asp]` extra** — `clingo` for preferred/stable/grounded
  extensions; import-guarded under `try/except ImportError`. Pure-Python no-op
  fallback in the no-extras path.
- **No `[verify]` dependency from `argue/`.** PR5 (Strategic-Coupled) implements
  a minimal one-coalition ATL evaluator inline — does NOT import from
  `council/symbolic/verify/`. This is enforced by architecture rules (no
  `argue/ → verify/` import).

---

## Commands

```bash
# Full test suite
uv run pytest tests/

# W2-only tests
uv run pytest tests/symbolic/argue/

# Theorem regressions (T4–T7)
uv run pytest tests/regressions/test_t4_borda.py \
              tests/regressions/test_t5_manipulability.py \
              tests/regressions/test_t6_postulates.py \
              tests/regressions/test_t7_coupled.py

# ASP backends (requires [argue-asp])
uv run pytest tests/symbolic/argue/test_asp_backends.py

# Type-check (must pass with 0 errors)
uv run mypy council/

# Lint
uv run ruff check council/ tests/

# Constitution audit
.claude/skills/check-constitution/run.sh

# Install ASP extra (system-level clingo also required)
# Ubuntu/Debian:  sudo apt install gringo
# macOS:          brew install clingo
# pip:            uv sync --extra argue-asp
```

---

## Project Structure

Files created by W2 (all new unless marked **MODIFIED**):

```
council/symbolic/argue/
├── __init__.py                  MODIFIED — add public re-exports
├── baf.py                       NEW — Argument, Attack, Support, QBAF (frozen+slots)
├── builders.py                  NEW — build_qbaf(trace, calibrator) → QBAF
├── aggregation_result.py        NEW — typed AggregationResult dataclass
├── aggregator_base.py           NEW — Aggregator ABC (single source for L2 contract)
├── aggregator.py                NEW — ArgumentationAggregator + LastProposeFallbackAggregator
├── visualisers.py               NEW — to_mermaid(qbaf), to_dot(qbaf)
├── asp_backends.py              NEW — preferred/stable/grounded via clingo (optional)
└── semantics/
    ├── __init__.py              NEW — registry of GradualSemantics implementations
    ├── base.py                  NEW — GradualSemantics ABC
    ├── df_quad.py               NEW — Rago-Toni-Aurisicchio-Baroni KR 2016 (default)
    ├── quad.py                  NEW — Quadratic Energy (Potyka 2018)
    ├── euler.py                 NEW — Euler-based (Amgoud-Ben-Naim 2017)
    └── coupled.py               NEW — Strategic-Coupled (DF-QuAD ⊕ ATL) — novel

council/calibrate/
├── __init__.py                  MODIFIED — re-export Calibrator ABC
└── base.py                      NEW — Calibrator ABC stub (W2-PR2; W3 fills concretes)

council/dialect/moves.py         MODIFIED (Patch C) — Challenge.confidence
council/dialect/parsers.py       MODIFIED (Patch C) — parse confidence from Challenge JSON
council/dialect/surface.py       MODIFIED (Patch C) — render confidence in Challenge NL form
council/context.py               MODIFIED (Patch D + E) — qbaf typing, is_complete() QBAF clause
council/core.py                  MODIFIED — _aggregate_answer delegates to context.aggregator
council/agent.py                 MODIFIED — accept optional aggregator arg; default Argumentation

tests/symbolic/argue/
├── __init__.py                  NEW
├── test_baf.py                  NEW — 25+ tests: construction, equality, immutability, invariants
├── test_builders.py             NEW — determinism round-trip, Walton-Krabbe golden, edge cases
├── test_df_quad.py              NEW — determinism, monotonicity, Walton-Krabbe values, T4 hooks
├── test_quad.py                 NEW — determinism, monotonicity, agreement
├── test_euler.py                NEW — determinism, monotonicity, agreement
├── test_coupled.py              NEW — DF-QuAD reduction, coalition flip example, T7 hook
├── test_aggregator.py           NEW — end-to-end synthetic trace; BAFMarginConfidence assertion
├── test_aggregator_base.py      NEW — Aggregator ABC contract enforcement
├── test_visualisers.py          NEW — Walton-Krabbe Mermaid golden, DOT smoke test
├── test_asp_backends.py         NEW — gated pytest.importorskip("clingo")
├── test_calibrator_stub.py      NEW — Calibrator ABC contract; identity default
└── fixtures/
    ├── walton_krabbe.json       NEW — canonical 5-move trace + expected QBAF golden
    └── borda_3candidate.json    NEW — vote-only BAF for T4 closed-form check

tests/regressions/
├── __init__.py                  NEW (if not present)
├── test_t4_borda.py             NEW — Borda-recovery property test + closed-form fixture
├── test_t5_manipulability.py    NEW — flip-cost upper bound parameterised by (in-deg, ratio)
├── test_t6_postulates.py        NEW — Caminada-Amgoud postulate satisfaction matrix
└── test_t7_coupled.py           NEW — coupled satisfies T3's CTLK invariant; pytest-only

tests/test_context.py            MODIFIED — Patch E: is_complete() QBAF clause regression
tests/test_core.py               MODIFIED — _aggregate_answer delegates; aggregator socket
tests/dialect/test_moves.py      MODIFIED — Patch C: Challenge.confidence default + range
tests/dialect/test_parsers.py    MODIFIED — Patch C: confidence round-trip
tests/dialect/test_surface.py    MODIFIED — Patch C: Challenge surface includes confidence

docs/
├── theory.md                    MODIFIED — append §T4, §T5, §T6, §T7 sections
└── adr/
    ├── 0006-challenge-confidence.md     NEW — Patch C decision (Risk 1)
    ├── 0007-self-attack-deferred.md     NEW — Risk 2 deferred to PR8 via tools.py
    └── 0008-calibrator-abc-location.md  NEW — Calibrator base in calibrate/, used by argue/
```

---

## Code Style

All new code follows `.claude/rules/code-style.md`. Representative snippets:

```python
# council/symbolic/argue/baf.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Argument:
    """A node in the BAF/QBAF, derived from a Propose move."""
    arg_id: str            # equals the Propose.move_id that produced it
    claim_surface: str
    base_score: float      # ∈ [0, 1] — from calibrator or Propose.confidence
    withdrawn: bool = False

@dataclass(frozen=True, slots=True)
class Attack:
    source: str            # arg_id of the Challenge's reason node
    target: str            # arg_id of the Challenged Propose
    weight: float          # ∈ [0, 1] — from Challenge.confidence (Patch C)

@dataclass(frozen=True, slots=True)
class Support:
    source: str
    target: str
    weight: float = 1.0    # Concede edges default to 1.0; future calibration hook

@dataclass(frozen=True, slots=True)
class QBAF:
    arguments: tuple[Argument, ...]
    attacks: tuple[Attack, ...]
    supports: tuple[Support, ...]

    def proposals(self) -> tuple[Argument, ...]:
        """Non-withdrawn arguments — the candidate winners."""
        return tuple(a for a in self.arguments if not a.withdrawn)
```

```python
# council/symbolic/argue/semantics/base.py
from abc import ABC, abstractmethod
from council.symbolic.argue.baf import QBAF

class GradualSemantics(ABC):
    """Maps QBAF → strength dict. Deterministic; monotone in base scores."""
    @abstractmethod
    def evaluate(self, baf: QBAF) -> dict[str, float]: ...
    @abstractmethod
    def preferred_extension(self, baf: QBAF) -> frozenset[str]: ...
```

```python
# council/symbolic/argue/aggregator_base.py
from abc import ABC, abstractmethod
from council.dialect.trace import Trace
from council.symbolic.argue.aggregation_result import AggregationResult

class Aggregator(ABC):
    """L2 aggregator base. Trace is the only input — D8 fix at the type level."""
    @abstractmethod
    async def aggregate(
        self, trace: Trace, *, original_question: str
    ) -> AggregationResult: ...
```

Key conventions:

- `frozen=True, slots=True` on every value object — `Argument`, `Attack`,
  `Support`, `QBAF`, `AggregationResult`.
- `ClassVar[str]` for any registry keys (e.g., `GradualSemantics.name`).
- ABCs via `abc.ABC` + `@abstractmethod`. No `typing.Protocol` for layer ABCs.
- Argument IDs equal the Propose `move_id` they derive from — preserves
  trace-to-graph traceability for `ProvenanceReceipt`.
- Strengths are returned as `dict[str, float]` keyed by `arg_id`; the order is
  insertion order (Python 3.7+ dict guarantee), matching `baf.arguments`.
- Self-attack detection in `builders.py` returns `frozenset()` until PR8 wires
  the `tools.py` path — documented inline with a TODO citing ADR-0007.

---

## Testing Strategy

Framework: `pytest` + `pytest-asyncio` (mode = `auto`)

### Layout

- All W2 unit tests under `tests/symbolic/argue/`.
- Theorem regressions under `tests/regressions/` (one file per theorem).
- Patch C/D/E regressions extend the existing W0 test files
  (`tests/dialect/test_moves.py`, `tests/dialect/test_parsers.py`,
  `tests/dialect/test_surface.py`, `tests/test_context.py`,
  `tests/test_core.py`).

### Test discipline

- **No real model calls.** Hand-built `Trace`s + `FakeModelClient` (W0
  fixture). All four semantics are pure functions over `QBAF` — no async.
- **Determinism.** Every semantics test runs the same input 10 times and
  asserts byte-equal output. `random.seed(0)` in property-based fixtures.
- **Monotonicity.** Each semantics has a property test: increasing the base
  score of an unattacked argument cannot decrease its strength.
- **Walton-Krabbe golden.** A canonical 5-move trace lives in
  `tests/symbolic/argue/fixtures/walton_krabbe.json`; the expected QBAF +
  per-semantics strength values are committed. All four semantics tests, the
  builder test, and the visualiser test reference the same fixture.
- **Borda recovery (T4).** Vote-only BAF on N candidates with K voters →
  DF-QuAD ranking equals Borda count up to monotone re-scaling. Implemented
  as a property-based test (Hypothesis-style: random ballots, fixed seed)
  plus a closed-form 3-candidate fixture in
  `tests/symbolic/argue/fixtures/borda_3candidate.json`.
- **Coverage targets** (`.claude/rules/testing.md`):
  - `council/symbolic/argue/` ≥ 85% line coverage
  - `council/core.py` remains ≥ 95% (do not regress)
  - `council/context.py` ≥ 90% (covers Patch E `is_complete()`)
- **Test count target.** ≥ 80 new tests under `tests/symbolic/argue/` +
  `tests/regressions/`. Per-PR breakdown in §"PR sequence" below.

### Per-PR test requirements

| Module | Required tests |
|---|---|
| `baf.py` | construction, equality, hashability, frozen-mutation rejection, empty-graph invariant, no-self-loops invariant, `proposals()` filtering withdrawn |
| `builders.py` | determinism round-trip, Walton-Krabbe golden, empty trace → empty QBAF, retract-marks-withdrawn, vote-boost-clamping, calibrator hook |
| `df_quad.py` | determinism (10×), monotonicity, single-arg degenerate, Walton-Krabbe golden values, continuity property |
| `quad.py` | determinism, monotonicity, agreement with df_quad on no-attack BAFs |
| `euler.py` | determinism, monotonicity, agreement on degenerate BAFs |
| `coupled.py` | reduction-to-DF-QuAD when no coalition modality active, coalition flip example, T7 hook |
| `aggregator.py` | end-to-end (trace → AggregationResult), `BAFMarginConfidence` type assertion, fallback path on empty BAF, `metadata.baf_mermaid` non-empty |
| `visualisers.py` | Walton-Krabbe canonical Mermaid string golden, DOT round-trip via pydot when available |
| `asp_backends.py` | gated `pytest.importorskip("clingo")`; preferred/stable/grounded extension correctness |
| `calibrate/base.py` | ABC contract enforcement; identity-default Calibrator returns input unchanged |

---

## Boundaries

**Always do:**

- Run `uv run mypy council/` before every PR — zero errors required.
- Run `uv run pytest tests/symbolic/argue/` and `tests/regressions/` before
  every PR.
- Populate `ProvenanceReceipt.qbaf` whenever `ArgumentationAggregator` runs.
- Use `BAFMarginConfidence` as the W2 confidence type — never a raw float,
  never `CopelandConfidence` on the headline path (only the fallback).
- Argument IDs equal the originating `Propose.move_id` (preserves
  trace-to-graph traceability).
- Tag the parser fallback path `tier="argument-mining-fallback"` in
  `aggregator.py` per architecture rules §L2 row.
- Determinism: every semantics + every builder is a pure function;
  `random.seed(0)` in any property-based test.

**Ask first (do not proceed without user confirmation):**

- Changing the `Trace` API or `Move` ADT beyond Patch C (`Challenge.confidence`).
- Changing `ProvenanceReceipt` fields beyond Patch D (qbaf typing) and
  Patch E (`is_complete()` QBAF clause). The receipt is the §11 contract.
- Adding any new optional dependency to `pyproject.toml` beyond `clingo`
  (`[argue-asp]` extra).
- Modifying `council/core.py` beyond the aggregator-delegation socket
  described in PR6.
- Changing `Aggregator.aggregate` signature — the master plan freezes
  `(trace, *, original_question)` (D13 fix).
- Adding a new approved exception to `.claude/rules/architecture.md`.
  PR8's `argue/asp_backends.py → tools.py` is *the* exception W2 needs;
  any other cross-layer import requires user approval.

**Never do:**

- Import `council/core.py` or `council/agent.py` from any
  `council/symbolic/argue/` module (architecture rules §forbidden imports).
- Import `council/symbolic/verify/` from `council/symbolic/argue/`. T7's
  ATL fragment is implemented inline in `coupled.py`, not via `verify/`.
- Call a generation model from `council/symbolic/argue/`. The argumentation
  graph is **constructed by the protocol**, not extracted from text
  (architecture rules §L2: "no LLM extraction in the headline path").
- Use `Counter()` on raw LLM output, `r.content.strip()` aggregation, or
  any substring-match logic — these are the legacy defects W2 fixes.
- Compute `BAFMarginConfidence` from raw text (Constitution §5: confidence
  is computed from the QBAF margin, never from `r.content`).
- Use `import networkx`, `import numpy` in `council/symbolic/argue/`
  runtime code (Constitution §8 zero-framework rule). Pure Python only.
- Hardcode model names anywhere in `council/symbolic/argue/` (this layer
  has no business calling models).
- Implement T7 (Strategic-Coupled / ATL) by reaching into MCMAS or SPOT.
  T7's mechanisation is a pytest-level finite-trace simulation; offline
  ATL verification via MCMAS is reviewer-bait, not a runtime requirement.

---

## Patch C — `Challenge.confidence`

```python
# council/dialect/moves.py — addition only
@dataclass(frozen=True, slots=True)
class Challenge:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.CHALLENGE
    target: str = ""
    reason: Claim = field(default_factory=lambda: Claim(surface=""))
    confidence: float = 0.5    # NEW (Patch C; ADR-0006) — feeds Attack.weight in W2
```

Parser side ([parsers.py](../council/dialect/parsers.py)) reads `confidence`
from JSON when present, defaults to `0.5` when absent (preserves backward
compatibility with W0/W1 fixtures). Surface side ([surface.py](../council/dialect/surface.py))
renders `(conf=0.X)` after the challenge clause, mirroring `Vote`'s rendering.

The default of `0.5` is intentional: the constitution does not prescribe a
prior, and `0.5` keeps unparseable challenges from biasing the BAF in either
direction. Documented in **ADR-0006**.

All existing `Challenge(...)` constructions in tests omit the field → default
applies. No callsite changes required.

---

## Patch D — `ProvenanceReceipt.qbaf` typing

```python
# council/context.py — addition only
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from council.symbolic.argue.baf import QBAF

@dataclass(frozen=True, slots=True)
class ProvenanceReceipt:
    trace: Trace
    qbaf: "QBAF | None" = None          # tightened from `object | None`
    monitor_verdicts: tuple[MonitorVerdict, ...] = ()
    asp_groundings: tuple[str, ...] = ()
    cost_ledger: tuple[tuple[str, float], ...] = ()
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    ...
```

The `TYPE_CHECKING` guard preserves Constitution §8 (no L2 import in
`context.py` at runtime) while letting mypy enforce the type. This pattern is
already used by [core.py:31-32](../council/core.py#L31-L32) for `Property`.
No runtime change.

---

## Patch E — `ProvenanceReceipt.is_complete()` QBAF clause

```python
# council/context.py:ProvenanceReceipt.is_complete (extension only)
def is_complete(self) -> bool:
    # ... existing (a), (b), (c) clauses ...

    # (d) Constitution §11 QBAF clause — the W2 receipt-completeness check
    if self.qbaf is not None:
        propose_count = sum(
            1 for m in self.trace.moves if isinstance(m, Propose)
        )
        if len(self.qbaf.arguments) != propose_count:
            return False

    return True
```

The clause is currently noted as deferred at
[context.py:84-85](../council/context.py#L84-L85). The check is intentionally
narrow: it asserts the count invariant only, not the bijection (the bijection
is enforced *constructively* by `build_qbaf`, which uses `Propose.move_id` as
`Argument.arg_id` — verified by `tests/symbolic/argue/test_builders.py`).

---

## PR sequence and acceptance criteria

| # | Branch slug | Key deliverable | Acceptance test |
|---|---|---|---|
| 0 | (patch, no own branch — part of PR1) | Patch C: `Challenge.confidence` | `tests/dialect/test_moves.py::test_challenge_confidence_default`, `test_parsers.py::test_challenge_confidence_round_trip`, `test_surface.py::test_challenge_renders_confidence` |
| 1 | `ns-w2-baf-types` | `baf.py`, `aggregation_result.py`, `aggregator_base.py`, `semantics/base.py`, `calibrate/base.py`, **ADR-0008** | `tests/symbolic/argue/test_baf.py` (25+ tests); `test_aggregator_base.py`; `test_calibrator_stub.py` |
| 2 | `ns-w2-builders` | `builders.py` — `build_qbaf(trace, calibrator=None) → QBAF` | `test_builders.py`: determinism round-trip (10×), Walton-Krabbe golden, empty-trace, retract, vote-boost clamping |
| 3 | `ns-w2-df-quad` | `semantics/df_quad.py` (default) + **T4 mechanisation** | `test_df_quad.py`: determinism, monotonicity, continuity, Walton-Krabbe golden values; `tests/regressions/test_t4_borda.py` |
| 4 | `ns-w2-quad-euler` | `semantics/quad.py`, `semantics/euler.py` | `test_quad.py`, `test_euler.py`: determinism, monotonicity, agreement on degenerate BAFs |
| 5 | `ns-w2-coupled-semantics` | `semantics/coupled.py` (novel; minimal one-coalition ATL inline) + **T7 mechanisation** | `test_coupled.py`: DF-QuAD reduction property, coalition flip example; `tests/regressions/test_t7_coupled.py` |
| 6 | `ns-w2-aggregator` | `aggregator.py` (`ArgumentationAggregator` + `LastProposeFallbackAggregator`); `core.py` aggregator socket; **Patch D** + **Patch E** | `test_aggregator.py`: end-to-end, `BAFMarginConfidence` assertion, `metadata.baf_mermaid` populated; `test_context.py::test_is_complete_qbaf_clause`; `test_core.py::test_aggregator_socket` |
| 7 | `ns-w2-visualisers` | `visualisers.py` — `to_mermaid(qbaf)`, `to_dot(qbaf)` | `test_visualisers.py`: Walton-Krabbe canonical Mermaid golden string |
| 8 | `ns-w2-asp-extensions` | `asp_backends.py` (optional `[argue-asp]`) + **ADR-0007** + new approved exception in `.claude/rules/architecture.md` | `test_asp_backends.py`: `pytest.importorskip("clingo")`-gated; preferred/stable/grounded extension correctness |
| 9 | `ns-w2-theorems` | `docs/theory.md` §T4–§T7; full `tests/regressions/test_t{5,6}_*.py` proofs | All four theorem regressions green; `docs/theory.md` has §T4, §T5, §T6, §T7 with statement, proof sketch, citation, mechanisation pointer |

PR1 is the smallest landable slice: pure ABCs + dataclasses, zero behaviour
change to `core.py` / `agent.py`. It unblocks PR2/PR3 to be developed in
parallel (PR2 needs `QBAF` types; PR3 needs `GradualSemantics` ABC; both are
in PR1).

---

## Risk register (resolved)

| # | Risk | Resolution | Captured in |
|---|---|---|---|
| 1 | `Challenge.confidence` missing — bible §6.3 expects it as Attack weight | Patch C: add field with default 0.5 | ADR-0006 (PR1) |
| 2 | Self-attack detection wants Z3/clingo; rules forbid `argue/ → verify/` | Defer to PR8 via `argue/asp_backends.py → tools.py` (new approved exception) | ADR-0007 (PR8) |
| 3 | `PluralityAggregator` fallback name conflicts with Constitution §5 | Rename `LastProposeFallbackAggregator`; emits `CopelandConfidence` | spec §"Project Structure" (PR6) |
| 4 | ATL fragment for T7 — W1 ships LTL_f only | Minimal one-coalition ATL evaluator inline in `coupled.py`; finite-trace simulation; offline MCMAS as reviewer-bait, not runtime | spec §"Tech Stack" (PR5) |
| 5 | `Calibrator` ABC location — referenced by W2, owned by W3 | Stub `Calibrator` ABC in `council/calibrate/base.py` (PR1); identity-default; W3 fills concretes | ADR-0008 (PR1) |
| 6 | `ProvenanceReceipt.qbaf: object | None` is too loose for §11 | Patch D: `TYPE_CHECKING`-guarded `QBAF | None`; same pattern as `core.py` for `Property` | spec §"Patch D" (PR6) |

All resolutions are pre-approved by the user's "solve the risks cross-checking
again with COUNCILAGENT_NS_MASTER_PLAN.md while optimizing the long-term
maintainability and health of the repository" instruction (2026-04-30).

---

## Theorems (T4–T7)

| ID | Statement (short) | Mechanisation |
|---|---|---|
| T4 | DF-QuAD on vote-only BAFs recovers Borda count up to monotone re-scaling | `tests/regressions/test_t4_borda.py` (closed-form + property-based) |
| T5 | Flip-cost upper bound parameterised by (in-degree, attack/support ratio); builds on Baroni-Rago-Toni 2019 | `tests/regressions/test_t5_manipulability.py` |
| T6 | Caminada-Amgoud postulate satisfaction matrix; identifies the necessarily-violated Arrow-style axiom | `tests/regressions/test_t6_postulates.py` |
| T7 | Strategic-Coupled satisfies T3's CTLK invariant on a small instance (original) | `tests/regressions/test_t7_coupled.py` |

Proofs (≤ 1 page each) appended to `docs/theory.md` in PR9. P2 (AAAI 2027)
appendix lifts these directly.

---

## Success Criteria

- [ ] `uv run mypy council/` exits 0 — no new errors introduced by W2.
- [ ] `uv run pytest tests/symbolic/argue/` passes — all W2 unit tests green.
- [ ] `uv run pytest tests/regressions/` passes — T4, T5, T6, T7 all green.
- [ ] `uv run pytest tests/` passes — no W0/W1 regressions.
- [ ] `uv run ruff check council/ tests/` — zero violations.
- [ ] Four gradual semantics implemented (DF-QuAD, QE, Euler, Strategic-Coupled),
      all passing determinism + monotonicity + Walton-Krabbe golden.
- [ ] `build_qbaf(trace, calibrator=None)` is byte-deterministic for fixed
      trace across 100 invocations (round-trip test).
- [ ] `ArgumentationAggregator(...).aggregate(trace, original_question="...")`
      returns an `AggregationResult` with:
      - `confidence: BAFMarginConfidence`
      - `metadata["baf_mermaid"]` non-empty string
      - `metadata["strengths"]` dict keyed by `arg_id`
      - `metadata["extension"]` is a `frozenset[str]`
- [ ] End-to-end `run_council()` with default `CouncilAgent` config returns a
      `CouncilResponse` whose `confidence` is `BAFMarginConfidence` and
      `receipt.qbaf` is a non-`None` `QBAF`.
- [ ] `ProvenanceReceipt.is_complete()` returns `False` when
      `qbaf.arguments` count differs from `Propose` count in the trace
      (Patch E regression).
- [ ] Walton-Krabbe canonical example produces the committed golden Mermaid
      string and the committed golden DF-QuAD strength values.
- [ ] T4–T7 mechanised in `tests/regressions/`; `docs/theory.md` has
      `## T4 — Borda Recovery`, `## T5 — Manipulability Bound`,
      `## T6 — Rationality Postulates`, `## T7 — Strategic-Coupled` each
      with a theorem statement, proof sketch (≤ 1 page), references, and a
      mechanisation pointer.
- [ ] `docs/adr/0006-challenge-confidence.md`, `0007-self-attack-deferred.md`,
      `0008-calibrator-abc-location.md` exist.
- [ ] No new forbidden imports: no `langgraph`, `hydra`, `mlflow`,
      `opentelemetry`, `pyribs`, `spot`, `clingo` (without the `[argue-asp]`
      guard) in `council/symbolic/argue/`.
- [ ] No `argue/ → verify/` import (T7 implements ATL inline).
- [ ] No `argue/ → core/` or `argue/ → agent/` imports.
- [ ] Test count ≥ 80 new tests under `tests/symbolic/argue/` +
      `tests/regressions/`.
- [ ] Coverage on `council/symbolic/argue/` ≥ 85%; `council/context.py`
      ≥ 90% (covers Patch E).

---

## Open Questions

None. The six risks raised by the workstream-planner are resolved above and
captured in ADR-0006 / ADR-0007 / ADR-0008 to be authored at the slice that
triggers each. The resolutions follow Constitution §1 (council-as-agent over
benchmark) and §11 (provenance receipts non-negotiable). Any new ambiguity
discovered during implementation is "Ask first" per §"Boundaries" above.
