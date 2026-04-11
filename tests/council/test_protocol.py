"""Tests for council/protocol.py — prompt construction from VisibilityContext.

Per testing.md §regressions Issue 6: every Protocol subclass's build_prompt()
must NOT contain a real agent_id when visible_responses are anonymized.

Architecture §3: protocols receive pre-filtered, pre-anonymized VisibilityContext.
They must not re-filter by agent identity or perform anonymization themselves.
"""

from __future__ import annotations

import pytest

from council.context import AgentResponse, CommunicationMode, VisibilityContext
from council.protocol import (
    DirectAnswerProtocol,
    PeerReviewProtocol,
    Protocol,
    SimultaneousProtocol,
)
from council.ranking import StructuredRanking

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _response(agent_id: str, content: str, round_index: int = 0) -> AgentResponse:
    return AgentResponse(
        agent_id=agent_id,
        content=content,
        round_index=round_index,
        tokens_in=5,
        tokens_out=5,
        cost=0.0,
    )


def _ctx(
    *,
    agent_id: str = "agent-0",
    round_index: int = 0,
    visible: list[AgentResponse] | None = None,
    own: list[AgentResponse] | None = None,
    mode: CommunicationMode = CommunicationMode.INDIVIDUAL,
    prompt: str = "What is 6x7?",
    total_agents: int = 3,
) -> VisibilityContext:
    return VisibilityContext(
        agent_id=agent_id,
        round_index=round_index,
        visible_responses=visible or [],
        own_previous_responses=own or [],
        total_agents=total_agents,
        communication_mode=mode,
        original_prompt=prompt,
    )


# ---------------------------------------------------------------------------
# Regression Issue 6 — parametrized over all Protocol subclasses
# ---------------------------------------------------------------------------

ALL_PROTOCOLS: list[Protocol] = [
    DirectAnswerProtocol(),
    PeerReviewProtocol(),
    SimultaneousProtocol(),
]


@pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=["DirectAnswer", "PeerReview", "Simultaneous"])
def test_issue6_no_real_agent_id_in_prompt_when_anonymized(protocol: Protocol) -> None:
    """Issue 6: when VisibilityContext contains anonymized agent_ids (e.g. 'Response A'),
    the prompt must not contain real model names like 'gpt-4o' or 'claude-sonnet'."""
    real_ids = ["gpt-4o", "claude-sonnet-4", "gemini-pro"]
    # Anonymized visible_responses: real IDs are replaced with "Response A/B/C"
    visible = [
        _response("Response A", "42", round_index=0),
        _response("Response B", "42", round_index=0),
    ]
    ctx = _ctx(
        agent_id="Response C",  # anonymized self
        round_index=1,
        visible=visible,
    )
    prompt = protocol.build_prompt(ctx)
    for real_id in real_ids:
        assert real_id not in prompt, (
            f"{type(protocol).__name__}.build_prompt leaked real agent_id {real_id!r}"
        )


# ---------------------------------------------------------------------------
# DirectAnswerProtocol
# ---------------------------------------------------------------------------


class TestDirectAnswerProtocol:
    def test_round_0_returns_original_prompt(self) -> None:
        protocol = DirectAnswerProtocol()
        ctx = _ctx(round_index=0)
        prompt = protocol.build_prompt(ctx)
        assert "What is 6x7?" in prompt

    def test_schema_injected_when_provided(self) -> None:
        schema = {"type": "object", "properties": {"answer": {"type": "number"}}}
        protocol = DirectAnswerProtocol(output_schema=schema)
        ctx = _ctx(round_index=0)
        prompt = protocol.build_prompt(ctx)
        assert "answer" in prompt  # schema content appears in prompt

    def test_no_schema_no_schema_text(self) -> None:
        protocol = DirectAnswerProtocol()
        ctx = _ctx(round_index=0)
        prompt = protocol.build_prompt(ctx)
        assert "json_schema" not in prompt.lower() or "schema" not in prompt.lower()

    def test_build_prompt_is_synchronous(self) -> None:
        # Protocol.build_prompt must be a regular function, not async.
        import inspect

        protocol = DirectAnswerProtocol()
        ctx = _ctx()
        result = protocol.build_prompt(ctx)
        assert not inspect.isawaitable(result)


# ---------------------------------------------------------------------------
# PeerReviewProtocol
# ---------------------------------------------------------------------------


