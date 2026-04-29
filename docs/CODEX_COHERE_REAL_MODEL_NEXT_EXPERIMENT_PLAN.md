> **WARNING (diagnostic/small-sample):** This document is not standalone canonical paper-facing evidence. Do not use for broad superiority claims without canonical matched-surface confirmation.

# CODEX Cohere Real-Model Next Experiment Plan (2026-04-29)

Status class for this plan: **diagnostic/supporting** (not canonical paper-table evidence by itself).

## 1) Current real-model evidence status

- Real-model Cohere/OpenAI evidence is currently **supporting/diagnostic only**, not headline canonical paper evidence.
- Durable Codex-local Cohere progress source is the compact ledger path under `outputs/cohere_compact_ledgers/`, with current continuation centered on timestamp `20260429T_COHERE_FULL_ACCURACY_CODEX`.
- The `openai/gsm8k`, budget `2`, seed `11` matched slice remains explicitly tracked as incomplete in status docs.

## 2) Safe vs diagnostic-only results

### Safe to use for manuscript-facing claims (with existing policy caveats)
- Canonical claim-bearing evidence remains only what is regenerated into:
  - `outputs/paper_tables/`
  - `outputs/paper_plot_data/`
  - `outputs/paper_figures/`
- Within method-positioning language: `strict_f3` is manuscript-facing matched-surface representative, while `strict_gate1_cap_k6` is broader operational default on a different surface.

### Diagnostic/supporting only (not headline-safe alone)
- Cohere real-model chunk runs and aggregates under `outputs/cohere_real_model_cost_normalized_validation_<timestamp>/`.
- Cross-provider/main-run audits that currently do not establish dominance over `external_l1_max`.
- Any tiny/provenance/interrupted runs and markdown-only progress notes not backed by compact ledger rows.

## 3) Exact runnable method set for next Cohere experiment

Use this 9-method runnable set (validated against live runner path):

1. `strict_f3`
2. `strict_gate1_cap_k6`
3. `strict_f2`
4. `direct_reserve_semantic_frontier_v2`
5. `direct_reserve_semantic_frontier_v2_selection_fix_v1`
6. `external_l1_max`
7. `tale`
8. `s1`
9. `self_consistency_3`

## 4) Method IDs to exclude

Must exclude from live full-comparison experiments:

- `direct_reserve_semantic_frontier_v2_thresholded_ordered`

Reason: diagnostic-only and not runtime-present in live `build_frontier_strategies(...)` runner path.

## 5) Smallest meaningful Cohere experiment to improve the paper

### Recommended minimal experiment
A **single fully completed matched slice** on Cohere for:
- Dataset: `openai/gsm8k`
- Budget: `2`
- Seed: `11`
- Methods: the 9-method runnable set above
- Target scored per method: `100`

Why this is the highest-value minimum:
- It directly closes the explicitly documented incomplete slice.
- It yields fair same-slice method comparisons including `external_l1_max`.
- It is the smallest unit that can materially tighten appendix-safe real-model narrative without running full multi-dataset/budget grids.

## 6) Exact commands to run (next task)

## 6.1 Preflight: method validation (no API calls)
```bash
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp 20260429T_COHERE_NEXT_MINIMAL \
  --providers cohere \
  --datasets openai/gsm8k \
  --budgets 2 \
  --seeds 11 \
  --methods strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3 \
  --validate-methods-only
```

## 6.2 Build chunk plan
```bash
python scripts/plan_cohere_real_model_chunks.py \
  --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_next_minimal.csv \
  --datasets openai/gsm8k \
  --budgets 2 \
  --seeds 11 \
  --methods strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3 \
  --target-scored-per-slice 100
```

## 6.3 Execute each missing chunk (API-calling; run in next task)
```bash
python scripts/status_cohere_chunk_progress.py \
  --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_next_minimal.csv \
  --timestamp 20260429T_COHERE_NEXT_MINIMAL

python scripts/run_cohere_chunk.py \
  --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_next_minimal.csv \
  --chunk-id <MISSING_CHUNK_ID> \
  --timestamp 20260429T_COHERE_NEXT_MINIMAL \
  --max-walltime-minutes 20
```

Repeat `run_cohere_chunk.py` until all nine chunks show complete.

## 6.4 Aggregate final outputs
```bash
python scripts/aggregate_cohere_chunks.py \
  --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_next_minimal.csv \
  --timestamp 20260429T_COHERE_NEXT_MINIMAL
```

## 7) Expected output directory names

Primary run directory:
- `outputs/cohere_real_model_cost_normalized_validation_20260429T_COHERE_NEXT_MINIMAL/`

Expected key files in that directory:
- `method_validation_report.csv`
- `slice_summary.csv` (or synthesized from compact ledger when absent)
- `pairwise_comparisons.csv` (if produced by run path)
- `chunk_progress_status.csv`
- `codex_per_slice_finality.csv`
- `codex_method_summary_final_only.csv`
- `codex_pairwise_vs_external_l1_max.csv`
- `codex_failed_or_incomplete_slices.csv`

Expected plan file:
- `outputs/codex_local_chunk_plan_20260429_cohere_next_minimal.csv`

Expected aggregate markdown:
- `docs/CODEX_LOCAL_COHERE_AGGREGATE_20260429T_COHERE_NEXT_MINIMAL.md`

## 8) Required columns in final summary CSVs

## 8.1 `codex_per_slice_finality.csv`
- `provider`
- `dataset`
- `seed`
- `budget`
- `method`
- `scored_examples`
- `target_scored_count`
- `failed_examples`
- `skipped_examples`
- `accuracy`
- `total_tokens`
- `estimated_cost_usd`
- `avg_latency_seconds`
- `is_final`

## 8.2 `codex_method_summary_final_only.csv`
- `method`
- `final_slices`
- `mean_accuracy`
- `total_tokens`
- `total_cost_usd`
- `mean_latency_seconds`

## 8.3 `codex_pairwise_vs_external_l1_max.csv`
- `provider`
- `dataset`
- `seed`
- `budget`
- `method_a`
- `method_b`
- `accuracy_delta_a_minus_b`
- `n_paired_examples`
- `ci95_lo`
- `ci95_hi`
- `ci95_status`

## 9) If this experiment succeeds, what manuscript claims become safer?

Safer (still bounded/appendix-safe) claims:
- Cohere real-model evidence is no longer missing for the specifically flagged `openai/gsm8k`, budget `2`, seed `11`, 9-method matched slice.
- Cross-method directional statements for that slice become more defensible with complete per-method scored counts.
- Provider-specific diagnostic stability wording (not dominance wording) can be strengthened.

## 10) What still remains unsafe even if it succeeds?

Still unsafe:
- Any universal/robust dominance claim over `external_l1_max` from this single-slice completion.
- Any claim that real-model evidence is canonical headline evidence on its own.
- Any token/latency/cost-matched fairness claim beyond what is explicitly computed/documented.
- Any broad cross-provider or cross-surface generalization claim requiring larger completed grids.
