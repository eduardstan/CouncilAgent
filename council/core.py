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
    PreferenceData,
    VisibilityContext,
)
from council.models import ModelClient, ModelFailure, ModelRequest
from council.protocol import Protocol
from council.ranking import NullRanking, Ranking
from council.termination import TerminationStrategy
from council.topology import Topology

logger = logging.getLogger(__name__)

# Module-level singleton used as the default `ranking` argument to run_council.
# NullRanking is stateless; sharing one instance avoids a mutable-default pitfall
# while keeping the signature honest (Ranking, not Ranking | None).
_NULL_RANKING: Ranking = NullRanking()


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Identity and per-agent model parameters for one council member.

    temperature and max_tokens default to None, meaning the ModelRequest
    defaults apply. Per-agent overrides let the policy layer shape the
    ensemble — e.g. a "creative" agent at 0.9 alongside a "conservative"
    one at 0.2 for calibrated disagreement.
    """

    id: str
    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    system_prompt: str | None = None


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
    ranking: Ranking = _NULL_RANKING,
    anonymize: bool = True,
    answer_response_format: dict[str, object] | None = None,
    task_hint: str = "",
) -> CouncilResult:
    """Run the full council pipeline and return a final answer with confidence.

    The pipeline runs at least one round (round 0 — initial generation). After
    each round, termination.should_stop() is checked. Deliberation continues
    until the strategy signals True.
    """
    state = CouncilState.initial(prompt)

    agent_ids = [a.id for a in agents]

    # Round 0 — initial generation (no visibility, no adjacency filtering needed).
    state = await _generate(state, agents, topology, protocol, model_client, answer_response_format, task_hint)

    # After every answer round, compute an interim aggregation so termination
    # strategies check consensus on normalized answers — not on raw response text.
    # This mirrors the academic peer review model: the area chair aggregates all
    # reviews before deciding whether to invoke another discussion round.
    if protocol.is_answer_round(0):
        r0_responses = [r for r in state.round_history if r.round_index == 0 and not isinstance(r, ModelFailure)]
        if r0_responses:
            prefs_r0 = await _rank(state, ranking, agent_ids, 0)
            state.interim_result = await aggregation.aggregate(
                r0_responses,
                prefs_r0,
                round_history=list(state.round_history),
                original_prompt=state.question,
            )

    stop, reason = await termination.should_stop(state)

    # Deliberation rounds 1+ — rank+aggregate run inside the loop so that
    # termination can check aggregated consensus after each answer round.
    while not stop:
        state = await _deliberate(state, agents, topology, protocol, model_client, anonymize, answer_response_format, task_hint)
        round_just_completed = state.current_round - 1
        if protocol.is_answer_round(round_just_completed):
            answer_responses = [
                r for r in state.round_history
                if r.round_index == round_just_completed and not isinstance(r, ModelFailure)
            ]
            if answer_responses:
                prefs = await _rank(state, ranking, agent_ids, round_just_completed)
                state.interim_result = await aggregation.aggregate(
                    answer_responses,
                    prefs,
                    round_history=list(state.round_history),
                    original_prompt=state.question,
                )
        stop, reason = await termination.should_stop(state)

    state.termination_reason = reason

    # Use the last interim_result as the final answer; it was computed from the
    # most recent answer round's responses. This is always set because round 0
    # is always an answer round and _generate always runs.
    agg_result = state.interim_result
    if agg_result is None:
        # Safety fallback: should not happen — aggregate whatever we have.
        all_responses = [r for r in state.round_history if not isinstance(r, ModelFailure)]
        prefs_fb = await _rank(state, ranking, agent_ids, state.current_round - 1)
        agg_result = await aggregation.aggregate(
            all_responses,
            prefs_fb,
            round_history=list(state.round_history),
            original_prompt=state.question,
        )

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


def _build_request(
    agent: AgentConfig,
    prompt: str,
    response_format: dict[str, object] | None,
) -> ModelRequest:
    """Construct a ModelRequest, applying per-agent overrides only when set."""
    kwargs: dict[str, object] = {
        "model": agent.model,
        "prompt": prompt,
        "response_format": response_format,
    }
    if agent.temperature is not None:
        kwargs["temperature"] = agent.temperature
    if agent.max_tokens is not None:
        kwargs["max_tokens"] = agent.max_tokens
    if agent.system_prompt is not None:
        kwargs["system_prompt"] = agent.system_prompt
    return ModelRequest(**kwargs)  # type: ignore[arg-type]


async def _generate(
    state: CouncilState,
    agents: list[AgentConfig],
    topology: Topology,
    protocol: Protocol,
    model_client: ModelClient,
    answer_response_format: dict[str, object] | None = None,
    task_hint: str = "",
) -> CouncilState:
    """Round 0: all agents answer the original prompt simultaneously."""
    ctx_for_agent = [
        VisibilityContext(
            agent_id=agent.id,
            round_index=0,
            visible_responses=[],
            own_previous_responses=[],
            total_agents=len(agents),
            communication_mode=topology.communication_mode,
            original_prompt=state.question,
            task_hint=task_hint,
        )
        for agent in agents
    ]
    # Round 0 is always an answer round — enforce structured output if requested.
    rf = answer_response_format if protocol.is_answer_round(0) else None
    tasks = [
        model_client.complete(
            _build_request(agent, protocol.build_prompt(ctx), rf),
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
    answer_response_format: dict[str, object] | None = None,
    task_hint: str = "",
) -> CouncilState:
    """Rounds 1+: each agent sees a filtered, optionally anonymized view of prior responses."""
    round_index = state.current_round
    adjacency = topology.get_adjacency_matrix(round_index)
    communication_mode = topology.communication_mode

    # Build a full history lookup keyed by agent_id, all prior rounds sorted ascending.
    # This makes SimultaneousProtocol's sliding window live: protocols receive the
    # complete visible history and apply their own window if needed.
    history_by_agent: dict[str, list[AgentResponse]] = {}
    for r in sorted(state.round_history, key=lambda x: x.round_index):
        history_by_agent.setdefault(r.agent_id, []).append(r)

    tasks = []
    for i, agent in enumerate(agents):
        # Collect all history from adjacency-permitted agents (in round order).
        visible_raw: list[AgentResponse] = []
        for j in range(len(agents)):
            if adjacency[i][j] and agents[j].id in history_by_agent:
                visible_raw.extend(history_by_agent[agents[j].id])
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
            task_hint=task_hint,
        )
        rf = answer_response_format if protocol.is_answer_round(round_index) else None
        tasks.append(
            model_client.complete(
                _build_request(agent, protocol.build_prompt(ctx), rf),
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
    round_index: int,
) -> list[PreferenceData]:
    """Extract preferences from the specified round's responses."""
    responses = [r for r in state.round_history if r.round_index == round_index]
    return [ranking.extract(r.content, agent_ids) for r in responses]


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
    task_hint: str = "",
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
            task_hint=task_hint,
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
        task_hint=task_hint,
    )
