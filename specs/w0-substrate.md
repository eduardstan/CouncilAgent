# Spec: W0 Substrate — Typed Move Algebra, Protocol Automata, Pure-Async Pipeline

**Branch:** `council-ns` → feature branches `feature/ns-w0-*`
**Milestone:** M1 (end May 2026)
**Workstream:** W0 (L0 only — no L1–L6 wired)
**Status:** APPROVED — proceed to implementation

---

## Objective

Build the `council/` Python package from scratch on `council-ns`. This is the typed substrate that every downstream workstream (W1–W7) depends on. It must be correct, strictly typed, and framework-free before any symbolic layer is attached.

**What we are building:**
- A typed `Move` ADT (8 variants) and immutable `Trace` with O(1) lookups
- A `ProtocolAutomaton` ABC and 5 concrete automata (deliberation, persuasion, inquiry, composite, socratic)
- Parsers (LLM output → `Move`) and surface renderers (`Move` → NL)
- `ModelClient` (LiteLLM wrapper, cache, meter, retry, fault-inject)
- `ToolClient` skeleton (MCP / Z3 / clingo / Lean stubs)
- `Topology` hierarchy + `CommunicationMode` enum
- `CouncilContext`, `CouncilResponse`, `ProvenanceReceipt`, `Confidence` tagged union
- `run_council()` pure-async pipeline + `CouncilAgent.complete()` interface
- `CouncilPolicy` skeleton (QD archive lookup stubbed)
- `TerminationStrategy` ABC + `CompositeTermination` + `FixedRounds`
- `tasks/profiles.py` task-profile registry (GSM8K seed)
- Full test suite: no real model calls; `FakeModelClient` throughout

**Why:** Every downstream layer (L1 monitors, L2 argumentation, L3 calibration, L4 cascade, L5 QD, L6 ILP) depends on the `Move`/`Trace`/`ProtocolAutomaton` contracts being frozen. Getting them wrong means cascading rework across all workstreams and all 5 papers.

**Success looks like:**
- `uv run python -c "import council"` succeeds with no optional extras installed
- `uv run mypy council/` → zero errors
- `uv run pytest tests/` → all pass, ≥ 85 % line coverage on `council/`
- `uv run pytest tests/dialect/` passes in < 5 s (no model calls)
- A 3-agent 2-round end-to-end run with `FakeModelClient` produces a `CouncilResponse` with a non-null `ProvenanceReceipt`

---

## Tech Stack

- **Python 3.11+** — `from __future__ import annotations` only for forward refs
- **asyncio** — all I/O-touching functions are `async def`; `asyncio.gather` for fan-out
- **LiteLLM** — only in `council/models.py`; never imported anywhere else in `council/`
- **mypy --strict** — enforced on all of `council/`
- **ruff** — line-length 100, `E/F/W/I/B/UP/SIM/RUF` rules
- **pytest + pytest-asyncio** (mode=auto) — all tests async-safe
- **uv** — package manager (`uv run <cmd>`)
- **Zero framework deps in core** — no `langgraph`, `hydra`, `mlflow`, `opentelemetry`, `langchain`, `pyribs`, `spot`, `clingo` in any `council/` module (optional-extra guards where needed)

---

## Commands

```bash
# Install dev dependencies
uv sync --extra dev

# Run all unit tests
uv run pytest tests/ -x -q

# Run a single workstream slice
uv run pytest tests/dialect/ -x -q

# Run integration tests (real models)
RUN_INTEGRATION=1 uv run pytest tests/integration/ -x -q

# Type-check
uv run mypy council/

# Lint + format check
uv run ruff check council/ tests/
uv run ruff format --check council/ tests/

# Coverage
uv run pytest tests/ --cov=council --cov-report=term-missing

# Verify zero framework imports in core
python -c "import council.core, council.agent, council.policy, council.dialect.moves, council.dialect.trace"
```

---

## Project Structure

