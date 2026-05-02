"""Tests for council.symbolic.verify.cgs:cgs_to_ispl - the CGS → ISPL emitter.

Stage 3 / Slice 3.1 of the T7 ATLK revision (specs/t7-atlk-revision.md).
Pure-text structural tests for the ISPL emitter. The MCMAS-parse-success
test (which actually invokes mcmas) lives at
tests/integration/test_t7_atlk_emitter.py and is gated by
``RUN_INTEGRATION=1``.

Grammar references: MCMAS v1.3.0 manual §3.2.4 (page 19) — the
``is ::= semantics? environment? agents+ evaluation istates groups?
fairformulae? formulae`` production.
"""

from __future__ import annotations

import pytest

from council.symbolic.verify.cgs import canonical_t3_cgs, cgs_to_ispl
from council.symbolic.verify.ltlf import (
    Atom,
    CoalitionFinally,
    Knows,
)

# ---------------------------------------------------------------------------
# Required-section tests
# ---------------------------------------------------------------------------


class TestISPLRequiredSections:
    """The emitted text must contain every required ISPL block."""

    def test_emits_string(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        assert isinstance(out, str)
        assert len(out) > 0

    def test_contains_environment_block(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        assert "Agent Environment" in out
        assert "end Agent" in out

    def test_contains_each_agent_block(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        assert "Agent agent_alice" in out
        assert "Agent agent_bob" in out
        assert "Agent agent_carol" in out

    def test_contains_required_top_level_sections(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        for section in (
            "Evaluation",
            "end Evaluation",
            "InitStates",
            "end InitStates",
            "Groups",
            "end Groups",
            "Formulae",
            "end Formulae",
        ):
            assert section in out, f"missing section {section!r}"

    def test_contains_per_agent_subsections(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        # Per-agent subsections required by the ISPL grammar (page 19).
        # Lobsvars is OMITTED for canonical_t3_cgs because env.Obsvars is
        # observable by all agents by default (manual page 14).
        for sub in ("Vars", "Actions", "Protocol", "Evolution"):
            assert sub in out, f"missing per-agent subsection {sub!r}"


# ---------------------------------------------------------------------------
# Environment block tests
# ---------------------------------------------------------------------------


class TestEnvironmentBlock:
    """Public vars go in Obsvars; private go in Vars."""

    def test_obsvars_contains_round(self) -> None:
        cgs = canonical_t3_cgs(max_rounds=2)
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        assert "Obsvars:" in out
        assert "round : 0..2;" in out

    def test_obsvars_contains_disclosure_flags(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        for short in ("alice", "bob", "carol"):
            assert f"disclosed_p1_{short} : boolean;" in out
            assert f"voted_p1_{short} : boolean;" in out

    def test_environment_private_vars_empty(self) -> None:
        # canonical_t3_cgs has no private moderator state for the headline.
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        # The Environment's "Vars: ... end Vars" block should contain no
        # variable declarations (it may be omitted entirely if the
        # emitter chooses to skip empty blocks).
        # Either: no "Vars:" inside Environment, or an empty Vars block.
        env_start = out.index("Agent Environment")
        env_end = out.index("end Agent", env_start)
        env_block = out[env_start:env_end]
        if "Vars:" in env_block:
            # Empty block: Vars: ... end Vars with no var declarations
            vars_idx = env_block.index("Vars:")
            end_vars_idx = env_block.index("end Vars", vars_idx)
            inside = env_block[vars_idx + len("Vars:") : end_vars_idx].strip()
            assert inside == ""


# ---------------------------------------------------------------------------
# Agent block tests
# ---------------------------------------------------------------------------


class TestAgentBlock:
    """Per-agent blocks have the right vars, actions, protocol, evolution."""

    def test_actions_listed_per_agent(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        # The 4-action set appears in each agent block
        alice_start = out.index("Agent agent_alice")
        alice_end = out.index("end Agent", alice_start)
        alice_block = out[alice_start:alice_end]
        for action in (
            "propose_no_witness",
            "propose_with_witness",
            "vote_p1",
            "abstain",
        ):
            assert action in alice_block

    def test_private_vars_listed_per_agent(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        for short in ("alice", "bob", "carol"):
            agent_start = out.index(f"Agent agent_{short}")
            agent_end = out.index("end Agent", agent_start)
            agent_block = out[agent_start:agent_end]
            assert "has_witness_p1 : boolean;" in agent_block

    def test_protocol_clause_gates_propose_with_witness(self) -> None:
        # The defining encoding fact in ISPL form: a Protocol clause
        # whose precondition includes ``has_witness_p1 = true`` enables
        # propose_with_witness.
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        alice_start = out.index("Agent agent_alice")
        alice_end = out.index("end Agent", alice_start)
        alice_block = out[alice_start:alice_end]
        proto_start = alice_block.index("Protocol:")
        proto_end = alice_block.index("end Protocol", proto_start)
        proto_block = alice_block[proto_start:proto_end]
        # The clause that includes propose_with_witness must condition on
        # has_witness_p1 = true.
        assert "has_witness_p1 = true" in proto_block
        assert "propose_with_witness" in proto_block


# ---------------------------------------------------------------------------
# Evaluation, InitStates, Groups blocks
# ---------------------------------------------------------------------------


class TestEvaluationBlock:
    def test_evaluation_includes_consensus_p1(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        eval_start = out.index("Evaluation")
        eval_end = out.index("end Evaluation", eval_start)
        eval_block = out[eval_start:eval_end]
        assert "consensus_p1" in eval_block
        # The expression should reference all three agents' votes.
        assert "voted_p1_alice" in eval_block

    def test_evaluation_includes_per_agent_evidence_aps(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        eval_start = out.index("Evaluation")
        eval_end = out.index("end Evaluation", eval_start)
        eval_block = out[eval_start:eval_end]
        for short in ("alice", "bob", "carol"):
            assert f"evidence_p1_{short}" in eval_block


class TestInitStatesBlock:
    def test_init_states_round_zero(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        init_start = out.index("InitStates")
        init_end = out.index("end InitStates", init_start)
        init_block = out[init_start:init_end]
        assert "Environment.round = 0" in init_block

    def test_init_states_no_witness_in_t3(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        init_start = out.index("InitStates")
        init_end = out.index("end InitStates", init_start)
        init_block = out[init_start:init_end]
        assert "agent_alice.has_witness_p1 = false" in init_block
        assert "agent_bob.has_witness_p1 = false" in init_block
        assert "agent_carol.has_witness_p1 = false" in init_block

    def test_init_states_alice_witness_positive_instance(self) -> None:
        cgs = canonical_t3_cgs(witness_initial={"agent_alice": True})
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        init_start = out.index("InitStates")
        init_end = out.index("end InitStates", init_start)
        init_block = out[init_start:init_end]
        assert "agent_alice.has_witness_p1 = true" in init_block
        assert "agent_bob.has_witness_p1 = false" in init_block


class TestGroupsBlock:
    def test_singleton_groups_emitted(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        groups_start = out.index("Groups")
        groups_end = out.index("end Groups", groups_start)
        groups_block = out[groups_start:groups_end]
        assert "g_alice = { agent_alice };" in groups_block
        assert "g_bob = { agent_bob };" in groups_block
        assert "g_carol = { agent_carol };" in groups_block


# ---------------------------------------------------------------------------
# Formulae translation tests
# ---------------------------------------------------------------------------


class TestFormulaeBlock:
    """Formulae are translated via ltlf_to_ctl from Slice 1.2."""

    def test_atom_formula(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        f_start = out.index("Formulae")
        f_end = out.index("end Formulae", f_start)
        f_block = out[f_start:f_end]
        assert "consensus_p1;" in f_block

    def test_t7_headline_atlk_formula(self) -> None:
        # The headline T7 formula in MCMAS syntax.
        cgs = canonical_t3_cgs()
        formula = CoalitionFinally(
            group="g_alice",
            arg=Knows(agent="agent_alice", arg=Atom("evidence_p1_alice")),
        )
        out = cgs_to_ispl(cgs, [formula])
        assert "<g_alice> F K(agent_alice, evidence_p1_alice);" in out

    def test_multiple_formulae_emitted_in_order(self) -> None:
        cgs = canonical_t3_cgs()
        formulae = [
            CoalitionFinally(group=f"g_{a}", arg=Atom(f"evidence_p1_{a}"))
            for a in ("alice", "bob", "carol")
        ]
        out = cgs_to_ispl(cgs, formulae)
        f_start = out.index("Formulae")
        f_end = out.index("end Formulae", f_start)
        f_block = out[f_start:f_end]
        assert "<g_alice> F evidence_p1_alice;" in f_block
        assert "<g_bob> F evidence_p1_bob;" in f_block
        assert "<g_carol> F evidence_p1_carol;" in f_block


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestEmitterValidation:
    def test_empty_formulae_raises(self) -> None:
        # MCMAS grammar requires Formulae to be non-empty
        # (formlist ::= formula ; | formlist formula ;).
        cgs = canonical_t3_cgs()
        with pytest.raises(ValueError, match=r"at least one formula"):
            cgs_to_ispl(cgs, [])


class TestLobsvarsOptIn:
    """Per-agent Lobsvars opt-in into Environment.private_vars.

    Public env vars in Environment.Obsvars are observable by every
    agent without any Lobsvars declaration (MCMAS manual page 14).
    Lobsvars is the per-agent opt-in into Environment.Vars (the
    private moderator state). The emitter should:
      - omit the Lobsvars block when agent.lobsvars is empty;
      - emit it when non-empty;
      - reject any reference to a name not in env.private_vars
        (because public Obsvars vars are already auto-observable
        and listing them in Lobsvars triggers MCMAS errors).
    """

    def test_default_agent_has_no_lobsvars(self) -> None:
        cgs = canonical_t3_cgs()
        out = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        assert "Lobsvars" not in out

    def test_lobsvars_emitted_when_agent_opts_in(self) -> None:
        from council.symbolic.verify.cgs import (
            CGSAgentSpec,
            CGSEnvironmentSpec,
            CGSGroup,
            CGSProtocolClause,
            DeliberationCGS,
        )

        env = CGSEnvironmentSpec(
            public_vars={"round": "0..1"},
            private_vars={"moderator_alert": "boolean"},
            initial_values={"round": "0", "moderator_alert": "false"},
        )
        agent = CGSAgentSpec(
            agent_id="agent_alice",
            actions=("noop",),
            private_vars={"x": "boolean"},
            initial_values={"x": "false"},
            protocol=(CGSProtocolClause(condition="Other", actions=("noop",)),),
            lobsvars=("moderator_alert",),
        )
        from council.symbolic.verify.cgs import CGSAtomicProposition

        cgs = DeliberationCGS(
            agents=(agent,),
            environment=env,
            atomic_propositions=(
                CGSAtomicProposition(name="ok", expression="x = true"),
            ),
            groups=(CGSGroup(name="g_alice", members=("agent_alice",)),),
            max_rounds=1,
        )
        out = cgs_to_ispl(cgs, [Atom("ok")])
        assert "Lobsvars = { moderator_alert };" in out

    def test_lobsvars_referencing_public_var_raises(self) -> None:
        # Manual page 14 forbids listing Obsvars members in any agent's
        # Lobsvars; MCMAS would reject this with "not defined in the
        # environment". The emitter must catch it earlier.
        from council.symbolic.verify.cgs import (
            CGSAgentSpec,
            CGSAtomicProposition,
            CGSEnvironmentSpec,
            CGSGroup,
            CGSProtocolClause,
            DeliberationCGS,
        )

        env = CGSEnvironmentSpec(
            public_vars={"round": "0..1", "tick_flag": "boolean"},
            private_vars={},
            initial_values={"round": "0", "tick_flag": "false"},
        )
        bad_agent = CGSAgentSpec(
            agent_id="agent_alice",
            actions=("noop",),
            private_vars={"x": "boolean"},
            initial_values={"x": "false"},
            protocol=(CGSProtocolClause(condition="Other", actions=("noop",)),),
            lobsvars=("tick_flag",),  # WRONG — public var, observable by default
        )
        cgs = DeliberationCGS(
            agents=(bad_agent,),
            environment=env,
            atomic_propositions=(
                CGSAtomicProposition(name="ok", expression="x = true"),
            ),
            groups=(CGSGroup(name="g_alice", members=("agent_alice",)),),
            max_rounds=1,
        )
        with pytest.raises(ValueError, match=r"not in Environment\.private_vars"):
            cgs_to_ispl(cgs, [Atom("ok")])
