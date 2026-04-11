# Testing Rules

## Framework
- `pytest` + `pytest-asyncio` (mode = `auto`).
- Test files live under `tests/`, mirroring the package layout: `tests/council/test_topology.py`, `tests/evaluation/test_metrics.py`.
- One test file per source module. One `Test<ClassName>` class per class under test is allowed but not required.

## Never call real models in unit tests
- `ModelClient` must be mockable. Every test that exercises the pipeline uses a `FakeModelClient` that returns pre-canned responses keyed by prompt hash.
- Real model calls are allowed in:
  - `tests/integration/` — gated behind `@pytest.mark.integration` and `RUN_INTEGRATION=1` env var
  - `experiments/` — never in `tests/`

## What every layer must have
- **Topology**: tests for `get_adjacency_matrix(0)`, `get_adjacency_matrix(1)`, symmetry where expected, and `communication_mode` correctness.
- **Protocol**: given a crafted `VisibilityContext`, assert the built prompt contains expected markers. No real models.
- **Aggregation**: given a fixed list of `AgentResponse` + `PreferenceData`, assert the winner and confidence. Deterministic.
- **Normalizer**: table-driven tests of `(raw_input, expected_canonical)` pairs. Include JSON-wrapped, plain-text, numerical, and malformed inputs.
- **Termination**: craft `CouncilState` snapshots, assert `(should_stop, reason)` tuples.
- **Core pipeline** (`run_council`): end-to-end test with `FakeModelClient`, 3 agents, 2 rounds, verifies that (a) all agents generated in round 0, (b) adjacency matrix was respected in round 1, (c) aggregation produced a non-null result, (d) state token counts are non-zero.

## Determinism
- Every test that uses randomness must call `random.seed(0)` / `np.random.seed(0)` / `torch.manual_seed(0)` in a fixture.
- `FakeModelClient` responses are deterministic — no random sampling.
- Time-based tests use `freezegun` or pass an injected `clock` function.

## Regressions from the deep review
These are the "never break again" tests. Each issue in Part II of the review should have a test that pins the fix:

- **Issue 3**: `MajorityVote` with responses `["The answer is 72.", "72", "answer: 72"]` must return "72" with confidence `1.0` (not 1/3).
- **Issue 4**: `StructuredRanking.extract('{"ranking": ["A","B"], "scores": {"A": 9, "B": 5}}')` succeeds; falls back gracefully on malformed JSON.
- **Issue 6**: Every protocol's prompt MUST NOT contain the real `agent_id` when `anonymize=True`. Enforce via a shared `test_anonymization_consistency` fixture run against every Protocol subclass.
- **Issue 9**: `task_accuracy("The answer is 172.", "72", method="smart")` returns `0.0` (word-boundary match, not substring).
- **Issue 10**: `AgreementThreshold(0.8)` on a state where 3/3 agents normalized to "72" returns `(True, ...)`.

## Coverage
- Target: ≥ 85% line coverage on `council/`, ≥ 70% on `evaluation/`.
- `council/core.py` and `council/agent.py` target 95%.
- Coverage is a guardrail, not a goal. Do not add tests solely to hit a number.
