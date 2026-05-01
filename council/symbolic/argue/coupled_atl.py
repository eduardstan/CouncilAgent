"""Trace-level fast path for the Strategically-Witnessable predicate.

This module computes a *sound under-approximation* of the
``Strategically-Witnessable`` predicate that anchors the revised T7
ATLK statement (``docs/theory.md`` §T7, mechanised by MCMAS under
``-atlk 2`` in ``tests/integration/test_t7_atlk.py``).

**Lemma (T7 under-approximation).** For any trace ``T`` reachable
in the deliberation CGS ``M(P, Π, Θ, R)``:

    evidence_backed_arg_ids(T)  ⊆  Strategically-Witnessable(q(T))

i.e., every arg_id witnessed by an actual move in the trace is also
strategically reachable by the witnessing agent in the CGS. The
converse fails in general: an agent can have a uniform strategy to
disclose without ever exercising it in the trace.

**Why this module exists.** The full ``Strategically-Witnessable``
predicate requires invoking MCMAS via
``council.symbolic.verify.atl_witness.evidence_backed_arg_ids_via_atl``
(several seconds per query). The trace-level fast path here runs in
microseconds and is sufficient for the W2 ``StrategicCoupledSemantics``
headline pipeline. The under-approximation lemma certifies it as
sound — it never overestimates witnessability.

**Concretely:** an arg_id is "evidence-backed" iff there exists at
least one Move in the trace that:
  (a) materially corresponds to the argument (same arg_id for
      Propose, or same claim surface for Vote), AND
  (b) carries non-empty evidence in its Claim.

This module exposes one function: ``evidence_backed_arg_ids(trace)``.
``StrategicCoupledSemantics`` consumes the result at construction
time and demotes consensus-reaching arg_ids that are not in this
set. The MCMAS-grounded variant
(``council.symbolic.verify.atl_witness.evidence_backed_arg_ids_via_atl``)
returns the strict superset.

**ADR provenance.** ADR-0012 originally placed the "trivial ATL"
fragment here, candidly noting it was "mathematically trivial on
finite traces — observable directly from Move metadata". ADR-0020 +
ADR-0021 + the T7 revision (Stages 1-6 of
``specs/t7-atlk-revision.md``) reinterpret this module as the fast
under-approximation, alongside the new
``council.symbolic.verify.{cgs, atl_witness}`` modules that implement
the genuine ATLK predicate via MCMAS. Function signature is
preserved (W2/PR5 callers untouched).

Future extensions (multi-coalition ``⟨⟨C⟩⟩ F φ``, multi-step
reachability) belong on the verify side; this trace-level helper is
preserved for cost-conscious callers.
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
