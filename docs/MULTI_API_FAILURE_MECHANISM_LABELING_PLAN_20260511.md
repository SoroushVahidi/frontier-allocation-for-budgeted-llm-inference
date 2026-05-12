# Multi-API Failure Mechanism Labeling Plan

## Purpose

Build a deterministic, multi-provider labeling scaffold for PAL failure mechanisms.

This is a no-API-first utility. It should be usable as a dry-run planner and
trace builder without any paid/model calls. Live provider calls are gated behind
explicit flags and hard caps.

## Experiment Shape

- Script: `scripts/label_failure_mechanisms_multi_api.py`
- Default mode: dry-run only
- Supported providers:
  - Cohere
  - Cerebras
  - Fireworks
- Default prompt packet: gold-free
- Gold assistance: opt-in only via `--include-gold-for-labeling`

## Label Schema

Each provider must return strict JSON with these keys:

- `case_id`
- `primary_label`
- `secondary_labels`
- `selector_vs_generation`
- `candidate_pool_status`
- `confidence`
- `evidence`
- `recommended_fix_family`

Allowed values are intentionally narrow:

- `primary_label` / `secondary_labels`
  - `wrong_target_variable`
  - `premature_intermediate_answer`
  - `wrong_entity_or_unit`
  - `wrong_time_or_state`
  - `wrong_relation`
  - `wrong_operator`
  - `ratio_or_percentage_base_error`
  - `PAL_code_grounding_error`
  - `PAL_execution_failure`
  - `pure_arithmetic_error`
  - `correct_candidate_present_not_selected`
  - `all_candidates_wrong`
  - `candidate_pool_missing`
  - `metadata_insufficient`
  - `unknown`
- `selector_vs_generation`
  - `selector_failure`
  - `generation_failure`
  - `mixed`
  - `metadata_insufficient`
  - `unknown`
- `candidate_pool_status`
  - `gold_present`
  - `gold_absent`
  - `no_candidate_pool`
  - `unknown`
- `recommended_fix_family`
  - `target_schema`
  - `equation_relation`
  - `unit_ledger`
  - `PAL_grounding`
  - `selector_structural`
  - `candidate_generation_diversity`
  - `richer_logging`
  - `unknown`

## Subset Recovery

The requested evaluation slices are built deterministically from the tracked
failure artifacts.

Exact slices:

- `diagnostic_30`
  - loaded from `docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl`
- `target_staged_15`
  - loaded from `docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl`

Approximate slices:

- `pal_still_failing_157`
  - filter `full_latest_method_failures.csv` to the default PAL method and `FULL` evidence completeness
  - sort by `case_id`, then `artifact_source`
  - trim to 157 if the corpus contains more rows
- `wrong_supported_consensus_97`
  - filter `gold_absent_subpattern_analysis_20260510.csv` to `external_contrast == Both wrong`
  - sort by `num_candidate_groups`, `diversity_bucket`, `case_id`
  - trim to 97 if the corpus contains more rows
- `direct_l1_anchor_potential_43`
  - filter `direct_l1_anchor_patch_effect_20260510.csv` to rows with truthy
    `anchor_matches_l1_max` or `external_l1_exact`
  - sort by anchor-match strength and `case_id`
  - trim to 43 if the corpus contains more rows

The approximate slices are documented as approximate because the raw source
counts do not match the nominal target counts exactly.

## Prompt Packet Contract

The rendered prompt may include only:

- `case_id`
- `question`
- `model_final_prediction`
- `candidate_answers`
- `candidate_answer_groups`
- `selector_metadata`
- `action_trace_summary`
- `pal_exec_summary`
- `structural_fields`
- `failure_audit_labels`
- `primary_subset`
- `subset_memberships`

The packet stays gold-free by default. If `--include-gold-for-labeling` is set,
the packet can include a reference answer, and the manifest/report must mark the
run as gold-assisted.

## Output Directory

Outputs are written under a timestamped directory:

- `outputs/failure_mechanism_multi_api_<TIMESTAMP>/`

Expected files:

- `manifest.json`
- `trace_packets.jsonl`
- `provider_requests_dry_run.jsonl`
- `raw_provider_labels.jsonl`
- `parsed_labels.jsonl`
- `agreement_summary.json`
- `label_frequency_summary.csv`
- `case_label_matrix.csv`
- `disagreement_cases.csv`
- `report.md`

## Cap Policy

Live mode is explicitly gated:

- `--allow-api`
- explicit `--providers`
- `--max-calls-total`

Provider caps are either:

- explicitly supplied per provider, or
- derived as an even split from `--max-calls-total`

The script should stop hard if the cap would be exceeded.

## Smoke Note

A tiny API smoke was run on 5 diagnostic cases across the 3 selected providers.

- Cohere produced 5 parsed labels.
- Cerebras failed all 5 calls with an API-layer 403 response.
- Fireworks failed all 5 calls with an API-layer 404 model-not-found response.

This is enough to confirm the Cohere path works on the small smoke slice, but it is not enough to draw any conclusion about the full diagnostic_30 or the larger 97/157 slices. Do not run the full 30-case or 97-case labeling until provider configs are fixed and a fresh smoke confirms readiness.

## Validation Plan

No-API validation should check:

- trace packet schema
- prompt rendering
- no-gold leakage
- dry-run behavior
- agreement aggregation
- label frequency outputs

This scaffold does not claim to beat any external baseline.

## Stop Criteria

Stop or pivot if any of the following happens:

- prompt packets leak reference-answer metadata by default
- subset selection is non-deterministic
- live mode ignores the cap policy
- agreement outputs do not separate consensus from disagreement cleanly
- the run requires runtime-default changes to function
