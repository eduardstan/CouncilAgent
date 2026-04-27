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


def _build_topology(name: str, n_agents: int) -> Any:
    """Factory: topology name → Topology instance. Raises ValueError on unknown name."""
    from council.topology import (
        BusTopology,
        CompleteGraphTopology,
        DynamicStarTopology,
        RingTopology,
        StarTopology,
    )
    _map = {
        "complete": CompleteGraphTopology,
        "star": StarTopology,
        "bus": BusTopology,
        "ring": RingTopology,
        "dynamic_star": DynamicStarTopology,
    }
    cls = _map.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown topology {name!r}. Valid options: {sorted(_map)}"
        )
    return cls(n_agents)


def _build_aggregation(
    name: str,
    normalizer: Any,
    model_client: Any,
    models: list[str],
    meta_judge: dict[str, Any] | None = None,
    protocol: Any = None,
    response_format: dict[str, object] | None = None,
    output_schema: dict[str, object] | None = None,
) -> Any:
    """Factory: aggregation name → Aggregation instance. Raises ValueError on unknown name.

    meta_judge: optional dict carrying the synthesis-judge overrides —
        {model?, temperature?, max_tokens?, system_prompt?}. `model` falls back
        to `models[0]` when absent. Unset keys leave MetaJudge defaults in place.
    protocol / response_format / output_schema: wired into MetaJudge so synthesis
        labels rounds via the protocol's answer/critique predicate, returns the
        same JSON shape as the deliberation rounds, and includes the schema in
        its synthesis prompt.
    """
    from council.aggregation import BordaCount, CondorcetAggregation, MajorityVote, MetaJudge

    if name == "majority_vote":
        return MajorityVote(normalizer=normalizer)
    if name == "borda":
        return BordaCount()
    if name == "condorcet":
        return CondorcetAggregation()
    if name == "meta_judge":
        cfg = meta_judge or {}
        judge_model = cfg.get("model") or models[0]

        kwargs: dict[str, Any] = {
            "model": judge_model,
            "model_client": model_client,
            "response_format": response_format,
            "normalizer": normalizer,
            "output_schema": output_schema,
        }
        for key in ("temperature", "max_tokens", "system_prompt", "max_rounds_to_include"):
            if key in cfg:
                kwargs[key] = cfg[key]

        if protocol is not None:
            def _round_label(round_index: int) -> str:
                if round_index == 0:
                    return "GENERATE"
                return "ANSWER" if protocol.is_answer_round(round_index) else "CRITIQUE"
            kwargs["round_label_fn"] = _round_label

        return MetaJudge(**kwargs)
    raise ValueError(
        f"Unknown aggregation {name!r}. Valid options: majority_vote, borda, condorcet, meta_judge"
    )


def _parse_agents(models_cfg: list[Any]) -> tuple[list[Any], list[str]]:
    """Parse YAML `council.models` into AgentConfig objects + a flat model-string list.

    Each entry is either a bare string (model identifier) or a dict:
        {model: str, temperature?: float, max_tokens?: int, system_prompt?: str}

    The returned `model_strings` list preserves input order and is used for the
    transcript header and MLflow params. Per-agent fields absent from the YAML
    stay as AgentConfig defaults (None → ModelRequest defaults apply).
    """
    from council.core import AgentConfig

    agents: list[AgentConfig] = []
    model_strings: list[str] = []
    for i, entry in enumerate(models_cfg):
        if isinstance(entry, str):
            agents.append(AgentConfig(id=f"agent-{i}", model=entry))
            model_strings.append(entry)
        elif isinstance(entry, dict):
            model = entry.get("model")
            if not isinstance(model, str) or not model:
                raise ValueError(
                    f"council.models[{i}] is a dict but missing or empty 'model' key. "
                    "Use either a bare string or {model: ..., temperature?, max_tokens?, system_prompt?}."
                )
            agents.append(
                AgentConfig(
                    id=f"agent-{i}",
                    model=model,
                    temperature=entry.get("temperature"),
                    max_tokens=entry.get("max_tokens"),
                    system_prompt=entry.get("system_prompt"),
                )
            )
            model_strings.append(model)
        else:
            raise ValueError(
                f"council.models[{i}] must be a string or dict, got {type(entry).__name__}."
            )
    return agents, model_strings


