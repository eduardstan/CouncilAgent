---
name: run-pareto
description: Extracts the Pareto front and computes hypervolume from a sweep result set in MLflow. Use in P3 / P4 paper drafts, or after a qd-runner halt to produce the table for §11.3 of the master plan.
---

# run-pareto

Extract the Pareto front from a sweep result set and compute hypervolume.

## Inputs
- `<experiment_id>` — MLflow experiment ID.
- Optional: `--axes=accuracy,cost,robustness` (default).
- Optional: `--out=papers_drafts/figures/<slug>` for figure output.

## Procedure

1. **Prerequisite check.** `evaluation/pareto.py` must exist; MLflow tracking dir `mlruns/` must contain runs for the experiment. If not, stop.
2. **Load runs:**
   ```bash
   uv run python -c "
   import mlflow
   exp = mlflow.get_experiment('<experiment_id>')
   runs = mlflow.search_runs(experiment_ids=[exp.experiment_id])
   ..."
   ```
3. **Compute Pareto front.** Call `evaluation/pareto.py` with the loaded metrics.
4. **Compute hypervolume** on the chosen axes (with documented reference point).
5. **Render outputs:**
   - LaTeX table of the Pareto front (sorted by hypervolume contribution).
   - 3D scatter plot of all runs with Pareto front highlighted (saved to `papers_drafts/figures/<slug>/pareto.pdf`).
   - YAML dump of the best genome.
6. **Emit a report:**
   ```
   ## Pareto front — experiment <experiment_id>
   
   ### Axes
   accuracy, cost, robustness
   
   ### Pareto front (top 5)
   | Genome | accuracy | cost | robustness | HV contribution |
   |--------|----------|------|------------|-----------------|
   
   ### Hypervolume
   <h>
   
   ### Best genome (YAML)
   <snippet>
   ```

## Invariants enforced
- Reference point is documented (otherwise hypervolume is meaningless).
- Pareto-front extraction is deterministic.
- Outputs land in `papers_drafts/figures/` so they can be `\includegraphics` directly.

## Reject criteria
- Experiment has < 5 runs (no meaningful front).
- Axes not all logged in MLflow.
