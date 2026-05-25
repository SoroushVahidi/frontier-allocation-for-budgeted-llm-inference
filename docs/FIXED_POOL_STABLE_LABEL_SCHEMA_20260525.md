# Fixed-Pool Stable Label Schema

Date: 2026-05-25

---

## Purpose

When training a learned selector on a fixed candidate pool, the features and labels must
be defined precisely to avoid leakage, ensure reproducibility, and support ablation.

This document defines the stable label schema for the MATH-500 fixed-pool selector.

---

## Permanent labels (fixed facts about the pool)

These describe fixed facts once the pool is frozen. They must NOT change between training runs.

| Column | Type | Description |
|---|---|---|
| `source_correct_vector` | list[bool] | Correctness of each source in the pool, in canonical order |
| `cluster_correct` | bool | Whether any cluster of identical answers contains the gold |
| `all_sources_wrong` | bool | True if every source in the pool is wrong for this example |
| `true_pool_failure` | bool | True if the pool has no correct answer for any method |
| `normalization_fixable` | bool | True if stronger normalization would reveal a correct answer (LaTeX cleanup, etc.) |
| `failure_type` | str | Classification: `pool_failure`, `selection_failure`, `normalization_fixable` |

---

## Derived labels (recomputed when action space changes)

These depend on which actions/providers are in the current pool. They must be recomputed
when new providers or methods are added.

| Column | Type | Description |
|---|---|---|
| `action_correct` | bool | Whether a specific action (provider, method) is correct for this example |
| `correct_actions` | list[str] | List of action names that are correct |
| `selector_family_success` | bool | Whether the selector's chosen action family is correct |

---

## FORBIDDEN features at runtime (leakage risk)

These must NEVER appear as model input features in a trained selector:

| Feature | Why forbidden |
|---|---|
| `gold` / `gold_answer` | Direct leakage of the answer |
| `frontier_correct` / `source_correct` | Encodes whether the source is right (oracle) |
| `oracle_action` / `oracle_source` | Best action in hindsight — not available at inference |
| `correct_answer_cluster` | Reveals which cluster is correct |
| `example_id` (as integer/positional) | Memorization risk; use as key only |
| Test-fold statistics | Any aggregate computed from the test fold |

---

## Selector training rules

1. Features must be computable at inference time without knowing the gold answer.
2. Label leakage via aggregation (e.g., "fraction correct in this subject") is forbidden.
3. The training/validation split must be on `example_id` (not random rows), so all
   action rows for a given example stay in the same fold.
4. Repeated cross-validation (10× 5-fold) with different random seeds is required for
   reliable CV accuracy estimates.
5. LOPO validation: train on N-1 providers, predict held-out provider — required before
   claiming generalization to new providers.

---

## Action-row vs. example-row distinction

The candidate-action table has one row per `(example_id, action_name)`. This is different
from the example-level case table which has one row per `example_id`.

- **Example-level features**: computed once per example (e.g., `cur_has_majority`,
  `pairwise_lc_agree_count`, subject, level, answer-type features)
- **Action-level features**: computed per (example, action) pair (e.g., `method_family`,
  `provider`, estimated cost, latency)
- **Label**: `action_correct` at action level; `oracle_ceiling_hit` at example level

---

## Key predictive features (from learned selector analysis)

Features found most informative by the learned meta-router on Cohere-only pool:

1. `cur_has_majority` — whether a plurality-majority answer exists
2. `pairwise_lc_agree_count` — number of source pairs with exact-match after LC normalization
3. Answer type features (integer vs. expression vs. other)
4. Subject category (Intermediate Algebra and Precalculus have high failure rates)
5. Difficulty level (levels 4–5 correlate strongly with all-wrong)

---

## Cohere-only pool failure summary (context)

| Metric | Value |
|---|---|
| N | 300 |
| True pool failure (all_sources_wrong) | ~161/300 = 53.7% |
| Oracle ceiling (Cohere-only) | ~139/300 = 46.3% |
| Normalization-fixable cases | ~4 (LaTeX cleanup) |
| Agreement-only accuracy | 33.0% |

The dominant failure mode is pool failure (no correct answer exists), not selection failure.
Multi-provider generation is the primary lever for oracle ceiling improvement.

---

## See also

- `docs/MATH500_POOL_IMPROVEMENT_INFRASTRUCTURE_20260525.md` — pool strategy overview
- `docs/COHERE_MATH500_FAILURE_LEARNING_20260525.md` — detailed failure analysis
- `outputs/math500_pool_improvement_infrastructure_20260525/stable_label_schema_for_fixed_pool_selection.md`
  — extended schema with full column list (local, not committed)
