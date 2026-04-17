# Allocation regret target experiment status (2026-04-17)

## Scope and bounded objective

Bounded canonical target-fidelity pass: add one consequence-aware target regime (`allocation_regret_target`) to the existing fixed-budget branch-allocation pipeline, compare against canonical baseline (`all_pairs`) under matched strict validation, and decide go/no-go without redesigning chooser/policy architecture.

## Insertion points inspected before implementation

Minimal-disruption insertion points identified and used:

1. `scripts/build_bruteforce_target_regimes.py`
   - Existing candidate-level and pair-level fields already expose `estimated_value_if_allocate_next`, `branch_vs_outside_gap`, `outside_option_value`, margin metadata, and supervision weight channel.
   - Clean insertion point: add a new pair strategy that computes regret fields and writes them to regime artifacts.
2. `scripts/build_exact_augmented_target_regimes.py`
   - Existing promoted exact regime construction supports adding parallel regimes with same row schema.
   - Clean insertion point: mirror allocation-regret annotation on promoted rows.
3. `experiments/bruteforce_branch_allocator.py`
   - Existing learning path already consumes per-row `supervision_reliability_weight` in `_pairwise_weight` with no downstream rule redesign.
   - Therefore we can route regret consequence signal through canonical weighting path.
4. `scripts/run_branch_value_uncertainty_strict_validation_pass.py`
   - Existing strict harness already emits accepted accuracy, coverage, defer rate, near-tie and adjacent-rank metrics by seed/regime.
   - New regimes can be passed via `--regimes` with no harness redesign.

## Exact target implemented

### `allocation_regret_target`

For pair `(i, j)` in state `s`:

- `value_i = estimated_value_if_allocate_next(i)`
- `value_j = estimated_value_if_allocate_next(j)`
- `best_value_in_state = max_k estimated_value_if_allocate_next(k)` over active branches in state
- `outside_option_value` from existing row/candidate fields
- `best_available_value = max(best_value_in_state, outside_option_value)`
- `regret_i = max(0, best_available_value - value_i)`
- `regret_j = max(0, best_available_value - value_j)`
- Direction label prefers lower regret branch (`regret_i <= regret_j` => label `i`)
- New consequence fields recorded per pair:
  - `allocation_regret_gap = |regret_i - regret_j|`
  - `allocation_regret_worse_pair = max(regret_i, regret_j)`
  - `allocation_regret_cost_weight = 1 + min(2, allocation_regret_worse_pair / |best_available_value|)`
- Training signal path: multiply canonical `supervision_reliability_weight` by `allocation_regret_cost_weight`.

### Ablation: `allocation_regret_target_no_outside`

Identical, except `best_available_value = best_value_in_state` (outside option removed).

## Why this is materially different from current target semantics

Current baseline supervision is immediate pair preference / margin over branch values. The new regime explicitly builds and persists **state-relative regret quantities** (branch shortfall to best available utility) and injects a **cost-of-being-wrong magnitude** (`allocation_regret_cost_weight`) into training. This adds consequence-aware semantics tied to global state utility reference, not only local pair gap.

## Commands run

```bash
python -m py_compile scripts/build_bruteforce_target_regimes.py scripts/build_exact_augmented_target_regimes.py scripts/run_branch_value_uncertainty_strict_validation_pass.py experiments/bruteforce_branch_allocator.py
python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417/regime_all_pairs_approx --output-dir outputs/branch_label_bruteforce_targets --run-id allocation_regret_target_20260417 --pair-strategies all_pairs,allocation_regret_target,allocation_regret_target_no_outside --near-tie-margin 0.03 --tie-abs-margin-threshold 0.03 --tie-relative-margin-threshold 0.15 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx
python scripts/run_branch_value_uncertainty_strict_validation_pass.py --targets-root outputs/branch_label_bruteforce_targets/allocation_regret_target_20260417 --run-id allocation_regret_target_strict_validation_20260417 --output-dir outputs/branch_label_bruteforce_learning --regimes all_pairs,allocation_regret_target,allocation_regret_target_no_outside --seeds 11,29,47 --feature-set v3
```

## Main metrics (matched strict evaluation)

Primary metric source: `full_method` in strict validation, aggregated over seeds `11,29,47`.

- Baseline `all_pairs`:
  - accepted accuracy: **0.9333**
  - coverage: **0.2698**
  - defer rate: **0.7302**
  - near-tie accepted accuracy: **0.0000**
  - adjacent-rank accepted accuracy: **0.8889**
- `allocation_regret_target`:
  - accepted accuracy: **0.9333** (delta **+0.0000**)
  - coverage: **0.2698** (delta **+0.0000**)
  - defer rate: **0.7302**
  - near-tie accepted accuracy: **0.0000** (delta **+0.0000**)
  - adjacent-rank accepted accuracy: **0.8889** (delta **+0.0000**)
- `allocation_regret_target_no_outside`:
  - accepted accuracy: **0.9333** (delta **+0.0000**)
  - coverage: **0.2698** (delta **+0.0000**)
  - defer rate: **0.7302**
  - near-tie accepted accuracy: **0.0000** (delta **+0.0000**)
  - adjacent-rank accepted accuracy: **0.8889** (delta **+0.0000**)

Per-seed summaries are written to:
- `outputs/branch_label_bruteforce_learning/allocation_regret_target_strict_validation_20260417/allocation_regret_per_seed_summary.json`

## Target/regret diagnostics

Regret-specific diagnostics (new regime summaries):

- `allocation_regret_target`:
  - mean regret gap: **0.0905**
  - near-tie mean regret gap: **0.0122**
  - non-near-tie mean regret gap: **0.1201**
  - mean worse-branch regret: **0.1116**
  - mean regret cost weight: **1.1363**

Outside-option ablation produced numerically identical regret diagnostics on this artifact slice (outside option did not alter best-available reference in these rows).

## Assumptions and caveats

- Reused available canonical artifact root from prior bounded pass: `target_semantics_upstream_20260417/regime_all_pairs_approx`.
- No chooser/policy redesign; only target regime construction and canonical weight channel usage were changed.
- Strict-validation operating point is defer-heavy and low-coverage; near-tie accepted set is sparse and should be interpreted cautiously.
- No evidence from this bounded run that outside-option inclusion materially changed labels/weights relative to no-outside ablation on this data slice.

## Hard conclusion (go / no-go)

**Conclusion: DROP / no-go for continuation in current form.**

Reasoning:

1. The consequence-aware allocation regret target is cleaner semantically, but produced **no measurable improvement** on accepted accuracy, near-tie accepted accuracy, adjacent-rank accepted accuracy, coverage, or defer rate versus canonical baseline in matched strict evaluation.
2. The no-outside ablation was also unchanged, indicating this implementation’s added regret semantics did not translate into effective discriminative gain on hard close-branch behavior.
3. Most likely failure source is not just this regret formulation itself, but limited effective fidelity/variation in available value semantics on this artifact slice (and potentially invariance of induced pair direction under current labels/features).

Given the stated success bar (credible hard-slice improvement without unacceptable deterioration), this pass does **not** meet continuation criteria.
