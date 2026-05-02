"""Tests for council.symbolic.verify.cgs - DeliberationCGS data model.

Stage 2 / Slice 2.1 of the T7 ATLK revision (specs/t7-atlk-revision.md).
Pins the symbolic CGS data model and the canonical T_3 factory used by
the headline theorem. Pure Python; no MCMAS subprocess.

Encoding decisions tested here (will be locked in ADR-0020 at Stage 4):
  - Per-agent private state (agent.Vars): has_witness_p1 (boolean)
  - Public-to-all state (Environment.Obsvars): round, disclosed_p1_<id>,
    voted_p1_<id>
  - Action set per agent (T_3 projection):
    {propose_no_witness, propose_with_witness, vote_p1, abstain}
  - Protocol: propose_with_witness enabled iff has_witness_p1 = true
  - APs: consensus_p1, evidence_p1_<id>, voted_p1_<id>
  - Singleton group g_<id> per agent (for ATL coalition operators)
  - max_rounds default = 2
"""

from __future__ import annotations

import dataclasses

import pytest

from council.symbolic.verify.cgs import (
    CGSAgentSpec,
    CGSAtomicProposition,
    CGSEnvironmentSpec,
    CGSGroup,
    CGSProtocolClause,
    canonical_t3_cgs,
)

# ---------------------------------------------------------------------------
# Value-object invariants
# ---------------------------------------------------------------------------


