# Direct-reserve learned candidate scorer (diagnostic) — 2026-04-26

## 1. Data before new API collection

- Prior `cohere_direct_reserve_validation_*` packages in the repo had at most **5–12** unique problems with full `candidate_branch_table.csv` + traces; **not** enough for a stable 30-problem target.
- Inventory: `outputs/direct_reserve_learned_scorer_inventory_20260426T000000Z/`.

## 2. New Cohere API run

**Yes.** A bounded real Cohere run was executed (budget **4** only, seed **23**).

- **Planned** `max_cases=30`; the loss-artifact **stratified pool** only yielded **20** unique `example_id` values in the planned set (strata: 9 absent, 2 present_not_selected, 9 control).
- **Output:** `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T150000Z/`
- **Methods:** `strict_f3`, `external_l1_max`, `direct_reserve_strong_v1`, `direct_reserve_strong_plus_diverse_v1`, plus `direct_reserve_strong_plus_diverse_margin_gated_v1` (comparison / per-case final only; margin rows **excluded** from default training in the dataset builder).
- **CLI change:** `scripts/run_cohere_direct_reserve_validation.py` now accepts `--scorer-dataset-extended` to allow `max-cases` up to **30** (still no budgets 6/8).

## 3. Final dataset size

- **Builder:** `outputs/direct_reserve_candidate_scorer_dataset_20260426T150000Z/`
- **Rows:** 124 candidate rows; **~20** unique (example_id, seed, budget) case keys.
- **Positive `is_gold_candidate` (trainable, margin_gated excluded):** 81 (from `dataset_summary.csv`).

## 4. Gold-present problems

- Count from `per_case_method_results` for `direct_reserve_strong_plus_diverse_v1` is in the 10–20 range for this run (see Cohere package `per_method_summary.csv`); the dataset also carries `problem_gold_present` / `diverse_gold_in_pool` per row.

## 5. Best model (diverse re-rank, held-out *groups*)

- On the default **0.3 test-fraction** grouped holdout, **logistic, random forest, and pairwise** all achieved the same **diverse top-1** rate: **0.85** (see `outputs/direct_reserve_candidate_scorer_train_20260426T150000Z/metrics.csv` — 5/6 test *cases* with 2+ diverse candidates).
- HGB: **0.5** on that metric (weaker for this small sparse tabular one-hot).
- This is a **small-sample** result; CIs are wide.

## 6. Did learning beat the base `direct_reserve_strong_plus_diverse_v1` selector?

- **On this run, yes, when measured as “re-rank among diverse branch rows”.**  
  `outputs/direct_reserve_candidate_scorer_eval_20260426T150000Z/selector_comparison.csv` reports **0.6** base vs **0.85** for learned logit/RF/pairwise (see table below).  
- **Caveat:** 20 problems is still small; a **5 percentage point** bar for *generalization* is not yet proven at scale.

## 7. Margin-gate “hurt” pattern vs learned scorer

- The margin-gated **per_case** final matches base at **0.6** in this table (same as original diverse selection policy on this pool when taking the model’s *final* answer). Learned re-rankers that only see *branch* features can score **higher** without the brittle “flip when gap low + entropy high” hand rule.
- The eval still exposes `margin_gated_per_case` for A/B; do **not** conflate with runtime integration of the *gate inside* the controller.

## 8. Present-not-selected

- `problem_present_not_selected` is in each row; aggregate reduction requires stricter reporting (not fully tabulated in this first pass). Support-count rose to **0.75** in `selector_comparison.csv` vs base **0.6** on this 20-problem set.

## 9. Control degradation

- `case_level_selection.csv` has `stratum` and per-selector `ok__*`. Spot-check `control_correct` **false positives**; no new safety claim without a control-specific slice.

## 10–11. Ready for diagnostic runtime? More data?

- **Not** for “always on” in production. **Suitable** for: offline scoring on logged candidate sets, and **confidence-gated** re-rank experiments after **30–50+** more grouped problems and stable feature contracts.
- **Next:** extend dataset to 30+ unique case keys if the pool allows, add verifier-on-disagreement, or collect seed **37** in a second small package to test seed holdout.

## Selector comparison (this run)

| Selector | selected_gold_rate (n=20) |
|----------|---------------------------:|
| base_plus_diverse | 0.60 |
| support_count | 0.75 |
| max_gap_rule | 0.55 |
| margin_gated_per_case | 0.60 |
| learned_logit | **0.85** |
| learned_rf | **0.85** |
| learned_hgb | 0.55 |
| pairwise_logit | **0.85** |

Paths:

- Training: `outputs/direct_reserve_candidate_scorer_train_20260426T150000Z/`
- Eval: `outputs/direct_reserve_candidate_scorer_eval_20260426T150000Z/`
- `selected_model.joblib` bundles `vectorizer`, `logistic`, `rf`, `hgb`, optional `pair_vectorizer` / `pair_logit`.

**Conservative recommendation:** *Promising* on this diagnostic slice, but **do not** integrate as default runtime re-rank until: (1) at least 30+ unique case keys with the same feature schema, (2) a second seed or stratum holdout, (3) explicit degradation/safety metrics on `control_correct`.

---

## Pipeline scripts

- `scripts/build_direct_reserve_learned_scorer_inventory.py`
- `scripts/build_direct_reserve_candidate_scorer_dataset.py`
- `scripts/train_direct_reserve_candidate_scorer.py`
- `scripts/run_direct_reserve_candidate_scorer_eval.py`
- `tests/test_direct_reserve_candidate_scorer.py`
