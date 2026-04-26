# Direct-reserve learned scorer validation (diagnostic) — 2026-04-26

## Scope

- Cursor-only bounded validation; no Wulver, Slurm, batch files, OpenAI, budget 6/8, broad sweep, or runtime wiring.
- All learned selectors remain diagnostic-only. `strict_f3` was not modified.

## API use and collection

- Cohere API used: **yes** (`command-r-plus-08-2024`), one real run, budget **4**, seed **37**.
- New collection output: `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T151700Z/`.
- New cases collected: **20** unique planned examples, **100** case-method rows, **164** candidate rows.
- Overlap with first slice: **20/20 examples**. The script received `--exclude-previous-output`, but the available planning pool only contained the same 20 GSM8K IDs, so it fell back to those IDs with a new seed.

## Dataset sizes

| slice | dataset | candidate rows | positive rows | case groups |
|---|---|---:|---:|---:|
| first seed 23 | `outputs/direct_reserve_candidate_scorer_dataset_20260426T150000Z/` | 124 | 81 | 20 |
| second seed 37 | `outputs/direct_reserve_candidate_scorer_dataset_20260426T153000Z/` | 164 | 74 | 20 |
| combined | `outputs/direct_reserve_candidate_scorer_dataset_20260426T153500Z/` | 328 | 155 | 40 |

## Selected-gold rates

| selector | first slice | second slice same-slice | first model on second | second model on first | combined grouped holdout |
|---|---:|---:|---:|---:|---:|
| base plus-diverse | 0.60 | 0.80 | 0.80 | 0.60 | 0.75 |
| support-count | 0.75 | 0.70 | 0.70 | 0.75 | 0.83 |
| max-gap rule | 0.55 | 0.60 | 0.60 | 0.55 | 0.58 |
| margin-gated per-case | 0.60 | 0.65 | 0.65 | 0.60 | 0.67 |
| learned logistic | 0.85 | 0.80 | 0.80 | 0.85 | 0.83 |
| learned random forest | 0.85 | 0.80 | 0.85 | 0.75 | 0.92 |
| learned HGB | 0.55 | 0.60 | 0.60 | 0.55 | 0.75 |
| pairwise logistic | 0.85 | 0.80 | 0.85 | 0.85 | 0.92 |

## Degradation and agreement

- First-slice audit: logistic/RF/pairwise each improved **5** cases over base and degraded **0**; logit/RF/pairwise selected-answer agreement was **0.90**.
- First model on second seed: RF and pairwise improved **1** case, degraded **0**, and had **0** control degradations; logistic tied base with **0** improvements/degradations.
- Second model on first seed: logistic and pairwise improved **5**, RF improved **3**, and none degraded base-correct cases.
- Combined grouped holdout: logistic improved **1**, RF/pairwise improved **2**, and none of logistic/RF/pairwise degraded control cases.
- HGB is not safe: it produced learned degradations, including control degradations.

## Interpretation

The new seed-37 run is a useful seed-robustness/control check, but it is **not** a disjoint problem generalization test because all 20 problem IDs overlapped with the first slice. Within that limit, logistic/RF/pairwise are stable enough to beat or tie base, and RF/pairwise clear the +5 percentage point bar on cross-seed and combined holdout without increasing control degradation. Support-count remains competitive and is sometimes stronger than logistic on the grouped holdout.

## Recommendation

Do **not** integrate as a default runtime method yet. The conservative recommendation is a **diagnostic confidence-gated learned override** only, preferably limited to RF/pairwise/logistic agreement or high-margin disagreement cases, while collecting a genuinely disjoint 20–30 case slice before runtime integration. HGB should be excluded from any override candidate.

## Artifacts

- Audit: `outputs/direct_reserve_candidate_scorer_validation_audit_20260426T153600Z/`
- Second collection: `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T151700Z/`
- Second dataset/train/eval: `outputs/direct_reserve_candidate_scorer_dataset_20260426T153000Z/`, `outputs/direct_reserve_candidate_scorer_train_20260426T153000Z/`, `outputs/direct_reserve_candidate_scorer_eval_20260426T153000Z/`
- Combined dataset/train: `outputs/direct_reserve_candidate_scorer_dataset_20260426T153500Z/`, `outputs/direct_reserve_candidate_scorer_train_20260426T153500Z/`
- Cross-slice eval: `outputs/direct_reserve_candidate_scorer_cross_slice_eval_20260426T153600Z/`
- Degradation analysis: `outputs/direct_reserve_candidate_scorer_degradation_analysis_20260426T153600Z/`
