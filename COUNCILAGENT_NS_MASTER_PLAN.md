# CouncilAgent‑NS — Master Migration & Execution Plan

> **Status.** This is the executable plan for migrating from the current `CouncilAgent@main` engineering baseline to **`CouncilAgent‑NS`**, the first multi-LLM council you can model-check.
> **Companion document.** [`COUNCIL_NS_PLAN.md`](./COUNCIL_NS_PLAN.md) is the *bible*: vision, theorems, layer specs, references. Read it first; then use **this** document to drive day-to-day work. Where the bible says *what* and *why*, this plan says *who, when, where, in what order, with what acceptance criteria*.
> **Scope.** Twelve months (M1–M6 milestones, week-grain schedule), six layers (L0–L6), five papers + a flagship (P1–P5, F), one Constitution (12 principles), one repo (mono-repo with `council/` legacy preserved next to `council/`).

---

## Table of contents

0. [Meta — how to read and use this plan](#0-meta--how-to-read-and-use-this-plan)
1. [Strategic frame](#1-strategic-frame)
2. [Branching, coexistence, and dual-track strategy](#2-branching-coexistence-and-dual-track-strategy)
3. [The substrate audit — what we keep, port, or discard](#3-the-substrate-audit)
4. [Repository layout (target)](#4-repository-layout-target)
5. [The Constitution (12 principles, binding)](#5-the-constitution-12-principles-binding)
6. [Architecture rules (binding, type-level)](#6-architecture-rules-binding-type-level)
7. [Workstreams W0–W7 (replaces "phases")](#7-workstreams-w0w7)
8. [Defect ↔ workstream ↔ theorem ↔ paper crosswalk](#8-defect--workstream--theorem--paper-crosswalk)
9. [Publication track (P1–P5, F) — per-paper plan](#9-publication-track-p1p5-f)
10. [Twelve-month sprint roadmap (M1–M6, week-grain)](#10-twelve-month-sprint-roadmap)
11. [Empirical plan (benchmarks, baselines, ablations, metrics)](#11-empirical-plan)
12. [Engineering operations (CI, releases, telemetry, env)](#12-engineering-operations)
13. [`.claude/` overhaul — agents, skills, rules, settings](#13-claude-overhaul)
14. [Risk register and counterfactual paper plans](#14-risk-register-and-counterfactual-paper-plans)
15. [Two-week kickoff (concrete, day-by-day)](#15-two-week-kickoff)
16. [Definitions of done](#16-definitions-of-done)
17. [Appendix A — Paper-PDF ↔ workstream crosswalk](#appendix-a--paper-pdf--workstream-crosswalk)
18. [Appendix B — Legacy v0.1.0 → NS migration table](#appendix-b--legacy-v010--ns-migration-table)
19. [Appendix C — README contract for the flagship](#appendix-c--readme-contract-for-the-flagship)
20. [Appendix D — Glossary (Move, Trace, ProtocolAutomaton, BAF/QBAF, DF-QuAD, JSD, MUSE, …)](#appendix-d--glossary)
21. [**Appendix E — Tutorial: agent + skill workflow toward F v1.0.0**](#appendix-e--tutorial-agent--skill-workflow-toward-f-v100)

---

## 0. Meta — how to read and use this plan

### 0.1 The four documents

| Document | Role | Mutability |
|---|---|---|
| [`COUNCIL_NS_PLAN.md`](./COUNCIL_NS_PLAN.md) | **The bible.** 21K words: vision, taxonomy, theorems, layer specs (L0–L6), competitive analysis, references. | **Frozen.** Treat as a citation target. |
| [`COUNCILAGENT_NS_MASTER_PLAN.md`](./COUNCILAGENT_NS_MASTER_PLAN.md) *(this file)* | **Executable plan.** Workstreams, sprints, acceptance criteria, paper-deadline coupling, agent/skill workflow tutorial. | **Living.** Update at each milestone (M1–M6). |
| [`LLMCouncil_Deep_Review.md`](./LLMCouncil_Deep_Review.md) | Engineering review of the v0.1.0 codebase. Used here only as the source of the defect catalogue (D1–D17 in §3 below). | Frozen. |
| [`plan.md`](./plan.md) | Original research plan (2024). Historical only. | Frozen. |

The 12-principle Constitution lives in `.claude/CLAUDE.md`. The architecture rules live in `.claude/rules/architecture.md`. They are the binding artefacts. §5 and §6 of this plan reproduce them as documentation; if the two ever drift, `.claude/` wins.

### 0.2 The branch model — one branch, one folder, one Constitution

| Branch | Constitution | Package folder | PyPI | Versions | Role |
|---|---|---|---|---|---|
| `main` | Legacy 10-principle | `council/` | `council-agent` | `0.1.0` (frozen at `legacy/v0.1.0`) | The student's reference, untouched. |
| `develop` | Legacy 10-principle | `council/` | `council-agent` | `0.1.x` (post-release patches if needed) | Student's working branch off `main`. |
| `council-ns` | 12-principle (this plan) | `council/` (NS implementation) + `legacy_council/` (frozen seed, removed at M3) | `councilagent` | `0.2.0.dev0` → `1.0.0` (M6 = flagship F) | All NS work. |

Concrete consequences:
- The package folder is always `council/` — there is no `council_ns/` directory.
- The Constitution file is always `.claude/CLAUDE.md` — there is no `CLAUDE-NS.md`. Different content per branch; never two files at once.
- Both packages install Python module `council`, so they cannot coexist in one venv. For the legacy ablation row in every paper, the NS evaluation harness subprocess-calls a sub-venv with `pip install council-agent==0.1.0`.
- The bible (`COUNCIL_NS_PLAN.md`) was written when a coexistence layout was being considered, so it uses `council_ns/`, `tests_ns/`, etc. **Read those names as `council/`, `tests/`, etc. on the `council-ns` branch.**

### 0.4 Reading order

1. Read [`COUNCIL_NS_PLAN.md`](./COUNCIL_NS_PLAN.md) §1, §4, §5 for the strategic framing (≈ 20 minutes).
2. Read this document, §1–§7 (≈ 30 minutes) — strategy, repo strategy, workstream skeleton.
3. Read [`COUNCIL_NS_PLAN.md`](./COUNCIL_NS_PLAN.md) §6 (L0–L6) when you start the corresponding workstream. The bible has the *types and theorems*; this plan has the *acceptance criteria and PR sequence*. Treat any `council/` reference there as `council/` per §0.2.
4. Read [`COUNCIL_NS_PLAN.md`](./COUNCIL_NS_PLAN.md) §11 alongside §9 of this plan when you start a paper.

### 0.5 What "done" means at every level

This plan adheres to three definitions of done, in increasing rigor:

- **PR-done.** Code merges, tests pass, mypy strict passes, ruff passes, the new module's invariants are tested. No regressions in adjacent modules.
- **Layer-done.** Every theorem the bible attributes to the layer is either proved, mechanised, or empirically demonstrated; the layer's acceptance criteria (§7) are checked off.
- **Paper-done.** The paper has a one-command reproduction in `experiments/reproduce/p<n>_*.sh`, all numbers in the paper come from a frozen config, the artefact submission passes its acceptance checklist (§16).

---

## 1. Strategic frame

### 1.1 The single sentence (locked tagline)

**`CouncilAgent‑NS` reframes a multi-LLM council as a typed transition system over speech-acts that you can model-check, aggregate via formal argumentation, illuminate with quality-diversity, and inductively learn protocols for — turning the existing engineering baseline into the first multi-LLM council whose deliberation has *provable* properties.**

This sentence is the **canonical headline**. Use it verbatim in the README, the JAIR/AIJ abstract, and the elevator pitch.

### 1.2 The five papers + flagship (the publication contract)

| ID | Title | Layers | Venue (target) | Backup | Deadline |
|----|-------|--------|----------------|--------|----------|
| **P1** | Verified Deliberation: Model-Checking Multi-LLM Councils with Epistemic-Strategic Logic | L0+L1 | **AAMAS 2027** main | NeSy 2026, KR 2026 | abstract Oct 2026 |
| **P2** | Strategic Gradual Argumentation for Multi-LLM Aggregation | L0+L2(+L3) | **AAAI 2027** | NeurIPS 2026 D&B, IJCAI 2027 | Aug 2026 |
| **P3** | Quality-Diversity over Deliberation Behaviour | L5 over L0+L1+L2+L3 | **NeurIPS 2026** main | ICLR 2027, GECCO 2027 | May 2026 |
| **P4** | Co-evolutionary Red/Blue Teaming of Deliberating Councils | L5 + red-team archive + L1 | **AAMAS 2027** companion | NeurIPS 2026 main, ICLR 2027 | Oct 2026 |
| **P5** | Inductive Discovery of Multi-Agent Dialogue Protocols | L6 (+ L0+L1) | **KR 2026** | NeSy 2026, ILP 2026/2027 | May/Jun 2026 |
| **F**  | CouncilAgent‑NS: A Neuro-Symbolic Multi-Agent LLM Council Framework | All layers | **JAIR / AIJ** flagship | NeSy 2027 keynote/tutorial | rolling, target Apr 2027 |

The plan's **load-bearing publication risk**: P3 must hit NeurIPS 2026 main (May 2026) — that requires L0+L1+L2+L3 functional and L5 evaluated end-to-end by April 2026. §10 maps that risk to weekly milestones.

### 1.3 The "wow" outcome

By M6 (Apr 2027) the repo must support — in a hosted Streamlit demo, in under 30 seconds — **a sycophancy-cascade scenario where:**

1. A user pastes an ARC-AGI-2 task.
2. The council (≥ 3 typed agents) deliberates over a `DeliberationAutomaton` protocol.
3. An LTL₍f₎ monitor detects an `NoSycophancyCascade` violation mid-debate.
4. An `Intervention` (devil's advocate or model upgrade) fires.
5. A QBAF is rendered live as a Mermaid graph in the side panel.
6. The verdict is produced, with a `ProvenanceReceipt` (typed Trace, BAF, monitor verdicts, ASP grounding, cost ledger).

This 30-second loop is the recruiting tool, the screen-cap for the README, the demo at NeSy/KR/AAMAS, and the lever that turns 5 papers into stars.

### 1.4 Strategic differentiators (why each competitor cannot scoop)

The 11-system fence in `COUNCIL_NS_PLAN.md` §4.1 is binding. Re-statement in one sentence each:

- **Sakana TRINITY** evolves a *single learned coordinator* with three fixed roles; we evolve **typed protocols × topologies × aggregators × calibrators** with verifier-derived behavioural descriptors.
- **Sakana Conductor** is RL on free text; we are QD on **typed protocol automata + LTL₍f₎ monitors**.
- **Mixture-of-Agents** is the matched-compute baseline; we **must beat it under matched tokens** (Constitution §6).
- **ArgLLMs / MArgE** extract a QBAF from text via an LLM; we **construct it from a typed-protocol-enforced trace** — no extraction step, no "Can LLMs Judge Debates?" failure mode.
- **AFlow / AgentSquare / MaAS / SwarmAgentic / EvoFlow** search workflows; we search **deliberations**, with verifier-derived descriptors and re-verified learned protocols.
- **GEPA / AlphaEvolve** are *tools we borrow* (LLM mutation emitters in W5), not competitors.
- **Karpathy llm-council** is the 2024 reference; we are the 2026 research artefact.
- **Perplexity Model Council** is closed product; we are open-source flagship.

---

## 2. Branching strategy (single folder per branch, no coexistence)

### 2.1 Two long-lived branches, branch-scoped state

```
main  ──tag legacy/v0.1.0──── frozen for the student
   │   PyPI: council-agent==0.1.0
   │   .claude/CLAUDE.md = legacy 10-principle Constitution
   │   council/ = legacy implementation
   │
   └─► council-ns ── the new "develop" for NS work
          PyPI: councilagent==0.2.0.dev0  →  1.0.0 at M6
          .claude/CLAUDE.md = NS 12-principle Constitution
          council/ = NS implementation (built fresh, W0–W6)
          legacy_council/ = the frozen legacy code, kept as seed/context (will be removed)
          │
          └─► feature/ns-w0-substrate
              feature/ns-w1-verification
              feature/ns-w2-argumentation
              feature/ns-w3-calibration
              feature/ns-w4-cascade
              feature/ns-w5-evolve
              feature/ns-w6-ilp
              feature/ns-w7-evaluation
```

- **`main`** = frozen v0.1.0 reference. Student keeps using it. Tag at the current commit (`7dc2e29 Merge develop → main: Phase 6 complete + README`) **before** branching `council-ns`. No NS work commits to `main` until the v1.0 merge at M6.
- **`develop`** continues to exist as the student's working branch off `main`. NS does not touch it. The student lives there; we live on `council-ns`.
- **`council-ns`** = the NS migration branch. **Single folder named `council/`** — that's the package. The legacy code lives in **`legacy_council/`** (renamed from `council/` during the migration commit) as seed/context only; it is *not* importable as `legacy_council` and is not intended to be wired into the NS pipeline. It will be removed entirely at M3 once enough NS substrate is in place that the legacy seed is no longer informative.
- **`feature/ns-w<n>-<slug>`** branches are short-lived (≤ 2 weeks each), branch off `council-ns`, merge back into `council-ns` after review.

### 2.2 No coexistence: there is only one `council/`

On `council-ns`, the top-level package is `council/` and its contents are the NS implementation. There is **no** parallel `council_ns/` directory. The legacy code is preserved only:
- as `legacy_council/` on the `council-ns` branch (read-only seed; will be deleted at M3);
- on the `main` branch unchanged;
- on PyPI as `council-agent==0.1.0` (the published, installable artefact);
- via the `legacy/v0.1.0` git tag.

For the legacy ablation row in every paper, NS subprocess-calls a managed sub-venv with `pip install council-agent==0.1.0` — never imports the legacy from inside the NS process.

### 2.3 The `.claude/` is branch-scoped — one file per branch

There is **one** `.claude/CLAUDE.md` file. There is **one** `.claude/rules/architecture.md` file. Their *content* differs by branch:

- On `main` (and `develop`): the legacy 10-principle Constitution and legacy architecture rules.
- On `council-ns`: the NS 12-principle Constitution (extracted from §5 of this plan) and the NS architecture rules (extracted from §6 of this plan).

The migration commit on `council-ns` carries these files in their NS form. There is one Constitution file and one architecture-rules file at any time; their contents differ per branch.

### 2.4 PyPI naming

- **Legacy:** `council-agent`, frozen at `0.1.0`. Tagged at the current `main`. The student installs and depends on this exactly.
- **NS:** **`councilagent`** (registered by the user; PyPI confirmed available). The NS branch's `pyproject.toml` is edited in place at branch creation: `name = "councilagent"`, `version = "0.2.0.dev0"`. There is no second `pyproject.*.toml` file.

The two packages cannot coexist in one venv (both install the Python package `council`). That is intentional — installing NS replaces legacy. For ablation, use sub-venvs.

---

## 3. The substrate audit

### 3.1 What ports verbatim (preserve)

These elements are *correct* in the legacy code and port to NS without semantic change. They become reusable infrastructure for the new stack.

| Legacy artefact | NS destination | Rationale |
|---|---|---|
| `council/core.py:70-162` `run_council` structure (pure async, generate→deliberate→rank→aggregate, framework-free) | `council/core.py` `run_council` skeleton | Constitution §8 already correct; only the dataclasses inside change to typed Move/Trace. |
| `council/core.py:323-394` `_build_visibility_context` — anonymisation in **one place** | `council/core.py` (same name) | Single-source-of-truth pattern stays; Trace→VisibilityContext build is the new operation. |
| `council/context.py` frozen `slots=True` dataclass shape (the *seam*) | `council/context.py` | Keep the shape, swap `content: str` → `move: Move`. |
| `council/aggregation.py:42-49` `Aggregation.aggregate(..., round_history=None, original_prompt=None)` debate-aware kwargs | `council/aggregation/base.py` (`Aggregator.aggregate(trace, *, original_question)`) | This is the exact socket the BAF/QBAF aggregator plugs into. |
| `council/protocol.py:28-47` `is_answer_round` + `cycle_length` predicates | `council/dialect/protocols/base.py` `is_answer_phase(trace)` + `cycle_length()` (now derived from automaton) | Generalise to `ProtocolAutomaton`. |
| `council/aggregation.py:306-375` `CondorcetAggregation` + Copeland fallback | `council/aggregation/social_choice.py` (baseline aggregator, **not** the headline) | Reviewer-quality social choice; reuse as a baseline for L2 ablations. |
| `council/topology.py` + `CommunicationMode` enum | `council/topology.py` (port + extend) | INDIVIDUAL/BROADCAST/RELAY semantically correct; expand the topology library to GNN-routed and learned topologies. |
| `council/termination.py:87-103` `CompositeTermination` (OR-composition) | `council/termination.py` | The right base for `LTLfMonitorTermination`, `JSDDivergenceTermination`, `ArgumentationStableTermination`. |
| `council/agent.py:91-123` `EscalationStrategy` ABC + 3 concrete strategies | `council/cascade/strategies.py` | Generalise to L4 cost-aware cascade router. |
| `evaluation/shapley.py` (exact ≤ 6, Monte-Carlo > 6, three-axiom tests) | `evaluation/shapley.py` | Reviewer-quality. Reuse for per-genome attribution in L5. |
| `evaluation/statistical.py` (bootstrap CI, Wilcoxon paired) | `evaluation/statistical.py` | Add AIPW + Bradley-Terry + mixed-effects. |
| `pyproject.toml` (mypy strict on context/core/agent; ruff B/UP/SIM/RUF; dep groups) | `pyproject.toml` (rewritten in place: `name = "councilagent"`, version `0.2.0.dev0`, mypy strict on all of `council/`, optional extras `[verify]`, `[argue-asp]`, `[evolve]`, `[ilp]`, `[full]`) | — |
| `tests/` discipline (pytest-asyncio, FakeModelClient, RUN_INTEGRATION gate) | `tests/` | Port the discipline; rewrite test bodies for typed Moves. |
| `.claude/` Constitution-as-doc + scaffolding skills | `.claude/CLAUDE.md` + new skills (§13) | Port idea; back with **type-level** enforcement. |

### 3.2 What ports with structural changes

These elements have correct intent but need substrate-level modification.

| Legacy artefact | NS change | Reason |
|---|---|---|
| `council/aggregation.py:138-145` `_default_round_label` (D13) | **Removed.** Round labels become `(automaton.state(trace), is_answer_phase(trace))`. | Layer violation: aggregation reaches into protocol semantics. |
| `council/aggregation.py:81-83` `MajorityVote.confidence = winner_count / total` (D2) | **Banned by Constitution §5.** Confidence becomes `JSD-margin` (L3) or `BAF-strength-margin` (L2). | Brand-promise violation. |
| `council/agent.py:198-202` raw-string dissent (D9) | **Replaced** by canonical-form dissent computation post-normalisation. | Already an audit defect; type system makes this impossible in NS. |
| `council/policy.py:31-160` two-tier if-statement policy (D4) | **Replaced** by `CouncilPolicy.plan(prompt, profile, budget) → CouncilGenome` — a lookup against the QD archive (W5). | The "policy" is currently a 2-line policy. |
| `council/protocol.py:117` `PeerReviewProtocol` hardcoded 2-cycle (D8) | **Subsumed** by `DeliberationAutomaton` (Walton 2010) from W0; the legacy 2-cycle becomes one preset. | Without an automaton, no monitor can attach. |
| `council/topology.py:65` `DynamicStarTopology` (D7) | **Augmented** with `GNNRoutedTopology`, `LearnedTopologyAdapter`, plus the round-parity dynamic remains as a baseline. | Topology dimension is the most active 2024–26 axis; add learned variants. |
| `evaluation/baselines.py:34-146` (D12) | **Augmented** with `MixtureOfAgentsBaseline`, `SelfMoABaseline`, `DebateOnly`, `CoTSelfConsistency`, `ConFreezeBaseline`, `KarpathyLLMCouncilBaseline`, **matched-token-budget** wrappers. | 2026 reviewer: matched-token comparisons mandatory. |
| `evaluation/metrics.py:64-100` `task_accuracy` smart matcher (D16) | **Augmented** with `semantic_equivalence` (LLM-as-judge), `execution_match` (code), `step_grading` (math). Existing word-boundary path stays as the numeric default. | Multi-domain Tier-A benchmarks need different correctness signals. |
| `experiments/run.py` 621-LOC monolith (D17) | **Split** into `experiments/run.py` (CLI), `experiments/service.py` (pure async), `experiments/logging_adapter.py` (MLflow), and `experiments/transcript.py` (formatting). | Flagship-grade hygiene. |

### 3.3 What is discarded

- **Plurality-fraction confidence.** Removed. Banned by NS Constitution §5.
- **`_default_round_label`** in `aggregation.py`. Removed. Replaced by automaton-derived phases.
- **`_FREE_MODELS` constant tier table** in `policy.py`. Removed. The QD archive replaces it.
- **`fast_vote` / `standard_deliberation` hard-coded tiers** in `policy.py`. Removed.

### 3.4 Net summary

- **Lines preserved verbatim:** ≈ 1,800 / 4,125 LOC (44%) — primarily `core.py` skeleton, `topology.py`, `termination.py`, `evaluation/shapley.py`, `evaluation/statistical.py`, and `models.py`.
- **Lines ported with changes:** ≈ 1,200 LOC (29%).
- **Lines discarded:** ≈ 1,125 LOC (27%) — primarily `policy.py`, the parity heuristic in `aggregation.py`, plurality-fraction paths in `agent.py` and `aggregation.py`, and the `experiments/run.py` monolith.
- **Tests preserved as discipline:** 422 functions; ≈ 60% port to `tests/` after type rewrites; 40% replaced with typed-Move equivalents. **Target by M6: ≥ 1,500 functions in `tests/`.**

---

## 4. Repository layout (target on `council-ns`)

This is the `council-ns` branch layout at v1.0 (M6, April 2027). Build it incrementally; do **not** create a directory until its workstream is active. On `main` the layout stays the legacy v0.1.0 layout — the student's reference, frozen.

```
CouncilAgent/                        # mono-repo, council-ns branch at v1.0
├── README.md                         # NS edition; tagline + GIF + value prop + 10-line code
├── ROADMAP.md                        # references this file's §10 sprint roadmap
├── CITATION.cff                      # Zenodo-hooked
├── LICENSE                           # MIT (legacy choice; unchanged unless we revisit)
├── pyproject.toml                    # name = "councilagent"; version stepping 0.2.0 → 1.0.0
├── conftest.py
├── docs/
│   ├── theory.md                     # Walton-Krabbe; Dung 1995; Baroni-Rago-Toni 2019;
│   │                                 #   Bauer-Leucker-Schallhart 2011; MCMAS
│   ├── protocols.md                  # how to write a new ProtocolAutomaton
│   ├── verifying.md                  # how to write a new LTL_f property
│   ├── argumentation.md              # how to plug a new gradual semantics
│   ├── calibration.md                # how to add a new calibrator
│   ├── cascade.md                    # how to add a routing strategy
│   ├── evolution.md                  # how to add a behavioural descriptor
│   ├── ilp.md                        # how to write an ASP background theory
│   ├── benchmarks.md                 # reproduction recipes for every paper number
│   └── adr/                          # architecture decision records
│       ├── 0001-typed-move-substrate.md
│       ├── 0002-ltlf-monitor-via-spot.md
│       └── …
│
├── legacy_council/                   # ← legacy v0.1.0 code, kept as seed/context only.
│                                     #   NOT importable as a package; NOT wired into NS.
│                                     #   Removed entirely at M3 once unnecessary.
│
├── council/                          # ← THE NEW STACK (pure Python + asyncio; no framework deps)
│   ├── __init__.py
│   ├── agent.py                      # CouncilAgent — drop-in `complete(prompt) → CouncilResponse`
│   ├── policy.py                     # CouncilPolicy — task + budget → CouncilGenome (QD lookup)
│   ├── core.py                       # run_council() — the pure async pipeline
│   ├── context.py                    # CouncilContext, CouncilState, CouncilResponse, ProvenanceReceipt
│   ├── models.py                     # ModelClient (LiteLLM)
│   ├── tools.py                      # ToolClient (MCP / Z3 / clingo / Lean / Python / web)
│   ├── topology.py                   # CommunicationMode + Topology hierarchy (extended)
│   ├── ranker.py                     # ordinal + cardinal preference extraction
│   ├── normalizer.py                 # canonical-form extraction
│   ├── termination.py                # FixedRounds, JSDDivergence, ConFreeze, LTLfMonitor, …
│   │
│   ├── dialect/                      # L0 — speech-act algebra + protocol automata
│   │   ├── __init__.py
│   │   ├── moves.py                  # Move = Propose|Challenge|Concede|Retract|Question|Clarify|Vote|Abstain
│   │   ├── trace.py                  # immutable Trace; .to_events() bridge for L1
│   │   ├── parsers.py                # MoveBundle JSON parser; argument-mining fallback
│   │   ├── surface.py                # Move → natural-language rendering
│   │   └── protocols/
│   │       ├── base.py               # ProtocolAutomaton ABC
│   │       ├── deliberation.py       # Walton 2010 deliberation
│   │       ├── persuasion.py         # Walton-Krabbe persuasion
│   │       ├── inquiry.py            # Hitchcock-Parsons inquiry
│   │       ├── composite.py          # deliberation w/ persuasion sub-dialogues
│   │       └── socratic.py           # question-driven
│   │
│   ├── symbolic/
│   │   ├── verify/                   # L1 — verification spine
│   │   │   ├── __init__.py
│   │   │   ├── ltlf.py               # LTL_f AST + parser
│   │   │   ├── monitor.py            # LTL3 three-valued monitor
│   │   │   ├── spot_backend.py       # SPOT bindings (ltl2tgba)
│   │   │   ├── ltl2mon_backend.py    # pure-Python fallback (Bauer 2010)
│   │   │   ├── ispl.py               # Trace + automaton → ISPL for MCMAS
│   │   │   ├── smv.py                # Trace + automaton → SMV for NuSMV
│   │   │   ├── properties.py         # named-property library (10+ formulas)
│   │   │   └── interventions.py      # ReprompCorrective, ForceChallenge, TriggerVerifier, EscalateModel, FreezeAndAccept
│   │   ├── argue/                    # L2 — argumentation aggregator
│   │   │   ├── __init__.py
│   │   │   ├── baf.py                # BAF / QBAF data structures
│   │   │   ├── builders.py           # Trace → QBAF construction rules (no LLM extraction)
│   │   │   ├── semantics/
│   │   │   │   ├── df_quad.py        # Rago-Toni-Aurisicchio-Baroni KR 2016
│   │   │   │   ├── quad.py           # Quadratic Energy (Potyka 2018)
│   │   │   │   ├── euler.py          # Euler-based (Amgoud-Ben-Naim 2017)
│   │   │   │   └── coupled.py        # Strategic gradual semantics (DF-QuAD ⊕ ATL)  ← novel
│   │   │   ├── aggregator.py         # ArgumentationAggregator (Aggregator subclass)
│   │   │   ├── asp_backends.py       # extension semantics via clingo (preferred/stable/…)
│   │   │   └── visualisers.py        # Mermaid + GraphViz exporters
│   │   └── ilp/                      # L6 — ILP / ASP rule mining
│   │       ├── __init__.py
│   │       ├── popper.py             # Popper integration (Cropper-Morel)
│   │       ├── ilasp.py              # ILASP4 integration (Law et al.)
│   │       ├── asp_constraints.py    # clingo wrapper for integrity constraints
│   │       ├── trace_to_atoms.py     # Trace → ASP atoms / Popper background
│   │       ├── rule_to_automaton.py  # learned rules → ProtocolAutomaton subclass
│   │       └── verify_learned.py     # MCMAS verification of induced protocols
│   │
│   ├── calibrate/                    # L3 — calibrated disagreement
│   │   ├── __init__.py
│   │   ├── jsd.py                    # Jensen-Shannon divergence over agent answer distributions
│   │   ├── muse.py                   # MUSE-style subset-ensemble divergence
│   │   ├── privileged.py             # per-domain calibration (Privileged Knowledge)
│   │   └── isotonic.py               # temperature-scaled isotonic regression
│   │
│   ├── cascade/                      # L4 — cost-aware escalation cascade
│   │   ├── __init__.py
│   │   ├── distillation.py           # In-Context Distillation Cascade (2512.02543)
│   │   ├── router.py                 # multi-tier router (open-source ↔ frontier)
│   │   ├── budget.py                 # per-role $ + token budget allocation
│   │   └── strategies.py             # CascadeEscalation, RouteByDomain, …
│   │
│   ├── evolve/                       # L5 — quality-diversity over compositions
│   │   ├── __init__.py
│   │   ├── genome.py                 # CouncilGenome ↔ CouncilConfig isomorphism
│   │   ├── descriptors.py            # behavioural descriptors derived from L1 + L2
│   │   ├── archives/
│   │   │   ├── grid.py               # MAP-Elites
│   │   │   ├── cvt.py                # CVT-MAP-Elites
│   │   │   └── cmamae.py             # CMA-MAE wrapper around pyribs
│   │   ├── emitters/
│   │   │   ├── cmaes.py              # CMA-ES emitters
│   │   │   ├── llm_reflective.py     # GEPA-style reflective Pareto-genetic
│   │   │   ├── llm_diff.py           # AlphaEvolve-style diff edits on protocol automata
│   │   │   └── structural.py         # topology rewiring, role swap, calibrator change
│   │   ├── evaluate.py               # genome → CouncilResult via run_council
│   │   ├── pareto.py                 # Pareto-front extraction, hypervolume
│   │   └── redteam/
│   │       ├── __init__.py
│   │       ├── rainbow.py            # Rainbow-Teaming-style adversarial archive
│   │       └── coevolve.py           # symmetric Pareto co-evolution
│   │
│   └── adapters/                     # optional integrations (kept at the edges)
│       ├── __init__.py
│       ├── langgraph.py              # optional LangGraph wrapper
│       ├── mcp.py                    # MCP tool integration
│       ├── otel.py                   # OpenTelemetry tracing
│       └── mlflow.py                 # MLflow logging adapter
│
├── evaluation/                    # benchmark mode only — never imported by council/
│   ├── __init__.py
│   ├── metrics.py                    # task_accuracy + verification_pass_rate + ECE + …
│   ├── baselines.py                  # MoA, Self-MoA, ConFreeze, CoT-SC, … + matched-token wrappers
│   ├── shapley.py                    # per-genome contribution attribution
│   ├── statistical.py                # bootstrap CI, Wilcoxon, AIPW, Bradley-Terry, mixed-effects
│   └── pareto.py                     # front extraction across genomes
│
├── tasks/                         # benchmark loaders
│   ├── arc_agi_2.py
│   ├── frontiermath.py
│   ├── livecodebench.py
│   ├── swe_bench_pro.py
│   ├── hle.py
│   ├── zebralogic_hard.py
│   ├── putnam_axiom.py
│   ├── gaia.py
│   ├── webarena.py
│   ├── tau2bench.py
│   └── profiles.py                   # per-dataset TaskProfile registry
│
├── experiments/
│   ├── run.py                        # single-genome runner (CLI front-end)
│   ├── service.py                    # pure async service
│   ├── logging_adapter.py            # MLflow + OTEL
│   ├── transcript.py                 # formatting
│   ├── sweep.py                      # Hydra-multirun sweep
│   ├── evolve.py                     # QD evolution runner
│   ├── coevolve.py                   # co-evolutionary red/blue runner
│   └── reproduce/
│       ├── p1_verification.sh
│       ├── p2_argumentation.sh
│       ├── p3_qd.sh
│       ├── p4_coevolve.sh
│       └── p5_ilp.sh
│
├── apps/                             # the "wow" demos
│   ├── streamlit_demo.py             # hosted Streamlit Cloud space
│   ├── arc_agi_runner.py             # one-click ARC-AGI-2 submission
│   └── live_monitor.py               # live LTL_f monitor + Mermaid BAF visualiser
│
├── tests/                         # target ≥ 1500 functions by M6
│   ├── dialect/
│   ├── symbolic/
│   ├── calibrate/
│   ├── cascade/
│   ├── evolve/
│   └── integration/
│
├── papers/                           # already populated; cite from here
└── .claude/
    ├── CLAUDE.md                     # the 12-principle Constitution (this branch)
    ├── rules/
    │   ├── architecture.md           # binding architecture rules (this branch)
    │   ├── code-style.md             # general Python style
    │   ├── testing.md                # pytest discipline, FakeModelClient, RUN_INTEGRATION
    │   ├── verification.md           # LTL_f authoring, monitor invariants
    │   ├── argumentation.md          # BAF/QBAF rules, semantics ABC contracts
    │   ├── evolution.md              # genome, descriptors, emitters
    │   └── papers.md                 # paper authoring, theorem-claim discipline
    ├── agents/
    │   ├── constitution-reviewer.md      # extended for NS
    │   ├── theorem-checker.md            # NEW — audits theorem statements/proofs
    │   ├── ltl-property-author.md        # NEW — drafts new LTL_f properties
    │   ├── qbaf-reviewer.md              # NEW — audits Trace→QBAF construction rules
    │   ├── qd-runner.md                  # NEW — drives evolve/coevolve experiments
    │   ├── paper-drafter.md              # scaffolds paper LaTeX from MLflow results
    │   └── workstream-planner.md         # maps requests to workstreams W0–W7
    ├── skills/
    │   ├── check-constitution/SKILL.md   # ported, extended
    │   ├── new-protocol/SKILL.md         # legacy (still works for `council/`)
    │   ├── new-aggregation/SKILL.md      # legacy
    │   ├── new-topology/SKILL.md         # legacy
    │   ├── new-protocol-automaton/SKILL.md   # NEW — scaffolds a ProtocolAutomaton + tests
    │   ├── new-property/SKILL.md             # NEW — scaffolds an LTL_f property + tests
    │   ├── new-semantics/SKILL.md            # NEW — scaffolds a gradual-semantics + tests
    │   ├── new-descriptor/SKILL.md           # NEW — scaffolds a behavioural descriptor + tests
    │   ├── new-emitter/SKILL.md              # NEW — scaffolds a QD emitter + tests
    │   ├── new-calibrator/SKILL.md           # NEW — scaffolds an L3 calibrator + tests
    │   ├── new-cascade-strategy/SKILL.md     # NEW — scaffolds an L4 cascade strategy + tests
    │   ├── mine-rules/SKILL.md               # NEW — runs Popper/ILASP4 over a labelled trace bundle
    │   ├── run-pareto/SKILL.md               # NEW — Pareto-front extraction + hypervolume on a result set
    │   ├── paper-skeleton/SKILL.md           # NEW — generates a P<n> LaTeX skeleton with theorem placeholders
    │   ├── ablation-row/SKILL.md             # NEW — generates an ablation-table row from a frozen config
    └── settings.json                     # extended (§13.5)
```

This is the **target**. We do **not** create directories until the corresponding workstream is active. §7 specifies which workstream creates what.

---

## 5. The Constitution (12 principles, binding)

The active copy lives at [`.claude/CLAUDE.md`](./.claude/CLAUDE.md). This section reproduces it for documentation; if the two ever drift, `.claude/` wins.

### Constitution (binding)

Every design decision is evaluated against these. Violations require explicit user approval. Several principles are **encoded at the type level** — meaning the Python type system rejects code that violates them.

1. **The council is an agent, not a benchmark.** *Unchanged from legacy §1.* If a decision helps benchmarking but hurts the agent interface, choose the agent.

2. **Same interface as a single LLM.** *Unchanged from legacy §2.* `CouncilAgent.complete(prompt) → CouncilResponse` with zero caller changes. `CouncilResponse` is a dataclass that subsumes `AgentResponse` plus a `ProvenanceReceipt`.

3. **Topology controls visibility. Protocol controls *admissibility*. Aggregator controls decision.** *Strengthened from legacy §3.* The protocol is now a **typed `ProtocolAutomaton`** — a finite-state machine over speech-acts — not a free-form prompt builder. `Aggregator` is parameterised by `Trace`, never by raw text. (Type-level enforced.)

4. **Structured types over free text.** *New (replaces legacy §4 "structured output over regex").* Every `AgentResponse` carries a `Move`. The free-text content is a *fallback* path for backwards-compatibility benchmarking only and is flagged in the trace metadata as `tier="text-fallback"`. (Type-level enforced.)

5. **Calibrated confidence is the council's unique value.** *Strengthened from legacy §5.* Every `CouncilResponse.confidence` is **derived from an information-theoretic disagreement signal or an argumentation-strength margin**, and carries its derivation tag (`"jsd"`, `"baf-margin"`, `"monitor-verdict"`, `"copeland"`, …). **Plurality fraction is banned** as a confidence signal. (Type-level enforced via `Confidence = JSDConfidence | BAFMarginConfidence | MonitorVerdictConfidence | CopelandConfidence`.)

6. **Every council run must beat (matched-compute) Mixture-of-Agents on at least one Pareto axis.** *New (replaces legacy §6 "must beat majority-vote-without-deliberation").* The 2026 baseline is MoA, not majority-no-deliberation. Constitution §6 violations are publication-blockers, not mere code-review concerns.

7. **Cost is first-class.** *Unchanged from legacy §7.* Every response carries its cost. Every config has an estimated cost. Budgets are enforced.

8. **The core pipeline has zero framework dependencies.** *Unchanged from legacy §8 in spirit.* `council/core.py`, `agent.py`, `policy.py`, `dialect/`, `symbolic/`, `calibrate/`, `cascade/`, `evolve/` are pure-Python + asyncio. LangGraph, Hydra, MLflow, OpenTelemetry live in `council/adapters/` and `experiments/`. **No exception** — even the QD layer's pyribs dependency lives in an extra (`[evolve]`); the core path falls back to a pure-Python random-search emitter.

9. **Correctness before features.** *Unchanged from legacy §9.* A correct DF-QuAD aggregator on 3 problems beats a broken one on 1000.

10. **Anonymise by default.** *Unchanged from legacy §10.* Agent identities are stripped during deliberation, preserved in metadata. The new substrate makes this trivial — the typed Move's `agent_id` is replaced by a stable label `A`/`B`/`C`/… by `_build_visibility_context` in **exactly one place** (legacy invariant ported).

11. **Symbolic outputs are first-class.** *New.* Every `CouncilResponse` carries a `ProvenanceReceipt` containing: the typed `Trace`, the QBAF (when applicable), monitor verdicts (when applicable), ASP groundings (when applicable), Lean/Z3 certificates (when applicable), and a per-move cost ledger. Receipts are **always emitted** when the corresponding layer is active in the genome — no "best effort" silent omission.

12. **The verifier can intervene.** *New.* `LTLfMonitorTermination` and `Intervention` allow the symbolic layer to *redirect* deliberation, not merely observe it. Specifically: on a `⊥` verdict from any active monitor, the configured intervention executes before the next deliberation round. This is what "LLM-Modulo at the dialogue level" means; the legacy stack only had passive monitoring (none, in fact).

### Constitution sections that are NS-specific

- **§5.1 (derivation).** Confidence sources, in order of authority: `MonitorVerdictConfidence` (when the verifier returns ⊤ on the answer-justifying property) > `BAFMarginConfidence` (when the QBAF has a single-strength winner) > `JSDConfidence` (default information-theoretic) > `CopelandConfidence` (social-choice fallback for ordinal aggregation).
- **§6.1 (matched compute).** "Matched compute" means equal **output tokens** by default and equal **dollar cost** when both are reportable. Reviewer-style: every NS table reports both.
- **§11.1 (receipt completeness).** `ProvenanceReceipt.is_complete()` returns `True` iff every move has cost, every Vote has at least one evidence atom, every ⊥-verdict triggered an intervention, and the QBAF's argument count equals the Propose count.

---

## 6. Architecture rules (binding, type-level)

The active copy lives at [`.claude/rules/architecture.md`](./.claude/rules/architecture.md). This section reproduces it for documentation; if the two ever drift, `.claude/` wins.

### 6.1 Layer responsibilities

| Layer | File(s) | May do | May NOT do |
|---|---|---|---|
| **L0 dialect/moves** | `council/dialect/moves.py` | Define the typed `Move` ADT, `Claim`, `Force`, `ClaimDomain` | Call models; reference protocols, topologies, aggregators |
| **L0 dialect/trace** | `council/dialect/trace.py` | Provide immutable `Trace` operations: `by_id`, `at_round`, `by_force`, `append`, `to_events` | Mutate state; depend on protocol-automaton internals |
| **L0 dialect/protocols** | `council/dialect/protocols/*.py` | Define `ProtocolAutomaton` ABC and concrete automata; expose `state(trace)`, `legal_forces(trace, agent_id)`, `is_terminal(trace)`, `is_answer_phase(trace)` | Construct prompts (that's `dialect/surface.py`); call models; read external state |
| **L0 dialect/parsers, surface** | `council/dialect/{parsers,surface}.py` | Parse LLM output → `Move`; render `Move` → NL | Embed business logic about admissibility |
| **L1 symbolic/verify** | `council/symbolic/verify/*` | Compile LTL₍f₎ properties → DFA; step monitors over `Trace.to_events()`; encode `(automaton, trace)` → ISPL/SMV; emit interventions | Construct prompts; call generation models; reach into aggregators |
| **L2 symbolic/argue** | `council/symbolic/argue/*` | Build BAF/QBAF from `Trace`; apply gradual semantics; export DOT/Mermaid | Re-extract arguments from raw text; mutate the trace; call generation models for argument-mining inside the headline path (a **fallback** mining hook is allowed under Constitution §4 and must be tagged `tier="argument-mining-fallback"`) |
| **L3 calibrate** | `council/calibrate/*` | Compute JSD / MUSE / privileged-knowledge calibration; produce `Confidence` values; expose `JSDDivergenceTermination`, `ConFreezeTermination` | Construct prompts; mutate the trace; call models (JSD reads existing distributions or token logprobs; per-domain calibration reads `TaskProfile`) |
| **L4 cascade** | `council/cascade/*` | Decide which agent / model handles which step; track $/token; trigger escalation | Construct deliberation prompts; mutate the trace; reach into aggregators |
| **L5 evolve** | `council/evolve/*` | Search the genome space via QD; compute behavioural descriptors **from L1+L2 outputs**; manage Pareto fronts | Call deliberation directly (always via `evaluate.py` → `run_council`); reach into protocol internals beyond what the genome exposes |
| **L6 symbolic/ilp** | `council/symbolic/ilp/*` | Run Popper/ILASP4 over labelled traces; enforce ASP integrity constraints via clingo; verify induced rules via MCMAS | Mutate the trace; call generation models; replace `dialect/` automata at runtime (only at genome-creation time, via `rule_to_automaton.py`) |
| **Core** | `council/core.py` | Compose the layers; build `VisibilityContext` (single source of anonymisation); thread response formats; honour interventions | Import `langgraph`, `hydra`, `mlflow`, `opentelemetry`, `langchain` |
| **Agent** | `council/agent.py` | Wrap `run_council` in the single-LLM `complete()` interface; assemble `ProvenanceReceipt`; route to escalation | Re-implement pipeline logic; recompute confidence in raw-text space |
| **Policy** | `council/policy.py` | Map `(prompt, TaskProfile, budget)` → `CouncilGenome` (drawing from the QD archive when present) | Execute councils |
| **ModelClient** | `council/models.py` | Route calls to LiteLLM; cache; meter; retry; inject faults | Know about topology/protocol/ranking semantics |
| **ToolClient** | `council/tools.py` | Route tool calls (MCP / Z3 / clingo / Lean / Python sandbox / web) | Construct prompts |

### 6.2 Forbidden imports (rejected by CI)

- `council/core.py`, `agent.py`, `policy.py`, and any `dialect/`, `calibrate/`, `cascade/`, `evolve/` module **MUST NOT** import `langgraph`, `hydra`, `mlflow`, `opentelemetry`, `langchain`, `langchain_*`, `pyribs` (without the `evolve` extra guard), `spot` (without the `verify` extra guard), `clingo` (without the `ilp` extra guard).
- Any `council/*.py` **MUST NOT** import from `evaluation/`, `experiments/`, `apps/`.
- Layer modules **MUST NOT** import each other except through dataclasses defined in `council/context.py` and `council/dialect/moves.py`. The exceptions are explicitly approved below.

### 6.3 Approved exceptions (permanent)

1. **`council/symbolic/argue/aggregator.py` may import `council/calibrate/jsd.py`** to build calibrated base scores. Documented; auditable; no other path.
2. **`council/cascade/strategies.py` may import `council/models.py`** to invoke escalated/upgraded models. The model is *injected* via the strategy's `__init__`, never hardcoded.
3. **`council/evolve/evaluate.py` may import `council/core.run_council`** to evaluate genomes. This is the only allowed path from L5 into the pipeline.
4. **`council/symbolic/verify/interventions.py` may import `council/dialect/moves.py`** to inject `Move`s on `⊥` verdicts (e.g. `ForceChallenge`).
5. **`evaluation/` may import from `council/`** but never the reverse. Same one-way relation as legacy.
6. **`apps/` may import from `council/` and `evaluation/`** but never the reverse.

### 6.4 Required contracts

```python
# L0 — speech-act algebra
class ProtocolAutomaton(ABC):
    @abstractmethod
    def state(self, trace: Trace) -> tuple[str, str]: ...
    @abstractmethod
    def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]: ...
    @abstractmethod
    def is_terminal(self, trace: Trace) -> bool: ...
    @abstractmethod
    def is_answer_phase(self, trace: Trace) -> bool: ...

# L1 — runtime monitor
class LTL3Monitor(ABC):
    @abstractmethod
    def step(self, event: dict) -> Verdict: ...      # Verdict = Top | Bottom | Unknown
    @abstractmethod
    def reset(self) -> None: ...

class Property(ABC):
    name: ClassVar[str]
    formula: ClassVar[str]                            # LTL_f source
    @abstractmethod
    def compile(self) -> LTL3Monitor: ...

class Intervention(ABC):
    @abstractmethod
    async def execute(self, trace: Trace, violated: Property,
                      ctx: CouncilContext) -> Trace: ...

# L2 — argumentation aggregator
class GradualSemantics(ABC):
    @abstractmethod
    def evaluate(self, baf: QBAF) -> dict[str, float]: ...

class Aggregator(ABC):
    @abstractmethod
    async def aggregate(self, trace: Trace, *, original_question: str) -> AggregationResult: ...

# L3 — calibration
class Calibrator(ABC):
    @abstractmethod
    def calibrate(self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain) -> float: ...

# L4 — cascade
class RoutingStrategy(ABC):
    @abstractmethod
    async def route(self, trace: Trace, ctx: CouncilContext) -> AgentSpec: ...

# L5 — evolve
class Emitter(ABC):
    @abstractmethod
    def emit(self, archive: Archive) -> list[CouncilGenome]: ...

class Descriptor(ABC):
    @abstractmethod
    def compute(self, result: CouncilResult) -> float: ...

# L6 — ILP
class RuleMiner(ABC):
    @abstractmethod
    async def mine(self, traces: list[LabelledTrace]) -> list[ASPRule]: ...
```

Every layer base class lives in its own module, uses `abc.ABC` with `@abstractmethod`, and has a corresponding test base class in `tests/`.

### 6.5 Per-agent and per-genome configuration

`CouncilGenome` (in `council/evolve/genome.py`) carries the *full* configuration — see [`COUNCIL_NS_PLAN.md`](./COUNCIL_NS_PLAN.md) §6.6 for the canonical spec. Per-agent fields (`temperature`, `max_tokens`, `system_prompt`) are unchanged from legacy `AgentConfig` and ported.

### 6.6 YAML runner schema (`experiments/run.py`)

The YAML contract is a strict superset of the legacy contract:

```yaml
genome:
  members:                          # list of AgentSpec
    - {model: "openai/gpt-4o-mini", temperature: 0.7, persona: "skeptic"}
    - {model: "anthropic/claude-3.5-sonnet", temperature: 0.4}
    - {model: "openrouter/google/gemma-3-27b-it:free"}
  topology: {name: "CompleteGraphTopology"}
  protocol: {name: "DeliberationAutomaton", params: {max_phases: 5}}
  aggregator: {name: "ArgumentationAggregator", semantics: "DFQuAD", calibrator: "JSD"}
  calibration: {name: "MUSE", privileged_per_domain: true}
  monitors: ["NoSycophancyCascade", "EventuallyDecide", "NoPrematureConsensus", "ProvenanceCompleteness"]
  termination:
    - {name: "LTLfMonitorTermination"}
    - {name: "JSDDivergenceTermination", threshold: 0.05}
    - {name: "FixedRounds", max_rounds: 3}
  cascade: {name: "InContextDistillationCascade", student_pool: [...], teacher_pool: [...]}
task: {profile: "frontiermath_t4"}
budget: {max_usd: 10.0, max_tokens: 200000, max_seconds: 1200}
```

### 6.7 Task-aware prompting

`TaskProfile.prompt_hint` (per-dataset answer-format instruction) is **deprecated as a separate field** in NS. Its functionality is subsumed by:
- `Claim.domain` (typed at L0) — answer-format is determined by domain.
- `dialect/surface.py` — domain-conditioned NL rendering.
- `apps/` and `experiments/` task profiles — per-dataset overrides.

Existing legacy `prompt_hint` callers continue to work via a thin shim in `council/policy.py`.

---

## 7. Workstreams W0–W7

The bible's "phases" vocabulary is replaced by **workstreams** because (a) workstreams advance in parallel where dependency permits, (b) the publication track demands non-strict ordering, and (c) the existing `phase-planner` agent's vocabulary maps cleanly to the legacy stack on `develop`/`main` while `workstream-planner` is the NS analogue.

### Dependency graph

```
W0 substrate (L0)
   ├─→ W1 verification (L1)            ────────────┐
   ├─→ W2 argumentation (L2)        ───────────┐   │
   └─→ W3 calibration (L3)         ─────────┐  │   │
                                            │  │   │
W4 cascade (L4)  ←──depends on W3──────────┘  │   │
                                               │   │
W5 evolve (L5)   ←──depends on W1,W2,W3,W4─────┴───┘
W6 ILP/ASP (L6)  ←──depends on W0,W1
W7 evaluation, demos, papers ←──depends on all
```

### W0 — Substrate (L0): typed Move algebra + protocol automata

- **Module paths.** `council/dialect/{moves,trace,parsers,surface}.py`, `council/dialect/protocols/{base,deliberation,persuasion,inquiry,composite,socratic}.py`, `council/{core,context,agent,policy,topology,ranker,normalizer,termination,models,tools}.py`.
- **Acceptance criteria.**
  - The Move ADT (`Propose | Challenge | Concede | Retract | Question | Clarify | Vote | Abstain`) is fully implemented with frozen-slots dataclasses.
  - `Trace.to_events()` produces atomic propositions consumable by L1 (round-trip test against a hand-crafted trace).
  - `DeliberationAutomaton` (Walton 2010) implements `state`, `legal_forces`, `is_terminal`, `is_answer_phase`.
  - The legacy `PeerReviewProtocol` and `DirectAnswerProtocol` embed isomorphically into `ProtocolAutomaton` instances; **mechanised as a pytest test** (`test_legacy_protocol_isomorphism.py`).
  - `run_council(prompt, genome, model_client) → CouncilResult` runs end-to-end on GSM8K-via-`tasks/profiles.py` with parity to legacy ± 1 pp accuracy.
  - mypy strict passes on every file in `council/dialect/` and `council/core.py`.
- **Theorem-level deliverable.** None at L0 (it's the substrate). The publishable claim is **type-correctness of the protocol-automaton encoding** — every legacy protocol embeds isomorphically into a `ProtocolAutomaton`. Mechanise in pytest.
- **Papers.** Feeds P1, P2, P5 directly; substrate for everything.
- **PR sequence.** (Each PR ≤ 600 LOC.)
  1. `feature/ns-w0-bootstrap` — empty `council/__init__.py` and empty layer packages (verifies the package re-emerges cleanly after the migration commit removed the legacy contents).
  2. `feature/ns-w0-moves` — `dialect/moves.py` + tests.
  3. `feature/ns-w0-trace` — `dialect/trace.py` + tests.
  4. `feature/ns-w0-parsers-surface` — JSON-schema-based parsers + NL renderer + tests.
  5. `feature/ns-w0-protocol-automaton-base` — `dialect/protocols/base.py` + tests.
  6. `feature/ns-w0-deliberation-automaton` — Walton 2010 deliberation + tests.
  7. `feature/ns-w0-other-automata` — persuasion, inquiry, composite, socratic + tests.
  8. `feature/ns-w0-models-tools` — port `models.py`; new `tools.py` skeleton.
  9. `feature/ns-w0-topology-port` — port topology hierarchy unchanged.
  10. `feature/ns-w0-pipeline` — `core.py`, `context.py`, `agent.py`, `policy.py` (genome lookup stubbed).
  11. `feature/ns-w0-gsm8k-parity` — task profile, end-to-end parity test.

### W1 — Verification spine (L1)

- **Module paths.** `council/symbolic/verify/{ltlf,monitor,spot_backend,ltl2mon_backend,ispl,smv,properties,interventions}.py`, `council/termination.py` (new strategies).
- **Acceptance criteria.**
  - LTL₍f₎ AST + parser; round-trip test: parse `G (consensus → ∃i. evidence(i))` → compile → step over a hand-crafted trace.
  - LTL3 three-valued monitor (Bauer-Leucker-Schallhart) implemented over the AST. `step(event) ∈ {⊤, ⊥, ?}`.
  - SPOT backend (`pip install spot`) wired; pure-Python `ltl2mon` fallback when SPOT unavailable.
  - **Named-property library** with at minimum: `RefutationReachable`, `NoPrematureConsensus`, `FairnessOfRoles`, `NoMonotoneAgreementCollapse`, `EventuallyDecide`, `BoundedRound`, `NoSycophancyCascade`, `ProvenanceCompleteness`, `ChallengeBeforeConsensus`, `ModalitySafe`. Each property has a positive trace test (returns ⊤) and a negative trace test (returns ⊥).
  - ISPL emitter for MCMAS; offline check on a 4-agent / 4-round example; verifies `EventuallyDecide` and `RefutationReachable`.
  - `LTLfMonitorTermination` plugs into `CompositeTermination`.
  - `Intervention` ABC + 5 concrete interventions: `ReprompCorrective`, `ForceChallenge`, `TriggerVerifier`, `EscalateModel`, `FreezeAndAccept`.
- **Theorems.**
  - **T1 — Soundness of LTL3 monitors.** Cite Bauer-Leucker-Schallhart 2011; mechanise as a pytest property-based test.
  - **T2 — Compositionality (assume-guarantee).** Original adaptation of Pnueli 1985 to the dialogue setting. Proof in `docs/theory.md`; appendix of P1.
  - **T3 — No-go for consensus-only aggregation.** Identify a CTLK invariant that no purely consensus-driven aggregator satisfies; verify its un-satisfiability for `MajorityVote`, `BordaCount`, `CondorcetAggregation` via small-instance MCMAS.
- **Papers.** P1 main contribution; appears as ablation in P3, P4.
- **PR sequence.**
  1. `feature/ns-w1-ltlf-ast`
  2. `feature/ns-w1-ltl3-monitor`
  3. `feature/ns-w1-spot-backend` + `feature/ns-w1-ltl2mon-backend`
  4. `feature/ns-w1-properties` (10+ named properties)
  5. `feature/ns-w1-ispl-mcmas`
  6. `feature/ns-w1-interventions`
  7. `feature/ns-w1-ltlf-termination`
  8. `feature/ns-w1-theorems` (Lean / Coq sketches optional; pytest + docs/theory.md mandatory)

### W2 — Argumentation aggregator (L2)

- **Module paths.** `council/symbolic/argue/{baf,builders,aggregator,asp_backends,visualisers}.py`, `council/symbolic/argue/semantics/{df_quad,quad,euler,coupled}.py`.
- **Acceptance criteria.**
  - BAF / QBAF dataclass with arguments, attacks, supports, base scores.
  - `build_qbaf(trace, calibrator)` is **deterministic** for a fixed trace — round-trip test.
  - Four gradual semantics implemented: DF-QuAD (Rago-Toni-Aurisicchio-Baroni), Quadratic Energy (Potyka), Euler-based (Amgoud-Ben-Naim), and the **novel Strategic-Coupled** semantics (DF-QuAD ⊕ ATL coalition reasoning).
  - `ArgumentationAggregator` produces an `AggregationResult` with `BAFMarginConfidence` and `metadata.baf_mermaid` (live-render-ready).
  - Mermaid + GraphViz exporters tested against a canonical Walton-Krabbe example.
  - ASP-backed extension semantics (preferred/stable/grounded) via clingo, optional under `[argue-asp]` extra.
- **Theorems.**
  - **T4 — Recovery-of-Borda lemma.** DF-QuAD on vote-only BAFs recovers Borda count up to monotone re-scaling. Short proof.
  - **T5 — Manipulability bound.** Flip-cost upper bound parameterised by (in-degree, attack/support ratio). Builds on Baroni-Rago-Toni 2019.
  - **T6 — Rationality-postulate characterisation.** Identify which Caminada-Amgoud postulates the aggregator satisfies; identify which Arrow-style axiom is necessarily violated (by Gibbard-Satterthwaite).
  - **T7 — Strategic gradual semantics satisfies T3's invariant.** Original.
- **Papers.** P2 main contribution; appears as headline aggregator in P3, P4, F.
- **PR sequence.**
  1. `feature/ns-w2-baf-types`
  2. `feature/ns-w2-builders`
  3. `feature/ns-w2-df-quad`
  4. `feature/ns-w2-quad-euler`
  5. `feature/ns-w2-coupled-semantics` (novel)
  6. `feature/ns-w2-aggregator`
  7. `feature/ns-w2-visualisers` (Mermaid + DOT)
  8. `feature/ns-w2-asp-extensions` (optional)
  9. `feature/ns-w2-theorems`

### W3 — Calibrated disagreement (L3)

- **Module paths.** `council/calibrate/{jsd,muse,privileged,isotonic}.py`.
- **Acceptance criteria.**
  - `JSDCalibrator.compute(distributions: list[dict[str, float]]) → float` — tested against a closed-form for n=2 uniform vs Dirac.
  - `MUSECalibrator` — subset-ensemble divergence; matches Kruse et al. 2025 reference numbers on a synthetic toy.
  - `PrivilegedKnowledgeCalibrator` — per-domain weights from `TaskProfile`; defaults match the DOCX table (factual 5%, math 0%, coding partial).
  - `IsotonicCalibrator` — temperature-scaled isotonic regression; ECE on a held-out GSM8K split drops below 0.05.
  - `JSDDivergenceTermination`, `ConFreezeTermination` plug into `CompositeTermination`.
- **Theorems.** None at L3 directly; the calibration accuracy is empirical (ECE ≤ 0.05 vs legacy 0.20).
- **Papers.** P2 (calibrator-fed BAF base scores), P3 (calibration as a behavioural-descriptor signal).
- **PR sequence.**
  1. `feature/ns-w3-jsd`
  2. `feature/ns-w3-muse`
  3. `feature/ns-w3-privileged`
  4. `feature/ns-w3-isotonic`
  5. `feature/ns-w3-terminations`

### W4 — Cost-aware escalation cascade (L4)

- **Module paths.** `council/cascade/{distillation,router,budget,strategies}.py`.
- **Acceptance criteria.**
  - `InContextDistillationCascade` — student-teacher cascade matching the 2.5× cost reduction on ALFWorld (cite `2512.02543v3`).
  - Multi-tier router (open-source via Ollama / OpenRouter `:free` ↔ frontier).
  - Per-role $ budget + token budget allocation.
  - `CascadeEscalationStrategy` extends the legacy `EscalationStrategy` ABC with `route(trace, ctx) → AgentSpec`.
  - End-to-end test on a synthetic 100-task GSM8K subset: ≥ 30% cost reduction at ≤ 2pp accuracy loss.
- **Papers.** P3 (cost-Pareto axis), F (flagship cost-Pareto).
- **PR sequence.**
  1. `feature/ns-w4-budget`
  2. `feature/ns-w4-router`
  3. `feature/ns-w4-distillation`
  4. `feature/ns-w4-strategies`

### W5 — Quality-Diversity over council compositions (L5)

- **Module paths.** `council/evolve/{genome,descriptors,evaluate,pareto}.py`, `council/evolve/archives/{grid,cvt,cmamae}.py`, `council/evolve/emitters/{cmaes,llm_reflective,llm_diff,structural}.py`, `council/evolve/redteam/{rainbow,coevolve}.py`.
- **Acceptance criteria.**
  - `CouncilGenome` is a frozen dataclass round-trippable to YAML; isomorphic to the YAML schema in §6.6.
  - **Behavioural descriptors** (≥ 7) computed from L1+L2+L3 outputs: `disagreement_persistence`, `qbaf_density`, `role_entropy`, `evidence_anchor_rate`, `cost`, `monitor_pass_rate`, `mast_coverage`. Tests for each.
  - CMA-MAE on pyribs (`[evolve]` extra) wraps `EvolutionStrategyEmitter`. Pure-Python fallback emitter for the no-extras path.
  - `LLMReflectiveEmitter` (GEPA-style) and `LLMDiffEmitter` (AlphaEvolve-style) both implemented; tests assert that emitted genomes are well-formed.
  - `StructuralEmitter` for topology rewiring, role swap, calibrator change.
  - `evaluate.py` runs a genome via `run_council` and returns `(fitness, descriptors)`.
  - **Co-evolution.** `RainbowTeaming` adversarial archive with axes (target_capability, attack_strategy). `CoevolveLoop` runs (host, parasite) pairs.
  - End-to-end QD run on GSM8K (100 tasks, 50 generations) produces a non-trivial Pareto front (hypervolume strictly increases in ≥ 80% of generations).
- **Theorems.**
  - **T8 — QD coverage theorem.** Under the verifier-derived descriptor space, expected coverage at generation T strictly exceeds single-objective optimisation at matched evaluations. Builds on Qian-Xue-Wang-Filipič-Ochoa 2025.
  - **T9 — Pareto-domination bound.** Under matched compute, no single council in the archive Pareto-dominates the QD-illuminated frontier.
  - **T10 — Robustness theorem.** A council passing the chosen monitors + sitting on the QD Pareto front is k-robust to adversarial archive samples.
- **Papers.** P3 main; P4 main (the co-evolutionary half).
- **PR sequence.**
  1. `feature/ns-w5-genome`
  2. `feature/ns-w5-descriptors`
  3. `feature/ns-w5-archives`
  4. `feature/ns-w5-cmaes-emitter`
  5. `feature/ns-w5-llm-emitters`
  6. `feature/ns-w5-structural-emitter`
  7. `feature/ns-w5-evaluate-pareto`
  8. `feature/ns-w5-rainbow-teaming`
  9. `feature/ns-w5-coevolve`
  10. `feature/ns-w5-theorems`

### W6 — ILP / ASP rule mining (L6)

- **Module paths.** `council/symbolic/ilp/{popper,ilasp,asp_constraints,trace_to_atoms,rule_to_automaton,verify_learned}.py`.
- **Acceptance criteria.**
  - `ASPConstraint.enforce(move, trace)` returns `(allowed, witness)` via clingo.
  - **CLMASP-replication.** Lift VirtualHome-style executability from <2% to >90% on a held-out plan-set (cite `2406.03367`).
  - Popper integration: learn first-order rules from labelled traces (success-vs-failure partition).
  - ILASP4 integration: learn ASP rules from positive/negative trace examples.
  - `rule_to_automaton.py` converts learned rules to a `ProtocolAutomaton` subclass; `verify_learned.py` runs MCMAS to confirm soundness against the L1 property library.
  - Round-trip test: learn → verify → re-verify holds for 5+ benchmark domains.
- **Theorems.**
  - **T12 — Soundness of ILP-induced protocols.** Corollary of T1; mechanise as a pytest test on at least one learned protocol.
  - **T13 — Generalisation characterisation.** When do learned rules transfer across task domains? Empirical lower-bound complement.
- **Papers.** P5 main contribution; ablation row in F.
- **PR sequence.**
  1. `feature/ns-w6-asp-constraints`
  2. `feature/ns-w6-trace-to-atoms`
  3. `feature/ns-w6-popper`
  4. `feature/ns-w6-ilasp`
  5. `feature/ns-w6-rule-to-automaton`
  6. `feature/ns-w6-verify-learned`
  7. `feature/ns-w6-clmasp-replication`

### W7 — Evaluation, demos, papers

- **Module paths.** `evaluation/*`, `tasks/*`, `experiments/*`, `apps/*`, `docs/*`.
- **Acceptance criteria.**
  - All Tier-A and Tier-B benchmarks loadable via `tasks/profiles.py` (§11).
  - Baselines from §11.2 implemented and tested.
  - Ablation-matrix runner (`experiments/sweep.py`) generates the ablation table from §11.3 with bootstrap CIs.
  - **Streamlit demo** (`apps/streamlit_demo.py`) — sycophancy-cascade scenario, Mermaid BAF, monitor verdicts. Hosted on Streamlit Cloud.
  - **One-click ARC-AGI-2 runner** (`apps/arc_agi_runner.py`) — Colab notebook + ProvenanceReceipt PDF.
  - **30-second demo video** — recorded; embedded in README.
  - Per-paper reproductions in `experiments/reproduce/`.
  - `docs/benchmarks.md` — every paper number reproducible by a one-command script.
- **Papers.** All five + the flagship.
- **PR sequence.**
  1. `feature/ns-w7-task-loaders` (×N tasks)
  2. `feature/ns-w7-baselines` (MoA, Self-MoA, ConFreeze, …)
  3. `feature/ns-w7-novel-metrics` (verification_pass_rate, ECE, hypervolume, …)
  4. `feature/ns-w7-runner-split` (D17 fix; CLI / service / logging adapter / transcript)
  5. `feature/ns-w7-sweep`
  6. `feature/ns-w7-streamlit-demo`
  7. `feature/ns-w7-arc-agi-runner`
  8. `feature/ns-w7-mlflow-otel-adapters`
  9. `feature/ns-w7-paper-reproductions`

---

## 8. Defect ↔ workstream ↔ theorem ↔ paper crosswalk

Every defect from `COUNCIL_NS_PLAN.md` §2.2 is fixed by a specific workstream and feeds into specific theorems/papers.

| Defect | Sev | Workstream | Theorem(s) | Paper(s) |
|---|---|---|---|---|
| **D1** Free-text `AgentResponse.content` | B | W0 | (substrate; type-correctness mechanised) | P1, P2, P3, P5, F |
| **D2** Plurality-fraction confidence | B | W2, W3 (banned at type level by Constitution §5) | T4, T5 | P2, F |
| **D3** No symbolic component | B | W1, W2, W6 | T1–T7, T12 | P1, P2, P5, F |
| **D4** Two-tier policy if-statement | B | W5 (genome lookup) | T8, T9 | P3, F |
| **D5** Plurality-on-canonical termination | H | W3 (JSD/ConFreeze) + W1 (LTLfMonitor) | — | P1, P2, P3 |
| **D6** Single dataset (GSM8K) | H | W7 | — | P1, P2, P3, P4, P5, F |
| **D7** Round-parity-only "dynamic" topology | H | W5 (learned/GNN-routed topologies as genome dimension) | T9 | P3, F |
| **D8** Hardcoded 2-cycle PeerReviewProtocol | H | W0 (ProtocolAutomaton replaces it) | (T1 attaches to it) | P1, P5 |
| **D9** Raw-string dissent in agent.py | H | W2/W3 (canonical-form post-aggregation; type system enforces) | — | P2 |
| **D10** No tools | H | W0 (ToolClient) + W4 (per-step tools) | — | P3, P4, F |
| **D11** DOCX-vs-code drift | H | W3 (MUSE/JSD/ConFreeze, privileged), W4 (cascade), W7 (modality-sabotage diagnostic, provenance receipts), W5 (TRINITY-style coordinator alternative) | — | F (the integration story) |
| **D12** Missing baselines | H | W7 | — | every paper |
| **D13** Round-parity in aggregation | H | W2 (automaton-derived phases) | — | P2 |
| **D14** Hardcoded escalation threshold | M | W4 (per-domain) | — | P3 |
| **D15** No QD / co-evolution | M | W5 | T8–T11 | P3, P4, F |
| **D16** task_accuracy gaps | M | W7 (semantic / execution / step grading) | — | P3 (esp. SWE-bench Pro), F |
| **D17** experiments/run.py monolith | M | W7 (CLI / service / adapter / transcript split) | — | F (artifact hygiene) |

---

## 9. Publication track (P1–P5, F)

For each paper: layers, theorems, headline empirics, deadline, backup venue, and the **milestone** that gates submission.

### P1 — Verified Deliberation: Model-Checking Multi-LLM Councils with Epistemic-Strategic Logic

- **Layers:** L0 + L1.
- **Theorems:** T1 (LTL3 soundness, cited), **T2 (compositionality, original)**, **T3 (no-go for consensus-only, original)**.
- **Headline empirics.** Tier-A: Putnam-AXIOM Variation (drop ≤ 5pp vs Original; baseline 15–25pp), ZebraLogic-hard (LLM + clingo hybrid). Per-property pass rate as the headline metric. Compose with the L0 substrate paper.
- **Sections.** Introduction (model-checking deliberation); Background (LTL₍f₎, MCMAS, multi-agent debate); Substrate (typed Move algebra, ProtocolAutomaton); Verification spine (LTL3 monitors, ISPL emitter, interventions); Theorems (T1–T3); Empirics (property pass rates, intervention triggering rates); Related work (ArgLLMs, MArgE, AgentSpec, Cemri-MAST); Limitations (MCMAS ≤ 6 agents, monitor scaling).
- **Target.** AAMAS 2027 main (Oct 2026 abstract). **Backup:** NeSy 2026 main (Jun 2026), KR 2026 (May/Jun 2026).
- **Gating milestone:** **M2 (end of Jul 2026).** L0+L1 done; 4-agent / 4-round MCMAS verification working.
- **PDF citations.** All papers in `papers/4 --- verification and model-checking/` (Pnueli, Clarke-Emerson, Alur-ATL, Bauer LTL3, De Giacomo LTL_f, MCMAS, MCMAS-SLK, MCMAS-BR, SPOT, Kambhampati LLM-Modulo, AgentSpec); Cemri MAST from `papers/1`; argumentation primer from `papers/3`.

### P2 — Strategic Gradual Argumentation for Multi-LLM Aggregation

- **Layers:** L0 + L2 (+ L3 for calibration).
- **Theorems:** **T4 (Borda recovery)**, **T5 (manipulability bound)**, **T6 (rationality postulates)**, **T7 (strategic gradual semantics)**.
- **Headline empirics.** HLE + LiveCodeBench. Head-to-head against ArgLLMs, MArgE. Headline metrics: ECE (calibration), flip-cost (T5), winner-strength margin.
- **Sections.** Argumentation aggregation as a vote replacement; BAF/QBAF construction from typed traces (no LLM extraction); Strategic gradual semantics (DF-QuAD ⊕ ATL); Theorems T4–T7; Empirics; Related work.
- **Target.** AAAI 2027 (Aug 2026). **Backup:** NeurIPS 2026 D&B (Jun 2026), IJCAI 2027 (Jan 2027).
- **Gating milestone:** **M2.** L0+L2(+L3 partial) done; one Tier-B benchmark with bootstrap CI.
- **PDF citations.** All papers in `papers/3 --- argumentation/` (Dung, Cayrol-Lagasquie-Schiex, Baroni-Rago-Toni, DF-QuAD, Potyka, Amgoud-Ben-Naim, ArgLLMs, MArgE, Sanayei "Can LLMs Judge Debates?", Gorur argument-mining); calibration primer from `papers/2`; debate primer from `papers/1`.

### P3 — Quality-Diversity over Deliberation Behaviour

- **Layers:** L5 over L0+L1+L2+L3.
- **Theorems:** **T8 (QD coverage)**, **T9 (Pareto domination)**, **T10 (robustness)**.
- **Headline empirics.** **ARC-AGI-2 verified submission** (target: match 54% at < $10/task **or** push 54% → 60% at < $40/task), FrontierMath Tier 4 (≥ 1 newly-solved problem), LiveCodeBench (head-to-head TRINITY 86.2%), SWE-bench Pro.
- **Sections.** QD over typed councils; verifier-derived behavioural descriptors (the novelty); CMA-MAE on pyribs + LLM-mutation emitters (GEPA + AlphaEvolve); Theorems T8–T10; Empirics (ARC Prize verified-leaderboard stamp); Pareto-Pareto comparisons; Related work.
- **Target.** **NeurIPS 2026 main** (May 2026 abstract / paper). **Backup:** ICLR 2027 (Sep/Oct 2026), GECCO 2027 (Jan/Feb 2027).
- **Gating milestone:** **M3 (end of Sep 2026).** L5 end-to-end on ARC-AGI-2 small-N; QD archive non-trivial.
- **PDF citations.** All papers in `papers/5 --- evolutionary and quality-diversity/` (MAP-Elites, CMA-ME, CMA-MAE, pyribs, FunSearch, AlphaEvolve, GEPA, QDAIF, Rainbow Teaming, MADRID, ADAS, AFlow, AgentSquare, MaAS, SwarmAgentic, QD-helpful-Qian); TRINITY/Conductor/MoA/Self-MoA from `papers/1`.

### P4 — Co-evolutionary Red/Blue Teaming of Deliberating Councils

- **Layers:** L5 with the red-team archive + L1 monitors.
- **Theorems:** **T11 (co-evolutionary convergence)**, refined T10.
- **Headline empirics.** Putnam-AXIOM Variation, GAIA, custom MAST-derived adversarial-injection benchmark.
- **Sections.** Co-evolution as red/blue teaming; Symmetric Pareto archives for hosts and parasites; Verification-aware host fitness; Empirics; Related work (Rainbow Teaming, MADRID).
- **Target.** AAMAS 2027 companion. **Backup:** ICLR 2027, NeurIPS 2026 main as a robustness paper.
- **Gating milestone:** **M4 (end of Dec 2026).** Co-evolutionary loop working at scale.
- **PDF citations.** Rainbow Teaming, MADRID, MAST taxonomy (Cemri).

### P5 — Inductive Discovery of Multi-Agent Dialogue Protocols

- **Layers:** L6 (with L0 + L1).
- **Theorems:** **T12 (soundness of ILP-induced protocols)**, **T13 (generalisation characterisation)**.
- **Headline empirics.** Show that protocol rules learned on one benchmark transfer (within domain) to another, with verified guarantees. Compare against PSALM (Zhu 2024) and LASP (Chen 2024) — single-agent ILP-from-traces precedents.
- **Sections.** ILP from labelled traces; ASP integrity constraints (CLMASP-replication); Re-verification by MCMAS; Theorems; Empirics.
- **Target.** **KR 2026** (May/Jun 2026). **Backup:** NeSy 2026 main (Jun 2026), ILP 2026/2027.
- **Gating milestone:** **M5 (end of Feb 2027).** L6 working end-to-end with at least one transferable learned protocol.
- **PDF citations.** All papers in `papers/6 --- nesy and ilp/` (Manhaeve DeepProbLog, Cropper Popper, Law ILASP, Lin CLMASP, Olausson LINC, Pan Logic-LM, Yang LLM-LP, Ye SatLM); plus Bauer 2011 (re-verification).

### F — CouncilAgent‑NS: A Neuro-Symbolic Multi-Agent LLM Council Framework

- **All layers integrated.**
- **Theorems.** T1–T13 in a unified framework.
- **Headline empirics.** Full Tier-A + Tier-B sweep with bootstrap CIs; ARC Prize verified-leaderboard stamp; Pareto-Pareto frontier vs TRINITY/Conductor/MoA.
- **Sections.** Long-form (~25 pages); software-artefact paper character.
- **Target.** **JAIR / AIJ** flagship (rolling submission, target Apr 2027). **Companion:** NeSy 2027 keynote/tutorial.
- **Gating milestone:** **M6 (end of Apr 2027).** Everything done; demo video; ARC Prize stamp; 1.0 release tagged.

---

## 10. Twelve-month sprint roadmap

Dates assume an **April 28, 2026 start**. Workstreams W0–W7 schedule onto weeks W1–W52.

### Month 1 (May 2026): W0 substrate

- **W1 (Apr 28 – May 4):** Bootstrap is **already done** (the migration commit on `council-ns` performed it). Verify: `legacy/v0.1.0` tag exists, `council-ns` branch is current, `legacy_council/` holds the v0.1.0 seed, `pyproject.toml` declares `name = "councilagent"` at version `0.2.0.dev0`, `.claude/CLAUDE.md` is the 12-principle Constitution, the seven NS agents and twelve NS skills are present. Reserve `councilagent` on PyPI (defensive).
- **W2:** L0 — `dialect/moves.py` + `dialect/trace.py` + `DeliberationAutomaton`; JSON-schema parser; surface-rendering. Acceptance: 3-agent peer-review trace round-trips through `Move` ADT and back to NL prompts losslessly. **First arXiv preprint:** "Typed Speech-Act Substrate for LLM Councils" (~5 pages, NeSy 2026 short-paper material).
- **W3:** Port `models.py` and `topology.py`; new `tools.py` skeleton (MCP + Z3 stubs).
- **W4:** Port `core.py` to `run_council(trace)` operating on Moves; port normalizer, ranker, termination. Acceptance: GSM8K end-to-end on Move-typed traces with parity to legacy ± 1pp.

**M1 (end May 2026):** typed substrate complete; GSM8K parity demonstrated; NeSy 2026 short-paper submitted.

### Months 2–3 (Jun–Jul 2026): W1 + W2

- **W5–6:** L1 LTL₍f₎ AST + parser; SPOT bindings; LTL3 monitor. Initial property library (8 named properties). Each property has positive + negative test traces. **NeSy 2026 main paper P1 submitted (Jun deadline).**
- **W7:** L1 ISPL encoder for MCMAS; offline check on 4-agent / 4-round example; T1, T2, T3 proofs drafted in `docs/theory.md`.
- **W8:** L2 `BAF/QBAF` data structures + DF-QuAD; `build_qbaf(trace)`. Acceptance: deterministic output for the canonical Walton-Krabbe example.
- **W9–10:** L2 `ArgumentationAggregator`; T4–T7 drafted. Mermaid + GraphViz visualisers. **KR 2026 P5 submission (May/Jun)** — risk: L6 not started yet; if not feasible, defer to NeSy 2026 second window or ILP 2026.
- **W11–12:** Empirical run #1: P1 demo on Putnam-AXIOM Variation + ZebraLogic-hard (matches gating for AAMAS 2027); P2 demo on HLE.

**M2 (end Jul 2026):** P1 + P2 ready to submit; NeurIPS 2026 D&B P2 deadline (Jun) — possibly delayed to AAAI 2027.

### Months 4–5 (Aug–Sep 2026): W3 + W4 + W5 (start)

- **W13:** L3 — JSD-based confidence; MUSE; per-domain calibration. Acceptance: ECE on GSM8K + MMLU drops below 0.05.
- **W14:** L4 — In-context distillation cascade; multi-tier router; budget tracker. **AAAI 2027 P2 submission (Aug)**.
- **W15–17:** L5 — Genome dataclass; pyribs CMA-MAE wrapper; LLM-mutation emitters (GEPA + AlphaEvolve). Initial QD run on GSM8K.
- **W18:** L5 — Behavioural descriptors derived from L1+L2 outputs. Empirical run #2: ARC-AGI-2 small-N.
- **W19–20:** L5 — full evaluate-loop wired; first verified ARC Prize 2026 submission. **ICLR 2027 P3 submission (Sep/Oct).** **AAMAS 2027 abstracts P1+P4 (Oct).**

**M3 (end Sep 2026):** L5 working end-to-end; first verified ARC-AGI-2 submission; P3 draft ready.

### Months 6–8 (Oct–Dec 2026): co-evolution + scaling

- **W21–22:** Red-team archive (Rainbow-Teaming-style); co-evolutionary loop.
- **W23–24:** Scale L5 to all Tier-A benchmarks. Cost-Pareto comparisons against TRINITY/MoA.
- **W25–26:** P4 draft on co-evolution.
- **W27–28:** P3 / P4 camera-ready; benchmark ledger frozen for the next round.

**M4 (end Dec 2026):** P3 + P4 in submission.

### Months 9–10 (Jan–Feb 2027): W6 + flagship integration

- **W29–30:** L6 — ASP integrity-constraint enforcement; clingo wrapper. CLMASP-replication demonstrated.
- **W31–32:** L6 — Popper integration; ILP from labelled traces; rule-to-automaton; MCMAS verification of induced rules.
- **W33–36:** P5 draft. Flagship F draft begins. **IJCAI 2027 P2 backup submission (Jan).**

**M5 (end Feb 2027):** P5 ready; F first draft.

### Months 11–12 (Mar–Apr 2027): flagship + viral demos

- **W37–40:** F flagship paper; complete benchmark ledger; all 13 theorems written up; reproductions in `experiments/reproduce/` for every paper.
- **W41–44:** Streamlit demo; live LTL₍f₎ monitor; Mermaid BAF visualiser; one-click ARC-AGI-2 runner; demo video. **GECCO 2027 P3 retry (Feb)** if needed.

**M6 (end Apr 2027):** F submitted to JAIR. Streamlit demo live. Repo at v1.0.0.

### Workshop checkpoints (insurance policy)

- **NeSy 2026 workshop (Jun 2026)** — substrate paper.
- **AAAI 2027 agent workshops (Aug 2026)**.
- **ICLR 2027 NeSy workshop (Sep 2026)**.
- **GECCO 2027 LLM track (Feb 2027)**.
- **ICML 2027 NeSy workshop (Apr 2027)**.

Every layer should appear in a workshop *before* its main-venue submission. Workshops give reviewer feedback and citable preprints without rejection sting.

---

## 11. Empirical plan

This section refines [`COUNCIL_NS_PLAN.md`](./COUNCIL_NS_PLAN.md) §9 with NS-specific operational detail.

### 11.1 Benchmarks

**Tier-A (must have):**

| Benchmark | Loader | SOTA (Apr 2026) | NS target | Eval signal |
|---|---|---|---|---|
| ARC-AGI-2 (semi-private) | `tasks/arc_agi_2.py` | 54% @ $30.57/task (Poetiq+Gemini 3 Pro) | match 54% @ < $10/task **or** 60% @ < $40/task | execution + ARC verified-leaderboard stamp |
| FrontierMath Tier 4 (private) | `tasks/frontiermath.py` | 38–42% (GPT-5.x Pro) | ≥ 1 newly-solved Tier-4 problem | LLM-as-judge + reference proof |
| LiveCodeBench | `tasks/livecodebench.py` | 86.2% pass@1 (Sakana TRINITY) | match 86.2% under matched compute, with cost-Pareto win | execution |

**Tier-B (sharpens specific layers):**

| Benchmark | Sharpens | SOTA |
|---|---|---|
| SWE-bench Pro | L4 cascade, L5 QD | ~64.3% (Claude Opus 4.7) |
| Humanity's Last Exam (HLE) | L3 calibration, L1 monitors | ~44–47% verified, 64% self-reported |
| ZebraLogic-hard | L1 verifier, L6 ASP | LLM+Z3 hybrid territory |
| Putnam-AXIOM Variation | L1 monitors, L2 argumentation | typical 15–25pp drop on Variation |
| GAIA | L4 cascade, tools | Magentic-One / OpenHands / Trase |
| WebArena | L4 router | OpAgent 71.6% (Jan 2026) |

**Tier-C (saturated, sanity rows only):** GSM8K, MATH, MMLU, ARC-AGI-1, AIME 2024/2025, GPQA Diamond, HumanEval. Use to demonstrate non-regression.

### 11.2 Baseline set (mandatory for every paper table)

Per Constitution §6, every NS configuration is compared against:

1. **Best single frontier model** — lower bound any multi-model system must beat.
2. **CoT + Self-Consistency** (Wang ICLR 2023, sample N, majority-vote) — single-agent matched-token-budget gold standard since Smit ICML 2024.
3. **Mixture-of-Agents** (Wang ICLR 2025 spotlight, `2406.04692`) — the 2026 multi-agent gold standard.
4. **Self-MoA** (`2502.00674`) — tests the "diversity helps" hypothesis.
5. **Karpathy llm-council** — the "vibe-coded baseline" reference.
6. **Sakana TRINITY** (LiveCodeBench Tier-A only) — head-to-head with the strongest evolved-coordinator competitor.
7. **Single-agent + Z3/clingo/Lean** (where applicable) — establishes that *deliberation* adds value beyond *symbolic post-hoc verification*.
8. **CouncilAgent v0.1** (legacy, on `develop`) — one ablation row showing the value-add of the symbolic stratum.
9. **Random-vote / oracle-best-of-N** — lower / upper bounds.

Matched-token-budget comparisons are **mandatory** in every table (Constitution §6.1).

### 11.3 Ablation matrix (P3's main result table)

Every cell × every Tier-A benchmark × ≥ 3 seeds × bootstrapped 95% CIs.

| Configuration | What it tests |
|---|---|
| MoA baseline | The 2026 reference |
| NS, L0 only | Does typing alone help? |
| NS + L1 | Verification-spine contribution |
| NS + L1 + L2 | Argumentation-aggregator contribution |
| NS + L1 + L2 + L3 | Calibration contribution |
| NS + L1 + L2 + L3 + L4 | Cost-Pareto contribution |
| NS + … + L6 (no L5) | Hard-constraint contribution |
| NS + L5 (single best from QD archive) | QD vs best-single-genome |
| **NS, full stack** | Every layer working together |
| Full minus L1 | Verification ablation |
| Full minus L2 | Argumentation ablation |
| Full minus L3 | Calibration ablation |
| Full minus L5 | QD-vs-hand-tuning |
| Full minus L6 | ILP-rule-mining ablation |
| Full + adversarial archive samples | Robustness attribution |
| Cost-matched: each layer at fixed $/task | Pareto attribution |
| Per-MAST-mode: 14 cells × NS-full | Failure-mode coverage (Cemri MAST) |

### 11.4 Novel evaluation metrics

Beyond `task_accuracy`, NS reports:

- `verification_pass_rate` — fraction of selected LTL₍f₎ properties that returned ⊤ over the test set.
- `confidence_calibration_ece` — ECE of the JSD/BAF-margin confidence vs true correctness.
- `qbaf_coherence` — fraction of council answers whose winning argument has flip-cost ≥ θ.
- `provenance_completeness` — fraction of votes anchored on ≥ 1 evidence atom.
- `pareto_hypervolume` — L5 archive's hypervolume on (accuracy, cost, robustness).
- `intervention_rate_per_type` — how often each L1 intervention fired.
- `mast_coverage` — Cemri MAST 14-mode failure regimes covered by the archive.

These are **new metrics** that no competitor reports — the existence is itself a contribution.

### 11.5 Statistical discipline

- **Bootstrap CIs** at α=0.05 on every reported number.
- **Wilcoxon signed-rank** for paired NS-vs-baseline comparisons.
- **AIPW** (`evaluation/statistical.py`) for unbiased aggregate estimates across heterogeneous configs.
- **Bradley-Terry** (Chatbot Arena methodology) for inter-model rankings.
- **Mixed-effects model** (`evaluation/statistical.py:MixedEffectsModel` ported) for domain-level random intercepts.

### 11.6 Reproducibility

Every paper number must be reproducible by:

```bash
$ bash experiments/reproduce/p<n>_<slug>.sh
```

The script:
1. Locks the Hydra config to a frozen YAML.
2. Pulls the exact PyPI package version.
3. Runs the genome on the frozen task set.
4. Logs to MLflow.
5. Emits the table cell + bootstrap CI.

Every config is checked in. Every random seed is logged. Every cost is tallied.

---

## 12. Engineering operations

### 12.1 Branching and CI

- **Branch protection.** `main`: 2-reviewer approval, all checks green. `develop`: 1-reviewer, all checks green. `council-ns`: 1-reviewer, all checks green. `feature/*`: no protection.
- **CI matrix.** `ruff check`, `mypy --strict` on the typed footprint, `pytest` (excluding `RUN_INTEGRATION`), `coverage` ≥ 85% on `council/`, ≥ 70% on `evaluation/`.
- **Smoke debate.** Every PR runs a 3-agent / 1-round debate on a 5-task synthetic set (≤ 30s wall-clock) to catch regressions in the pipeline.
- **Constitution check.** `.claude/skills/check-constitution` runs on every PR via a pre-commit hook (when settings.json is configured to enable hooks; see §13.5).

### 12.2 Releases

- **Semantic versioning** for both `council-agent` and `councilagent`.
- **NS release cadence.** v0.1.0 at M1 (substrate); v0.2.0 at M2 (verification + argumentation); v0.3.0 at M3 (QD); v0.4.0 at M4 (co-evolution); v0.5.0 at M5 (ILP); **v1.0.0 at M6 (flagship)**.
- **Each release.** GitHub release notes; PyPI publish; Zenodo DOI auto-mint via CITATION.cff.

### 12.3 Telemetry

- **OpenTelemetry** for distributed tracing of multi-agent pipelines (W7 milestone). Spans: `generate`, `deliberate.{round}`, `monitor.{property}`, `aggregate`, `terminate`.
- **MLflow** for experiment tracking. Per-run: full genome, all config, per-round outputs, aggregation results, token counts, latencies, costs, monitor verdicts, BAF Mermaid string, ProvenanceReceipt JSON.
- **Bradley-Terry leaderboard** generator runs nightly during ablation sweeps; results pushed to GitHub Pages.

### 12.4 Dev environment

- **Python 3.11+ required** (3.12 recommended).
- **`uv sync`** is the only setup command. `uv sync --extra ns` for full NS dev.
- **Optional extras:** `[verify]` (spot, mcmas-py), `[argue]` (no extra deps), `[evolve]` (pyribs, cma), `[ilp]` (clingo, popper-bin), `[full]`. The no-extras path always works (pure-Python fallbacks for SPOT/clingo/pyribs).
- **API keys.** `.env.example` lists every key NS uses; `.env` is git-ignored. ARC Prize 2026 access requested in W2 of the kickoff.

### 12.5 Test discipline (target)

- **`tests/` ≥ 1500 functions by M6** (current legacy baseline: 422).
- **Layer coverage.** Every layer ABC has its own contract test class. Every concrete subclass has a property-based test, a deterministic-output test, and an integration test.
- **`FakeModelClient`** ported — never call real models in unit tests. Real model calls are gated by `RUN_INTEGRATION=1` and live in `tests/integration/`.
- **Determinism.** Every test that uses randomness fixes `random.seed(0)` / `np.random.seed(0)`. Every `Trace` test uses a hand-crafted, deterministic move sequence.
- **Regression pins.** Every defect D1–D17 has a regression test in `tests/regressions/`.

---

## 13. `.claude/` layout

### 13.1 Files in this branch

| Path | Purpose |
|---|---|
| `.claude/CLAUDE.md` | The 12-principle Constitution. Auto-loaded by Claude Code each session. |
| `.claude/rules/architecture.md` | Binding architecture rules: layer responsibilities, forbidden imports, required ABC contracts, mypy-strict invariants. |
| `.claude/rules/code-style.md` | Python style baseline (async-first, dataclasses over dicts, no `print`, no silent except, …). |
| `.claude/rules/testing.md` | pytest discipline, `FakeModelClient`, `RUN_INTEGRATION` gating, coverage targets, regression pins. |
| `.claude/rules/verification.md` | LTL₍f₎ authoring rules: every property has `name`, `formula`, positive + negative test traces; every monitor's `step` is total; interventions never raise. |
| `.claude/rules/argumentation.md` | BAF/QBAF rules: `build_qbaf` is deterministic; gradual semantics is monotone in base scores; visualisers never call models. |
| `.claude/rules/evolution.md` | Genome rules: serialisable to YAML; descriptors derived only from L1+L2+L3 outputs; emitters never call generation models in the no-extras path. |
| `.claude/rules/papers.md` | Theorem-claim discipline: every claimed theorem has either a proof in `docs/theory.md` or a mechanised pytest test (or both); no hand-waving in submission drafts. |
| `.claude/agents/*.md` | Seven agents, listed in §13.2. |
| `.claude/skills/*/SKILL.md` | Twelve skills, listed in §13.3. |
| `.claude/settings.json` | Hooks, permissions, env vars (§13.4). |

The `.claude/` files have no `-ns` suffix. There is one Constitution, one architecture rules file, one set of agents, one set of skills. Different branches carry different content; never multiple staged versions in the same tree.

### 13.2 Agents (`.claude/agents/`)

| Agent | When to invoke | Tools |
|---|---|---|
| **`workstream-planner`** | Starting any new task. Triages a fuzzy request ("add an LTL property for sycophancy") into a workstream (W0–W7), layer (L0–L6), feature branch name, file list, theorem connection (T1–T13), paper (P1–P5/F), and effort estimate. | Read, Grep, Glob, Bash |
| **`constitution-reviewer`** | Before committing any change to `council/`. Audits the diff against the 12 Constitution principles + binding architecture rules. Emits BLOCKER / WARNING / NIT findings with `file:line` citations. | Read, Grep, Glob, Bash |
| **`theorem-checker`** | Before paper submission, or after touching `docs/theory.md`. Audits theorem statements against bible §10, published lemmas in `papers/`, and mechanisations in `tests/regressions/`. Verdict: GO / BLOCK / REVISE. | Read, Grep, Glob, Bash |
| **`ltl-property-author`** | When adding to the named-property library (W1). Drafts the LTL₍f₎ formula from a natural-language intent, writes the `Property` subclass, generates ⊤ and ⊥ test traces, runs the monitor. | Read, Edit, Write, Bash |
| **`qbaf-reviewer`** | After any change to `council/symbolic/argue/builders.py` or `aggregator.py`. Audits layer cleanliness, determinism, monotonicity, Walton-Krabbe canonical agreement, T4 Borda-recovery. | Read, Grep, Bash |
| **`qd-runner`** | When running W5 / P3 / P4 experiments. Launches `experiments/evolve.py` in background, monitors hypervolume sparsely, halts on plateau or budget exhaustion, extracts the Pareto front. | Bash, Read, Edit, Glob |
| **`paper-drafter`** | At paper kickoff. Scaffolds the LaTeX skeleton from §9 of this plan + §10 of the bible + MLflow run JSONs. Never invents results. | Read, Write, Edit, Bash |

### 13.3 Skills (`.claude/skills/`)

Each skill scaffolds a layer artefact and its tests, on a `feature/ns-w<n>-<slug>` branch.

| Skill | Scaffolds | Workstream |
|---|---|---|
| **`new-protocol-automaton`** | `ProtocolAutomaton` subclass under `council/dialect/protocols/`. Refuses round-parity heuristics. | W0 |
| **`new-property`** | `Property` subclass in `council/symbolic/verify/properties.py` with ⊤ and ⊥ tests. | W1 |
| **`new-semantics`** | `GradualSemantics` subclass under `council/symbolic/argue/semantics/`. Tests determinism + monotonicity + Walton-Krabbe agreement. | W2 |
| **`new-calibrator`** | `Calibrator` subclass in `council/calibrate/`. Tests against synthetic distributions with known calibration. | W3 |
| **`new-cascade-strategy`** | `RoutingStrategy` subclass in `council/cascade/strategies.py`. Tests budget enforcement and cost-Pareto wins over `NullStrategy`. | W4 |
| **`new-descriptor`** | `Descriptor` subclass in `council/evolve/descriptors.py`. Refuses descriptors that read raw text or call generation models. | W5 |
| **`new-emitter`** | `Emitter` subclass under `council/evolve/emitters/`. Tests genome well-formedness + diversity. | W5 |
| **`mine-rules`** | Runs Popper / ILASP4 over a labelled-trace bundle, then `verify_learned.py` (MCMAS) on the induced rules. | W6 |
| **`run-pareto`** | Extracts the Pareto front and computes hypervolume from MLflow runs. Renders a 3D scatter to `papers_drafts/figures/`. | W5, W7 |
| **`paper-skeleton`** | LaTeX skeleton under `papers_drafts/p<n>_<slug>/`: `main.tex`, `supplementary.tex`, `Makefile`, theorem placeholders verbatim from bible §10. | W7 |
| **`ablation-row`** | Hashes a frozen Hydra config, runs it, computes bootstrap CI, emits a LaTeX table row, appends to `papers_drafts/_ablation_log.tsv`. | W7 |
| **`check-constitution`** | Fast `rg`-driven audit of the 12 Constitution principles. Pre-commit gate; complements the `constitution-reviewer` agent. | continuous |

### 13.4 `settings.json`

- **Hooks.**
  - `pre-commit` runs `.claude/skills/check-constitution/run.sh` on the staged set.
  - `post-test` runs `mypy --strict council/` and `ruff check council/`.
- **Permissions.** Allow-list `uv run pytest`, `uv run mypy`, `uv run ruff`, `uv run python -m mlflow`, `uv run python -m experiments.run|sweep|evolve|coevolve`, `uv run streamlit run`, `gh pr create|view`, and the `[ilp]`-extra binaries (`clingo`, `popper`, `ilasp`).
- **Env vars.** `MLFLOW_TRACKING_URI=./mlruns` (default).

### 13.5 Personal skills the workflow leans on

These ship with the user's `~/src/` library; this plan invokes them as named operations. They are *not* duplicated into `.claude/skills/`.

- **`spec-driven-development`** — at the start of every workstream W0–W7, write a layer spec before any code.
- **`incremental-implementation`** — every PR ≤ 600 LOC, lands one piece, leaves the tree green.
- **`test-driven-development`** — drives W1 property tests, W2 builder tests, W3 calibrator tests.
- **`debugging-and-error-recovery`** — default when a monitor / QD run / theorem-mechanisation misbehaves.
- **`documentation-and-adrs`** — after every architectural decision; ADRs land in `docs/adr/` (e.g. `0001-typed-move-substrate.md`, `0002-ltlf-via-spot.md`, `0003-df-quad-as-default-semantics.md`).
- **`git-workflow-and-versioning`** — governs the `feature/ns-*` branch flow and the `0.2.0 → 1.0.0` release ladder.
- **`code-review-and-quality`** — runs before every PR merge.
- **`code-simplification`** — periodic; before paper submissions, simplify L0–L6 code paths touched by that paper.
- **`security-and-hardening`** — for `apps/streamlit_demo.py` (handles untrusted user input) and the MCP `ToolClient`.

---

## 14. Risk register and counterfactual paper plans

For every risk: trigger, mitigation, fallback paper plan if the risk materialises.

### 14.1 Scientific risks

| Risk | Trigger | Mitigation | Fallback paper plan |
|---|---|---|---|
| **MAD-doesn't-beat-CoT-SC reviewer pushback** (Smit 2024, "Stop overvaluing MAD" 2025, "Single-Agent vs MAS" 2025) | Reviewer reads our table, finds matched-token CoT-SC matches NS | Constitution §6.1 makes matched-token-budget tables mandatory in every paper. Headline claim is *not* "more agents"; it is "verified + argumentative + evolved councils with calibrated confidence". | Pivot P3 to *cost-Pareto* framing only; P1 (verification) and P2 (argumentation) carry the headline. |
| **MCMAS scales to ~6 agents only** | We try 10-agent verification, fail | Bounded-recall MCMAS-BR (`papers/4 .../Balardinelli et al. 2020`); rely on LTL₍f₎ runtime monitors (LTL3, SPOT) for online enforcement at arbitrary scale; frame model-checking as *offline protocol validation*. | P1 frames the contribution explicitly as "online runtime monitoring + offline small-instance verification". |
| **ArgLLMs / MArgE / DCI scoop the argumentation aggregator** | New paper appears with QBAF over multiple LLMs | Differentiator stays: ours operates over a *typed-protocol-enforced* graph (no LLM extraction step); fuses with the verification layer (T7 strategic gradual semantics). Move fast on P2 — submit AAAI 2027 even if NeurIPS 2026 D&B slips. | P2 pivots to "strategic gradual semantics" as the headline (T7 alone), with the full BAF-over-traces framing as a system contribution. |
| **TRINITY / Conductor / MaAS / AFlow / AgentSquare / SwarmAgentic / EvoFlow scoop QD** | New paper appears with verifier-derived descriptors | Our descriptors come from L1+L2 — *verifier-derived*, not LLM-tagged. EvoFlow is single-objective workflow-search; SwarmAgentic is PSO; MaAS is continuous-distribution without an archive; AgentSquare is greedy modular search. None evolves *typed protocols* with verification descriptors. | P3 pivots to "co-evolutionary red/blue with verifier descriptors" (P3+P4 merge); flagship F absorbs the QD framing. |
| **Benchmark contamination crisis** (Berkeley RDI 2026; OpenAI Dec 2025) | New audit shows our Tier-A includes contamination | Prioritise SWE-bench Pro, FrontierMath Tier 4, ARC-AGI-2 semi-private, MathArena live competitions, Putnam-AXIOM Variation. Publish our eval harness; pre-empt the dominant 2026 critique. | F flagship sells the eval harness as a contribution (a "trust-by-design" benchmark suite). |
| **Typed-protocol refactor takes longer than expected** | M1 slips; W0 substrate not done by end-May | Publish L0 (typed-protocol substrate) as a NeSy 2026 short paper or a SoftwareX tooling paper, decoupling engineering risk from publication path. The DOCX's H1–H10 hypothesis tests still run on the legacy substrate (student track). | M1+1 month: ship NeSy 2026 short paper; defer P1 to KR 2026 second window. |
| **QD genome space too large; CMA-MAE doesn't converge** | M3 hypervolume stalls before generation 100 | Stage the search: (i) first illuminate over `(monitors × aggregator)` only with a fixed pool of 3 agents; (ii) expand to topology and protocol; (iii) expand to members. Each stage delivers a citable result. | P3 pivots to "staged QD" — each stage is a contribution. |
| **An LTL₍f₎ property turns out non-monotonic / unsatisfiable for all practical councils** | M2 testing finds property X never ⊤'s | Bauer 2011 shows 44% of LTL formulae are non-monotonic; not every property is monitorable. Document negative results; they are themselves publishable (modality-sabotage framing). | P1 includes a "limits of LTL₍f₎ monitoring for council deliberation" section; the negative-result table is itself a contribution. |
| **Paper-deadline overload** | Multiple deadlines in the same month and W4–W5 not done | Workshop checkpoints (§10) ensure every layer has a citable preprint before the main-venue submission. | Demote affected papers to workshops; preserve the main-venue submission for the next cycle. |

### 14.2 Engineering risks

| Risk | Trigger | Mitigation |
|---|---|---|
| **Branch-and-rebuild costs ~3 months before any new empirics** | Stakeholders impatient | The ablation matrix shows that even L0 alone (typed Trace, no symbolic) is publishable as a substrate paper. Plan for incremental wins — NeSy 2026 short paper at end of M1 is the first deliverable. |
| **SPOT / MCMAS / clingo / Popper are C/C++ binaries** | Install friction stops adoption | Ship them as optional extras (`[verify]`, `[ilp]`); test the no-extras path always works. Fall back to pure-Python `ltl2mon` for LTL3 monitors when SPOT unavailable. |
| **LiteLLM provider quirks** (some models don't honour `response_format`) | Run on a new provider, JSON breaks | Layered structured-output enforcer: JSON-schema-in-prompt → `response_format` → grammar-constrained-decoding (Outlines) → argument-mining fallback. Tier marked in ProvenanceReceipt. |
| **Cost: full QD on ARC-AGI-2 + FrontierMath + LiveCodeBench could exceed $20K** | Budget exhausted mid-M3 | Use cascade (L4) aggressively; open-source-tier proposers + frontier-tier verifier keeps ~80% on the cheap tier. Apply for ARC Prize compute credits / Anthropic / OpenAI research grants in W2. |
| **MCMAS Python bindings flaky** | M2 ISPL emitter can't be tested via CI | Subprocess-call MCMAS via its CLI; ship a Docker image with MCMAS pre-installed for CI. |

### 14.3 Adoption risks

| Risk | Trigger | Mitigation |
|---|---|---|
| **NeSy is a niche audience** | Stars don't materialise | "Model-check your LLM debate" is broadly intelligible. ARC Prize 2026 verified-leaderboard stamp is a credibility multiplier across communities. The Streamlit demo is the viral lever. Submit a Hacker News post on M6 day. |
| **Engineers don't want to write LTL₍f₎** | New users don't extend | Default property library (10 named properties) covers 95% of use-cases. Power-users have a clean DSL when they need it. |
| **QD layer is research-grade, users want production stability** | Users adopt for prod, hit instability | Two entry points: `CouncilAgent.from_yaml("configs/verified-fast.yaml")` is *production-ready* (single hand-tuned genome from the QD archive); QD evolution is opt-in via `experiments/evolve.py`. |

### 14.4 Coordination risks (dual-track)

| Risk | Trigger | Mitigation |
|---|---|---|
| **Student's `develop` work conflicts with NS** | Student lands a refactor on `develop` (off `main`) | No conflict possible: `council-ns` does not import `develop` and vice versa. The legacy ablation runs `pip install council-agent==0.1.0` in a sub-venv — it pulls the frozen v0.1.0 release, not whatever is on `develop`. |
| **Student needs a feature already done in NS** | Student wants typed Move algebra for their thesis chapter | Allow opt-in NS imports from `develop`-side experiments via a thin `legacy_compat` shim in `council/legacy/__init__.py`. NS does **not** import legacy. |
| **CLAUDE.md and architecture rules diverge unhelpfully** | Student's automation breaks because rules differ | The two branches carry different content for the same paths intentionally: `main` keeps the legacy 10-principle Constitution; `council-ns` carries the 12-principle one. The v1.0 merge to `main` is one-shot and adopts the NS files. Documented in `docs/adr/0000-branching-strategy.md`. |

---

## 15. Two-week kickoff (post-migration)

The migration commit on `council-ns` is already done: `legacy/v0.1.0` tag exists, `legacy_council/` holds the seed, `pyproject.toml` is `councilagent==0.2.0.dev0`, the 12-principle Constitution and architecture rules are in `.claude/`, the seven NS agents and twelve NS skills are in place. The two weeks below land the **W0 substrate** end-to-end.

### Week 1 — typed substrate (W0 / L0)

**Day 1.** Reserve `councilagent` on PyPI (defensive). Apply for ARC Prize 2026 access (https://arcprize.org). Apply for Anthropic / OpenAI research credits. Update `README.md` with the locked tagline, demo-GIF placeholder, three-line value prop, ten-line code example. Pin a `ROADMAP.md` linking to this plan.

**Day 2.** `Skill: spec-driven-development` — write `docs/specs/w0-substrate.md` (Move ADT + Trace + ProtocolAutomaton ABC, derived from bible §6.1). `Agent: workstream-planner` — confirm prerequisites, propose `feature/ns-w0-moves`.

**Day 3.** Open `feature/ns-w0-moves`. Sketch `council/dialect/moves.py` (Move ADT + Claim + Force + ClaimDomain), ≤ 200 LOC. `Skill: test-driven-development` for the Move ADT tests.

**Day 4.** `council/dialect/trace.py` and `council/dialect/protocols/base.py`, ≤ 150 LOC each. Add tests.

**Day 5.** Spike SPOT bindings (`pip install spot`); 100-LOC LTL3 monitor over a hand-crafted `Trace.to_events()` returning ⊤/⊥/?. Land in `experiments/spikes/spot_smoke.py` (not in `council/`; just to verify).

**Day 6.** Read Freedman-Toni AAAI 2025 (`papers/3/.../Freedman et al.`) + Baroni-Rago-Toni 2019. Sketch `council/symbolic/argue/baf.py` + stub `DFQuADSemantics`, ≤ 200 LOC.

**Day 7.** `Agent: code-reviewer` and `Agent: constitution-reviewer` on the W0 PR. Merge `feature/ns-w0-moves`. Write 30 tests against the Move ADT + Trace.

### Week 2 — pipeline + first monitor (W0 + W1 toehold)

**Day 8–9.** Build `run_council` on the new typed substrate. Port `_build_visibility_context` (single source of anonymisation, Constitution §10). Use a `DeliberationAutomaton` as the first concrete `ProtocolAutomaton`. Acceptance: GSM8K (re-loaded under `tasks/`) runs end-to-end on Move-typed traces with parity to legacy `council-agent==0.1.0` ± 1pp.

**Day 10.** `Skill: new-property` — author the four simplest LTL₍f₎ properties: `EventuallyDecide`, `BoundedRound`, `ProvenanceCompleteness`, `NoMonotoneAgreementCollapse`. Wire `LTLfMonitorTermination` into `CompositeTermination`.

**Day 11.** Acceptance: run a 3-agent deliberation on GSM8K with monitors active; emit a `ProvenanceReceipt` JSON containing the typed Trace + the four monitor verdicts.

**Day 12.** Sketch `apps/streamlit_demo.py` — even a static one with a hand-crafted trace and Mermaid BAF render. Start the viral artefact early.

**Day 13.** Email Lomuscio's group about MCMAS-BR Python bindings, or allocate a 1-day spike to subprocess-call MCMAS via its CLI in M2.

**Day 14.** `Skill: documentation-and-adrs` — land `docs/adr/0001-typed-move-substrate.md` and `docs/adr/0002-ltlf-via-spot.md`. `Skill: code-review-and-quality`. Cut `v0.2.0` (substrate release).

After these two weeks:
- Typed substrate ✓
- First runtime monitor producing verdicts on real GSM8K runs ✓
- First Provenance Receipt format ✓
- Streamlit demo skeleton ✓
- ARC Prize 2026 access requested ✓
- ADRs 0001, 0002 landed ✓
- `v0.2.0` tagged on `council-ns` ✓

---

## 16. Definitions of done

### 16.1 Layer-done

A layer is done when:
1. Every module path in §4 is created and tested.
2. Every base ABC has a contract test class.
3. Every concrete class has property + deterministic + integration tests.
4. mypy strict passes on every file in the layer.
5. ruff passes.
6. All theorems attributed to the layer (§9 of this plan; §6 of bible) are either proved in `docs/theory.md`, mechanised in pytest, or both.
7. The layer's acceptance criteria (§7 of this plan) are checked off.
8. ADR(s) for any architectural decision are landed in `docs/adr/`.

### 16.2 Paper-done

A paper is done when:
1. `experiments/reproduce/p<n>_<slug>.sh` reproduces every number in the paper.
2. Every claim has a citation in `papers/`.
3. Every theorem has either a proof or a mechanised test (`docs/theory.md` cross-references `tests/regressions/test_t<n>.py`).
4. Bootstrap CIs at α=0.05 on every reported number.
5. Matched-token-budget tables included (Constitution §6.1).
6. Camera-ready PDF generated; supplementary materials are a Zenodo-DOI'd snapshot of the repo at the submission tag (e.g. `paper/p3-neurips-submission-2026-05-15`).
7. Constitution violations checked: zero blockers (`.claude/skills/check-constitution`).
8. The user has manually swept the relevant arXiv categories the week before submission for any newly-posted scoop risks.

### 16.3 Repo-done (v1.0)

The repo is at v1.0 when:
1. All workstreams W0–W7 are layer-done.
2. All five papers + flagship are paper-done (or in submission with full reproducibility).
3. Streamlit demo live on Streamlit Cloud; one-click ARC-AGI-2 runner; demo video ≤ 30s.
4. ARC Prize 2026 verified-leaderboard stamp obtained.
5. `tests/` ≥ 1500 functions; coverage ≥ 85% on `council/`.
6. mypy strict passes on all of `council/`.
7. PyPI: `councilagent==1.0.0` published.
8. Zenodo DOI minted via CITATION.cff.
9. README pinned to the locked tagline and the paper list.
10. `docs/` has full API reference, theory chapter, every paper's reproduction recipe.
11. Tagged `v1.0.0` on `council-ns`; merged to `main` as a single squash-merge that adopts the NS `.claude/` files and `council/` package as the new canonical content.

---

## Appendix A — Paper-PDF ↔ workstream crosswalk

Every PDF in `papers/` is mapped to the workstream(s) it primarily supports. Multi-mapping is the norm; the workstream listed first is the *primary* user.

### `papers/1 --- multi-agent LLM debate and orchestration/`

| PDF | Workstream(s) | Used in |
|---|---|---|
| Cemri 2025 — MAST taxonomy (NeurIPS D&B 2025; `2503.13657`) | W5 (descriptor `mast_coverage`), W7 (per-MAST ablation) | P3, P4, F |
| Choi 2025 — Debate or Vote (NeurIPS 2025; `2508.17536`) | W7 (motivation: voting captures most gain) | every paper's intro |
| Du 2024 — Multi-Agent Debate (ICML 2024; `2305.14325`) | W7 (related work) | every paper |
| Estornell-Liu 2024 — Multi-LLM Debate Framework (NeurIPS 2024) | W2, W7 | P2, F |
| Khan 2024 — Debating with More Persuasive LLMs (ICML 2024 Best Paper; `2402.06782`) | W7 (motivation) | P1, F |
| Liang 2024 — Encouraging Divergent Thinking (EMNLP 2024; `2305.19118`) | W7 | P3, F |
| Li 2026 — Self-MoA (TMLR; `2502.00674`) | W7 (baseline) | every paper |
| Nielsen 2026 — **Conductor** (ICLR 2026; `2512.04388`) | competitive analysis | every paper |
| Smit 2024 — Should we be going MAD? (ICML 2024; `2311.17371v3`) | W7 (matched-token defence) | every paper |
| Wang 2024 — Bounds of LLM Reasoning (ACL 2024; `2402.18272`) | W7 (motivation) | P3, F |
| Wang 2025 — **Mixture-of-Agents** (ICLR 2025 spotlight; `2406.04692`) | W7 (THE matched-compute baseline) | every paper |
| Wynn 2025 — Talk Isn't Always Cheap (`2509.05396v2`) | W7 (failure-mode catalogue) | P1, P4 |
| Xu 2026 — **TRINITY** (ICLR 2026; `2512.04695`) | competitive analysis (head-on for P3) | every paper |
| Zhang 2025 — Stop Overvaluing MAD (`2502.08788v3`) | W7 (matched-compute defence) | every paper |

### `papers/2 --- calibration and disagreement/`

| PDF | Workstream(s) | Used in |
|---|---|---|
| Ai 2025 — Beyond Majority Voting (`2510.01499`) | W2 (higher-order info → BAF base scores) | P2 |
| Anonymous 2026 — **ConFreeze** (OpenReview `PrqXuAS4BZ`) | W3 (`ConFreezeTermination`), W7 (baseline) | P1, P3 |
| Anonymous 2026 — **Privileged Knowledge** (OpenReview `du3ZBA8Z3Z`) | W3 (`PrivilegedKnowledgeCalibrator`) | P2, P3 |
| Cheng 2026 — ELEPHANT sycophancy (ICLR 2026; `2505.13995`) | W1 (`NoSycophancyCascade` property) | P1 |
| Fanous 2025 — SycEval (AIES; `2502.08177`) | W1 (sycophancy properties), W7 | P1 |
| Kruse 2025 — **MUSE** (EMNLP; `2507.07236`) | W3 (`MUSECalibrator`) | P2, P3 |
| Wataoka 2024 — Self-Preference Bias (`2410.21819`) | W7 (related work) | P2 |
| Zheng 2023 — MT-Bench / Chatbot Arena (NeurIPS 2023; `2306.05685`) | W7 (Bradley-Terry inspiration) | every paper |

### `papers/3 --- argumentation/`

| PDF | Workstream(s) | Used in |
|---|---|---|
| Amgoud-Ben-Naim 2018 — Weighted bipolar evaluation | W2 (Euler semantics) | P2 |
| Baroni 2018 — How Many Properties for Gradual? (AAAI) | W2 (rationality postulates → T6) | P2 |
| Baroni 2019 — Fine-grained properties (IJAR) | W2 (T5 manipulability bound) | P2 |
| Cayrol-Lagasquie-Schiex 2009 — Bipolar argumentation | W2 (BAF foundation) | P2 |
| Dung 1995 — On the acceptability (AIJ) | W2 (the foundation) | P2, F |
| Freedman 2025 — **ArgLLMs** (AAAI; `2405.02079`) | W2 (closest precedent — differentiator) | P2 |
| Gorur 2025 — Relation-based Argument Mining (COLING; `2402.11243`) | W0 (parser fallback), W2 | P2 |
| Ng 2025 — **MArgE** (`2508.02584`) | W2 (closest competitor) | P2 |
| Potyka 2018 — Continuous dynamical systems (KR) | W2 (Quadratic Energy semantics) | P2 |
| Rago 2016 — **DF-QuAD** (KR) | W2 (default semantics) | P2, F |
| Sanayei 2025 — Can LLMs Judge Debates? (EMNLP Findings; `2509.15739`) | W2 (motivates type-enforced graph; differentiator) | P2 |

### `papers/4 --- verification and model-checking/`

| PDF | Workstream(s) | Used in |
|---|---|---|
| Alur 2002 — ATL (JACM) | W1 (FairnessOfRoles property) | P1 |
| Balardinelli 2020 — MCMAS-BR (AAAI 2020) | W1 (bounded-recall semantics) | P1 |
| Bauer 2011 — Runtime verification LTL/TLTL (TOSEM) | W1 (T1 cited; LTL3 monitor) | P1 |
| Cermák 2014 — MCMAS-SLK (CAV) | W1 (strategy-logic verification) | P1 |
| Clarke-Emerson 1981 — Synthesis via branching-time (Logic of Programs) | W1 (CTL foundation) | P1 |
| De Giacomo-Vardi 2013 — LTL_f / LDL_f (IJCAI) | W1 (LTL_f foundation) | P1 |
| De Giacomo 2014 — LTL_f / LDL_f Monitoring (`1405.0054`) | W1 (monitor algorithms) | P1 |
| Duret-Lutz 2016 — Spot 2.0 | W1 (`spot_backend.py`) | P1 |
| Fagin 1995 — Reasoning About Knowledge (book) | W1 (CTLK foundation) | P1 |
| Kambhampati 2024 — LLM-Modulo (ICML 2024 position; `2402.01817`) | W1 (intervention layer) | P1, F |
| Lomuscio 2017 — MCMAS (STTT) | W1 (`ispl.py`) | P1 |
| Pnueli 1977 — Temporal Logic of Programs (FOCS) | W1 (T2 cited) | P1 |
| Wang 2026 — **AgentSpec** (ICSE 2026; `2503.18666`) | W1 (related work — runtime enforcement) | P1 |

### `papers/5 --- evolutionary and quality-diversity/`

| PDF | Workstream(s) | Used in |
|---|---|---|
| Agrawal 2026 — **GEPA** (ICLR oral; `2507.19457`) | W5 (`LLMReflectiveEmitter`) | P3 |
| Bradley 2024 — QDAIF (ICLR; `2310.13032`) | W5 | P3 |
| Fontaine-Nikolaidis 2023 — **CMA-MAE** (GECCO; `2205.10752`) | W5 (default optimiser) | P3 |
| Fontaine 2020 — CMA-ME (GECCO; `1912.02400`) | W5 | P3 |
| Hu 2025 — ADAS (ICLR; `2408.08435`) | W7 (related work) | P3 |
| Lehman 2022 — Evolution Through Large Models (`2206.08896`) | W5 | P3 |
| Mouret-Clune 2015 — MAP-Elites (`1504.04909`) | W5 | P3 |
| Novikov 2025 — **AlphaEvolve** (`2506.13131`) | W5 (`LLMDiffEmitter`) | P3 |
| Qian 2025 — QD provably helpful (IJCAI; `2401.10539`) | W5 (T8 builds on it) | P3 |
| Romera-Paredes 2023 — FunSearch (Nature) | W5 (motivation) | P3, F |
| Samvelyan 2024 — **Rainbow Teaming** (NeurIPS; `2402.16822`) | W5 (`redteam/rainbow.py`) | P4 |
| Samvelyan 2024 — MADRID (AAMAS; `2401.13460`) | W5 (related work) | P4 |
| Shang 2025 — AgentSquare (ICLR; `2410.06153`) | W7 (related work) | P3 |
| Tjanaka 2023 — pyribs (GECCO; `2303.00191`) | W5 (the library) | P3 |
| Zhang 2025 — AFlow (ICLR; `2410.10762`) | W7 (related work) | P3 |
| Zhang 2025 — MaAS (ICML; `2502.04180`) | W7 (related work) | P3 |
| Zhang 2025 — SwarmAgentic (EMNLP; `2506.15672`) | W7 (related work) | P3 |

### `papers/6 --- nesy and ilp/`

| PDF | Workstream(s) | Used in |
|---|---|---|
| Cropper-Morel 2021 — **Popper** (Mach. Learning) | W6 (rule mining) | P5 |
| Law 2020 — **ILASP** (`2005.00904`) | W6 (rule mining) | P5 |
| Lin 2024 — **CLMASP** (`2406.03367`) | W6 (replication target) | P5 |
| Manhaeve 2021 — DeepProbLog (AIJ) | W6 (NeSy precedent) | P5, F |
| Olausson 2023 — LINC (EMNLP; `2310.15164`) | W6 (LLM+FOL) | P5, F |
| Pan 2023 — Logic-LM (EMNLP Findings; `2305.12295`) | W6 (LLM+symbolic) | P5, F |
| Yang 2023 — Coupling LLMs with LP (ACL Findings; `2307.07696`) | W6 | P5 |
| Ye 2023 — SatLM (NeurIPS; `2305.09656`) | W6 (LLM+SAT) | P5 |

---

## Appendix B — Legacy-file → NS migration table

This is the mechanical migration plan. For each legacy file: action (port-verbatim / port-with-changes / discard), NS path, and the workstream that does the migration.

| Legacy file | Action | NS destination | Workstream | Notes |
|---|---|---|---|---|
| `council/__init__.py` | discard (keep for legacy import) | — | — | Legacy import path stays. |
| `council/agent.py` (220 LOC) | port-with-changes | `council/agent.py` | W0 + W3 + W4 | Confidence path: replace plurality fraction with `BAFMarginConfidence`/`JSDConfidence`; replace raw-string dissent with canonical-form dissent. |
| `council/aggregation.py` (375 LOC) | port-with-changes | split into `council/aggregation/{majority,borda,condorcet,meta_judge}.py` (baselines) + `council/symbolic/argue/aggregator.py` (NS headline) | W0 (baselines) + W2 (argumentation) | Remove `_default_round_label` (D13). Remove plurality-fraction confidence path (D2). |
| `council/context.py` (138 LOC) | port-with-changes | `council/context.py` | W0 | Replace `AgentResponse.content: str` with `AgentResponse.move: Move` (D1). Add `CouncilResponse`, `ProvenanceReceipt`. |
| `council/core.py` (394 LOC) | port-verbatim (skeleton) + extend | `council/core.py` | W0 | Skeleton ports; type substitution to `Move`/`Trace`; add monitor-step + intervention hook. |
| `council/models.py` (336 LOC) | port-verbatim | `council/models.py` | W0 | LiteLLM wrapper unchanged. |
| `council/normalizer.py` (74 LOC) | port-verbatim | `council/normalizer.py` | W0 | Used by baselines and as fallback in the typed parser. |
| `council/policy.py` (160 LOC) | discard | `council/policy.py` (rewritten) | W0 + W5 | Two-tier if-statement (D4) replaced by genome lookup against the QD archive. |
| `council/protocol.py` (250 LOC) | port-with-changes | `council/dialect/protocols/*.py` | W0 | `PeerReviewProtocol` becomes one preset of `DeliberationAutomaton`. `is_answer_round` becomes derived from the automaton's answer-phase predicate. |
| `council/ranking.py` (132 LOC) | port-verbatim | `council/ranker.py` | W0 | Used for ordinal aggregators (BordaCount, Condorcet) as baselines. |
| `council/task_profile.py` (40 LOC) | port-with-changes | `tasks/profiles.py` | W0 | `prompt_hint` deprecated; subsumed by `Claim.domain` + `dialect/surface.py`. |
| `council/termination.py` (103 LOC) | port-verbatim + extend | `council/termination.py` | W0 + W1 + W3 | `CompositeTermination` is the right base; add `LTLfMonitorTermination`, `JSDDivergenceTermination`, `ConFreezeTermination`, `ArgumentationStableTermination`. |
| `council/topology.py` (120 LOC) | port-verbatim + extend | `council/topology.py` | W0 + W5 | Existing topologies unchanged; W5 adds `GNNRoutedTopology`, `LearnedTopologyAdapter`. |
| `evaluation/baselines.py` (164 LOC) | port-with-changes | `evaluation/baselines.py` | W7 | Add MoA, Self-MoA, ConFreeze, KarpathyLLMCouncil, matched-token wrappers (D12). |
| `evaluation/__init__.py` | port-verbatim | `evaluation/__init__.py` | W7 | — |
| `evaluation/metrics.py` (301 LOC) | port-with-changes | `evaluation/metrics.py` | W7 | Extend with `verification_pass_rate`, ECE, hypervolume, semantic_equivalence (LLM-as-judge), execution_match, step_grading (D16). |
| `evaluation/shapley.py` (101 LOC) | port-verbatim | `evaluation/shapley.py` | W5 + W7 | Reused for per-genome attribution. |
| `evaluation/statistical.py` (307 LOC) | port-verbatim + extend | `evaluation/statistical.py` | W7 | Add Bradley-Terry; AIPW already there. |
| `experiments/run.py` (621 LOC) | port-with-changes | `experiments/{run,service,logging_adapter,transcript}.py` | W7 | Split into 4 modules (D17). |
| `experiments/sweep.py` (84 LOC) | port-verbatim | `experiments/sweep.py` | W7 | Hydra multirun. |
| `tasks/gsm8k.py` (60 LOC) | port-verbatim | `tasks/gsm8k.py` | W7 | Sanity-tier benchmark. |
| `tasks/loader.py` (43 LOC) | port-verbatim | `tasks/loader.py` | W7 | — |
| `tasks/profiles.py` (55 LOC) | port-with-changes | `tasks/profiles.py` | W0 | Add ARC-AGI-2, FrontierMath, LiveCodeBench, SWE-bench Pro, HLE, Putnam-AXIOM Variation, ZebraLogic-hard, GAIA, WebArena, τ²-bench profiles. |
| `tasks/registry.py` (18 LOC) | port-verbatim | `tasks/registry.py` | W7 | — |
| `tests/` (28 files, 422 functions) | port-with-changes | `tests/` | every workstream | ≈ 60% port mechanically; 40% rewritten for typed Move. |
| `configs/experiment/*.yaml` | port-with-changes | `experiments/configs/*.yaml` | W7 | New schema (§6.6). |
| `configs/hydra/*.yaml` | port-with-changes | `experiments/configs/hydra/*.yaml` | W7 | — |
| `pyproject.toml` | rewritten in place | `pyproject.toml` | W0 | `name = "councilagent"`, version `0.2.0.dev0`, mypy strict on all of `council/`, optional extras. |
| `conftest.py` | port-verbatim | `conftest.py` (shared) | W0 | — |
| `README.md` | port-with-changes | `README.md` (NS edition) | W0 | New tagline; new value prop; new code example. |
| `LLMCouncil_Deep_Review.md` | preserve | (no destination) | — | Reference for student track. |
| `plan.md` | preserve | (no destination) | — | Historical. |
| `COUNCIL_NS_PLAN.md` | preserve | (no destination) | — | The bible. |
| `Enhancing LLM Council Orchestration.docx` | preserve | (no destination) | — | DOCX seed. |
| `papers/` | preserve | (no destination) | every workstream | Citation source. |

---

## Appendix C — README contract for the flagship

The README (on `council-ns` from Day 2) follows this structure exactly:

```
# CouncilAgent‑NS

> The first multi-LLM council you can model-check.

[ short demo GIF — 30s, sycophancy-cascade scenario ]

**Drop-in `complete(prompt) → response` replacement for any LLM call.**
**Confidence is a measured Jensen-Shannon margin, not a self-report.**
**Every answer ships with a Provenance Receipt: typed Trace, argumentation graph, monitor verdicts, cost ledger.**

```python
from council import CouncilAgent

agent = CouncilAgent.from_yaml("configs/verified-fast.yaml")
resp = await agent.complete("What's the smallest prime > 100?")

print(resp.answer)               # "101"
print(resp.confidence)           # 0.93 — JSD margin
print(resp.receipt.monitors)     # {"NoPrematureConsensus": ⊤, ...}
print(resp.receipt.baf_mermaid)  # → live rendered argument graph
```

## Headline benchmarks

| Benchmark | NS | Best baseline | Δ |
|---|---|---|---|
| ARC-AGI-2 (verified) | … | 54% (Poetiq) | … |
| FrontierMath Tier 4 | … | 38–42% | … |
| LiveCodeBench | … | 86.2% (TRINITY) | … |
| SWE-bench Pro | … | 64.3% | … |

## Architecture (L0–L6)

[ five-architectures diagram ]

## Quickstart

…

## Papers

- P1 — Verified Deliberation (AAMAS 2027) — [PDF, BibTeX]
- P2 — Strategic Gradual Argumentation (AAAI 2027) — …
- P3 — Quality-Diversity over Deliberation Behaviour (NeurIPS 2026) — …
- P4 — Co-evolutionary Red/Blue Teaming (AAMAS 2027) — …
- P5 — Inductive Discovery of Multi-Agent Dialogue Protocols (KR 2026) — …
- F — A Neuro-Symbolic Multi-Agent LLM Council Framework (JAIR/AIJ) — …

## Citation

CITATION.cff (auto-generated; Zenodo-hooked).

## License

Apache-2.0.
```

---

## Appendix D — Glossary

| Term | Definition |
|---|---|
| **Move** | A typed speech-act in the council's deliberation. ADT: `Propose | Challenge | Concede | Retract | Question | Clarify | Vote | Abstain`. Lives at L0. |
| **Claim** | The content of a `Propose`/`Challenge`/`Concede`/`Vote`. Has a `surface` (NL), an optional `formula` (canonical form), a `domain` (`fol|ltlf|arith|code|free`), and `evidence` (move-IDs / URLs / tool-call IDs). |
| **Trace** | Immutable sequence of `Move`s with O(1) lookup. `to_events()` produces the atomic propositions for the LTL₍f₎ monitor. |
| **ProtocolAutomaton** | Finite-state machine over admissible `Move`s. Defines `state`, `legal_forces`, `is_terminal`, `is_answer_phase`. Replaces the legacy `Protocol`. |
| **BAF / QBAF** | Bipolar / Quantitative Bipolar Argumentation Framework (Cayrol-Lagasquie-Schiex 2009; Baroni-Rago-Toni 2018). Nodes are arguments; edges are attacks (negative) or supports (positive); each argument has a base score. |
| **DF-QuAD** | Discontinuity-Free Quantitative Argumentation Debates (Rago-Toni-Aurisicchio-Baroni KR 2016). The default gradual semantics for L2. |
| **Gradual semantics** | A function from a (Q)BAF to a vector of strengths in [0, 1]. We implement DF-QuAD, Quadratic Energy (Potyka), Euler-based (Amgoud-Ben-Naim), and the novel Strategic-Coupled (DF-QuAD ⊕ ATL). |
| **LTL₍f₎** | Linear Temporal Logic on finite traces (De Giacomo-Vardi 2013). The logic in which we write monitor properties. |
| **LTL3** | Three-valued runtime monitor variant (Bauer-Leucker-Schallhart 2011). Returns ⊤ / ⊥ / ?. |
| **MCMAS** | Open-source model checker for multi-agent systems (Lomuscio et al.). Used offline for small-instance verification. |
| **ATL / CTLK** | Alternating-Time / Computation-Tree Logic with Knowledge. Used in P1 to express coalition-strategic and epistemic properties. |
| **ISPL** | Interpreted Systems Programming Language. The MCMAS input format. |
| **Intervention** | An action triggered when a monitor returns ⊥. Five concrete: `ReprompCorrective`, `ForceChallenge`, `TriggerVerifier`, `EscalateModel`, `FreezeAndAccept`. |
| **JSD** | Jensen-Shannon Divergence. The L3 default disagreement metric: `JSD(P_1,…,P_n) = H(Σ w_i P_i) − Σ w_i H(P_i)`. |
| **MUSE** | Multi-LLM Uncertainty via Subset Ensembles (Kruse et al. EMNLP 2025). A specific JSD-based UQ method. |
| **ConFreeze** | Selective Multi-Model Debate through Consensus Freezing (OpenReview `PrqXuAS4BZ`). Stops deliberation when JSD < threshold AND confidence > floor. |
| **Privileged Knowledge** | The 2026 finding that models are better at predicting their own correctness than peers' on factual tasks (~5% gap), zero on math, partial on coding. Drives per-domain calibration weights. |
| **Provenance Receipt** | First-class output of every NS run. Contains: typed Trace, QBAF (when applicable), monitor verdicts, ASP groundings, Lean/Z3 certificates, per-move cost ledger. |
| **CouncilGenome** | Frozen dataclass containing `(members, topology, protocol, aggregator, monitors, calibration, termination, cascade)`. The unit of search in L5. |
| **Behavioural descriptor** | A scalar summary of a council's deliberation behaviour, computed from L1+L2+L3 outputs. Examples: `disagreement_persistence`, `qbaf_density`, `role_entropy`, `evidence_anchor_rate`, `cost`, `monitor_pass_rate`, `mast_coverage`. |
| **CMA-MAE** | Covariance Matrix Adaptation MAP-Annealing (Fontaine-Nikolaidis GECCO 2023). The default QD optimiser. |
| **pyribs** | Python QD library (Tjanaka et al. GECCO 2023). The implementation backend for L5. |
| **Rainbow Teaming** | Open-Ended Generation of Diverse Adversarial Prompts (Samvelyan NeurIPS 2024). The basis for L5's red-team archive. |
| **Popper** | Inductive Logic Programming via learning-from-failures (Cropper-Morel). The L6 default rule miner. |
| **ILASP** | Inductive Learning of Answer Set Programs (Law et al.). The L6 alternative miner. |
| **CLMASP** | Coupling LLMs with Answer Set Programming for plan executability (`2406.03367`). The L6 replication target. |
| **Workstream** | A coherent body of layered work that delivers a layer of NS. Replaces "Phase" vocabulary on the `council-ns` branch. Workstreams W0–W7 are defined in §7. |
| **Constitution §N** | The N-th principle in the NS Constitution (12 principles, §5 of this plan). |
| **Defect D<n>** | The n-th defect in the legacy substrate, catalogued in `COUNCIL_NS_PLAN.md` §2.2 (D1–D17). Each is mapped to a workstream in §8 of this plan. |
| **Theorem T<n>** | The n-th theorem in the unified NS theory (T1–T13). Defined in `COUNCIL_NS_PLAN.md` §10; mapped to papers in §9 of this plan. |

---

## Appendix E — Tutorial: agent + skill workflow toward F v1.0.0

This is the workflow you (Eduard) follow inside Claude Code, day to day, to get from `v0.2.0.dev0` to `v1.0.0` (the flagship F submission). It is the answer to the question *"what do I type to get the most out of this setup?"*.

### E.0 The toolbox at a glance

**Project agents** (`.claude/agents/`, invoked via `Task` or natural-language reference):
- `workstream-planner` — triage. Always the first agent on any new task.
- `constitution-reviewer` — diff audit against the 12 principles + architecture rules.
- `theorem-checker` — theorem audit before paper submission.
- `ltl-property-author` — drafts a new LTL₍f₎ `Property` end to end.
- `qbaf-reviewer` — audits any change to the QBAF builder/aggregator.
- `qd-runner` — drives long QD experiments in background.
- `paper-drafter` — scaffolds a paper LaTeX skeleton.

**Project skills** (`.claude/skills/`, invoked as `/<skill>`):
- `new-protocol-automaton`, `new-property`, `new-semantics`, `new-calibrator`, `new-cascade-strategy`, `new-descriptor`, `new-emitter` — scaffolds for the layered abstractions.
- `mine-rules`, `run-pareto`, `paper-skeleton`, `ablation-row` — paper-supporting workflows.
- `check-constitution` — fast pre-commit grep audit.

**Personal skills** (in your `~/src/` library, invoked as `/<skill>`):
- `spec-driven-development`, `incremental-implementation`, `test-driven-development`, `debugging-and-error-recovery`, `documentation-and-adrs`, `git-workflow-and-versioning`, `code-review-and-quality`, `code-simplification`, `security-and-hardening`, `planning-and-task-breakdown`, `context-engineering`.

### E.1 The daily loop (the inner workflow you'll repeat hundreds of times)

```
1.  Define the task → /workstream-planner "<request>"
       output: workstream Wn, layer Ln, branch name, file list, theorem T?, paper P?
2.  Spec it      → /spec-driven-development on the planner's output
       output: docs/specs/<workstream>-<slug>.md
3.  Branch       → /git-workflow-and-versioning  (creates feature/ns-w<n>-<slug>)
4.  Scaffold     → /<new-X> (the project skill that matches the layer)
       output: source file + test file, both empty stubs but well-formed
5.  Plan slices  → /planning-and-task-breakdown  (carves work into ≤ 600 LOC PRs)
6.  Implement    → /incremental-implementation + /test-driven-development
       per slice: write failing test → make it pass → commit
7.  Document     → /documentation-and-adrs  if the slice made an architectural decision
       output: docs/adr/NNNN-<slug>.md
8.  Layer audit  → invoke the layer-specific reviewer agent:
       L1 → @qbaf-reviewer is wrong layer; for L1 use the existing test suite + theorem-checker
       L2 → @qbaf-reviewer
       L3, L4, L5, L6 → @code-reviewer + @constitution-reviewer
9.  Pre-commit   → /check-constitution           (fast grep gate)
10. Final review → @constitution-reviewer        (nuanced audit)
11. PR           → gh pr create against council-ns
12. Merge        → after CI green and review pass
```

If a step breaks, jump to `/debugging-and-error-recovery`.

### E.2 The per-workstream playbook

#### Starting W0 (substrate, L0) — already partially live; finish during weeks 1–2 of the kickoff

```
/workstream-planner "build the W0 substrate"
/spec-driven-development                                  → docs/specs/w0-substrate.md
/new-protocol-automaton DeliberationAutomaton            → council/dialect/protocols/deliberation.py + tests
/new-protocol-automaton PersuasionAutomaton              → council/dialect/protocols/persuasion.py + tests
/new-protocol-automaton InquiryAutomaton                 → council/dialect/protocols/inquiry.py + tests
/new-protocol-automaton SocraticAutomaton                → council/dialect/protocols/socratic.py + tests
/test-driven-development                                  → 30+ Move/Trace tests
@constitution-reviewer                                    → audit before merge
/documentation-and-adrs                                   → docs/adr/0001-typed-move-substrate.md
```
**Acceptance.** GSM8K runs end-to-end on Move-typed traces with parity to legacy `council-agent==0.1.0` ± 1pp.

#### W1 (verification spine, L1)

```
/workstream-planner "wire L1 verification"
/spec-driven-development                                  → docs/specs/w1-verification.md
@ltl-property-author "RefutationReachable: every winning consensus survived ≥ 1 challenge"
@ltl-property-author "NoPrematureConsensus"
@ltl-property-author "FairnessOfRoles"
@ltl-property-author "NoMonotoneAgreementCollapse"
@ltl-property-author "EventuallyDecide"
@ltl-property-author "BoundedRound"
@ltl-property-author "NoSycophancyCascade"
@ltl-property-author "ProvenanceCompleteness"
@ltl-property-author "ChallengeBeforeConsensus"
@ltl-property-author "ModalitySafe"
/new-property                                              # used inside the agent
@theorem-checker T1                                        → docs/theory.md proof of LTL3 soundness
@theorem-checker T2                                        → docs/theory.md proof of compositionality
@theorem-checker T3                                        → docs/theory.md no-go for consensus-only
```
**Acceptance.** Each property has ⊤ + ⊥ tests; ISPL emitter passes a 4-agent / 4-round MCMAS check; T1, T2, T3 mechanised in `tests/regressions/`.

#### W2 (argumentation aggregator, L2)

```
/workstream-planner "wire L2 argumentation aggregator"
/new-semantics DFQuADSemantics            → df_quad.py + tests
/new-semantics QuadraticEnergySemantics   → quad.py + tests
/new-semantics EulerSemantics             → euler.py + tests
/new-semantics CoupledSemantics           → coupled.py + tests       # the novel strategic-coupled
@qbaf-reviewer                            → audit determinism + monotonicity + Walton-Krabbe
@theorem-checker T4 T5 T6 T7              → proofs in docs/theory.md
@constitution-reviewer
```
**Acceptance.** `ArgumentationAggregator` runs on the canonical Walton-Krabbe trace; emits BAFMarginConfidence; Mermaid render works in a smoke run.

#### W3 (calibration, L3)

```
/new-calibrator JSDCalibrator
/new-calibrator MUSECalibrator
/new-calibrator PrivilegedKnowledgeCalibrator
/new-calibrator IsotonicCalibrator
@constitution-reviewer
```
**Acceptance.** ECE on a held-out GSM8K split drops below 0.05.

#### W4 (cascade, L4)

```
/new-cascade-strategy InContextDistillationCascade
/new-cascade-strategy RouteByDomainStrategy
/new-cascade-strategy DisagreementGatedEscalation
@constitution-reviewer
```
**Acceptance.** ≥ 30% cost reduction at ≤ 2pp accuracy loss on a 100-task synthetic GSM8K.

#### W5 (quality-diversity, L5) — the load-bearing P3 deadline

```
/new-descriptor DisagreementPersistenceDescriptor
/new-descriptor QBAFDensityDescriptor
/new-descriptor RoleEntropyDescriptor
/new-descriptor EvidenceAnchorRateDescriptor
/new-descriptor MASTCoverageDescriptor
/new-emitter CMAESEmitter
/new-emitter LLMReflectiveEmitter
/new-emitter LLMDiffEmitter
/new-emitter StructuralEmitter
@qd-runner "run QD on GSM8K, 100 tasks, 50 generations, seeds 0,1,2"
/run-pareto <experiment_id>
@theorem-checker T8 T9 T10
```
**Acceptance.** Hypervolume strictly increases in ≥ 80% of generations; Pareto front contains ≥ 5 non-dominated genomes.

#### W6 (ILP / ASP, L6)

```
/workstream-planner "mine protocol rules from labelled traces"
# First, generate a labelled trace bundle:
#   experiments/traces/<slug>/{positive,negative}.json + background.pl
/mine-rules <slug>                       → rules.lp + MCMAS verification report
/new-protocol-automaton <Name>Automaton  → wire the verified rules into a new ProtocolAutomaton subclass
@theorem-checker T12 T13
```
**Acceptance.** ≥ 1 learned protocol passes all L1 monitors and outperforms its un-learned counterpart on a held-out task.

#### W7 (continuous: evaluation, demos, papers)

```
# Add a benchmark
/workstream-planner "load FrontierMath Tier 4"
# Implement tasks/frontiermath.py + tests/tasks/test_frontiermath.py

# Run an ablation row for §11.3
/ablation-row <config_name> <benchmark>

# Reproduce a paper
bash experiments/reproduce/p<n>_<slug>.sh

# Build the demo
/security-and-hardening                    → audit apps/streamlit_demo.py
uv run streamlit run apps/streamlit_demo.py
```

### E.3 The per-paper playbook

For each of P1–P5, F:

```
1.  /paper-skeleton P<n> <slug>            → papers_drafts/p<n>_<slug>/{main,supplementary}.tex + Makefile
2.  Fill prose; reference the layer's API by reading council/<layer>/.
3.  Run the experiment matrix:
       /ablation-row <config> <benchmark>   (×N, one per row in §11.3)
4.  /run-pareto <experiment_id>             → Pareto figure for §11.3
5.  Theorem audit:
       @theorem-checker T<a> T<b> T<c>
6.  Code review:
       @code-reviewer                       (your private agent)
       @constitution-reviewer               (NS-specific blockers)
7.  Document the decisions:
       /documentation-and-adrs              for any new architectural choice the paper introduced
8.  Camera-ready hygiene:
       /code-simplification                 on the paths the paper exercises
       /code-review-and-quality             on the whole PR series
9.  Submit (manual): zip the supplementary + push the `paper/p<n>-<venue>-submission-<date>` tag.
```

### E.4 Cheat-sheet: which agent / skill solves which problem

| Symptom / situation | Reach for |
|---|---|
| "I don't know where to start." | `@workstream-planner` |
| "I have a fuzzy spec." | `/spec-driven-development` |
| "I'm about to write a lot of code." | `/incremental-implementation` |
| "I need to write tests first." | `/test-driven-development` |
| "I need a new layer artefact." | `/<new-X>` matching the layer (see table in §13.3) |
| "Something broke and I don't know why." | `/debugging-and-error-recovery` |
| "I just made an architectural decision." | `/documentation-and-adrs` |
| "I'm about to commit." | `/check-constitution` (fast) → `@constitution-reviewer` (nuanced) |
| "I changed the QBAF builder." | `@qbaf-reviewer` |
| "I'm running a long QD experiment." | `@qd-runner` (in background) |
| "I claimed a theorem." | `@theorem-checker` |
| "I'm starting paper P<n>." | `/paper-skeleton P<n> <slug>`, then `@paper-drafter` |
| "I need a row for the ablation table." | `/ablation-row` |
| "I need the Pareto figure." | `/run-pareto` |
| "I want to learn a protocol from traces." | `/mine-rules` |
| "Code feels overcomplicated." | `/code-simplification` |
| "Demo handles user input." | `/security-and-hardening` |
| "Long-running poll loop." | `/loop` |

### E.5 The release ladder (M1 → M6)

| Milestone | Tag | Workstreams done | Headline artefact |
|---|---|---|---|
| **M1** (end May 2026) | `v0.2.0` | W0 | typed substrate, GSM8K parity, NeSy 2026 short paper |
| **M2** (end Jul 2026) | `v0.3.0` | W0, W1, W2 | LTL₍f₎ monitors live; argumentation aggregator working; P1 + P2 ready to submit |
| **M3** (end Sep 2026) | `v0.4.0` | + W3, W4, W5 (start) | first verified ARC-AGI-2 submission; legacy_council/ deleted; P3 draft ready |
| **M4** (end Dec 2026) | `v0.5.0` | + W5 (full) | co-evolutionary loop scaling; P3 + P4 in submission |
| **M5** (end Feb 2027) | `v0.9.0` | + W6 | learned protocols re-verified by MCMAS; P5 in submission |
| **M6** (end Apr 2027) | **`v1.0.0`** | F integrates all | flagship F submitted (JAIR/AIJ); Streamlit demo live; ARC Prize stamp |

The merge `council-ns` → `main` happens **once**, at v1.0.0. Until then, `main` stays at `legacy/v0.1.0` for the student.

---

*End of master plan. Single-folder convention; one Constitution per branch; one PyPI name per branch (`council-agent` on `main`, `councilagent` on `council-ns`); seven NS agents and twelve NS skills in `.claude/`. Update this document at each milestone (M1–M6).*
