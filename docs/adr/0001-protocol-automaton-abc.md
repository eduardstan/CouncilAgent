# ADR-0001: Use abc.ABC (not typing.Protocol) for ProtocolAutomaton

## Status
Accepted

## Date
2026-04-29

## Context

`ProtocolAutomaton` is the base type for every dialogue-protocol implementation in W0
(deliberation, persuasion, inquiry, composite, socratic). The W1 verification layer
attaches `LTLfMonitorTermination` hooks to the automaton's `is_terminal` and
`is_answer_phase` predicates. The W6 ILP layer uses `rule_to_automaton.py` to produce
new subclasses from learned ASP rules at genome-creation time.

We needed to choose between two mechanisms:

1. **`abc.ABC` + `@abstractmethod`** — nominal typing; every subclass must explicitly
   inherit from `ProtocolAutomaton` and override every abstract method.
2. **`typing.Protocol`** — structural typing; any class that implements the four methods
   is automatically compatible, whether or not it inherits from `ProtocolAutomaton`.

## Decision

Use **`abc.ABC` + `@abstractmethod`**.

## Alternatives Considered

### `typing.Protocol` (structural typing)
- **Pros:** More flexible; third-party automata can satisfy the contract without importing
  our base class; fits the "duck typing" Python idiom.
- **Cons:**
  - Under `mypy --strict`, structural compatibility is checked at *use sites*, not at
    *definition sites*. A class that accidentally has the four method names with
    incompatible signatures silently satisfies the Protocol — the error only surfaces
    when the object is passed somewhere that expects `ProtocolAutomaton`.
  - The W1 `LTLfMonitorTermination` hook needs to call `isinstance(automaton, ProtocolAutomaton)`
    at runtime (to distinguish it from other termination strategies). Protocol-based
    `isinstance` checks require `@runtime_checkable`, which is fragile and not required
    for `abc.ABC`.
  - W6's `rule_to_automaton.py` generates subclasses dynamically. Using `type(..., (ProtocolAutomaton,), {...})` is unambiguous with ABC; with Protocol there is no explicit
    inheritance contract, making the dynamic subclass invisible to static analysis.

### `abc.ABC` (chosen)
- **Pros:**
  - Every concrete automaton is *visibly* a `ProtocolAutomaton` — explicit inheritance
    makes the contract nominal and traceable in `git blame`.
  - `isinstance(automaton, ProtocolAutomaton)` works without `@runtime_checkable`.
  - Missing `@abstractmethod` overrides raise `TypeError` at instantiation — fast fail.
  - mypy strict catches signature mismatches at the *subclass definition site*, not
    only at use sites.
- **Cons:**
  - Slightly more import coupling (subclasses must import `base.py`). Acceptable because
    all automata live in `council/dialect/protocols/` and that coupling is expected.

## Consequences

- All five concrete automata (deliberation, persuasion, inquiry, composite, socratic)
  inherit from `ProtocolAutomaton`.
- W6 `rule_to_automaton.py` must call `type("Learned_NNN", (ProtocolAutomaton,), {...})`
  when generating protocol classes from ASP rules.
- W1 interventions can safely call `isinstance(automaton, ProtocolAutomaton)`.
- Adding a new automaton that forgets one of the four abstract methods fails loudly
  at construction time, not silently at runtime.
