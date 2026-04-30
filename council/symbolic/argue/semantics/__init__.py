"""L2 argumentation — gradual semantics package.

Contains the GradualSemantics ABC (`base`) and concrete implementations
(`df_quad`, `quad`, `euler`, `coupled`) that ship in W2/PR3-PR5.
"""

from council.symbolic.argue.semantics.base import GradualSemantics
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics
from council.symbolic.argue.semantics.euler import EulerBasedSemantics
from council.symbolic.argue.semantics.quad import QESemantics

__all__ = [
    "DFQuADSemantics",
    "EulerBasedSemantics",
    "GradualSemantics",
    "QESemantics",
]
