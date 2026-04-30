"""Tests for council/symbolic/argue/baf.py — frozen dataclasses for the QBAF.

These are pure unit tests over value objects. No model calls, no async, no
Trace dependency. The tests pin:
  - frozen+slots immutability (mutation rejected)
  - Attack/Support weight clamping to [0, 1] in __post_init__
  - QBAF structural invariants (no self-loops, edge endpoints reference
    declared arguments) raised on construction
  - QBAF.proposals() filters withdrawn arguments
  - hashability (so QBAFs can be cached / used as dict keys)
"""

from __future__ import annotations

import dataclasses

import pytest

from council.symbolic.argue.baf import QBAF, Argument, Attack, Support

# ---------------------------------------------------------------------------
# Argument
# ---------------------------------------------------------------------------


class TestArgument:
    def test_construct_with_all_defaults(self) -> None:
        arg = Argument(arg_id="a1", claim_surface="The sky is blue.", base_score=0.7)
        assert arg.arg_id == "a1"
        assert arg.claim_surface == "The sky is blue."
        assert arg.base_score == 0.7
        assert arg.withdrawn is False

    def test_withdrawn_defaults_false(self) -> None:
        arg = Argument(arg_id="a", claim_surface="x", base_score=0.5)
        assert arg.withdrawn is False

    def test_frozen_rejects_mutation(self) -> None:
        arg = Argument(arg_id="a", claim_surface="x", base_score=0.5)
        with pytest.raises(dataclasses.FrozenInstanceError):
            arg.base_score = 0.9  # type: ignore[misc]

    def test_class_uses_slots(self) -> None:
        # Slots design choice: no __dict__, fixed attributes.
        assert hasattr(Argument, "__slots__")
        assert "arg_id" in Argument.__slots__
        assert "claim_surface" in Argument.__slots__
        assert "base_score" in Argument.__slots__
        assert "withdrawn" in Argument.__slots__

    def test_hashable(self) -> None:
        arg = Argument(arg_id="a", claim_surface="x", base_score=0.5)
        # Hashable means usable as dict key / set member
        d = {arg: 1}
        assert d[arg] == 1

    def test_equality_by_value(self) -> None:
        a = Argument(arg_id="a", claim_surface="x", base_score=0.5)
        b = Argument(arg_id="a", claim_surface="x", base_score=0.5)
        assert a == b

    def test_inequality_when_arg_id_differs(self) -> None:
        a = Argument(arg_id="a", claim_surface="x", base_score=0.5)
        b = Argument(arg_id="b", claim_surface="x", base_score=0.5)
        assert a != b


# ---------------------------------------------------------------------------
# Attack
# ---------------------------------------------------------------------------


class TestAttack:
    def test_construct_in_range(self) -> None:
        edge = Attack(source="a1", target="a2", weight=0.8)
        assert edge.source == "a1"
        assert edge.target == "a2"
        assert edge.weight == 0.8

    def test_weight_clamped_above_one(self) -> None:
        edge = Attack(source="a", target="b", weight=2.5)
        assert edge.weight == 1.0

    def test_weight_clamped_below_zero(self) -> None:
        edge = Attack(source="a", target="b", weight=-0.3)
        assert edge.weight == 0.0

    def test_weight_zero_preserved(self) -> None:
        edge = Attack(source="a", target="b", weight=0.0)
        assert edge.weight == 0.0

    def test_weight_one_preserved(self) -> None:
        edge = Attack(source="a", target="b", weight=1.0)
        assert edge.weight == 1.0

    def test_frozen_rejects_mutation(self) -> None:
        edge = Attack(source="a", target="b", weight=0.5)
        with pytest.raises(dataclasses.FrozenInstanceError):
            edge.weight = 0.1  # type: ignore[misc]

    def test_hashable(self) -> None:
        edge = Attack(source="a", target="b", weight=0.5)
        assert {edge}  # set membership requires hash


# ---------------------------------------------------------------------------
# Support
# ---------------------------------------------------------------------------


class TestSupport:
    def test_construct_in_range(self) -> None:
        edge = Support(source="a1", target="a2", weight=0.6)
        assert edge.source == "a1"
        assert edge.target == "a2"
        assert edge.weight == 0.6

    def test_weight_default_is_one(self) -> None:
        edge = Support(source="a", target="b")
        assert edge.weight == 1.0

    def test_weight_clamped_above_one(self) -> None:
        edge = Support(source="a", target="b", weight=1.7)
        assert edge.weight == 1.0

    def test_weight_clamped_below_zero(self) -> None:
        edge = Support(source="a", target="b", weight=-1.0)
        assert edge.weight == 0.0

    def test_frozen_rejects_mutation(self) -> None:
        edge = Support(source="a", target="b")
        with pytest.raises(dataclasses.FrozenInstanceError):
            edge.weight = 0.4  # type: ignore[misc]


