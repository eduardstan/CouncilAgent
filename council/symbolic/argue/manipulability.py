"""L2 argumentation — Manipulability bound (T5).

Master plan §10 T5:
  Define the *flip cost* of a BAF as the minimum number of attack-edge
  flips needed to change the winner under DF-QuAD. Provide an upper
  bound parameterised by (in-degree, attack/support ratio). Builds on
  Baroni-Rago-Toni 2019.

This module ships:

  flip_cost(baf, sem, *, max_search=8) -> int
    Brute-force minimum number of binary edge perturbations (each:
    toggle weight 0 ↔ 1 between any ordered pair of distinct
    non-withdrawn arguments) required to change the winner under
    `sem`. Returns -1 if no such flip is found within `max_search`
    perturbations (the deterministic sentinel for "no flip in budget"
    / "single-argument BAF").

  flip_cost_upper_bound(baf, sem) -> int
    The headline T5 closed-form bound:
      max(0, |proposals| - 1)
    where proposals = non-withdrawn arguments in the BAF. Computed
    in O(|args|).

Per ADR-0010 Q2, withdrawn arguments are excluded.

The brute-force search is exponential in `max_search` — intended for
small examples (<= ~6 arguments). For larger graphs, only the upper
bound is computed.
"""

from __future__ import annotations

from itertools import combinations

from council.symbolic.argue.baf import QBAF, Attack
from council.symbolic.argue.semantics.base import GradualSemantics


def _proposals(baf: QBAF) -> list[str]:
    """Non-withdrawn argument IDs (the candidate winners; ADR-0010 Q2)."""
    return [a.arg_id for a in baf.arguments if not a.withdrawn]


def _winner_id(baf: QBAF, sem: GradualSemantics) -> str | None:
    """The current strongest non-withdrawn argument's id, or None if empty.

    Ties broken by insertion order (matches ArgumentationAggregator's
    max-with-key behaviour).
    """
    proposals = [a for a in baf.arguments if not a.withdrawn]
    if not proposals:
        return None
    strengths = sem.evaluate(baf)
    return max(proposals, key=lambda a: strengths[a.arg_id]).arg_id


def flip_cost_upper_bound(baf: QBAF, sem: GradualSemantics) -> int:
    """Closed-form T5 upper bound: |non-withdrawn proposals| - 1, with the
    -1 sentinel for unflippable BAFs.

    Returns:
      n - 1   when n >= 2 (the headline T5 bound)
      -1      when n < 2 (sentinel: no swap target -> unflippable)

    The -1 sentinel matches `flip_cost`'s return for the same inputs, so
    `flip_cost(baf, sem) <= flip_cost_upper_bound(baf, sem)` is well
    defined uniformly over all inputs. (Theorem audit fix, 2026-05-01:
    aligned with `flip_cost` after a sentinel inconsistency was found
    where this returned 0 for n=1 while `flip_cost` returned -1.)

    Proof sketch (docs/theory.md §T5): for any current winner under
    DF-QuAD, setting the attack weight from every other non-withdrawn
    argument toward the winner to 1.0 saturates v_a in the F-aggregation,
    dropping the winner's strength to its lower bound c(w, 1, 0) =
    w - w·1 = 0. The runner-up (with no attackers) retains its base
    score. Thus n-1 perturbations always suffice when proposals >= 2.
    """
    del sem  # currently semantics-independent (T5 holds uniformly)
    n = len(_proposals(baf))
    if n < 2:
        return -1
    return n - 1


def _toggle_attacks(
    baf: QBAF, edges_to_flip: tuple[tuple[str, str], ...]
) -> QBAF:
    """Return a new QBAF with attack weights toggled on the given (s, t) edges.

    Toggle semantics:
      - If (s, t) is currently an Attack with weight > 0: remove it
        (set weight to 0 via omission).
      - Otherwise: add it with weight 1.0.
    """
    flipped = set(edges_to_flip)
    new_attacks: list[Attack] = []
    seen: set[tuple[str, str]] = set()
    for att in baf.attacks:
        key = (att.source, att.target)
        seen.add(key)
        if key in flipped:
            # Toggle off (weight to 0 — i.e., remove)
            continue
        new_attacks.append(att)
    for s, t in flipped:
        if (s, t) not in seen:
            # Toggle on (was absent → add weight 1.0)
            new_attacks.append(Attack(source=s, target=t, weight=1.0))
    return QBAF(
        arguments=baf.arguments,
        attacks=tuple(new_attacks),
        supports=baf.supports,
    )


def _candidate_edges(baf: QBAF) -> list[tuple[str, str]]:
    """All ordered pairs (s, t) of distinct non-withdrawn arg_ids."""
    proposals = _proposals(baf)
    return [(s, t) for s in proposals for t in proposals if s != t]


def flip_cost(
    baf: QBAF,
    sem: GradualSemantics,
    *,
    max_search: int = 8,
) -> int:
    """Brute-force minimum binary edge perturbations to change the winner.

    Returns:
      -1 if there's no possible flip — empty BAF (no proposals), single
         proposal (no swap target), an already-cyclic initial BAF
         (semantics raises ValueError), or no flip set is found within
         `max_search` perturbations;
      k >= 1 if a flip set of size k is found that changes the winner
         and k <= max_search.

    The -1 sentinel matches `flip_cost_upper_bound` so the two are
    directly comparable. (Theorem audit fix, 2026-05-01.)

    Algorithm:
      1. Compute the current winner.
      2. For k = 1, 2, ..., min(max_search, |candidate_edges|):
           For each subset of size k of candidate edges:
             Toggle those edges and re-evaluate.
             If the winner changes, return k.
      3. Return -1.

    The search is breadth-first by subset size, so the first match is
    the minimum. Exponential in worst case; bounded by max_search.
    """
    proposals = _proposals(baf)
    if len(proposals) < 2:
        # No swap target possible (empty or single argument) -> unflippable
        return -1

    try:
        current_winner = _winner_id(baf, sem)
    except ValueError:
        # The base BAF is cyclic for the chosen semantics; flip_cost is
        # undefined under that semantics. Return -1 sentinel.
        return -1
    if current_winner is None:
        return 0

    edges = _candidate_edges(baf)
    upper = min(max_search, len(edges))

    for k in range(1, upper + 1):
        for edge_subset in combinations(edges, k):
            perturbed = _toggle_attacks(baf, edge_subset)
            try:
                new_winner = _winner_id(perturbed, sem)
            except ValueError:
                # Some semantics (DF-QuAD) raise on cycles introduced by
                # the perturbation. Skip those flip sets.
                continue
            if new_winner is not None and new_winner != current_winner:
                return k

    return -1
