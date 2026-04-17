# Branch-value uncertainty canonical regime recovery commands (2026-04-17)

## Goal
Recover/regenerate canonical target root `regime_*` artifacts needed by:

- `scripts/run_branch_value_uncertainty_strict_validation_pass.py`

Required regime directories per target root:

- `regime_all_pairs_approx`
- `regime_promoted_exact_hard_region`
- `regime_penalized_marginal_defer`

## Commands run

```bash
# Enumerate tracked files quickly
rg --files | head -n 200

# Inspect strict validation harness requirements
sed -n '1,560p' scripts/run_branch_value_uncertainty_strict_validation_pass.py

# Search references to canonical replay roots and regime names
rg -n "near_tie_compare_bundle_exact_augmented_regimes_20260417|incomparability_exact_augmented_regimes_20260417|validation_penalized_regimes_nt_l0.20_t0.02_eu0.10_cap1.50_20260417|regime_promoted_exact_hard_region|regime_penalized_marginal_defer" outputs docs scripts -g '*.json' -g '*.md' -g '*.py'

# Verify candidate target roots and upstream roots exist
python - <<'PY'
from pathlib import Path
candidates=[
'outputs/branch_label_bruteforce_targets/near_tie_compare_bundle_exact_augmented_regimes_20260417',
'outputs/branch_label_bruteforce_targets/incomparability_exact_augmented_regimes_20260417',
'outputs/branch_label_bruteforce_targets/validation_penalized_regimes_nt_l0.20_t0.02_eu0.10_cap1.50_20260417',
'outputs/branch_label_bruteforce_targets/strict_validation_proxy_20260418',
'outputs/branch_label_bruteforce/near_tie_compare_bundle_20260417',
'outputs/branch_label_bruteforce/incomparability_base_20260417',
'outputs/branch_label_bruteforce/validation_penalized_20260417',
'outputs/branch_label_bruteforce_targets/incomparability_hard_region_exact_expansion_20260417',
'outputs/branch_label_bruteforce_targets/hard_region_exact_expansion_20260417',
'outputs/branch_label_bruteforce_targets/validation_penalized_hard_region_exact_expansion_20260417',
]
for p in candidates:
    print(f"{p}\t{'exists' if Path(p).exists() else 'missing'}")
PY

# Search for any compliant regime dirs in checkout
find . -name 'candidate_labels.jsonl' -o -name 'pairwise_labels.jsonl' -o -name 'state_summaries.jsonl'

# Re-run strict validation harness unchanged against strongest canonical candidate root
python scripts/run_branch_value_uncertainty_strict_validation_pass.py \
  --targets-root outputs/branch_label_bruteforce_targets/near_tie_compare_bundle_exact_augmented_regimes_20260417 \
  --run-id branch_value_uncertainty_strict_validation_canonical_recovery_probe_20260417 \
  --regimes all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer \
  --seeds 11,29,47 \
  --feature-set v3
```

## Assumptions

- Replaying strict validation unchanged requires full per-regime label artifacts (`candidate_labels.jsonl`, `pairwise_labels.jsonl`, `state_summaries.jsonl`) under each required `regime_*` directory.
- Canonical replay roots are the three documented in prior replay notes plus the last strict-validation proxy root.

## Caveats

- `outputs/*` is mostly ignored by git in this repository, so canonical target artifacts can be absent in clean checkouts even when docs reference them.
- No compliant regime label artifacts were present anywhere in this checkout during this recovery attempt.
