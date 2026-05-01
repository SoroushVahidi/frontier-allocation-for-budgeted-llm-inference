# New-paper frontier matrix — interpretation (20260413T214719Z)

## What this run measures

- **Strategy frontier**: fixed controller families (greedy, self-consistency, beam, adaptive min-expand variants, verifier-guided search, program-of-thought) evaluated under a shared action budget.
- **Simple calib→eval selector**: picks the strategy with highest calibration accuracy subject to average-actions feasibility; reports **oracle** accuracy (best per-example strategy on eval) minus selected accuracy (**oracle gap**).
- **Anti-collapse**: for `adaptive_min_expand_k`, tracks forced expands before prune vs prune share in the adaptive action trace (simulator uses stochastic scores).

## Completed datasets

- `EleutherAI/hendrycks_math`

## Oracle gap (headroom)

- Mean oracle-minus-selected gap across (dataset, budget) cells: **0.3750** (std **0.1443**).

## Selector choices

The budgeted selector frequency is in `frontier_allocation_controller_selector.csv` (one row per dataset × budget).

## Honest limits

- **Simulator mode** (default): HF examples provide questions/gold answers; branch generation is **not** a real LLM—accuracy is a **process proxy** for allocation dynamics and oracle gaps, not benchmark SOTA.
- **OpenAI mode** (`--use-openai-api`): real generations; requires `OPENAI_API_KEY` and is rate/cost limited.
- **Verifier-guided search** uses `SimulatedScorerVerifier` in simulation or `LLMVerifyProxyVerifier` with API—neither is a trained PRM.
- **GPQA Diamond** is gated; without HF auth the loader fails and is skipped when using `--try-gpqa`.

