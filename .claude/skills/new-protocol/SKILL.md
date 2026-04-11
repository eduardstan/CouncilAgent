---
name: new-protocol
description: Scaffolds a new Protocol subclass in council/protocol.py plus a matching test file. Use when the user says "add a new protocol", "create a <name> protocol", or "/new-protocol <Name>". Enforces Constitution §3 (takes VisibilityContext, no state access) and §4 (injects output schema).
---

# new-protocol

Scaffold a new deliberation `Protocol` that conforms to the CouncilAgent architecture.

## Inputs
- `<Name>`: PascalCase name ending in `Protocol`, e.g. `SocraticProtocol`, `AdversarialProtocol`
- Optional: one-line description of what the protocol does

## Procedure

1. **Confirm prerequisites.** Check that `council/protocol.py` and `council/context.py` exist. If not, tell the user: "Phase 1 must complete `VisibilityContext` and the base `Protocol` class first. Run the phase-planner agent." and stop.

2. **Read the existing base class.** `Read council/protocol.py` to find `class Protocol(abc.ABC)` — match its exact signature.

3. **Append the new subclass** to `council/protocol.py`:
   ```python
   class <Name>(Protocol):
       """<one-line description>."""

       def __init__(self, output_schema: dict | None = None):
           self.output_schema = output_schema

       def build_prompt(self, ctx: VisibilityContext) -> str:
           # Use ONLY ctx.visible_responses, ctx.own_previous_responses,
           # ctx.original_prompt, ctx.round_index, ctx.communication_mode.
           # Do NOT touch round_history directly.
           raise NotImplementedError("Fill in <Name>.build_prompt")
   ```

4. **Create the test file** `tests/council/test_protocol_<snake_name>.py`:
   ```python
   import pytest
   from council.context import VisibilityContext, CommunicationMode
   from council.protocol import <Name>

   def _ctx(round_index=0, visible=None, own=None):
       return VisibilityContext(
           agent_id="Response A",
           round_index=round_index,
           visible_responses=visible or [],
           own_previous_responses=own or [],
           total_agents=3,
           communication_mode=CommunicationMode.INDIVIDUAL,
           original_prompt="What is 2+2?",
       )

   def test_<snake_name>_round_zero_returns_original_prompt():
       p = <Name>()
       prompt = p.build_prompt(_ctx())
       assert "2+2" in prompt

   def test_<snake_name>_does_not_leak_real_agent_ids():
       # Constitution §10 — all agent_ids in ctx must already be anonymized.
       # Verify the protocol does not invent new identity strings.
       p = <Name>()
       prompt = p.build_prompt(_ctx(round_index=1))
       assert "gpt-" not in prompt.lower()
       assert "claude-" not in prompt.lower()

   def test_<snake_name>_injects_schema_when_provided():
       schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
       p = <Name>(output_schema=schema)
       prompt = p.build_prompt(_ctx())
       assert "answer" in prompt
   ```

5. **Create a feature branch** `feature/p1-protocol-<snake_name>` if not already on one.

6. **Report**: files created, test file path, next step ("Implement `build_prompt` and run `pytest tests/council/test_protocol_<snake_name>.py`").

## Invariants the scaffold enforces
- Subclass MUST take only `VisibilityContext` as prompt-building input (§3)
- Subclass MUST accept `output_schema` in `__init__` for structured output injection (§4)
- Test file asserts anonymization (§10) and schema injection (§4)
