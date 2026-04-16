# Frontier target construction pipeline

This note documents the practical workflow for constructing frontier supervision targets for stop-vs-act and branch-pair ranking experiments.

## Workflow overview

1. **Build deterministic pilot state manifest**
   - Script: `scripts/build_oracle_label_pilot_state_manifest.py`.
   - Purpose: choose a stratified, deterministic subset of state snapshots from the source stop-vs-act simulator.
   - Main guarantees:
     - deterministic dedupe,
     - deterministic `state_id` assignment,
     - deterministic per-budget/per-stratum selection ordering.

2. **(Optional) shard the manifest for distributed runs**
   - Script: `scripts/oracle_label_pilot_sharding.py split`.
   - Purpose: split one manifest into deterministic shards and emit a split manifest with provenance.

3. **Generate oracle-ish stop-vs-act labels**
   - Prototype path: `scripts/run_oracle_label_generator_prototype.py` (small runs).
   - Heavy path: `scripts/run_oracle_label_generator_heavy.py` (resume/progress/error-aware, shard friendly).
   - Core target:
     - estimate `q_act` and `q_stop` via paired local rollouts,
     - compute `oracle_action_gap = q_act - q_stop`,
     - set `oracle_label_act = 1` iff gap is positive.

4. **Validate and merge shard outputs (if sharded)**
   - Validation script: `scripts/validate_oracle_label_pilot_outputs.py`.
   - Merge script: `scripts/oracle_label_pilot_sharding.py merge`.
   - Merge preserves original source-manifest ordering by `state_id` order from source rows.

5. **Downstream dataset construction/training**
   - Distillation preprocessing: `scripts/build_stop_vs_act_oracle_distillation_dataset.py`.
   - Matched random controls: `scripts/build_random_matched_coverage_oracle_distillation_dataset.py`.
   - Student training/eval: `scripts/train_oracle_distilled_stop_vs_act_student.py`.

## Key assumptions

- Local rollouts are a **bounded approximation** of continuation value, not a full global oracle.
- Paired ACT-vs-STOP rollout seeds reduce variance from RNG mismatch but do not remove model mismatch or simulator bias.
- Replay-based state reconstruction assumes source config compatibility (seed, budget, simulator settings).
- Label quality depends on rollout count/horizon/depth; low budgets may underresolve hard near-tie states.

## Caveats and limitations

- **Not exact global optimality labels**:
  - these are constrained local counterfactual estimates.
- **Resume semantics**:
  - heavy generator treats existing `state_id` rows as complete and skips them when `--resume` is set.
  - this assumes prior rows are valid and contract-compliant.
- **Partial failure handling**:
  - heavy path can continue on row-level errors (`--continue-on-state-error`) and emit partial outputs for debugging (`--allow-partial-output`), but those runs are not clean final artifacts.
- **Near-tie sensitivity**:
  - around zero-gap states, uncertainty is expected and calibration is required.
- **Manifest/config coupling**:
  - mismatched split manifest, state manifest, or source reconstruction settings should be treated as a hard failure.

## Recommended operational checks

- Verify uniqueness of `state_id` and expected state count before generation.
- Store/track manifest hashes (`state_manifest_sha256`, split-manifest hash) for provenance.
- Check `rows_written == rows_expected_from_manifest` and `complete == true` in heavy run manifest.
- Monitor `state_errors` and reject partial outputs for canonical reporting.