```
council/                        ← new package (created in W0)
  __init__.py                   ← re-exports CouncilAgent, CouncilResponse
  agent.py                      ← CouncilAgent.complete() — drop-in LLM interface
  core.py                       ← run_council() pure-async pipeline
  context.py                    ← frozen dataclasses: CouncilContext, CouncilState,
                                   CouncilResponse, ProvenanceReceipt, Confidence union
  policy.py                     ← CouncilPolicy: (prompt, TaskProfile, budget) → CouncilGenome
  models.py                     ← ModelClient (LiteLLM wrapper only)
  tools.py                      ← ToolClient skeleton (MCP/Z3/clingo/Lean stubs)
  topology.py                   ← CommunicationMode enum + topology hierarchy
  normalizer.py                 ← answer normalisation (port from legacy)
  ranker.py                     ← response ranking (port from legacy)
  termination.py                ← TerminationStrategy ABC + CompositeTermination + FixedRounds

  dialect/                      ← L0 speech-act algebra
    __init__.py
    moves.py                    ← Move ADT (Propose|Challenge|Concede|Retract|Question|Clarify|Vote|Abstain)
    trace.py                    ← immutable Trace + to_events() bridge
    parsers.py                  ← LLM output → Move (JSON schema + argument-mining fallback)
    surface.py                  ← Move → NL rendering (domain-conditioned)
    protocols/
      __init__.py
      base.py                   ← ProtocolAutomaton ABC
      deliberation.py           ← DeliberationAutomaton (Walton 2010)
      persuasion.py
      inquiry.py
      composite.py
      socratic.py

  symbolic/                     ← L1–L6 namespace (stubs only in W0)
    __init__.py
    verify/__init__.py          ← L1 stub
    argue/__init__.py           ← L2 stub
    ilp/__init__.py             ← L6 stub

  calibrate/__init__.py         ← L3 stub
  cascade/__init__.py           ← L4 stub
  evolve/__init__.py            ← L5 stub (CouncilGenome lives here at W5; stub in W0)
  adapters/__init__.py          ← LangGraph / OTel adapters (empty in W0)

tasks/
  __init__.py
  profiles.py                   ← TaskProfile dataclass + GSM8K seed registration

tests/
  conftest.py                   ← FakeModelClient, shared fixtures
  __init__.py
  dialect/
    __init__.py
    test_moves.py
    test_trace.py
    test_parsers.py
    test_surface.py
    test_protocol_base.py
    test_deliberation_automaton.py
    test_legacy_protocol_isomorphism.py
    test_other_automata.py
  test_models.py
  test_topology.py
  test_core.py
  test_agent.py
  test_termination.py
  integration/
    __init__.py
    test_gsm8k_parity.py        ← gated: @pytest.mark.integration + RUN_INTEGRATION=1

specs/
  w0-substrate.md               ← this file
  adrs/                         ← architectural decision records (created as needed)
```

---

## Code Style

All code in `council/` follows `.claude/rules/code-style.md`. Key points:

```python
# Frozen value objects — no mutable state
@dataclass(frozen=True, slots=True)
class Propose:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.PROPOSE
    claim: Claim = field(default_factory=lambda: Claim(surface=""))
    confidence: float = 0.5

# ABCs via abc.ABC + @abstractmethod — no protocol classes
class ProtocolAutomaton(ABC):
    @abstractmethod
    def state(self, trace: Trace) -> tuple[str, str]: ...

# Async I/O only — never ThreadPoolExecutor
async def run_council(prompt: str, genome: CouncilGenome, ...) -> CouncilResponse: ...

# Typed union — no Optional[Move], no Any
Move = Union[Propose, Challenge, Concede, Retract, Question, Clarify, Vote, Abstain]
Confidence = JSDConfidence | BAFMarginConfidence | MonitorVerdictConfidence | CopelandConfidence
```

Naming:
- Modules: `snake_case.py`
- Classes: `PascalCase`; abstract bases end in role noun (`ProtocolAutomaton`, `TerminationStrategy`)
- Constants: `UPPER_SNAKE`
- Private helpers: `_leading_underscore`

No `print()` — use `logging.debug`. No hardcoded model names in `council/`. No `from x import *`.

---

## Testing Strategy

- **Framework:** pytest + pytest-asyncio (mode=auto)
- **No real model calls in `tests/`** — `FakeModelClient` in `conftest.py` returns pre-canned `AgentResponse` keyed by prompt hash
- **Integration tests** in `tests/integration/` gated by `@pytest.mark.integration` + `RUN_INTEGRATION=1` env var
- **Determinism:** `random.seed(0)` / `np.random.seed(0)` in fixtures; `FakeModelClient` is deterministic
- **Coverage target:** ≥ 85 % line on `council/`; `council/core.py` + `council/agent.py` target 95 %
- **Regression pins** (per `.claude/rules/testing.md`): anonymisation consistency, smart matcher, agreement threshold

Per-module test requirements:
| Module | Required tests |
|---|---|
| `moves.py` | Immutability, union exhaustiveness, Claim round-trip |
| `trace.py` | by_id, at_round, by_force, append, to_events schema |
| `parsers.py` | Table-driven: all 5 main forces; malformed JSON → fallback tagged `tier="argument-mining-fallback"` |
| `surface.py` | All 8 Move variants render non-empty; anonymisation regression |
| `protocols/base.py` | ABC contract; missing method → TypeError |
| `protocols/deliberation.py` | Empty trace forces, answer-phase derivation (no round-parity hack), terminal detection |
| `topology.py` | adjacency(0), adjacency(1), symmetry, communication_mode |
| `core.py` | 3-agent 2-round FakeModelClient run; adjacency respected; confidence is tagged Confidence type |
| `termination.py` | FixedRounds boundary, CompositeTermination OR-semantics |

