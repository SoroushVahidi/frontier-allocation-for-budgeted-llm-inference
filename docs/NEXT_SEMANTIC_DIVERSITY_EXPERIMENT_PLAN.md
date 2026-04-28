# Next semantic-diversity experiment plan (post loss-full diagnostic)

This plan follows the diagnostic run **`20260427T232800Z`** (Slurm **`1011561`**). Evidence there is **not** manuscript-grade; use this as an engineering roadmap only.

## Objective

Validate whether **`direct_reserve_semantic_frontier_v1`** (and optionally **`semantic_minimum_maturation_plus_direct_reserve_v1`**) **replicate** paired gains vs **`strict_f3`** on a **larger, independently selected** internal-wrong / external-correct–oriented cohort, while tracking **cost vs `external_l1_max`**.

## Methods to keep

- **`external_l1_max`** (baseline)
- **`strict_f3`** (canonical internal)
- **`direct_reserve_semantic_frontier_v1`** (primary hypothesis)

## Methods to drop or demote (for the next focused run)

- **`semantic_minimum_maturation_frontier_v1_d3`** alone — **no aggregate lift** vs strict on the diagnostic cohort.
- **`branching_necessity_gate_v1`** — optional **ablation** only (small lift vs strict; adds complexity).

## Methods optional (secondary track)

- **`semantic_minimum_maturation_plus_direct_reserve_v1`** — include **only if** budget allows; middle accuracy between DR and strict on the pilot.

## Case count and selection

- **Target:** **30 unique `example_id`s** where the JSONL pool supports it (the pilot run yielded **9** IDs after filters — refresh / widen the loss pool or relax filters with explicit documentation).
- **Budgets:** **4, 6, 8** (same as pilot).
- **Dataset:** **`openai/gsm8k`** Cohere reruns only (same as pilot).

## Runtime (rough)

- Pilot (**9 × 6 × 3 = 162** controller calls) finished in **~13 minutes** wall time on Wulver.
- Linear extrapolation to **30** cases: **~40–50 minutes** if API latency stable — budget **2–6 hours** Slurm wall time for safety.

## Wulver sbatch plan

- Clone pattern from **`batch/run_semantic_diversity_loss_full_20260427T232800Z.sbatch`**:
  - **Job name:** e.g. `semdiv-loss-focus`
  - **Resources:** **4 CPUs**, **16 GB**, partition per site policy (**debug** vs general — confirm wall-time limits).
  - **Logs:** `outputs/slurm_logs/semantic_diversity_loss_focus_<timestamp>_%j.{out,err}`
  - **Environment:** conda / `.venv` per prior successful jobs; **`COHERE_API_KEY`** required (never echo value).
- Python invocation (methods narrowed via **`--methods`** once supported, or fork manifest to **`METHODS_LOSS_FULL`** minus dropped entries):

```bash
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp <timestamp> \
  --mode cohere \
  --run-live-cohere \
  --max-cases 30 \
  --allow-large-run \
  --selection-profile loss-full \
  --budgets 4,6,8 \
  --emit-full-traces \
  --dataset-name openai/gsm8k
```

If `--methods CSV` is used in the future, restrict to **`external_l1_max,strict_f3,direct_reserve_semantic_frontier_v1`** (+ optional combined variant).

## Stopping criteria

- Stop after **one full successful manifest** (`manifest.json`, complete `per_case_results.csv`).
- **Do not** extend mid-run unless resumability is implemented — this runner is single-pass.

## Claim boundaries

- **Allowed internally:** directional paired deltas vs strict on **held-out selection** from the loss JSONL pipeline.
- **Not allowed for paper text:** single **N=9** cohort accuracy ordering vs external; **bad seeding** and **telemetry gaps** dominate failure_taxonomy — requires replication and cleaner semantic telemetry parity across methods.

## Analysis command (offline, no API)

```bash
python scripts/analyze_semantic_diversity_diagnostic_run.py --timestamp <timestamp>
```
