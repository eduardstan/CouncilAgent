"""Operational ``Witnessed`` predicate — the deliberation-time
realisation of T7's witness condition.

This module ships the **operational** half of T7's witness story.
The two halves are genuinely different functions, each tied to a
distinct phase of the L2 lifecycle:

  - **Operational predicate** (this module, ``Witnessed(T)``): a
    trace-direct witness check, used at deliberation time by
    ``StrategicCoupledSemantics`` to decide which consensus
    arguments to demote. Pure-Python; microseconds per call;
    no external dependencies.
  - **Verification predicate**
    (``council.symbolic.verify.atl_witness.evidence_backed_arg_ids_via_atl``,
    ``Strategically-Witnessable(q)``): a real ATLK fixpoint over a
    deliberation CGS, evaluated by MCMAS under ``-atlk 2``. Used at
    theorem time (``docs/theory.md`` §T7,
    ``tests/integration/test_t7_atlk.py``) and would be used in any
    paper-grade certification of the full strategic-witnessability
    fixpoint. Subprocess; seconds per call; needs the ``mcmas`` binary.

Both are necessary by design — not by inertia.
``StrategicCoupledSemantics`` cannot afford a subprocess in the hot
path; the verification predicate cannot run cheaply enough for
real-time aggregation. The two are semantically related by the
following lemma, which licenses using the operational predicate as a
*sound* (subset) approximation of the verification predicate
whenever both are well-defined.

**Lemma (T7 under-approximation).** For any trace ``T`` reachable
in the deliberation CGS ``M(P, Π, Θ, R)``:

    Witnessed(T)  ⊆  Strategically-Witnessable(q(T))

*Proof.* Every move in the trace was the result of *some* uniform
strategy for the move's author (the strategy "play the move on this
observation"). If a move makes ``evidence(a, i)`` hold, then agent
``i`` had a strategy to make it hold — namely, the strategy
including the move. Therefore the witnessed arg id is
strategy-reachable. The converse fails: an agent can have a uniform
strategy to disclose without ever exercising it in the trace.

**Concretely:** an arg_id is "witnessed by ``T``" iff there exists
at least one Move in the trace that:

  (a) materially corresponds to the argument (same ``arg_id`` for
      Propose, or same ``claim.surface`` for Vote), AND
  (b) carries non-empty evidence in its ``Claim``.

The function ``evidence_backed_arg_ids(trace)`` is the entry point.
``StrategicCoupledSemantics`` consumes its output at construction
time and demotes consensus-reaching arg_ids that are not witnessed.
The MCMAS-grounded counterpart
(``council.symbolic.verify.atl_witness.evidence_backed_arg_ids_via_atl``)
returns the strict superset on the same canonical instances; the
two agree on the headline T_3 instance (both empty) and on the
alice-witness positive instance (both ``{p1}``).

**Provenance.** ADR-0012 originally placed the trace-direct check
here. ADR-0020 + ADR-0021 + the T7 revision (Stages 1-6 of
``specs/t7-atlk-revision.md``) introduced the verification predicate
on the verify side, *alongside* this operational one — not in place
of it. The T7 statement (``docs/theory.md`` §T7) is parameterised
over the predicate one chooses; both yield the same theorem under
the under-approximation lemma.

**Future-work boundary.** Multi-coalition ``⟨⟨C⟩⟩ F φ``,
multi-step reachability, and richer-Force projections all extend
the *verification* predicate (more expressive ATLK formulas, larger
CGS). The *operational* predicate's grammar — trace-direct evidence
check — is fully expressive for the W2 ``StrategicCoupledSemantics``
demotion rule and intentionally simple. Adding a new operational
predicate (e.g., one that exploits W3 calibrated confidence) lives
in a sibling module, not here.
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
