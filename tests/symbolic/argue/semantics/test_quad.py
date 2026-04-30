"""Tests for council/symbolic/argue/semantics/quad.py — Quadratic Energy.

QE is from Potyka 2018, "Continuous dynamical systems for weighted bipolar
argumentation" (KR). The W2 generalisation matches ADR-0010 + ADR-0011:
weighted edges multiply source strength, withdrawn args contribute 0,
cycles raise ValueError.

Closed-form acyclic equilibrium (Proposition 2):

  s_j* = w(j) + (1 - w(j)) * h(E_j) - w(j) * h(-E_j)

  E_j = sum(weight * strength) over supporters
       - sum(weight * strength) over attackers
  h(x) = max(x, 0)^2 / (1 + max(x, 0)^2)
"""

from __future__ import annotations

import math

import pytest

from council.symbolic.argue.baf import QBAF, Argument, Attack, Support
from council.symbolic.argue.semantics.quad import QESemantics


def _arg(arg_id: str, *, base: float = 0.5, withdrawn: bool = False) -> Argument:
    return Argument(
        arg_id=arg_id,
        claim_surface=f"surface-{arg_id}",
        base_score=base,
        withdrawn=withdrawn,
    )


# ---------------------------------------------------------------------------
# Empty / degenerate
# ---------------------------------------------------------------------------


class TestQEEmpty:
    def test_empty_qbaf_returns_empty_dict(self) -> None:
        sem = QESemantics()
        assert sem.evaluate(QBAF(arguments=(), attacks=(), supports=())) == {}

    def test_single_unattacked_argument_strength_equals_base(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.7)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        # E = 0; h(0) = 0; h(-0) = 0; s = 0.7 + 0 - 0 = 0.7
        assert sem.evaluate(baf)["a"] == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Closed-form formula (Proposition 2)
# ---------------------------------------------------------------------------


class TestQEFormula:
    def test_supporter_only_pushes_toward_one(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.8)
        baf = QBAF(
            arguments=(a, b),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        # E_a = 0.8; h(0.8) = 0.64/1.64 ≈ 0.3902
        # s_a = 0.5 + 0.5 * 0.3902 = 0.6951
        h_pos = 0.8 * 0.8 / (1 + 0.8 * 0.8)
        expected = 0.5 + 0.5 * h_pos
        assert sem.evaluate(baf)["a"] == pytest.approx(expected)

    def test_attacker_only_pushes_toward_zero(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.8)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        # E_a = -0.8; h(-(-0.8)) = h(0.8) ≈ 0.3902
        # s_a = 0.5 - 0.5 * 0.3902 = 0.3049
        h_neg = 0.8 * 0.8 / (1 + 0.8 * 0.8)
        expected = 0.5 - 0.5 * h_neg
        assert sem.evaluate(baf)["a"] == pytest.approx(expected)

    def test_balanced_attacker_supporter_equal_strengths_returns_base(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.6)
        c = _arg("c", base=0.6)
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(Support(source="c", target="a", weight=1.0),),
        )
        # E_a = 0.6 - 0.6 = 0; h(0) = 0; h(-0) = 0; s = base = 0.5
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)

    def test_zero_base_with_strong_supporter_recovers_value(self) -> None:
        """Boundary-ish: w=0 + supporter. Per QE formula, s = 0 + 1*h(E) - 0*h(-E)
        = h(E). Unlike Ebs, QE recovers from zero base."""
        sem = QESemantics()
        a = _arg("a", base=0.0)
        b = _arg("b", base=0.9)
        baf = QBAF(
            arguments=(a, b),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        h_pos = 0.9 * 0.9 / (1 + 0.9 * 0.9)
        # s_a = 0 + 1*h_pos - 0 = h_pos ≈ 0.4475
        assert sem.evaluate(baf)["a"] == pytest.approx(h_pos)

    def test_one_base_with_strong_attacker_pulls_down(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=0.9)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        h_neg = 0.9 * 0.9 / (1 + 0.9 * 0.9)
        # s_a = 1 + 0*h_pos - 1*h_neg = 1 - h_neg ≈ 0.5525
        assert sem.evaluate(baf)["a"] == pytest.approx(1.0 - h_neg)


# ---------------------------------------------------------------------------
# Edge weights (W2 extension; ADR-0011 Q1 + ADR-0010 Q1)
# ---------------------------------------------------------------------------


class TestQEEdgeWeights:
    def test_attack_weight_zero_has_no_effect(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.9)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=0.0),),
            supports=(),
        )
        # Effective contribution = 0; E = 0; s = base = 0.5
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)

    def test_attack_weight_half_dampens(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.8)
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
        # Half-weight attack reduces a less than full-weight attack
        assert s_half > s_full
        # Half-weight result is between no-attack (0.5) and full-attack
        assert 0.5 > s_half > s_full


# ---------------------------------------------------------------------------
# Withdrawn handling (ADR-0010 Q2)
# ---------------------------------------------------------------------------


class TestQEWithdrawn:
    def test_withdrawn_strength_is_zero(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.9, withdrawn=True)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert sem.evaluate(baf)["a"] == 0.0

    def test_withdrawn_attacker_contributes_zero(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.9, withdrawn=True)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        # b withdrawn → contributes 0 → E=0 → s=base=0.5
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Cycle detection (ADR-0011 Q1 — raise on cycle)
# ---------------------------------------------------------------------------


class TestQECycleDetection:
    def test_two_cycle_raises(self) -> None:
        sem = QESemantics()
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
# Bounded strength (Lemma 1 in Potyka 2018)
# ---------------------------------------------------------------------------


class TestQEBoundedness:
    def test_strengths_in_unit_interval(self) -> None:
        sem = QESemantics()
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

    def test_max_attacker_drives_to_zero(self) -> None:
        """Saturation: with base=1 and a max-strength attacker, h(-E) ≈ 0.5,
        so s ≈ 1 - 0.5 = 0.5 (NOT 0; QE is more conservative than DF-QuAD)."""
        sem = QESemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=1.0)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        # E_a = -1; h(-(-1)) = h(1) = 1/(1+1) = 0.5; s = 1 - 1*0.5 = 0.5
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Determinism + Order independence
# ---------------------------------------------------------------------------


class TestQEDeterminism:
    def test_byte_equal_over_50_invocations(self) -> None:
        sem = QESemantics()
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
        sem = QESemantics()
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
# Preferred extension (ADR-0010 Q4)
# ---------------------------------------------------------------------------


class TestQEPreferredExtension:
    def test_high_strength_in_extension(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.9)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert "a" in sem.preferred_extension(baf)

    def test_low_strength_excluded(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.1)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert "a" not in sem.preferred_extension(baf)

    def test_withdrawn_excluded(self) -> None:
        sem = QESemantics()
        a = _arg("a", base=0.9, withdrawn=True)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert "a" not in sem.preferred_extension(baf)
