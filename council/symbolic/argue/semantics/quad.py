"""Quadratic Energy semantics -- Potyka (KR 2018).

`papers/3 --- argumentation/Potyka 2018 ... (KR).pdf` defines the QE model
as the equilibrium of a system of ODEs over a weighted bipolar argumentation
graph. For acyclic BAGs (Proposition 16) the equilibrium reduces to a
closed-form computable in topological order:

  s_j = w(j) + (1 - w(j)) * h(E_j) - w(j) * h(-E_j)
  E_j = sum(weight * strength) over supporters
       - sum(weight * strength) over attackers
  h(x) = max(x, 0)^2 / (1 + max(x, 0)^2)        (the impact function)

W2 generalisations (ADR-0010 + ADR-0011):
  - Edge weights multiply source strength: contribution = weight * strength
  - Withdrawn arguments have strength 0 and contribute 0 to others
  - Cycles raise ValueError (PR4 ships acyclic case only; numerical
    integration for cyclic case deferred per ADR-0011 Q1)
  - Preferred extension: non-withdrawn args with strength >= 0.5

Compared to DF-QuAD: QE is more conservative on the boundaries. A max-
strength attacker against a base=1 Propose drives the result to 0.5
(h(1) = 0.5), not to 0. The smoothness of h(x) = x^2/(1+x^2) prevents the
extreme saturation that DF-QuAD's combination function exhibits.
"""

from __future__ import annotations

from collections import defaultdict

from council.symbolic.argue.baf import QBAF, Argument
from council.symbolic.argue.semantics.base import GradualSemantics
from council.symbolic.argue.semantics.df_quad import _topological_order

_EXTENSION_THRESHOLD = 0.5


def _impact(x: float) -> float:
    """h(x) = max(x, 0)^2 / (1 + max(x, 0)^2). Potyka 2018, Definition 2."""
    if x <= 0:
        return 0.0
    sq = x * x
    return sq / (1.0 + sq)


class QESemantics(GradualSemantics):
    """Quadratic Energy gradual semantics (Potyka 2018).

    Acyclic-only in PR4 (raises on cycle). Generalised to weighted edges and
    withdrawn arguments per ADR-0011. On unweighted edges and no
    withdrawals, reduces to the paper algorithm exactly.
    """

    def evaluate(self, baf: QBAF) -> dict[str, float]:
        if not baf.arguments:
            return {}

        # Reuse DF-QuAD's topological sort — same cycle-detection contract
        # (raises ValueError on cycle).
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

            w = arg.base_score
            strengths[arg_id] = w + (1.0 - w) * _impact(energy) - w * _impact(-energy)

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