class TestPeerReviewProtocol:
    def test_round_0_contains_original_prompt(self) -> None:
        protocol = PeerReviewProtocol()
        ctx = _ctx(round_index=0)
        prompt = protocol.build_prompt(ctx)
        assert "What is 6x7?" in prompt

    def test_odd_round_contains_critique_framing(self) -> None:
        visible = [_response("Response A", "The answer is 72")]
        ctx = _ctx(round_index=1, visible=visible)
        protocol = PeerReviewProtocol()
        prompt = protocol.build_prompt(ctx)
        assert any(word in prompt.lower() for word in ("critique", "review", "evaluate", "assess"))

    def test_even_round_gt_0_contains_revision_framing(self) -> None:
        visible = [_response("Response A", "critique: wrong")]
        own = [_response("agent-0", "my first answer", round_index=0)]
        ctx = _ctx(round_index=2, visible=visible, own=own)
        protocol = PeerReviewProtocol()
        prompt = protocol.build_prompt(ctx)
        assert any(word in prompt.lower() for word in ("revise", "update", "refine", "improve"))

    def test_round_1_is_critique_not_revision(self) -> None:
        visible = [_response("Response A", "my answer")]
        ctx = _ctx(round_index=1, visible=visible)
        protocol = PeerReviewProtocol()
        prompt = protocol.build_prompt(ctx)
        # Must have critique framing, not revision framing
        has_critique = any(w in prompt.lower() for w in ("critique", "review", "evaluate", "assess"))
        has_revision = any(w in prompt.lower() for w in ("revise", "update", "refine", "improve"))
        assert has_critique
        assert not has_revision

    def test_visible_responses_included_in_prompt(self) -> None:
        visible = [_response("Response A", "forty-two")]
        ctx = _ctx(round_index=1, visible=visible)
        protocol = PeerReviewProtocol()
        prompt = protocol.build_prompt(ctx)
        assert "forty-two" in prompt

    def test_broadcast_mode_formats_as_shared_board(self) -> None:
        visible = [_response("Response A", "some answer")]
        ctx = _ctx(round_index=1, visible=visible, mode=CommunicationMode.BROADCAST)
        protocol = PeerReviewProtocol()
        prompt = protocol.build_prompt(ctx)
        # Shared board: no per-sender label needed — just the content
        assert "some answer" in prompt

    def test_schema_injected_in_output(self) -> None:
        schema = StructuredRanking.SCHEMA
        protocol = PeerReviewProtocol(output_schema=schema)
        ctx = _ctx(round_index=1, visible=[_response("Response A", "x")])
        prompt = protocol.build_prompt(ctx)
        assert "ranking" in prompt  # schema field name appears

    def test_protocol_does_not_filter_by_agent_identity(self) -> None:
        # Protocol must format all visible_responses regardless of agent_id.
        # It receives pre-filtered ctx; it must NOT re-filter here.
        visible = [
            _response("Response A", "answer one"),
            _response("Response B", "answer two"),
        ]
        ctx = _ctx(round_index=1, visible=visible)
        protocol = PeerReviewProtocol()
        prompt = protocol.build_prompt(ctx)
        assert "answer one" in prompt
        assert "answer two" in prompt


# ---------------------------------------------------------------------------
# SimultaneousProtocol
# ---------------------------------------------------------------------------


class TestSimultaneousProtocol:
    def test_round_0_contains_original_prompt(self) -> None:
        protocol = SimultaneousProtocol()
        ctx = _ctx(round_index=0)
        prompt = protocol.build_prompt(ctx)
        assert "What is 6x7?" in prompt

    def test_window_size_1_includes_only_last_round(self) -> None:
        # window_size=1 → only responses from the most recent round visible.
        visible = [
            _response("Response A", "old answer", round_index=0),
            _response("Response A", "new answer", round_index=1),
        ]
        ctx = _ctx(round_index=2, visible=visible)
        protocol = SimultaneousProtocol(window_size=1)
        prompt = protocol.build_prompt(ctx)
        assert "new answer" in prompt
        assert "old answer" not in prompt

    def test_window_size_2_includes_two_rounds(self) -> None:
        visible = [
            _response("Response A", "round0 answer", round_index=0),
            _response("Response A", "round1 answer", round_index=1),
        ]
        ctx = _ctx(round_index=2, visible=visible)
        protocol = SimultaneousProtocol(window_size=2)
        prompt = protocol.build_prompt(ctx)
        assert "round0 answer" in prompt
        assert "round1 answer" in prompt

    def test_visible_responses_included(self) -> None:
        visible = [_response("Response A", "the answer is here")]
        ctx = _ctx(round_index=1, visible=visible)
        protocol = SimultaneousProtocol()
        prompt = protocol.build_prompt(ctx)
        assert "the answer is here" in prompt


# ---------------------------------------------------------------------------
# Cross-layer isolation
# ---------------------------------------------------------------------------


def test_protocol_has_no_non_context_council_imports() -> None:
    import importlib.util

    spec = importlib.util.find_spec("council.protocol")
    assert spec is not None and spec.origin is not None
    with open(spec.origin) as f:
        source = f.read()
    allowed = {"council.context", "council.ranking"}
    bad = [
        line
        for line in source.splitlines()
        if ("from council." in line or "import council." in line)
        and not any(a in line for a in allowed)
        and not line.strip().startswith("#")
    ]
    assert bad == [], f"protocol.py forbidden imports: {bad}"
