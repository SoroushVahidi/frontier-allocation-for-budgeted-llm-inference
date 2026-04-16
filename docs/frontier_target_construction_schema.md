# Frontier target construction schema

This document defines the core artifacts used by the frontier target-construction pipeline (pilot state manifest, generated labels, and run manifests).

## 1) Pilot state manifest (`pilot_state_manifest.jsonl`)

Produced by `scripts/build_oracle_label_pilot_state_manifest.py`.

### Required fields

- `state_id` (`str`): deterministic unique key in the form `s{source_seed}_b{budget}_e{episode_id}_d{decision_id}_{current_branch_id}`.
- `selection_name` (`str`): selection-config identifier.
- `selection_seed` (`int`): deterministic selection seed.
- `source_pipeline` (`str`): source dataset builder path/name.
- `source_seed` (`int`): source simulation seed.
- `budget` (`int`): decision budget.
- `episode_id` (`int`): source episode index.
- `decision_id` (`int`): source decision index.
- `current_branch_id` (`str`): branch identifier at this decision.
- `remaining_budget` (`int`): remaining decision steps.
- `split` (`str`): train/test split tag from source row.
- `ambiguity_bucket` (`high|medium|low`): ambiguity stratum from `abs_gap_to_best_other_gain` tertiles (per budget).
- `uncertainty_bucket` (`uncertain|certain`): uncertainty stratum from source uncertainty flag.
- `stratum_tag` (`str`): combined stratification key (`budget=...|ambiguity=...|uncertainty=...`).
- `label_act_proxy` (`int`): source proxy stop-vs-act label.
- `delta_mean_proxy` (`float`): source local delta estimate.
- `delta_std_proxy` (`float`): source local instability estimate.
- `delta_sign_flip_rate_proxy` (`float`): source estimator sign instability metric.
- `abs_gap_to_best_other_gain` (`float`): absolute competition gap.
- `score_entropy` (`float`): source branch score entropy feature.
- `features` (`dict[str,float]`): stop-vs-act feature vector.
- `selected_rank_in_stratum` (`int`): deterministic selection rank.

## 2) Oracle stop-vs-act labels (`oracle_stop_vs_act_labels.jsonl`)

Produced by prototype/heavy generators.

### Required fields

- `state_id` (`str`): join key back to state manifest.
- `example_id` (`str`): episode-level grouping key (e.g., `seed7_ep12`).
- `budget` (`int`), `remaining_budget` (`int`), `current_branch_id` (`str`): copied state metadata.
- `q_act` (`float`): expected continuation value under forced ACT-here first action.
- `q_stop` (`float`): expected continuation value under STOP-here-first (skip branch first action).
- `oracle_action_gap` (`float`): `q_act - q_stop`.
- `oracle_label_act` (`0|1`): binary ACT decision (`1` iff `oracle_action_gap > 0`).
- `horizon` (`int`), `rollout_depth` (`int`): local rollout evaluation horizon/depth.
- `teacher_mode` (`str`): expected `offline_policy_coupled_oracle_rollout`.
- `paired_randomness_used` (`bool`): paired RNG rollout policy flag.
- `gap_std` (`float`): per-state rollout gap standard deviation.
- `agreement_rate` (`float`): fraction of rollout-gap signs matching final sign.
- `rollout_count` (`int`): paired rollouts per state.
- `generator_impl` (`str`): implementation tag.
- `prototype_mode` (`bool`): prototype vs heavy-path flag.
- `shard_name` (`str`, heavy only), `shard_id` (`int`, heavy only).

## 3) Pairwise oracle preferences (`pairwise_oracle_preferences.jsonl`)

Produced by branch-label generation (`experiments/oracle_branch_labels.py` path).

### Required fields

- `episode_id`, `decision_id`, `remaining_budget`.
- `branch_a_id`, `branch_b_id`.
- `approx_oracle_a`, `approx_oracle_b`.
- `proxy_a`, `proxy_b`.
- `oracle_preference` (`-1|0|1`): branch A preferred/tie/not-preferred under oracle-ish value and tie margin.
- `proxy_preference` (`-1|0|1`): same using proxy value.
- `oracle_proxy_agree` (`0|1`): preference agreement indicator.
- `oracle_tie`, `proxy_tie` (`0|1`): tie indicators.
- `oracle_margin`, `proxy_margin` (`float`): absolute pairwise margins.
- `label_source` (`str`): provenance label.

## 4) Run manifests

### Heavy generator manifest (`oracle_label_manifest.json`)

Key sections:

- `generator_contract`, `generator_impl`, `heavy_path`, `prototype_real_rollouts`.
- `inputs`: config paths, `state_manifest_sha256`, resume settings.
- `teacher`: rollout/evaluation settings.
- `source_reconstruction`: source replay settings.
- `shard`: shard provenance and split-manifest verification status.
- `outputs`: label path and completion accounting.
- `run_stats`: processed/skipped/error counts and elapsed time.
- `partial_failures`: row-level error captures.

### Progress file (`oracle_label_progress.json`)

- rolling status with `rows_total`, `rows_completed`, `rows_skipped_by_resume`, `state_errors`, `last_state_id`.

## 5) Exact vs approximate branch-value mode fields

For branch-value labels (oracle-ish continuation values):

- `value_is_exact` (`bool`) and `label_kind` (`str`) disambiguate exact terminal/zero-budget labels from approximate bounded-rollout labels.
- Expected `label_kind` values:
  - `exact_terminal_or_zero_budget`.
  - `approx_high_budget_rollout_max`.
  - `approx_high_budget_rollout_robust_blend`.
