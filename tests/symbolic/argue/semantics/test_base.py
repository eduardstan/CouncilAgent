"""Tests for council/symbolic/argue/semantics/base.py — GradualSemantics ABC.

Concrete semantics (DF-QuAD, QE, Euler, Strategic-Coupled) ship in PR3-PR5.
This test pins the ABC contract only.
"""

from __future__ import annotations

import inspect

import pytest

from council.symbolic.argue.baf import QBAF, Argument
from council.symbolic.argue.semantics.base import GradualSemantics


class _ConstantSemantics(GradualSemantics):
    """Test-only: every argument gets strength 0.5; preferred extension empty."""

    def evaluate(self, baf: QBAF) -> dict[str, float]:
        return {a.arg_id: 0.5 for a in baf.arguments}

    def preferred_extension(self, baf: QBAF) -> frozenset[str]:
        return frozenset()


class _MissingEvaluate(GradualSemantics):
    """Subclass missing `evaluate` — should fail to instantiate."""

    def preferred_extension(self, baf: QBAF) -> frozenset[str]:
        return frozenset()


class _MissingExtension(GradualSemantics):
    """Subclass missing `preferred_extension` — should fail to instantiate."""

    def evaluate(self, baf: QBAF) -> dict[str, float]:
        return {}


class TestGradualSemanticsABC:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            GradualSemantics()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self) -> None:
        sem = _ConstantSemantics()
        assert isinstance(sem, GradualSemantics)

    def test_subclass_missing_evaluate_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            _MissingEvaluate()  # type: ignore[abstract]

    def test_subclass_missing_extension_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            _MissingExtension()  # type: ignore[abstract]


class TestGradualSemanticsContract:
    def test_evaluate_is_sync(self) -> None:
        # Semantics are pure mathematical functions — no I/O, no async.
        assert not inspect.iscoroutinefunction(GradualSemantics.evaluate)

    def test_preferred_extension_is_sync(self) -> None:
        assert not inspect.iscoroutinefunction(GradualSemantics.preferred_extension)

    def test_evaluate_returns_dict_keyed_by_arg_id(self) -> None:
        sem = _ConstantSemantics()
        a = Argument(arg_id="a", claim_surface="x", base_score=0.4)
        b = Argument(arg_id="b", claim_surface="y", base_score=0.6)
        baf = QBAF(arguments=(a, b), attacks=(), supports=())
        strengths = sem.evaluate(baf)
        assert set(strengths.keys()) == {"a", "b"}
        assert strengths["a"] == 0.5
        assert strengths["b"] == 0.5

    def test_preferred_extension_returns_frozenset(self) -> None:
        sem = _ConstantSemantics()
        baf = QBAF(arguments=(), attacks=(), supports=())
        ext = sem.preferred_extension(baf)
        assert isinstance(ext, frozenset)


class TestPrepareHook:
    """ADR-0013: GradualSemantics ABC has a default no-op prepare(trace)
    hook that trace-aware semantics can override."""

    def test_default_prepare_returns_self(self) -> None:
        from council.dialect.trace import Trace

        sem = _ConstantSemantics()
        prepared = sem.prepare(Trace())
        assert prepared is sem

    def test_default_prepare_is_idempotent(self) -> None:
        """For stateless semantics, prepare(trace1) and prepare(trace2)
        return the same object (self)."""
        from council.dialect.moves import Claim, Propose
        from council.dialect.trace import Trace

        sem = _ConstantSemantics()
        t1 = Trace()
        t2 = Trace().append(
            Propose(
                move_id="p1",
                agent_id="A",
                round_index=0,
                claim=Claim(surface="x"),
                confidence=0.5,
            )
        )
        assert sem.prepare(t1) is sem
        assert sem.prepare(t2) is sem

    def test_prepare_signature_takes_trace_returns_semantics(self) -> None:
        import inspect

        from council.dialect.trace import Trace

        sig = inspect.signature(GradualSemantics.prepare)
        params = sig.parameters
        assert "trace" in params
        # Return type annotation: GradualSemantics
        # (we don't introspect the annotation string, just that prepare is sync)
        assert not inspect.iscoroutinefunction(GradualSemantics.prepare)
        # Default impl returns the semantics instance
        sem = _ConstantSemantics()
        assert isinstance(sem.prepare(Trace()), GradualSemantics)