# ---------------------------------------------------------------------------
# QBAF — construction-time validation + queries
# ---------------------------------------------------------------------------


def _arg(arg_id: str, *, score: float = 0.5, withdrawn: bool = False) -> Argument:
    return Argument(arg_id=arg_id, claim_surface=f"surface-{arg_id}", base_score=score, withdrawn=withdrawn)


class TestQBAFConstruction:
    def test_empty_qbaf(self) -> None:
        baf = QBAF(arguments=(), attacks=(), supports=())
        assert baf.arguments == ()
        assert baf.attacks == ()
        assert baf.supports == ()

    def test_single_argument_no_edges(self) -> None:
        a = _arg("a1")
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert baf.arguments == (a,)

    def test_two_arguments_with_attack(self) -> None:
        a, b = _arg("a"), _arg("b")
        edge = Attack(source="a", target="b", weight=0.5)
        baf = QBAF(arguments=(a, b), attacks=(edge,), supports=())
        assert baf.attacks == (edge,)

    def test_self_attack_rejected(self) -> None:
        a = _arg("a")
        with pytest.raises(ValueError, match="self-loop"):
            QBAF(arguments=(a,), attacks=(Attack(source="a", target="a", weight=0.5),), supports=())

    def test_self_support_rejected(self) -> None:
        a = _arg("a")
        with pytest.raises(ValueError, match="self-loop"):
            QBAF(arguments=(a,), attacks=(), supports=(Support(source="a", target="a"),))

    def test_dangling_attack_source_rejected(self) -> None:
        a = _arg("a")
        with pytest.raises(ValueError, match="unknown argument"):
            QBAF(arguments=(a,), attacks=(Attack(source="ghost", target="a", weight=0.5),), supports=())

    def test_dangling_attack_target_rejected(self) -> None:
        a = _arg("a")
        with pytest.raises(ValueError, match="unknown argument"):
            QBAF(arguments=(a,), attacks=(Attack(source="a", target="ghost", weight=0.5),), supports=())

    def test_dangling_support_endpoint_rejected(self) -> None:
        a = _arg("a")
        with pytest.raises(ValueError, match="unknown argument"):
            QBAF(arguments=(a,), attacks=(), supports=(Support(source="a", target="ghost"),))

    def test_duplicate_arg_id_rejected(self) -> None:
        a1, a2 = _arg("a"), _arg("a", score=0.9)
        with pytest.raises(ValueError, match="duplicate argument"):
            QBAF(arguments=(a1, a2), attacks=(), supports=())


class TestQBAFQueries:
    def test_proposals_filters_withdrawn(self) -> None:
        a = _arg("a", withdrawn=False)
        b = _arg("b", withdrawn=True)
        c = _arg("c", withdrawn=False)
        baf = QBAF(arguments=(a, b, c), attacks=(), supports=())
        assert baf.proposals() == (a, c)

    def test_proposals_empty_when_all_withdrawn(self) -> None:
        a = _arg("a", withdrawn=True)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert baf.proposals() == ()

    def test_proposals_preserves_order(self) -> None:
        a, b, c = _arg("a"), _arg("b"), _arg("c")
        baf = QBAF(arguments=(c, a, b), attacks=(), supports=())
        # Insertion order preserved
        assert baf.proposals() == (c, a, b)


class TestQBAFImmutability:
    def test_frozen_rejects_mutation(self) -> None:
        baf = QBAF(arguments=(), attacks=(), supports=())
        with pytest.raises(dataclasses.FrozenInstanceError):
            baf.arguments = (_arg("a"),)  # type: ignore[misc]

    def test_class_uses_slots(self) -> None:
        assert hasattr(QBAF, "__slots__")
        assert set(QBAF.__slots__) == {"arguments", "attacks", "supports"}

    def test_hashable_when_built_from_tuples(self) -> None:
        a = _arg("a")
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        # tuple-of-frozen-dataclasses is hashable
        d = {baf: "ok"}
        assert d[baf] == "ok"

    def test_equality_by_value(self) -> None:
        a = _arg("a")
        baf1 = QBAF(arguments=(a,), attacks=(), supports=())
        baf2 = QBAF(arguments=(a,), attacks=(), supports=())
        assert baf1 == baf2