---

## Boundaries

**Always do:**
- Run `uv run mypy council/` before marking any PR done
- Run `uv run pytest tests/dialect/` (and the relevant test file) before merging each PR
- Emit `ProvenanceReceipt` on every `run_council()` call — even sparse (W0 has no QBAF/monitors)
- Use `CopelandConfidence` as the W0 confidence type (lowest in hierarchy; §5 derivation)
- Keep `_build_visibility_context()` as the **single** anonymisation site in `council/core.py`

**Ask first:**
- Any change to the `Trace.to_events()` event dict schema (W1 compiles LTL_f against it — schema freeze matters)
- Any change to `ProtocolAutomaton` ABC method signatures (all concrete automata and W1 hooks depend on them)
- Adding a new optional dependency to `pyproject.toml`
- Changing `CouncilGenome` field names or types (W5 QD depends on them)

**Never do:**
- Import from `legacy_council/` in any `council/` module
- Use `round_index % 2` as a protocol predicate in `core.py` or `agent.py` (D8 fix — use `automaton.is_answer_phase(trace)`)
- Leave `AgentResponse.move: Move | None` — it must be `Move` (non-optional) from PR 2 onward
- Import `langgraph`, `hydra`, `mlflow`, `opentelemetry`, `langchain`, `pyribs`, `spot`, `clingo` in any `council/` module without an optional-extra guard
- Use `Counter(r.content)` or substring match on raw LLM output — always normalise first
- Commit with failing mypy or failing unit tests

---

## Key Contracts (frozen after each PR)

```python
# After PR2 — frozen
Move = Union[Propose, Challenge, Concede, Retract, Question, Clarify, Vote, Abstain]
Force(StrEnum)  # 9 values including PASS

# After PR3 — frozen (W1 compiles LTL_f against to_events() schema)
class Trace:
    def to_events(self) -> tuple[dict[str, object], ...]:
        # Each dict: {"force": str, "agent_id": str, "round_index": int,
        #             "is_propose": bool, "is_challenge": bool, ..., "is_abstain": bool}

# After PR5 — frozen (all concrete automata + W1 hooks depend on this)
class ProtocolAutomaton(ABC):
    def state(self, trace: Trace) -> tuple[str, str]: ...
    def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]: ...
    def is_terminal(self, trace: Trace) -> bool: ...
    def is_answer_phase(self, trace: Trace) -> bool: ...

# After PR10 — frozen (W1–W7 all depend on these)
Confidence = JSDConfidence | BAFMarginConfidence | MonitorVerdictConfidence | CopelandConfidence

class CouncilResponse:
    answer: str
    confidence: Confidence   # NEVER a raw float
    receipt: ProvenanceReceipt
    cost_usd: float

async def run_council(
    prompt: str,
    genome: CouncilGenome,
    model_client: ModelClient,
    *,
    context: CouncilContext | None = None,
) -> CouncilResponse: ...
```

---

## Success Criteria

- [ ] `uv run python -c "import council"` — no ImportError, no optional-extra required
- [ ] `uv run mypy council/` — zero errors, zero `# type: ignore` in non-stub code
- [ ] `uv run pytest tests/ -x -q` — all pass, zero real model calls
- [ ] `uv run pytest tests/ --cov=council --cov-report=term-missing` — ≥ 85 % line coverage
- [ ] `uv run ruff check council/ tests/` — zero violations
- [ ] 3-agent 2-round `FakeModelClient` run produces `CouncilResponse` with typed `Confidence` and non-null `ProvenanceReceipt`
- [ ] `ProvenanceReceipt.trace` is a non-empty `Trace` with at least 3 moves (1 per agent, round 0)
- [ ] `_build_visibility_context` is the only place in `council/` that strips agent IDs
- [ ] No `round_index % 2` in `core.py` or `agent.py` — only `automaton.is_answer_phase(trace)`
- [ ] `Trace.to_events()` emits the boolean-flag schema that W1 will compile LTL_f against
- [ ] `AgentResponse.move` is `Move` (non-optional) everywhere
- [ ] `CouncilResponse.confidence` is one of the 4 tagged `Confidence` types (plurality fraction impossible)

---

## Open Questions

None — all clarified by the workstream-planner output and bible (COUNCIL_NS_PLAN.md §6.1).
The `CouncilGenome` stub in W0 will be a minimal frozen dataclass; W5 will replace it with the full QD-search genome.