class TestCGSValueObjects:
    """Frozen+slots dataclasses, hashable, structural equality."""

    def test_agent_spec_is_frozen(self) -> None:
        spec = CGSAgentSpec(
            agent_id="agent_alice",
            actions=("vote_p1", "abstain"),
            private_vars={"has_witness_p1": "boolean"},
            initial_values={"has_witness_p1": "false"},
            protocol=(CGSProtocolClause(condition="Other", actions=("vote_p1", "abstain")),),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.agent_id = "agent_bob"  # type: ignore[misc]

    def test_environment_spec_is_frozen(self) -> None:
        env = CGSEnvironmentSpec(
            public_vars={"round": "0..3"},
            private_vars={},
            initial_values={"round": "0"},
            evolution_rules=(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            env.public_vars = {}  # type: ignore[misc]

    def test_atomic_proposition_is_frozen(self) -> None:
        ap = CGSAtomicProposition(name="consensus_p1", expression="Environment.voted_p1_alice = true")
        with pytest.raises(dataclasses.FrozenInstanceError):
            ap.name = "other"  # type: ignore[misc]

    def test_group_is_frozen(self) -> None:
        g = CGSGroup(name="g_alice", members=("agent_alice",))
        with pytest.raises(dataclasses.FrozenInstanceError):
            g.name = "g_bob"  # type: ignore[misc]

    def test_agent_spec_hashable(self) -> None:
        a = CGSAgentSpec(
            agent_id="agent_alice",
            actions=("vote_p1",),
            private_vars={"x": "boolean"},
            initial_values={"x": "false"},
            protocol=(CGSProtocolClause(condition="Other", actions=("vote_p1",)),),
        )
        b = CGSAgentSpec(
            agent_id="agent_alice",
            actions=("vote_p1",),
            private_vars={"x": "boolean"},
            initial_values={"x": "false"},
            protocol=(CGSProtocolClause(condition="Other", actions=("vote_p1",)),),
        )
        assert hash(a) == hash(b)
        assert {a, b} == {a}


# ---------------------------------------------------------------------------
# Canonical T_3 CGS structural tests
# ---------------------------------------------------------------------------


class TestCanonicalT3CGSStructure:
    """The hand-built canonical T_3 CGS has the structure the spec demands."""

    def test_three_agents(self) -> None:
        cgs = canonical_t3_cgs()
        agent_ids = tuple(a.agent_id for a in cgs.agents)
        assert agent_ids == ("agent_alice", "agent_bob", "agent_carol")

    def test_each_agent_has_t3_action_set(self) -> None:
        cgs = canonical_t3_cgs()
        expected = frozenset({
            "propose_no_witness",
            "propose_with_witness",
            "vote_p1",
            "abstain",
        })
        for agent in cgs.agents:
            assert frozenset(agent.actions) == expected

    def test_each_agent_has_witness_var(self) -> None:
        cgs = canonical_t3_cgs()
        for agent in cgs.agents:
            assert "has_witness_p1" in agent.private_vars
            assert agent.private_vars["has_witness_p1"] == "boolean"

    def test_environment_has_round_counter(self) -> None:
        cgs = canonical_t3_cgs(max_rounds=2)
        assert "round" in cgs.environment.public_vars
        assert cgs.environment.public_vars["round"] == "0..2"

    def test_environment_has_per_agent_disclosure_flags(self) -> None:
        cgs = canonical_t3_cgs()
        for short_id in ("alice", "bob", "carol"):
            assert f"disclosed_p1_{short_id}" in cgs.environment.public_vars
            assert cgs.environment.public_vars[f"disclosed_p1_{short_id}"] == "boolean"

    def test_environment_has_per_agent_vote_flags(self) -> None:
        cgs = canonical_t3_cgs()
        for short_id in ("alice", "bob", "carol"):
            assert f"voted_p1_{short_id}" in cgs.environment.public_vars
            assert cgs.environment.public_vars[f"voted_p1_{short_id}"] == "boolean"

    def test_environment_private_vars_empty_for_headline(self) -> None:
        # Headline T_3 has no moderator/private state in the environment.
        cgs = canonical_t3_cgs()
        assert cgs.environment.private_vars == {}

    def test_atomic_propositions_include_consensus_evidence_voted(self) -> None:
        cgs = canonical_t3_cgs()
        ap_names = {ap.name for ap in cgs.atomic_propositions}
        assert "consensus_p1" in ap_names
        for short_id in ("alice", "bob", "carol"):
            assert f"evidence_p1_{short_id}" in ap_names
            assert f"voted_p1_{short_id}" in ap_names

    def test_singleton_groups_per_agent(self) -> None:
        cgs = canonical_t3_cgs()
        groups_by_name = {g.name: g for g in cgs.groups}
        assert set(groups_by_name) == {"g_alice", "g_bob", "g_carol"}
        assert groups_by_name["g_alice"].members == ("agent_alice",)
        assert groups_by_name["g_bob"].members == ("agent_bob",)
        assert groups_by_name["g_carol"].members == ("agent_carol",)

    def test_default_max_rounds_is_two(self) -> None:
        cgs = canonical_t3_cgs()
        assert cgs.max_rounds == 2

    def test_propose_with_witness_protocol_clause_gated_by_has_witness(self) -> None:
        # The defining encoding fact: propose_with_witness is enabled
        # ONLY when the agent's has_witness_p1 is true.
        cgs = canonical_t3_cgs()
        alice = next(a for a in cgs.agents if a.agent_id == "agent_alice")
        protocol_with_pwt = [c for c in alice.protocol if "propose_with_witness" in c.actions]
        assert protocol_with_pwt, "propose_with_witness must appear in some protocol clause"
        for clause in protocol_with_pwt:
            assert "has_witness_p1 = true" in clause.condition


# ---------------------------------------------------------------------------
# Initial state tests
# ---------------------------------------------------------------------------


class TestCanonicalT3CGSInitialState:
    """The T_3 instance: no agent has witness, no disclosure, no votes."""

    def test_default_initial_state_t3_no_witness(self) -> None:
        cgs = canonical_t3_cgs()
        for agent in cgs.agents:
            assert agent.initial_values["has_witness_p1"] == "false"

    def test_default_initial_state_round_zero(self) -> None:
        cgs = canonical_t3_cgs()
        assert cgs.environment.initial_values["round"] == "0"

    def test_default_initial_state_no_disclosures(self) -> None:
        cgs = canonical_t3_cgs()
        for short_id in ("alice", "bob", "carol"):
            assert cgs.environment.initial_values[f"disclosed_p1_{short_id}"] == "false"

    def test_default_initial_state_no_votes(self) -> None:
        cgs = canonical_t3_cgs()
        for short_id in ("alice", "bob", "carol"):
            assert cgs.environment.initial_values[f"voted_p1_{short_id}"] == "false"

    def test_alice_witness_initial_state(self) -> None:
        # Positive instance: alice starts with witness, others don't.
        # Used in Stage 5 to assert <g_alice> F K(alice, evidence_p1_alice) is TRUE.
        cgs = canonical_t3_cgs(witness_initial={"agent_alice": True})
        alice = next(a for a in cgs.agents if a.agent_id == "agent_alice")
        bob = next(a for a in cgs.agents if a.agent_id == "agent_bob")
        carol = next(a for a in cgs.agents if a.agent_id == "agent_carol")
        assert alice.initial_values["has_witness_p1"] == "true"
        assert bob.initial_values["has_witness_p1"] == "false"
        assert carol.initial_values["has_witness_p1"] == "false"


# ---------------------------------------------------------------------------
# Step simulator (used by Stage 5 faithfulness test)
# ---------------------------------------------------------------------------


class TestStepSimulator:
    """The Python-side step simulator must match the ISPL evolution rules.

    This is what Stage 5's faithfulness test relies on: enumerate joint
    strategies in MCMAS interactive mode, and assert state-by-state
    agreement with these step() outputs.
    """

    def test_initial_state_round_zero(self) -> None:
        cgs = canonical_t3_cgs()
        s = cgs.initial_state()
        assert s["Environment"]["round"] == "0"

    def test_step_increments_round(self) -> None:
        cgs = canonical_t3_cgs()
        s0 = cgs.initial_state()
        joint = {"agent_alice": "abstain", "agent_bob": "abstain", "agent_carol": "abstain"}
        s1 = cgs.step(s0, joint)
        assert s1["Environment"]["round"] == "1"

    def test_step_propose_no_witness_does_not_disclose(self) -> None:
        cgs = canonical_t3_cgs()
        s0 = cgs.initial_state()
        joint = {
            "agent_alice": "propose_no_witness",
            "agent_bob": "propose_no_witness",
            "agent_carol": "propose_no_witness",
        }
        s1 = cgs.step(s0, joint)
        for short in ("alice", "bob", "carol"):
            assert s1["Environment"][f"disclosed_p1_{short}"] == "false"

    def test_step_propose_with_witness_when_alice_has_witness(self) -> None:
        # Positive instance: alice starts with witness; chooses
        # propose_with_witness; env.disclosed_p1_alice flips to true.
        cgs = canonical_t3_cgs(witness_initial={"agent_alice": True})
        s0 = cgs.initial_state()
        joint = {
            "agent_alice": "propose_with_witness",
            "agent_bob": "abstain",
            "agent_carol": "abstain",
        }
        s1 = cgs.step(s0, joint)
        assert s1["Environment"]["disclosed_p1_alice"] == "true"
        assert s1["Environment"]["disclosed_p1_bob"] == "false"
        assert s1["Environment"]["disclosed_p1_carol"] == "false"

    def test_step_rejects_propose_with_witness_without_witness(self) -> None:
        # T_3 instance: alice has no witness; choosing propose_with_witness
        # is illegal (protocol disables it). Step must raise.
        cgs = canonical_t3_cgs()
        s0 = cgs.initial_state()
        joint = {
            "agent_alice": "propose_with_witness",
            "agent_bob": "abstain",
            "agent_carol": "abstain",
        }
        with pytest.raises(ValueError, match=r"not enabled|illegal action"):
            cgs.step(s0, joint)

    def test_step_vote_sets_voted_flag(self) -> None:
        cgs = canonical_t3_cgs()
        s0 = cgs.initial_state()
        joint = {"agent_alice": "vote_p1", "agent_bob": "abstain", "agent_carol": "abstain"}
        s1 = cgs.step(s0, joint)
        assert s1["Environment"]["voted_p1_alice"] == "true"
        assert s1["Environment"]["voted_p1_bob"] == "false"

    def test_is_terminal_at_max_rounds(self) -> None:
        cgs = canonical_t3_cgs(max_rounds=2)
        s = cgs.initial_state()
        assert not cgs.is_terminal(s)
        joint = {a.agent_id: "abstain" for a in cgs.agents}
        s = cgs.step(s, joint)
        assert not cgs.is_terminal(s)
        s = cgs.step(s, joint)
        assert cgs.is_terminal(s)

    def test_step_at_terminal_state_keeps_round_saturated(self) -> None:
        # Once we hit max_rounds, further steps stay in the terminal state.
        cgs = canonical_t3_cgs(max_rounds=2)
        s = cgs.initial_state()
        joint = {a.agent_id: "abstain" for a in cgs.agents}
        for _ in range(5):
            s = cgs.step(s, joint)
        assert s["Environment"]["round"] == "2"
        assert cgs.is_terminal(s)


# ---------------------------------------------------------------------------
# Atomic propositions evaluation
# ---------------------------------------------------------------------------


class TestEvaluateAtomicPropositions:
    """evaluate_atomic_propositions(state) returns dict[ap_name, bool]."""

    def test_no_consensus_at_initial_state(self) -> None:
        cgs = canonical_t3_cgs()
        s = cgs.initial_state()
        aps = cgs.evaluate_atomic_propositions(s)
        assert aps["consensus_p1"] is False

    def test_no_evidence_at_initial_state_t3(self) -> None:
        cgs = canonical_t3_cgs()
        s = cgs.initial_state()
        aps = cgs.evaluate_atomic_propositions(s)
        for short_id in ("alice", "bob", "carol"):
            assert aps[f"evidence_p1_{short_id}"] is False

    def test_consensus_after_all_three_vote(self) -> None:
        cgs = canonical_t3_cgs(max_rounds=3)
        s = cgs.initial_state()
        s = cgs.step(s, {a.agent_id: "vote_p1" for a in cgs.agents})
        aps = cgs.evaluate_atomic_propositions(s)
        assert aps["consensus_p1"] is True

    def test_evidence_alice_after_alice_discloses(self) -> None:
        cgs = canonical_t3_cgs(witness_initial={"agent_alice": True})
        s = cgs.initial_state()
        s = cgs.step(
            s,
            {
                "agent_alice": "propose_with_witness",
                "agent_bob": "abstain",
                "agent_carol": "abstain",
            },
        )
        aps = cgs.evaluate_atomic_propositions(s)
        assert aps["evidence_p1_alice"] is True
        assert aps["evidence_p1_bob"] is False
        assert aps["evidence_p1_carol"] is False


# ---------------------------------------------------------------------------
# ISPL Boolean evaluator (recursive-descent, no eval() —
# replaced post-constitution-reviewer's C1 finding)
# ---------------------------------------------------------------------------


class TestEvalCondition:
    """Lock the recursive-descent parser/evaluator against eval()'s
    permissiveness. The grammar is documented in the _eval_condition
    docstring; this class pins it.
    """

    @staticmethod
    def _eval(expression: str, **vars_: str) -> bool:
        from council.symbolic.verify.cgs import _eval_condition

        return _eval_condition(expression, vars_, {})

    def test_simple_equality_true(self) -> None:
        assert self._eval("x = true", x="true") is True

    def test_simple_equality_false(self) -> None:
        assert self._eval("x = true", x="false") is False

    def test_inequality_via_negation(self) -> None:
        assert self._eval("! x = true", x="false") is True
        assert self._eval("not x = true", x="false") is True

    def test_conjunction_short_form(self) -> None:
        assert self._eval("x = true and y = true", x="true", y="true") is True
        assert self._eval("x = true and y = true", x="true", y="false") is False

    def test_disjunction(self) -> None:
        assert self._eval("x = true or y = true", x="false", y="true") is True
        assert self._eval("x = true or y = true", x="false", y="false") is False

    def test_parentheses(self) -> None:
        assert self._eval("(x = true)", x="true") is True
        assert (
            self._eval("! (x = true and y = true)", x="true", y="false") is True
        )

    def test_integer_comparison(self) -> None:
        assert self._eval("round = 1", round="1") is True
        assert self._eval("round = 1", round="2") is False

    def test_qualified_environment_reference(self) -> None:
        from council.symbolic.verify.cgs import _eval_condition

        out = _eval_condition(
            "Environment.round = 0", {}, {"round": "0"}
        )
        assert out is True

    def test_rejects_illegal_character(self) -> None:
        with pytest.raises(ValueError, match=r"illegal character"):
            self._eval("x * y = 1", x="1", y="1")

    def test_rejects_unbalanced_parens(self) -> None:
        with pytest.raises(ValueError, match=r"expected '\)'"):
            self._eval("(x = true", x="true")

    def test_rejects_unknown_name(self) -> None:
        with pytest.raises(ValueError, match=r"unknown name"):
            self._eval("undefined_var = true")

    def test_rejects_trailing_junk(self) -> None:
        with pytest.raises(ValueError, match=r"trailing"):
            self._eval("x = true x", x="true")

    def test_rejects_attribute_chain(self) -> None:
        # qualified name is at most one '.'; attribute chains are not in the grammar.
        with pytest.raises(ValueError):
            self._eval("a.b.c = true")

    def test_rejects_malicious_function_call(self) -> None:
        # The previous eval()-based implementation could in principle
        # have parsed "len(x) = 0" if Python builtins leaked; the new
        # parser has no concept of function calls and must raise.
        with pytest.raises(ValueError):
            self._eval("len(x) = 0", x="true")
