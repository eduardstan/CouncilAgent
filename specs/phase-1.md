# Spec: CouncilAgent — Phase 1 (Core Abstractions)

**Status**: Draft → pending human approval
**Branch family**: `feature/p1-<slug>`
**Authoritative references**:
- [.claude/CLAUDE.md](../.claude/CLAUDE.md) — Constitution, tech stack, layered architecture
- [.claude/rules/architecture.md](../.claude/rules/architecture.md) — layer responsibilities, forbidden imports
- [.claude/rules/code-style.md](../.claude/rules/code-style.md) — Python style, error handling, LLM call rules
- [.claude/rules/testing.md](../.claude/rules/testing.md) — test framework, required tests per layer, regressions
- [LLMCouncil_Deep_Review.md](../LLMCouncil_Deep_Review.md) — Part II (issues), Part IV (phased roadmap)

This spec does **not** duplicate the rules files. It adds only what is new for Phase 1.

---

## 1. Objective

Build the correct skeleton of the CouncilAgent pipeline: a pure, framework-free async core that composes pluggable `Topology`, `Protocol`, `Ranking`, `Aggregation`, `Normalizer`, and `ModelClient` layers per the Constitution (§3, §8).

Phase 1 is **not** a working agent. It is the foundation that makes `run_council(prompt, ...) → CouncilResult` correct for a single round and the first multi-round deliberation (PeerReview), with structured output and anonymization enforced end-to-end. `CouncilAgent.complete()`, termination strategies, and escalation are Phase 2/3 work.

### Users / Callers (Phase 1 scope)
- **Future Phase 2/3 code** that will wrap `run_council` into `CouncilAgent.complete()`.
- **Integration tests** and **experiments** that exercise the pipeline directly.
- **Not end users.** Phase 1 is not shipped to anyone.

### Success Criteria (testable, specific)
1. `run_council(prompt, 3 agents, ring topology, direct answer, majority vote, max_rounds=1)` returns a `CouncilResult` whose `final_answer`, `confidence`, `total_cost`, `tokens_in`, `tokens_out`, and `round_history` are all populated, using only `FakeModelClient`.
2. With `PeerReviewProtocol` + `max_rounds=2`, round 1 prompts contain critique framing and round 2 prompts contain revision framing. Verified via a spy/capture fixture on `Protocol.build_prompt`.
3. With `RingTopology(4)` + `max_rounds=2`, agent `i` at round 1 sees exactly one response: agent `(i-1) % 4`. Verified via spy on `VisibilityContext`.
4. With `anonymize=True`, no real agent_id string appears in any prompt string passed to `ModelClient.complete`. Verified via a parametrized test over **every** `Protocol` subclass (testing.md Issue 6 regression).
5. `StructuredRanking.extract('{"ranking": ["A","B"], "scores": {"A":9,"B":5}}', ["A","B"])` returns a `RichPreference` with correct fields; malformed JSON falls back without raising (testing.md Issue 4 regression).
6. `MajorityVote` over `AgentResponse` contents `["The answer is 72.", "72", "answer: 72"]` (using `StructuredOutputNormalizer`) returns "72" with `confidence == 1.0` (testing.md Issue 3 regression).
7. `StarTopology(n).get_adjacency_matrix(0) == StarTopology(n).get_adjacency_matrix(1)` — pure relay, no round parity (architecture rule).
8. `import council.core` succeeds in a venv with **no** `langgraph`, `hydra`, `mlflow`, `opentelemetry`, or `langchain*` installed (Constitution §8).
9. `mypy --strict` passes for `council/context.py`, `council/core.py`, `council/agent.py` (agent.py may be empty or a stub in Phase 1 — still passes).
10. `uv run pytest tests/council/ -q` green with ≥ 85% line coverage on `council/` (target from testing.md).

---

## 2. Tech Stack

