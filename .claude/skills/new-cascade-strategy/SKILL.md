---
name: new-cascade-strategy
description: Scaffolds a new RoutingStrategy subclass in council/cascade/strategies.py plus tests. Use when the user says "add a new cascade strategy" or "/new-cascade-strategy <Name>". Enforces budget tracking and cost-Pareto wins over a NullStrategy baseline.
---

# new-cascade-strategy

Scaffold a `RoutingStrategy` (W4 / L4) for cost-aware escalation.

## Inputs
- `<Name>` — PascalCase, ending in `Strategy` or `Cascade`. Examples: `InContextDistillationCascade`, `RouteByDomainStrategy`, `DisagreementGatedEscalation`.

## Procedure

1. **Prerequisite check.** `council/cascade/{router,budget}.py` must exist. If not, stop.
2. **Append the subclass** to `council/cascade/strategies.py`:
   ```python
   from council.cascade.base import RoutingStrategy, AgentSpec, CouncilContext
   from council.dialect.trace import Trace

   class <Name>(RoutingStrategy):
       """<one-line description>."""
       async def route(self, trace: Trace, ctx: CouncilContext) -> AgentSpec:
           raise NotImplementedError
   ```
3. **Create test file** `tests/cascade/test_<slug>.py` with:
   - Budget enforcement on a 100-task synthetic.
   - Cost-Pareto improvement over `NullStrategy` (matched-task accuracy ≥ baseline; cost strictly less).
   - Trigger condition test (e.g. routing to teacher when JSD > threshold).
4. Branch `feature/ns-w4-cascade-<slug>`.

## Invariants enforced
- Models are *injected* via `__init__`, never hardcoded.
- Strategy never modifies the trace.
- Strategy never constructs deliberation prompts.
- Cost ledger entries are stamped on every routed call.

## Reject criteria
- Hardcoded model names (e.g. `"openai/gpt-4o-mini"` literal).
- Strategy imports from `council/dialect/protocols/` or `council/symbolic/argue/`.
