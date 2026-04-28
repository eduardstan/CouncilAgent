# CouncilAgent — Project Brief for Claude

## Vision
**The first multi-LLM council you can model-check.** A `CouncilAgent` is a drop-in replacement for a single LLM call: same `complete(prompt) → CouncilResponse` interface, but internally dispatches to multiple models, deliberates over a typed `ProtocolAutomaton`, aggregates via an argumentation-derived BAF/QBAF, calibrates confidence through information-theoretic disagreement, and returns a synthesized answer **with a `ProvenanceReceipt`** (typed `Trace`, QBAF, monitor verdicts, ASP groundings, cost ledger). The benchmarking apparatus is the *evaluation layer* of this agent — never the product.

## Reference docs (frozen, in repo root)
- [`COUNCIL_NS_PLAN.md`](../COUNCIL_NS_PLAN.md) — the bible (vision, taxonomy, layer specs L0–L6, theorems T1–T13, references).
- [`COUNCILAGENT_NS_MASTER_PLAN.md`](../COUNCILAGENT_NS_MASTER_PLAN.md) — the executable plan (workstreams W0–W7, sprint roadmap M1–M6, paper-deadline coupling, tutorial).
- [`legacy_council/`](../legacy_council/) — frozen v0.1.0 code, kept as seed/context only. Not importable. Not wired into the pipeline. Removed entirely at M3.

## The Constitution (12 principles, immutable)

Every design decision is evaluated against these. Violations require explicit user approval. Several principles are **type-enforced** (mypy strict catches them).

1. **The council is an agent, not a benchmark.** If a decision helps benchmarking but hurts the agent interface, choose the agent.
2. **Same interface as a single LLM.** `CouncilAgent.complete(prompt) → CouncilResponse` with zero caller changes. `CouncilResponse` carries the answer plus a `ProvenanceReceipt`.
3. **Topology controls visibility. Protocol controls *admissibility*. Aggregator controls decision.** **TYPE-ENFORCED.** Protocols are typed `ProtocolAutomaton`s — finite-state machines over speech-acts — not free-form prompt builders. `Aggregator` is parameterised by `Trace`, never by raw text.
4. **Structured types over free text.** **TYPE-ENFORCED.** Every `AgentResponse` carries a `Move`. Free text is a *fallback* path tagged `tier="text-fallback"`.
5. **Calibrated confidence is the council's unique value.** **TYPE-ENFORCED.** `CouncilResponse.confidence` is a tagged `Confidence` value: `JSDConfidence | BAFMarginConfidence | MonitorVerdictConfidence | CopelandConfidence`. Plurality fraction is type-impossible. Derivation hierarchy: `MonitorVerdictConfidence` > `BAFMarginConfidence` > `JSDConfidence` > `CopelandConfidence`.
6. **Every council run must beat (matched-compute) Mixture-of-Agents on at least one Pareto axis.** Matched-compute means equal output tokens by default and equal $-cost when both are reportable. Tables in every paper report both.
7. **Cost is first-class.** Every response carries its cost. Every config has an estimated cost. Budgets are enforced.
8. **The core pipeline has zero framework dependencies.** `council/core.py`, `agent.py`, `policy.py`, `dialect/`, `symbolic/`, `calibrate/`, `cascade/`, `evolve/` are pure Python + asyncio. LangGraph, Hydra, MLflow, OpenTelemetry, pyribs, SPOT, clingo live in `council/adapters/` or behind optional extras (`[verify]`, `[argue-asp]`, `[evolve]`, `[ilp]`). The no-extras path always works (pure-Python fallbacks).
9. **Correctness before features.** A correct DF-QuAD aggregator on 3 problems beats a broken one on 1000.
10. **Anonymise by default.** Agent identities are stripped during deliberation, preserved in metadata. Anonymisation lives in **exactly one place** (`core._build_visibility_context`).
11. **Symbolic outputs are first-class.** Every `CouncilResponse` carries a `ProvenanceReceipt` with: typed `Trace`, QBAF (when applicable), monitor verdicts (when applicable), ASP groundings (when applicable), Lean/Z3 certificates (when applicable), per-move cost ledger. Receipts are always emitted when the corresponding layer is active in the genome — no silent omission. `ProvenanceReceipt.is_complete()` returns True iff every move has cost, every Vote has ≥ 1 evidence atom, every ⊥ verdict triggered an intervention, and the QBAF's argument count equals the Propose count.
12. **The verifier can intervene.** `LTLfMonitorTermination` and `Intervention` permit the symbolic layer to *redirect* deliberation, not merely observe it. On a `⊥` verdict from any active monitor, the configured intervention executes before the next deliberation round. This is "LLM-Modulo at the dialogue level".

