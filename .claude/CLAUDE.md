# CouncilAgent — Project Brief for Claude

## Vision
**The council is an agent, not a benchmark.** A `CouncilAgent` is a drop-in replacement for a single LLM call: same `complete(prompt) → response` interface, but internally dispatches to multiple models, deliberates, aggregates, and returns a synthesized answer *with calibrated confidence derived from inter-agent agreement*. The benchmarking apparatus is the *evaluation layer* of this agent — never the product.

Reference docs (frozen, in repo root):
- [plan.md](../plan.md) — original research plan (taxonomy, hypotheses, classical foundations)
- [LLMCouncil_Deep_Review.md](../LLMCouncil_Deep_Review.md) — architectural review and phased roadmap. **This is the source of truth for implementation.**

The previous attempt lives in `../LLMCouncil/` (gitignored). It is **reference only** — we are building fresh per the deep review.

## The Constitution (immutable)
Every design decision is evaluated against these. Violations require explicit user approval.

1. **The council is an agent, not a benchmark.** If a decision helps benchmarking but hurts the agent interface, choose the agent.
2. **Same interface as a single LLM.** `council.complete(prompt) → response` with zero caller changes.
3. **Topology controls visibility. Protocol controls presentation. Aggregation controls decision.** No layer does another's job. No privileged agents in a topology. No visibility filtering inside a protocol. No prompt construction inside aggregation.
4. **Structured output over regex parsing.** Ask for JSON at prompt time; parse with `json.loads()`. Regex is a fallback only.
5. **Calibrated confidence is the council's unique value.** Derived from inter-agent agreement, not self-report. It drives termination, escalation, and user-facing reliability.
6. **Every council run must beat majority-vote-without-deliberation** on the same models. If it doesn't, the protocol is burning tokens.
7. **Cost is first-class.** Every response carries its cost. Every config has an estimated cost. Budgets are enforced.
8. **The core pipeline has zero framework dependencies.** `council/core.py` is pure Python + asyncio. LangGraph, Hydra, MLflow live at the edges.
9. **Correctness before features.** A correct `MajorityVote` on 3 problems beats a broken one on 1000.
10. **Anonymize by default.** Agent identities are a confound — strip during deliberation, preserve in metadata.

## Layered Architecture
```
CouncilAgent        (agent.py)      — drop-in LLM interface, confidence, escalation
CouncilPolicy       (policy.py)     — task profile + budget → config
run_council()       (core.py)       — pure async pipeline: generate → deliberate → rank → aggregate
Topology | Protocol | Ranking | Aggregation | Normalizer | Termination
ModelClient         (models.py)     — LiteLLM/OpenRouter wrapper: cache, meter, retry, fault-inject
Evaluation layer    (evaluation/)   — metrics, baselines, Shapley, statistics, MLflow — benchmark mode only
```

## Tech Stack
- **Language**: Python ≥ 3.11, async-first (`asyncio`)
- **Model access**: LiteLLM **and** OpenRouter — both supported behind the `ModelClient` abstraction. The abstraction decides which backend to use per-model based on config (e.g. `openrouter/anthropic/claude-sonnet-4` routes via OpenRouter; `openai/gpt-4o` via LiteLLM direct). Never call providers directly from core code.
- **Orchestration**: LangGraph *only* as a thin adapter in `council/adapters/langgraph.py`. The core pipeline must run without it.
- **Config**: Hydra (YAML composition) for experiments. The `CouncilAgent` itself must be usable without Hydra.
- **Tracking**: MLflow for experiments, OpenTelemetry for distributed tracing.
- **Testing**: pytest + pytest-asyncio. Structured-output fixtures over free-text fixtures.
- **Lint/format**: ruff. Type-check: mypy (strict in `council/core.py`, `council/agent.py`).

## Target Repository Layout
```
council/
  agent.py          policy.py        core.py          context.py
  models.py         topology.py      protocol.py      ranking.py
  aggregation.py    normalizer.py    termination.py   task_profile.py
  adapters/langgraph.py
evaluation/
  metrics.py  baselines.py  shapley.py  statistical.py
tasks/              experiments/     analysis/        configs/         tests/
```
Do not create these files until the corresponding Phase task (see the deep review, Part IV) is active.

## Phased Roadmap (from the Deep Review)
- **Phase 0** — Foundation corrections (but we're building fresh, so this is merged into Phase 1)
- **Phase 1** — Core abstractions: `VisibilityContext`, `CommunicationMode`, pure `core.py`, `AnswerNormalizer`, structured output, multi-round peer review
- **Phase 2** — Termination & control: `TerminationStrategy`, `TaskProfile`, cost estimation
- **Phase 3** — `CouncilAgent`, `CouncilPolicy`, `EscalationStrategy`, Condorcet/Copeland
- **Phase 4** — Benchmark infrastructure: MLflow, AIPW, Hydra sweeps, Shapley
- **Phase 5** — Hypothesis testing (H1, H3, H5, H6, H10 + council-vs-single-LLM)
- **Phase 6** — Polish, demos, thesis integration

## Git Workflow
- `main` — protected, release-tagged only
- `develop` — integration branch, default working branch
- `feature/<phase>-<slug>` — one branch per deep-review task (e.g. `feature/p1-visibility-context`)
- Never commit to `main` directly. Never force-push `develop` or `main`.
- Commits on `develop` are allowed for infra/docs (like this .claude setup). Code work goes on feature branches.

## Operating Rules for Claude
- **Read `LLMCouncil_Deep_Review.md` before touching any architectural decision.** It contains the tradeoff analysis for every major choice.
- **Do not port code from `../LLMCouncil/`.** It is reference only. Build fresh.
- **When uncertain about a layering call, stop and ask.** Constitution §3 violations are the most common failure mode.
- **Follow the phased roadmap.** Do not skip ahead (e.g. don't add Shapley values before `CouncilAgent` works end-to-end).
- **Rules files** in `.claude/rules/` are binding. Subagents in `.claude/agents/` handle reviews and scaffolding — use them.

## Common Commands (to be populated as the project grows)
```bash
# These will be filled in once pyproject.toml exists
uv run pytest tests/
uv run ruff check council/ evaluation/
uv run mypy council/core.py council/agent.py
```
