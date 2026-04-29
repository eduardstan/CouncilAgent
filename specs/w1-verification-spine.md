# Spec: W1 — Verification Spine (L1)

## Objective

Build the L1 symbolic verification layer for `CouncilAgent-NS`: a three-valued LTL_f runtime monitor that steps over typed `Trace` events, a named-property library of ten or more citable deliberation invariants, an offline ISPL/SMV emitter for MCMAS/NuSMV, five concrete `Intervention` implementations (Constitution §12), and the `LTLfMonitorTermination` strategy that wires monitors and interventions into `run_council()`.

Two W1 micro-patches extend W0 files before the main work begins:
- **Patch A** (`council/dialect/trace.py`): extend `to_events()` with three derived boolean APs needed for faithful LTL_f property encoding — `has_evidence`, `has_prior_challenge`, `same_agent_concede_run_ge_3`.
- **Patch B** (`council/context.py`): add `tool_client: ToolClient | None = None` to `CouncilContext` so `TriggerVerifier` can invoke Z3/clingo/Lean.

**Why this matters:** Constitution §12 requires the verifier to *redirect* deliberation (not merely observe). P1 (AAMAS 2027) is built on T1–T3. The QD descriptor `monitor_pass_rate` used in W5/P3 depends on W1 being functional.

**Users:** the `run_council()` pipeline (runtime use), researchers reproducing P1 results (offline MCMAS use), and future contributors adding new properties (library use).

**Success:** every W1 acceptance criterion from `COUNCILAGENT_NS_MASTER_PLAN.md §7 W1` is checked off, `mypy --strict` passes on `council/symbolic/verify/`, all 10 named properties have positive and negative trace tests, and an end-to-end `run_council()` test with an active `LTLfMonitorTermination` populates `ProvenanceReceipt.monitor_verdicts`.

---

## Tech Stack

- Python 3.11+, `asyncio`, `mypy --strict`, `ruff`
- `pytest` + `pytest-asyncio` (mode = `auto`)
- SPOT Python bindings — optional `[verify]` extra; import-guarded; **not conda** — see installation docs below
- No other new dependencies in the core path (no `lark`, no `antlr`, no `networkx`)
- MCMAS and NuSMV: subprocess only, in `tests/integration/`; not pip-installable; documented in `docs/install_spot.md`

---

## Commands

```bash
# Full test suite
uv run pytest tests/

# W1-only tests
uv run pytest tests/symbolic/

# Integration tests (require MCMAS and RUN_INTEGRATION=1)
RUN_INTEGRATION=1 uv run pytest tests/integration/test_mcmas_offline.py

# Type-check (must pass with 0 errors)
uv run mypy council/

# Lint
uv run ruff check council/ tests/

# Install SPOT (system-level, not conda — documented in docs/install_spot.md)
# Ubuntu/Debian:  sudo apt install spot python3-spot
# pip (unofficial wheel):  pip install spot   # if available for your platform
# From source:  see docs/install_spot.md
```

---

## Project Structure

Files created by W1 (all new unless marked *modified*):

```
council/symbolic/verify/
├── __init__.py               (already exists — add public re-exports)
├── ltlf.py                   NEW — LTL_f AST nodes + recursive-descent parser
├── monitor.py                NEW — LTL3Monitor ABC + Verdict enum
├── ltl2mon_backend.py        NEW — ProgressionMonitor (pure-Python, Bauer 2010)
├── spot_backend.py           NEW — SPOTMonitor + make_monitor() factory
├── properties.py             NEW — 10 named Property subclasses + PROPERTY_REGISTRY
├── ispl.py                   NEW — trace_to_ispl() MCMAS text emitter
├── smv.py                    NEW — trace_to_smv() NuSMV text emitter
└── interventions.py          NEW — Intervention ABC + 5 concrete impls

council/dialect/trace.py      MODIFIED (Patch A) — extend to_events() with 3 derived APs
council/context.py            MODIFIED (Patch B) — add tool_client field to CouncilContext
council/termination.py        MODIFIED — add LTLfMonitorTermination
council/core.py               MODIFIED — honour pending intervention before next round

docs/                         NEW directory (first W1 file creates it)
├── install_spot.md           NEW — SPOT + MCMAS + NuSMV installation guide
└── theory.md                 NEW — T1, T2, T3 theorem statements + proof sketches

tests/symbolic/
├── __init__.py               NEW
└── verify/
    ├── __init__.py           NEW
    ├── test_ltlf.py          NEW — 20+ round-trip parse tests
    ├── test_monitor.py       NEW — LTL3Monitor step/reset/absorbing-state tests
    ├── test_ltl2mon.py       NEW — ProgressionMonitor; cross-validates with PurePython
    ├── test_spot_backend.py  NEW — SPOTMonitor (skipif SPOT unavailable); make_monitor()
    ├── test_properties.py    NEW — positive + negative trace per property; registry
    ├── test_ispl.py          NEW — structural ISPL/SMV output tests
    ├── test_interventions.py NEW — all 5 interventions with FakeModelClient
    ├── test_ltlf_termination.py NEW — LTLfMonitorTermination + CompositeTermination
    └── test_theorems.py      NEW — mechanised T1, T2, T3

tests/integration/
└── test_mcmas_offline.py     NEW — gated RUN_INTEGRATION=1 + MCMAS available

specs/adrs/
└── 0002-w1-to-events-extension.md   NEW — ADR for Patch A decision
```

