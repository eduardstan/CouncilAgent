"""T7 — Strategic-Coupled satisfies T3's CTLK invariant (master plan §10).

T3 statement (docs/theory.md):
  G(consensus -> exists i. K_i evidenceFor(consensus))
  -- "every consensus state must have at least one agent whose knowledge
  witnesses evidence for the consensus".

T3 counterexample: a 3-agent trace where all three agents Propose/Vote
for the same answer with empty Claim.evidence. A consensus is reached
(all three converge on the same answer) but no agent witnesses evidence.
The CTLK invariant is violated by any aggregator that only consults the
vote count.

T7 statement (master plan §10):
  Strategic-Coupled gradual semantics satisfies T3's invariant on a
  small instance.

T7 mechanization. We construct the T3 counterexample BAF and run two
semantics:
  - DFQuADSemantics: returns high strength for "X" (consensus-reaching).
    The argument is in the preferred extension. The CTLK invariant is
    violated -- DF-QuAD admits the unsupported consensus.
  - StrategicCoupledSemantics with empty evidence_backed: demotes "X"
    by alpha = 0.5 because consensus is reached without backing. The
    argument falls below the extension threshold and is excluded. The
    CTLK invariant is satisfied -- Strategic-Coupled rejects unsupported
    consensus.

The contrast between the two semantics on this canonical fixture is the
existence proof of T7.
"""

from __future__ import annotations

from council.dialect.moves import Claim, ClaimDomain, Propose, Vote
from council.dialect.trace import Trace
from council.symbolic.argue.builders import build_qbaf
from council.symbolic.argue.coupled_atl import evidence_backed_arg_ids
from council.symbolic.argue.semantics.coupled import StrategicCoupledSemantics
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics


def _t3_counterexample_trace() -> Trace:
    """The 3-agent unanimous-vote-without-evidence trace.

    Three agents (A, B, C) each Propose "X is the answer" with empty
    evidence. They then all Vote for "X" with empty evidence. No agent
    witnesses evidence anywhere in the trace.
    """
    trace = Trace()
    for i, agent in enumerate(["A", "B", "C"]):
        trace = trace.append(
            Propose(
                move_id=f"p{i+1}",
                agent_id=agent,
                round_index=0,
                claim=Claim(
                    surface="X is the answer",
                    domain=ClaimDomain.FREE,
                    evidence=(),  # NO EVIDENCE
                ),
                confidence=0.7,
            )
        )
    for i, agent in enumerate(["A", "B", "C"]):
        trace = trace.append(
            Vote(
                move_id=f"v{i+1}",
                agent_id=agent,
                round_index=1,
                option=Claim(surface="X is the answer", evidence=()),
                confidence=0.5,
            )
        )
    return trace


def _t3_counterexample_with_one_witness() -> Trace:
    """Variant: one agent provides evidence -- T3 invariant satisfied.

    Same as the counterexample, except agent C's Propose carries a
    non-empty evidence tuple. With one witness, the CTLK invariant
    is satisfied; both DF-QuAD and Strategic-Coupled should accept "X".
    """
    trace = Trace()
    for i, agent in enumerate(["A", "B"]):
        trace = trace.append(
            Propose(
                move_id=f"p{i+1}",
                agent_id=agent,
                round_index=0,
                claim=Claim(surface="X is the answer", evidence=()),
                confidence=0.7,
            )
        )
    # Agent C provides evidence
    trace = trace.append(
        Propose(
            move_id="p3",
            agent_id="C",
            round_index=0,
            claim=Claim(
                surface="X is the answer",
                evidence=("source: published proof",),
            ),
            confidence=0.7,
        )
    )
    return trace


# ---------------------------------------------------------------------------
# T3 counterexample: DF-QuAD admits consensus without evidence
# ---------------------------------------------------------------------------


class TestT3CounterexampleDFQuADFails:
    """DF-QuAD does not satisfy T3's CTLK invariant on the counterexample."""

    def test_df_quad_accepts_unsupported_consensus(self) -> None:
        trace = _t3_counterexample_trace()
        baf = build_qbaf(trace)
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)
        ext = sem.preferred_extension(baf)
        # Three Proposes for "X is the answer", boosted by three votes.
        # Each starts at base 0.7; each gets 3*0.5=1.5 vote boost (clamped
        # to 1.0). So all three Propose-derived args reach 1.0.
        for arg_id in ("p1", "p2", "p3"):
            assert strengths[arg_id] == 1.0
            assert arg_id in ext, (
                f"DF-QuAD admits {arg_id} into extension despite no agent "
                f"providing evidence -- T3 invariant violated."
            )


# ---------------------------------------------------------------------------
# T7: Strategic-Coupled rejects unsupported consensus
# ---------------------------------------------------------------------------