- **Python**: 3.11 (floor). Dev environment uses 3.12.3.
- **Package manager**: stdlib `venv` + `pip`. `pyproject.toml` declares deps; `.venv/` is local (gitignored). No `uv` for now; may revisit later.
- **Async**: `asyncio` (stdlib). `asyncio.gather` for fan-out; never `ThreadPoolExecutor`.
- **Model backends** (pluggable behind `ModelClient`):
  - `LiteLLMClient` — wraps the `litellm` library (covers OpenAI, Anthropic, Google, Groq, etc.)
  - `OpenRouterClient` — direct `httpx` calls to `https://openrouter.ai/api/v1`. Does **not** go through `litellm`. Auth: `OPENROUTER_API_KEY` env var only (no referer/title headers in Phase 1).
  - `OllamaClient` — direct `httpx` calls to local Ollama daemon (default `http://localhost:11434`). No auth. Cost always `0.0`.
  - `RoutingModelClient` — dispatches by model-prefix: `openrouter/*` → OpenRouter, `ollama/*` → Ollama, else → LiteLLM. Owns a dict of backend instances.
- **Cost estimation**:
  - `OpenRouterClient`: fetches `/api/v1/models` once at first call, caches in-process. Falls back to `0.0` with a `WARNING` log if fetch fails.
  - `LiteLLMClient`: reads `litellm.model_cost` dict.
  - `OllamaClient`: always `0.0`.
- **HTTP**: `httpx` (async). Used only inside `council/models.py`.
- **Logging**: stdlib `logging`. Loggers named `council.<module>`. No `structlog` in Phase 1.
- **Testing**: `pytest`, `pytest-asyncio` (mode=auto), `pytest-cov`, `freezegun`, `pytest-mock`.
- **Lint**: `ruff` (line length 100, target-version `py311`).
- **Type check**: `mypy` — strict scope = `council/context.py`, `council/core.py`, `council/agent.py`. Non-strict elsewhere in Phase 1.
- **Forbidden in Phase 1 deps**: `langgraph`, `hydra`, `mlflow`, `opentelemetry`, `langchain*`. These belong in Phase 3/4 edges.

### Environment variables
| Var | Required | Purpose |
|-----|----------|---------|
| `OPENROUTER_API_KEY` | When using `OpenRouterClient` | Bearer auth |
| `OPENAI_API_KEY` | When routing an `openai/*` model via LiteLLM | LiteLLM reads this itself |
| `ANTHROPIC_API_KEY` | When routing an `anthropic/*` model via LiteLLM | LiteLLM reads this itself |
| `RUN_INTEGRATION` | `1` to enable `tests/integration/` | Gates real-model tests |

Committed: `.env.example` with names only (no values). Gitignored: `.env`.

### Deferred to later phases (explicitly not in Phase 1)
- **Response cache** — `ModelClient` caching is out of scope. `FakeModelClient` makes tests deterministic; a real cache is Phase 2 work. `models.py` must include a `# TODO(phase-2): response cache` comment at the class level of each real backend, and the Phase 2 spec will reference it.
- **Retry / fault injection** — `max_retries` parameter is accepted but implemented as a no-op with a `# TODO(phase-2)` flag. A single attempt; any failure → `ModelFailure`.
- **`TerminationStrategy`** — Phase 1 uses a fixed `max_rounds: int` parameter on `run_council`. No pluggable termination.
- **`CouncilAgent`, `CouncilPolicy`, `TaskProfile`** — Phase 3.
- **`MetaJudge`, `BordaCount`, `Condorcet`, `Copeland`** — stubs raising `NotImplementedError`. Full impls in Phase 3.
- **Evaluation layer** (`evaluation/`) — Phase 4.

---

## 3. Commands

All commands assume the venv is active (`source .venv/bin/activate`) or use explicit `.venv/bin/` paths.

