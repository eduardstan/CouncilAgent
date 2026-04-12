"""Tests for experiments/sweep.py.

Hydra and omegaconf are benchmark extras — tests that require them use
pytest.importorskip. The module-import and config-file tests always run.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Module import (always runs — verifies no top-level framework imports)
# ---------------------------------------------------------------------------


def test_sweep_module_importable() -> None:
    """experiments.sweep must be importable without hydra installed."""
    import experiments.sweep  # noqa: F401


def test_sweep_has_no_top_level_hydra_import() -> None:
    """Hydra must only be imported inside function bodies, not at module level."""
    import ast
    import importlib.util

    spec = importlib.util.find_spec("experiments.sweep")
    assert spec is not None and spec.origin is not None
    with open(spec.origin) as f:
        source = f.read()

    tree = ast.parse(source)
    # Walk top-level statements only (not inside functions/classes)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = ""
            if isinstance(node, ast.Import):
                module = node.names[0].name
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            assert "hydra" not in module, (
                f"experiments/sweep.py has top-level hydra import: {module}"
            )


# ---------------------------------------------------------------------------
# Hydra sweep config file
# ---------------------------------------------------------------------------


def test_sweep_config_file_exists() -> None:
    cfg_path = Path("configs/hydra/sweep_topology_x_protocol.yaml")
    assert cfg_path.exists(), f"Sweep config missing: {cfg_path}"


def test_sweep_config_has_required_keys() -> None:
    import yaml

    with open("configs/hydra/sweep_topology_x_protocol.yaml") as f:
        cfg = yaml.safe_load(f)
    assert "council" in cfg
    assert "models" in cfg["council"]
    assert "max_rounds" in cfg["council"]
    assert "dataset" in cfg


# ---------------------------------------------------------------------------
# run_sweep_point — requires omegaconf (skipped if not installed)
# ---------------------------------------------------------------------------


def test_run_sweep_point_requires_omegaconf_or_raises() -> None:
    """run_sweep_point raises ImportError when omegaconf is not installed."""
    try:
        from omegaconf import OmegaConf  # type: ignore[import-untyped]
        pytest.skip("omegaconf installed — ImportError path not exercised")
    except ImportError:
        from experiments.sweep import run_sweep_point
        with pytest.raises(ImportError, match="hydra-core"):
            run_sweep_point({})
