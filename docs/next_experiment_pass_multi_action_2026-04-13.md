# Next experiment pass: multi-action controller allocation sweep

## Selected experiment family

**Family:** controller-level fixed-budget allocation over a branch frontier with multiple controller policies and learned scorers.

This uses the existing branch-scorer stack (`simulate_controller`) where the controller repeatedly allocates compute to one of several active branches under a fixed budget, with per-step operation types (`expand`, optional `verify`) recorded in branch state and scorer features.

## Why this is materially different from binary cheap-vs-revise

- The decision is **not** a single binary escalate/no-escalate routing gate.
- At each decision point, the controller chooses among **many competing branches** under a global budget.
- Multiple controller policies are compared (`adaptive_eptree_baseline`, `adaptive_score_plus_progress`, `adaptive_relative_rank`, and learned scorers `v4/v5/v6`).
- Evaluation includes budget and initial-branch regime sweeps, testing allocation quality across richer state/action conditions.

## Scripts and outputs

- Main run script: `scripts/run_multi_action_allocation_pass.sh`
- Core evaluator: `scripts/evaluate_branch_scorer_robustness.py`
- Per-regime eval helper: `scripts/evaluate_branch_scorer_controller.py`
- Wulver sbatch: `jobs/multi_action_allocation_pass.sbatch`

Outputs:

- `outputs/multi_action_allocation_pass/robustness/robustness_summary.json`
- `outputs/multi_action_allocation_pass/robustness/robustness_per_setting.csv`
- `outputs/multi_action_allocation_pass/robustness/robustness_note.md`
- `outputs/multi_action_allocation_pass/controller_eval/controller_eval_b*_i*.json`

## Wulver launch

```bash
sbatch jobs/multi_action_allocation_pass.sbatch
```

The run script auto-builds/trains scorer artifacts if missing, then runs robustness + per-regime controller evaluation.

## Manual Wulver run note (batch + direct shell)

Working directory:

```bash
cd /home/sv96/adaptive-reasoning-budget-allocation
```

Environment setup (repo-consistent with existing job scripts):

```bash
source ~/.bashrc
conda activate base
python --version
```

Required environment variables:

- None required for this synthetic controller pass.
- Optional knobs:
  - `OUT_ROOT` (default `outputs/multi_action_allocation_pass`)
  - `MODEL_DIR` (default `outputs/branch_scorer_v3/models`)
  - `TRAIN_ROOT` (default `outputs/branch_scorer_v3`)
  - `ROBUSTNESS_SEEDS` (default `3,7,11,19,23`)
  - `ROBUSTNESS_BUDGETS` (default `8,10,12,14`)
  - `ROBUSTNESS_INIT_BRANCHES` (default `3,5,7`)
  - `ROBUSTNESS_EPISODES` (default `700`)
  - `CONTROLLER_EVAL_EPISODES` (default `1200`)
  - `CONTROLLER_EVAL_SEED` (default `17`)

### Direct shell launch (no sbatch)

```bash
cd /home/sv96/adaptive-reasoning-budget-allocation
source ~/.bashrc
conda activate base
bash scripts/run_multi_action_allocation_pass.sh
```

### Batch launch on Wulver

```bash
cd /home/sv96/adaptive-reasoning-budget-allocation
sbatch jobs/multi_action_allocation_pass.sbatch
```

### Expected outputs

- `outputs/multi_action_allocation_pass/robustness/robustness_summary.json`
- `outputs/multi_action_allocation_pass/robustness/robustness_per_setting.csv`
- `outputs/multi_action_allocation_pass/robustness/robustness_note.md`
- `outputs/multi_action_allocation_pass/controller_eval/controller_eval_b*_i*.json`

### Resume / rerun behavior

- Safe resume is supported:
  - robustness sweep is skipped if `robustness_summary.json` already exists;
  - per-regime controller eval files are skipped individually if the JSON already exists.
- To force a full rerun, remove the output root first:

```bash
rm -rf outputs/multi_action_allocation_pass
bash scripts/run_multi_action_allocation_pass.sh
```