```bash
# Initial setup (Task P0)
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

# Run all Phase 1 tests
.venv/bin/pytest tests/council/ -q

# With coverage
.venv/bin/pytest tests/council/ --cov=council --cov-report=term-missing

# Single test file
.venv/bin/pytest tests/council/test_topology.py -q

# Integration tests (requires real API keys)
RUN_INTEGRATION=1 .venv/bin/pytest tests/integration/ -q

# Lint
.venv/bin/ruff check council/ tests/
.venv/bin/ruff format council/ tests/

# Type check (strict scope only)
.venv/bin/mypy council/context.py council/core.py council/agent.py

# Forbidden-imports check (ad-hoc until Phase 4 CI)
.venv/bin/python -c "import council.core, sys; \
  assert not any(m.startswith(('langgraph','hydra','mlflow','opentelemetry','langchain')) for m in sys.modules), \
  'framework leaked into council.core'"
```

---

## 4. Project Structure (Phase 1 delta only)

Only files that exist **by end of Phase 1** are listed. Files flagged `(stub)` exist but are empty or contain only a module docstring + `__all__ = []`.

```
CouncilAgent/
├── pyproject.toml                    # Task P0
├── .env.example                      # Task P0
├── .gitignore                        # Task P0 (adds .venv/)
├── conftest.py                       # Task P0 — pytest-asyncio config
├── specs/
│   └── phase-1.md                    # this file (Task P0)
├── council/
│   ├── __init__.py                   # Task P0 → re-exports run_council after Task 1.8
│   ├── context.py                    # Task 1.1
│   ├── models.py                     # Task 1.2
│   ├── topology.py                   # Task 1.3
│   ├── normalizer.py                 # Task 1.4
│   ├── ranking.py                    # Task 1.5
│   ├── aggregation.py                # Task 1.6
│   ├── protocol.py                   # Task 1.7
│   ├── core.py                       # Task 1.8
│   └── agent.py                      # (stub) — Phase 3 owns this
└── tests/
    ├── __init__.py
    ├── council/
    │   ├── __init__.py
    │   ├── test_context.py           # Task 1.1
    │   ├── test_models.py            # Task 1.2
    │   ├── test_topology.py          # Task 1.3
    │   ├── test_normalizer.py        # Task 1.4
    │   ├── test_ranking.py           # Task 1.5
    │   ├── test_aggregation.py       # Task 1.6
    │   ├── test_protocol.py          # Task 1.7
    │   ├── test_core.py              # Task 1.8
    │   └── test_integration.py       # Task 1.9 (pipeline smoke)
    └── integration/
        ├── __init__.py
        └── conftest.py               # skip-unless-RUN_INTEGRATION marker
```

**Not created in Phase 1**: `council/policy.py`, `council/termination.py`, `council/task_profile.py`, `council/adapters/`, `evaluation/`, `experiments/`, `tasks/`, `analysis/`, `configs/`.

---

## 5. Code Style

Full rules: [.claude/rules/code-style.md](../.claude/rules/code-style.md). Phase 1 highlight — here is the canonical shape of a layer module:

```python
# council/topology.py
"""Communication graphs. Pure — no prompts, no model calls, no privileged agents."""
from __future__ import annotations

from abc import ABC, abstractmethod

from council.context import CommunicationMode


class Topology(ABC):
    communication_mode: CommunicationMode

    def __init__(self, num_agents: int) -> None:
        if num_agents < 2:
            raise ValueError(f"num_agents must be >= 2, got {num_agents}")
        self.num_agents = num_agents

    @abstractmethod
    def get_adjacency_matrix(self, round_index: int) -> list[list[bool]]: ...


class CompleteGraphTopology(Topology):
    communication_mode = CommunicationMode.INDIVIDUAL

    def get_adjacency_matrix(self, round_index: int) -> list[list[bool]]:
        n = self.num_agents
        return [[i != j for j in range(n)] for i in range(n)]
```

Key invariants (restated for emphasis):
- Every layer module imports **only** from `council.context` (and stdlib). Not from each other.
- No `print()`. No comments explaining *what* the code does. Only `why`-comments for non-obvious invariants.
- All I/O functions are `async def`.
- Frozen `@dataclass(frozen=True, slots=True)` for value objects crossing function boundaries.

