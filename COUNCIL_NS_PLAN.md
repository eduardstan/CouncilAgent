# CouncilAgent‑NS

## *The first multi-LLM council you can model-check.*

**A complete redesign plan for `eduardstan/CouncilAgent` toward a flagship neuro-symbolic agentic-AI repository.**

> Status of this document: a self-contained, code-grounded plan based on the actual `main` branch of the repository (114 commits, 4,125 LOC core, 6,014 LOC tests, 422 test functions), the deep-research DOCX `Enhancing_LLM_Council_Orchestration.docx`, the existing `LLMCouncil_Deep_Review.md`, and verified April 2026 SOTA numbers from the relevant leaderboards. Prepared as a working blueprint for a researcher-developer who has the capability to execute it.

---

## Table of contents

1. [Executive summary](#1-executive-summary)
2. [Forensic audit of `CouncilAgent@main`](#2-forensic-audit-of-councilagentmain)
3. [Cross-reference: DOCX vs. code vs. April-2026 literature](#3-cross-reference-docx-vs-code-vs-april-2026-literature)
4. [Competitive landscape and the publishable gap](#4-competitive-landscape-and-the-publishable-gap)
5. [The redesign: `CouncilAgent‑NS`](#5-the-redesign-councilagent-ns)
6. [Layer-by-layer specification (L0–L6)](#6-layer-by-layer-specification-l0l6)
7. [The new repository layout](#7-the-new-repository-layout)
8. [The new Constitution (12 principles)](#8-the-new-constitution-12-principles)
9. [Empirical plan: benchmarks, baselines, ablations](#9-empirical-plan-benchmarks-baselines-ablations)
10. [Theoretical contributions to claim](#10-theoretical-contributions-to-claim)
11. [Publication strategy: 5 papers + a flagship](#11-publication-strategy-5-papers--a-flagship)
12. [12-month execution roadmap](#12-12-month-execution-roadmap)
13. [Repo strategy for stars and adoption](#13-repo-strategy-for-stars-and-adoption)
14. [Risks, threats and counterfactuals](#14-risks-threats-and-counterfactuals)
15. [Two-week kickoff checklist](#15-two-week-kickoff-checklist)
16. [References](#16-references)

---

## 1. Executive summary

### 1.1 The single sentence

`CouncilAgent‑NS` reframes a multi-LLM council as a **typed transition system over speech-acts that you can model-check, aggregate via formal argumentation, illuminate with quality-diversity, and inductively learn protocols for** — turning the existing engineering baseline into the first multi-LLM council whose deliberation has *provable* properties.

### 1.2 Three uncomfortable truths first

1. **Your repo is much better than the previous report assumed, but it has zero research substance.** `CouncilAgent@main` is a B+ engineering submission: layered Constitution, 422 tests, ruff/mypy strict on core, structured-output enforcement, working Condorcet/Copeland with confidence formula, real Shapley + AIPW + Wilcoxon. But it ships **one dataset (GSM8K)**, **no symbolic component of any kind**, **plurality-fraction "confidence" mis-marketed as calibrated**, and the only "dynamic" topology is round-parity adjacency. The deep review's roadmap stops at hypothesis-testing on existing benchmarks — these are *engineering experiments*, not a research contribution.

2. **The competitive landscape moved while you were building.** As of April 2026: **Sakana TRINITY** (ICLR 2026, `arXiv:2512.04695v2`) holds **86.2 % LiveCodeBench** with a **0.6B coordinator + 10K-param head + sep-CMA-ES**; **Conductor** (`arXiv:2512.04388`) RL-trains a 7B NL-orchestrator with recursive topology; **MaAS / AFlow / AgentSquare / SwarmAgentic** automate workflow design; **Mixture-of-Agents** is the gold-standard ensembling baseline; **AlphaEvolve / GEPA / OpenEvolve** make LLM-driven evolution mainstream. Your DOCX correctly identifies this frontier but the code is two years behind it.

3. **The neuro-symbolic redesign is the cleanest move available given your CV.** Nobody at the intersection of (i) typed multi-agent dialogue, (ii) LTL_f / ATL model-checking, (iii) gradual argumentation aggregation, and (iv) QD over deliberation behaviour is publishing in 2026. This is *your* slot. The DOCX ends with engineering hardening; the redesign below pushes the same project past the publication bar.

### 1.3 The strategy in one paragraph

**Don't preserve legacy.** Branch the existing repository as `legacy/v0.1`, archive it, and rebuild `CouncilAgent‑NS` ground-up around a typed `Move`/`Trace` algebra. Six new layers (L1–L6) attach cleanly: **L1 verification** (LTL_f runtime monitors compiled via SPOT, offline MCMAS / NuSMV checks for small instances), **L2 argumentation aggregation** (BAF/QBAF + DF-QuAD gradual semantics, derived directly from the typed Trace — no LLM extraction step), **L3 calibrated disagreement** (Jensen-Shannon divergence with privileged-knowledge per-domain calibration), **L4 cost-aware escalation** (in-context distillation cascade, multi-tier router), **L5 quality-diversity co-evolution** (CMA-MAE over council compositions with verification-derived behavioural descriptors, plus Rainbow-Teaming-style red-team archive), **L6 ILP rule mining** (Popper / ILASP4 over labelled traces, learned protocols re-verified by L1). Five publishable papers + a flagship JAIR/AIJ integration, mapped to NeSy 2026 / KR 2026 / NeurIPS 2026 D&B / AAMAS 2027 / ICLR 2027. Benchmarks: ARC-AGI-2, FrontierMath Tier 4, LiveCodeBench, SWE-bench Pro, HLE, ZebraLogic-hard, Putnam-AXIOM Variation. The "wow" demo is a hosted Streamlit space that shows an LTL_f monitor catching a sycophancy collapse mid-debate, redirecting to a devil's-advocate role, producing a verified verdict, and rendering the BAF as a live Mermaid graph — every claim with a *provenance receipt*.

### 1.4 Why the previous report's "preserve legacy" instinct was wrong

I had to retract that. The legacy code has:
- **Free-text `AgentResponse.content: str`** with no algebraic structure — every L1–L6 layer would be forced to re-parse natural language to attach.
- **Plurality-fraction confidence** mis-marketed as "calibrated" via Constitution §5 — the brand contract is broken.
- **`CouncilPolicy` returns one of two static tiers** (`fast_vote`, `standard_deliberation`) — this is a hardcoded if-statement, not a policy.
- **Round-parity is hardcoded into `_default_round_label`** in `aggregation.py:138` — the protocol can declare `is_answer_round`, but the aggregator's default labelling reaches across the layer boundary anyway.
- **The "Constitution" is enforced by review skills**, not by types — there is no compile-time guarantee that a new aggregator won't `Counter(r.content)` on raw text.

Each of these is a *design defect*, not an engineering oversight. They cannot be patched layer-by-layer; the substrate has to change. Section 5.1 explains why "additive" was wrong and "branch-and-rebuild" is right.

### 1.5 The five papers and one flagship

| ID | Headline | Target venue (2026/2027) | Backup |
|---|---|---|---|
| **P1** | *Verified Deliberation: Model-Checking Multi-LLM Councils with Epistemic-Strategic Logic* | **AAMAS 2027** main (Oct 2026 abstract) | NeSy 2026 |
| **P2** | *Strategic Gradual Argumentation for Multi-LLM Aggregation* | **AAAI 2027** (Aug 2026) | NeurIPS 2026 D&B |
| **P3** | *Quality-Diversity over Deliberation Behaviour* | **NeurIPS 2026** main (May 2026) | ICLR 2027 |
| **P4** | *Co-evolutionary Red/Blue Teaming of Deliberating Councils* | **AAMAS 2027** companion | NeurIPS 2026 main |
| **P5** | *Inductive Discovery of Multi-Agent Dialogue Protocols* | **KR 2026** | ILP 2026, NeSy 2026 |
| **F** | *CouncilAgent‑NS: A Neuro-Symbolic Multi-Agent LLM Council Framework* | **JAIR / AIJ** flagship | — |

§11 has the per-paper experimental plan, theorems, and contingencies.

---

## 2. Forensic audit of `CouncilAgent@main`

This is grounded against the actual files I read. File:line citations are exact.

### 2.1 What's already right (preserve in spirit, port to the new design)

| Where | What is right |
|---|---|
| `council/core.py:70-162` | `run_council()` is pure async, framework-free; clean separation of `_generate` / `_deliberate` / `_rank` / aggregation. Phase 5 fix: rank+aggregate happen *inside* the loop so termination strategies see aggregated state. **Port the structure.** |
| `council/core.py:323-394` | `_build_visibility_context()` — anonymisation in **exactly one place**. Textbook single-source-of-truth. **Port the rule.** |
| `council/context.py` | Frozen `slots=True` dataclasses for `AgentResponse`/`VisibilityContext`/`AggregationResult`/`PreferenceData`/`RichPreference`. The seam is correct; the *content* is wrong (untyped strings). **Port the seam, change the content.** |
| `council/aggregation.py:42-49` | `Aggregation.aggregate(..., round_history=None, original_prompt=None)` — debate-aware aggregation kwargs (Phase 5.4). **This is exactly the socket the argumentation aggregator plugs into.** |
| `council/protocol.py:28-47` | `is_answer_round(round_index) -> bool` and `cycle_length() -> int` predicates. Critical for any monitor that needs to distinguish votes from critiques. **Generalise to a protocol automaton.** |
| `council/aggregation.py:306-375` | `CondorcetAggregation` with Copeland fallback and a confidence formula `(copeland + max_wins) / (2 * max_wins)`. Real social-choice work. **Reuse as a baseline aggregator inside L2.** |
| `council/topology.py` + `CommunicationMode` enum | `INDIVIDUAL` / `BROADCAST` / `RELAY` correctly differentiate `BusTopology` from `CompleteGraphTopology` semantically. **Port the enum, expand the topology library.** |
| `council/termination.py:87-103` | `CompositeTermination` with `OR`-composition. **The right base for `LTLfMonitorTermination`, `JSDDivergenceTermination`, `ArgumentationStableTermination`.** |
| `council/agent.py:91-123` | `EscalationStrategy` ABC with `HumanInTheLoop`, `UpgradeModels`, `AddDeliberation`. **Generalise to the cost-aware cascade router (L4).** |
| `evaluation/shapley.py` | Real Shapley with exact (n ≤ 6) + Monte-Carlo paths and three-axiom tests. Reviewer-quality. **Keep as-is, expand to per-genome attribution in L5.** |
| `evaluation/statistical.py` | Bootstrap CI, Wilcoxon — paired stats correctly used. **Keep, add AIPW + mixed-effects + Bradley-Terry.** |
| `pyproject.toml` | Strict mypy on `council.context/core/agent`; ruff B/UP/SIM/RUF; clean dep groups (`dev`, `benchmark`, `embeddings`). **Port; tighten the strict-mypy footprint.** |
| `tests/`, 422 functions | pytest-asyncio, `FakeModelClient`, `RUN_INTEGRATION=1` gating. **Port the discipline; rewrite the bodies for the new types.** |
| `.claude/` discipline | `CLAUDE.md` Constitution + `rules/architecture.md` + scaffolding skills. **Port the Constitution-as-doc idea; back it with type-level enforcement.** |

### 2.2 The 17 design defects that block top-tier publication

Each defect is grounded by a precise file/function reference and tagged by severity (B = blocker for top-tier publication, H = high, M = medium).

| # | Sev | Where | Defect | Implication |
|---|---|---|---|---|
| **D1** | **B** | `council/context.py:25` `AgentResponse.content: str` | **Messages are free-text strings.** No `Move = Propose / Challenge / Concede / Vote` algebra, no protocol automaton, no admissibility relation. | Nothing symbolic can attach without re-parsing free text. The previous report's "this is the precondition for everything" diagnosis is confirmed against the actual code. |
| **D2** | **B** | `council/aggregation.py:81-83` `MajorityVote.confidence = winner_count / total_responses` | **"Calibrated confidence" is plurality fraction.** The Constitution §5 brand promise ("calibrated confidence is the council's unique value, derived from inter-agent agreement, not self-report") is materially false. | Reviewer reads §5 + the `MajorityVote` body in 30 seconds → reject. |
| **D3** | **B** | No symbolic anything | No verifier interface. No Z3 / clingo / Lean / SPOT / MCMAS. No LTL_f / CTL / ATL / DEL formulae. No argumentation framework. No ILP. | NeSy 2026 / KR 2026 / NeurIPS 2026 NeSy track / AAMAS each *require* a symbolic component. Without one you cannot enter. |
| **D4** | **B** | `council/policy.py:31` `_FREE_MODELS` + `policy.py:88` `plan()` returns one of two hard-coded tiers | **`CouncilPolicy` is a 2-line if-statement.** No learned routing, no QD-archive lookup, no per-domain calibration, no cost-budget Pareto. | Sakana TRINITY/Conductor occupy this turf; without QD over typed protocols you cannot differentiate. |
| **D5** | **H** | `council/termination.py:44-70` `AgreementThreshold` | Plurality-on-canonical. No information-theoretic stopping (no JSD / KL / mutual information), no ConFreeze, no protocol-completion criterion, no LTL_f-monitor verdict. | DOCX explicitly calls for MUSE/JSD; ConFreeze is the cleanest single layer-3 win. |
| **D6** | **H** | `tasks/profiles.py:31` only `gsm8k` registered | **One dataset.** Deep review Phase 4 promised MMLU / TruthfulQA / HumanEval; not done. The DOCX still proposes MMLU + MATH500 + LiveCodeBench, but those are saturated by April 2026. | A NeurIPS submission needs ≥ 4 benchmarks across reasoning / math / code / agentic with bootstrapped CIs. |
| **D7** | **H** | `council/topology.py:65` `DynamicStarTopology` | **Round-parity adjacency is the only "dynamic" topology.** No learned routing, no GNN-routed graph, no graph-evolved-over-rounds. | Topology is the single most active dimension in the 2024–2026 literature (G-Designer, MacNet 1000-agent, MaAS, AFlow, Trinity); static topologies are 2024 priors. |
| **D8** | **H** | `council/protocol.py:117` `PeerReviewProtocol` | Hardcoded 2-cycle (critique + revision). The protocol is **not** a finite-state machine over typed speech acts. No Walton-Krabbe deliberation typology, no McBurney-Hitchcock-Parsons primitives, no admissible-move predicate. | Without a protocol automaton, you cannot state — let alone verify — properties like "no premature consensus", "every winning claim was challenged at least once", "only valid retraction transitions". |
| **D9** | **H** | `council/agent.py:198-202` and `council/aggregation.py:81` | **Dissent / agreement computed in raw-string space.** `agent.py` does `r.content.strip().lower() != winner` despite the Phase 6.21 audit item explicitly identifying this as a defect. | Misreports dissent on prose answers like "The answer is 15." vs canonical "15". Confidence calculations are systematically biased toward over-reporting dissent. |
| **D10** | **H** | No tools at all | Council can only call LLMs via LiteLLM. No MCP, no retrieval, no Python execution sandbox, no Z3 / clingo / Lean tool, no web. | All 2026 frontier benchmarks (GAIA, SWE-bench Pro, BrowseComp, MLE-bench, ARC-AGI-2 verified solutions) require tools. Without them you cannot enter their leaderboards. |
| **D11** | **H** | DOCX-vs-code drift | DOCX advocates **TRINITY-style evolved coordinator**, **MUSE/JSD ConFreeze**, **In-Context Distillation Cascade** (`2512.02543`), **Modality Sabotage diagnostic** (`2511.02794`), **Privileged-Knowledge per-domain calibration** (`2604.12373`), **Council of Rivals**, **Provenance Receipts**. **None** of these are in the code. | Reviewers will read both the DOCX (when you cite it) and the code; drift is a credibility failure. |
| **D12** | **H** | `evaluation/baselines.py:34-146` | Baselines are random / best-single / oracle-best-of-N / self-consistency / majority-without-deliberation. **Missing**: Mixture-of-Agents, Self-MoA, debate-only, single-agent-equal-token-budget (the "Stop overvaluing MAD" gold standard), ConFreeze. | A 2026 reviewer who reads "Should we be going MAD?" or "Single-Agent vs MAS Under Equal Thinking-Token Budgets" rejects the paper. |
| **D13** | **H** | `council/aggregation.py:138-145` `_default_round_label` | The default round-label heuristic is `"ANSWER" if round_index % 2 == 0 else "CRITIQUE"`. This is a layer violation: aggregation reaches into protocol semantics. | A protocol-agnostic aggregator must not embed assumptions about a specific protocol's round structure. |
| **D14** | **M** | `council/agent.py:147` `escalation_threshold: float = 0.4` | Hardcoded magic number. No domain-aware threshold (DOCX shows factual ≠ math ≠ coding privileged-knowledge gaps). | Per-`TaskProfile` knob today; missing. |
| **D15** | **M** | No co-evolution / QD | Phase 7 hypothesis-testing is "vary one parameter at a time". No QD archive, no MAP-Elites, no behavioural descriptors, no co-evolutionary loop. | TRINITY is the fence; without QD over typed protocols you cannot push past it. |
| **D16** | **M** | `evaluation/metrics.py:64-100` `task_accuracy` smart matcher | Word-boundary match + numeric canonicalisation is reasonable, but no semantic-equivalence path for free-text tasks (summarisation, code), no LLM-as-judge hybrid, no execution-feedback for code. | Multi-domain benchmarks (HumanEval, BrowseComp, GAIA) need different correctness signals; the existing `_word_boundary_match` is a numeric-tasks specialist. |
| **D17** | **M** | `experiments/run.py:621` LOC monolith | The runner does YAML parsing + factory wiring + transcript formatting + MLflow logging + per-task evaluation in one file. | This is fine for a baseline; for a flagship repo, it must be split into a CLI front-end + a pure async service + a logging adapter. |

### 2.3 Verdict

The repo is a **strong engineering baseline** with **zero research substance** by April-2026 standards. The defects are not patchable; they are *substrate-level*. The Constitution promises calibrated confidence and gets plurality fraction; the architecture promises layer cleanliness and an aggregator reaches into protocol semantics for round labels; the design promises drop-in LLM replacement and provides a static if-statement policy. **Branch-and-rebuild is the rational decision**, and §5.1 makes the case in detail.

---

## 3. Cross-reference: DOCX vs. code vs. April-2026 literature

The DOCX is a good direction document but its load-bearing citations need calibration against the live literature. I checked each.

| DOCX claim (#cit) | Citation | In code? | April-2026 status | Action in CouncilAgent‑NS |
|---|---|---|---|---|
| **TRINITY**: 0.6B coordinator, 10K-param head, sep-CMA-ES, **86.2 ± 0.5 % LiveCodeBench**, ICLR 2026 | `2512.04695v2` | No | **Verified.** Sakana FUGU is the productisation; Thinker/Worker/Verifier triple, Qwen3-0.6B coordinator. | **Head-on competitor.** Differentiator: TRINITY evolves a learned coordinator; CouncilAgent‑NS evolves the *deliberation* (compositions × typed protocols × verifier-derived descriptors). Also: TRINITY has no symbolic verifier, no argumentation graph, no QD over deliberation behaviour. |
| **Conductor**: 7B RL-trained NL orchestrator, recursive topology | `2512.04388` | No | **Verified.** | **Second competitor.** Differentiator: theirs is RL on free text; yours is QD over typed protocol automata + LTL_f monitors. |
| **MUSE**: JSD-based multi-LLM uncertainty | `PMC12702469` | No | **Verified directionally.** Information-theoretic UQ via Jensen-Shannon Divergence over predictive distributions is a recurring 2025/2026 theme. | **Implement** as L3 backbone (`council_ns/calibrate/jsd.py`). Cleanest single calibration win. |
| **ConFreeze**: selective debate via consensus freezing | OpenReview `PrqXuAS4BZ` | No | **Probable but not deeply verified.** OpenReview ID consistent; description matches recent disagreement-aware debate work. | Implement as `ConFreezeTermination` (L1 + L3). Treat as a baseline + ablation, not a citation foundation. |
| **In-Context Distillation Cascade**: 2.5× cost on ALFWorld | `2512.02543v3` | No | **Verified directionally.** Student-teacher cascades for cost reduction is an active 2025/2026 area. | Implement as `CascadeEscalationStrategy` (L4). Cost-Pareto enabler. |
| **Modality Sabotage** diagnostic | `2511.02794v1` | No | **Verified.** "When One Modality Sabotages the Others" — diagnostic lens for multimodal reasoning. | Adopt as one of the **error-taxonomy axes** for empirical analysis. The "sabotage" pattern (one high-confidence error overriding correct evidence) maps directly to a sycophancy-monitor LTL_f formula. |
| **Privileged-Knowledge gap** (~5 % factual, ~0 math) | `2604.12373v4` | No | **Verified directionally.** "Masked by Consensus: Disentangling Privileged Knowledge in LLM Correctness". | Use to motivate the **per-domain calibration** module in L3 (`privileged.py`). |
| **MMLU / MATH500 / LiveCodeBench** plan | DOCX §3 | Only GSM8K | **MMLU + MATH** are saturated by April 2026 (>90 %); **LiveCodeBench** is held by TRINITY at 86.2 %. | **Replace** with the 2026 frontier suite (§9): ARC-AGI-2, FrontierMath Tier 4, SWE-bench Pro, HLE, ZebraLogic-hard, Putnam-AXIOM Variation. Keep LiveCodeBench as a head-to-head against TRINITY. |
| **Provenance Receipts** | blog-tier | No | Blog post; useful framing but not citable as a method. | Implement as a **first-class output** of every NS run (typed Trace + QBAF + LTL_f verdict + ASP grounding + cost ledger). This is the **viral demo** material. |
| **CLAUDE.md 3-tier memory hierarchy** | engineering | Yes | Your `.claude/CLAUDE.md` is well-done. | Keep, polish; back the discipline with type-level enforcement (§7). |

**The DOCX's verdict on itself.** Its Phase 1–4 plan ("infrastructure stabilisation + uncertainty controller + benchmarking + publishable artefact" in 10 weeks, on MMLU/MATH500/LiveCodeBench) is *too modest* by 2 publication tiers. The plan below subsumes its directions and pushes them past the publication bar.

### 3.1 What the DOCX nailed

- **Calibrated disagreement as the central novelty axis** — correct.
- **Cost-Pareto as a first-class metric** — correct.
- **The cascade pattern (open-source student → frontier teacher)** — correct.
- **Modular reproducibility via locked configs and trace bundles** — correct, and partially in the existing code.
- **Identifying TRINITY/Conductor as the competitive frontier** — correct and current.

### 3.2 What the DOCX missed

- **No formal verification dimension.** The DOCX never names a logic, a model-checker, or a runtime-monitor library. This is your largest unclaimed publishable territory.
- **No argumentation framework.** Despite citing "social choice" in the previous research plan (`plan.md`), it goes from "voting" to "MetaJudge synthesis" without ever passing through Dung 1995 / Baroni-Rago-Toni 2019 / Freedman-Toni 2024.
- **No quality-diversity** — the DOCX has "evolutionary strategies" as a Trinity description but does not generalise to QD over typed protocols.
- **No ILP / ASP** — the DOCX's symbolic side is empty.
- **Old benchmarks.** MMLU/MATH/LiveCodeBench are 2024 priors; the 2026 frontier is ARC-AGI-2 / FrontierMath Tier 4 / SWE-bench Pro / HLE.

The plan in §5–§12 fills exactly these gaps.

---

## 4. Competitive landscape and the publishable gap

A 2026 reviewer's null hypothesis: *"another multi-LLM debate paper that does not beat Mixture-of-Agents under matched compute."* You need a credible refutation. Here is the threat model.

### 4.1 The 11-system fence

| System | Headline | What it does | Why it's not Council‑NS |
|---|---|---|---|
| **Sakana TRINITY** (ICLR 2026, `2512.04695v2`) | 86.2 % LiveCodeBench pass@1 | 0.6B coordinator + 10K head, sep-CMA-ES, assigns Thinker/Worker/Verifier each turn | Evolves a *single learned coordinator*; no symbolic verifier, no argumentation graph, no QD over deliberation. 3 fixed roles vs. your typed Move algebra. |
| **Sakana Conductor** (`2512.04388`) | ~SOTA long-horizon | 7B model, RL-trained, NL-orchestrates workers incl. itself; recursive topology | RL on free text. No types, no logic, no QD. |
| **Mixture-of-Agents** (Wang et al., ICLR 2025 spotlight, `2406.04692`) | Strong on AlpacaEval / MMLU | Layered ensembling: proposers → aggregator | Gold-standard *baseline*; you must beat it under matched tokens. |
| **Self-MoA** (`2502.00674`) | Beats mixed-MoA by 6.6 % | Self-mixing one strong model | Argues *against* heterogeneity. Your H1-style hypothesis (DOCX) tests the inverse. |
| **AFlow / AgentSquare / MaAS / SwarmAgentic / EvoFlow** | Various | Auto-design / search of agentic workflows | None defines deliberation as a *typed transition system* or applies formal verification. |
| **GEPA** (Agrawal et al., ICLR 2026 oral, `2507.19457`) | +6 pp avg vs GRPO with 35× fewer rollouts | Reflective Pareto-genetic prompt evolution | A **method to use** for L5's LLM-mutation, not a competitor. |
| **AlphaEvolve / OpenEvolve** (Novikov et al., May 2025, `2506.13131`) | Beat Strassen on 4×4 matmul | LLM-mutation in evolutionary code search | A **tool to borrow** for L5 protocol-automaton mutations. |
| **ArgLLMs** (Freedman et al., AAAI 2025, `2405.02079`) | Explainable, contestable claim verification | LLM-extracted QBAF + DF-QuAD gradual semantics | **Closest published precedent** to L2. Single-claim verification, not multi-LLM aggregation. Differentiator: ours operates on a *typed-protocol-enforced* graph; no LLM extraction step ⇒ no "Can LLMs Judge Debates?" (`2509.15739`) error mode. |
| **MArgE** (`2508.02584`) | Multi-LLM evidence meshing | Same QBAF approach over multiple LLMs | Closest direct neighbour. Differentiator: ours adds verification + co-evolution. |
| **Karpathy llm-council** (15.3K stars) | "Vibe-coded" baseline | Static 3-stage (fan-out → peer-review → chair) | The 2024 reference, not a research artefact. |
| **Perplexity Model Council** (Feb 2026) | Production product | Three frontier models in parallel + synthesizer + agreement-display UX | Closed; product not research. |

### 4.2 Your unique slot

No public system at April 2026 does any of these. **Each is a publishable contribution.**

1. **Model-checks the deliberation trace** against LTL_f / ATL / CTLK specifications.
2. **Aggregates** multi-LLM councils via a **typed-protocol-enforced** bipolar argumentation graph with gradual semantics.
3. **Co-evolves council compositions and adversarial prompts** under quality-diversity with **verification-derived behavioural descriptors** — diversity over *deliberation behaviour*, not over outputs.
4. **Mines dialogue protocols** from labelled deliberation traces via ILP and re-verifies the learned protocols.

These four are the spine of P1, P2, P3+P4, P5 respectively. The flagship F integrates all four.

### 4.3 The "first multi-LLM council you can model-check" tagline

This isn't marketing fluff; it's a precise factual claim. As of April 2026, no public system:
- Publishes a typed `Move` algebra for council deliberation,
- Compiles LTL_f formulae against council traces via SPOT,
- Emits ISPL for MCMAS (or NuSMV for CTL fragment) over the council interpreted system,
- Lets you state and check properties like `RefutationReachable`, `NoPrematureConsensus`, `NoMonotoneAgreementCollapse` against actual deliberation traces.

The GitHub README's first line should be exactly this: *"The first multi-LLM council you can model-check."* It is true, scarce, and viral.

---

## 5. The redesign: `CouncilAgent‑NS`

### 5.1 Why *branch-and-rebuild*, not *additive refactor*

Two reasons that compound:

1. **The substrate is wrong.** `AgentResponse.content: str` is the data type that propagates through 4,125 LOC and 422 tests. Replacing it requires touching almost every file. An "additive" approach that adds `AgentResponse.move: Move | None = None` keeps the old free-text path alive, doubles the API surface, and creates a permanent "are we typed yet?" pseudo-state. This **prevents** the static-typing guarantees that make the verification layer worthwhile.

2. **The Constitution is type-erased.** Constitution §3 ("topology controls visibility, protocol controls presentation, aggregation controls decision") is enforced by review skills (`.claude/agents/constitution-reviewer.md`) and grep audits (`.claude/skills/check-constitution`), not by types. Defects D9 (raw-string dissent in `agent.py`) and D13 (round-parity heuristic in `aggregation.py`) escaped despite the discipline. The new design encodes the Constitution at the *type* level — you cannot construct an `Aggregator[BAFAggregator, MoveTrace]` over a non-typed trace.

Therefore: **archive `CouncilAgent@main` as `legacy/v0.1`, declare it the engineering baseline (worth one ablation row in every paper), and build `council_ns/` ground-up.** The new repo's PyPI name is `councilagent-ns`; the legacy import path stays for backwards-compatibility benchmarking.

### 5.2 The architectural picture

```
                    USER-FACING SURFACE
                           │
                           ▼
              ┌─────────────────────────┐
              │   CouncilAgent.complete │  drop-in LLM replacement
              │   → CouncilResponse     │  + typed Trace + QBAF + LTL verdict
              └────────────┬────────────┘     + Provenance Receipts
                           │
                           ▼
              ┌─────────────────────────┐
              │     CouncilPolicy       │  cost-aware planner
              │  (task → genome lookup) │  draws from the QD archive
              └────────────┬────────────┘
                           │
              ━━━━━━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                              SYMBOLIC STRATUM (Council‑NS)
              L6  ILP / ASP rule mining and integrity constraints
                    (Popper, ILASP4, clingo)
              L5  Co-evolution / QD over compositions
                    (CMA-MAE on pyribs + LLM-mutation à la GEPA / AlphaEvolve)
              L4  Cost-aware escalation cascade
                    (in-context distillation, multi-tier router)
              L3  Calibrated disagreement
                    (Jensen-Shannon, MUSE, ConFreeze, privileged-knowledge per-domain)
              L2  Argumentation-based aggregator
                    (BAF/QBAF + DF-QuAD / QE / Euler gradual semantics)
              L1  Verification spine
                    (LTL_f runtime monitors via SPOT / ltl2mon, offline MCMAS)
              L0  Speech-act algebra
                    (typed Move/Trace + protocol automaton)
              ━━━━━━━━━━━━━┯━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                           │                NEURAL STRATUM
                           ▼
         run_council() — pure async pipeline (framework-free)
            generate → deliberate → monitor → aggregate → terminate
                           │
                           ▼
       Topology │ Protocol │ Ranker │ Aggregator │ Calibrator │ Termination
                           │
                           ▼
                  ModelClient — LiteLLM wrapper
                  ToolClient  — MCP / Z3 / clingo / Lean / Python / web
                           │
                           ▼
              ┌─────────────────────────┐
              │   Evaluation harness    │  metrics, baselines, Shapley,
              │   (benchmark mode only) │  AIPW, Bradley-Terry, mixed-effects
              └─────────────────────────┘
```

The new design has **two tools clients** (LLM and tools), **two strata** (neural + symbolic), and **one orchestrator** (`run_council_ns`).

### 5.3 The non-negotiable invariants

These are what the new Constitution (§8) encodes at the type level:

- Every `AgentResponse` carries a `Move`. There is no untyped path.
- Every protocol is a *finite-state machine* over an admissibility relation. There is no implicit "round 0 = generate, round 1 = critique" magic.
- Every aggregator is `BAFAggregator | OrdinalAggregator` — both consume `Trace`, never raw text.
- Every confidence value carries its *derivation*: `JSD(P_1, ..., P_n)`, `BAF strength margin`, `monitor verdict`, etc. — never plurality fraction.
- Every council run produces a **Provenance Receipt** with the typed Trace, QBAF, monitor verdicts, ASP groundings, cost ledger, and (when applicable) Lean/Z3 certificates.
- The verification layer can *intervene* (interrupt, force-challenge, escalate) — not just observe.

§8 has the formal Constitution.

---

## 6. Layer-by-layer specification (L0–L6)

This is the technical core of the plan. Each subsection: purpose, module path, types, key APIs, how it connects to neighbouring layers, what *theorem* the paper proves about it.

### 6.1 L0 — Speech-act algebra (the new substrate)

#### Purpose
Replace `AgentResponse.content: str` with a typed `Move` over typed `Claim`s, plus a finite-state `ProtocolAutomaton` that defines admissibility. **This is the precondition for L1–L6.**

#### Module path
```
council_ns/dialect/
  __init__.py
  moves.py            # Move ADT + Claim parser
  trace.py            # Trace, MoveID, immutable transitions
  protocols/
    base.py           # ProtocolAutomaton ABC
    deliberation.py   # Walton 2010 deliberation dialogue
    persuasion.py     # Persuasion sub-dialogue
    inquiry.py        # Inquiry dialogue
    composite.py      # Walton-Krabbe composite (deliberation w/ persuasion sub-dialogues)
    socratic.py       # Socratic question-driven
  parsers.py          # LLM-output → Move (structured-output schema)
  surface.py          # Move → natural-language rendering (for the next agent's prompt)
```

#### The Move ADT (concrete)

```python
# council_ns/dialect/moves.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Union

class Force(StrEnum):
    PROPOSE = "propose"
    CHALLENGE = "challenge"
    CONCEDE = "concede"
    RETRACT = "retract"
    QUESTION = "question"
    CLARIFY = "clarify"
    VOTE = "vote"
    ABSTAIN = "abstain"
    PASS = "pass"

class ClaimDomain(StrEnum):
    FOL = "fol"      # propositional/FOL → ASP-groundable
    LTLF = "ltlf"    # LTL_f over Trace events → self-referential meta-claims
    ARITH = "arith"  # arithmetic equality / inequality → SMT-verifiable
    CODE = "code"    # code snippet → executable / testable
    FREE = "free"    # free text → flagged for argument-mining sub-call

@dataclass(frozen=True, slots=True)
class Claim:
    surface: str                          # Natural-language statement
    formula: str | None = None            # Canonical form when extractable
    domain: ClaimDomain = ClaimDomain.FREE
    evidence: tuple[str, ...] = ()        # MoveIDs / source URLs / tool-call IDs

# All move kinds carry the same metadata header.
@dataclass(frozen=True, slots=True)
class _MoveHeader:
    move_id: str
    agent_id: str
    round_index: int

@dataclass(frozen=True, slots=True)
class Propose(_MoveHeader):
    force: Force = Force.PROPOSE
    claim: Claim = field(default_factory=lambda: Claim(surface=""))
    confidence: float = 0.5    # uncalibrated self-report

@dataclass(frozen=True, slots=True)
class Challenge(_MoveHeader):
    force: Force = Force.CHALLENGE
    target: str = ""           # MoveID of the targeted Propose
    reason: Claim = field(default_factory=lambda: Claim(surface=""))

@dataclass(frozen=True, slots=True)
class Concede(_MoveHeader):
    force: Force = Force.CONCEDE
    target: str = ""

@dataclass(frozen=True, slots=True)
class Retract(_MoveHeader):
    force: Force = Force.RETRACT
    own: str = ""              # MoveID of the agent's own Propose
    why: Claim | None = None

@dataclass(frozen=True, slots=True)
class Question(_MoveHeader):
    force: Force = Force.QUESTION
    target: str = ""
    query: Claim = field(default_factory=lambda: Claim(surface=""))

@dataclass(frozen=True, slots=True)
class Clarify(_MoveHeader):
    force: Force = Force.CLARIFY
    target: str = ""
    restated: Claim = field(default_factory=lambda: Claim(surface=""))

@dataclass(frozen=True, slots=True)
class Vote(_MoveHeader):
    force: Force = Force.VOTE
    option: Claim = field(default_factory=lambda: Claim(surface=""))
    confidence: float = 0.5

@dataclass(frozen=True, slots=True)
class Abstain(_MoveHeader):
    force: Force = Force.ABSTAIN
    why: str = ""

Move = Union[Propose, Challenge, Concede, Retract, Question, Clarify, Vote, Abstain]
```

#### The Trace

```python
# council_ns/dialect/trace.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
from council_ns.dialect.moves import Move

@dataclass(frozen=True, slots=True)
class Trace:
    """Immutable sequence of typed moves with O(1) lookup by MoveID and round."""
    moves: tuple[Move, ...] = ()

    def by_id(self, move_id: str) -> Move:
        # backed by a precomputed dict in __post_init__
        ...

    def at_round(self, r: int) -> tuple[Move, ...]:
        ...

    def by_force(self, f: Force) -> tuple[Move, ...]:
        ...

    def append(self, m: Move) -> "Trace":
        return Trace(self.moves + (m,))

    def to_events(self) -> tuple[dict, ...]:
        """Serialise to LTL_f atomic-proposition events for the monitor."""
        ...
```

Crucially, `Trace.to_events()` produces the *atomic propositions* the LTL_f monitor consumes. This is the one bridge between L0 and L1.

#### The ProtocolAutomaton

```python
# council_ns/dialect/protocols/base.py
from abc import ABC, abstractmethod
from council_ns.dialect.moves import Move, Force
from council_ns.dialect.trace import Trace

class ProtocolAutomaton(ABC):
    """A finite-state machine over typed moves.

    `state(trace)` returns a (round_phase, agent_turn) state.
    `legal_forces(trace, agent_id)` returns admissible Force values.
    `is_terminal(trace)` returns True when no admissible non-trivial move remains.
    `is_answer_phase(trace)` returns True when the next move is expected to be a Vote.
    """

    @abstractmethod
    def state(self, trace: Trace) -> tuple[str, str]: ...

    @abstractmethod
    def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]: ...

    @abstractmethod
    def is_terminal(self, trace: Trace) -> bool: ...

    @abstractmethod
    def is_answer_phase(self, trace: Trace) -> bool: ...
```

`is_answer_round(round_index)` and `cycle_length()` from the legacy code become *derived* from the automaton's terminal-state and answer-phase predicates — no more round-parity hardcoding.

Concrete implementations: **`DeliberationAutomaton`** (Walton 2010), **`PersuasionAutomaton`** (Walton-Krabbe), **`InquiryAutomaton`**, **`CompositeAutomaton`** (deliberation with persuasion sub-dialogues), **`SocraticAutomaton`** (question-driven). Each is ~150 LOC.

#### The parser

LLMs emit a `MoveBundle` per turn via structured output (`response_format={"type": "json_object"}` + JSON schema injection):

```json
{
  "moves": [
    {
      "force": "propose",
      "claim": {"surface": "The answer is 72.", "formula": "answer == 72", "domain": "arith"},
      "confidence": 0.9
    },
    {
      "force": "challenge",
      "target": "m_03_a1",
      "reason": {"surface": "Step 3 has an arithmetic error: 18 × 4 = 72, not 64."}
    }
  ]
}
```

When the LLM violates the schema, fall back to argument-mining (Gorur-Rago-Toni 2024, `2402.11243`, open-source LLMs beat RoBERTa on attack/support detection across 10 datasets).

#### Theorem (L0)
**No theorem at L0; L0 is the substrate.** The publishable claim from L0 alone is **type-correctness of the protocol-automaton encoding**: every legacy protocol embeds isomorphically into a `ProtocolAutomaton` instance. Mechanise this in pytest, not in a proof.

#### What L0 enables for upstream layers
- **L1** can compile LTL_f formulae over `Trace.to_events()` and check them online.
- **L2** can build a BAF/QBAF directly from `Trace` (every `Challenge`→attack, every `Concede`→support, every `Vote`→base-score boost). No LLM extraction step.
- **L5** can mutate the *automaton itself* as part of the genome, evolving new protocols.
- **L6** can mine ASP rules over move sequences.

---

### 6.2 L1 — Verification spine

#### Purpose
Two complementary mechanisms: (a) **online runtime monitoring** with LTL_f / LTL3 — fast, prevents protocol violations; (b) **offline model-checking** with MCMAS or NuSMV for small instances — proves properties hold under modelling assumptions.

#### Module path
```
council_ns/symbolic/verify/
  __init__.py
  ltlf.py             # LTL_f formula AST + parsing (using lark or pyparsing)
  monitor.py          # LTL3 three-valued monitor: trace events → {⊤, ⊥, ?}
  spot_backend.py     # SPOT bindings (ltl2mon, ltl2tgba)
  ltl2mon_backend.py  # Bauer-Leucker-Schallhart LTL3 fallback
  ispl.py             # Trace + ProtocolAutomaton → ISPL for MCMAS
  smv.py              # Trace + ProtocolAutomaton → SMV for NuSMV (CTLK fragment)
  properties.py       # Named property library
  interventions.py    # Actions on monitor verdicts
```

#### The named-property library (initial)

These are LTL_f formulae over the atomic propositions emitted by `Trace.to_events()`. They **become reviewer-citable invariants**: each is a paragraph in P1's paper.

| Name | LTL_f sketch | Reading |
|---|---|---|
| `RefutationReachable` | `F (challenge_accepted ∧ target ∈ winning_claims)` | Any winning consensus survives at least one accepted challenge. |
| `NoPrematureConsensus` | `G (consensus → evidence_anchor_count ≥ θ)` | Consensus only allowed when enough agents anchored on evidence. |
| `FairnessOfRoles` | `(<<Pro>> F speak) ∧ (<<Con>> F speak)` (ATL) | Both pro and con coalitions retain strategic ability to speak. |
| `NoMonotoneAgreementCollapse` | `G ¬(prevWinner ⊃ winner ∧ ¬challengeOccurred)` | Winners cannot persist round-to-round without ever being challenged. |
| `EventuallyDecide` | `F terminated` | Liveness — the dialogue eventually ends. |
| `BoundedRound` | `F^≤k terminated` | Timed liveness with bound k. |
| `NoSycophancyCascade` | `G ¬(repeatConcedes(i, j) > τ)` | An agent concedes to one peer at most τ times in a row. |
| `ProvenanceCompleteness` | `G (vote → evidence(claim) ≠ ∅)` | Every vote is anchored on at least one evidence atom. |
| `ChallengeBeforeConsensus` | `G ((proposal_accepted) → O (challenge_against(proposal)))` (past-LTL) | Every accepted proposal had at least one prior challenge. |
| `ModalitySafe` | `G ¬(dominant_agent ∧ contradicted_evidence)` | The "modality sabotage" pattern (DOCX `2511.02794`) is excluded. |

#### Online monitoring (LTL3, Bauer-Leucker-Schallhart 2011)

Use **SPOT** (Renault, Duret-Lutz et al.) for LTL → Büchi → on-the-fly DFA, exposed via the `spot` Python package. Fallback: the `ltl2mon` reference implementation (Bauer 2010). The monitor compiles each LTL_f formula to a deterministic Moore automaton over `{⊤, ⊥, ?}` (Bauer-Leucker-Schallhart, TOSEM 2011); each new `Move` produces a new `Trace.to_events()` symbol; the monitor steps once per move. On `⊥` verdict, the **intervention layer** is triggered.

#### Interventions

```python
# council_ns/symbolic/verify/interventions.py
class Intervention(ABC):
    @abstractmethod
    async def execute(self, trace: Trace, violated: Property,
                      ctx: CouncilContext) -> Trace: ...

class ReprompCorrective(Intervention):    # Re-prompt the offending agent
class ForceChallenge(Intervention):       # Insert a Challenge from a devil's advocate
class TriggerVerifier(Intervention):      # Call Z3 / clingo / Lean
class EscalateModel(Intervention):        # Bump to the frontier-tier
class FreezeAndAccept(Intervention):      # Accept the partial result, log violation
```

This is **LLM-Modulo (Kambhampati et al. ICML 2024) at the dialogue level** — the existing LLM-Modulo work is single-agent; multi-agent is open.

#### Offline model-checking (MCMAS for ATL+CTLK; NuSMV for CTL fragment)

For each of N test cases, the deliberation Trace is encoded as an ISPL **interpreted system** for MCMAS:
- Each agent → ISPL `Agent` module with local protocol = `legal_forces(state, agent_id)`.
- The moderator → ISPL `Environment` with the global turn variable.
- The properties from `properties.py` are written in CTLK / ATLK; MCMAS supports both via OBDDs.
- Bounded-recall variants for memoryless-agent assumption: **MCMAS-BR** (AAAI 2020).
- For pure CTL fragment without strategy logic: NuSMV is faster.

This works at small scale (n ≤ 6 agents, bounded round depth) — sufficient for the **soundness theorem** in P1.

#### Theorem (L1)
**Soundness of the runtime monitor.** For every property φ in the LTL_f safety fragment, if the LTL3 monitor returns ⊤ on the realised trace, then φ holds on every infinite extension that respects the protocol automaton. (Standard; cite Bauer-Leucker-Schallhart 2011.)

**Compositionality (assume-guarantee).** Let A1 ‖ A2 be a sub-council composition with monitors M1, M2 verifying φ1, φ2. Under the standard assume-guarantee rule (Pnueli 1985, adapted), the composite system satisfies φ1 ∧ φ2 if and only if M1 and M2 agree on the shared atomic propositions. (Adapt to the dialogue setting; original contribution.)

**A no-go theorem.** Identify a CTLK invariant (e.g. `G (consensus → ∃i. K_i evidenceFor(consensus))` under shared-knowledge semantics) that *no* purely consensus-driven aggregator can satisfy. This motivates L2.

#### What L1 enables
- **A new termination strategy** `LTLfMonitorTermination(monitor, on_violation: Intervention)` plugs into the existing `CompositeTermination`.
- **A new metric** `verification_passed: dict[PropertyName, bool]` in every `CouncilResult`.
- **The theoretical anchor** for P1.

---

### 6.3 L2 — Argumentation-based aggregator

#### Purpose
Replace plurality voting with a **typed-protocol-derived bipolar argumentation framework + gradual semantics**. Eliminates the "Can LLMs Judge Debates?" (`2509.15739`) failure mode because the graph is *constructed by the protocol*, not extracted from text.

#### Module path
```
council_ns/symbolic/argue/
  __init__.py
  baf.py              # BAF / QBAF data structures
  builders.py         # Trace → QBAF construction rules
  semantics/
    df_quad.py        # Rago-Toni-Aurisicchio-Baroni KR 2016
    quad.py           # Quadratic Energy (Potyka 2018)
    euler.py          # Euler-based (Amgoud-Ben-Naim 2017)
    coupled.py        # Strategic gradual semantics (NEW — combines DF-QuAD with ATL coalition reasoning)
  aggregator.py       # ArgumentationAggregator: an Aggregation subclass
  asp_backends.py     # Optional: extension semantics (preferred/stable/...) via clingo
  visualisers.py      # Mermaid + GraphViz exporters for the demo
```

#### The Trace → QBAF construction

```python
# council_ns/symbolic/argue/builders.py
def build_qbaf(trace: Trace, calibrator: Calibrator | None = None) -> QBAF:
    """
    Construct a QBAF from a typed Trace. Rules:
      - Every Propose → an argument node.
        Base score = calibrator(propose.confidence, propose.agent_id, claim.domain)
                     when calibrator is given; else propose.confidence.
      - Every Challenge(target, reason) → attack edge (reason → target),
        with attack weight = LLM-emitted certainty of the challenge.
      - Every Concede(target) → support edge (concession_node → target).
      - Every Retract(own) → mark own_node as withdrawn, recompute strengths.
      - Every Vote(option, conf) → base-score boost on the matching Propose's
        argument (clamped to [0, 1]).
      - Self-attacks (an argument that contradicts its own evidence) are detected
        via a sub-call to the verifier (Z3 / clingo) when claim.domain ∈ {ARITH, FOL}.
    """
    ...
```

#### The aggregator

```python
# council_ns/symbolic/argue/aggregator.py
class ArgumentationAggregator(Aggregator):
    """A new Aggregator subclass operating on Trace, not raw responses."""

    def __init__(self,
                 semantics: GradualSemantics = DFQuADSemantics(),
                 calibrator: Calibrator | None = None,
                 fallback: Aggregator | None = None):
        self._sem = semantics
        self._calib = calibrator
        self._fallback = fallback or PluralityAggregator()  # for empty BAFs

    async def aggregate(self, trace: Trace, *, original_question: str) -> AggregationResult:
        baf = build_qbaf(trace, calibrator=self._calib)
        if not baf.proposals:
            return await self._fallback.aggregate(trace, original_question=original_question)
        strengths = self._sem.evaluate(baf)
        winner = max(baf.proposals, key=lambda a: strengths[a.id])
        runner_up = max((a for a in baf.proposals if a.id != winner.id),
                        key=lambda a: strengths[a.id], default=None)
        margin = strengths[winner.id] - (strengths[runner_up.id] if runner_up else 0.0)
        return AggregationResult(
            answer=winner.claim,
            confidence=float(margin),    # ∈ [-1, 1] → clamp to [0, 1] in L3
            method="ArgumentationAggregator",
            metadata={
                "baf": baf.to_dot(),
                "baf_mermaid": baf.to_mermaid(),
                "strengths": dict(strengths),
                "extension": self._sem.preferred_extension(baf),
            },
        )
```

The `metadata.baf_mermaid` is the demo gold — every council answer comes with a live argument-graph visualisation.

#### Theorem (L2)
1. **Recovery-of-Borda lemma.** When the BAF has only `Vote` moves (no `Propose`/`Challenge`/`Concede` outside the votes themselves), DF-QuAD gradual semantics recovers Borda count up to monotone re-scaling.
2. **Manipulability bound.** Define the *flip cost* of a BAF as the minimum number of attack-edge flips needed to change the winner under DF-QuAD. Provide an upper bound parameterised by (in-degree, attack/support ratio). Builds on Baroni-Rago-Toni 2019.
3. **Rationality postulates.** Identify which Caminada-Amgoud postulates the aggregator satisfies; identify which is violated (some must, by Gibbard-Satterthwaite).
4. **No-go from L1, fix in L2.** The CTLK invariant that no consensus-only aggregator satisfies — show that DF-QuAD over the typed BAF satisfies it.

These four are short theorems (≤ 1 page each in the appendix) that *sell* P2 to KR / AAAI / IJCAI.

---

### 6.4 L3 — Calibrated disagreement

#### Purpose
Replace the plurality-fraction "confidence" with **calibrated, information-theoretic disagreement signals**. This is the DOCX's central direction, finally implemented.

#### Module path
```
council_ns/calibrate/
  __init__.py
  jsd.py              # Jensen-Shannon divergence over agent answer distributions
  muse.py             # MUSE-style subset-ensemble divergence
  privileged.py       # Per-domain calibration (DOCX 2604.12373)
  termination.py      # JSDDivergenceTermination, ConFreezeTermination
  isotonic.py         # Temperature-scaled isotonic regression for confidence calibration
```

#### The math
$$\mathrm{JSD}(P_1,\ldots,P_n) = H\!\left(\sum_i w_i P_i\right) - \sum_i w_i H(P_i)$$

where $P_i$ is agent i's predictive distribution over canonical answers. The empirical $P_i$ comes from:
1. **K-shot temperature variants** of the same agent (cheap, ~3× cost),
2. **Token logprobs** when the backend exposes them (free, but provider-specific),
3. **Council-internal cross-agent estimation** when neither is available.

#### The privileged-knowledge router

DOCX `2604.12373v4` finding: factual tasks have ~5 % privileged-knowledge gap (agents predict their own correctness better than peers'); math tasks have ~0; coding has partial. Calibration weights derive from this:

```python
DOMAIN_CALIBRATION = {
    "factual":  {"self_weight": 0.55, "peer_weight": 0.45},   # privileged knowledge
    "math":     {"self_weight": 0.50, "peer_weight": 0.50},   # consensus dominates
    "coding":   {"self_weight": 0.50, "peer_weight": 0.30, "execution_weight": 0.20},
    # ... per TaskProfile
}
```

#### Termination strategies

```python
class JSDDivergenceTermination(TerminationStrategy):
    """Stop when JSD between consecutive rounds < threshold."""

class ConFreezeTermination(TerminationStrategy):
    """Stop when JSD < freeze_threshold AND confidence > confidence_floor."""
```

Both compose into the existing `CompositeTermination`.

#### What L3 enables
- The L2 BAF base-scores become *calibrated* (`Calibrator(confidence, agent_id, claim.domain)` in `build_qbaf`).
- The user-facing `CouncilResponse.confidence` is now provably an **information-theoretic disagreement margin**, not plurality fraction. The Constitution §5 brand promise becomes true.
- The L4 cascade triggers on JSD spikes, not on plurality fractions.

---

### 6.5 L4 — Cost-aware escalation cascade

#### Purpose
Implement the DOCX's In-Context Distillation Cascade and the multi-tier router.

#### Module path
```
council_ns/cascade/
  __init__.py
  distillation.py     # In-Context Distillation Cascade (2512.02543)
  router.py           # Multi-tier router (open-source ↔ frontier)
  budget.py           # Per-role $ accounting + token-budget allocation
  strategies.py       # CascadeEscalationStrategy, RouteByDomainStrategy, ...
```

The legacy `EscalationStrategy` (existing `council/agent.py:91`) generalises into a routing layer with multiple policies. The cascade fires when L3 reports JSD above per-domain thresholds.

---

### 6.6 L5 — Quality-Diversity over council compositions

#### Purpose
Search the space of *typed councils* — `(members × topology × protocol_automaton × aggregator × monitors × calibration)` — for Pareto-optimal Pareto coverage on `(accuracy, cost, robustness)` axes. Use **CMA-MAE on pyribs** with **LLM-mutation** à la GEPA / AlphaEvolve.

This is the **core empirical engine** of P3 and it differentiates Council‑NS from TRINITY: TRINITY evolves a single learned coordinator (10K params); Council‑NS illuminates a Pareto frontier of *typed protocols*.

#### Module path
```
council_ns/evolve/
  __init__.py
  genome.py           # CouncilGenome ↔ CouncilConfig isomorphism
  descriptors.py      # Behavioural descriptors (derived from L1 + L2)
  archives/
    grid.py           # MAP-Elites
    cvt.py            # CVT-MAP-Elites
    cmamae.py         # CMA-MAE wrapper around pyribs
  emitters/
    cmaes.py          # CMA-ES emitters from pyribs
    llm_reflective.py # GEPA-style reflective Pareto-genetic
    llm_diff.py       # AlphaEvolve-style diff-edit on protocol-automata
    structural.py     # Topology rewiring, role swap, calibrator change
  evaluate.py         # Genome → CouncilResult via run_council_ns
  pareto.py           # Pareto-front extraction, hypervolume
  redteam/
    __init__.py
    rainbow.py        # Rainbow-Teaming-style adversarial archive
    coevolve.py       # Symmetric Pareto co-evolution
```

#### The genome

```python
@dataclass(frozen=True, slots=True)
class CouncilGenome:
    members: tuple[AgentSpec, ...]              # (model_id, persona, decoding, tools)
    topology: TopologySpec                      # name + params
    protocol: ProtocolAutomatonSpec             # automaton class + params
    aggregator: AggregatorSpec                  # plurality / borda / DF-QuAD / ...
    monitors: tuple[PropertyName, ...]          # which LTL_f properties are active
    calibration: CalibrationSpec                # JSD / MUSE / privileged
    termination: tuple[TerminationSpec, ...]    # composite of strategies
    cascade: CascadeSpec | None = None          # L4 escalation policy
```

The genome is a *typed dataclass* — round-trippable to YAML for full reproducibility.

#### Behavioural descriptors (the QD archive keys)

These come from L1 + L2 + L3 — *not* from output text. **This is the publishable novelty over EvoFlow / SwarmAgentic / MaAS.**

| Descriptor | Computed from | Why it matters |
|---|---|---|
| `disagreement_persistence` | `# rounds with at least one accepted Challenge / # rounds` | Distinguishes councils that resolve quickly (good for easy tasks) from councils that argue (good for hard tasks). |
| `qbaf_density` | `(|attacks| + |supports|) / |arguments|` | High density = thoroughly contested; low = consensus-prone. |
| `role_entropy` | Shannon entropy of move-force distribution per agent | Differentiates "many proposers" from "many challengers" councils. |
| `evidence_anchor_rate` | Fraction of `Propose`/`Vote` with non-empty `evidence` | Provenance hygiene. |
| `cost` | $/task and seconds/task | Hard Pareto axis. |
| `monitor_pass_rate` | Fraction of selected LTL_f monitors that returned ⊤ | Verification compliance. |
| `mast_coverage` | For each of the 14 MAST failure modes (Cemri et al. NeurIPS 2025 D&B `2503.13657`), did this council survive an injection? | Coverage over **failure regimes**, not just performance. |

#### The optimiser

**CMA-MAE** (Fontaine-Nikolaidis GECCO 2023, `2205.10752`) on **pyribs** (Tjanaka et al. GECCO 2023). Emitters:
- `EvolutionStrategyEmitter` (CMA-ES) for continuous parameters (decoding, calibration thresholds).
- `LLMReflectiveEmitter` (GEPA-style, `2507.19457`) for prompt-mutations.
- `LLMDiffEmitter` (AlphaEvolve-style, `2506.13131`) for protocol-automaton edits.
- `StructuralEmitter` for topology rewiring and aggregator swaps.

#### Co-evolution

A **parallel red-team archive** of adversarial prompts (Rainbow-Teaming-style, Samvelyan et al. NeurIPS 2024, `2402.16822`) over `(target_capability, attack_strategy)` axes. Each generation, sample (host, parasite) pairs:
- Hosts win when their argumentation graph still produces the gold answer.
- Parasites win when the council's verdict flips.

This is host-parasite dynamics with QD coverage on both sides — open in the multi-agent LLM literature.

#### Theorem (L5)
1. **QD-coverage theorem.** Under the verifier-derived descriptor space, expected coverage at generation T strictly exceeds single-objective optimisation at matched evaluations. Builds on Qian-Xue-Wang-Filipič-Ochoa GECCO 2025.
2. **Pareto-domination bound.** Under matched compute, no single council in the archive Pareto-dominates the QD-illuminated frontier on `(accuracy, cost, robustness)`.
3. **Robustness theorem.** A council passing the chosen LTL_f monitors + sitting on the QD Pareto front is k-robust to adversarial archive samples, for k a function of L2's manipulability bound.

---

### 6.7 L6 — ILP / ASP rule mining

#### Purpose
Two uses, one upstream and one downstream of the council:

- **Upstream: ASP as a hard-constraint enforcer.** Domain constraints (e.g., "any plan involving credentials must include a verified-revoke step", "any math claim must cite a previously-asserted lemma") are encoded as ASP integrity constraints; clingo runs at every verifier call; if `UNSAT`, the move is rejected and the agent is re-prompted with the failing constraint serialised back. Extends CLMASP (`2406.03367`, lifting executability from <2 % to >90 % for VirtualHome) to multi-agent dialogue.
- **Downstream: ILP for protocol discovery.** Popper / ILASP4 learn dialogue rules from labelled traces (successful vs failed, partitioned by L1's verifier + ground-truth correctness). Output rules are then verified with MCMAS to confirm soundness; surviving rules go into the QD search space as new `ProtocolAutomaton` candidates. **The council learns its own playbook, then proves it sound.**

#### Module path
```
council_ns/symbolic/ilp/
  __init__.py
  popper.py           # Popper integration (Cropper-Morel 2020)
  ilasp.py            # ILASP4 integration (Law et al.)
  asp_constraints.py  # ASP integrity-constraint enforcer (clingo wrapper)
  trace_to_atoms.py   # Trace → ASP atoms / Popper background knowledge
  rule_to_automaton.py # Learned ASP rules → ProtocolAutomaton subclass
  verify_learned.py   # MCMAS verification of induced rules
```

#### Theorem (L6)
**Soundness of ILP-induced protocols.** A protocol automaton P induced from labelled traces by Popper/ILASP4 and subsequently verified by MCMAS against properties Φ satisfies Φ on all admissible runs. This is a corollary of the L1 soundness theorem; the contribution is the ILP→automaton extraction algorithm.

The truly novel claim: **the council's playbook can itself be a research output.** P5 exhibits the learned protocol rules as the artefact, with verified guarantees.

---

## 7. The new repository layout

```
councilagent-ns/                # PyPI: councilagent-ns; importable as council_ns
├── README.md                   # First line: "The first multi-LLM council you can model-check."
├── CITATION.cff                # auto-generated; Zenodo-hooked
├── LICENSE                     # Apache-2.0
├── pyproject.toml              # ruff + mypy strict on ALL of council_ns/
├── docs/
│   ├── theory.md               # Walton-Krabbe, Dung 1995, Baroni-Rago-Toni 2019,
│   │                           #   Bauer-Leucker-Schallhart 2011, Lomuscio MCMAS
│   ├── protocols.md            # How to write a new ProtocolAutomaton
│   ├── verifying.md            # How to write a new LTL_f property
│   ├── argumentation.md        # How to plug a new gradual semantics
│   ├── evolution.md            # How to add a new behavioural descriptor
│   ├── ilp.md                  # How to write a new ASP background theory
│   └── benchmarks.md           # Reproduction recipes for every paper number
├── council_ns/                 # The pure-Python core (no framework deps)
│   ├── __init__.py
│   ├── agent.py                # CouncilAgent — drop-in LLM replacement
│   ├── policy.py               # CouncilPolicy — task + budget → genome
│   ├── core.py                 # run_council_ns() — pure async pipeline
│   ├── context.py              # CouncilContext, CouncilResult, AgentResponse,
│   │                           #   CouncilState, ProvenanceReceipt
│   ├── models.py               # ModelClient (LiteLLM)
│   ├── tools.py                # ToolClient (MCP / Z3 / clingo / Lean / Python / web)
│   ├── topology.py             # CommunicationMode, Topology hierarchy
│   ├── ranker.py               # Ordinal / cardinal preference extraction
│   ├── normalizer.py           # Canonical-form extraction
│   ├── termination.py          # FixedRounds, JSDDivergence, ConFreeze, LTLfMonitor, ...
│   │
│   ├── dialect/                # L0
│   │   ├── moves.py
│   │   ├── trace.py
│   │   ├── parsers.py
│   │   ├── surface.py
│   │   └── protocols/
│   │       ├── base.py
│   │       ├── deliberation.py
│   │       ├── persuasion.py
│   │       ├── inquiry.py
│   │       ├── composite.py
│   │       └── socratic.py
│   │
│   ├── symbolic/
│   │   ├── verify/             # L1
│   │   │   ├── ltlf.py
│   │   │   ├── monitor.py
│   │   │   ├── spot_backend.py
│   │   │   ├── ltl2mon_backend.py
│   │   │   ├── ispl.py
│   │   │   ├── smv.py
│   │   │   ├── properties.py
│   │   │   └── interventions.py
│   │   ├── argue/              # L2
│   │   │   ├── baf.py
│   │   │   ├── builders.py
│   │   │   ├── semantics/
│   │   │   ├── aggregator.py
│   │   │   ├── asp_backends.py
│   │   │   └── visualisers.py
│   │   └── ilp/                # L6
│   │       ├── popper.py
│   │       ├── ilasp.py
│   │       ├── asp_constraints.py
│   │       └── ...
│   │
│   ├── calibrate/              # L3
│   │   ├── jsd.py
│   │   ├── muse.py
│   │   ├── privileged.py
│   │   └── isotonic.py
│   │
│   ├── cascade/                # L4
│   │   ├── distillation.py
│   │   ├── router.py
│   │   └── budget.py
│   │
│   ├── evolve/                 # L5
│   │   ├── genome.py
│   │   ├── descriptors.py
│   │   ├── archives/
│   │   ├── emitters/
│   │   ├── evaluate.py
│   │   ├── pareto.py
│   │   └── redteam/
│   │
│   └── adapters/               # Optional integrations (kept at the edges)
│       ├── langgraph.py        # Optional LangGraph wrapper
│       ├── mcp.py              # MCP tool integration
│       ├── otel.py             # OpenTelemetry tracing
│       └── mlflow.py           # MLflow logging
│
├── evaluation/                 # Benchmark mode only — never imported by council_ns
│   ├── metrics.py              # task_accuracy + verification_passed_rate +
│   │                           #   confidence_calibration_ECE + ...
│   ├── baselines.py            # MoA, Self-MoA, ConFreeze, CoT-SC, ... + matched-token
│   ├── shapley.py              # Per-genome contribution attribution
│   ├── statistical.py          # Bootstrap CI, Wilcoxon, AIPW, Bradley-Terry, mixed-effects
│   └── pareto.py               # Front extraction across genomes
│
├── tasks/                      # Benchmark loaders
│   ├── arc_agi_2.py            # ARC-AGI-2 (semi-private)
│   ├── frontiermath.py         # FrontierMath Tier 4
│   ├── livecodebench.py
│   ├── swe_bench_pro.py        # SWE-bench Pro (Scale AI 2026)
│   ├── hle.py                  # Humanity's Last Exam
│   ├── zebralogic_hard.py      # ZebraLogic-hard (NeSy-friendly)
│   ├── putnam_axiom.py         # Putnam-AXIOM Variation
│   ├── gaia.py
│   ├── webarena.py
│   ├── tau2bench.py
│   └── profiles.py             # Per-dataset TaskProfile registry
│
├── experiments/
│   ├── run.py                  # Single-genome runner (CLI)
│   ├── sweep.py                # Hydra-multirun sweep
│   ├── evolve.py               # QD evolution runner (uses L5)
│   ├── coevolve.py             # Co-evolutionary red/blue runner
│   └── reproduce/              # Per-paper one-command reproductions
│       ├── p1_verification.sh
│       ├── p2_argumentation.sh
│       ├── p3_qd.sh
│       ├── p4_coevolve.sh
│       └── p5_ilp.sh
│
├── apps/                       # The "wow" demos
│   ├── streamlit_demo.py       # Hosted Streamlit space
│   ├── arc_agi_runner.py       # One-click ARC-AGI-2 submission
│   └── live_monitor.py         # Live LTL_f monitor + Mermaid BAF visualiser
│
├── tests/                      # ~1500 test functions targeted; mirror the package layout
└── .github/workflows/          # CI: ruff / mypy / pytest / smoke-debate
```

This is **a flagship-grade layout**: clean module boundaries, no framework deps in `council_ns/`, optional integrations at the edges, every paper has a one-command reproduction, hosted demo for the README.

---

## 8. The new Constitution (12 principles)

The legacy Constitution (10 principles in `.claude/CLAUDE.md`) is mostly correct, but two key principles are *brand promises that the code does not honour*. The new Constitution adds two principles and tightens the others. **All 12 are encoded at the type level wherever possible.**

1. **The council is an agent, not a benchmark.** *Unchanged.*
2. **Same interface as a single LLM.** *Unchanged.* `CouncilAgent.complete(prompt) → CouncilResponse`.
3. **Topology controls visibility. Protocol controls *admissibility*. Aggregator controls decision.** *Strengthened*: protocols are typed FSMs (`ProtocolAutomaton`), not free-form prompt builders.
4. **Structured types over free text.** *New, replaces "structured output over regex"*: every `AgentResponse` carries a `Move`. Free-text content is a *fallback* path for backwards-compatibility and is flagged as such in the trace.
5. **Calibrated confidence is the council's unique value.** *Strengthened*: every `CouncilResponse.confidence` is **derived from an information-theoretic disagreement signal or an argumentation-strength margin**. Plurality fraction is *banned* from confidence outputs.
6. **Every council run must beat (matched-compute) Mixture-of-Agents on at least one Pareto axis.** *New, replaces the old "must beat majority-vote-without-deliberation" baseline*: the 2026 baseline is MoA, not majority-no-deliberation.
7. **Cost is first-class.** *Unchanged.*
8. **The core pipeline has zero framework dependencies.** *Unchanged.* `council_ns/core.py`, `agent.py`, `policy.py`, `dialect/`, `symbolic/`, `calibrate/`, `cascade/`, `evolve/` are pure-Python + asyncio. LangGraph, Hydra, MLflow, OpenTelemetry live in `adapters/`.
9. **Correctness before features.** *Unchanged.*
10. **Anonymise by default.** *Unchanged.*
11. **Symbolic outputs are first-class.** *New*: every `CouncilResponse` carries a `ProvenanceReceipt` with the typed `Trace`, the QBAF (when applicable), monitor verdicts (when applicable), ASP groundings (when applicable), Lean/Z3 certificates (when applicable), and a cost ledger.
12. **The verifier can intervene.** *New*: `LTLfMonitorTermination` + `Intervention` permit the symbolic layer to *redirect* deliberation, not merely observe it. This is what "LLM-Modulo at the dialogue level" means.

The legacy `.claude/` discipline (CLAUDE.md + rules + skills + agents) ports as-is; the architecture-rules table is regenerated from §6.

### 8.1 What the Constitution buys you

A reviewer who reads the Constitution and then reads the code:
- Sees a typed Move algebra (D1 fixed at substrate level).
- Sees confidence outputs derived from JSD / BAF margins (D2 fixed; brand promise becomes true).
- Sees a verifier interface and at least one concrete back-end (D3 fixed).
- Sees a benchmark suite ≥ 4 datasets across the April-2026 frontier (D6 fixed).
- Sees co-evolutionary QD over typed protocols (D15 fixed).
- Sees ProvenanceReceipts on every output (DOCX's "Provenance Receipts" lever, viral demo material).

This is what *flagship-grade* looks like.

---

## 9. Empirical plan: benchmarks, baselines, ablations

### 9.1 The benchmark suite (April-2026 frontier)

Tier-A is the headline; Tier-B sharpens specific layer claims; Tier-C is the saturated-but-still-useful sanity tier.

**Tier-A — must have, three different SOTA holders:**

| Benchmark | Type | Current SOTA (Apr 2026) | Why it matters | Council‑NS target |
|---|---|---|---|---|
| **ARC-AGI-2** (semi-private) | Reasoning, abstraction | **54 %** at $30.57/task — Poetiq + Gemini 3 Pro refinement (verified Dec 2025); Grand Prize unclaimed | The credibility multiplier — ARC Prize verifies submissions independently. Current SOTA is a *refinement loop*, exactly the shape of Council‑NS. | Match 54 % at < $10/task **or** push 54 % → 60 % at < $40/task. Either is publication-grade. Submit via ARC Prize 2026 to get the verified-leaderboard stamp. |
| **FrontierMath Tier 4** (private) | Research-level math | 38–42 % held by GPT-5.x Pro / Thinking; only ~17–20/48 ever solved cumulatively (Apr 2026) | The hardest currently-public math benchmark; tools allowed. | Solve **at least one Tier-4 problem the QD-illuminated frontier of `(verifier, council, prover)` triples handles that no single backbone solves**. One newly-solved problem is publication-worthy. |
| **LiveCodeBench** | Code, contamination-resistant | **86.2 % pass@1** — Sakana TRINITY (ICLR 2026) | Direct head-to-head against the strongest competitor. | Match or beat 86.2 % under matched compute, with the LTL_f monitor + the in-context cascade providing the cost-Pareto win. |

**Tier-B — sharpens specific contributions:**

| Benchmark | Sharpens which layer | Why |
|---|---|---|
| **SWE-bench Pro** (Scale AI) | L4 cascade, L5 QD | Contamination-resistant 2026 standard for agentic coding; SOTA ~64.3 % (Claude Opus 4.7, Apr 2026). |
| **Humanity's Last Exam (HLE)** | L3 calibration, L1 monitors | Multi-domain hard reasoning; SOTA ~44–47 % (verified) and 64+ % (self-reported). Specialist-by-domain council story. |
| **ZebraLogic-hard** | L1 verifier, L6 ASP enforcement | "Curse of complexity" benchmark — even o1/R1 collapse past CSP-size threshold. Direct call for LLM + Z3/clingo hybrid. |
| **Putnam-AXIOM Variation** | L1 monitors, L2 argumentation | Robustness benchmark — typical 15–25 pp drop on Variation vs Original. Council‑NS should drop ≤ 5 pp. **Best dataset for the verification-layer ablation.** |
| **GAIA** | L4 cascade, tools (L7) | The agentic-tooling reference; current SOTA from Magentic-One / OpenHands / Trase. Establishes Council‑NS as a real agentic system. |
| **WebArena** | L4 router | OpAgent at 71.6 % (Jan 2026) — head-to-head shows Council‑NS routes traffic and reasons about price/latency Pareto. |

**Tier-C — saturated, sanity rows only:**

GSM8K, MATH, MMLU, ARC-AGI-1, AIME 2024/2025, GPQA Diamond, HumanEval. These appear in the table but are not headline numbers — by April 2026 they are saturated and contamination-prone (Berkeley RDI 2026 audit, OpenAI Dec 2025 audit). Use to demonstrate non-regression.

### 9.2 The baseline set

Per Constitution §6, every Council‑NS configuration is compared against:

| Baseline | Why it's required |
|---|---|
| **Best single frontier model** | The lower bound any multi-model system must beat. |
| **CoT + Self-Consistency** (Wang ICLR 2023, sample N, majority-vote) | The "single agent with equal token budget" gold standard since Smit ICML 2024 "Should we be going MAD?" and "Stop overvaluing MAD" (`2502.08788`). **Matched-token-budget comparisons are mandatory.** |
| **Mixture-of-Agents** (Wang ICLR 2025 spotlight, `2406.04692`) | The 2026 multi-agent gold standard. |
| **Self-MoA** (`2502.00674`) | Tests the "diversity helps" hypothesis (DOCX H1). |
| **Karpathy llm-council** | The "vibe-coded baseline" reference. |
| **Sakana TRINITY** (`2512.04695v2`) on LiveCodeBench (Tier-A) | Head-to-head with the strongest evolved-coordinator competitor. |
| **Single-agent + Z3/clingo/Lean** (where applicable) | Establishes that *deliberation* adds value beyond *symbolic post-hoc verification*. |
| **CouncilAgent v0.1** (legacy) | One ablation row showing the value-add of the symbolic stratum. |
| **Random-vote / oracle-best-of-N** | Lower / upper bounds. |

### 9.3 The ablation matrix (P3's main result table)

Every cell × every Tier-A benchmark × ≥ 3 seeds × bootstrapped 95 % CIs.

| Configuration | What it tests |
|---|---|
| MoA baseline | The 2026 reference |
| Council‑NS, L0 only (typed Trace, no symbolic) | Does typing alone help? |
| Council‑NS + L1 (LTL_f monitor + intervention) | Verification spine contribution |
| Council‑NS + L1 + L2 (DF-QuAD aggregator) | Argumentation aggregator contribution |
| Council‑NS + L1 + L2 + L3 (JSD calibration) | Calibration contribution |
| Council‑NS + L1 + L2 + L3 + L4 (cost cascade) | Cost-Pareto contribution |
| Council‑NS + ... + L6 (ASP integrity constraints, no L5) | Hard-constraint contribution |
| Council‑NS + L5 (QD-Pareto front, single best from archive) | QD vs best-single-genome |
| **Council‑NS, full stack** | Every layer working together |
| Full minus L1 | Verification ablation |
| Full minus L2 (back to OW/ISP voting) | Argumentation ablation |
| Full minus L3 (back to plurality fraction) | Calibration ablation |
| Full minus L5 (no QD, hand-tuned single genome) | QD-vs-hand-tuning |
| Full minus L6 | ILP-rule-mining ablation |
| Full + adversarial archive samples | Robustness attribution |
| Cost-matched: each layer at fixed $/task | Pareto attribution |
| Per-MAST-mode: 14 cells × Council‑NS-full | Failure-mode coverage (Cemri NeurIPS 2025 D&B) |

### 9.4 The novel evaluation metrics

Beyond `task_accuracy`, Council‑NS reports:

| Metric | Definition |
|---|---|
| **Verification pass rate** | Fraction of selected LTL_f properties that returned ⊤ over the test set. |
| **Confidence calibration** | Expected Calibration Error (ECE) of the JSD-based confidence vs. true correctness. |
| **QBAF coherence** | Fraction of council answers whose winning argument has flip-cost ≥ θ. |
| **Provenance completeness** | Fraction of votes anchored on at least one evidence atom. |
| **Pareto hypervolume** | The L5 archive's hypervolume on (accuracy, cost, robustness). |
| **Diversity preservation** | Diversity_trajectory (already in `evaluation/metrics.py` — keep). |
| **Intervention rate** | How often L1 interventions were triggered, per intervention type. |

Several of these are **new metrics** that no competitor reports — that itself is a contribution.

---

## 10. Theoretical contributions to claim

P1 through P5 each have 1–4 theorems/propositions. The flagship F integrates them into a unified theory.

| ID | Theorem / Proposition | Paper | Difficulty |
|---|---|---|---|
| T1 | **Soundness of LTL3 monitors** for the L1 property library; verdict ⊤ ⇒ φ holds on every infinite extension respecting the protocol automaton. | P1 | Standard; cite Bauer-Leucker-Schallhart 2011. |
| T2 | **Compositionality (assume-guarantee)** for stacked sub-councils. | P1 | Original adaptation of Pnueli 1985. |
| T3 | **No-go for consensus-only aggregation.** Identify a CTLK invariant satisfied by no purely consensus-driven aggregator; motivates L2. | P1 | Original; small-instance result. |
| T4 | **Recovery-of-Borda lemma** for DF-QuAD on vote-only BAFs. | P2 | Short. |
| T5 | **Manipulability bound** on QBAF aggregation: minimum number of attack-flips to flip the winner, parameterised by graph structure. | P2 | Builds on Baroni-Rago-Toni 2019. |
| T6 | **Rationality-postulate characterisation** of the Council‑NS argumentation aggregator (which Caminada-Amgoud postulates hold; which Arrow-style axiom is necessarily violated, by Gibbard-Satterthwaite). | P2 | Standard form; original instantiation. |
| T7 | **Strategic gradual semantics** combining DF-QuAD with ATL coalition reasoning satisfies T3's invariant. | P2 | Original. |
| T8 | **QD coverage theorem** under verifier-derived descriptors. | P3 | Builds on Qian-Xue-Wang-Filipič-Ochoa GECCO 2025. |
| T9 | **Pareto-domination bound** for QD-illuminated archive vs. single-objective optimisation. | P3 | Original. |
| T10 | **Robustness theorem** for monitor-passing × Pareto-front × bounded-attacker. | P3 + P4 | Original. |
| T11 | **Co-evolutionary convergence properties** (host-parasite Pareto front in the bounded-attacker case). | P4 | Original. |
| T12 | **Soundness of ILP-induced protocols** when re-verified by MCMAS. | P5 | Corollary of T1. |
| T13 | **A characterisation theorem**: when do learned protocol rules generalise to held-out task domains? | P5 | Original; small empirical lower-bound complement. |

The flagship paper F integrates T1–T13 into a single architectural theorem: **Council‑NS satisfies a chosen subset of soundness, fairness, calibration, and robustness properties under standard modelling assumptions.**

---

## 11. Publication strategy: 5 papers + a flagship

### 11.1 Paper-by-paper plan

#### P1 — Verified Deliberation: Model-Checking Multi-LLM Councils with Epistemic-Strategic Logic

- **Layers**: L0 + L1.
- **Headline**: First multi-LLM council whose deliberation can be model-checked. Soundness theorem (T1), compositionality (T2), no-go for consensus-only aggregation (T3).
- **Empirics**: Tier-A on Putnam-AXIOM Variation (the verification-layer ablation makes this benchmark sing) + ZebraLogic-hard. Per-property pass rate as the headline metric.
- **Target**: AAMAS 2027 main (Oct 2026 abstract). Multi-agent + epistemic logic is AAMAS's home turf.
- **Backup**: NeSy 2026 main (June 2026). KR 2026 (May/June 2026).

#### P2 — Strategic Gradual Argumentation for Multi-LLM Aggregation

- **Layers**: L0 + L2 (+ L3 for calibration).
- **Headline**: Replace voting with typed-protocol-derived QBAF + DF-QuAD. T4 (Borda recovery), T5 (manipulability bound), T6 (rationality postulates), T7 (strategic gradual semantics).
- **Empirics**: HLE + LiveCodeBench, head-to-head against ArgLLMs and MArgE. Confidence calibration (ECE) + flip-cost as headline metrics.
- **Target**: AAAI 2027 (Aug 2026). Argumentation work is AAAI's home turf.
- **Backup**: NeurIPS 2026 D&B (Jun 2026). IJCAI 2027 (Jan 2027).

#### P3 — Quality-Diversity over Deliberation Behaviour

- **Layers**: L5 (with L0+L1+L2+L3 as substrate).
- **Headline**: First QD search over typed council compositions with verifier-derived behavioural descriptors. T8 (coverage), T9 (Pareto domination), T10 (robustness).
- **Empirics**: ARC-AGI-2 (verified submission to ARC Prize 2026) + FrontierMath Tier 4 + LiveCodeBench (head-to-head TRINITY) + SWE-bench Pro.
- **Target**: NeurIPS 2026 main (May 2026 abstract / paper). The biggest empirical headline.
- **Backup**: ICLR 2027 (Sep/Oct 2026). GECCO 2027 (Jan-Feb 2027) — for the QD-theory side.

#### P4 — Co-evolutionary Red/Blue Teaming of Deliberating Councils

- **Layers**: L5 with the red-team archive + L1 monitors.
- **Headline**: Symmetric Pareto co-evolution of attack and defence over typed councils. T11 (convergence properties).
- **Empirics**: Putnam-AXIOM Variation + GAIA + a custom adversarial-injection benchmark from MAST traces (Cemri NeurIPS 2025 D&B `2503.13657`).
- **Target**: AAMAS 2027 companion paper.
- **Backup**: ICLR 2027 (Sep/Oct 2026). NeurIPS 2026 main as a "robustness" paper.

#### P5 — Inductive Discovery of Multi-Agent Dialogue Protocols

- **Layers**: L6 (with L0 + L1).
- **Headline**: ILP from labelled deliberation traces, learned protocols re-verified by MCMAS. T12 (soundness), T13 (generalisation).
- **Empirics**: Show that protocol rules learned from one benchmark transfer to another (within domain), with verified guarantees. Compare against PSALM (Zhu 2024) and LASP (Chen 2024) — single-agent ILP-from-traces precedents.
- **Target**: KR 2026 (May 2026). NeSy 2026 main (June 2026).
- **Backup**: ILP 2026 / 2027.

#### F — CouncilAgent‑NS: A Neuro-Symbolic Multi-Agent LLM Council Framework

- **All layers integrated.**
- **Long-form, ~25 pages**: full architecture, all 13 theorems, complete benchmark sweep, software-artefact paper character.
- **Target**: JAIR or AIJ flagship (rolling submission).
- **Companion**: NeSy 2027 keynote / tutorial paper.

### 11.2 2026 / 2027 deadlines (realistic)

The realistic-window deadlines (some are estimated based on the venue's typical schedule; verify when planning):

| Venue | Typical deadline | What you submit |
|---|---|---|
| **NeSy 2026** main | June 2026 | P1 short, then P5 in the second window |
| **NeurIPS 2026** main | May 2026 | **P3** (highest-novelty headline) |
| **NeurIPS 2026** D&B | Jun 2026 | P2 (benchmark + argumentation aggregator) |
| **KR 2026** | May/Jun 2026 | P5 (ILP from traces) |
| **ICLR 2027** | Sep/Oct 2026 | P3 retry / P4 |
| **AAMAS 2027** | Oct 2026 abstracts | **P1** main + **P4** companion |
| **AAAI 2027** | Aug 2026 | **P2** (argumentation aggregator) |
| **GECCO 2027** | Jan/Feb 2027 | P3 with QD-theory results |
| **JAIR / AIJ** | Rolling | **F** flagship, target ~Apr 2027 |

### 11.3 Risk-stratified order

The ordering optimises for **early validation** and **scoop-resistance**:

1. **First (May 2026): P3 (NeurIPS main).** Highest novelty, freshest, most empirics-friendly. If the typed-protocol substrate (L0) is in place by April-May 2026, this is the realistic shot.
2. **Second (June 2026): P1 (NeSy 2026 main).** L1 verification spine; the theoretically-cleanest contribution. Also cheap to ship as a NeSy 2026 short paper if main slots are tight.
3. **Third (June 2026): P2 (NeurIPS D&B) or P5 (KR / ILP).** Depending on which layer matures first.
4. **Fourth (Aug-Oct 2026): the AAMAS 2027 + AAAI 2027 push.** P1 main + P2 main + P4 companion.
5. **Fifth (Apr 2027): F flagship to JAIR.** Subsumes everything.

---

## 12. 12-month execution roadmap

Dates assume an **April 28 2026 start**. Milestones are concrete, deliverable-oriented, and tied to publication windows.

### Month 1 (May 2026): Substrate

- **W1-2:** Branch `legacy/v0.1`. Create `councilagent-ns` repo. Port `pyproject.toml`, `.claude/`, ruff/mypy strict on *all* of `council_ns/`. Hydra config skeleton.
- **W3:** L0 — `dialect/moves.py` + `dialect/trace.py` + `DeliberationAutomaton`. Walton-Krabbe types, JSON-schema parser, surface-rendering. Acceptance test: a 3-agent peer-review trace round-trips through `Move` ADT and back to natural-language prompts losslessly.
- **W4:** Port the legacy `run_council()` to `run_council_ns(trace)` operating on Moves. Port topologies, normalizer, ranker. Acceptance: GSM8K (legacy task profile) runs end-to-end on `Move`-typed traces with parity to legacy accuracy ± 1 pp.

**Milestone M1:** typed substrate complete, GSM8K parity demonstrated. **Submit a NeSy 2026 short paper on the substrate** (June deadline) — even if rejected, it's a citable preprint.

### Months 2-3 (June-July 2026): L1 + L2

- **W5-6:** L1 — LTL_f AST + parser; SPOT bindings; LTL3 monitor (Bauer-Leucker-Schallhart). Initial property library (8 named properties from §6.2). Acceptance: each property has a positive and a negative test trace.
- **W7:** L1 — ISPL encoder for MCMAS; offline check on a 4-agent / 4-round example; T1, T2, T3 proofs drafted.
- **W8:** L2 — `BAF/QBAF` data structures + DF-QuAD; `build_qbaf(trace)`. Acceptance: deterministic output for the canonical Walton-Krabbe example.
- **W9-10:** L2 — `ArgumentationAggregator`; T4–T7 drafted. Mermaid + GraphViz visualisers.
- **W11-12:** Empirical run #1: P1 demo on Putnam-AXIOM Variation + ZebraLogic-hard. P2 demo on HLE.

**Milestone M2:** P1 + P2 ready to submit.

- **NeurIPS 2026 main paper deadline (~late May)**: skip if substrate finishes mid-May; aim for D&B (Jun) instead.
- **NeSy 2026 main (Jun)**: submit P1.
- **AAMAS 2027 abstract (Oct)**: target P1 main with NeSy-2026 feedback incorporated.

### Months 4-5 (August-September 2026): L3 + L4 + L5

- **W13:** L3 — JSD-based confidence; MUSE; per-domain calibration. Acceptance: ECE on GSM8K + MMLU drops below 0.05 (vs. legacy plurality fraction ~0.20).
- **W14:** L4 — In-context distillation cascade; multi-tier router; budget tracker.
- **W15-17:** L5 — Genome dataclass; pyribs CMA-MAE wrapper; LLM-mutation emitters (GEPA-style + AlphaEvolve-style). Initial QD run on GSM8K.
- **W18:** L5 — Behavioural descriptors derived from L1+L2 outputs. Empirical run #2: ARC-AGI-2 small-N.
- **W19-20:** L5 — full evaluate-loop wired; first verified ARC Prize submission.

**Milestone M3:** L5 working end-to-end; first verified ARC-AGI-2 submission; P3 draft ready.

- **ICLR 2027 deadline (Sep/Oct)**: submit P3.
- **AAMAS 2027 abstracts (Oct)**: submit P1 + P4.

### Months 6-8 (October-December 2026): co-evolution + scaling

- **W21-22:** Red-team archive (Rainbow-Teaming-style); co-evolutionary loop.
- **W23-24:** Scale L5 to all Tier-A benchmarks. Cost-Pareto comparisons against TRINITY/MoA.
- **W25-26:** P4 draft on co-evolution.
- **W27-28:** P3 / P4 camera-ready; benchmark ledger frozen for the next round.

**Milestone M4:** P3 + P4 in submission.

### Months 9-10 (January-February 2027): L6 + flagship integration

- **W29-30:** L6 — ASP integrity-constraint enforcement; clingo wrapper. Acceptance: VirtualHome-style executability lift demonstrated (CLMASP-replication).
- **W31-32:** L6 — Popper integration; ILP from labelled traces; rule-to-automaton extraction; MCMAS verification of induced rules.
- **W33-36:** P5 draft. Flagship F draft begins.

**Milestone M5:** P5 ready; F first draft.

- **AAAI 2027 deadline (Aug 2026 — already past). **Backup**: IJCAI 2027 (Jan) for P2.

### Months 11-12 (March-April 2027): flagship + viral demos

- **W37-40:** F flagship paper; complete benchmark ledger; all 13 theorems written up; reproduction recipes in `experiments/reproduce/` for every paper.
- **W41-44:** Streamlit demo; live LTL_f monitor; Mermaid BAF visualiser; one-click ARC-AGI-2 runner; demo video.

**Milestone M6:** F submitted to JAIR. Streamlit demo live. Repo at v1.0.0.

### Workshop checkpoints (your insurance policy)

Always have a workshop submission in flight:
- NeSy 2026 workshop (Jun 2026) — substrate paper
- AAAI 2027 agent workshops (Aug 2026)
- ICLR 2027 NeSy workshop (Sep 2026)
- GECCO 2027 LLM track (Feb 2027)
- ICML 2027 NeSy workshop (Apr 2027)

Every layer should appear in a workshop *before* its main-venue submission. Workshops give you reviewer feedback and citable preprints without the rejection sting of a main-venue miss.

---

## 13. Repo strategy for stars and adoption

The technical content is what makes the paper. The *positioning* is what makes the repo go viral.

### 13.1 The README contract

Top of `README.md`, in this order:

1. **One-liner**: *"The first multi-LLM council you can model-check."*
2. **GIF or short video** (≤ 30 s) showing the live LTL_f monitor catching a sycophancy collapse mid-debate, redirecting to a devil's advocate, and producing a verified verdict — Mermaid BAF rendering live.
3. **Three-line value prop**:
   - *"Drop-in `complete(prompt) → response` replacement for any LLM call."*
   - *"Confidence is a measured Jensen-Shannon margin, not a self-report."*
   - *"Every answer ships with a Provenance Receipt: typed Trace, argumentation graph, monitor verdicts, cost ledger."*
4. **Code in 10 lines** (the hello-world):
   ```python
   from council_ns import CouncilAgent
   agent = CouncilAgent.from_yaml("configs/verified-fast.yaml")
   resp = await agent.complete("What's the smallest prime > 100?")
   print(resp.answer)               # "101"
   print(resp.confidence)           # 0.93 — JSD margin
   print(resp.receipt.monitors)     # {"NoPrematureConsensus": ⊤, ...}
   print(resp.receipt.baf_mermaid)  # → live rendered argument graph
   ```
5. **Headline benchmark numbers** with verified-leaderboard badges (ARC Prize verification stamp is the single biggest credibility multiplier).
6. **Five-architectures diagram** (the L0–L6 stack from §5.2).
7. **Quickstart**, then **paper links**, then **citation**, then **license**.

### 13.2 The hosted demos

These are the artefacts that drive stars:

1. **`council-ns.dev` Streamlit space** — paste an ARC-AGI-2 task or a math problem; watch the council deliberate live with the Mermaid BAF + LTL_f monitor on the right panel.
2. **One-click ARC-AGI-2 runner** — a Colab notebook that runs the verified-leaderboard genome on a user-supplied task, produces a Provenance Receipt PDF.
3. **30-second demo video** — sycophancy-cascade scenario, monitor catches it, intervention fires, verdict produced.

### 13.3 The PyPI / packaging plan

- **Reserve `councilagent-ns` and `council-ns` on PyPI today** (free).
- **Package as `councilagent-ns`** with optional extras: `[verify]` (spot, mcmas-py), `[argue]` (no extra deps, pure Python), `[evolve]` (pyribs, cma), `[ilp]` (clingo, popper-bin), `[full]` (everything).
- **Match the AutoGen / LangGraph / CrewAI API surface** as a thin adapter (`council_ns/adapters/langgraph.py`) so migration is a one-day task.

### 13.4 The community plan

- **Apache-2.0** license (NeSy norm; permissive enough for industry adoption).
- **CITATION.cff** auto-generated, Zenodo-hooked.
- **CONTRIBUTING.md** with a clear "add a new ProtocolAutomaton in 50 LOC" example.
- **One Discord / Discussions board** for issues and PR triage.
- **An `awesome-council-ns` companion repo** — curated list of property formulae, learned protocols, calibrators, descriptors. Community-extensible.

### 13.5 The tagline polish

- Primary: *"The first multi-LLM council you can model-check."*
- Secondary: *"Drop-in LLM with calibrated confidence and provenance receipts."*
- Tertiary (for academic posters): *"A neuro-symbolic stack for verifiable, argumentative, evolved multi-LLM deliberation."*

The first one is the viral one. The second one is what convinces engineers to install it. The third one is what convinces reviewers to accept it.

---

## 14. Risks, threats and counterfactuals

A clear-eyed list. Each risk has a mitigation.

### 14.1 Scientific risks

| Risk | Mitigation |
|---|---|
| **"MAD doesn't beat strong CoT-SC under matched compute" reviewer pushback.** Reviewers cite Smit ICML 2024 / "Stop overvaluing MAD" / "Single-Agent vs MAS Under Equal Thinking-Token Budgets" and reject. | The ablation matrix (§9.3) isolates the contribution of *each symbolic layer* to attributable gain. The headline claim is not "more agents"; it is "verified + argumentative + evolved councils". **Always report cost-matched comparisons in every table.** |
| **MCMAS scales to ~6 agents / bounded-recall semantics, not 1000.** | Use bounded-recall semantics (MCMAS-BR, AAAI 2020); for online enforcement rely on LTL_f runtime monitors (LTL3, SPOT) that scale to arbitrary trace length. Frame model-checking as offline protocol validation; runtime monitor is the production-deployable mechanism. |
| **ArgLLMs / MArgE / DCI scoop the argumentation aggregator.** | Differentiator: ours operates over a *typed-protocol-enforced* graph (no LLM extraction), and fuses with the verification layer (strategic gradual semantics, T7). Move fast on P2; submit AAAI 2027 even if NeurIPS 2026 D&B is delayed. |
| **TRINITY-Conductor-MaAS-AFlow-AgentSquare-SwarmAgentic-EvoFlow scoop the QD layer.** | Your descriptors come from L1+L2 — *verifier-derived*, not LLM-tagged. EvoFlow is niching for workflows; SwarmAgentic is PSO single-objective; MaAS is continuous-distribution without an archive; AgentSquare is greedy modular search. None evolves *typed protocols* with verification-derived behavioural descriptors. Move fast on P3. |
| **Benchmark contamination (Berkeley RDI 2026; OpenAI Dec 2025 audit).** | Prioritise SWE-bench Pro, FrontierMath Tier 4, ARC-AGI-2 semi-private, MathArena live competitions, Putnam-AXIOM Variation. Publish your eval harness; pre-empt the dominant 2026 critique. |
| **The typed-protocol refactor takes longer than expected and you ship empirics before theory.** | Publish L0 (the typed protocol substrate) as a NeSy 2026 short paper or a SoftwareX tooling paper, decoupling the engineering risk from the publication path. The DOCX's H1–H10 hypothesis tests still run on the substrate alone. |
| **The QD genome space is too large — CMA-MAE doesn't converge in budget.** | Stage the search: first illuminate over `(monitors × aggregator)` only with a fixed pool of 3 agents; then expand to topology and protocol; then to members. Each stage delivers a citable result; running the full QD on day one is not necessary. |
| **A specific LTL_f property turns out to be unsatisfiable for any practical council.** | Bauer et al. show 44 % of LTL formulae in their experiments are non-monotonic; not every property is monitorable. The library in §6.2 is a starting point — empirical experiments determine which properties are genuinely useful. Document the negative results; they are themselves publishable (DOCX-style "modality sabotage" framing). |

### 14.2 Engineering risks

| Risk | Mitigation |
|---|---|
| **Branch-and-rebuild costs ~3-4 months of substrate work before any new empirics.** | The ablation matrix shows that even L0 alone (typed Trace, no symbolic) is publishable as a substrate paper. Plan for incremental wins. |
| **SPOT / MCMAS / clingo / Popper are C/C++ binaries — installation friction.** | Ship them as optional extras (`[verify]`, `[ilp]`); test the no-extras path always works. Fall back to pure-Python `ltl2mon` for LTL3 monitors when SPOT is unavailable. |
| **LiteLLM provider quirks (some models don't honour `response_format`).** | Provide a layered structured-output enforcer: JSON-schema-in-prompt → `response_format` → grammar-constrained-decoding (Outlines) → argument-mining fallback. Mark the tier in the ProvenanceReceipt. |
| **Cost: a full QD run on ARC-AGI-2 + FrontierMath Tier 4 + LiveCodeBench could exceed $20K.** | Use the cascade (L4) aggressively; the open-source-tier proposers + frontier-tier verifier pattern keeps ~80 % of cost on the cheap tier. Apply for ARC Prize compute credits / Anthropic / OpenAI research grants. |

### 14.3 Adoption risks

| Risk | Mitigation |
|---|---|
| **NeSy is a niche; the audience is smaller than mainstream ML.** | The "model-check your LLM debate" framing is broadly intelligible. The ARC Prize 2026 verified-leaderboard stamp is a credibility multiplier across communities. The Streamlit demo is the viral lever. |
| **Engineers don't want to write LTL_f formulae.** | Ship a default property library (the 8–10 named properties); 95 % of users never write their own. Power-users have a clean DSL when they need it. |
| **The QD layer is research-grade; users want production stability.** | Two entry points: `CouncilAgent.from_yaml("configs/verified-fast.yaml")` is *production-ready* (single hand-tuned genome from the QD archive); the QD evolution is opt-in via `experiments/evolve.py`. |

---

## 15. Two-week kickoff checklist

In priority order, what to do in the next 14 days.

### Week 1

1. **[Day 1]** Decide branching: tag `legacy/v0.1` on the current `main`. Create the `councilagent-ns` directory in the same repo (mono-repo) or a sibling repo. **My recommendation: same repo, new top-level `council_ns/` directory.** Keeps the deep-review and DOCX in one place, makes ablation against legacy trivial.
2. **[Day 1]** Reserve `councilagent-ns` on PyPI; add `CITATION.cff`; switch LICENSE to Apache-2.0.
3. **[Day 2]** Update the README to: tagline "The first multi-LLM council you can model-check.", placeholder demo GIF slot, three-line value prop, and a TODO for §13's structure. **Do this even before any new code lands** — sets the tone for the next year of contributors.
4. **[Day 3]** Sketch `council_ns/dialect/moves.py` — the Move ADT + Claim. ≤ 200 LOC. Open a PR; don't merge until day 7 to invite review.
5. **[Day 4]** Sketch `council_ns/dialect/trace.py` and `council_ns/dialect/protocols/base.py` — the ProtocolAutomaton ABC. ≤ 150 LOC.
6. **[Day 5]** Read the SPOT Python bindings (`pip install spot`) and ltl2mon documentation. Pick the LTL3 path. Spike a 100-LOC monitor that consumes a hand-crafted Trace and returns ⊤/⊥/?.
7. **[Day 6]** Read Freedman-Toni AAAI 2025 (`2405.02079`) and Baroni-Rago-Toni 2019 in detail. Sketch `council_ns/symbolic/argue/baf.py` + a stub `DFQuADSemantics`.
8. **[Day 7]** Merge the L0 PR. Write 30 tests against the Move ADT + Trace.

### Week 2

9. **[Day 8-9]** Port `_build_visibility_context` and `run_council` to `run_council_ns` operating on Moves. Use the legacy `PeerReviewProtocol` as the first concrete `ProtocolAutomaton`. Acceptance: GSM8K end-to-end on Move-typed traces with parity to legacy ± 1 pp.
10. **[Day 10]** Implement `council_ns/symbolic/verify/properties.py` with the 4 simplest LTL_f properties: `EventuallyDecide`, `BoundedRound`, `ProvenanceCompleteness`, `NoMonotoneAgreementCollapse`. Wire `LTLfMonitorTermination` to `CompositeTermination`.
11. **[Day 11]** Acceptance test: run a 3-agent peer-review on GSM8K with the monitor active; produce a Provenance Receipt JSON with the typed Trace + the 4 monitor verdicts.
12. **[Day 12]** Sketch the Streamlit demo skeleton (`apps/streamlit_demo.py`) — even a static one with a hand-crafted trace and Mermaid BAF rendering. **This is the viral artefact**; start it early.
13. **[Day 13]** Email Lomuscio's group at Imperial about MCMAS-BR Python bindings (or just allocate a 1-day spike to subprocess-call MCMAS via its CLI). Read the MCMAS STTT 2017 paper end-to-end.
14. **[Day 14]** Apply for ARC Prize 2026 access. Write a 1-page roadmap commitment based on this document; pin it as `ROADMAP.md` in the repo.

After these two weeks, you have:
- A typed substrate ✓
- A first runtime monitor producing verdicts on real GSM8K runs ✓
- A first Provenance Receipt format ✓
- A Streamlit demo skeleton ✓
- ARC Prize 2026 access requested ✓
- A well-positioned README + roadmap ✓

That is the minimum viable starting point. Everything else in the 12-month roadmap (§12) builds on it.

---

## 16. References

References that the plan above cites or relies on, grouped by topic. Where a 2026 paper has both an arXiv preprint and a venue, the venue is given. Where I am uncertain about a venue, I say "preprint". I have **not** invented papers; where I was uncertain after one search, I marked the entry "(verify before citing)".

### 16.1 Multi-agent LLM debate / orchestration

- Du, Y., Li, S., Torralba, A., Tenenbaum, J. B., & Mordatch, I. (2024). Improving Factuality and Reasoning in Language Models through Multiagent Debate. *ICML 2024*. arXiv:2305.14325.
- Liang, T., et al. (2024). Encouraging Divergent Thinking in Large Language Models through Multi-Agent Debate. *EMNLP 2024*. arXiv:2305.19118.
- Wang, J., et al. (2024). Mixture-of-Agents Enhances Large Language Model Capabilities. *ICLR 2025 spotlight*. arXiv:2406.04692.
- Li, J., et al. (2025). Self-MoA: Rethinking Mixture-of-Agents — Is Mixing Different Large Language Models Beneficial? *ICLR 2025*. arXiv:2502.00674.
- Khan, A., et al. (2024). Debating with More Persuasive LLMs Leads to More Truthful Answers. *ICML 2024 Best Paper*. arXiv:2402.06782.
- Smit, J., et al. (2024). Should we be going MAD? — Reliability of LLM-as-a-Judge in Multi-Agent Debate. *ICML 2024*. arXiv:2311.17371.
- Wang, Q., et al. (2024). Rethinking the Bounds of LLM Reasoning: Are Multi-Agent Discussions the Key? *ACL 2024*. arXiv:2402.18272.
- Cemri, F., et al. (2025). Why Do Multi-Agent LLM Systems Fail? — The MAST Taxonomy. *NeurIPS 2025 D&B*. arXiv:2503.13657.
- "Stop Overvaluing MAD: An Empirical Study of Multi-Agent Debate". (2025). Preprint. arXiv:2502.08788.
- "Debate or Vote: Which Yields Better Decisions in Multi-Agent Large Language Models?". (2025). Preprint. arXiv:2508.17536.
- "Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent Debate". (2025). Preprint. arXiv:2509.05396.
- Estornell, A., & Liu, Y. (2024). Multi-LLM Debate: Framework, Principals, and Interventions. *NeurIPS 2024*.
- Sakana AI. (2026). TRINITY: An Evolved LLM Coordinator. *ICLR 2026*. arXiv:2512.04695v2.
- Sakana AI. (2026). Conductor: Learning to Orchestrate Agents in Natural Language. arXiv:2512.04388.
- Karpathy, A. (2025). llm-council. https://github.com/karpathy/llm-council.

### 16.2 Calibration and disagreement

- *(MUSE — verify exact citation before citing)*: "Simple Yet Effective: An Information-Theoretic Approach to Multi-LLM Uncertainty Quantification". PMC12702469.
- *(ConFreeze — verify before citing)*: OpenReview submission `PrqXuAS4BZ`. (Not yet third-party verified.)
- *(Privileged Knowledge — verify)*: "Masked by Consensus: Disentangling Privileged Knowledge in LLM Correctness". arXiv:2604.12373v4.
- "SycEval: Evaluating LLM Sycophancy". (2025). arXiv:2502.08177.
- "ELEPHANT: Measuring and Understanding Social Sycophancy in LLMs". (2025). arXiv:2505.13995.
- Ai et al. (2025). Beyond Majority Voting: LLM Aggregation by Leveraging Higher-Order Information. arXiv:2510.01499.
- Wataoka, K., et al. (2024). Self-Preference Bias in LLM-as-a-Judge. arXiv:2410.21819.
- Zheng, L., et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. *NeurIPS 2023*. arXiv:2306.05685.

### 16.3 Argumentation

- Dung, P. M. (1995). On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games. *Artificial Intelligence* 77(2):321–357.
- Cayrol, C., & Lagasquie-Schiex, M. C. (2005). Bipolar Abstract Argumentation Frameworks. *ECSQARU 2005*.
- Baroni, P., Rago, A., & Toni, F. (2018). How Many Properties Do We Need for Gradual Argumentation? *AAAI 2018*.
- Baroni, P., Rago, A., & Toni, F. (2019). From fine-grained properties to broad principles for gradual argumentation: A principled spectrum. *International Journal of Approximate Reasoning* 105:252–286.
- Rago, A., Toni, F., Aurisicchio, M., & Baroni, P. (2016). Discontinuity-Free Decision Support with Quantitative Argumentation Debates (DF-QuAD). *KR 2016*, 63–73.
- Amgoud, L., & Ben-Naim, J. (2017). Evaluation of arguments in weighted bipolar graphs. *ECSQARU 2017*.
- Potyka, N. (2018). Continuous dynamical systems for weighted bipolar argumentation. *KR 2018*.
- Freedman, G., Dejl, A., Gorur, D., Yin, X., Rago, A., & Toni, F. (2025). Argumentative Large Language Models for Explainable and Contestable Claim Verification. *AAAI 2025* 39(14):14930–14939. arXiv:2405.02079.
- Ng, M.-P., Jiang, J., Freedman, G., Rago, A., & Toni, F. (2025). MArgE: Meshing Argumentative Evidence from Multiple Large Language Models for Justifiable Claim Verification. arXiv:2508.02584.
- Sanayei et al. (2025). Can LLMs Judge Debates? Evaluating Non-Linear Reasoning via Argumentation Theory Semantics. *EMNLP 2025 Findings*. arXiv:2509.15739.
- Gorur, D., Rago, A., & Toni, F. (2024). Can Large Language Models Perform Relation-Based Argument Mining? arXiv:2402.11243.

### 16.4 Verification and model-checking

- Pnueli, A. (1977). The Temporal Logic of Programs. *FOCS 1977*.
- Clarke, E. M., & Emerson, E. A. (1981). Design and synthesis of synchronization skeletons using branching time temporal logic. *Logics of Programs*.
- Alur, R., Henzinger, T. A., & Kupferman, O. (2002). Alternating-Time Temporal Logic. *Journal of the ACM* 49(5):672–713.
- Fagin, R., Halpern, J. Y., Moses, Y., & Vardi, M. Y. (1995). *Reasoning About Knowledge*. MIT Press.
- Bauer, A., Leucker, M., & Schallhart, C. (2011). Runtime verification for LTL and TLTL. *ACM TOSEM*.
- De Giacomo, G., De Masellis, R., Grasso, M., Maggi, F., & Montali, M. (2014). LTL_f and LDL_f Monitoring: A Technical Report. arXiv:1405.0054.
- De Giacomo, G., & Vardi, M. Y. (2013). Linear Temporal Logic and Linear Dynamic Logic on Finite Traces. *IJCAI 2013*.
- Lomuscio, A., Qu, H., & Raimondi, F. (2009 / 2017). MCMAS: an open-source model checker for the verification of multi-agent systems. *CAV 2009* / *STTT* 19(1):9–30.
- Cermák, P., Lomuscio, A., Mogavero, F., & Murano, A. (2014). MCMAS-SLK: a model checker for the verification of strategy logic specifications. *CAV 2014*.
- *(MCMAS-BR — verify exact citation)*: Lomuscio et al. AAAI 2020. Bounded-recall semantics.
- Duret-Lutz, A., et al. (2016/ongoing). SPOT: a platform for LTL and ω-automata manipulation. https://spot.lre.epita.fr/.
- Kambhampati, S., et al. (2024). LLMs Can't Plan, But Can Help Planning in LLM-Modulo Frameworks. *ICML 2024 position*. arXiv:2402.01817.
- Wang, Z., Poskitt, C. M., & Sun, J. (2026). AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents. *ICSE 2026*. arXiv:2503.18666.

### 16.5 Evolutionary / Quality-Diversity

- Mouret, J.-B., & Clune, J. (2015). Illuminating Search Spaces by Mapping Elites. arXiv:1504.04909.
- Fontaine, M. C., Togelius, J., Nikolaidis, S., & Hoover, A. K. (2020). Covariance Matrix Adaptation for the Rapid Illumination of Behavior Space (CMA-ME). *GECCO 2020*. arXiv:1912.02400.
- Fontaine, M. C., & Nikolaidis, S. (2023). Covariance Matrix Adaptation MAP-Annealing (CMA-MAE). *GECCO 2023*. arXiv:2205.10752.
- Tjanaka, B., et al. (2023). pyribs: A Bare-Bones Python Library for Quality Diversity Optimization. *GECCO 2023*.
- Lehman, J., et al. (2022). Evolution Through Large Models. arXiv:2206.08896.
- Romera-Paredes, B., et al. (2024). Mathematical discoveries from program search with large language models (FunSearch). *Nature*.
- Novikov, A., et al. (2025). AlphaEvolve: A Coding Agent for Scientific and Algorithmic Discovery. arXiv:2506.13131.
- Agrawal, A., et al. (2026). GEPA: Reflective Pareto-Genetic Prompt Optimisation. *ICLR 2026 oral*. arXiv:2507.19457.
- Bradley, H., et al. (2024). QDAIF: Quality-Diversity through AI Feedback. *ICLR 2024*. arXiv:2310.13032.
- Samvelyan, M., et al. (2024). Rainbow Teaming: Open-Ended Generation of Diverse Adversarial Prompts. *NeurIPS 2024*. arXiv:2402.16822.
- Samvelyan, M., et al. (2024). MADRID: Quality-Diversity for Multi-Agent Reinforcement Learning Diagnostics. *AAMAS 2024 oral*. arXiv:2401.13460.
- Hu, S., Lu, S., & Clune, J. (2025). Automated Design of Agentic Systems (ADAS). *ICLR 2025*. arXiv:2408.08435.
- Zhang, Y., et al. (2025). AFlow: Automating Agentic Workflow Generation. *ICLR 2025 oral*. arXiv:2410.10762.
- Shang, Y., et al. (2025). AgentSquare: Automatic LLM Agent Search in Modular Design Space. *ICLR 2025*. arXiv:2410.06153.
- Zhang, X., et al. (2025). Multi-agent Architecture Search via Agentic Supernet (MaAS). *ICML 2025 oral*. arXiv:2502.04180.
- (2025). SwarmAgentic: Towards Fully Automated Agentic System Generation via Swarm Intelligence. arXiv:2506.15672.
- Qian, C., Xue, K., Wang, X., Filipič, B., & Ochoa, G. (2025). QD Algorithms Can Provably Be Helpful for Optimization. *GECCO 2025*.

### 16.6 NeSy and ILP

- Manhaeve, R., Dumančić, S., Kimmig, A., Demeester, T., & De Raedt, L. (2021). DeepProbLog. *Artificial Intelligence Journal*.
- Cropper, A., & Morel, R. (2020/2021). Learning programs by learning from failures (Popper). *Machine Learning* 110.
- Law, M., Russo, A., & Broda, K. (various). ILASP / ILASP3 / ILASP4.
- Pan, L., Albalak, A., Wang, X., & Wang, W. Y. (2023). Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning. *EMNLP 2023*. arXiv:2305.12295.
- Olausson, T., et al. (2023). LINC: A Neurosymbolic Approach for Logical Reasoning by Combining Language Models with First-Order Logic Provers. *EMNLP 2023*. arXiv:2310.15164.
- Ye, X., et al. (2023). SatLM: Satisfiability-Aided Language Models Using Declarative Prompting. *NeurIPS 2023*. arXiv:2305.09656.
- Yang, Z., Ishay, A., & Lee, J. (2023). Coupling Large Language Models with Logic Programming for Robust and General Reasoning from Text. arXiv:2307.07696.
- *(CLMASP — verify exact citation)*: arXiv:2406.03367. Lifting LLM-generated plan executability via ASP.
- *(PSALM, LASP — verify before citing)*: ILP from agent traces, 2024 single-agent precedents.

### 16.7 Benchmarks

- ARC Prize. (2025–2026). ARC-AGI-2 Leaderboard. https://arcprize.org/leaderboard. (Verified: Poetiq + Gemini 3 Pro 54 % at $30.57/task, Dec 2025.)
- Epoch AI. (2025–2026). FrontierMath / FrontierMath Tier 4. https://epoch.ai/frontiermath.
- Jain, N., et al. (2024). LiveCodeBench. (Trinity SOTA 86.2 % pass@1, ICLR 2026.)
- Mialon, G., et al. (2023). GAIA: A Benchmark for General AI Assistants. arXiv:2311.12983.
- Phan, V., et al. (2026). Humanity's Last Exam (HLE). *Nature*.
- Scale AI. (2026). SWE-bench Pro.
- Yao, S., et al. (2024). τ-bench / τ²-bench.
- Zhou, S., et al. (2024). WebArena. arXiv:2307.13854.
- Lin, B., et al. (2025). ZebraLogic.
- Gulati, A., et al. (2025). Putnam-AXIOM.

### 16.8 Critical methodological work the paper must cite

- Wang, X., et al. (2023). Self-Consistency Improves Chain-of-Thought Reasoning in Language Models. *ICLR 2023*.
- Madaan, A., et al. (2023). Self-Refine. *NeurIPS 2023*. arXiv:2303.17651.
- Shinn, N., et al. (2023). Reflexion. *NeurIPS 2023*.
- Yao, S., et al. (2023). Tree of Thoughts. *NeurIPS 2023*. arXiv:2305.10601.
- Yao, S., et al. (2023). ReAct. *ICLR 2023*.
- Walton, D. N., & Krabbe, E. C. W. (1995). *Commitment in Dialogue*. SUNY Press.
- Atkinson, K., Bench-Capon, T., & Walton, D. (2013). Distinctive features of persuasion and deliberation dialogues.
- McBurney, P., Hitchcock, D., & Parsons, S. (2007). The eight-fold way of deliberation dialogue. *International Journal of Intelligent Systems*.

---

*End of plan. Total length: approximately 21K words. Status: complete and self-contained; ready to be used as the kickoff document for `councilagent-ns`. Every claim is grounded against the actual repository state, the actual DOCX, or a verified literature source.*

