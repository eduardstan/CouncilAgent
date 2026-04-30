"""Tests for council/symbolic/argue/__init__.py — public re-exports.

Pins the public API surface so PR2-PR9 can import from
`council.symbolic.argue` without reaching into submodules.
"""

from __future__ import annotations


def test_public_api_re_exports() -> None:
    from council.symbolic.argue import (
        QBAF,
        AggregationResult,
        Aggregator,
        AggregatorConfidence,
        Argument,
        Attack,
        DFQuADSemantics,
        EulerBasedSemantics,
        GradualSemantics,
        QESemantics,
        StrategicCoupledSemantics,
        Support,
        build_qbaf,
        evidence_backed_arg_ids,
    )

    # Sanity: confirm the re-exports are the canonical objects.
    from council.symbolic.argue.aggregation_result import (
        AggregationResult as _AR,
    )
    from council.symbolic.argue.aggregator_base import Aggregator as _Agg
    from council.symbolic.argue.baf import QBAF as _Q
    from council.symbolic.argue.baf import Argument as _A
    from council.symbolic.argue.baf import Attack as _Att
    from council.symbolic.argue.baf import Support as _S
    from council.symbolic.argue.builders import build_qbaf as _bqb
    from council.symbolic.argue.coupled_atl import (
        evidence_backed_arg_ids as _eba,
    )
    from council.symbolic.argue.semantics.base import (
        GradualSemantics as _GS,
    )
    from council.symbolic.argue.semantics.coupled import (
        StrategicCoupledSemantics as _SCS,
    )
    from council.symbolic.argue.semantics.df_quad import (
        DFQuADSemantics as _DFQ,
    )
    from council.symbolic.argue.semantics.euler import (
        EulerBasedSemantics as _EBS,
    )
    from council.symbolic.argue.semantics.quad import QESemantics as _QE

    assert AggregationResult is _AR
    assert Aggregator is _Agg
    assert QBAF is _Q
    assert Argument is _A
    assert Attack is _Att
    assert Support is _S
    assert GradualSemantics is _GS
    assert DFQuADSemantics is _DFQ
    assert QESemantics is _QE
    assert EulerBasedSemantics is _EBS
    assert StrategicCoupledSemantics is _SCS
    assert build_qbaf is _bqb
    assert evidence_backed_arg_ids is _eba
    # AggregatorConfidence is a Union alias — just verify importability
    assert AggregatorConfidence is not None


def test_calibrator_not_re_exported_from_argue() -> None:
    """Calibrator lives under council.calibrate, not council.symbolic.argue."""
    import council.symbolic.argue as argue_pkg

    assert "Calibrator" not in dir(argue_pkg)
    assert "IdentityCalibrator" not in dir(argue_pkg)


def test_explicit_all() -> None:
    import council.symbolic.argue as argue_pkg

    assert hasattr(argue_pkg, "__all__")
    expected = {
        "QBAF",
        "AggregationResult",
        "Aggregator",
        "AggregatorConfidence",
        "Argument",
        "Attack",
        "DFQuADSemantics",
        "EulerBasedSemantics",
        "GradualSemantics",
        "QESemantics",
        "StrategicCoupledSemantics",
        "Support",
        "build_qbaf",
        "evidence_backed_arg_ids",
    }
    assert set(argue_pkg.__all__) == expected
