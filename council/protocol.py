"""Protocol layer — build a single-agent prompt from a VisibilityContext.

Constitution §3:
- Protocol controls presentation only. One method, no state.
- Must NOT filter by agent identity (ctx is already filtered by core.py).
- Must NOT perform anonymization (ctx.visible_responses are already anonymized).
- Must NOT read round_history from global state — only what ctx provides.

Anonymization is centralized in core._build_visibility_context(). Protocols
trust that ctx.visible_responses already contain anonymized agent_ids
(e.g. "Response A", "Response B"). They format whatever they receive.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

from council.context import AgentResponse, CommunicationMode, VisibilityContext


class Protocol(ABC):
    """Build a prompt string for one agent in one round."""

    @abstractmethod
    def build_prompt(self, ctx: VisibilityContext) -> str: ...

    def is_answer_round(self, round_index: int) -> bool:
        """Return True if agents produce a final answer this round.

        Default: all rounds are answer rounds (correct for DirectAnswerProtocol
        and SimultaneousProtocol). PeerReviewProtocol overrides to return False
        for odd (critique) rounds.
        """
        return True

    def cycle_length(self) -> int:
        """Number of raw rounds per deliberation cycle.

        A "cycle" is the smallest unit of deliberation the protocol defines.
        For PeerReview: critique + revision = 2 rounds per cycle.
        For DirectAnswer/Simultaneous: 1 round per cycle.

        Used by the runner to translate config max_rounds (deliberation cycles)
        to the total raw round count: total = 1 + max_rounds * cycle_length().
        """
        return 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_schema(schema: dict[str, object]) -> str:
    return f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"


def _append_hint(prompt: str, hint: str) -> str:
    """Append a task-level formatting hint to a prompt. No-op when hint is empty."""
    if not hint:
        return prompt
    return f"{prompt}\n\n{hint}"


def _format_responses(ctx: VisibilityContext) -> str:
    """Format visible_responses according to communication_mode."""
    if not ctx.visible_responses:
        return ""

    if ctx.communication_mode == CommunicationMode.BROADCAST:
        # Shared board: no per-sender labels, just a numbered list.
        lines = [f"{i + 1}. {r.content}" for i, r in enumerate(ctx.visible_responses)]
        return "Shared board:\n" + "\n".join(lines)
    else:
        # INDIVIDUAL or RELAY: label each response with the (anonymized) agent_id.
        lines = [f"[{r.agent_id}]: {r.content}" for r in ctx.visible_responses]
        return "\n".join(lines)


def _filter_window(ctx: VisibilityContext, window_size: int) -> list[AgentResponse]:
    """Return the window_size most-recent rounds of visible_responses."""
    if not ctx.visible_responses:
        return []
    max_round = max(r.round_index for r in ctx.visible_responses)
    cutoff = max_round - window_size + 1
    return [r for r in ctx.visible_responses if r.round_index >= cutoff]


# ---------------------------------------------------------------------------
# DirectAnswerProtocol
# ---------------------------------------------------------------------------


class DirectAnswerProtocol(Protocol):
    """Round 0 baseline protocol — return the original prompt, optionally with a schema.

    Used for MajorityVote where no deliberation is needed.
    """

    def __init__(self, output_schema: dict[str, object] | None = None) -> None:
        self._schema = output_schema

    def build_prompt(self, ctx: VisibilityContext) -> str:
        prompt = ctx.original_prompt
        if self._schema:
            prompt += _format_schema(self._schema)
        # DirectAnswer: every round is an answer round — always inject hint.
        return _append_hint(prompt, ctx.task_hint)


# ---------------------------------------------------------------------------
# PeerReviewProtocol
# ---------------------------------------------------------------------------


class PeerReviewProtocol(Protocol):
    """Multi-round alternating critique / revision protocol.

    Round 0       → original prompt (generate initial answer)
    Odd rounds    → critique: review visible responses, identify weaknesses
    Even rounds>0 → revision: revise own answer given received critiques
    """

    def __init__(self, output_schema: dict[str, object] | None = None) -> None:
        self._schema = output_schema

    def is_answer_round(self, round_index: int) -> bool:
        return round_index % 2 == 0

    def cycle_length(self) -> int:
        return 2

    def build_prompt(self, ctx: VisibilityContext) -> str:
        if ctx.round_index == 0:
            return self._initial_prompt(ctx)
        if ctx.round_index % 2 == 1:
            return self._critique_prompt(ctx)
        return self._revision_prompt(ctx)

    def _initial_prompt(self, ctx: VisibilityContext) -> str:
        prompt = ctx.original_prompt
        if self._schema:
            prompt += _format_schema(self._schema)
        return _append_hint(prompt, ctx.task_hint)

    def _windowed_ctx(self, ctx: VisibilityContext) -> VisibilityContext:
        """Return ctx with visible_responses limited to the last round (window=1).

        Prevents quadratic context growth and logical confusion between rounds
        in multi-round deliberation (audit §2).
        """
        windowed = _filter_window(ctx, window_size=1)
        return VisibilityContext(
            agent_id=ctx.agent_id,
            round_index=ctx.round_index,
            visible_responses=windowed,
            own_previous_responses=ctx.own_previous_responses,
            total_agents=ctx.total_agents,
            communication_mode=ctx.communication_mode,
            original_prompt=ctx.original_prompt,
            task_hint=ctx.task_hint,
        )

    def _critique_prompt(self, ctx: VisibilityContext) -> str:
        formatted = _format_responses(self._windowed_ctx(ctx))
        parts = [
            f"Original question: {ctx.original_prompt}",
            "",
            "The following responses were submitted by other agents:",
            formatted,
            "",
            "Critique each response above. Identify any errors, gaps, or weaknesses. "
            "Be specific and constructive.",
        ]
        # Critiques are free-text analysis — no JSON schema here.
        # Schema is only injected in answer rounds (initial + revision).
        return "\n".join(parts)

    def _revision_prompt(self, ctx: VisibilityContext) -> str:
        formatted = _format_responses(self._windowed_ctx(ctx))
        own_prev = ctx.own_previous_responses[-1].content if ctx.own_previous_responses else ""
        parts = [
            f"Original question: {ctx.original_prompt}",
            "",
        ]
        if own_prev:
            parts += [f"Your previous answer: {own_prev}", ""]
        parts += [
            "Critiques received from other agents:",
            formatted,
            "",
            "Revise and improve your answer based on the critiques above.",
        ]
        if self._schema:
            parts.append(_format_schema(self._schema))
        # Revision rounds are answer rounds — inject the hint here too.
        return _append_hint("\n".join(parts), ctx.task_hint)


# ---------------------------------------------------------------------------
# SimultaneousProtocol
# ---------------------------------------------------------------------------


class SimultaneousProtocol(Protocol):
    """All agents see a sliding window of previous-round responses.

    Bounded context growth: only the last `window_size` rounds are included.
    This prevents quadratic context growth in long deliberations (Issue 7).
    """

    def __init__(
        self,
        window_size: int = 2,
        output_schema: dict[str, object] | None = None,
    ) -> None:
        self._window_size = window_size
        self._schema = output_schema

    def build_prompt(self, ctx: VisibilityContext) -> str:
        if ctx.round_index == 0 or not ctx.visible_responses:
            prompt = ctx.original_prompt
            if self._schema:
                prompt += _format_schema(self._schema)
            return _append_hint(prompt, ctx.task_hint)

        windowed = _filter_window(ctx, self._window_size)
        temp_ctx = VisibilityContext(
            agent_id=ctx.agent_id,
            round_index=ctx.round_index,
            visible_responses=windowed,
            own_previous_responses=ctx.own_previous_responses,
            total_agents=ctx.total_agents,
            communication_mode=ctx.communication_mode,
            original_prompt=ctx.original_prompt,
            task_hint=ctx.task_hint,
        )
        formatted = _format_responses(temp_ctx)
        parts = [
            f"Original question: {ctx.original_prompt}",
            "",
            "Recent responses from other agents:",
            formatted,
            "",
            "Provide your answer, taking the above responses into account.",
        ]
        if self._schema:
            parts.append(_format_schema(self._schema))
        return _append_hint("\n".join(parts), ctx.task_hint)
