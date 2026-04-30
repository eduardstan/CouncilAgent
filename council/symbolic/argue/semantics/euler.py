"""Euler-based / Exponent-based gradual semantics -- Amgoud-Ben-Naim (IJAR 2018).

`papers/3 --- argumentation/Amgoud and Ben-Naim 2018 ... (IJAR).pdf` defines
the "Exponent-based restricted semantics" (Ebs) in Definition 19 for acyclic
non-maximal weighted bipolar argumentation graphs. The bible refers to it as
"Euler-based" -- the W2 class name `EulerBasedSemantics` matches the bible
nomenclature; the docstring documents the equivalence to Ebs.

Definition 19 (Amgoud-Ben-Naim 2018):

  f(a) = 1 - (1 - w(a)^2) / (1 + w(a) * 2^E)

where E = sum f(x) over supporters - sum f(x) over attackers.

W2 generalisations per ADR-0011:
  - Edge weights multiply source strength: contribution = weight * f(source)
  - Withdrawn arguments have strength 0 and contribute 0 to others
  - Cycles raise ValueError (paper requires acyclic non-maximal graphs)
  - Boundary degeneracy (w=0 -> f=0; w=1 -> f=1) is faithful to the paper
    formula. The aggregator (PR6) defaults to DF-QuAD which has no such
    degeneracy. ADR-0011 Q3 records this design choice.
  - Preferred extension: non-withdrawn args with strength >= 0.5
"""

from __future__ import annotations

from collections import defaultdict

from council.symbolic.argue.baf import QBAF, Argument
from council.symbolic.argue.semantics.base import GradualSemantics
from council.symbolic.argue.semantics.df_quad import _topological_order

_EXTENSION_THRESHOLD = 0.5


def _ebs_strength(w: float, energy: float) -> float:
    """f(a) = 1 - (1 - w^2) / (1 + w * 2^E). Definition 19, Amgoud-Ben-Naim 2018."""
    two_to_e: float = 2.0**energy
    return 1.0 - (1.0 - w * w) / (1.0 + w * two_to_e)


class EulerBasedSemantics(GradualSemantics):
    """Exponent-based restricted semantics ("Ebs"; Amgoud-Ben-Naim 2018, Def 19).

    The W2 generalisation supports weighted edges and withdrawn arguments per
    ADR-0011. On unweighted edges, no withdrawals, and 0 < w < 1 for all
    arguments, reduces to the paper formula exactly.

    The class name is `EulerBasedSemantics` to match the bible's nomenclature
    in COUNCIL_NS_PLAN.md §6.3; in the source paper, this is "Ebs" or
    "Exponent-based restricted semantics".

    Boundary degeneracy: w(a) = 0 fixes f(a) = 0; w(a) = 1 fixes f(a) = 1.
    This is faithful to the paper formula. The aggregator (PR6) defaults to
    DF-QuAD which has no such degeneracy. ADR-0011 Q3 records the choice.
    """

    def evaluate(self, baf: QBAF) -> dict[str, float]:
        if not baf.arguments:
            return {}

        order = _topological_order(baf)
        arg_by_id: dict[str, Argument] = {a.arg_id: a for a in baf.arguments}

        incoming_attacks: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for att in baf.attacks:
            incoming_attacks[att.target].append((att.source, att.weight))
        incoming_supports: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for sup in baf.supports:
            incoming_supports[sup.target].append((sup.source, sup.weight))

        strengths: dict[str, float] = {}
        for arg_id in order:
            arg = arg_by_id[arg_id]
            if arg.withdrawn:
                strengths[arg_id] = 0.0
                continue

            supporter_sum = sum(
                weight * strengths[src]
                for src, weight in incoming_supports[arg_id]
            )
            attacker_sum = sum(
                weight * strengths[src]
                for src, weight in incoming_attacks[arg_id]
            )
            energy = supporter_sum - attacker_sum
            strengths[arg_id] = _ebs_strength(arg.base_score, energy)

        return strengths

    def preferred_extension(self, baf: QBAF) -> frozenset[str]:
        if not baf.arguments:
            return frozenset()
        strengths = self.evaluate(baf)
        return frozenset(
            a.arg_id
            for a in baf.arguments
            if not a.withdrawn and strengths[a.arg_id] >= _EXTENSION_THRESHOLD
        )
