"""Tests for council/context.py — shared vocabulary dataclasses and enums.

All tests are pure (no I/O, no async). council/context.py must have zero
imports outside stdlib so no external deps are needed here.
"""

import pytest

from council.context import (
    AgentResponse,
    AggregationResult,
    CommunicationMode,
    CouncilResult,
    CouncilState,
    VisibilityContext,
)

# ---------------------------------------------------------------------------
# CommunicationMode
# ---------------------------------------------------------------------------


class TestCommunicationMode:
    def test_values_are_correct_strings(self) -> None:
        assert CommunicationMode.INDIVIDUAL == "individual"
        assert CommunicationMode.BROADCAST == "broadcast"
        assert CommunicationMode.RELAY == "relay"

    def test_all_three_members_exist(self) -> None:
        modes = {m.value for m in CommunicationMode}
        assert modes == {"individual", "broadcast", "relay"}


# ---------------------------------------------------------------------------
# AgentResponse
# ---------------------------------------------------------------------------


class TestAgentResponse:
    def _make(self, **kwargs: object) -> AgentResponse:
        defaults: dict[str, object] = {
            "agent_id": "agent-0",
            "content": "The answer is 42.",
            "round_index": 0,
            "tokens_in": 10,
            "tokens_out": 20,
            "cost": 0.001,
        }
        defaults.update(kwargs)
        return AgentResponse(**defaults)  # type: ignore[arg-type]

    def test_fields_stored_correctly(self) -> None:
        r = self._make(agent_id="x", content="hello", round_index=1, tokens_in=5, tokens_out=8, cost=0.002)
        assert r.agent_id == "x"
        assert r.content == "hello"
        assert r.round_index == 1
        assert r.tokens_in == 5
        assert r.tokens_out == 8
        assert r.cost == 0.002

    def test_is_frozen(self) -> None:
        r = self._make()
        with pytest.raises((AttributeError, TypeError)):
            r.content = "changed"  # type: ignore[misc]

    def test_metadata_defaults_to_empty_dict(self) -> None:
        r = self._make()
        assert r.metadata == {}

    def test_two_instances_with_same_values_are_equal(self) -> None:
        r1 = self._make(agent_id="a")
        r2 = self._make(agent_id="a")
        assert r1 == r2

    def test_metadata_is_not_shared_between_instances(self) -> None:
        # Each instance must get its own metadata dict (no mutable default arg sharing).
        r1 = self._make()
        r2 = self._make()
        assert r1.metadata is not r2.metadata


# ---------------------------------------------------------------------------
# VisibilityContext
# ---------------------------------------------------------------------------


class TestVisibilityContext:
    def _make_response(self, agent_id: str, round_index: int = 0) -> AgentResponse:
        return AgentResponse(
            agent_id=agent_id,
            content=f"response from {agent_id}",
            round_index=round_index,
            tokens_in=5,
            tokens_out=10,
            cost=0.0,
        )

    def test_fields_stored_correctly(self) -> None:
        visible = [self._make_response("Response A"), self._make_response("Response B")]
        own = [self._make_response("agent-0", round_index=0)]
        ctx = VisibilityContext(
            agent_id="agent-0",
            round_index=1,
            visible_responses=visible,
            own_previous_responses=own,
            total_agents=3,
            communication_mode=CommunicationMode.INDIVIDUAL,
            original_prompt="What is 6x7?",
        )
        assert ctx.agent_id == "agent-0"
        assert ctx.round_index == 1
        assert len(ctx.visible_responses) == 2
        assert len(ctx.own_previous_responses) == 1
        assert ctx.total_agents == 3
        assert ctx.communication_mode == CommunicationMode.INDIVIDUAL
        assert ctx.original_prompt == "What is 6x7?"

    def test_is_frozen(self) -> None:
        ctx = VisibilityContext(
            agent_id="a",
            round_index=0,
            visible_responses=[],
            own_previous_responses=[],
            total_agents=1,
            communication_mode=CommunicationMode.BROADCAST,
            original_prompt="p",
        )
        with pytest.raises((AttributeError, TypeError)):
            ctx.agent_id = "b"  # type: ignore[misc]

    def test_each_communication_mode_accepted(self) -> None:
        for mode in CommunicationMode:
            ctx = VisibilityContext(
                agent_id="a",
                round_index=0,
                visible_responses=[],
                own_previous_responses=[],
                total_agents=1,
                communication_mode=mode,
                original_prompt="p",
            )
            assert ctx.communication_mode == mode

    def test_no_adjacency_matrix_field(self) -> None:
        # Constitution §3: the pipeline resolves adjacency to filtered lists before
        # building VisibilityContext. The adjacency matrix must NOT appear here.
        ctx = VisibilityContext(
            agent_id="a",
            round_index=0,
            visible_responses=[],
            own_previous_responses=[],
            total_agents=1,
            communication_mode=CommunicationMode.INDIVIDUAL,
            original_prompt="p",
        )
        assert not hasattr(ctx, "adjacency_matrix")


