# Code Style Rules

## Python baseline
- **Version**: 3.11+. Use `from __future__ import annotations` only when needed for forward refs.
- **Async by default.** All I/O-touching functions are `async def`. Use `asyncio.gather` for parallel fan-out, never `ThreadPoolExecutor`.
- **Type hints required** on all public functions, dataclass fields, and class attributes. `mypy --strict` must pass for `council/core.py`, `council/agent.py`, `council/context.py`.
- **Dataclasses over dicts** for any structured payload that crosses a function boundary. Use `@dataclass(frozen=True, slots=True)` for value objects.
- **Prefer functions to classes** when no state is held. A `Protocol` subclass with only `build_prompt` is fine; a `PromptBuilder` class with a single `@staticmethod` is not — make it a module-level function.
- **No mutable default arguments.** No `def f(x=[]): ...`.
- **No `from x import *`.** Explicit imports only.

## Naming
- Modules: `snake_case.py`.
- Classes: `PascalCase`. Abstract bases end in the role (`Protocol`, `Aggregation`), concrete impls start with the variant (`PeerReviewProtocol`, `MajorityVote`).
- Constants: `UPPER_SNAKE`.
- Private helpers: leading underscore (`_format_responses`).

## Error handling
- Validate at boundaries only: `ModelClient` (inputs from callers), `CouncilAgent.complete` (user input), CLI entry points. Internal code trusts its inputs.
- Never swallow exceptions silently. `except Exception: pass` is banned; log and re-raise or convert to a typed error.
- Model call failures are expected: `ModelClient` returns `ModelResponse | ModelFailure`, never raises up to the pipeline. The pipeline decides whether to continue with partial results.

## LLM calls
- All model calls go through `ModelClient`. Never `import litellm` or `import openai` outside `council/models.py`.
- Prompts that expect structured output MUST inject the JSON schema into the prompt AND request `response_format={"type": "json_object"}` where the provider supports it.
- Ranking/scoring outputs parsed with `json.loads()` first; regex fallback only on `JSONDecodeError`.

## Comments and docstrings
- Default: no comments. Only write a comment when the *why* is non-obvious (subtle invariant, workaround, surprising constraint).
- Docstrings on public classes and non-trivial functions — one short paragraph max, no Sphinx-style param blocks unless the function has ≥4 parameters.
- Never reference tasks, PRs, or the current Phase in code comments.

## Forbidden patterns
- `print()` for debugging — use `logging` at `DEBUG` level.
- Hardcoded model names anywhere outside `configs/` and tests. `openai/gpt-4o-mini` in `aggregation.py` is a bug.
- Substring match for answer comparison (`if g in p`) — use the `task_accuracy` smart matcher from `evaluation/metrics.py`.
- `Counter(r.content.strip())` on raw LLM output — always normalize first.
- Quadratic context growth in protocols — bounded windows or summarization required.
