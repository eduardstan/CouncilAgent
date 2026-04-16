# Architecture Rules (binding)

These rules encode Constitution §3 and §8 at file-and-symbol granularity. A PR that violates any of these is rejected unless the user explicitly overrides.

## Layer responsibilities

| Layer | File | May do | May NOT do |
|-------|------|--------|-----------|
| **Topology** | `council/topology.py` | Return `adjacency_matrix(round_index)`, declare `communication_mode` | Construct prompts, call models, know about protocols, hardcode "chairman" or any privileged agent |
| **Protocol** | `council/protocol.py` | Build a single-agent prompt from a `VisibilityContext` | Read `state["round_history"]` directly, filter by agent identity, embed anonymization logic |
| **Ranking** | `council/ranking.py` | Parse rankings/scores from a text response | Call models, reshape responses, decide winners |
| **Aggregation** | `council/aggregation.py` | Reduce responses + preferences to a final answer | Construct deliberation prompts, mutate state history, hardcode the synthesis model |
| **Normalizer** | `council/normalizer.py` | Turn raw text into a canonical answer key | Do embedding calls inside `MajorityVote` (embedding normalizers are allowed, but via their own class) |
| **Termination** | `council/termination.py` | Read `CouncilState`, return `(should_stop, reason)` | Mutate state, call aggregation |
| **Core pipeline** | `council/core.py` | Compose the above; read adjacency matrix; build `VisibilityContext`; centralize anonymization | Import `langgraph`, `hydra`, `mlflow`, or any framework |
| **Agent** | `council/agent.py` | Wrap `run_council` in the single-LLM `complete()` interface; compute confidence from agreement | Re-implement pipeline logic |
| **Policy** | `council/policy.py` | Map `(prompt, TaskProfile, budget)` → `CouncilConfig` | Execute councils |
| **ModelClient** | `council/models.py` | Route calls to LiteLLM or OpenRouter; cache; meter; retry; inject faults | Know about topology, protocols, or rankings |

## Forbidden imports
- `council/core.py`, `council/agent.py`, `council/policy.py` MUST NOT import `langgraph`, `hydra`, `mlflow`, `opentelemetry`, `langchain`, `langchain_*`.
- Any `council/*.py` MUST NOT import from `evaluation/` or `experiments/`.
- Any layer module (topology, protocol, ranking, aggregation, normalizer, termination) MUST NOT import another layer module. They communicate only through dataclasses defined in `council/context.py`.

### Approved exception — `council/aggregation.py` may import `council/models.py`
`MetaJudge` (an `Aggregation` subclass) calls an LLM to synthesize a final answer. It receives a `ModelClient` at construction time — the model is injected, never hardcoded. This is an aggregation-internal operation, distinct from deliberation-phase prompt construction. The import is approved and permanent:
```python
from council.models import ModelClient, ModelFailure, ModelRequest
```
No other layer module may import from `council/models.py`.

### Approved exception — `evaluation/` may import from `council/`
`evaluation/` is downstream of the pipeline (benchmark mode only, never imported by `council/`).
It is not a peer layer and is explicitly excluded from the peer-layer mutual-import prohibition.
`evaluation/metrics.py` imports `council.context.CouncilState` (to read round_history) and
`council.normalizer.AnswerNormalizer` (for smart task_accuracy matching). This is approved and permanent.
No `council/` module may import from `evaluation/` — the direction is one-way.

## Required contracts
- `Protocol.build_prompt(ctx: VisibilityContext) -> str` — build the prompt for one agent in one round.
- `Protocol.is_answer_round(round_index: int) -> bool` — True if agents produce a final answer this round. Default: all rounds are answer rounds. PeerReviewProtocol returns False for odd (critique) rounds. Core pipeline gates `response_format` and aggregation input on this predicate.
- `Protocol.cycle_length() -> int` — number of raw rounds per deliberation cycle. DirectAnswer/Simultaneous = 1, PeerReview = 2 (critique + revision). Used by the runner to translate config `max_rounds` (deliberation cycles) to total raw rounds: `total = 1 + max_rounds * cycle_length()`.
- `Topology.get_adjacency_matrix(round_index: int) -> list[list[bool]]` — pure function of round.
- Every layer base class lives in its own module and uses `abc.ABC` with `@abstractmethod`.
- `StarTopology` is a **pure relay** — it returns a complete graph or an explicit 2-hop relay. It must NOT alternate on round parity. Round-dependent visibility lives in `DynamicStarTopology`.

## Framework adapters
- LangGraph wrapper lives ONLY in `council/adapters/langgraph.py`.
- Hydra entry points live ONLY in `experiments/`.
- MLflow logging lives ONLY in `evaluation/` and `experiments/`.

## When in doubt
If you cannot place a piece of logic cleanly in one of the layers above, the abstraction is wrong. Stop and ask the user — do not paper over it with a cross-layer helper.
