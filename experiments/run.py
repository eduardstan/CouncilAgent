"""Fast-mode experiment runner for CouncilAgent benchmarks.

Runs a council configuration against a task dataset, logs results to MLflow,
and returns an ExperimentSummary. No Hydra in fast mode — config is a plain
Python dict or loaded from a YAML file.

Usage (fast mode):
    uv run python -m experiments.run --config configs/experiment/fast.yaml

MLflow lives only in this module (Constitution §8).
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ExperimentSummary:
    """Aggregated results from one experiment run.

    Produced by run_experiment() and logged as MLflow params/metrics.
    """

    config_name: str
    task_count: int
    mean_accuracy: float
    mean_cost: float
    baseline_comparison: dict[str, float] = field(default_factory=dict)
    mlflow_run_id: str = ""
    errors: list[str] = field(default_factory=list)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML experiment config file."""
    with open(path) as f:
        return yaml.safe_load(f)


async def run_experiment(config: dict[str, Any]) -> ExperimentSummary:
    """Run a benchmark experiment and log to MLflow.

    Config keys:
        name:           Experiment config name (used in MLflow experiment name).
        dataset:        Task dataset name (key in tasks.registry.REGISTRY).
        task_limit:     Max tasks to evaluate (None = full dataset).
        council:        Council config dict with keys: models, topology, protocol,
                        aggregation, max_rounds, budget_usd.
        mlflow:         MLflow config dict with keys: tracking_uri, experiment_name.
                        Optional — if absent, MLflow logging is skipped.
    """
    try:
        import mlflow  # type: ignore[import-untyped]
        mlflow_available = True
    except ImportError:
        mlflow_available = False
        logger.warning("mlflow not installed — results will not be logged. "
                       "Install with: uv pip install 'council-agent[benchmark]'")

    from council.agent import CouncilAgent
    from council.aggregation import MajorityVote
    from council.core import AgentConfig, run_council
    from council.models import LiteLLMClient
    from council.normalizer import StructuredOutputNormalizer
    from council.policy import CouncilConfig
    from council.protocol import DirectAnswerProtocol
    from council.termination import FixedRounds
    from council.topology import CompleteGraphTopology
    from evaluation.baselines import majority_vote_no_deliberation
    from evaluation.metrics import task_accuracy
    from tasks.registry import REGISTRY

    cfg_name: str = config.get("name", "unnamed")
    dataset_name: str = config.get("dataset", "gsm8k")
    task_limit: int | None = config.get("task_limit")
    council_cfg: dict[str, Any] = config.get("council", {})
    mlflow_cfg: dict[str, Any] = config.get("mlflow", {})

    # --- Build council config from YAML --------------------------------
    models: list[str] = council_cfg.get("models", [
        "openrouter/google/gemma-3-27b-it:free",
        "openrouter/nvidia/nemotron-3-nano-30b-a3b:free",
        "openrouter/z-ai/glm-4.5-air:free",
    ])
    max_rounds: int = council_cfg.get("max_rounds", 1)
    budget_usd: float = council_cfg.get("budget_usd", 0.10)
    task_delay: float = council_cfg.get("task_delay_seconds", 2.0)

    agents = [AgentConfig(id=f"agent-{i}", model=m) for i, m in enumerate(models)]
    normalizer = StructuredOutputNormalizer()
    council_config = CouncilConfig(
        name=cfg_name,
        agents=agents,
        topology=CompleteGraphTopology(len(agents)),
        protocol=DirectAnswerProtocol(),
        aggregation=MajorityVote(normalizer=normalizer),
        termination=FixedRounds(max_rounds),
        estimated_cost_usd=0.0,
    )

    model_client = LiteLLMClient()
    agent = CouncilAgent(config=council_config, model_client=model_client)

    # --- Load tasks -------------------------------------------------------
    loader = REGISTRY[dataset_name]
    tasks = loader.load(limit=task_limit)
    logger.info("Loaded %d tasks from %s", len(tasks), dataset_name)

    # --- MLflow setup -----------------------------------------------------
    sha = _git_sha()
    experiment_name = mlflow_cfg.get(
        "experiment_name", f"council/{cfg_name}/{sha}"
    )
    tracking_uri = mlflow_cfg.get("tracking_uri", "mlruns")

    run_id = ""
    if mlflow_available:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)

    # --- Evaluate ---------------------------------------------------------
    accuracies: list[float] = []
    costs: list[float] = []
    baseline_accuracies: list[float] = []
    errors: list[str] = []

    for task_idx, task in enumerate(tasks):
        if task_idx > 0 and task_delay > 0:
            await asyncio.sleep(task_delay)
        try:
            response = await agent.complete(task.question)
            acc = await task_accuracy(response.content, task.ground_truth, method="smart", normalizer=normalizer)
            accuracies.append(acc)
            costs.append(response.cost)

            # §6 baseline: majority vote without deliberation
            # We re-use the single response as a "council of 1" for this baseline.
            # In full evaluation, pass round-0 responses from run_council directly.
            baseline_result = await majority_vote_no_deliberation(
                [response], normalizer, ground_truth=task.ground_truth
            )
            if baseline_result.accuracy is not None:
                baseline_accuracies.append(baseline_result.accuracy)

        except Exception as e:
            logger.error("Task %s failed: %s", task.id, e)
            errors.append(f"{task.id}: {e}")

    mean_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0
    mean_cost = sum(costs) / len(costs) if costs else 0.0
    mean_baseline = sum(baseline_accuracies) / len(baseline_accuracies) if baseline_accuracies else 0.0

    summary = ExperimentSummary(
        config_name=cfg_name,
        task_count=len(tasks),
        mean_accuracy=mean_accuracy,
        mean_cost=mean_cost,
        baseline_comparison={"majority_vote_no_deliberation": mean_baseline},
        errors=errors,
    )

    # --- Log to MLflow ----------------------------------------------------
    if mlflow_available:
        with mlflow.start_run() as run:
            run_id = run.info.run_id
            mlflow.log_params({
                "config_name": cfg_name,
                "dataset": dataset_name,
                "task_limit": task_limit,
                "models": str(models),
                "max_rounds": max_rounds,
                "budget_usd": budget_usd,
                "git_sha": sha,
            })
            mlflow.log_metrics({
                "mean_accuracy": mean_accuracy,
                "mean_cost": mean_cost,
                "baseline_majority_vote": mean_baseline,
                "task_count": float(len(tasks)),
                "error_count": float(len(errors)),
            })
        summary.mlflow_run_id = run_id
        logger.info("MLflow run logged: %s (experiment: %s)", run_id, experiment_name)

    return summary


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="CouncilAgent fast-mode benchmark runner")
    parser.add_argument("--config", required=True, help="Path to YAML experiment config")
    args = parser.parse_args()

    cfg = load_config(args.config)
    summary = asyncio.run(run_experiment(cfg))

    print(f"\n=== Experiment: {summary.config_name} ===")
    print(f"Tasks evaluated: {summary.task_count}")
    print(f"Mean accuracy:   {summary.mean_accuracy:.3f}")
    print(f"Mean cost (USD): {summary.mean_cost:.6f}")
    for baseline, score in summary.baseline_comparison.items():
        print(f"Baseline ({baseline}): {score:.3f}")
    if summary.mlflow_run_id:
        print(f"MLflow run: {summary.mlflow_run_id}")
    if summary.errors:
        print(f"Errors ({len(summary.errors)}): {summary.errors[:3]}")


if __name__ == "__main__":
    main()