def _build_termination(
    cfg: str | dict[str, Any],
    total_rounds: int,
    normalizer: Any,
    budget_usd: float,
) -> Any:
    """Factory: termination config → TerminationStrategy instance.

    cfg may be a bare string (e.g. ``"fixed"``) or a dict:
        {name: agreement, agreement_threshold: 0.95}
    Unset dict keys fall back to the defaults shown below.
    """
    from council.termination import (
        AgreementThreshold,
        BudgetExhaustion,
        CompositeTermination,
        FixedRounds,
    )

    if isinstance(cfg, str):
        name = cfg
        extra: dict[str, Any] = {}
    else:
        name = cfg.get("name", "fixed")
        extra = {k: v for k, v in cfg.items() if k != "name"}

    agreement_threshold: float = extra.get("agreement_threshold", 0.8)

    if name == "fixed":
        return FixedRounds(total_rounds)
    if name == "agreement":
        return CompositeTermination(
            AgreementThreshold(agreement_threshold, normalizer=normalizer),
            FixedRounds(total_rounds),
        )
    if name == "budget":
        return BudgetExhaustion(budget_usd)
    if name == "composite":
        return CompositeTermination(
            AgreementThreshold(agreement_threshold, normalizer=normalizer),
            BudgetExhaustion(budget_usd),
            FixedRounds(total_rounds),
        )
    raise ValueError(
        f"Unknown termination {name!r}. Valid options: fixed, agreement, budget, composite"
    )


def _format_task_transcript(
    task_idx: int,
    task_id: str,
    question: str,
    ground_truth: str,
    round_history: list[Any],
    final_answer: str,
    confidence: float,
    accuracy: float,
    model_map: dict[str, str],
    final_round_normalized: dict[str, str],  # agent_id → normalized answer
    aggregation_name: str = "MajorityVote",
) -> str:
    """Format the full round-by-round debate for one task as a readable string.

    Pipeline stages shown:
      GENERATE  — Round 0: each agent answers independently
      DELIBERATE — Round 1+: critiques and revisions
      RANK      — NullRanking (no preferences collected in fast mode)
      AGGREGATE — MajorityVote on final-round responses
    """
    lines: list[str] = []
    sep = "=" * 72
    lines.append(sep)
    lines.append(f"## Task {task_idx + 1}  `{task_id}`")
    lines.append(sep)
    lines.append(f"**Q:** {question[:300]}{'...' if len(question) > 300 else ''}")
    lines.append(f"**Ground truth:** `{ground_truth}`")
    lines.append("")

    # Group responses by round
    rounds: dict[int, list[Any]] = {}
    for r in round_history:
        rounds.setdefault(r.round_index, []).append(r)

    def _round_label(idx: int) -> str:
        if idx == 0:
            return "GENERATE — Initial answers"
        return "DELIBERATE — Critiques" if idx % 2 == 1 else "DELIBERATE — Revisions"

    for round_idx in sorted(rounds):
        label = _round_label(round_idx)
        lines.append(f"### {label}")
        lines.append("")
        for resp in sorted(rounds[round_idx], key=lambda r: r.agent_id):
            model = model_map.get(resp.agent_id, resp.agent_id)
            short_model = model.split("/")[-1]
            content = resp.content.strip()
            lines.append(f"**[{short_model}]**")
            lines.append("")
            lines.append(content)
            lines.append("")

    # AGGREGATE section — show per-agent normalized votes
    lines.append(f"### AGGREGATE — {aggregation_name} on final-round responses")
    lines.append("")
    lines.append("| Agent | Model | Normalized answer |")
    lines.append("|-------|-------|-------------------|")
    vote_counts: dict[str, int] = {}
    for agent_id, norm in sorted(final_round_normalized.items()):
        model = model_map.get(agent_id, agent_id)
        short_model = model.split("/")[-1]
        lines.append(f"| `{agent_id}` | {short_model} | `{norm}` |")
        vote_counts[norm] = vote_counts.get(norm, 0) + 1
    lines.append("")
    total = sum(vote_counts.values())
    for answer, count in sorted(vote_counts.items(), key=lambda x: -x[1]):
        marker = " ← **winner**" if answer == final_answer else ""
        lines.append(f"- `{answer}`: {count}/{total} votes{marker}")
    lines.append("")

    tick = "✓" if accuracy == 1.0 else "✗"
    lines.append(f"**Final answer:** `{final_answer}`  — confidence: {confidence:.2f}  — {tick} (expected: `{ground_truth}`)")
    lines.append("")
    return "\n".join(lines)


