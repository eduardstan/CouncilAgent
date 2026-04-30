"""council/core.py — pure async pipeline: generate → deliberate → aggregate → terminate.

No framework imports (Constitution §8). All anonymisation flows through
_build_visibility_context — the single anonymisation site (Constitution §10).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from council.context import (
    CouncilContext,
    CouncilResponse,
    ProvenanceReceipt,
    VisibilityContext,
)
from council.dialect.moves import Abstain, Move
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
    from council.symbolic.argue.aggregator_base import Aggregator
    from council.symbolic.argue.baf import QBAF
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


def _resolve_aggregator(context: CouncilContext) -> Aggregator:
    """Return context.aggregator, or instantiate LastProposeFallbackAggregator.

    Lazy import keeps core.py free of unconditional L2 deps at import time
    (matches the W0 pattern where core.py touches L2 only via composition).
    """
    if context.aggregator is not None:
        return context.aggregator
    from council.symbolic.argue.aggregator import LastProposeFallbackAggregator
    return LastProposeFallbackAggregator()


def _extract_qbaf(metadata: dict[str, object]) -> QBAF | None:
    """Pull a QBAF instance from AggregationResult.metadata if present."""
    from council.symbolic.argue.baf import QBAF as _QBAF
    qbaf = metadata.get("qbaf")
    return qbaf if isinstance(qbaf, _QBAF) else None


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
                        # Snapshot trace length so we can ledger any moves the
                        # intervention appends with cost=0.0 (Constitution §11:
                        # intervention moves come from the symbolic layer, not
                        # from a model call, so their cost is structurally zero).
                        prev_len = len(trace.moves)
                        trace = await pending.execute(trace, violated, context)
                        for m in trace.moves[prev_len:]:
                            cost_ledger.append((m.move_id, 0.0))
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

    aggregator = _resolve_aggregator(context)
    agg_result = await aggregator.aggregate(
        trace, original_question=context.original_question
    )
    qbaf = _extract_qbaf(agg_result.metadata)

    receipt = ProvenanceReceipt(
        trace=trace,
        qbaf=qbaf,
        cost_ledger=tuple(cost_ledger),
        monitor_verdicts=tuple(monitor_verdicts),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
    )

    return CouncilResponse(
        answer=agg_result.answer,
        confidence=agg_result.confidence,
        receipt=receipt,
    )


def _find_violated_property(
    termination: LTLfMonitorTermination,
    verdicts: list[MonitorVerdict],
) -> Property | None:
    """Locate the Property instance whose most recent verdict is BOTTOM."""
    for v in reversed(verdicts):
        if v.verdict == "bottom":
            prop = termination.find_property(v.property_name)
            if prop is not None:
                return prop
    return None


def _find_ltlf_termination(strategy: object) -> LTLfMonitorTermination | None:
    """Walk a TerminationStrategy (possibly wrapped in CompositeTermination) to
    find the embedded LTLfMonitorTermination, if any.
    """
    if isinstance(strategy, LTLfMonitorTermination):
        return strategy
    if isinstance(strategy, CompositeTermination):
        for inner in strategy.strategies:
            found = _find_ltlf_termination(inner)
            if found is not None:
                return found
    return None
