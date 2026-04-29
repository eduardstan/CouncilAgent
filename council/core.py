"""council/core.py — pure async pipeline: generate → deliberate → aggregate → terminate.

No framework imports (Constitution §8). All anonymisation flows through
_build_visibility_context — the single anonymisation site (Constitution §10).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from council.context import (
    CopelandConfidence,
    CouncilContext,
    CouncilResponse,
    ProvenanceReceipt,
    VisibilityContext,
)
from council.dialect.moves import Abstain, Force, Move, Propose
from council.dialect.parsers import parse_move
from council.dialect.surface import render_move
from council.dialect.trace import Trace
from council.models import ModelFailure, ModelRequest
from council.termination import (
    CompositeTermination,
    LTLfMonitorTermination,
    MonitorVerdict,
)

if TYPE_CHECKING:
    from council.symbolic.verify.monitor import Property


def _build_visibility_context(
    context: CouncilContext,
    trace: Trace,
    round_index: int,
    agent_id: str,
) -> VisibilityContext:
    """Single anonymisation site (Constitution §10).

    Filters the trace to moves visible to agent_id based on the topology
    adjacency matrix, then tags the result with the anonymise flag.
    """
    agents_list = list(context.agents)
    adj = context.topology.get_adjacency_matrix(round_index)

    try:
        agent_idx = agents_list.index(agent_id)
    except ValueError:
        agent_idx = -1

    visible_agent_ids: set[str] = {agent_id}
    for other_idx, other_agent in enumerate(agents_list):
        if agent_idx >= 0 and adj[other_idx, agent_idx] > 0:
            visible_agent_ids.add(other_agent)

    visible_moves = tuple(m for m in trace.moves if m.agent_id in visible_agent_ids)

    return VisibilityContext(
        visible_moves=visible_moves,
        agent_id=agent_id,
        anonymize=context.anonymize,
        round_index=round_index,
    )


async def _generate_for_agent(
    agent_id: str,
    prompt: str,
    trace: Trace,
    context: CouncilContext,
    round_index: int,
) -> tuple[Move, int, int, float]:
    """Generate one Move from agent_id, returning (move, input_tokens, output_tokens, cost)."""
    vis = _build_visibility_context(context, trace, round_index, agent_id)

    history_parts = [
        render_move(m, anonymize=vis.anonymize) for m in vis.visible_moves
    ]
    history = "\n".join(history_parts)
    full_prompt = f"{prompt}\n\nHistory:\n{history}" if history else prompt

    request = ModelRequest(
        model=agent_id,
        prompt=full_prompt,
        response_format={"type": "json_object"},
    )
    result = await context.model_client.complete(request)

    move_id = str(uuid.uuid4())

    if isinstance(result, ModelFailure):
        move: Move = Abstain(
            move_id=move_id,
            agent_id=agent_id,
            round_index=round_index,
        )
        return (move, 0, 0, 0.0)

    move = parse_move(
        result.content,
        agent_id=agent_id,
        round_index=round_index,
        move_id=move_id,
    )
    return (move, result.input_tokens, result.output_tokens, result.cost_usd)


def _aggregate_answer(trace: Trace) -> str:
    """Simple last-propose aggregation; upgraded by L2 ArgumentationAggregator in W2."""
    votes = trace.by_force(Force.VOTE)
    if votes:
        last = votes[-1]
        if isinstance(last, Propose):  # type guard — Vote shares surface field
            return last.claim.surface
        from council.dialect.moves import Vote
        if isinstance(last, Vote):
            return last.option.surface

    proposes = trace.by_force(Force.PROPOSE)
    if proposes:
        last_p = proposes[-1]
        if isinstance(last_p, Propose):
            return last_p.claim.surface

    return ""


async def run_council(
    prompt: str,
    *,
    context: CouncilContext,
) -> CouncilResponse:
    """Pure async council pipeline.

    Runs rounds until termination fires, then assembles CouncilResponse with a
    ProvenanceReceipt. When the termination strategy is an
    `LTLfMonitorTermination` (W1/PR8), violations trigger a pending Intervention
    that is applied before the next round, up to `max_interventions` times
    (Constitution §12).

    No framework dependencies.
    """
    trace = Trace()
    round_index = 0
    cost_ledger: list[tuple[str, float]] = []
    monitor_verdicts: list[MonitorVerdict] = []
    total_input = 0
    total_output = 0

    ltlf_term = _find_ltlf_termination(context.termination)

    while True:
        stop, _ = context.termination.should_stop(trace, round_index)
        # Drain accumulated verdicts each round if any L1 termination is wired in
        if ltlf_term is not None:
            monitor_verdicts.extend(ltlf_term.consume_verdicts())
        if stop:
            # Constitution §12: honour pending intervention before stopping
            if ltlf_term is not None:
                pending = ltlf_term.pending_intervention()
                if pending is not None:
                    violated = _find_violated_property(ltlf_term, monitor_verdicts)
                    if violated is not None:
                        trace = await pending.execute(trace, violated, context)
                        ltlf_term.acknowledge_intervention()
                        monitor_verdicts.extend(ltlf_term.consume_verdicts())
                        round_index += 1
                        continue
            break

        results = await asyncio.gather(*[
            _generate_for_agent(agent_id, prompt, trace, context, round_index)
            for agent_id in context.agents
        ])

        for move, inp, out, cost in results:
            trace = trace.append(move)
            total_input += inp
            total_output += out
            cost_ledger.append((move.move_id, cost))

        round_index += 1

    answer = _aggregate_answer(trace)
    receipt = ProvenanceReceipt(
        trace=trace,
        cost_ledger=tuple(cost_ledger),
        monitor_verdicts=tuple(monitor_verdicts),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
    )
    confidence = CopelandConfidence(value=0.5)

    return CouncilResponse(answer=answer, confidence=confidence, receipt=receipt)


def _find_violated_property(
    termination: LTLfMonitorTermination,
    verdicts: list[MonitorVerdict],
) -> Property | None:
    """Locate the Property instance whose most recent verdict is BOTTOM."""
    for v in reversed(verdicts):
        if v.verdict == "bottom":
            for prop, _ in termination._compiled:
                if prop.name == v.property_name:
                    return prop
    return None


def _find_ltlf_termination(strategy: object) -> LTLfMonitorTermination | None:
    """Walk a TerminationStrategy (possibly wrapped in CompositeTermination) to
    find the embedded LTLfMonitorTermination, if any.
    """
    if isinstance(strategy, LTLfMonitorTermination):
        return strategy
    if isinstance(strategy, CompositeTermination):
        for inner in strategy._strategies:
            found = _find_ltlf_termination(inner)
            if found is not None:
                return found
    return None