# ---------------------------------------------------------------------------
# AggregationResult
# ---------------------------------------------------------------------------


class TestAggregationResult:
    def test_fields_stored_correctly(self) -> None:
        r = AggregationResult(
            final_answer="42",
            confidence=0.9,
            method="MajorityVote",
        )
        assert r.final_answer == "42"
        assert r.confidence == 0.9
        assert r.method == "MajorityVote"

    def test_is_frozen(self) -> None:
        r = AggregationResult(final_answer="x", confidence=1.0, method="m")
        with pytest.raises((AttributeError, TypeError)):
            r.final_answer = "y"  # type: ignore[misc]

    def test_metadata_defaults_to_empty_dict(self) -> None:
        r = AggregationResult(final_answer="x", confidence=1.0, method="m")
        assert r.metadata == {}


# ---------------------------------------------------------------------------
# CouncilState
# ---------------------------------------------------------------------------


class TestCouncilState:
    def test_initial_factory(self) -> None:
        state = CouncilState.initial("What is 6x7?")
        assert state.question == "What is 6x7?"
        assert state.current_round == 0
        assert state.round_history == []
        assert state.total_cost == 0.0
        assert state.tokens_in == 0
        assert state.tokens_out == 0
        assert state.termination_reason == ""
        assert state.final_result is None

    def test_is_mutable(self) -> None:
        # CouncilState is mutable — the pipeline accumulates into it.
        state = CouncilState.initial("q")
        state.current_round = 1
        assert state.current_round == 1

    def test_round_history_not_shared(self) -> None:
        s1 = CouncilState.initial("q1")
        s2 = CouncilState.initial("q2")
        s1.round_history.append(
            AgentResponse(agent_id="a", content="r", round_index=0, tokens_in=1, tokens_out=1, cost=0.0)
        )
        assert s2.round_history == []


# ---------------------------------------------------------------------------
# CouncilResult
# ---------------------------------------------------------------------------


class TestCouncilResult:
    def _make(self) -> CouncilResult:
        return CouncilResult(
            final_answer="42",
            confidence=1.0,
            method="MajorityVote",
            rounds_used=1,
            total_cost=0.001,
            tokens_in=30,
            tokens_out=60,
            termination_reason="max_rounds",
            round_history=[],
        )

    def test_fields_stored_correctly(self) -> None:
        r = self._make()
        assert r.final_answer == "42"
        assert r.confidence == 1.0
        assert r.method == "MajorityVote"
        assert r.rounds_used == 1
        assert r.total_cost == 0.001
        assert r.tokens_in == 30
        assert r.tokens_out == 60
        assert r.termination_reason == "max_rounds"
        assert r.round_history == []

    def test_is_frozen(self) -> None:
        r = self._make()
        with pytest.raises((AttributeError, TypeError)):
            r.final_answer = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Zero cross-imports
# ---------------------------------------------------------------------------


def test_context_has_no_council_imports() -> None:
    """council/context.py must import nothing from the council package itself."""
    import importlib
    import importlib.util

    # Re-import with a clean module name copy to inspect source
    spec = importlib.util.find_spec("council.context")
    assert spec is not None
    assert spec.origin is not None

    with open(spec.origin) as f:
        source = f.read()

    # Any line that does 'from council.' or 'import council.' is a violation.
    bad_lines = [
        line
        for line in source.splitlines()
        if ("from council." in line or "import council." in line)
        and not line.strip().startswith("#")
    ]
    assert bad_lines == [], f"council/context.py imports from council/: {bad_lines}"
