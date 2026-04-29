"""L1 verification — named-property library.

Ten citable LTL_f properties of multi-agent deliberation, each with a name, a
human-readable formula, and a `compile()` method that returns a fresh
`LTL3Monitor`. The PROPERTY_REGISTRY maps names to classes for genome-driven
configuration (the YAML `monitors:` field references these names).

All formulas are written against the atomic propositions emitted by
`Trace.to_events()`:
  - is_propose, is_challenge, is_concede, is_vote, is_question, is_clarify,
    is_retract, is_abstain, is_pass        (force flags, W0)
  - has_evidence                            (W1 Patch A: Propose/Vote with evidence)
  - has_prior_challenge                     (W1 Patch A: any earlier Challenge)
  - same_agent_concede_run_ge_3             (W1 Patch A: 3-in-a-row by same agent)
"""

from __future__ import annotations

from typing import ClassVar

from council.symbolic.verify.ltlf import parse
from council.symbolic.verify.monitor import LTL3Monitor, Property
from council.symbolic.verify.spot_backend import make_monitor

# ---------------------------------------------------------------------------
# 1. EventuallyDecide — F is_vote
# ---------------------------------------------------------------------------

class EventuallyDecide(Property):
    """Every council run must eventually emit a Vote.

    Formal: F(is_vote)
    """

    name: ClassVar[str] = "EventuallyDecide"
    formula: ClassVar[str] = "F(is_vote)"

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))


# ---------------------------------------------------------------------------
# 2. NoSycophancyCascade — G !same_agent_concede_run_ge_3
# ---------------------------------------------------------------------------

class NoSycophancyCascade(Property):
    """No agent may emit 3+ Concedes in a row.

    Formal: G(!same_agent_concede_run_ge_3)
    Defends against the sycophancy pattern where one agent keeps yielding to
    another (Constitution §11; cited in P1 ablation).
    """

    name: ClassVar[str] = "NoSycophancyCascade"
    formula: ClassVar[str] = "G(!same_agent_concede_run_ge_3)"

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))


# ---------------------------------------------------------------------------
# 3. NoPrematureConsensus — G (is_vote -> has_prior_challenge)
# ---------------------------------------------------------------------------

class NoPrematureConsensus(Property):
    """No Vote may occur before any Challenge has been raised.

    Formal: G(is_vote -> has_prior_challenge)
    Prevents the "rubber-stamp" failure mode where the council votes without
    deliberation.
    """

    name: ClassVar[str] = "NoPrematureConsensus"
    formula: ClassVar[str] = "G(is_vote -> has_prior_challenge)"

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))


# ---------------------------------------------------------------------------
# 4. ProvenanceCompleteness — G (is_vote -> has_evidence)
# ---------------------------------------------------------------------------

class ProvenanceCompleteness(Property):
    """Every Vote must carry at least one evidence atom.

    Formal: G(is_vote -> has_evidence)
    Constitution §11 receipt-completeness: every Vote justifies its choice.
    """

    name: ClassVar[str] = "ProvenanceCompleteness"
    formula: ClassVar[str] = "G(is_vote -> has_evidence)"

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))


# ---------------------------------------------------------------------------
# 5. NoMonotoneAgreementCollapse — G (is_propose -> F (is_challenge || is_vote))
# ---------------------------------------------------------------------------

class NoMonotoneAgreementCollapse(Property):
    """Every Propose must eventually be Challenged or Voted on.

    Formal: G(is_propose -> F(is_challenge || is_vote))
    Without this, agents can flood the trace with proposals that are never
    examined — collapsing deliberation into monotone agreement.
    """

    name: ClassVar[str] = "NoMonotoneAgreementCollapse"
    formula: ClassVar[str] = "G(is_propose -> F(is_challenge || is_vote))"

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))


# ---------------------------------------------------------------------------
# 6. ChallengeBeforeConsensus — F (is_challenge && F is_vote)
# ---------------------------------------------------------------------------

class ChallengeBeforeConsensus(Property):
    """At least one Challenge must precede the eventual Vote.

    Formal: F(is_challenge && F(is_vote))
    A liveness counterpart to NoPrematureConsensus.
    """

    name: ClassVar[str] = "ChallengeBeforeConsensus"
    formula: ClassVar[str] = "F(is_challenge && F(is_vote))"

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))


# ---------------------------------------------------------------------------
# 7. RefutationReachable — F (is_challenge && F is_vote)  [synonym at L1; differentiated semantics at L2]
# ---------------------------------------------------------------------------

