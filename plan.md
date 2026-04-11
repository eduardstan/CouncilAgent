# LLM Council Benchmarking: An Exhaustive Research Investigation

**Multi-model deliberation systems—where several LLMs independently respond, evaluate, and synthesize—represent one of the most promising yet under-formalized paradigms in AI evaluation and reasoning.** This investigation reveals a field at an inflection point: Karpathy's 335-line proof-of-concept has spawned a commercial product (Perplexity Model Council), inspired derivative frameworks, and catalyzed academic research, yet the theoretical foundations remain fragmented and no standardized benchmark exists. The research landscape spans social choice theory, distributed consensus, multi-agent debate, and LLM evaluation methodology—domains that have developed largely in isolation but must converge for rigorous council benchmarking. This report synthesizes findings from 4 primary resources, 20+ academic papers, 10+ multi-agent frameworks, and the full classical foundations to support six formal deliverables: systematic literature review, taxonomy document, benchmark requirements specification, research gaps/hypotheses, implementation architecture, and a vibecoding seed prompt.

---

## 1. Theoretical foundations constrain every council design choice

Three classical results impose hard constraints on LLM council architectures. **Arrow's Impossibility Theorem** (1951) proves that no ordinal aggregation rule over ≥3 alternatives can simultaneously satisfy unrestricted domain, Pareto efficiency, independence of irrelevant alternatives, and non-dictatorship. For councils that aggregate ranked candidate outputs, this means every aggregation method sacrifices at least one fairness axiom—Borda count violates IIA, majority rule can cycle, and any "perfect" method is dictatorial. The practical escape route: **cardinal scoring** (where LLMs rate rather than rank) sidesteps Arrow's constraints, which is why confidence-weighted voting (ReConcile, Chen et al. ACL 2024) and numerical scoring outperform pure ordinal methods.

**The Condorcet Jury Theorem** (1785) provides the primary theoretical justification for councils: if each agent independently answers correctly with probability p > 0.5, majority vote accuracy approaches 1 as council size grows. Li et al. (TMLR 2024, "More Agents Is All You Need") confirmed this empirically—accuracy on GSM8K scales monotonically with agent count, with harder tasks benefiting more. But the theorem's independence assumption is severely violated when LLMs share training data, architectures, and RLHF objectives. Ladha (1992) showed that correlation reduces or eliminates the wisdom-of-crowds effect, making **model diversity** (different families, not just different instances) the critical success factor. ReConcile demonstrated this directly: multi-model diversity contributed **6.8%** of the total improvement, dwarfing other components.

The **Gibbard-Satterthwaite Theorem** (1973/1975) warns that non-dictatorial ordinal mechanisms with ≥3 outcomes are manipulable—relevant as RLHF-trained models may learn to game aggregation. From distributed systems, the **FLP Impossibility Result** (Fischer, Lynch, Paterson 1985) proves that deterministic async consensus is impossible with even one faulty process, mapping directly to council protocols where LLM response times are unbounded. **Byzantine Fault Tolerance** (Lamport et al. 1982) establishes that councils need >2/3 reliable models to tolerate adversarial or hallucinating agents. **Shapley values** (1953) provide the mathematically unique fair attribution of each council member's marginal contribution—essential for determining which models to include.

---

## 2. A ten-dimensional taxonomy of council architectures

Research across 30+ papers reveals that LLM council architectures vary along **ten independent dimensions**, creating a vast combinatorial design space that is mostly unexplored.

