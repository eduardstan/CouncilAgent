"""Inline ATL fragment for the Strategic-Coupled gradual semantics.

ADR-0012 places the minimal one-coalition ATL fragment here, in `argue/`,
rather than reaching into the W1 verification spine. The fragment we need
is mathematically trivial on finite traces — observable directly from
Move metadata.

The Alur-Henzinger-Kupferman ATL operator `<<A>> phi` reads "the coalition
A has a strategy to ensure phi". For T7's CTLK invariant
`G(consensus -> exists i. K_i evidenceFor(consensus))` (master plan §10),
the relevant ATL fragment is:

    <<{i}>> X witness_evidence(arg)

"there exists an agent i with a strategy to enforce that arg has evidence
backing in the next state". On a finite trace, this reduces to direct
observation: did agent i's moves witness evidence for the argument?

Concretely: an arg_id is "evidence-backed" iff there exists at least one
Move in the trace that:
  (a) materially corresponds to the argument (same arg_id for Propose, or
      same claim surface for Vote), AND
  (b) carries non-empty evidence in its Claim.

This module exposes one function: `evidence_backed_arg_ids(trace)`. The
StrategicCoupledSemantics consumes the result at construction time and
demotes consensus-reaching arg_ids that are not in this set.

Future ATL extensions (multi-coalition `<<C>> F phi`, multi-step
reachability) are deferred -- the Aggregator (PR6) will use the inline
helper for the W2 deliverable.
"""

from __future__ import annotations

from council.dialect.moves import Propose, Vote
from council.dialect.trace import Trace


def evidence_backed_arg_ids(trace: Trace) -> frozenset[str]:
    """Compute the set of arg_ids witnessed by at least one agent's evidence.

    Currently scans Propose and Vote moves only:
      - Propose with non-empty Claim.evidence -> the Propose's move_id is backed.
      - Vote with non-empty Claim.evidence -> every Propose with the same
        claim surface as Vote.option.surface is backed (via the same
        surface-equality matching rule used by build_qbaf for vote boosts).

    Concede / Challenge / Question moves are ignored -- they carry no
    evidence atoms in W2's typed Move ADT (ADR-0012 documents the scope).
    """
    backed: set[str] = set()

    # Pass 1: directly-evidenced Proposes
    for move in trace.moves:
        if isinstance(move, Propose) and move.claim.evidence:
            backed.add(move.move_id)

    # Pass 2: Vote-witnessed Proposes (vote evidence backs the matching Propose)
    propose_by_surface: dict[str, list[str]] = {}
    for move in trace.moves:
        if isinstance(move, Propose):
            propose_by_surface.setdefault(move.claim.surface, []).append(
                move.move_id
            )

    for move in trace.moves:
        if isinstance(move, Vote) and move.option.evidence:
            for arg_id in propose_by_surface.get(move.option.surface, ()):
                backed.add(arg_id)

    return frozenset(backed)
