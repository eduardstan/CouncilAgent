"""Tests for council/symbolic/argue/semantics/euler.py — Ebs (Amgoud-Ben-Naim 2018).

Ebs is the "Exponent-based restricted semantics" from Amgoud-Ben-Naim 2018
(IJAR), Definition 19. The bible refers to it as "Euler-based"; the W2 class
name `EulerBasedSemantics` matches the bible nomenclature.

Closed-form (acyclic):

  f(a) = 1 - (1 - w(a)^2) / (1 + w(a) * 2^E)
  E = sum(weight * f(x)) over supporters
     - sum(weight * f(x)) over attackers

W2 design per ADR-0011: edges weighted, withdrawn args contribute 0, cycles
raise. Boundary degeneracy at w(a) = 0 / 1 is faithful to the paper formula.
"""

from __future__ import annotations

import math

import pytest

from council.symbolic.argue.baf import QBAF, Argument, Attack, Support
from council.symbolic.argue.semantics.euler import EulerBasedSemantics


def _arg(arg_id: str, *, base: float = 0.5, withdrawn: bool = False) -> Argument:
    return Argument(
        arg_id=arg_id,
        claim_surface=f"surface-{arg_id}",
        base_score=base,
        withdrawn=withdrawn,
    )


def _ebs_formula(w: float, energy: float) -> float:
    """Reference implementation of f(a) = 1 - (1 - w^2) / (1 + w * 2^E)."""
    return 1.0 - (1.0 - w * w) / (1.0 + w * (2.0**energy))


# ---------------------------------------------------------------------------
# Empty / degenerate
# ---------------------------------------------------------------------------


class TestEbsEmpty:
    def test_empty_qbaf_returns_empty_dict(self) -> None:
        sem = EulerBasedSemantics()
        assert sem.evaluate(QBAF(arguments=(), attacks=(), supports=())) == {}

    def test_no_edges_returns_base(self) -> None:
        """E = 0 -> f(a) = 1 - (1-w^2)/(1+w) = 1 - (1-w) = w."""
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.42)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert sem.evaluate(baf)["a"] == pytest.approx(0.42)

    def test_no_edges_returns_base_for_various_w(self) -> None:
        sem = EulerBasedSemantics()
        for w in [0.1, 0.3, 0.5, 0.7, 0.9]:
            a = _arg("a", base=w)
            baf = QBAF(arguments=(a,), attacks=(), supports=())
            assert sem.evaluate(baf)["a"] == pytest.approx(w)


# ---------------------------------------------------------------------------
# Closed-form formula (Definition 19)
# ---------------------------------------------------------------------------


class TestEbsFormula:
    def test_supporter_only_increases_strength(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.6)
        baf = QBAF(
            arguments=(a, b),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        # E = 0.6; expected = 1 - (1-0.25)/(1 + 0.5 * 2^0.6)
        expected = _ebs_formula(0.5, 0.6)
        assert sem.evaluate(baf)["a"] == pytest.approx(expected)
        assert sem.evaluate(baf)["a"] > 0.5  # strength increased

    def test_attacker_only_decreases_strength(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.6)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        expected = _ebs_formula(0.5, -0.6)
        assert sem.evaluate(baf)["a"] == pytest.approx(expected)
        assert sem.evaluate(baf)["a"] < 0.5  # strength decreased

    def test_balanced_returns_base(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.6)
        c = _arg("c", base=0.6)
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(Support(source="c", target="a", weight=1.0),),
        )
        # E = 0.6 - 0.6 = 0; f(a) = base = 0.5
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Boundary degeneracy (ADR-0011 Q3 — faithful to paper)
# ---------------------------------------------------------------------------


class TestEbsBoundaryDegeneracy:
    """Per Definition 19, at w(a) = 0: f(a) = 1 - 1 / (1 + 0) = 0 (frozen).
    At w(a) = 1: f(a) = 1 - 0 / (1 + 2^E) = 1 (frozen).
    PR4 ships these without intervention (ADR-0011 Q3); the aggregator
    defaults to DF-QuAD which has no such degeneracy."""

    def test_zero_base_is_frozen_at_zero(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.0)
        b = _arg("b", base=0.9)
        baf = QBAF(
            arguments=(a, b),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        assert sem.evaluate(baf)["a"] == pytest.approx(0.0)

    def test_one_base_is_frozen_at_one(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=0.9)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        assert sem.evaluate(baf)["a"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Edge weights (W2 extension)
# ---------------------------------------------------------------------------


class TestEbsEdgeWeights:
    def test_attack_weight_zero_has_no_effect(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.9)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=0.0),),
            supports=(),
        )
        # E = 0; f = base
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)

    def test_full_weight_attack_decreases_more_than_half_weight(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.9)
        baf_full = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        baf_half = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=0.5),),
            supports=(),
        )
        s_full = sem.evaluate(baf_full)["a"]
        s_half = sem.evaluate(baf_half)["a"]
        assert s_full < s_half < 0.5


# ---------------------------------------------------------------------------
# Withdrawn handling
# ---------------------------------------------------------------------------


class TestEbsWithdrawn:
    def test_withdrawn_strength_is_zero(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.9, withdrawn=True)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert sem.evaluate(baf)["a"] == 0.0

    def test_withdrawn_attacker_contributes_zero(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.9, withdrawn=True)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        # b withdrawn -> contributes 0 -> E=0 -> f=base=0.5
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


class TestEbsCycleDetection:
    def test_two_cycle_raises(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.5)
        baf = QBAF(
            arguments=(a, b),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="a", weight=1.0),
            ),
            supports=(),
        )
        with pytest.raises(ValueError, match="cycle"):
            sem.evaluate(baf)


# ---------------------------------------------------------------------------
# Boundedness + Determinism
# ---------------------------------------------------------------------------


class TestEbsInvariants:
    def test_strengths_in_unit_interval(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.6)
        c = _arg("c", base=0.4)
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(Attack(source="c", target="a", weight=0.7),),
            supports=(Support(source="b", target="a", weight=0.5),),
        )
        for v in sem.evaluate(baf).values():
            assert 0.0 <= v <= 1.0
            assert math.isfinite(v)

    def test_byte_equal_over_50_invocations(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.4)
        c = _arg("c", base=0.6)
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(Attack(source="b", target="a", weight=0.7),),
            supports=(Support(source="c", target="a", weight=0.5),),
        )
        first = sem.evaluate(baf)
        for _ in range(50):
            assert sem.evaluate(baf) == first

    def test_argument_order_independent(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.4)
        c = _arg("c", base=0.6)
        baf1 = QBAF(
            arguments=(a, b, c),
            attacks=(Attack(source="b", target="a", weight=0.7),),
            supports=(Support(source="c", target="a", weight=0.5),),
        )
        baf2 = QBAF(
            arguments=(c, a, b),
            attacks=(Attack(source="b", target="a", weight=0.7),),
            supports=(Support(source="c", target="a", weight=0.5),),
        )
        assert sem.evaluate(baf1) == sem.evaluate(baf2)


# ---------------------------------------------------------------------------
# Preferred extension
# ---------------------------------------------------------------------------


class TestEbsPreferredExtension:
    def test_high_strength_in_extension(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.9)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert "a" in sem.preferred_extension(baf)

    def test_withdrawn_excluded(self) -> None:
        sem = EulerBasedSemantics()
        a = _arg("a", base=0.9, withdrawn=True)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert "a" not in sem.preferred_extension(baf)
