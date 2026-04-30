"""T4 — Recovery-of-Borda lemma (master plan §10).

> When the BAF has only Vote moves (no Propose / Challenge / Concede outside
> the votes themselves), DF-QuAD gradual semantics recovers Borda count up
> to monotone re-scaling.

Mechanisation. The "Borda BAF" is a no-edge QBAF where each candidate's
base_score = Borda_count(c) / max_possible_Borda. DF-QuAD on a no-edge
graph returns the base scores (Lemma 1: F(()) = 0; c(v0, 0, 0) = v0).
Therefore strength(c) = Borda_count(c) / max → strict monotone re-scaling
of Borda counts (the rescaling factor is 1 / max).

This is the existence claim of T4: there is a BAF construction such that
DF-QuAD's output is a monotone function of Borda counts. The non-trivial
part of the mechanisation is the property-based check across random
elections: the BAF construction is well-defined for any N, K, ballot
distribution, and the ranking by DF-QuAD strength equals the ranking by
Borda count for every such election.

The richer encoding (per-voter Support edges with weight = points/(N-1))
does NOT preserve the Borda ranking in general — F's saturating
multiplicative form (1 - prod(1 - x_i)) is not monotone in the sum of
inputs. T4's "up to monotone re-scaling" wording correctly admits only
the simple encoding.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from council.symbolic.argue.baf import QBAF, Argument
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics

FIXTURES_DIR = Path(__file__).parent.parent / "symbolic" / "argue" / "fixtures"


# ---------------------------------------------------------------------------
# Borda BAF construction helper
# ---------------------------------------------------------------------------


def _borda_count(candidate: str, ballots: list[list[str]]) -> int:
    """Standard Borda count: candidate at rank r in an N-candidate ballot
    receives (N - 1 - r) points (top = N-1, bottom = 0)."""
    n = len(ballots[0])
    total = 0
    for ballot in ballots:
        rank = ballot.index(candidate)
        total += (n - 1) - rank
    return total


def _borda_baf(candidates: list[str], ballots: list[list[str]]) -> QBAF:
    """Build the no-edge BAF where base_score(c) = Borda_count(c) / max_Borda."""
    n = len(candidates)
    k = len(ballots)
    max_borda = k * (n - 1) if n > 1 else 1
    arguments = tuple(
        Argument(
            arg_id=c,
            claim_surface=f"candidate-{c}",
            base_score=_borda_count(c, ballots) / max_borda if max_borda > 0 else 0.0,
        )
        for c in candidates
    )
    return QBAF(arguments=arguments, attacks=(), supports=())


# ---------------------------------------------------------------------------
# Closed-form 3-candidate fixture
# ---------------------------------------------------------------------------


class TestT4ClosedForm3Candidate:
    """Hand-derived 3-candidate Borda fixture; expected values committed in
    tests/symbolic/argue/fixtures/borda_3candidate.json."""

    def _load_fixture(self) -> dict[str, object]:
        return json.loads((FIXTURES_DIR / "borda_3candidate.json").read_text())

    def test_borda_counts_match_fixture(self) -> None:
        fixture = self._load_fixture()
        ballots = [b["ranking"] for b in fixture["ballots"]]  # type: ignore[index]
        candidates = fixture["candidates"]  # type: ignore[index]
        expected = fixture["expected_borda"]  # type: ignore[index]
        for c in candidates:  # type: ignore[union-attr]
            assert _borda_count(c, ballots) == expected[c]  # type: ignore[index]

    def test_df_quad_strengths_equal_normalized_borda(self) -> None:
        fixture = self._load_fixture()
        ballots = [b["ranking"] for b in fixture["ballots"]]  # type: ignore[index]
        candidates = fixture["candidates"]  # type: ignore[index]
        expected = fixture["expected_df_quad_strengths"]  # type: ignore[index]
        baf = _borda_baf(candidates, ballots)  # type: ignore[arg-type]
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)
        for c in candidates:  # type: ignore[union-attr]
            assert strengths[c] == pytest.approx(expected[c])  # type: ignore[index]

    def test_df_quad_ranking_matches_borda_ranking(self) -> None:
        fixture = self._load_fixture()
        ballots = [b["ranking"] for b in fixture["ballots"]]  # type: ignore[index]
        candidates = fixture["candidates"]  # type: ignore[index]
        expected_ranking = fixture["expected_borda_ranking"]  # type: ignore[index]
        baf = _borda_baf(candidates, ballots)  # type: ignore[arg-type]
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)
        actual_ranking = sorted(
            candidates, key=lambda c: strengths[c], reverse=True  # type: ignore[union-attr]
        )
        assert actual_ranking == expected_ranking


# ---------------------------------------------------------------------------
# Property-based: random Borda elections preserve ranking
# ---------------------------------------------------------------------------


class TestT4PropertyRandomElections:
    """Random Borda elections with various N (candidates) and K (voters).
    Fixed seed → deterministic test. Asserts: DF-QuAD strength ranking
    equals Borda count ranking on the no-edge "Borda BAF" encoding."""

    @pytest.mark.parametrize(
        "n_candidates,n_voters",
        [
            (2, 3),
            (3, 3),
            (3, 5),
            (4, 5),
            (5, 7),
            (6, 10),
        ],
    )
    def test_random_election_preserves_ranking(
        self, n_candidates: int, n_voters: int
    ) -> None:
        rng = random.Random(0)
        candidates = [chr(ord("A") + i) for i in range(n_candidates)]
        ballots: list[list[str]] = []
        for _ in range(n_voters):
            ballot = candidates.copy()
            rng.shuffle(ballot)
            ballots.append(ballot)

        # Compute Borda counts and the expected Borda ranking
        borda = {c: _borda_count(c, ballots) for c in candidates}
        borda_ranking = sorted(candidates, key=lambda c: borda[c], reverse=True)

        # Build BAF and run DF-QuAD
        baf = _borda_baf(candidates, ballots)
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)

        # Rank candidates by DF-QuAD strength
        df_ranking = sorted(candidates, key=lambda c: strengths[c], reverse=True)

        # Tie-breaking: when Borda counts tie, DF-QuAD strengths also tie,
        # but sorted() may produce different orderings. Assert ranking up to
        # tie-breaking by comparing strength-equivalence classes.
        def _equivalence_classes(
            order: list[str], score: dict[str, float | int]
        ) -> list[frozenset[str]]:
            classes: list[frozenset[str]] = []
            current: list[str] = []
            current_score: float | int | None = None
            for item in order:
                s = score[item]
                if current_score is None or s == current_score:
                    current.append(item)
                    current_score = s
                else:
                    classes.append(frozenset(current))
                    current = [item]
                    current_score = s
            if current:
                classes.append(frozenset(current))
            return classes

        borda_classes = _equivalence_classes(borda_ranking, borda)
        df_classes = _equivalence_classes(
            df_ranking, {c: strengths[c] for c in candidates}
        )
        assert borda_classes == df_classes, (
            f"Ranking mismatch on N={n_candidates}, K={n_voters}:\n"
            f"  Borda: {borda}\n"
            f"  Strengths: {strengths}\n"
            f"  Borda classes: {borda_classes}\n"
            f"  DF-QuAD classes: {df_classes}"
        )

    def test_strict_monotone_rescaling_for_distinct_borda_counts(self) -> None:
        """When all Borda counts are distinct, DF-QuAD strengths are strictly
        Borda(c) / max_Borda. This is the strongest form of T4."""
        # Construct an election with strictly distinct Borda counts
        candidates = ["A", "B", "C", "D"]
        ballots = [
            ["A", "B", "C", "D"],
            ["A", "B", "C", "D"],
            ["B", "A", "D", "C"],
        ]
        # Borda: A = (3+3+2) = 8; B = (2+2+3) = 7; C = (1+1+0) = 2;
        # D = (0+0+1) = 1; max = K*(N-1) = 3*3 = 9
        borda = {c: _borda_count(c, ballots) for c in candidates}
        assert borda == {"A": 8, "B": 7, "C": 2, "D": 1}
        max_borda = 3 * 3
        baf = _borda_baf(candidates, ballots)
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)
        for c in candidates:
            assert strengths[c] == pytest.approx(borda[c] / max_borda)


# ---------------------------------------------------------------------------
# Sanity: Borda BAF satisfies QBAF structural invariants
# ---------------------------------------------------------------------------


class TestBordaBAFWellFormed:
    def test_no_edges_in_borda_baf(self) -> None:
        ballots = [["A", "B"], ["B", "A"]]
        baf = _borda_baf(["A", "B"], ballots)
        assert baf.attacks == ()
        assert baf.supports == ()

    def test_borda_baf_arguments_in_unit_interval(self) -> None:
        rng = random.Random(0)
        for _ in range(10):
            n = rng.randint(2, 6)
            k = rng.randint(2, 8)
            candidates = [chr(ord("A") + i) for i in range(n)]
            ballots = []
            for _ in range(k):
                b = candidates.copy()
                rng.shuffle(b)
                ballots.append(b)
            baf = _borda_baf(candidates, ballots)
            for arg in baf.arguments:
                assert 0.0 <= arg.base_score <= 1.0

    def test_max_borda_candidate_has_strength_one(self) -> None:
        """When one candidate is unanimously top-ranked, normalised Borda
        is 1.0."""
        candidates = ["A", "B", "C"]
        ballots = [["A", "B", "C"], ["A", "B", "C"], ["A", "C", "B"]]
        # Borda(A) = 2*3 = 6; max = 3*2 = 6 → A has normalised Borda 1.0
        baf = _borda_baf(candidates, ballots)
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)
        assert strengths["A"] == pytest.approx(1.0)
