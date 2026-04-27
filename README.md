# CouncilAgent

**A drop-in replacement for a single LLM call that internally runs a council of models, deliberates, and returns a synthesized answer with calibrated confidence.**

```python
agent = CouncilAgent.from_yaml("configs/fast.yaml")
response = await agent.complete("What is the capital of France?")
print(response.answer)       # "Paris"
print(response.confidence)   # 0.95  (derived from inter-agent agreement)
```

Same interface as one model call. Internally: fan-out → deliberate → rank → aggregate → confidence.

---

## Why a council?

A single LLM gives one answer and a self-reported confidence that is often miscalibrated.  
A council gives one answer and a *measured* confidence derived from how much the members agreed — before and after deliberation.

The council is not a benchmark harness. It is an agent.

---

## Architecture

```
CouncilAgent       (agent.py)       — complete(prompt) → CouncilResponse
CouncilPolicy      (policy.py)      — task profile + budget → CouncilConfig
run_council()      (core.py)        — pure async pipeline
─────────────────────────────────────────────────────────────
Topology           (topology.py)    — who sees whom each round
Protocol           (protocol.py)    — prompt construction per agent
Ranking            (ranking.py)     — extract preferences from text
Aggregation        (aggregation.py) — reduce to final answer
Normalizer         (normalizer.py)  — canonical answer keys
Termination        (termination.py) — when to stop deliberating
─────────────────────────────────────────────────────────────
ModelClient        (models.py)      — LiteLLM wrapper: cache, meter, retry
─────────────────────────────────────────────────────────────
Evaluation layer   (evaluation/)    — metrics, baselines, Shapley, MLflow
```

Each layer has exactly one job. No layer does another's job (Constitution §3).  
`council/core.py` is pure Python + asyncio — zero framework dependencies (§8).

### Topologies

| Class | Visibility | Communication mode |
|---|---|---|
| `CompleteGraphTopology` | All agents see all | INDIVIDUAL |
| `StarTopology` | Pure relay, round-invariant | RELAY |
| `DynamicStarTopology` | Alternating fan-out/fan-in | RELAY |
| `BusTopology` | Shared broadcast | BROADCAST |
| `RingTopology` | Predecessor only | RELAY |

### Protocols

| Class | Rounds | Use case |
|---|---|---|
| `DirectAnswerProtocol` | 1 | Fast, single-shot |
| `PeerReviewProtocol` | 2 per cycle (answer + critique) | Quality-focused deliberation |
| `SimultaneousProtocol` | N with sliding window | Iterative refinement |

### Aggregation

| Class | Requires ranking? | Notes |
|---|---|---|
| `MajorityVote` | No | Normalizer-canonical majority |
| `BordaCount` | Yes | Positional scoring |
| `CondorcetAggregation` | Yes | Pairwise majority |
| `MetaJudge` | No | LLM synthesizes final answer from debate |

---

## Quickstart

### Install

```bash
pip install -e .
# or
uv sync
```

### Run the benchmark runner

```bash
# Fast mode (3 free-tier models, MajorityVote, 1 deliberation round)
uv run python experiments/run.py configs/experiment/fast.yaml

# Custom experiment
uv run python experiments/run.py configs/experiment/my_experiment.yaml
```

### YAML config shape

```yaml
council:
  models:
    - model: openrouter/meta-llama/llama-3.1-8b-instruct:free
      temperature: 0.7
    - openrouter/mistralai/mistral-7b-instruct:free
    - openrouter/google/gemma-2-9b-it:free

  topology: complete          # complete | star | dynamic_star | bus | ring
  protocol: peer_review       # direct | peer_review | simultaneous
  ranking: structured         # null | regex | structured
  aggregation: majority_vote  # majority_vote | borda | condorcet | meta_judge

  termination:
    name: agreement_threshold
    agreement_threshold: 0.8  # stop early when ≥80% of agents agree

  max_rounds: 2               # deliberation cycles (not counting round 0)

dataset:
  name: mmlu
  split: test
  n_samples: 100
```

### Programmatic API

```python
from council.agent import CouncilAgent
from council.context import CouncilConfig
from council.topology import CompleteGraphTopology
from council.protocol import PeerReviewProtocol
from council.aggregation import MajorityVote
from council.models import LiteLLMClient, AgentConfig

config = CouncilConfig(
    agents=[
        AgentConfig(model="openai/gpt-4o-mini"),
        AgentConfig(model="anthropic/claude-haiku-4-5-20251001"),
        AgentConfig(model="openrouter/google/gemma-2-9b-it:free"),
    ],
    topology=CompleteGraphTopology(3),
    protocol=PeerReviewProtocol(),
    aggregation=MajorityVote(),
    max_rounds=1,
)
agent = CouncilAgent(config, model_client=LiteLLMClient())
response = await agent.complete("What is 6 × 7?")
```

---

## Testing

```bash
uv run pytest tests/ -q                          # full unit suite (455 tests)
RUN_INTEGRATION=1 uv run pytest tests/integration/  # real model calls (needs API keys)
uv run ruff check council/ evaluation/           # lint
uv run mypy council/core.py council/agent.py     # strict type-check
```

---

## Design principles (the Constitution)

1. The council is an **agent**, not a benchmark.
2. **Same interface** as a single LLM — `complete(prompt) → response`.
3. **Topology controls visibility. Protocol controls presentation. Aggregation controls decision.** No layer does another's job.
4. **Structured output over regex** — JSON first, regex fallback only.
5. **Calibrated confidence** from inter-agent agreement, not self-report.
6. Every council run must **beat majority-vote-without-deliberation** on the same models.
7. **Cost is first-class** — every response carries its cost, budgets are enforced.
8. **Zero framework dependencies** in `council/core.py`.
9. **Correctness before features.**
10. **Anonymize by default** — agent identities stripped during deliberation.

---

## Phased roadmap

| Phase | Status | Scope |
|---|---|---|
| 1 | ✅ | Core abstractions, VisibilityContext, multi-round peer review |
| 2 | ✅ | Termination, TaskProfile, cost estimation |
| 3 | ✅ | CouncilAgent, CouncilPolicy, EscalationStrategy, Condorcet |
| 4 | ✅ | Benchmark infrastructure: MLflow, AIPW, Hydra, Shapley |
| 5 | ✅ | Pipeline hardening: is_answer_round, cycle_length, debate-aware aggregation |
| 6 | ✅ | Runner configurability, per-agent config, audit polish (7 fixes) |
| 7 | 🔜 | Hypothesis testing (H1, H3, H5, H6, H10) |
| 8 | 🔜 | Polish, demos, thesis integration |

---

## License

Research prototype — see `plan.md` and `LLMCouncil_Deep_Review.md` for context.