async def run_experiment(config: dict[str, Any]) -> ExperimentSummary:
    """Run a benchmark experiment and log to MLflow.

    Config keys:
        name:           Experiment config name (used in MLflow experiment name).
        dataset:        Task dataset name (key in tasks.registry.REGISTRY).
        task_limit:     Max tasks to evaluate (None = full dataset).
        council:        Council config dict. Required keys:
                          models — list (≥2). Each entry is either a bare model
                              string OR a dict with `model` plus optional
                              `temperature`, `max_tokens`, `system_prompt` that
                              override the ModelRequest defaults for that agent.
                        Optional keys (all have defaults):
                          protocol         — direct | peer_review | simultaneous (default: peer_review)
                          topology         — complete | star | bus | ring | dynamic_star (default: complete)
                          aggregation      — majority_vote | borda | condorcet | meta_judge (default: majority_vote)
                          termination      — fixed | agreement | budget | composite (default: fixed)
                          meta_judge       — dict of synthesis-judge overrides:
                              {model?, temperature?, max_tokens?, system_prompt?}.
                              `model` falls back to `models[0]` when absent.
                          max_rounds       — deliberation cycles after initial generation (default: 1)
                          budget_usd       — cost cap in USD (default: 0.10)
                          task_delay_seconds — sleep between tasks (default: 2.0)
                          prompt_hint      — overrides the TaskProfile answer-format hint.
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

    from council.core import run_council
    from council.models import LiteLLMClient
    from council.protocol import DirectAnswerProtocol, PeerReviewProtocol, SimultaneousProtocol
    from evaluation.baselines import majority_vote_no_deliberation
    from evaluation.metrics import task_accuracy
    from tasks.profiles import get_profile
    from tasks.registry import REGISTRY

    cfg_name: str = config.get("name", "unnamed")
    dataset_name: str = config.get("dataset", "gsm8k")
    task_limit: int | None = config.get("task_limit")
    council_cfg: dict[str, Any] = config.get("council", {})
    mlflow_cfg: dict[str, Any] = config.get("mlflow", {})

    # --- Build components from YAML ----------------------------------------
    models_cfg: list[Any] = council_cfg.get("models", [])
    if not models_cfg:
        raise ValueError(
            "council.models must be specified in the experiment config. "
            "Example:\n  council:\n    models:\n      - openrouter/openai/gpt-4.1-nano"
        )
    agents, models = _parse_agents(models_cfg)
    max_rounds: int = council_cfg.get("max_rounds", 1)
    budget_usd: float = council_cfg.get("budget_usd", 0.10)
    task_delay: float = council_cfg.get("task_delay_seconds", 2.0)
    protocol_name: str = council_cfg.get("protocol", "peer_review")
    topology_name: str = council_cfg.get("topology", "complete")
    aggregation_name: str = council_cfg.get("aggregation", "majority_vote")
    termination_cfg: str | dict[str, Any] = council_cfg.get("termination", "fixed")
    # meta_judge: structured dict of synthesis-judge overrides.
    meta_judge_cfg: dict[str, Any] | None = council_cfg.get("meta_judge")

    # TaskProfile drives normalizer, output schema, and the answer-format hint.
    # YAML-level overrides win: council.prompt_hint, if set, replaces the profile hint.
    profile = get_profile(dataset_name)
    normalizer = profile.normalizer
    output_schema = profile.output_schema
    prompt_hint = council_cfg.get("prompt_hint", profile.prompt_hint)

    _protocol_map = {
        "direct": DirectAnswerProtocol(output_schema=output_schema),
        "peer_review": PeerReviewProtocol(output_schema=output_schema),
        "simultaneous": SimultaneousProtocol(output_schema=output_schema),
    }
    protocol = _protocol_map.get(protocol_name, DirectAnswerProtocol(output_schema=output_schema))
    if protocol_name not in _protocol_map:
        logger.warning("Unknown protocol %r, falling back to 'direct'", protocol_name)

    # max_rounds in the config means "deliberation cycles after initial generation."
    # Translate to total raw rounds for FixedRounds:
    #   total = 1 (generation) + max_rounds * protocol.cycle_length()
    # E.g. PeerReview with max_rounds=1: 1 + 1*2 = 3 raw rounds (generate, critique, revise).
    total_rounds = 1 + max_rounds * protocol.cycle_length()

    # Convenience map for transcript formatting: agent-0 → full model string
    model_map = {f"agent-{i}": m for i, m in enumerate(models)}
    models_global_cfg: dict[str, Any] = config.get("models", {})
    model_client = LiteLLMClient(
        timeout=float(models_global_cfg.get("timeout_seconds", 60.0)),
        max_retries=int(models_global_cfg.get("max_retries", 3)),
    )

    topology = _build_topology(topology_name, len(agents))
    # Request structured JSON only when the profile declares an output schema.
    # Free-text tasks (future) will have output_schema=None and no response_format.
    answer_rf: dict[str, object] | None = (
        {"type": "json_object"} if output_schema else None
    )
    aggregation = _build_aggregation(
        aggregation_name,
        normalizer,
        model_client,
        models,
        meta_judge=meta_judge_cfg,
        protocol=protocol,
        response_format=answer_rf,
        output_schema=output_schema,
    )
    termination = _build_termination(termination_cfg, total_rounds, normalizer, budget_usd)

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
    all_transcripts: list[str] = []

    print(f"\n{'=' * 72}")
    print(f"Experiment: {cfg_name}  |  dataset: {dataset_name}  |  tasks: {task_limit or 'all'}")
    print(f"Models: {', '.join(m.split('/')[-1] for m in models)}")
    print(f"Protocol: {protocol_name}  |  deliberation_cycles: {max_rounds}  |  total_rounds: {total_rounds}")
    termination_label = termination_cfg if isinstance(termination_cfg, str) else termination_cfg.get("name", "?")
    print(f"Topology: {topology_name}  |  aggregation: {aggregation_name}  |  termination: {termination_label}")
    print(f"{'=' * 72}\n")

    for task_idx, task in enumerate(tasks):
        if task_idx > 0 and task_delay > 0:
            await asyncio.sleep(task_delay)
        try:
            result = await run_council(
                prompt=task.question,
                agents=agents,
                model_client=model_client,
                topology=topology,
                protocol=protocol,
                aggregation=aggregation,
                termination=termination,
                answer_response_format=answer_rf,
                task_hint=prompt_hint,
            )

            acc = await task_accuracy(
                result.final_answer, task.ground_truth, method="smart", normalizer=normalizer
            )
            accuracies.append(acc)
            costs.append(result.total_cost)

            # §6 baseline: majority vote on round-0 responses only (before any
            # deliberation), measured with task_accuracy for consistency.
            round0_responses = [r for r in result.round_history if r.round_index == 0]
            baseline_result = await majority_vote_no_deliberation(round0_responses, normalizer)
            baseline_acc = await task_accuracy(
                baseline_result.answer, task.ground_truth, method="smart", normalizer=normalizer
            )
            baseline_accuracies.append(baseline_acc)

            # Normalize each final-round response for the aggregation section.
            last_round_idx = result.rounds_used - 1
            final_round_normalized = {
                r.agent_id: await normalizer.normalize(r.content)
                for r in result.round_history
                if r.round_index == last_round_idx
            }

            transcript = _format_task_transcript(
                task_idx=task_idx,
                task_id=task.id,
                question=task.question,
                ground_truth=task.ground_truth,
                round_history=result.round_history,
                final_answer=result.final_answer,
                confidence=result.confidence,
                accuracy=acc,
                model_map=model_map,
                final_round_normalized=final_round_normalized,
                aggregation_name=type(aggregation).__name__,
            )
            print(transcript)
            all_transcripts.append(transcript)

        except Exception as e:
            logger.error("Task %s failed: %s", task.id, e)
            errors.append(f"{task.id}: {e}")
            print(f"[ERROR] Task {task.id}: {e}\n")

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
                "deliberation_cycles": max_rounds,
                "total_rounds": total_rounds,
                "protocol": protocol_name,
                "topology": topology_name,
                "aggregation": aggregation_name,
                "termination": termination_label,
                "meta_judge_model": (meta_judge_cfg or {}).get("model") or models[0],
                "meta_judge_temperature": (meta_judge_cfg or {}).get("temperature", ""),
                "meta_judge_max_tokens": (meta_judge_cfg or {}).get("max_tokens", ""),
                "meta_judge_system_prompt": (meta_judge_cfg or {}).get("system_prompt", ""),
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
            # Save the full debate transcript as an artifact so it's browsable
            # in the MLflow UI under Artifacts → debate_transcript.txt
            if all_transcripts:
                full_transcript = "\n".join(all_transcripts)
                mlflow.log_text(full_transcript, "debate_transcript.md")

        summary.mlflow_run_id = run_id
        logger.info("MLflow run logged: %s (experiment: %s)", run_id, experiment_name)

    return summary


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="CouncilAgent fast-mode benchmark runner")
    parser.add_argument("--config", required=True, help="Path to YAML experiment config")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)  # suppress INFO noise; keep WARNING+
    cfg = load_config(args.config)
    summary = asyncio.run(run_experiment(cfg))

    print(f"\n{'=' * 72}")
    print(f"RESULTS  —  {summary.config_name}")
    print(f"{'=' * 72}")
    print(f"Tasks evaluated:  {summary.task_count}")
    print(f"Mean accuracy:    {summary.mean_accuracy:.3f}")
    print(f"Mean cost (USD):  {summary.mean_cost:.6f}")
    for baseline, score in summary.baseline_comparison.items():
        delta = summary.mean_accuracy - score
        sign = "+" if delta >= 0 else ""
        print(f"Baseline ({baseline}): {score:.3f}  (council delta: {sign}{delta:.3f})")
    if summary.mlflow_run_id:
        print(f"\nMLflow run: {summary.mlflow_run_id}")
        print("  → open MLflow UI, click 'Experiments' (left sidebar), not 'Traces'")
    if summary.errors:
        print(f"\nErrors ({len(summary.errors)}): {summary.errors[:3]}")


if __name__ == "__main__":
    main()