---

## 6. Testing Strategy

Full rules: [.claude/rules/testing.md](../.claude/rules/testing.md).

### Phase 1 test matrix

| Layer | Test file | Minimum coverage obligations |
|-------|-----------|------------------------------|
| context | `test_context.py` | frozen-ness, field defaults, `CouncilState.initial()` |
| models | `test_models.py` | `FakeModelClient` determinism, `RoutingModelClient` prefix dispatch (mocked backends), `OpenRouterClient` auth header (mocked httpx), `OllamaClient` URL shape (mocked httpx) |
| topology | `test_topology.py` | `get_adjacency_matrix(0)` and `(1)`, symmetry where expected, `StarTopology` no-round-parity, `communication_mode` per class |
| normalizer | `test_normalizer.py` | table-driven `(raw, canonical)` pairs incl. JSON, plain, numeric, malformed; **Issue 3 regression** |
| ranking | `test_ranking.py` | `StructuredRanking` JSON primary / regex fallback; **Issue 4 regression** |
| aggregation | `test_aggregation.py` | `MajorityVote` with normalizer; confidence math; **Issue 3 regression (confidence == 1.0)** |
| protocol | `test_protocol.py` | prompt markers per round, schema injection, **Issue 6 parametrized regression** over all `Protocol` subclasses |
| core | `test_core.py` | 4-point core-pipeline test from testing.md (all agents in round 0, adjacency respected in round 1, aggregation non-null, tokens>0), anonymization end-to-end, `ModelFailure` partial-result handling |
| integration | `test_integration.py` | 3-agent 2-round PeerReview smoke, ring visibility, anonymization E2E, structured-output round-trip |

### Regressions from the deep review included in Phase 1
- **Issue 3** — `MajorityVote` confidence on normalized responses. Task 1.6.
- **Issue 4** — `StructuredRanking.extract` success + malformed fallback. Task 1.5.
- **Issue 6** — No real `agent_id` in any protocol prompt when `anonymize=True`. Tasks 1.7 + 1.8, parametrized across all `Protocol` subclasses.

**Deferred**: Issue 9 (`task_accuracy`, belongs to Phase 4 evaluation). Issue 10 (`AgreementThreshold`, belongs to Phase 2 termination).

### Test doubles
- `FakeModelClient` lives in `council/models.py` (canonical). Constructor takes `dict[tuple[str, int], str]` keyed by `(agent_id, round_index)`, or a callable `(request, agent_id, round_index) -> str`. Deterministic; never random.
- No real models in `tests/council/`. Real calls only in `tests/integration/`, gated by `@pytest.mark.integration` and `RUN_INTEGRATION=1`.

### Determinism
- Every test using randomness seeds it in a fixture (`random.seed(0)`, etc.).
- Time-dependent code injects a `clock: Callable[[], datetime]` or uses `freezegun`. None expected in Phase 1.

---

## 7. Boundaries

### Always
- Follow the Constitution (CLAUDE.md §Constitution). Violations require explicit user approval.
- Respect layer boundaries per [.claude/rules/architecture.md](../.claude/rules/architecture.md). Layer modules import only from `council.context`.
- Anonymization lives **only** in `council/core.py::_build_visibility_context`. Nowhere else.
- `StructuredOutputNormalizer` tries `json.loads` first; regex is a fallback.
- Every `ModelClient` call path returns `AgentResponse | ModelFailure`. Never raise up to the pipeline.
- Seed randomness in tests.
- Run `.venv/bin/pytest`, `.venv/bin/ruff check`, `.venv/bin/mypy` locally before asking for review on any `feature/p1-*` branch.
- Use `TDD` per session: RED → GREEN → REFACTOR. Spec first (this file), test second, code third.