## Layered Architecture

```
CouncilAgent              (agent.py)        — drop-in LLM interface, ProvenanceReceipt assembly
CouncilPolicy             (policy.py)       — task profile + budget → CouncilGenome
run_council()             (core.py)         — pure async pipeline: generate → deliberate → monitor → aggregate → terminate
                                              composes Topology, ProtocolAutomaton, Ranker, Aggregator, Calibrator, Termination
─────────────────────────  SYMBOLIC STRATUM  ──────────────────────────
L6 ILP / ASP rule mining  (symbolic/ilp/)         Popper, ILASP4, clingo
L5 QD over compositions   (evolve/)               CMA-MAE on pyribs + LLM-mutation (GEPA, AlphaEvolve)
L4 cost-aware cascade     (cascade/)              in-context distillation, multi-tier router
L3 calibrated disagreement(calibrate/)            JSD, MUSE, ConFreeze, privileged-knowledge per-domain
L2 argumentation          (symbolic/argue/)       BAF/QBAF + DF-QuAD / QE / Euler / Strategic-Coupled gradual
L1 verification spine     (symbolic/verify/)      LTL_f LTL3 monitors via SPOT, offline MCMAS
L0 speech-act algebra     (dialect/)              typed Move/Trace + ProtocolAutomaton
─────────────────────────  NEURAL STRATUM  ────────────────────────────
ModelClient               (models.py)       LiteLLM wrapper: cache, meter, retry, fault-inject
ToolClient                (tools.py)        MCP, Z3, clingo, Lean, Python sandbox, web
Evaluation                (evaluation/)     metrics, baselines (MoA, Self-MoA, ConFreeze, KarpathyLLMCouncil), Shapley, AIPW, Bradley-Terry, mixed-effects
```

## Tech Stack

- **Language:** Python ≥ 3.11; `mypy --strict` on all of `council/` (per `pyproject.toml`).
- **Async:** `asyncio` everywhere I/O touches; never `ThreadPoolExecutor`.
- **Model access:** **LiteLLM** is the single backend (`LiteLLMClient`) — `openai/*`, `anthropic/*`, `openrouter/*` (incl. `:free`), `ollama/*`. Never call providers directly from core.
- **Tools:** **MCP** is the universal tool integration. Z3 / clingo / Lean / Python sandbox / web exposed via MCP servers; council code talks to `ToolClient` only.
- **Verification:** SPOT (preferred), `ltl2mon` fallback (pure Python), MCMAS via subprocess. Optional `[verify]`.
- **Argumentation:** pure Python by default; clingo for ASP-extensions optional `[argue-asp]`.
- **Calibration:** numpy + scipy + scikit-learn (in `[benchmark]`).
- **Evolution:** **pyribs** for CMA-MAE; pure-Python random-search fallback. Optional `[evolve]`.
- **ILP:** Popper (Cropper-Morel), ILASP4 (Law et al.); both shell out. Optional `[ilp]`.
- **Orchestration:** LangGraph **only** as a thin adapter in `council/adapters/langgraph.py`. The core pipeline runs without it.
- **Config:** Hydra (YAML composition) for `experiments/`. The `CouncilAgent` itself works without Hydra.
- **Tracking:** MLflow for experiments; OpenTelemetry for distributed tracing; both in `experiments/` and `evaluation/`.
- **Testing:** pytest + pytest-asyncio. Structured-output fixtures over free-text fixtures. Target: ≥ 1500 functions in `tests/` by M6.
- **Lint/format:** ruff. Type-check: `mypy --strict council/`.

## Workstream Roadmap

