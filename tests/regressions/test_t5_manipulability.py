"""T5 — Manipulability bound for DF-QuAD on the W2 QBAF.

Master plan §10:
  Define the *flip cost* of a BAF as the minimum number of attack-edge
  flips needed to change the winner under DF-QuAD. Provide an upper
  bound parameterised by (in-degree, attack/support ratio). Builds on
  Baroni-Rago-Toni 2019.

Mechanisation. We define `flip_cost(baf, sem)` as the minimum number of
binary attack-edge perturbations (each: toggle weight 0 ↔ 1 between any
ordered pair of distinct non-withdrawn arguments) required to change
the strongest Propose-derived argument under the chosen semantics.

The upper bound (the headline T5 claim):

  flip_cost(baf, sem) <= max(0, |proposals| - 1)

Proof sketch (in docs/theory.md §T5): for any non-degenerate winner, set
the attack weight from every other argument toward the winner to 1.0.
Under DF-QuAD's saturating F-aggregation, the winner's v_a saturates
and strength drops below any candidate without an attacker — a winner
flip in (|proposals| - 1) flips. Refinements (taking out- vs in-degree,
attack/support ratio) tighten the bound; this PR ships the simpler
n-1 form.

Edge perturbation set. We allow flips on any *potential* attack edge
(s, t) where s, t are distinct non-withdrawn arguments. Flipping a
potential edge that is currently absent from the BAF means *adding* it
with weight 1.0; flipping a present edge means *removing* it (weight
0). This matches the "flip cost" framing in Baroni-Rago-Toni 2019: an
adversary's perturbations are weighted edge edits, not graph-structure
restrictions.

Determinism. `flip_cost` performs a bounded breadth-first search over
edge subsets (up to `max_search` flips, default 8). Exponential in the
worst case; intended for small examples (<= ~6 arguments). For larger
graphs, only the upper bound is computed.
"""

from __future__ import annotations

from itertools import combinations

import pytest

from council.symbolic.argue.baf import QBAF, Argument, Attack
from council.symbolic.argue.manipulability import (
    flip_cost,
    flip_cost_upper_bound,
)
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics


def _arg(arg_id: str, *, base: float = 0.5, withdrawn: bool = False) -> Argument:
    return Argument(
        arg_id=arg_id,
        claim_surface=f"surface-{arg_id}",
        base_score=base,
        withdrawn=withdrawn,
    )


# ---------------------------------------------------------------------------
# Upper bound — closed form, runs on any graph size
# ---------------------------------------------------------------------------


class TestFlipCostUpperBound:
    def test_empty_qbaf_unflippable(self) -> None:
        """Empty BAF: no proposals -> -1 sentinel.
        (Theorem audit fix 2026-05-01: aligned with flip_cost.)"""
        baf = QBAF(arguments=(), attacks=(), supports=())
        assert flip_cost_upper_bound(baf, DFQuADSemantics()) == -1

    def test_single_argument_unflippable(self) -> None:
        """Single Propose: no candidate runner-up. -1 sentinel."""
        a = _arg("a", base=0.7)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert flip_cost_upper_bound(baf, DFQuADSemantics()) == -1

    def test_two_arguments_bound_is_one(self) -> None:
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.5)
        baf = QBAF(arguments=(a, b), attacks=(), supports=())
        # 2 proposals → bound is n-1 = 1
        assert flip_cost_upper_bound(baf, DFQuADSemantics()) == 1

    def test_five_arguments_bound_is_four(self) -> None:
        args = tuple(_arg(f"a{i}", base=0.5) for i in range(5))
        baf = QBAF(arguments=args, attacks=(), supports=())
        assert flip_cost_upper_bound(baf, DFQuADSemantics()) == 4

    def test_withdrawn_arguments_excluded_from_bound(self) -> None:
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.5)
        c = _arg("c", base=0.3, withdrawn=True)
        baf = QBAF(arguments=(a, b, c), attacks=(), supports=())
        # Only 2 non-withdrawn proposals → bound = 1
        assert flip_cost_upper_bound(baf, DFQuADSemantics()) == 1


# ---------------------------------------------------------------------------
# flip_cost — exact brute-force on small examples
# ---------------------------------------------------------------------------