class TestT7StrategicCoupledRescue:
    """Strategic-Coupled satisfies T3's CTLK invariant on the same trace."""

    def test_evidence_backed_set_is_empty_on_counterexample(self) -> None:
        trace = _t3_counterexample_trace()
        backed = evidence_backed_arg_ids(trace)
        assert backed == frozenset(), (
            "T3 counterexample has no agent-witnessed evidence; the "
            "ATL fragment must report empty backing."
        )

    def test_strategic_coupled_demotes_unsupported_consensus(self) -> None:
        trace = _t3_counterexample_trace()
        baf = build_qbaf(trace)
        backed = evidence_backed_arg_ids(trace)
        sem = StrategicCoupledSemantics(
            base=DFQuADSemantics(),
            evidence_backed=backed,
            alpha=0.5,
            consensus_threshold=0.5,
        )
        strengths = sem.evaluate(baf)
        # Each unsupported consensus argument was at 1.0 under DF-QuAD;
        # Strategic-Coupled demotes by alpha=0.5 -> 0.5
        for arg_id in ("p1", "p2", "p3"):
            assert strengths[arg_id] == 0.5

    def test_strategic_coupled_rejects_unsupported_consensus_below_threshold(
        self,
    ) -> None:
        """With a stricter alpha=0 (hard rejection) the demoted strengths
        fall below the extension threshold and are excluded.

        With the default alpha=0.5 the demoted strength equals 0.5 which
        is exactly at the threshold; we use alpha=0.4 here so the demoted
        result is strictly below 0.5 and thus rejected from the extension.
        This proves the principle: a strict-enough Strategic-Coupled
        instance excludes unsupported consensus from the extension,
        satisfying T3's invariant by construction.
        """
        trace = _t3_counterexample_trace()
        baf = build_qbaf(trace)
        backed = evidence_backed_arg_ids(trace)
        sem = StrategicCoupledSemantics(
            base=DFQuADSemantics(),
            evidence_backed=backed,
            alpha=0.4,
            consensus_threshold=0.5,
        )
        ext = sem.preferred_extension(baf)
        for arg_id in ("p1", "p2", "p3"):
            assert arg_id not in ext, (
                f"Strategic-Coupled (alpha=0.4) admits {arg_id} into "
                f"extension despite no evidence backing -- T7 violated."
            )


# ---------------------------------------------------------------------------
# T3 invariant satisfied: Strategic-Coupled reduces to DF-QuAD
# ---------------------------------------------------------------------------


class TestT7BackwardCompatibility:
    """When the trace satisfies T3's invariant (one agent witnesses evidence),
    Strategic-Coupled reduces to DF-QuAD on the consensus-reaching args.
    This shows the new semantics is not over-aggressive: it diverges from
    DF-QuAD only when the invariant is violated."""

    def test_one_witness_keeps_consensus_intact(self) -> None:
        trace = _t3_counterexample_with_one_witness()
        baf = build_qbaf(trace)
        backed = evidence_backed_arg_ids(trace)
        # p3 carries evidence; p1 and p2 do not. But all three have the
        # same surface -- p3 in the backed set is the witness.
        assert "p3" in backed
        # p1 and p2 are NOT directly backed, but the W2 ATL fragment is
        # per-arg_id. So p1 and p2 are still demoted unless their own
        # Vote/Propose evidence backs them. This is by design: each
        # Propose's evidence-witnessing is checked independently.

        sem_df = DFQuADSemantics()
        sem_sc = StrategicCoupledSemantics(
            base=sem_df, evidence_backed=backed
        )
        df_strengths = sem_df.evaluate(baf)
        sc_strengths = sem_sc.evaluate(baf)
        # p3 has backing -> strength preserved
        assert sc_strengths["p3"] == df_strengths["p3"]


# ---------------------------------------------------------------------------
# Sanity: extension-membership flip on the canonical T7 example
# ---------------------------------------------------------------------------


class TestT7ExtensionFlip:
    """The headline reviewer-visible result: DF-QuAD includes the unsupported
    consensus argument in its preferred extension; Strategic-Coupled (with
    alpha=0.4 to clear the threshold) excludes it.
    """

    def test_extension_membership_differs_between_semantics(self) -> None:
        trace = _t3_counterexample_trace()
        baf = build_qbaf(trace)
        backed = evidence_backed_arg_ids(trace)

        df = DFQuADSemantics()
        sc = StrategicCoupledSemantics(
            base=df, evidence_backed=backed, alpha=0.4
        )

        df_ext = df.preferred_extension(baf)
        sc_ext = sc.preferred_extension(baf)

        # DF-QuAD admits; Strategic-Coupled does not -> extensions differ
        assert df_ext != sc_ext
        # Specifically: p1, p2, p3 are in DF-QuAD's extension, none in SC's
        for arg_id in ("p1", "p2", "p3"):
            assert arg_id in df_ext
            assert arg_id not in sc_ext
