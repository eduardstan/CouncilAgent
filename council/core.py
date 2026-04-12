"""Pure async pipeline — the compositional heart of CouncilAgent.

run_council() composes Topology, Protocol, ModelClient, Ranking, Aggregation,
and TerminationStrategy without knowing how any of them work internally.

Constitution §8: zero framework imports. This module uses only stdlib + asyncio
and the other council layer modules. LangGraph, Hydra, MLflow, OpenTelemetry are
strictly excluded — they live at the edges (adapters/, experiments/).

Constitution §10: anonymize=True is the default. _build_visibility_context() is
the ONLY place in the entire codebase that performs anonymization.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from council.aggregation import Aggregation
from council.context import (
    AgentResponse,
    CommunicationMode,
    CouncilResult,
    CouncilState,
    VisibilityContext,
)
from council.models import ModelClient, ModelFailure, ModelRequest
from council.protocol import Protocol
from council.context import PreferenceData
from council.ranking import NullRanking, Ranking
from council.termination import TerminationStrategy
from council.topology import Topology

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Identity and model assignment for one council member."""

    id: str
    model: str


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_council(
    prompt: str,
    agents: list[AgentConfig],
    model_client: ModelClient,
    topology: Topology,
    protocol: Protocol,
    aggregation: Aggregation,
    termination: TerminationStrategy,
    ranking: Ranking | None = None,
    anonymize: bool = True,
) -> CouncilResult:
    """Run the full council pipeline and return a final answer with confidence.

    The pipeline runs at least one round (round 0 — initial generation). After
    each round, termination.should_stop() is checked. Deliberation continues
    until the strategy signals True.
    """
    if ranking is None:
        ranking = NullRanking()

    state = CouncilState.initial(prompt)

    # Round 0 — initial generation (no visibility, no adjacency filtering needed).
    state = await _generate(state, agents, protocol, model_client)
    stop, reason = await termination.should_stop(state)

    # Deliberation rounds 1+ — loop until termination strategy halts.
    while not stop:
        state = await _deliberate(state, agents, topology, protocol, model_client, anonymize)
        stop, reason = await termination.should_stop(state)

    state.termination_reason = reason

    # Rank (no-op for NullRanking).
    preferences = await _rank(state, ranking, [a.id for a in agents])

    # Aggregate across all rounds that ran.
    round_responses = [r for r in state.round_history if not isinstance(r, ModelFailure)]
    agg_result = await aggregation.aggregate(round_responses, preferences)
    state.final_result = agg_result

    return CouncilResult(
        final_answer=agg_result.final_answer,
        confidence=agg_result.confidence,
        method=agg_result.method,
        rounds_used=state.current_round,
        total_cost=state.total_cost,
        tokens_in=state.tokens_in,
        tokens_out=state.tokens_out,
        termination_reason=state.termination_reason,
        round_history=list(state.round_history),
    )


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


async def _generate(
    state: CouncilState,
    agents: list[AgentConfig],
    protocol: Protocol,
    model_client: ModelClient,
) -> CouncilState:
    """Round 0: all agents answer the original prompt simultaneously."""
    ctx_for_agent = [
        VisibilityContext(
            agent_id=agent.id,
            round_index=0,
            visible_responses=[],
            own_previous_responses=[],
            total_agents=len(agents),
            communication_mode=CommunicationMode.INDIVIDUAL,
            original_prompt=state.question,
        )
        for agent in agents
    ]
    tasks = [
        model_client.complete(
            ModelRequest(model=agent.model, prompt=protocol.build_prompt(ctx)),
            agent_id=agent.id,
            round_index=0,
        )
        for agent, ctx in zip(agents, ctx_for_agent, strict=True)
    ]
    results = await asyncio.gather(*tasks)

    for agent, outcome in zip(agents, results, strict=True):
        if isinstance(outcome, ModelFailure):
            logger.debug("Agent %s failed in round 0: %s", agent.id, outcome.error)
        else:
            state.round_history.append(outcome)
            state.tokens_in += outcome.tokens_in
            state.tokens_out += outcome.tokens_out
            state.total_cost += outcome.cost

    state.current_round = 1
    return state