---

## Code Style

All new code follows `.claude/rules/code-style.md`. Representative snippet:

```python
# council/symbolic/verify/ltlf.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

class LTLf(ABC):
    @abstractmethod
    def __str__(self) -> str: ...

@dataclass(frozen=True, slots=True)
class Atom(LTLf):
    name: str
    def __str__(self) -> str:
        return self.name

@dataclass(frozen=True, slots=True)
class Globally(LTLf):
    arg: LTLf
    def __str__(self) -> str:
        return f"G({self.arg})"

def parse(formula: str) -> LTLf:
    """Recursive-descent LTL_f parser. No external dependencies."""
    ...
```

Key conventions:
- `frozen=True, slots=True` on every value object
- `ClassVar[str]` for `Property.name` and `Property.formula`
- `Verdict` is an `enum.Enum`, not a string
- `make_monitor()` is the single factory call site — callers never instantiate `SPOTMonitor` or `ProgressionMonitor` directly
- Import guard pattern for SPOT:
  ```python
  try:
      import spot as _spot
      _SPOT_AVAILABLE = True
  except ImportError:
      _SPOT_AVAILABLE = False
  ```

---

## Testing Strategy

Framework: `pytest` + `pytest-asyncio` (mode = `auto`)

All unit tests under `tests/symbolic/verify/`:
- Use hand-crafted `Trace` objects — no `FakeModelClient` unless testing `Intervention`
- Are deterministic: no random sampling, no time dependency
- Each `Property` subclass gets exactly two trace tests: one that produces `Verdict.TOP` (or `Verdict.UNKNOWN` for liveness on finite trace) and one that produces `Verdict.BOTTOM`

Intervention tests use `FakeModelClient` (already in W0 `tests/`).

Integration tests (`tests/integration/test_mcmas_offline.py`):
- Gated behind `@pytest.mark.skipif(not _mcmas_available(), reason="MCMAS not installed")` AND `RUN_INTEGRATION=1` env var
- Never run in CI unless explicitly enabled

Coverage targets (from `.claude/rules/testing.md`):
- `council/symbolic/verify/` ≥ 85% line coverage
- `council/core.py` remains ≥ 95% (do not regress)

---

## Boundaries

**Always do:**
- Run `uv run mypy council/` before every PR — zero errors required
- Run `uv run pytest tests/symbolic/` before every PR
- Guard every `import spot` with `try/except ImportError`
- Populate `ProvenanceReceipt.monitor_verdicts` whenever any monitor is active
- Fire interventions only on `Verdict.BOTTOM`, never on `Verdict.UNKNOWN`
- Keep `council/symbolic/verify/interventions.py` as the only L1 file that imports from `council/dialect/moves.py` (approved exception 4)

**Ask first (do not proceed without user confirmation):**
- Changing the `to_events()` schema beyond the three fields specified in Patch A
- Adding any new `[verify]` extra dependency beyond `spot`
- Modifying `council/core.py` beyond the intervention-honour loop described in this spec
- Changing `ProvenanceReceipt` fields (affects Constitution §11 contract)
- Extending `TerminationStrategy.should_stop()` signature

**Never do:**
- Import `council/core.py` from any `council/symbolic/verify/` module
- Import `evaluation/`, `experiments/`, or `apps/` from `council/`
- Call a generation model from `council/symbolic/verify/` (except `EscalateModel.execute()` which calls `ctx.model_client.complete()` — this is the boundary)
- Use `import lark` or any parser-generator library in the core path
- Run MCMAS/NuSMV as a subprocess from `council/` — only from `tests/integration/`
- Add a `spot` conda-install instruction anywhere — pip or system packages only

---

## Patch A — `to_events()` extension (ADR 0002)

The three derived boolean APs are computed inside `to_events()` with a single pass over `self.moves` up to each move's index:

| New AP key | Type | Semantics |
|---|---|---|
| `has_evidence` | `bool` | `True` for `Propose` and `Vote` moves whose `claim`/`option` has `evidence != ()` |
| `has_prior_challenge` | `bool` | `True` if any `Challenge` move appears strictly before this move in the trace |
| `same_agent_concede_run_ge_3` | `bool` | `True` if this move is a `Concede` AND both of the immediately preceding moves (regardless of round) from the same `agent_id` are also `Concede` |

All three are computed purely from `self.moves` — no model calls, no external state. The "frozen after W0/PR3" docstring comment is updated to "extended in W1/PR1 — add has_evidence, has_prior_challenge, same_agent_concede_run_ge_3".

---

## Patch B — `tool_client` on `CouncilContext`

```python
# council/context.py (addition only)
from council.tools import ToolClient   # already exists as W0 stub

@dataclass(frozen=True, slots=True)
class CouncilContext:
    agents: tuple[str, ...]
    model_client: ModelClient
    protocol: object
    topology: Topology
    termination: TerminationStrategy
    anonymize: bool = True
    original_question: str = ""
    tool_client: ToolClient | None = None   # NEW — needed by TriggerVerifier (W1)
```

