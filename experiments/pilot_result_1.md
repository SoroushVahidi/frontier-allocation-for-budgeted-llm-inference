# Pilot Result 1: First Feasibility Signal (Lightweight GSM8K Scaffold)

This is the first empirical feasibility pilot for the adaptive reasoning budget project, run using the repository's current lightweight pilot scaffold.

## Exact commands used

```bash
python - <<'PY'
import importlib
mods=['experiments.controllers','experiments.scoring','experiments.branching','experiments.data','scripts.run_pilot_gsm8k','scripts.evaluate_pilot_gsm8k']
for m in mods:
    importlib.import_module(m)
print('imports_ok')
PY

python scripts/run_pilot_gsm8k.py --config configs/pilot_gsm8k.yaml
python scripts/evaluate_pilot_gsm8k.py outputs/pilot/20260412T222522Z
```

## Config summary

- Config file: `configs/pilot_gsm8k.yaml`
- Seed: `7`
- Pilot size: `30`
- Split requested: `gsm8k_split=test`
- Matched per-problem budget: `max_actions_per_problem=12`
- Method params:
  - Best-of-N: `n_candidates=3`
  - Fixed-width beam: `width=2`
  - Adaptive: `high_threshold=0.72`, `low_threshold=0.42`, `max_branches=3`
- Simulation params: `max_depth=5`, `finish_prob_base=0.22`, `answer_noise=0.2`

## Data source used

- **Fallback/mock mode was used**.
- Manifest reports: `data_source = mock_arithmetic` with note that GSM8K was unavailable.
- No silent dataset substitution was performed; this matches the documented fallback behavior.

## Metrics (run id: `20260412T222522Z`)

| Method | Final accuracy | Avg actions used | Avg expansions | Avg verifications | Avg surviving branches | Budget exhaustion rate | # evaluated examples | Data source |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Greedy single-path | 0.5333 | 1.6667 | 1.6667 | 0.0000 | 1.0000 | 0.0000 | 30 | mock_arithmetic (fallback) |
| Best-of-N | 0.5333 | 9.0333 | 6.1333 | 2.9000 | 1.5285 | 0.1000 | 30 | mock_arithmetic (fallback) |
| Fixed-width beam | **0.6667** | 3.5000 | 3.5000 | 0.0000 | 2.0000 | 0.0000 | 30 | mock_arithmetic (fallback) |
| Adaptive expand/verify/prune | 0.2000 | 5.2667 | 1.0000 | 4.2667 | 0.8874 | 0.2667 | 30 | mock_arithmetic (fallback) |

## Short interpretation

### Did the adaptive controller win, lose, or tie?

- On this run, the adaptive controller **lost clearly** versus all baselines, including greedy and beam.
- Fixed-width beam was strongest on this fallback run.

### Was the result meaningful or too noisy?

- It is **meaningful as a smoke-test signal** for controller behavior under the current scaffold.
- It is **not meaningful as a GSM8K claim**, because real GSM8K was not used.
- With only 30 examples and simulation/fallback data, variance is likely high.

### What looks broken or suspicious?

- Adaptive behavior appears verification-heavy (high verify count, low expansions) with low accuracy.
- Adaptive also has the highest budget exhaustion rate here.
- This suggests threshold policy and/or score calibration mismatch in current simulation setting.

### What should be changed next?

1. Inspect adaptive policy decisions per-step (especially verify vs expand triggers).
2. Recalibrate adaptive thresholds and scoring scale before broader claims.
3. Enable real GSM8K loading reliably, then rerun matched-budget comparison.
4. Increase sample size after real-data path is stable to reduce noise.