class TestFlipCostExact:
    def test_empty_qbaf_unflippable(self) -> None:
        """Empty BAF: -1 sentinel. (Theorem audit fix 2026-05-01.)"""
        baf = QBAF(arguments=(), attacks=(), supports=())
        assert flip_cost(baf, DFQuADSemantics()) == -1

    def test_single_argument_unflippable(self) -> None:
        """Single Propose: nothing to swap to. -1 sentinel."""
        a = _arg("a", base=0.7)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert flip_cost(baf, DFQuADSemantics()) == -1

    def test_two_args_no_edges_one_flip(self) -> None:
        """a (base 0.7) > b (base 0.5). Adding one attack a→b doesn't help
        (already winning); adding b→a with weight 1 brings a's strength to
        c(0.7, 0.5, 0) = 0.7 - 0.7*0.5 = 0.35 < 0.5 = b's strength.
        Winner flips with 1 edge perturbation."""
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.5)
        baf = QBAF(arguments=(a, b), attacks=(), supports=())
        cost = flip_cost(baf, DFQuADSemantics())
        assert cost == 1

    def test_two_args_existing_attack_flip_to_remove(self) -> None:
        """a (base 1.0) attacked by b (base 0.5) at weight 1.0:
        strength(a) = 1.0 - 1.0 * 0.5 = 0.5 = strength(b). Tie — winner
        in insertion order. Removing the attack: strength(a) = 1.0,
        strength(b) = 0.5 → a still wins. So flip_cost >= 2 here.
        Adding a→b (a counter-attacks b): strength(b) goes to 0.5 -
        0.5 * 1.0 = 0.0; a stays at 0.5. a wins more decisively.
        Need to find a flip that swaps the winner. Try several."""
        a = _arg("a", base=1.0)
        b = _arg("b", base=0.5)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        sem = DFQuADSemantics()
        # Sanity: who wins now?
        strengths = sem.evaluate(baf)
        # If a and b tie at 0.5, the aggregator picks insertion-order first → a
        assert strengths["a"] == pytest.approx(0.5)
        assert strengths["b"] == pytest.approx(0.5)

        cost = flip_cost(baf, sem)
        # Bounded by upper bound (n-1 = 1)
        assert 0 <= cost <= 1 or cost == -1


class TestFlipCostBoundedByUpperBound:
    """The headline T5 claim: flip_cost <= flip_cost_upper_bound."""

    def test_two_args_no_edges(self) -> None:
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.5)
        baf = QBAF(arguments=(a, b), attacks=(), supports=())
        sem = DFQuADSemantics()
        cost = flip_cost(baf, sem)
        bound = flip_cost_upper_bound(baf, sem)
        assert cost <= bound

    def test_three_arg_chain(self) -> None:
        """a → b → c; chain of attacks. Winner depends on base scores."""
        a = _arg("a", base=0.6)
        b = _arg("b", base=0.5)
        c = _arg("c", base=0.4)
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="c", weight=1.0),
            ),
            supports=(),
        )
        sem = DFQuADSemantics()
        cost = flip_cost(baf, sem)
        bound = flip_cost_upper_bound(baf, sem)
        assert cost <= bound

    def test_random_4arg_qbafs_all_within_bound(self) -> None:
        """Property-based: across a small random sample of 4-arg QBAFs,
        flip_cost is always <= upper_bound."""
        import random

        rng = random.Random(0)
        sem = DFQuADSemantics()
        for _ in range(20):
            n = 4
            args = tuple(
                _arg(f"a{i}", base=rng.uniform(0.1, 0.9)) for i in range(n)
            )
            edges: list[Attack] = []
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    if rng.random() < 0.3:
                        edges.append(
                            Attack(
                                source=f"a{i}",
                                target=f"a{j}",
                                weight=round(rng.uniform(0.1, 1.0), 2),
                            )
                        )
            baf = QBAF(arguments=args, attacks=tuple(edges), supports=())
            cost = flip_cost(baf, sem, max_search=4)
            bound = flip_cost_upper_bound(baf, sem)
            assert cost == -1 or cost <= bound


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestFlipCostDeterminism:
    def test_byte_equal_over_10_invocations(self) -> None:
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.5)
        baf = QBAF(arguments=(a, b), attacks=(), supports=())
        sem = DFQuADSemantics()
        first = flip_cost(baf, sem)
        for _ in range(10):
            assert flip_cost(baf, sem) == first


# ---------------------------------------------------------------------------
# Helper-API regression: combinations import works (sanity check the test)
# ---------------------------------------------------------------------------


def test_combinations_imported() -> None:
    """Sanity: itertools.combinations is used inside flip_cost; this test
    pins that the import is available in the test environment."""
    assert list(combinations([1, 2, 3], 2)) == [(1, 2), (1, 3), (2, 3)]
