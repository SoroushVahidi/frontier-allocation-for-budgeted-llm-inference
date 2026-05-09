# Present-not-selected offline replay / selector counterfactual report

- Bundle: `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z`
- PAL method: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`
- Gold labels used **only** for offline scoring (not proposed runtime rules).

## A. 23-case inventory (preferred / present_not_selected)

Validated `case_id` list (from `failure_cluster_summary.csv`, matches `selected_failure_cases.jsonl` / `pal_loss_external_win_cases.csv` rows): `openai_gsm8k_1082`, `openai_gsm8k_1083`, `openai_gsm8k_1085`, `openai_gsm8k_1087`, `openai_gsm8k_1095`, `openai_gsm8k_1097`, `openai_gsm8k_1116`, `openai_gsm8k_1120`, `openai_gsm8k_1121`, `openai_gsm8k_1122`, `openai_gsm8k_1124`, `openai_gsm8k_1150`, `openai_gsm8k_1175`, `openai_gsm8k_1205`, `openai_gsm8k_1210`, `openai_gsm8k_1214`, `openai_gsm8k_1279`, `openai_gsm8k_1290`, `openai_gsm8k_1291`, `openai_gsm8k_1299`, `openai_gsm8k_1303`, `openai_gsm8k_1307`, `openai_gsm8k_1314`

Each row is PAL wrong with at least one external correct, and mining tagged `present_not_selected` / gold present in PAL-side artifacts.

## B. Replay feasibility counts

- `replay_ready`: **23** / 23
- `manual_trace_needed`: **0**
- `not_replayable`: **0**
- Rows with non-empty `ambiguous_gold_presence` cross-check: **15** / 23 (see table column; mostly `gold_in_tree` vs normalized selector pool mismatch).

## C. Main commitment failure mechanisms (offline diagnosis)

- **overlay_previous_equals_gold_but_surface_used_bad_pal_stdout**: 16 case(s)
- **frontier_tiebreak_selected_peer_not_gold_while_gold_in_pool**: 3 case(s)
- **gold_in_tree_but_not_in_selector_pool_normalized**: 2 case(s)
- **histogram_skew_duplicate_paths_favor_wrong_answer**: 1 case(s)
- **gold_in_pool_but_missing_from_answer_group_histogram**: 1 case(s)

Representative patterns:

- **Histogram / grouping dominates**: duplicate paths inflate the wrong numeric (`openai_gsm8k_1083`).
- **Branch-score ordering among ties**: triple ties resolved by `answer_group_best_branch_scores` lex tie-break (`openai_gsm8k_1279`, `openai_gsm8k_1291`, `openai_gsm8k_1307`).
- **Frontier tie-break channel chooses the PAL peer** while DR holds gold (`openai_gsm8k_1124`).
- **PAL stdout / overlay mismatch**: overlay records gold-aligned prior but surfaced answer follows executable PAL output (`openai_gsm8k_1087`).
- **Gold visible in tree but not normalized into selector pool**: limits pool-only oracle ceilings (**8 / 23** rows have gold literally present in `selector_candidate_pool`).

## D. Counterfactual policy results (23-case subset)

- Best-scoring policy on this slice (fixes minus NA penalty): **`max_answer_group_support`**.
- `max_answer_group_support` / `hybrid_max_support_else_dr` / `pal_overlay_previous`: **16** / 23 offline fixes.
- `direct_reserve_answer` / `pool_max_branch_score`: **5** / 23 (often mirrors the committed DR path).
- `max_support_tie_prefer_direct_reserve`: **15** / 23 (hurts some overlay/tie rows; see guardrails).

Detail: `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/counterfactual_policy_summary.csv` and `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/present_not_selected_replay_table.csv`.

### D2. Seven cases still wrong under `max_answer_group_support` (offline)

| case_id | gold (normalized) | max-support prediction | Failure sketch |
|---|---|---|---|
| `openai_gsm8k_1083` | 55 | 605 | Duplicate paths inflate **605** vs **55** in `answer_group_support_counts`. |
| `openai_gsm8k_1085` | 156 | 260 | Histogram collapses to **260** only; **156** appears in pool with weak branch score — grouping gap. |
| `openai_gsm8k_1095` | 4 | 2 | Gold **4** appears in pool but histogram keys are **2** vs **7** — grouping omits gold bucket. |
| `openai_gsm8k_1124` | 45 | 25 | Equal support **25** vs **45**; branch-score metadata favors **25** (PAL seed peer). |
| `openai_gsm8k_1279` | 24 | 30 | Triple tie among **24 / 30 / 12**; branch-score tie-break favors **30**. |
| `openai_gsm8k_1291` | 50 | 25 | Triple tie; scores omit **50** from `answer_group_best_branch_scores` → defaults lose to **25**. |
| `openai_gsm8k_1307` | 26 | 23 | Triple tie **26 / 23 / 24**; lex / branch ordering picks **23** over gold **26**. |

## E. Guardrail evaluation (offline regressions)

- Band **openai_gsm8k_1072–1318**, PAL exact-match cohort: **189** rows.
- **Both PAL and best-external correct**: **183** rows.
- **PAL-only correct** (unique PAL wins): **5** rows.
Counterfactual regressions counted when policy prediction differs from gold while surfaced PAL answer already equals gold.

| policy | regressions (both-correct) | regressions (PAL-only) |
|---|---:|---:|
| `max_answer_group_support` | 39 | 2 |
| `max_frontier_answer_group` | 33 | 3 |
| `direct_reserve_answer` | 112 | 5 |
| `pool_max_branch_score` | 113 | 5 |
| `pal_overlay_previous` | 39 | 3 |
| `guarded_direct_reserve` | 112 | 5 |
| `hybrid_max_support_else_dr` | 39 | 2 |
| `max_support_tie_prefer_direct_reserve` | 60 | 5 |
| `prefer_strong_pal_executable` | 1 | 0 |
| `frontier_tiebreak_selected_group` | 24 | 2 |

Prior selector-isolated / rate-ratio harmed-case replay directories were **not** attached in this bundle; mark **N/A** here.

## F. Recommended Track B intervention (hypothesis)

- Prioritize **commitment-layer fixes** (histogram construction, tie-breaking among equal-support groups, and consistent surfacing after PAL overlay / tie-break) before expanding TRCE-only breadth.
- Treat duplicate-path inflation and **numeric normalization in grouping** as first-class to avoid wrong majors winning support counts.
- Where frontier tie-break fires, ensure the chosen peer is consistent with **selector-visible** candidates and final surfacing (avoid PAL stdout superseding overlay decisions).

## G. Why this avoids previously failed directions

- Does **not** rely on gold traces at runtime; diagnostics show failures cluster in **selection / commitment**, not only PAL codegen coverage.
- Avoids **direct_reserve-as-final** defaults: offline DR policies regress heavily on already-correct rows.
- Avoids **naive PAL-strength always-wins** (`prefer_strong_pal_executable` barely helps on these 23).

## H. Likely source touch-points (future implementation only)

- `experiments/controllers.py` — final commitment / overlay vs surfaced answer ordering.
- `experiments/frontier_matrix_core.py` / frontier tie-break hooks.
- `experiments/branching.py` — candidate propagation into selector pools / histogram keys.
- `experiments/output_layer_repair.py` — repair vs controller final path.
- `experiments/pal_executor.py` (if present) — PAL stdout vs overlay contract.

## I. Offline tests required before code changes

- Unit tests for **answer-group aggregation** with duplicate branches and numeric normalization.
- Fixture replay from `per_example_records.jsonl` rows **1124, 1087, 1083, 1279** covering tie-break, overlay/surface mismatch, and skewed histograms.
- Regression harness on GSM8K band **1072–1318** PAL-correct rows for any new selector rule.

## J. API needed now?

**No** — this memo used only saved artifacts in `outputs/`.

## K. Exact next action

1. Review `present_not_selected_replay_table.csv` for per-case mechanisms.
2. Prototype a **Track B** histogram / tie-break patch behind flags; replay this bundle offline.
3. Re-run the cost-normalized validation job only after offline replay parity checks pass.

---

### Artifact paths

- `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/present_not_selected_replay_table.csv`
- `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/counterfactual_policy_summary.csv`
