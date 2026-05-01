# Architecture Rules (binding)

These rules encode the 12-principle Constitution at file-and-symbol granularity. A PR that violates any of them is rejected unless the user explicitly overrides.

## Layer responsibilities

| Layer | File(s) | May do | May NOT do |
|---|---|---|---|
| **L0 dialect/moves** | `council/dialect/moves.py` | Define the typed `Move` ADT (`Propose | Challenge | Concede | Retract | Question | Clarify | Vote | Abstain`), `Claim`, `Force`, `ClaimDomain` | Call models; reference protocols, topologies, aggregators; embed admissibility rules (those live in `protocols/`) |
| **L0 dialect/trace** | `council/dialect/trace.py` | Provide immutable `Trace` operations: `by_id`, `at_round`, `by_force`, `append`, `to_events` | Mutate state; depend on protocol-automaton internals; embed semantics |
| **L0 dialect/protocols** | `council/dialect/protocols/{base,deliberation,persuasion,inquiry,composite,socratic}.py` | Define `ProtocolAutomaton` ABC and concrete automata; expose `state(trace)`, `legal_forces(trace, agent_id)`, `is_terminal(trace)`, `is_answer_phase(trace)` | Construct prompts (that's `dialect/surface.py`); call models; read external state |
| **L0 dialect/parsers, surface** | `council/dialect/{parsers,surface}.py` | Parse LLM output → `Move`; render `Move` → NL | Embed business logic about admissibility |
| **L1 symbolic/verify** | `council/symbolic/verify/*` | Compile LTL₍f₎ properties → DFA; step monitors over `Trace.to_events()`; encode `(automaton, trace)` → ISPL/SMV; emit interventions | Construct prompts; call generation models; reach into aggregators |
| **L2 symbolic/argue** | `council/symbolic/argue/*` | Build BAF/QBAF from `Trace`; apply gradual semantics; export DOT/Mermaid | Re-extract arguments from raw text on the headline path; mutate the trace; call generation models on the headline path. A **fallback** mining hook is allowed under §4 and must be tagged `tier="argument-mining-fallback"` |
| **L3 calibrate** | `council/calibrate/*` | Compute JSD / MUSE / privileged-knowledge calibration; produce `Confidence` values; expose `JSDDivergenceTermination`, `ConFreezeTermination` | Construct prompts; mutate the trace; call generation models |
| **L4 cascade** | `council/cascade/*` | Decide which agent / model handles which step; track $/token; trigger escalation | Construct deliberation prompts; mutate the trace; reach into aggregators |
| **L5 evolve** | `council/evolve/*` | Search the genome space via QD; compute behavioural descriptors **from L1+L2 outputs**; manage Pareto fronts | Call deliberation directly (always via `evaluate.py` → `run_council`); reach into protocol internals beyond what the genome exposes; use generation-model calls in the no-extras path |
| **L6 symbolic/ilp** | `council/symbolic/ilp/*` | Run Popper/ILASP4 over labelled traces; enforce ASP integrity constraints via clingo; verify induced rules via MCMAS | Mutate the trace at runtime; replace `dialect/` automata at runtime (only at genome-creation time, via `rule_to_automaton.py`) |
| **Core** | `council/core.py` | Compose the layers; build `VisibilityContext` (single source of anonymisation); thread response formats; honour interventions; assemble `ProvenanceReceipt` skeleton | Import `langgraph`, `hydra`, `mlflow`, `opentelemetry`, `langchain`, `pyribs`, `spot`, `clingo` |
| **Agent** | `council/agent.py` | Wrap `run_council` in the single-LLM `complete()` interface; finalise `ProvenanceReceipt`; route to escalation | Re-implement pipeline logic; recompute confidence in raw-text space |
| **Policy** | `council/policy.py` | Map `(prompt, TaskProfile, budget)` → `CouncilGenome` (drawing from the QD archive when present) | Execute councils; embed hardcoded model tiers |
| **ModelClient** | `council/models.py` | Route calls to LiteLLM; cache; meter; retry; inject faults | Know about topology/protocol/ranking semantics |
| **ToolClient** | `council/tools.py` | Route tool calls (MCP / Z3 / clingo / Lean / Python sandbox / web) | Construct prompts; call generation models |

## Forbidden imports (rejected by CI)

- `council/core.py`, `agent.py`, `policy.py`, and any module under `dialect/`, `calibrate/`, `cascade/`, `evolve/` MUST NOT import: `langgraph`, `hydra`, `mlflow`, `opentelemetry`, `langchain`, `langchain_*`, `pyribs` (without the `evolve` extra guard), `spot` (without the `verify` extra guard), `clingo` (without the `ilp` extra guard).
- Any `council/*.py` MUST NOT import from `evaluation/`, `experiments/`, `apps/`, or `legacy_council/`.
- Layer modules MUST NOT import each other except through dataclasses defined in `council/context.py` and `council/dialect/moves.py`. Exceptions are explicitly listed below.

## Approved exceptions (permanent)

1. **`council/symbolic/argue/aggregator.py` → `council/calibrate/jsd.py`** — to build calibrated base scores. Documented; no other path.
2. **`council/cascade/strategies.py` → `council/models.py`** — to invoke escalated/upgraded models. The model is *injected* via the strategy's `__init__`, never hardcoded.
3. **`council/evolve/evaluate.py` → `council/core.run_council`** — to evaluate genomes. The only allowed path from L5 into the pipeline.
4. **`council/symbolic/verify/interventions.py` → `council/dialect/moves.py`** — to inject `Move`s on `⊥` verdicts (e.g. `ForceChallenge`).
5. **`evaluation/` → `council/`** but never the reverse. One-way.
6. **`apps/` → `council/` and `evaluation/`** but never the reverse.
7. **`council/termination.py` → `council/calibrate/jsd.py`** (W3/PR5; ADR-0019) — `JSDDivergenceTermination` and `ConFreezeTermination` re-use the `jsd_divergence` primitive to compute inter-round JSD on Propose distributions. Function-scope import to keep the L0 termination ABC importable without the `[calibrate]` extra; only the W3 strategies pull the dependency in.

## Required contracts

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
    formula: ClassVar[str]                           # LTL_f source
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
    def calibrate(self, raw_confidence: float, agent_id: str,
                  claim_domain: ClaimDomain) -> float: ...

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

## Type-level invariants enforced by mypy strict

- `AgentResponse.move: Move` — no `Any`, no `Optional`. (Constitution §4.)
- `CouncilResponse.confidence: Confidence` where `Confidence = JSDConfidence | BAFMarginConfidence | MonitorVerdictConfidence | CopelandConfidence`. (§5; **plurality fraction is type-impossible.**)
- `Aggregator.aggregate(trace: Trace, *, original_question: str)` — no `responses: list[AgentResponse]` overload; the trace is the only input.
- `ProtocolAutomaton.legal_forces(trace, agent_id) -> frozenset[Force]` — return is immutable.

## Per-genome configuration

`CouncilGenome` (in `council/evolve/genome.py`) is a **frozen `slots=True` dataclass** with these fields:
- `members: tuple[AgentSpec, ...]` — `(model_id, persona, decoding, tools)` per agent.
- `topology: TopologySpec`
- `protocol: ProtocolAutomatonSpec`
- `aggregator: AggregatorSpec`
- `monitors: tuple[PropertyName, ...]`
- `calibration: CalibrationSpec`
- `termination: tuple[TerminationSpec, ...]`
- `cascade: CascadeSpec | None = None`

Every spec is round-trippable to YAML. The genome is the unit of search in L5 and the unit of provenance in `ProvenanceReceipt`.

## YAML runner schema (`experiments/run.py`)

```yaml
genome:
  members:
    - {model: "openai/gpt-4o-mini", temperature: 0.7, persona: "skeptic"}
    - {model: "anthropic/claude-3.5-sonnet", temperature: 0.4}
    - {model: "openrouter/google/gemma-3-27b-it:free"}
  topology: {name: "CompleteGraphTopology"}
  protocol: {name: "DeliberationAutomaton", params: {max_phases: 5}}
  aggregator:
    name: "ArgumentationAggregator"
    semantics: "DFQuAD"
    calibrator: "JSD"
  calibration:
    name: "MUSE"
    privileged_per_domain: true
  monitors:
    - "NoSycophancyCascade"
    - "EventuallyDecide"
    - "NoPrematureConsensus"
    - "ProvenanceCompleteness"
  termination:
    - {name: "LTLfMonitorTermination"}
    - {name: "JSDDivergenceTermination", threshold: 0.05}
    - {name: "FixedRounds", max_rounds: 3}
  cascade:
    name: "InContextDistillationCascade"
    student_pool: ["openrouter/google/gemma-3-27b-it:free"]
    teacher_pool: ["anthropic/claude-3.5-sonnet"]
task:
  profile: "frontiermath_t4"
budget:
  max_usd: 10.0
  max_tokens: 200000
  max_seconds: 1200
```

## ProtocolAutomaton-derived predicates

`is_answer_round(round_index)` and `cycle_length()` (from the legacy stack) are **derived** from the automaton's `is_answer_phase(trace)` and terminal-state predicates. There is no round-parity hardcoding anywhere — that defect (D8) is fixed at the type level.

## Task-aware prompting

Per-dataset answer-format instructions are subsumed by:
- `Claim.domain` (typed at L0) — answer-format is determined by domain.
- `dialect/surface.py` — domain-conditioned NL rendering.
- `tasks/profiles.py` — per-dataset overrides expose a `surface_overrides: dict[str, str]` field.

## Framework adapters

- LangGraph wrapper lives ONLY in `council/adapters/langgraph.py`.
- Hydra entry points live ONLY in `experiments/`.
- MLflow logging lives ONLY in `evaluation/` and `experiments/`.
- OpenTelemetry instrumentation lives ONLY in `council/adapters/otel.py` and is enabled by `experiments/`.

## When in doubt

If you cannot place a piece of logic cleanly in one of the layers above, the abstraction is wrong. **Stop and ask the user — do not paper over it with a cross-layer helper.** §3 violations are the most common failure mode and the type system catches some — but not all — of them.