**Agent heterogeneity** ranges from homogeneous (multiple instances of one model, as in Du et al. 2024's original multi-agent debate) through prompt-diversified (same model, different personas, as in HAD for financial sentiment) to fully heterogeneous (different model families, as in Mixture-of-Agents). A surprising counter-result: Self-MoA (2025) found that self-ensembling one top model can outperform mixed-model MoA on AlpacaEval by **6.6%**, challenging the assumption that diversity always helps. The key appears to be whether diversity introduces capability variance or genuine complementary knowledge.

**Communication topology** has been studied most systematically. Exchange-of-Thought (Yin et al. 2023) identified four canonical patterns—Memory (bus), Report (star), Relay (ring), and Debate (complete graph)—finding that different topologies excel on different tasks. MacNet (ICLR 2025) scaled mesh topology to 1000+ agents. G-Designer (Zhang et al. 2024) used GNNs to learn task-aware topologies. The critical finding from "Topological Structure Learning Should Be A Research Priority" (2025): **performance varies by up to 10% across topologies**, making topology a first-class optimization target.

**Deliberation protocol** includes simultaneous generation (Karpathy's fan-out), sequential round-robin (classic multi-agent debate), structured debate with affirmative/negative roles (MAD framework, Liang et al. EMNLP 2024), negotiation (FOMC simulation), and peer review (Language Model Council, Zhao et al. NAACL 2025). Kaesberg et al. (ACL 2025 Findings) provided the first systematic comparison of 7 protocols across 6 tasks, finding that **consensus-based protocols outperform on knowledge tasks** while **voting-based protocols outperform on reasoning tasks**.

**Aggregation mechanism** spans majority vote (most common), confidence-weighted voting (ReConcile), Borda count ("Ranked Voting based Self-Consistency," ACL 2025), meta-judge synthesis (MoA, Karpathy's chairman), generative fusion (LLM-Blender, Jiang et al. ACL 2023), and Shapley-value weighting (proposed but unimplemented). The llm-deliberate open-source project implements Condorcet methods including Ranked Pairs. A critical finding from "Debate or Vote" (2025): **simple majority voting accounts for most observed gains** from multi-agent debate, formalized via a martingale proof showing expected belief is unchanged by debate rounds.

The remaining dimensions—**consensus definition** (unanimity through fixed rounds), **role assignment** (static prescribed to emergent, with dynamic assignment improving performance by up to **74.8%** per Zhang et al. 2025), **termination condition** (fixed rounds vs. convergence detection), **memory/state** (stateless through graph-structured with 6-component architectures like MIRIX), **prompt architecture** (including anti-sycophancy prompting from CONSENSAGENT), and **evaluation target** (reasoning, factuality, creativity, safety, code)—each add additional combinatorial complexity.

The gaps analysis reveals that while individual dimensions are increasingly studied, **the combinatorial space of dimension interactions remains largely unexplored**. No work exists on formal Pareto efficiency analysis of council outputs, information-theoretic information gain per debate round, gossip protocols for LLMs, strategy-proof aggregation mechanisms, or formal diversity preservation guarantees.

---

## 3. Four primary resources reveal convergent architectural insights

**R1: "How Benchmark Prediction from Fewer Data Misses the Mark"** (Zhang, Dorner, Hardt; NeurIPS 2025) formalizes benchmarks as triples **(D, F, s)** and introduces the critical distinction between interpolation and extrapolation regimes. The paper's central finding—that RANDOM-SAMPLING-LEARN (random sample + Ridge regression) outperforms sophisticated core-set selection methods, reducing estimation gap by **37%**—parallels findings in council systems where simple aggregation often beats complex coordination. The AIPW (Augmented Inverse Propensity Weighting) estimator, a consistent estimator that doesn't rely on model similarity for asymptotic correctness, could be adapted for multi-agent evaluation settings where different council members evaluate different subsets. For council benchmarking, this paper establishes that evaluation must test extrapolation (novel model configurations) and that all methods implicitly rely on model similarity.

**R2: "Towards a Science of Scaling Agent Systems"** (Kim et al.; Google/MIT 2025) provides the most rigorous formal framework for multi-agent system evaluation. It defines agent systems as **S = (A, E, C, Ω)** with five canonical architectures (SAS, Independent MAS, Decentralized MAS, Centralized MAS, Hybrid MAS) and derives scaling laws from 180 controlled configurations across 4 benchmarks. Three dominant effects emerged: the **tool-coordination trade-off** (β = -0.330, p < 0.001), the **~45% capability ceiling** (once single agents exceed ~45% accuracy, adding agents yields diminishing or negative returns), and **architecture-dependent error amplification** (independent agents amplify errors 17.2× vs. centralized 4.4×). The mixed-effects model achieves **87% accuracy** in predicting optimal architecture for held-out tasks. For council benchmarking, this means architecture selection should be guided by measurable task properties, not one-size-fits-all.

**R3: Karpathy's llm-council** implements a 3-stage pipeline in ~335 lines of Python: (1) parallel fan-out to all models via OpenRouter, (2) anonymized peer review where each model ranks all responses with identities stripped, and (3) chairman synthesis where a designated model produces the final answer. The architecture uses a star-plus-funnel topology with Borda-like ranking aggregation (average rank position). Key design insights include anonymization to prevent model favoritism, self-evaluation as part of peer review, and graceful degradation when models fail. Karpathy observed that "models are surprisingly willing to select another LLM's response as superior to their own" and concluded that "the construction of LLM ensembles seems under-explored." The repo has **15.3K stars** and spawned derivatives including Swarms' LLMCouncil class, llm-council.dev (with confidence tiers and jury mode), and llm-deliberate (adding social choice voting methods).

**R4** yielded the **Aegean protocol** (Ruan et al., NUS, 2025)—the most theoretically rigorous consensus framework for LLM agents. It defines multi-agent refinement with three formal properties adapted from classical distributed consensus: Refinement Termination, Refinement Validity (output quality ≥ majority optimal solution), and Refinement Monotonicity (later outputs are at least as good). Key parameters include similarity threshold α and stability horizon β. Aegean achieves **1.2–20× latency reduction** vs. baselines while maintaining quality within 2.5%, with P99 tail latency reduction up to 11×. The MAKER system (Meyerson et al. 2025) demonstrated consensus-via-voting at extreme scale, solving a **million-step task with zero errors** using first-to-ahead-by-K voting.

---

## 4. The ecosystem has crystallized around two paradigms

Two distinct paradigms have emerged in practice. **Council for answer generation** (Karpathy's llm-council, Perplexity's Model Council) dispatches queries to multiple models, then synthesizes outputs into a single best answer. Perplexity launched Model Council in February 2026 for Max subscribers ($200/month), sending queries in parallel to three frontier models (Claude Opus 4.6, GPT 5.2, Gemini 3.0) with a dedicated synthesizer that highlights where models agree and differ. **Council for evaluation/benchmarking** (Zhao et al.'s Language Model Council at NAACL 2025, Verga et al.'s PoLL) uses multiple models as judges to reduce evaluation bias. Verga et al. demonstrated that a Panel of LLM evaluators (PoLL) using three smaller models outperformed a single GPT-4 judge while being **7× cheaper** and exhibiting less intra-model bias.

The academic literature reveals 15+ major papers since 2023. Irving et al.'s "AI Safety via Debate" (2018) established the foundational theoretical result that debate with optimal play can answer any question in PSPACE. Khan et al. (ICML 2024, **Best Paper**) provided empirical validation, showing debate helps non-experts achieve **76% accuracy** (models) and **88%** (humans) on questions where naive baselines achieve 48% and 60%. Du et al. (ICML 2024) demonstrated that multi-agent debate improves factuality and reasoning across 6 benchmarks. ChatEval (Chan et al., ICLR 2024) showed multi-agent evaluation outperforms single-agent by **6.2%** for ChatGPT and improves Spearman correlation with human judgments by **16.3%**. Kenton et al. (NeurIPS 2024) conducted the most comprehensive scalable oversight study across 9 tasks and ~5M generation calls, finding debate consistently outperforms consultancy.

Critical counter-evidence also exists. Wang et al. (ACL 2024) showed that single-agent LLMs with strong few-shot prompting can match multi-agent debate. "Debate or Vote" (2025) provided a martingale proof that majority voting captures most gains. The DEBATE benchmark (NeurIPS 2025) found LLM groups exhibit significantly stronger convergence than human groups, producing "overly moderate stances" and "unnatural patterns of opinion alignment."

---

## 5. Ten frameworks compete for multi-agent orchestration dominance

The multi-agent framework market reached **$7.84B** in 2025 (projected $52.62B by 2030). **LangGraph** leads enterprise adoption with **34.5M monthly downloads** and 400+ production companies (Klarna saved $60M; 853 employee-equivalents). Its graph-based state machine architecture supports all communication topologies with built-in persistence and checkpointing. **CrewAI** (44.3K stars, $18M raised) takes a role-based approach with Crews (autonomous teams) and Flows (deterministic workflows), using LiteLLM for 100+ provider support. **AutoGen** (54.6K stars) pioneered event-driven multi-agent conversations but entered maintenance mode in October 2025, merging with Semantic Kernel into the **Microsoft Agent Framework**. **MetaGPT** (57.6K stars, ICLR 2024 oral) implements SOP-based software company simulation. **OpenAI replaced Swarm** with the Agents SDK (March 2025, 10.3M downloads/month). Google launched **ADK** (April 2025) with multi-language support. **CAMEL** (NeurIPS 2023) focuses on role-playing communicative agents.

Key architectural convergences: all major frameworks now use the **adapter pattern** for LLM abstraction (LiteLLM dominates as standalone adapter), **graph-based architectures** have become dominant (LangGraph, Google ADK, Microsoft Agent Framework, Mastra), **MCP** (Model Context Protocol) is becoming the universal tool integration standard, and **OpenTelemetry** is the observability backbone for all 2025+ frameworks. For experiment tracking, MLflow provides native tracing for 7+ frameworks, Langfuse serves the open-source community (23K stars), and LangSmith dominates the LangChain ecosystem.

For council benchmarking specifically, none of these frameworks natively support the full council pattern (independent generation → peer review → aggregated synthesis). Karpathy's implementation remains the closest reference architecture, with llm-deliberate extending it with social choice voting methods.

---

## 6. Benchmark requirements specification

Based on the synthesis of R1's benchmark formalism, R2's scaling methodology, the classical foundations, and the taxonomy analysis, an LLM council benchmark must satisfy these requirements:

**Metric requirements.** The benchmark must measure at minimum: (a) **task accuracy** against ground truth across diverse domains, (b) **convergence rate** (rounds to agreement, AUC-agreement per Wu et al. 2025), (c) **deliberation efficiency** (quality improvement per round and per token), (d) **communication cost** (total tokens, API calls, wall-clock time), (e) **diversity preservation** (semantic diversity trajectory across rounds), (f) **fairness** (contribution distribution via Shapley values), (g) **robustness** (performance under injected faults per BFT theory), and (h) **inter-rater agreement** (Cohen's κ, Krippendorff's α for evaluation councils).

**Statistical requirements.** Per R1, evaluation must separately report **interpolation** (similar model configurations) and **extrapolation** (novel configurations) performance. The AIPW estimator should be used for unbiased aggregate estimates. Per R2, a **mixed-effects model** with domain-specific random intercepts should control for task effects. Confidence intervals must be reported via Bradley-Terry models (per Chatbot Arena methodology). At minimum **100 random trials** per configuration (per R1). The benchmark should use **paired statistical tests** (Wilcoxon signed-rank or bootstrap) rather than unpaired comparisons.

**Baseline requirements.** Every council configuration must be compared against: (a) best single model on the task, (b) self-consistency (same model sampled N times with majority vote), (c) random sampling equivalent (N independent responses with majority vote, no deliberation), (d) oracle best-of-N (upper bound), and (e) simple majority vote without deliberation. The "Debate or Vote" finding—that majority voting captures most gains—means the deliberation value-add must be isolated from the ensemble value-add.

**Task requirements.** Per R2's agentic task definition, benchmark tasks must span: (a) tasks where individual models are uncertain (below the ~45% ceiling), (b) tasks with information asymmetry (where debate provably helps per Khan et al.), (c) both objective (verifiable answers) and subjective (preference-based) evaluation, (d) tasks requiring both knowledge retrieval and reasoning, and (e) varying difficulty levels to test scaling behavior.

**Contamination requirements.** Per the benchmark contamination literature (Xu et al. 2024), the benchmark must use dynamically generated evaluation data, employ contamination detection, and include canary strings (per BIG-Bench methodology).

---

## 7. Research gaps yield twelve testable hypotheses

The intersection of the taxonomy gaps analysis, classical foundations, and empirical findings generates specific testable hypotheses:

**H1 (Diversity-performance curve):** There exists a non-monotonic relationship between council model diversity and performance—moderate diversity (2-3 model families) outperforms both homogeneous councils and maximally diverse councils, due to the tension between complementary knowledge and capability variance. Evidence: Self-MoA's surprising result; ReConcile's diversity contribution.

**H2 (Topology-task matching):** The optimal communication topology is predictable from measurable task properties (information density, reasoning depth, answer space size) with >80% accuracy, analogous to R2's 87% architecture prediction. No existing work formalizes this mapping.

**H3 (Deliberation diminishing returns):** For tasks with verifiable answers, >90% of council benefit comes from the first round (independent generation + aggregation), with deliberation rounds providing logarithmically diminishing returns. Evidence: "Debate or Vote" martingale proof; Wu et al.'s finding that additional rounds entrench errors.

**H4 (Byzantine resilience threshold):** LLM councils exhibit a sharp phase transition in performance at the 1/3 adversarial agent threshold predicted by BFT theory, and this threshold is tighter than 1/3 due to correlated failures from shared training data. Completely unexplored.

**H5 (Cardinal escape from Arrow):** Cardinal scoring mechanisms (where LLMs rate responses 1-10) produce strictly better council outcomes than ordinal ranking mechanisms across all task types, because they escape Arrow's impossibility constraints. Partially supported by ReConcile's confidence weighting but not systematically tested.

**H6 (Anti-sycophancy is necessary for convergence quality):** Without explicit anti-sycophancy prompting, councils converge to the majority opinion regardless of correctness within 3 rounds (per DEBATE benchmark findings), and anti-sycophancy interventions improve final accuracy by >5%.

**H7 (Dynamic role assignment dominates static):** Capability-aware dynamic role assignment (selecting which model debates, judges, or synthesizes based on task properties) outperforms fixed role assignment by >15%. Partial evidence: Zhang et al. (2025) showed 74.8% improvement, but only for debate roles.

**H8 (Memory-augmented deliberation improves multi-turn councils):** Adding shared episodic memory (where agents can reference specific prior exchanges) improves multi-round deliberation efficiency by >20% compared to stateless re-prompting. Completely unexplored.

**H9 (Shapley-optimal councils outperform greedy selection):** Council member selection guided by Shapley value computation produces councils that outperform both random selection and greedy "add-best-model" selection, because Shapley values capture complementarity. Proposed but never implemented.

**H10 (Information gain per round is measurable and predictive):** KL-divergence between council output distributions at round t and t+1 serves as a reliable predictor of when to terminate deliberation, and adaptive termination based on this metric reduces cost by >40% with <2% quality loss. No existing work.

**H11 (The ~45% ceiling is topology-dependent):** R2's finding that multi-agent systems hurt when single agents exceed ~45% accuracy holds only for specific topologies (independent, centralized) and can be pushed to ~65% with debate-style decentralized topologies on tasks with information asymmetry. Partially supported by R2's finding that decentralized debate excels for exploration tasks.

**H12 (Formal strategy-proofness is achievable via computational hardness):** While Gibbard-Satterthwaite proves no non-dictatorial mechanism is strategy-proof, computational complexity results (Bartholdi et al. 1989) suggest that the optimal manipulation of council aggregation is NP-hard, providing practical strategy-proofness for current LLMs. Never tested in LLM council settings.

---

## 8. Implementation architecture for a council benchmarking framework

Based on Karpathy's reference implementation, the multi-agent framework survey, and best practices for reproducible LLM evaluation, the recommended architecture follows a layered design:

**API abstraction layer.** Use **LiteLLM** as the universal model backend (100+ providers, OpenAI-compatible format, 8ms P95 latency at 1K RPS, built-in cost tracking). This provides the provider agnosticism that Karpathy achieves via OpenRouter but with local control and no vendor dependency. Wrap LiteLLM in a thin `ModelClient` abstraction that adds: response caching (for reproducibility), token counting, latency measurement, and failure injection (for robustness testing).

**Orchestration layer.** Use **LangGraph** for the council orchestration pipeline, leveraging its graph-based state machine for defining arbitrary council topologies. Each topology (star, mesh, chain, layered, debate) maps to a specific graph structure. LangGraph's built-in persistence enables checkpointing mid-deliberation, and its cycle support enables multi-round debate. The functional API (`@entrypoint`, `@task` decorators) provides clean abstractions. For simpler prototyping, a custom async orchestrator following Karpathy's `asyncio.gather()` pattern is sufficient.

**Configuration layer.** Use **Hydra** (by Facebook) for hierarchical configuration management with YAML composition. Define separate config groups for: council composition (which models, how many), topology (communication graph), protocol (deliberation rules), aggregation (voting method), and evaluation (metrics, baselines). This enables systematic sweeps over the taxonomy's 10 dimensions. Each experiment configuration should be fully serializable and version-controlled.

**Experiment tracking.** Use **MLflow** for experiment tracking (30M+ monthly downloads, native integrations with LangGraph, supports autologging). Log: per-round outputs, aggregation results, token counts, latencies, costs, and all configuration parameters. Use **OpenTelemetry** for distributed tracing of the multi-agent pipeline. For leaderboard-style comparison, implement Bradley-Terry scoring per Chatbot Arena methodology.

**Key code abstractions** (extending Karpathy's design):

- `Council(models, topology, protocol, aggregation)` — top-level orchestrator
- `Topology` — defines communication graph (adjacency matrix + message routing)
- `Protocol` — defines round structure (simultaneous, sequential, debate, peer-review)
- `Aggregation` — implements voting/scoring methods (majority, Borda, weighted, meta-judge)
- `ConsensusDetector` — monitors convergence, triggers termination
- `DiversityTracker` — measures semantic diversity across rounds
- `FaultInjector` — simulates Byzantine agents for robustness testing
- `ShapleyComputer` — computes per-model contribution via subset evaluation

The directory structure should follow:

```
council-bench/
├── configs/           # Hydra YAML configs (council, topology, protocol, aggregation, eval)
├── council/
│   ├── models.py      # LiteLLM wrapper with caching, metering, fault injection
│   ├── topology.py    # Graph-based topology definitions
│   ├── protocol.py    # Deliberation protocols (simultaneous, debate, peer-review)
│   ├── aggregation.py # Voting/scoring methods (majority, Borda, weighted, meta-judge)
│   ├── consensus.py   # Convergence detection, termination conditions
│   ├── diversity.py   # Semantic diversity tracking, funneling measurement
│   └── pipeline.py    # LangGraph-based orchestration pipeline
├── evaluation/
│   ├── metrics.py     # All benchmark metrics (accuracy, convergence, efficiency, fairness)
│   ├── baselines.py   # Single-model, self-consistency, random-vote baselines
│   ├── shapley.py     # Shapley value computation for member attribution
│   └── statistical.py # AIPW estimator, Bradley-Terry, bootstrap CI
├── tasks/             # Benchmark task definitions and data loaders
├── experiments/       # Experiment scripts and sweep configurations
└── analysis/          # Visualization, leaderboard generation, report templates
```

---

## 9. Vibecoding seed prompt for rapid prototyping

The following prompt, designed for Claude or GPT-level coding assistants, generates a functional council benchmarking prototype that can be iteratively refined:

```
Build an LLM Council Benchmarking Framework in Python with the following architecture:

## Core Design
- Use LiteLLM for model abstraction (supports 100+ providers)
- Use asyncio for parallel model queries (fan-out pattern)
- Use Hydra for YAML-based configuration management
- Use MLflow for experiment tracking

## Council Pipeline (3 configurable stages)
Stage 1 - Independent Generation: Query N models in parallel with the same prompt.
  Return list of (model_id, response, latency, tokens) tuples.

Stage 2 - Deliberation: Implement 4 protocol options:
  a) "none" - skip deliberation, go straight to aggregation
  b) "peer_review" - each model reviews anonymized responses and ranks them (Karpathy-style)
  c) "debate" - multi-round sequential debate where models respond to each other
  d) "simultaneous" - all models see all responses and revise simultaneously

Stage 3 - Aggregation: Implement 5 methods:
  a) majority_vote - simple plurality
  b) borda_count - positional scoring from rankings
  c) weighted_vote - confidence-weighted plurality
  d) meta_judge - separate LLM synthesizes final answer from all responses
  e) best_of_n - oracle selection (for upper-bound baseline)

## Configuration (Hydra YAML)
council:
  models: [openai/gpt-4o, anthropic/claude-3.5-sonnet, google/gemini-2.0-flash]
  chairman: openai/gpt-4o  # for meta_judge aggregation
  protocol: peer_review  # none | peer_review | debate | simultaneous
  aggregation: borda_count  # majority_vote | borda_count | weighted_vote | meta_judge
  max_rounds: 3
  anonymize: true  # strip model names during deliberation
  anti_sycophancy: true  # add anti-conformity instructions

## Evaluation Metrics (computed automatically)
- task_accuracy: compare final output to ground truth
- convergence_rate: rounds until agreement (AUC-agreement)
- deliberation_efficiency: accuracy_gain / tokens_spent
- diversity_trajectory: cosine distance between outputs per round
- communication_cost: total tokens, API calls, wall-clock time
- inter_rater_agreement: Cohen's kappa between model rankings

## Baselines (run automatically for comparison)
- single_best: best individual model on the task
- self_consistency: best model sampled N times with majority vote
- random_vote: N models, majority vote, no deliberation
- oracle_best_of_n: best individual response (upper bound)

## Experiment Runner
- Load tasks from a JSONL file (question, ground_truth, domain, difficulty)
- Run each council configuration on all tasks
- Log everything to MLflow (configs, per-round outputs, metrics)
- Generate comparison tables and plots

## Key Implementation Details
- All model calls via litellm.acompletion() with async/await
- Response caching with SHA256(prompt) keys for reproducibility
- Graceful degradation: if a model fails, continue with remaining
- Anonymization: replace model names with "Response A", "Response B" etc.
- Ranking parser: regex-based extraction of "FINAL RANKING:" section with fallbacks
- Token budget tracking per experiment
- Seed everything for reproducibility

## Anti-patterns to avoid
- Don't use LangChain (too heavy for this)
- Don't use classes where functions suffice
- Don't over-abstract - keep it readable
- Don't hardcode model names - everything via config

Start with a working end-to-end prototype that runs a 3-model council
on 10 GSM8K math problems, comparing all 4 protocols × 5 aggregation
methods, logging results to MLflow. Make it runnable with `python run.py`.
```

---

## 10. The road ahead requires bridging four disconnected communities

The most striking finding from this investigation is the **fragmentation across four research communities** that must converge for rigorous council benchmarking. Social choice theorists have spent decades proving impossibility results about aggregation, but these results have barely penetrated the LLM council literature—only the Berkeley position paper (ICML 2024) and GEDI (2024) directly engage with Arrow's theorem. Distributed systems researchers have formalized consensus under adversarial conditions, but only Aegean (2025) bridges this to LLM agents. The multi-agent debate community has produced compelling empirical results but largely ignores the theoretical constraints. And the LLM benchmarking community (HELM, Chatbot Arena, BIG-Bench) has developed sophisticated evaluation methodology that council researchers rarely adopt.

The **"Debate or Vote" martingale result** may be the most important finding for the field's trajectory: if majority voting truly captures most gains from multi-agent systems, then the research priority should shift from designing better deliberation protocols to understanding when and why deliberation adds value beyond voting. The conditions appear to be: information asymmetry (Khan et al.), task difficulty below the ~45% ceiling (Kim et al.), genuine model diversity (Chen et al.), and tasks where the correct answer is more "persuasive" than incorrect ones (the truthful debate advantage). A rigorous benchmark must isolate and measure these conditions.

Perplexity's commercial deployment of Model Council validates the paradigm's practical value but also reveals its current limitations: three models, one synthesis round, no iterative deliberation, no formal evaluation of synthesis quality. The gap between this production system and what the research suggests is possible—dynamic topology selection, capability-aware role assignment, adaptive termination, strategy-proof aggregation—represents both the research opportunity and the benchmark's purpose. **The field needs a benchmark not to rank existing councils, but to systematically map the conditions under which each design dimension matters**, enabling principled council engineering rather than ad hoc experimentation.