# Pilot GSM8K feasibility experiment

This pilot is a **lightweight scaffold** to test whether a simple adaptive
expand/verify/prune controller shows promise against simple baselines under a
matched action budget.

## What this pilot is

- A small, configurable run on a GSM8K subset (default: 12 examples).
- A side-by-side comparison of baseline and adaptive controller styles.
- A transparent output format for quick inspection and diagnostics.

## Methods compared

1. **Greedy single-path**: one branch, expand until done or budget limit.
2. **Best-of-N**: generate `N` independent candidates (default `N=3`) and pick the highest-scored one.
3. **Fixed-width beam**: keep top `W` partial branches each round (default `W=2`).
4. **Adaptive expand/verify/prune**: simple heuristic policy based on branch score thresholds.

## Budgeting (matched)

Per-problem budget uses `max_actions_per_problem`.

- `expand` = 1 action
- `verify` = 1 action
- `prune` = 0 actions

## Current simplifications (important)

This is **not** the final pipeline. It includes provisional pieces:

- If `OPENAI_API_KEY` is set and `model.use_openai_api=true`, run uses OpenAI API-backed branch expansion/verification.
- If API mode cannot be used, the run falls back to local simulation mode.
- Fallback mock arithmetic data is available if GSM8K loading is unavailable (clearly recorded in `manifest.json`).

## Run

```bash
python scripts/run_pilot_gsm8k.py --config configs/pilot_gsm8k.yaml
```

## Evaluate outputs

```bash
python scripts/evaluate_pilot_gsm8k.py outputs/pilot/<run_id>
```

Outputs are written to:

- `outputs/pilot/<run_id>/manifest.json`
- `outputs/pilot/<run_id>/<method>.jsonl`
- `outputs/pilot/<run_id>/adaptive_diagnostics.jsonl`
- `outputs/pilot/<run_id>/summary.json` (after evaluation)

## What results mean (and do not mean)

- Useful for checking whether adaptive control behavior is directionally promising.
- Useful for inspecting action usage (expand/verify/prune behavior).
- **Not** a publishable claim of SOTA performance or final algorithm quality.
- Any gains in this pilot should be treated as motivation for deeper experiments,
  better verifiers, stronger model backends, and broader evaluation.
