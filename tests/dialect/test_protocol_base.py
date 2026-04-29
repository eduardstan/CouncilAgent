"""Tests for council/dialect/protocols/base.py — ProtocolAutomaton ABC."""

from __future__ import annotations

import pytest


def test_protocol_automaton_cannot_be_instantiated_directly() -> None:
    from council.dialect.protocols.base import ProtocolAutomaton
    with pytest.raises(TypeError):
        ProtocolAutomaton()  # type: ignore[abstract]


def test_concrete_subclass_without_all_methods_raises_type_error() -> None:
    from council.dialect.protocols.base import ProtocolAutomaton

    class Incomplete(ProtocolAutomaton):
        pass  # missing all four abstract methods

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_minimal_concrete_subclass_can_instantiate() -> None:
    from council.dialect.moves import Force
    from council.dialect.protocols.base import ProtocolAutomaton
    from council.dialect.trace import Trace

    class Minimal(ProtocolAutomaton):
        def state(self, trace: Trace) -> tuple[str, str]:
            return ("start", "open")

        def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]:
            return frozenset({Force.PROPOSE})

        def is_terminal(self, trace: Trace) -> bool:
            return False

        def is_answer_phase(self, trace: Trace) -> bool:
            return False

    m = Minimal()
    assert isinstance(m, ProtocolAutomaton)


def test_legal_forces_returns_frozenset() -> None:
    from council.dialect.moves import Force
    from council.dialect.protocols.base import ProtocolAutomaton
    from council.dialect.trace import Trace

    class Stub(ProtocolAutomaton):
        def state(self, trace: Trace) -> tuple[str, str]:
            return ("s", "d")
        def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]:
            return frozenset({Force.PROPOSE, Force.VOTE})
        def is_terminal(self, trace: Trace) -> bool:
            return False
        def is_answer_phase(self, trace: Trace) -> bool:
            return False

    s = Stub()
    result = s.legal_forces(Trace(), "agent_0")
    assert isinstance(result, frozenset)
    # Constitution §3: return is immutable
    with pytest.raises((TypeError, AttributeError)):
        result.add(Force.CHALLENGE)  # type: ignore[attr-defined]


def test_is_answer_phase_and_is_terminal_are_bool() -> None:
    from council.dialect.moves import Force
    from council.dialect.protocols.base import ProtocolAutomaton
    from council.dialect.trace import Trace

    class Stub(ProtocolAutomaton):
        def state(self, trace: Trace) -> tuple[str, str]:
            return ("s", "d")
        def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]:
            return frozenset()
        def is_terminal(self, trace: Trace) -> bool:
            return True
        def is_answer_phase(self, trace: Trace) -> bool:
            return True

    s = Stub()
    assert s.is_terminal(Trace()) is True
    assert s.is_answer_phase(Trace()) is True
