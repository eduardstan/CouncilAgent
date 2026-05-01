"""ATLK headline-theorem witness via MCMAS.

Stage 5 of the T7 ATLK revision (specs/t7-atlk-revision.md).

This module composes the components built in Stages 1-3:

  - Stage 1 ATL+CTLK AST nodes (CoalitionFinally, Knows, ...)
  - Stage 2 DeliberationCGS data model
  - Stage 3 cgs_to_ispl emitter

into the headline operation: given a CGS and a list of argument ids,
return the subset that is **Strategically-Witnessable** under the
``-atlk 2`` semantics (ADR-0021). The model-checking is done by an
injected ``MCMASRunner`` callable so the composition logic is
testable without invoking the real MCMAS binary; the tests in
``tests/integration/test_t7_atlk.py`` provide a real-subprocess
runner for the headline-theorem regression.

The Strategically-Witnessable predicate, per
``specs/t7-atlk-revision.md`` §"The math":

    Strategically-Witnessable(q) :=
        { a ∈ consensus_args(q) :
            ∃ i ∈ Π. (M, q) ⊨ ⟨⟨{i}⟩⟩ F K_i evidence(a, i) }

This module evaluates the right-hand side via MCMAS and returns the
arg_ids satisfying it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

from council.symbolic.verify.cgs import DeliberationCGS, cgs_to_ispl
from council.symbolic.verify.ltlf import (
    Atom,
    CoalitionFinally,
    Knows,
    LTLf,
)


class MCMASRunner(Protocol):
    """Callable that invokes MCMAS on an ISPL string and returns stdout.

    The integration-test runner shells out to the ``mcmas`` binary;
    unit tests use a stub returning canned output.
    """

    def __call__(self, ispl: str, *, atlk: int) -> str: ...


_VERDICT_RE = re.compile(
    r"Formula\s+number\s+(\d+):\s+.*?,\s+is\s+(TRUE|FALSE)\s+in\s+the\s+model"
)


def parse_mcmas_verdicts(stdout: str) -> list[bool]:
    """Extract per-formula verdicts from MCMAS stdout, in formula order.

    Parses the v1.3.0 output line shape:
        Formula number N: (formula text), is TRUE|FALSE in the model

    Raises ``ValueError`` if no verdict lines are found — empty input,
    parse-only invocations, or malformed output should not silently
    return an empty list.
    """
    matches = _VERDICT_RE.findall(stdout)
    if not matches:
        raise ValueError(
            "no verdicts found in MCMAS stdout — expected lines like "
            "'Formula number N: (...), is TRUE|FALSE in the model'"
        )
    # Sort by formula number to be safe, though MCMAS emits in order.
    matches_with_n = [(int(n), v) for n, v in matches]
    matches_with_n.sort(key=lambda x: x[0])
    return [v == "TRUE" for _, v in matches_with_n]


def _short_id(agent_id: str) -> str:
    return agent_id.removeprefix("agent_")


def _build_witness_formula(arg_id: str, agent_id: str) -> LTLf:
    """Build ⟨⟨{i}⟩⟩ F K_i evidence(arg_id, i) in the LTLf AST."""
    short = _short_id(agent_id)
    return CoalitionFinally(
        group=f"g_{short}",
        arg=Knows(
            agent=agent_id,
            arg=Atom(f"evidence_{arg_id}_{short}"),
        ),
    )


def evidence_backed_arg_ids_via_atl(
    cgs: DeliberationCGS,
    arg_ids: Sequence[str],
    *,
    runner: MCMASRunner,
) -> frozenset[str]:
    """Return the arg_ids that are Strategically-Witnessable in the CGS.

    For each (arg_id, agent_id) pair, builds the ATLK formula
    ``⟨⟨{i}⟩⟩ F K_i evidence(arg_id, i)``, emits ISPL via
    ``cgs_to_ispl``, runs MCMAS through the injected ``runner`` under
    ``-atlk 2``, and includes ``arg_id`` in the result iff the formula
    evaluates TRUE for at least one agent.

    Empty ``arg_ids`` returns ``frozenset()`` without invoking the
    runner — short-circuit for test clarity.
    """
    if not arg_ids:
        return frozenset()

    # Build the full formula list in deterministic order: outer arg_id
    # then inner agent_id. The verdict list will come back in the same
    # order, allowing direct zip-style aggregation.
    pairs: list[tuple[str, str]] = []
    formulae: list[LTLf] = []
    for arg_id in arg_ids:
        for agent in cgs.agents:
            pairs.append((arg_id, agent.agent_id))
            formulae.append(_build_witness_formula(arg_id, agent.agent_id))

    ispl = cgs_to_ispl(cgs, formulae)
    stdout = runner(ispl, atlk=2)
    verdicts = parse_mcmas_verdicts(stdout)

    if len(verdicts) != len(formulae):
        raise ValueError(
            f"verdict count mismatch: sent {len(formulae)} formulae, "
            f"got {len(verdicts)} verdicts"
        )

    witnessed: set[str] = set()
    for (arg_id, _agent_id), verdict in zip(pairs, verdicts, strict=True):
        if verdict:
            witnessed.add(arg_id)
    return frozenset(witnessed)
