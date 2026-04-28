---
name: new-protocol-automaton
description: Scaffolds a new ProtocolAutomaton subclass in council/dialect/protocols/<slug>.py plus matching tests. Use when the user says "add a new protocol-automaton" or "/new-protocol-automaton <Name>". Enforces NS Constitution §3 (typed FSM, no round-parity hardcoding) and §4 (works on Move/Trace, never raw text).
---

# new-protocol-automaton

Scaffold a `ProtocolAutomaton` (W0 / L0) — a typed finite-state machine over speech-acts.

## Inputs
- `<Name>` — PascalCase, ending in `Automaton`. Examples: `DeliberationAutomaton`, `PersuasionAutomaton`, `InquiryAutomaton`, `SocraticAutomaton`.
- Optional one-line description.

## Procedure

1. **Prerequisite check.** `council/dialect/protocols/base.py`, `council/dialect/{moves,trace}.py`, `council/context.py` must exist. If any are missing, tell the user "Workstream W0 substrate is incomplete; finish that first" and stop.
2. **Refuse round-parity smuggling.** If the user's description amounts to `if round_index % k == 0` without a state-based justification, refuse and explain that NS bans round-parity (defect D8).
3. **Append the subclass** to a new file `council/dialect/protocols/<slug>.py`:
   ```python
   from council.dialect.protocols.base import ProtocolAutomaton
   from council.dialect.moves import Force, Move
   from council.dialect.trace import Trace

   class <Name>(ProtocolAutomaton):
       """<one-line description>."""
       def state(self, trace: Trace) -> tuple[str, str]:
           raise NotImplementedError

       def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]:
           raise NotImplementedError

       def is_terminal(self, trace: Trace) -> bool:
           raise NotImplementedError

       def is_answer_phase(self, trace: Trace) -> bool:
           raise NotImplementedError
   ```
4. **Create test file** `tests/dialect/protocols/test_<slug>.py` with:
   - State-transition coverage tests (every state reachable from a hand-crafted trace).
   - `legal_forces` returns a `frozenset` (immutable).
   - `is_terminal` is deterministic (same trace → same answer).
   - `is_answer_phase` agrees with manually-counted answer phases on a fixture trace.
5. Run `uv run pytest tests/dialect/protocols/test_<slug>.py`.
6. Branch `feature/ns-w0-protocol-<slug>`.

## Invariants enforced
- §3 (typed FSM, immutable returns).
- §4 (works on `Move`/`Trace`, never raw text).
- No imports from `aggregation`, `topology`, `models`, `evaluate`, `evolve`.
- No `round_index % k` heuristics.

## Reject criteria
- `<Name>` not ending in `Automaton`.
- Subclass touches `state` or external services.
- Round-parity in any of the four methods.
