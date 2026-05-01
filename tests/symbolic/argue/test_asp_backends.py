"""Tests for council/symbolic/argue/asp_backends.py — Dung extension semantics.

Per ADR-0014:
  - grounded_extension is pure Python (no clingo); always tested.
  - preferred_extensions and stable_extensions require clingo
    (`[argue-asp]` extra); tests gate via `pytest.importorskip("clingo")`.

Extensions are computed over the attack subgraph only — supports do
NOT affect extension membership (Dung 1995 classical AAFs).
"""

from __future__ import annotations

import pytest

from council.symbolic.argue.asp_backends import (
    grounded_extension,
    preferred_extensions,
    stable_extensions,
)
from council.symbolic.argue.baf import QBAF, Argument, Attack, Support


def _arg(arg_id: str, *, withdrawn: bool = False) -> Argument:
    return Argument(
        arg_id=arg_id,
        claim_surface=f"surface-{arg_id}",
        base_score=0.5,
        withdrawn=withdrawn,
    )


# ---------------------------------------------------------------------------
# Module import structure: clingo is gated, grounded works without it
# ---------------------------------------------------------------------------


class TestModuleImportGating:
    def test_module_imports_without_clingo(self) -> None:
        """The module is import-safe even when clingo is missing — but the
        clingo-dependent functions raise at call time. (We can't simulate
        absence here; we just verify the module imports cleanly.)"""
        import council.symbolic.argue.asp_backends as asp

        assert hasattr(asp, "grounded_extension")
        assert hasattr(asp, "preferred_extensions")
        assert hasattr(asp, "stable_extensions")


# ---------------------------------------------------------------------------
# Grounded extension (pure Python; always available)
# ---------------------------------------------------------------------------


class TestGroundedExtension:
    """Dung 1995 grounded extension: least fixed point of the characteristic
    function F(S) = { a : every attacker of a is attacked by some member of S }.
    Always exists and is unique for any AAF."""

    def test_empty_qbaf_returns_empty_set(self) -> None:
        baf = QBAF(arguments=(), attacks=(), supports=())
        assert grounded_extension(baf) == frozenset()

    def test_single_unattacked_argument_in_grounded(self) -> None:
        baf = QBAF(arguments=(_arg("a"),), attacks=(), supports=())
        assert grounded_extension(baf) == frozenset({"a"})

    def test_two_arguments_no_attacks_both_in_grounded(self) -> None:
        baf = QBAF(arguments=(_arg("a"), _arg("b")), attacks=(), supports=())
        assert grounded_extension(baf) == frozenset({"a", "b"})

    def test_two_argument_cycle_grounded_is_empty(self) -> None:
        """Mutual attack a<->b: neither is acceptable in grounded. The
        unique least fixed point is empty."""
        baf = QBAF(
            arguments=(_arg("a"), _arg("b")),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="a", weight=1.0),
            ),
            supports=(),
        )
        assert grounded_extension(baf) == frozenset()

    def test_three_argument_chain_grounded(self) -> None:
        """a -> b -> c. a is unattacked; b is attacked by a (in grounded).
        c is attacked by b but b is defeated by a, so c is acceptable."""
        baf = QBAF(
            arguments=(_arg("a"), _arg("b"), _arg("c")),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="c", weight=1.0),
            ),
            supports=(),
        )
        assert grounded_extension(baf) == frozenset({"a", "c"})

    def test_attacker_defended_by_other_arg(self) -> None:
        """a -> b, c -> a. c attacks a; a's attack on b is no longer
        unchallenged. Grounded computes: c unattacked (in); c attacks a
        so a is defeated; b's attacker (a) is defeated, so b is in."""
        baf = QBAF(
            arguments=(_arg("a"), _arg("b"), _arg("c")),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="c", target="a", weight=1.0),
            ),
            supports=(),
        )
        assert grounded_extension(baf) == frozenset({"b", "c"})

    def test_supports_do_not_affect_grounded(self) -> None:
        """Per ADR-0014 Q2: extension semantics ignore the support relation."""
        baf = QBAF(
            arguments=(_arg("a"), _arg("b")),
            attacks=(),
            supports=(Support(source="a", target="b", weight=1.0),),
        )
        # Both unattacked -> both in grounded; support is irrelevant
        assert grounded_extension(baf) == frozenset({"a", "b"})

    def test_withdrawn_excluded_from_grounded(self) -> None:
        """ADR-0010 / ADR-0014 Q3: withdrawn args are not in play."""
        baf = QBAF(
            arguments=(_arg("a"), _arg("b", withdrawn=True)),
            attacks=(Attack(source="a", target="b", weight=1.0),),
            supports=(),
        )
        # b is withdrawn -> excluded; a is unattacked (b's withdrawn)
        result = grounded_extension(baf)
        assert "a" in result
        assert "b" not in result

    def test_grounded_is_unique_byte_equal_50_invocations(self) -> None:
        baf = QBAF(
            arguments=(_arg("a"), _arg("b"), _arg("c")),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="c", weight=1.0),
            ),
            supports=(),
        )
        first = grounded_extension(baf)
        for _ in range(50):
            assert grounded_extension(baf) == first


