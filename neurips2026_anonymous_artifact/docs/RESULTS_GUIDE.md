# RESULTS_GUIDE

This file is the source-of-truth guide for interpreting repository results for NeurIPS-style review.

## A) Canonical paper-facing results

### Canonical output locations
- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_facing_baseline_tables/`

### Canonical regeneration scripts
- Canonical paper package regeneration:
  - `python scripts/paper/run_all_neurips_paper_artifacts.py`
- Canonical supporting evidence generators (outside paper-output roots but claim-scoped by docs):
  - `python scripts/run_broader_strict_phased_default_decision_eval.py`
  - `python scripts/run_paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3.py`
  - `python scripts/build_paper_facing_baseline_tables.py`

### Canonical supporting reports/docs
- `docs/PAPER_SOURCE_OF_TRUTH.md`
- `docs/PAPER_ARTIFACT_MAP.md`
- `docs/CLAIM_BOUNDARIES.md`
- `docs/MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`

### Canonical definition
An output is canonical only if it is in the promoted paper-facing directories above or explicitly referenced by the source-of-truth documents.

### Method-surface contract (always preserve)
- Manuscript-facing matched-surface representative: `strict_f3`
- Broader operational default on a different surface: `strict_gate1_cap_k6`
- Margin status on matched-surface slices: fragile/non-decisive unless canonical statistical evidence states otherwise.

---

## B) Real-model validation (OpenAI + Cohere)

### Artifact locations
- OpenAI: `outputs/real_model_ours_vs_external_validation_20260424T_OPENAI_REAL_MAIN/`
- Cohere: `outputs/real_model_ours_vs_external_validation_20260424T_COHERE_REAL_MAIN/`
- Additional long-run Cohere diagnostic: `outputs/real_model_ours_vs_external_validation_20260425T_CLUSTER_COHERE_LONG/`
- Cost-normalized Cohere package: `outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN/`

### Provider/model/dataset/budget/seed contract
For any real-model comparison claim, report:
1. provider,
2. exact model identifier,
3. dataset,
4. budget settings,
5. seed policy,
6. whether token/cost/latency matching was enforced.

### Safe vs unsafe interpretation
- **Safe:** real-model runs are diagnostic/stress-test evidence and provider realism checks.
- **Unsafe:** claiming universal or robust superiority from these runs alone.
- Real-model runs are not, by default, a replacement for canonical matched-surface manuscript evidence.

---

## C) Loss-case diagnostics

### Key packages
- Detailed loss-case package: `docs/DETAILED_LOSS_CASE_ANALYSIS_20260425T_CLUSTER_COHERE_LONG_DETAIL.md`
- 10-case deep dive report: `docs/TEN_CASE_LOSS_DEEP_DIVE_20260425T221500Z.md`
- Supporting build script: `scripts/build_10_case_loss_deep_dive.py`

### Problem statements and gold answers
- Structured case bundles and packaged outputs in the `outputs/strict_f3_vs_external_l1_max_more_loss_cases_*` family.
- Gold-answer/problem metadata are stored with per-case records in generated loss packages.

### Recoverable vs rerun-dependent traces
- Recoverable now: packaged summary-level traces and saved per-case diagnostics in committed outputs/docs.
- Requires rerun: missing full branch traces from older runs where branch-level serialization was not enabled.

### Failure-mode definitions
- **present-not-selected:** correct answer/tree evidence appears in explored candidates but final selector chose another candidate.
- **absent-from-tree:** explored reasoning tree never contained a correct candidate to select.

---

## D) Diagnostic/probe variants (non-canonical by default)

The following are currently diagnostic-only unless explicitly promoted by future canonical evidence:
- shallow exhaustive probes,
- direction combinatorics guard,
- typed strategy seeded variant,
- family-normalized reranker,
- selection ablations.

Representative scripts:
- `scripts/run_direction_combinatorics_guard_eval.py`
- `scripts/run_typed_strategy_seeded_eval.py`
- `scripts/run_family_normalized_rerank_eval.py`
- `tests/test_shallow_exhaustive_probe_methods.py`

Use these for mechanism diagnosis, not final method claims, unless revalidated and promoted.

---

## E) Learned scoring status

### Existing learned branch scorers
- Pairwise/BT-style branch scoring and learned branch allocation pipelines are implemented and auditable.
- Learned branch scorers support bounded evaluations and provide useful directional evidence.

### What they currently do
- Improve experimental control over branch ranking decisions.
- Enable targeted ablations and supervision/feature diagnostics.

### What they do not yet do
- They do not establish robust universal superiority across all datasets/providers/budgets.
- They do not replace canonical claim-safety boundaries.

### Explicit non-canonical item
- A learned **answer-group reranker** is not canonical at present unless later implemented, validated, and promoted via canonical evidence paths.

### Paired selector diagnostics (new)
- Use `scripts/run_direct_reserve_paired_selector_eval.py` for interpretable learned-selector evaluation.
- It compares selectors on the **same candidate pools** from `candidate_branch_table.csv` (no independent stochastic reruns).
- Current paired diagnostic packages:
  - `outputs/direct_reserve_paired_selector_eval_20260426T_REPAIRED_FIRST/`
  - `outputs/direct_reserve_paired_selector_eval_20260426T_REPAIRED_OVERLAP_DIAGNOSTIC/`
- Status note:
  - `docs/DIRECT_RESERVE_PAIRED_SELECTOR_EVAL_STATUS.md`
