# Current runbook (operational)

Short **current** commands only. For the full script inventory, see repository [`README.md`](../README.md) and [`scripts/README.md`](README.md).

## Health and reviewer-safe checks

```bash
cd /path/to/adaptive-reasoning-budget-allocation   # repo root
make health
make reviewer-test
```

Optional selector-focused tests:

```bash
make selector-test
```

## Selected selector rerun (recovery evidence package)

Align flags with `configs/selected_selector_current.json`:

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
python scripts/run_outcome_verifier_answer_group_selector.py \
  --input outputs/unified_selector_evidence_20260501T145906Z/unified_candidate_trace_enriched.jsonl \
  --output-dir "outputs/outcome_verifier_answer_group_selector_selected_${STAMP}" \
  --selector-name outcome_verifier_answer_group_selector_v1 \
  --scorer-mode cached_jsonl \
  --score-cache outputs/outcome_verifier_scores_cohere_smoke10_20260501T162328Z/verifier_scores.jsonl \
  --min-verifier-margin 0.0 \
  --require-trace-for-override \
  --dedupe-verifier-items \
  --no-gold-features
```

Dry-run call counts before paid scoring:

```bash
python scripts/run_outcome_verifier_answer_group_selector.py --help
# use --scorer-mode dry_run_call_plan when wiring a new input
```

## Self-consistency literature baseline

```bash
python scripts/run_self_consistency_majority_selector.py --help
```

Use only on **existing** candidate pools; compare on **matched** paired slices with the verifier selector.

## External-baseline / paired selector application

```bash
python scripts/apply_selected_selector_to_paired_validation.py --help
```

## External-loss 88-case diagnostics + related cluster jobs (Wulver)

Read `docs/FULL_SCORE_COMPLETION_88_EXTERNAL_LOSSES_20260502.md` before any paid scoring. **Do not submit casually:** verify partition/QoS/workspace env per cluster policy (`docs/FAST_SELECTOR_EXECUTION_POLICY.md`).

| Batch file | Purpose |
|------------|---------|
| `batch/run_full_pipeline_best_selector_on_88_external_losses_wulver.sbatch` | Full pipeline + selector on **88** external-loss slice (**1018219-era** artefacts may show missing verifier scores vs **1018248**) |
| `batch/run_full_score_completion_on_88_external_losses_wulver.sbatch` | **Score completion merge + selector rerun** (bounded calls; **`1018248`**) |
| `batch/run_main3_external_vs_best3_internal_100case_wulver.sbatch` | **1018203‑class** GSM8k main external-vs-internal (**100**/method harness) |
| `batch/run_strategy_seeded_discovery_on_66_gold_absent_wulver.sbatch` | Strategy-seeded discovery pilot on curated **66** gold-absent slice (**`1018304`**) |
| `batch/run_strategy_seeded_discovery_final_check_wulver.sbatch` | Fair-check / alignment audit cohort for **`direct_reserve_strategy_seeded_semantic_frontier_v2_final`** |
| `batch/run_gold_absent_path_gap_diagnostic_wulver.sbatch` | Preferred **gold-absent path-gap proxy** exporter (**1018287** bundle family) |

Submit (example):

```bash
sbatch batch/run_full_score_completion_on_88_external_losses_wulver.sbatch
```

## Inspect latest relevant results (non-exhaustive)

| Goal | Where to look |
|------|----------------|
| Current selector decision | `docs/CURRENT_SELECTOR_DECISION.md`, `outputs/final_selector_decision_20260501T175547Z/` |
| Recovery audit | `outputs/selected_selector_audit_20260501T181608Z/` |
| External L1 comparison (diagnostic if cache-limited) | `outputs/best_selector_vs_external_l1_comparison_*/` |
| 88-case external-loss slice | `outputs/best_methods_on_external_losses_20260430T195200Z/` |
| Method / artifact classification | `docs/METHOD_STATUS_TABLE.md`, `docs/ARTIFACT_STATUS_TABLE.md` |

## What not to run casually

- Full **`outputs/` regeneration**, **main3-vs-best3** long harnesses, or large **`cohere_real_model_cost_normalized_validation`** sweeps without an explicit experiment plan + API/token budget (**includes `run_main3_external_vs_best3_internal_100case_wulver.sbatch`**).
- **Paper artifact** regeneration (`scripts/paper/run_all_neurips_paper_artifacts.py`) when you only need selector health checks.
- **Historical** scripts in `scripts/HISTORICAL_INDEX.md` unless reproducing provenance.

Follow `docs/FAST_SELECTOR_EXECUTION_POLICY.md` for any paid API use.