# ---------------------------------------------------------------------------
# Preferred extensions (clingo-gated)
# ---------------------------------------------------------------------------


class TestPreferredExtensions:
    """Maximal admissible sets. Multiple preferred extensions may exist."""

    @pytest.fixture(autouse=True)
    def _require_clingo(self) -> None:
        pytest.importorskip("clingo")

    def test_empty_qbaf_returns_singleton_empty(self) -> None:
        """The empty set is the only admissible set in an empty AAF."""
        baf = QBAF(arguments=(), attacks=(), supports=())
        result = preferred_extensions(baf)
        assert result == frozenset({frozenset()})

    def test_single_argument_returns_singleton_set(self) -> None:
        baf = QBAF(arguments=(_arg("a"),), attacks=(), supports=())
        result = preferred_extensions(baf)
        assert result == frozenset({frozenset({"a"})})

    def test_two_argument_cycle_two_preferred(self) -> None:
        """a <-> b: two preferred extensions, {a} and {b}."""
        baf = QBAF(
            arguments=(_arg("a"), _arg("b")),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="a", weight=1.0),
            ),
            supports=(),
        )
        result = preferred_extensions(baf)
        assert result == frozenset({frozenset({"a"}), frozenset({"b"})})

    def test_chain_preferred_equals_grounded(self) -> None:
        """For acyclic AAFs, the unique preferred extension equals the
        grounded extension."""
        baf = QBAF(
            arguments=(_arg("a"), _arg("b"), _arg("c")),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="c", weight=1.0),
            ),
            supports=(),
        )
        result = preferred_extensions(baf)
        assert result == frozenset({frozenset({"a", "c"})})

    def test_returns_frozenset_of_frozensets(self) -> None:
        baf = QBAF(arguments=(_arg("a"),), attacks=(), supports=())
        result = preferred_extensions(baf)
        assert isinstance(result, frozenset)
        for ext in result:
            assert isinstance(ext, frozenset)

    def test_supports_do_not_affect_preferred(self) -> None:
        baf = QBAF(
            arguments=(_arg("a"), _arg("b")),
            attacks=(),
            supports=(Support(source="a", target="b", weight=1.0),),
        )
        # Both unattacked -> {a, b} is the unique preferred extension
        result = preferred_extensions(baf)
        assert result == frozenset({frozenset({"a", "b"})})

    def test_withdrawn_excluded_from_preferred(self) -> None:
        baf = QBAF(
            arguments=(_arg("a"), _arg("b", withdrawn=True)),
            attacks=(),
            supports=(),
        )
        result = preferred_extensions(baf)
        # Only "a" appears in extensions (b is withdrawn → excluded)
        all_args_in_extensions = set().union(*result)
        assert "a" in all_args_in_extensions
        assert "b" not in all_args_in_extensions

    def test_determinism_50_invocations(self) -> None:
        baf = QBAF(
            arguments=(_arg("a"), _arg("b")),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="a", weight=1.0),
            ),
            supports=(),
        )
        first = preferred_extensions(baf)
        for _ in range(50):
            assert preferred_extensions(baf) == first


# ---------------------------------------------------------------------------
# Stable extensions (clingo-gated)
# ---------------------------------------------------------------------------


