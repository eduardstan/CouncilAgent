"""Hydra-powered sweep runner for CouncilAgent full-mode benchmarks.

Wraps experiments/run.py in a Hydra @hydra.main decorator. Each sweep point
is a separate MLflow run under a shared experiment. Parallelism is controlled
by Hydra's --multirun flag.

Hydra lives ONLY in this file (Constitution §8 — no framework imports in core/).

Usage:
    # Single run with overrides:
    uv run python -m experiments.sweep council.max_rounds=2

    # Full 4x4x5x3 sweep (requires mlflow + hydra-core):
    uv run python -m experiments.sweep --multirun \\
        council.max_rounds=1,2 \\
        council.topology=complete,star \\
        dataset=gsm8k

    # Or use the pre-built sweep config:
    uv run python -m experiments.sweep \\
        --config-name sweep_topology_x_protocol \\
        --multirun
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


def run_sweep_point(cfg: object) -> None:
    """Run a single sweep point from a Hydra DictConfig.

    Called by Hydra for each point in the sweep grid. Converts the DictConfig
    to a plain dict and delegates to run_experiment().
    """
    try:
        from omegaconf import OmegaConf  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError(
            "experiments.sweep requires hydra-core (which includes omegaconf). "
            "Install with: uv pip install 'council-agent[benchmark]'"
        ) from e

    from experiments.run import run_experiment

    config_dict = OmegaConf.to_container(cfg, resolve=True)
    summary = asyncio.run(run_experiment(config_dict))

    logger.info(
        "Sweep point done: config=%s accuracy=%.3f cost=%.6f mlflow_run=%s",
        summary.config_name,
        summary.mean_accuracy,
        summary.mean_cost,
        summary.mlflow_run_id,
    )


def main() -> None:
    """Entry point — wraps run_sweep_point with Hydra."""
    try:
        import hydra  # type: ignore[import-untyped]
        from omegaconf import DictConfig  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError(
            "experiments.sweep requires hydra-core. "
            "Install with: uv pip install 'council-agent[benchmark]'"
        ) from e

    @hydra.main(
        version_base=None,
        config_path="../configs/hydra",
        config_name="sweep_topology_x_protocol",
    )
    def _hydra_main(cfg: DictConfig) -> None:
        run_sweep_point(cfg)

    _hydra_main()


if __name__ == "__main__":
    main()