### Ask first
- Adding any dependency not in the Tech Stack list above.
- Changing Python floor from 3.11.
- Introducing a new layer module or a helper that crosses existing layers.
- Adding a new subclass to a Phase 2+ abstraction (e.g. a second `Aggregation`, a new `Protocol`).
- Weakening a Constitution principle for a "pragmatic" reason.
- Any deviation from the spec that affects success criteria §1.

### Never
- `import litellm`, `import httpx`, or any provider SDK outside `council/models.py`.
- `import langgraph | hydra | mlflow | opentelemetry | langchain*` in `council/core.py`, `council/agent.py`, `council/policy.py`.
- Port code from `../LLMCouncil/`. Reference-only.
- Commit `.env` or any API key.
- Add regex as the primary answer extraction path.
- Add `print()` calls. Use `logging` at `DEBUG`.
- Use `except Exception: pass`.
- Use substring matching for answer comparison.
- Hardcode model names outside `configs/` and tests.
- Force-push `develop` or `main`.
- Skip or disable a failing test to get a green suite.

---

## 8. Phase 1 Task List

Ordered. Each task = one branch = one PR merged into `develop`.

| # | Task | Branch | Depends on | Size |
|---|------|--------|------------|------|
| P0 | Foundation: pyproject, conftest, skeleton, this spec | `develop` (direct) | — | XS |
| 1.1 | `context.py` — `VisibilityContext`, `CommunicationMode`, `AgentResponse`, `CouncilState`, `CouncilResult`, `AggregationResult` | `feature/p1-visibility-context` | P0 | S |
| 1.2 | `models.py` — `ModelClient` ABC, `FakeModelClient`, `LiteLLMClient`, `OpenRouterClient`, `OllamaClient`, `RoutingModelClient` | `feature/p1-model-client` | 1.1 | M |
| 1.3 | `topology.py` — `Complete`, `Star` (pure relay), `DynamicStar`, `Bus`, `Ring` | `feature/p1-topology` | 1.1 | S |
| 1.4 | `normalizer.py` — `StructuredOutputNormalizer`, `IdentityNormalizer` | `feature/p1-normalizer` | 1.1 | S |
| 1.5 | `ranking.py` — `StructuredRanking`, `RegexOrdinalRanking`, `NullRanking`, `RichPreference` | `feature/p1-ranking` | 1.1 | S |
| 1.6 | `aggregation.py` — `MajorityVote`, stubs for `BordaCount`/`MetaJudge` | `feature/p1-aggregation` | 1.1, 1.4, 1.5 | S |
| 1.7 | `protocol.py` — `DirectAnswer`, `PeerReview` (alternating critique/revision), `Simultaneous` (sliding window) | `feature/p1-protocol` | 1.1, 1.5 | M |
| 1.8 | `core.py` — `run_council`, `_build_visibility_context`, `_generate`, `_deliberate`, `_aggregate` | `feature/p1-core-pipeline` | 1.1–1.7 | L |
| 1.9 | `test_integration.py` — 4 end-to-end smoke tests | `feature/p1-integration-test` | 1.8 | M |

Tasks 1.2–1.6 may run in parallel on separate branches after 1.1 lands. 1.7 → 1.8 → 1.9 are strictly sequential.

Per-task acceptance criteria, test obligations, Constitution risks, and file lists are in the plan produced by the `phase-planner` agent (earlier in this conversation). This spec defines **what "done" means for Phase 1 overall**; the plan defines the *how* for each task.

---

## 9. Open Questions

None blocking. Answered during spec drafting:
- ✅ Multiple backends (OpenRouter, LiteLLM, Ollama) behind a `RoutingModelClient`.
- ✅ Single `OPENROUTER_API_KEY` env var; no attribution headers.
- ✅ Cost source: provider-appropriate (OpenRouter `/models` fetch, LiteLLM `model_cost`, Ollama zero).
- ✅ Response cache deferred to Phase 2 — flagged with `TODO(phase-2)` in each backend.
- ✅ This spec covers all of Phase 1; Phase 2 will have its own spec.

Reopen this section if any answer changes during implementation.