class TestStableExtensions:
    """Conflict-free sets that attack every non-member. May not exist
    (returns empty frozenset of frozensets)."""

    @pytest.fixture(autouse=True)
    def _require_clingo(self) -> None:
        pytest.importorskip("clingo")

    def test_empty_qbaf_returns_singleton_empty(self) -> None:
        """The empty set is stable in the empty AAF (vacuously attacks
        every non-member, of which there are none)."""
        baf = QBAF(arguments=(), attacks=(), supports=())
        result = stable_extensions(baf)
        assert result == frozenset({frozenset()})

    def test_single_unattacked_argument_in_stable(self) -> None:
        baf = QBAF(arguments=(_arg("a"),), attacks=(), supports=())
        result = stable_extensions(baf)
        assert result == frozenset({frozenset({"a"})})

    def test_two_argument_cycle_two_stable(self) -> None:
        """a <-> b: two stable extensions, {a} and {b}."""
        baf = QBAF(
            arguments=(_arg("a"), _arg("b")),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="a", weight=1.0),
            ),
            supports=(),
        )
        result = stable_extensions(baf)
        assert result == frozenset({frozenset({"a"}), frozenset({"b"})})

    def test_three_argument_cycle_no_stable(self) -> None:
        """a -> b -> c -> a (3-cycle): no stable extension exists.
        Result is empty frozenset (no extensions found)."""
        baf = QBAF(
            arguments=(_arg("a"), _arg("b"), _arg("c")),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="c", weight=1.0),
                Attack(source="c", target="a", weight=1.0),
            ),
            supports=(),
        )
        result = stable_extensions(baf)
        assert result == frozenset()

    def test_chain_stable_equals_grounded(self) -> None:
        baf = QBAF(
            arguments=(_arg("a"), _arg("b"), _arg("c")),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="c", weight=1.0),
            ),
            supports=(),
        )
        result = stable_extensions(baf)
        assert result == frozenset({frozenset({"a", "c"})})

    def test_returns_frozenset_of_frozensets(self) -> None:
        baf = QBAF(arguments=(_arg("a"),), attacks=(), supports=())
        result = stable_extensions(baf)
        assert isinstance(result, frozenset)
        for ext in result:
            assert isinstance(ext, frozenset)

    def test_supports_do_not_affect_stable(self) -> None:
        baf = QBAF(
            arguments=(_arg("a"), _arg("b")),
            attacks=(),
            supports=(Support(source="a", target="b", weight=1.0),),
        )
        result = stable_extensions(baf)
        assert result == frozenset({frozenset({"a", "b"})})

    def test_withdrawn_excluded_from_stable(self) -> None:
        baf = QBAF(
            arguments=(_arg("a"), _arg("b", withdrawn=True)),
            attacks=(),
            supports=(),
        )
        result = stable_extensions(baf)
        all_args_in_extensions: set[str] = set()
        for ext in result:
            all_args_in_extensions.update(ext)
        assert "a" in all_args_in_extensions
        assert "b" not in all_args_in_extensions


# ---------------------------------------------------------------------------
# Walton-Krabbe canonical
# ---------------------------------------------------------------------------


class TestWaltonKrabbeExtensions:
    """Sanity check on the canonical W2/PR2 fixture's attack subgraph.
    The fixture has one attack (c1 -> p1) and one support (co1 -> p2);
    extensions ignore supports. The attack subgraph is a 4-arg DAG with
    one attack edge."""

    def _walton_krabbe(self) -> QBAF:
        return QBAF(
            arguments=(
                _arg("p1"),
                _arg("p2"),
                _arg("c1"),
                _arg("co1"),
            ),
            attacks=(Attack(source="c1", target="p1", weight=0.7),),
            supports=(Support(source="co1", target="p2", weight=1.0),),
        )

    def test_grounded(self) -> None:
        result = grounded_extension(self._walton_krabbe())
        # c1 is unattacked -> in; c1 attacks p1 -> p1 out;
        # p2, co1 unattacked -> in; result = {c1, p2, co1}
        assert result == frozenset({"c1", "p2", "co1"})

    def test_preferred_equals_grounded_on_dag(self) -> None:
        pytest.importorskip("clingo")
        result = preferred_extensions(self._walton_krabbe())
        assert result == frozenset({frozenset({"c1", "p2", "co1"})})

    def test_stable_equals_grounded_on_dag(self) -> None:
        pytest.importorskip("clingo")
        result = stable_extensions(self._walton_krabbe())
        assert result == frozenset({frozenset({"c1", "p2", "co1"})})