async def _deliberate(
    state: CouncilState,
    agents: list[AgentConfig],
    topology: Topology,
    protocol: Protocol,
    model_client: ModelClient,
    anonymize: bool,
) -> CouncilState:
    """Rounds 1+: each agent sees a filtered, optionally anonymized view of prior responses."""
    round_index = state.current_round
    adjacency = topology.get_adjacency_matrix(round_index)
    communication_mode = topology.communication_mode

    # Build a slot-aligned lookup for the previous round.
    # Keyed by agent_id so that gaps from failed agents don't shift indices.
    prev_by_agent = {
        r.agent_id: r
        for r in state.round_history
        if r.round_index == round_index - 1
    }

    tasks = []
    for i, agent in enumerate(agents):
        visible_raw = [
            prev_by_agent[agents[j].id]
            for j in range(len(agents))
            if adjacency[i][j] and agents[j].id in prev_by_agent
        ]
        own_prev = [r for r in state.round_history if r.agent_id == agent.id]
        ctx = _build_visibility_context(
            agent_id=agent.id,
            round_index=round_index,
            visible_responses=visible_raw,
            own_previous_responses=own_prev,
            total_agents=len(agents),
            communication_mode=communication_mode,
            original_prompt=state.question,
            anonymize=anonymize,
        )
        tasks.append(
            model_client.complete(
                ModelRequest(model=agent.model, prompt=protocol.build_prompt(ctx)),
                agent_id=agent.id,
                round_index=round_index,
            )
        )

    results = await asyncio.gather(*tasks)

    for agent, outcome in zip(agents, results, strict=True):
        if isinstance(outcome, ModelFailure):
            logger.debug("Agent %s failed in round %d: %s", agent.id, round_index, outcome.error)
        else:
            state.round_history.append(outcome)
            state.tokens_in += outcome.tokens_in
            state.tokens_out += outcome.tokens_out
            state.total_cost += outcome.cost

    state.current_round = round_index + 1
    return state


async def _rank(
    state: CouncilState,
    ranking: Ranking,
    agent_ids: list[str],
) -> list[PreferenceData]:
    """Extract preferences from the last round's responses."""
    last_round = state.current_round - 1
    last_responses = [r for r in state.round_history if r.round_index == last_round]
    return [ranking.extract(r.content, agent_ids) for r in last_responses]


# ---------------------------------------------------------------------------
# Anonymization — the ONLY place in the codebase this happens (Constitution §10)
# ---------------------------------------------------------------------------


def _build_visibility_context(
    agent_id: str,
    round_index: int,
    visible_responses: list[AgentResponse],
    own_previous_responses: list[AgentResponse],
    total_agents: int,
    communication_mode: CommunicationMode,
    original_prompt: str,
    anonymize: bool,
) -> VisibilityContext:
    """Build a VisibilityContext, anonymizing agent IDs if requested.

    When anonymize=True:
    - Each visible response's agent_id is replaced with a stable label
      ("Response A", "Response B", …) based on sort order of real IDs.
    - The real agent_id is preserved in metadata["_real_agent_id"].
    - The calling agent's own ID is also anonymized in the context.

    Protocols receive this context and trust it — they perform no anonymization.
    """
    if not anonymize:
        return VisibilityContext(
            agent_id=agent_id,
            round_index=round_index,
            visible_responses=visible_responses,
            own_previous_responses=own_previous_responses,
            total_agents=total_agents,
            communication_mode=communication_mode,
            original_prompt=original_prompt,
        )

    # Build a stable mapping: real_id → "Response A/B/C/…" by sorted order.
    all_ids = sorted({r.agent_id for r in visible_responses} | {agent_id})
    id_map = {real: f"Response {chr(65 + i)}" for i, real in enumerate(all_ids)}

    anon_visible = [
        AgentResponse(
            agent_id=id_map.get(r.agent_id, r.agent_id),
            content=r.content,
            round_index=r.round_index,
            tokens_in=r.tokens_in,
            tokens_out=r.tokens_out,
            cost=r.cost,
            metadata={**r.metadata, "_real_agent_id": r.agent_id},
        )
        for r in visible_responses
    ]
    anon_own = [
        AgentResponse(
            agent_id=id_map.get(r.agent_id, r.agent_id),
            content=r.content,
            round_index=r.round_index,
            tokens_in=r.tokens_in,
            tokens_out=r.tokens_out,
            cost=r.cost,
            metadata={**r.metadata, "_real_agent_id": r.agent_id},
        )
        for r in own_previous_responses
    ]

    return VisibilityContext(
        agent_id=id_map.get(agent_id, agent_id),
        round_index=round_index,
        visible_responses=anon_visible,
        own_previous_responses=anon_own,
        total_agents=total_agents,
        communication_mode=communication_mode,
        original_prompt=original_prompt,
    )
