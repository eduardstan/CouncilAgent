---
name: new-aggregation
description: Scaffolds a new Aggregation subclass in council/aggregation.py plus a matching test file. Use when the user says "add a new aggregation", "create <Name> aggregation", or "/new-aggregation <Name>". Enforces Constitution §4 (no raw string Counter — use a Normalizer) and §7 (results carry cost and confidence).
---

# new-aggregation

Scaffold a new `Aggregation` method that conforms to the CouncilAgent architecture.

## Inputs
- `<Name>`: PascalCase class name, e.g. `CondorcetAggregation`, `WeightedBorda`, `CopelandAggregation`
- Optional: whether it needs a `PreferenceData` input (ranking-based) or only `AgentResponse` list (vote-based)

## Procedure

1. **Prerequisite check.** `council/aggregation.py`, `council/normalizer.py`, and `council/context.py` must exist. If any are missing, tell the user and stop.

2. **Read** the `Aggregation` base class and the `AggregationResult` dataclass from `council/aggregation.py`.

3. **Append the subclass**:
   ```python
   class <Name>(Aggregation):
       """<one-line description>."""

       def __init__(self, normalizer: AnswerNormalizer | None = None):
           # Constitution §4: always have a normalizer path. Never Counter() raw text.
           self.normalizer = normalizer or StructuredOutputNormalizer()

       async def aggregate(
           self,
           responses: list[AgentResponse],
           preferences: list[PreferenceData] | None = None,
           **kwargs,
       ) -> AggregationResult:
           if not responses:
               raise ValueError("<Name> requires at least one response")

           # 1. Normalize all response content to canonical keys
           normalized = [await self.normalizer.normalize(r.content) for r in responses]

           # 2. Implement the aggregation rule here
           raise NotImplementedError("Fill in <Name>.aggregate")

           # 3. Return an AggregationResult carrying:
           #    - final_answer (the winning content, not the normalized key)
           #    - confidence (0-1, derived from agreement / margin)
           #    - method="<Name>"
           #    - metadata (any diagnostic info)
   ```

4. **Reject hardcoded model names.** If the aggregation is synthesis-style (MetaJudge-like), the synthesis model MUST be injected via `__init__`, never hardcoded. Example:
   ```python
   def __init__(self, synthesis_model: str, model_client: ModelClient, ...):
       self.synthesis_model = synthesis_model
   ```

5. **Create test file** `tests/council/test_aggregation_<snake_name>.py`:
   ```python
   import pytest
   from council.aggregation import <Name>, AggregationResult
   from council.context import AgentResponse

   def _r(agent_id: str, content: str, round_index: int = 0) -> AgentResponse:
       return AgentResponse(agent_id=agent_id, content=content, round_index=round_index)

   @pytest.mark.asyncio
   async def test_<snake_name>_basic_agreement():
       agg = <Name>()
       responses = [
           _r("A", '{"answer": 72}'),
           _r("B", '{"answer": 72}'),
           _r("C", '{"answer": 72}'),
       ]
       result = await agg.aggregate(responses)
       assert isinstance(result, AggregationResult)
       assert result.confidence == 1.0
       assert result.method == "<Name>"

   @pytest.mark.asyncio
   async def test_<snake_name>_mixed_responses():
       agg = <Name>()
       responses = [
           _r("A", '{"answer": 72}'),
           _r("B", '{"answer": 72}'),
           _r("C", '{"answer": 100}'),
       ]
       result = await agg.aggregate(responses)
       # Deep review Issue 3: "The answer is 72" and "72" must group together
       assert "72" in result.final_answer

   @pytest.mark.asyncio
   async def test_<snake_name>_rejects_empty():
       agg = <Name>()
       with pytest.raises(ValueError):
           await agg.aggregate([])
   ```

6. **Branch**: `feature/p1-aggregation-<snake_name>` or `feature/p3-aggregation-<snake_name>` (Condorcet/Copeland are Phase 3).

7. **Report**: files touched, invariants, next step.

## Invariants enforced
- §4: normalizer is required, no raw `Counter(r.content)` anywhere
- §7: result carries `confidence` (cost is tracked at the pipeline level, not per-aggregation)
- No hardcoded model names — synthesis models are injected
- Empty response list raises `ValueError` (fail fast at the boundary)