All existing `CouncilContext(...)` call sites omit `tool_client` → default `None`. No callsite changes required.

---

## PR sequence and acceptance criteria

| # | Branch slug | Key deliverable | Acceptance test |
|---|---|---|---|
| 0a | (patch, no own branch — part of PR1) | `to_events()` extended | `test_trace_derived_aps.py` |
| 0b | (patch, no own branch — part of PR1) | `tool_client` on `CouncilContext` | existing tests still pass |
| 1 | `ns-w1-ltlf-ast` | `ltlf.py`: 9 AST nodes + `parse()` + `to_spot_str()` | 20+ round-trip tests |
| 2 | `ns-w1-ltl3-monitor` | `monitor.py`: `LTL3Monitor` ABC + `Verdict` enum + `PurePythonLTL3Monitor` (safety+reachability) | step/reset/absorbing tests |
| 3 | `ns-w1-ltl2mon-backend` | `ltl2mon_backend.py`: `progression()` + `ProgressionMonitor` (full LTL_f) | cross-validates with PR2 monitor |
| 4 | `ns-w1-spot-backend` | `spot_backend.py`: `SPOTMonitor` + `make_monitor()` | skipif SPOT absent; agrees with PR3 on same traces |
| 5 | `ns-w1-properties` | `properties.py`: 10 named `Property` subclasses + `PROPERTY_REGISTRY` | +/- trace per property; registry contains all 10 |
| 6 | `ns-w1-ispl-mcmas` | `ispl.py` + `smv.py` text emitters | structural string tests + integration test |
| 7 | `ns-w1-interventions` | `interventions.py`: `Intervention` ABC + 5 impls | `FakeModelClient`-based tests; no real model |
| 8 | `ns-w1-ltlf-termination` | `LTLfMonitorTermination` + `core.py` wiring + `receipt.monitor_verdicts` | end-to-end `run_council()` populates receipt |
| 9 | `ns-w1-theorems` | `docs/theory.md` (T1–T3) + `test_theorems.py` | pytest passes; theory.md has §T1, §T2, §T3 |

---

## SPOT and MCMAS installation documentation

`docs/install_spot.md` (created in PR4) will cover:

- **SPOT** (required for `[verify]` extra):
  - Ubuntu 22.04+: `sudo apt install spot python3-spot`
  - Arch: `yay -S spot`
  - macOS (Homebrew): `brew install spot` then `pip install spot` (if wheel available)
  - From source: `./configure && make && make install` per [spot.lre.epita.fr](https://spot.lre.epita.fr/install.html)
  - Verification: `python -c "import spot; print(spot.version())"`
- **MCMAS** (required only for `RUN_INTEGRATION=1` tests):
  - Binary download from [mcmas.org.uk](https://mcmas.org.uk) (Linux x86_64 and macOS available)
  - Add to `PATH`; verify: `mcmas --version`
- **NuSMV** (optional, for SMV-format offline checking):
  - `sudo apt install nusmv` or download from [nusmv.fbk.eu](https://nusmv.fbk.eu)

---

## Success Criteria

- [ ] `uv run mypy council/` exits 0 — no new errors introduced by W1
- [ ] `uv run pytest tests/symbolic/` passes — all W1 unit tests green
- [ ] `uv run pytest tests/` passes — no W0 regressions
- [ ] 10 named properties in `PROPERTY_REGISTRY`, each with a positive and negative trace test
- [ ] `make_monitor(parse("F is_vote"), prefer_spot=False)` returns a `ProgressionMonitor` with no import error
- [ ] `make_monitor(parse("F is_vote"), prefer_spot=True)` returns `SPOTMonitor` when SPOT installed, `ProgressionMonitor` when not — no exception in either case
- [ ] End-to-end `run_council()` test with `LTLfMonitorTermination([EventuallyDecide()])` and a trace that lacks a Vote move returns `(True, "EventuallyDecide")` from `should_stop`, fires `ForceChallenge`, and the resulting `ProvenanceReceipt.monitor_verdicts` is non-empty
- [ ] `ProvenanceReceipt.is_complete()` returns `False` when `monitor_verdicts` is empty and a monitor was active (extended check)
- [ ] `docs/theory.md` exists with sections `## T1 — Soundness`, `## T2 — Compositionality`, `## T3 — No-go for consensus-only` each with a theorem statement, proof sketch, and citation
- [ ] `docs/install_spot.md` exists with pip/apt/brew/source instructions
- [ ] `specs/adrs/0002-w1-to-events-extension.md` exists documenting the Patch A decision

## Open Questions

None — all four decisions from the workstream-planner review have been resolved:

1. **`to_events()` extension** → Option A (extend with derived booleans); captured in ADR 0002.
2. **`tool_client` on `CouncilContext`** → add `tool_client: ToolClient | None = None`.
3. **PR3 vs PR4 order** → ltl2mon-backend first (PR3), then spot-backend (PR4).
4. **Deadline pressure** → none; follow the full plan.
