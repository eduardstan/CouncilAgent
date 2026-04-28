---
name: ablation-row
description: Given a frozen Hydra config and a benchmark, runs the row, computes bootstrap CI, emits a LaTeX table line. Use during M3, M4 to fill out the §11.3 ablation matrix.
---

# ablation-row

Run a single ablation row and emit a LaTeX table line.

## Inputs
- `<config_name>` — Hydra config name under `experiments/configs/`. Must be a *frozen* config (locked seeds, locked task profile).
- `<benchmark>` — `arc_agi_2` | `frontiermath` | `livecodebench` | `swe_bench_pro` | `hle` | `zebralogic_hard` | `putnam_axiom` | `gaia` | `webarena`.

## Procedure

1. **Prerequisite check.** `experiments/configs/<config_name>.yaml` must exist; the benchmark loader in `tasks/<benchmark>.py` must exist. If not, stop.
2. **Hash the config** for the audit trail:
   ```bash
   sha256sum experiments/configs/<config_name>.yaml
   ```
   Save the hash to `papers_drafts/_ablation_log.tsv`.
3. **Run the row:**
   ```bash
   uv run python -m experiments.run --config-name <config_name> task=<benchmark>
   ```
4. **Compute bootstrap CI** at α=0.05 from the per-task accuracies via `evaluation/statistical.py:bootstrap_ci`.
5. **Emit a LaTeX line:**
   ```latex
   \texttt{<config_name>} & \(<acc>\)\(_{[<lo>, <hi>]}\) & \$<cost> & <rounds> & <verification_pass_rate> \\
   ```
6. **Append to `papers_drafts/_ablation_log.tsv`:**
   ```
   <date>\t<config_hash>\t<benchmark>\t<acc>\t<lo>\t<hi>\t<cost>\t<rounds>\t<vpr>
   ```

## Invariants enforced
- Config must be frozen (hashed and logged).
- Bootstrap CI is reported (no point estimates without uncertainty).
- Matched-token-budget comparison automatically computed against the MoA baseline (Constitution §6.1).
- Ablation log is append-only (audit trail).

## Reject criteria
- Config has not been hashed and logged.
- Benchmark loader missing.
- < 30 tasks in the benchmark sample (CI not meaningful).