- **W0** — Substrate (L0): typed Move algebra + protocol automata + pure-async pipeline → M1.
- **W1** — Verification spine (L1): LTL_f / LTL3 monitors, ISPL/MCMAS, named-property library, interventions → M2.
- **W2** — Argumentation aggregator (L2): BAF/QBAF, DF-QuAD / QE / Euler / Strategic-Coupled, Mermaid visualisers → M2.
- **W3** — Calibrated disagreement (L3): JSD, MUSE, privileged-knowledge per-domain, isotonic → M3.
- **W4** — Cost-aware cascade (L4): in-context distillation, multi-tier router, budget tracker → M3.
- **W5** — QD over compositions (L5): genome, descriptors, archives, emitters, Pareto, red-team archive, co-evolution → M4.
- **W6** — ILP / ASP (L6): Popper, ILASP4, ASP integrity constraints, MCMAS-verified learned protocols → M5.
- **W7** — Evaluation, demos, papers: benchmarks, baselines, novel metrics, MLflow/OTEL, Streamlit demo, paper reproductions → continuously, sealed at M6.

## Publication Track

Five papers + a flagship — see [`COUNCILAGENT_NS_MASTER_PLAN.md`](../COUNCILAGENT_NS_MASTER_PLAN.md) §9.
- **P1** Verified Deliberation — AAMAS 2027 main.
- **P2** Strategic Gradual Argumentation — AAAI 2027.
- **P3** Quality-Diversity over Deliberation Behaviour — **NeurIPS 2026 main** (load-bearing).
- **P4** Co-evolutionary Red/Blue Teaming — AAMAS 2027 companion.
- **P5** Inductive Discovery of Multi-Agent Dialogue Protocols — KR 2026.
- **F** A Neuro-Symbolic Multi-Agent LLM Council Framework — JAIR / AIJ flagship (Apr 2027 → v1.0.0).

## Git Workflow

- `main` — frozen at `legacy/v0.1.0` (PyPI `council-agent==0.1.0`); the student's reference. Untouched by NS work until v1.0.0 merge.
- `develop` — student's working branch off `main`; not used here.
- `council-ns` — long-lived development branch (this branch). PyPI `councilagent`, version stepping `0.2.0.dev0` → `1.0.0`.
- `feature/ns-w<n>-<slug>` — short-lived (≤ 2 weeks) per workstream task.
- Never commit to `main` directly. Never force-push `develop`, `main`, or `council-ns`.

## Operating Rules for Claude

- **Read [`COUNCIL_NS_PLAN.md`](../COUNCIL_NS_PLAN.md) before touching any architectural decision.** It contains the tradeoff analysis for every major choice and the layer specifications. Note: the bible writes `council_ns/` for clarity in its migration narrative; on this branch the package is just `council/`.
- **Read [`COUNCILAGENT_NS_MASTER_PLAN.md`](../COUNCILAGENT_NS_MASTER_PLAN.md) §11 (Tutorial) before invoking agents/skills.** The tutorial maps each workstream and each paper to the right agent/skill chain.
- **Do NOT port code from `legacy_council/`.** It is a frozen seed for context only. Copy-pasting legacy classes preserves the defects D1–D17 we are fixing.
- **When uncertain about a layering call, stop and ask.** §3 violations are the most common failure mode. The type system catches some — but not all; resist `Any` and `cast`.
- **Follow workstream order.** Don't skip ahead.
- **Rules files** in `.claude/rules/` are binding.
- **Provenance receipts are non-negotiable.** Any new aggregator, monitor, calibrator, or strategy must emit its contribution to the receipt (§11).

## Common Commands

```bash
# Tests
uv run pytest tests/                          # full unit test suite
uv run pytest tests/dialect/                  # one workstream
RUN_INTEGRATION=1 uv run pytest tests/integration/

# Lint + type-check
uv run ruff check council/ evaluation/ tasks/ experiments/
uv run mypy council/                          # strict on all of council/

# Constitution audit
.claude/skills/check-constitution/run.sh

# Experiments
uv run python -m experiments.run --config-name fast
uv run python -m experiments.sweep --multirun
uv run python -m experiments.evolve --config-name qd_arc_agi_2

# Paper reproductions
bash experiments/reproduce/p3_qd.sh

# Streamlit demo
uv run streamlit run apps/streamlit_demo.py
```