class RefutationReachable(Property):
    """The dialogue must reach a state where a Challenge is followed by a Vote.

    Formal: F(is_challenge && F(is_vote))
    Operationally synonymous with ChallengeBeforeConsensus at L1; argumentation
    semantics at L2 (W2) distinguishes them via attack/support roles.
    """

    name: ClassVar[str] = "RefutationReachable"
    formula: ClassVar[str] = "F(is_challenge && F(is_vote))"

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))


# ---------------------------------------------------------------------------
# 8. FairnessOfRoles — F is_propose && F is_challenge
# ---------------------------------------------------------------------------

class FairnessOfRoles(Property):
    """Both proposing and challenging roles must be exercised at least once.

    Formal: F(is_propose) && F(is_challenge)
    Coarse propositional approximation of ATL coalition-fairness; the strategic
    extension lives at L2 (Strategic Gradual Argumentation, P2).
    """

    name: ClassVar[str] = "FairnessOfRoles"
    formula: ClassVar[str] = "F(is_propose) && F(is_challenge)"

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))


# ---------------------------------------------------------------------------
# 9. ModalitySafe — G (is_propose -> (has_evidence || F is_challenge))
# ---------------------------------------------------------------------------

class ModalitySafe(Property):
    """Every Propose must either carry evidence or be eventually challenged.

    Formal: G(is_propose -> (has_evidence || F(is_challenge)))
    Defends against the must/may modality failure mode where an agent asserts
    necessity without grounding.
    """

    name: ClassVar[str] = "ModalitySafe"
    formula: ClassVar[str] = "G(is_propose -> (has_evidence || F(is_challenge)))"

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))


# ---------------------------------------------------------------------------
# 10. BoundedRound — F is_vote within k rounds (k enforced at termination)
# ---------------------------------------------------------------------------

class BoundedRound(Property):
    """Eventually decide within k rounds (k enforced at the termination layer).

    Formal at L1: F(is_vote)  — bound k is checked by FixedRounds termination.
    The k parameter is exposed as an instance attribute for reading by future
    YAML-runner wiring.

    .. note::
       BoundedRound is the only Property in PROPERTY_REGISTRY whose ``__init__``
       takes a parameter (``k``, default 10). YAML-driven code that does
       ``PROPERTY_REGISTRY["BoundedRound"](k=5)`` works; the no-arg form
       ``PROPERTY_REGISTRY["BoundedRound"]()`` falls back to the default.
       Future YAML runners (W8) should special-case parameterised properties
       — see L1_PARAMETERISED_PROPERTIES below.
    """

    name: ClassVar[str] = "BoundedRound"
    formula: ClassVar[str] = "F(is_vote)"

    def __init__(self, k: int = 10) -> None:
        if k < 1:
            raise ValueError(f"BoundedRound.k must be >= 1, got {k}")
        self.k = k

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))


# ---------------------------------------------------------------------------
# Registry — name -> Property class, for YAML-driven configuration
# ---------------------------------------------------------------------------

PropertyName = str

PROPERTY_REGISTRY: dict[PropertyName, type[Property]] = {
    cls.name: cls
    for cls in (
        EventuallyDecide,
        NoSycophancyCascade,
        NoPrematureConsensus,
        ProvenanceCompleteness,
        NoMonotoneAgreementCollapse,
        ChallengeBeforeConsensus,
        RefutationReachable,
        FairnessOfRoles,
        ModalitySafe,
        BoundedRound,
    )
}

#: Pairs of property names whose LTL_f formulas are syntactically identical
#: at L1 but are intended to be differentiated at L2 (W2) via argumentation
#: attack/support roles or by termination-layer parameters. Documented so
#: that callers configuring multiple-aliases are not surprised when both
#: monitors fire simultaneously with the same verdict.
#:
#: - (ChallengeBeforeConsensus, RefutationReachable): both encode
#:   F(is_challenge && F(is_vote)). At L2, RefutationReachable will additionally
#:   require the Challenge to attack the Vote in the QBAF.
#: - (EventuallyDecide, BoundedRound): both encode F(is_vote). BoundedRound
#:   carries an instance-attr k that the termination layer honours via FixedRounds.
L1_EQUIVALENCE_GROUPS: tuple[tuple[PropertyName, ...], ...] = (
    ("ChallengeBeforeConsensus", "RefutationReachable"),
    ("EventuallyDecide", "BoundedRound"),
)

#: Properties whose constructors take parameters beyond no-args. YAML-driven
#: callers must inspect this set and pass the right kwargs (e.g.
#: ``PROPERTY_REGISTRY["BoundedRound"](k=5)``) rather than blindly doing
#: ``cls()``. Empty tuple means "all parameterless" — that is the case for
#: every property except BoundedRound today.
L1_PARAMETERISED_PROPERTIES: tuple[PropertyName, ...] = ("BoundedRound",)
