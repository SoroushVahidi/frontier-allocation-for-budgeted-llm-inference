# Canonical corpus recovery + comparator-boundary execution pass (PRM800K) — 2026-04-16

## Objective

Complete the already-implemented comparator-boundary PRM800K evaluation by:
1) recovering missing canonical corpus artifacts in a provenance-safe way,
2) validating corpus integrity,
3) running matched anchor vs broad vs aligned vs boundary evaluation.

No new method was introduced in this pass.

## 1) Missing-corpus diagnosis (evidence-based)

### What was missing
The workspace was missing both required artifact trees:
- `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1`
- `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`

### Why missing
The repository `.gitignore` ignores `outputs/*` (except selected allowlisted folders), so canonical corpus and external corpus artifacts are not tracked by git and are often absent in fresh workspaces.

Evidence:
- `git check-ignore -v outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1/rows/candidate_rows.jsonl`
- `git check-ignore -v outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416/rows/candidate_rows.jsonl`

Both resolve to `.gitignore: outputs/*`.

Diagnosis conclusion:
- missing due to **artifact non-materialization in this environment + outputs ignore policy**, not because of a code regression in the comparator-boundary implementation.

## 2) Recovery path used

Preferred search-first checks found no prebuilt canonical row files anywhere in this workspace.

Because exact original artifact files were unavailable, I performed a faithful in-workspace rebuild using the repository generators and preserved the canonical identity path:

- rebuilt canonical corpus at:
  - `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1`
- rebuilt external PRM artifact at:
  - `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`

Important provenance caveat:
- exact byte-identical recovery of the originally produced 2026-04-16 corpus is not provable in this workspace because original output artifacts were absent.
- this run is a **faithful protocol rebuild** using available scripts, recorded path identities, and deterministic configuration where possible.

## 3) Exact commands run

```bash
# Diagnose absence and search
find outputs -maxdepth 5 -type f
find . -maxdepth 6 -type f \( -name 'candidate_rows.jsonl' -o -name 'pairwise_rows.jsonl' -o -name 'outside_option_rows.jsonl' -o -name 'manifest.json' \)
git check-ignore -v outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1/rows/candidate_rows.jsonl outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416/rows/candidate_rows.jsonl

# Rebuild internal source runs (approx + exact, two datasets)
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_gsm8k_approx_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 17 --max-frontier-states 24 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_math500_approx_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 17 --max-frontier-states 24 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_gsm8k_exact_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 29 --max-frontier-states 8 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 2 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 2
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_math500_exact_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 29 --max-frontier-states 8 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 2 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 2

# Merge and build canonical corpus at canonical path identity
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/recover_run_ids.txt --output-dir outputs/branch_label_bruteforce_merged --run-id recover_multi_dataset_merged_20260416_v1 --near-tie-margin 0.03
python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/recover_multi_dataset_merged_20260416_v1 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_v1 --split-seed 17 --train-ratio 0.8 --val-ratio 0.1 --near-tie-margin 0.03 --small-margin-threshold 0.08

# Rebuild external PRM corpus at expected canonical path
python scripts/build_external_prm_mathshepherd_apps_corpus.py --output-root outputs/branch_learning_corpora_external --run-id external_prm_mathshepherd_apps_20260416 --max-rows-per-dataset 128

# Validate canonical corpus integrity
python - <<'PY'
import json,hashlib
from pathlib import Path
root=Path('outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1')
required=['rows/candidate_rows.jsonl','rows/pairwise_rows.jsonl','rows/outside_option_rows.jsonl','manifest.json','summaries/corpus_summary.json','summaries/slice_stats.json','meta/checksums.json','meta/schema.json','meta/source_artifacts.json']
missing=[p for p in required if not (root/p).exists()]
assert not missing, missing
checks=json.loads((root/'meta/checksums.json').read_text())
for key,rel in [('candidate_rows_sha256','rows/candidate_rows.jsonl'),('pairwise_rows_sha256','rows/pairwise_rows.jsonl'),('outside_option_rows_sha256','rows/outside_option_rows.jsonl')]:
    h=hashlib.sha256((root/rel).read_bytes()).hexdigest()
    assert h==checks.get(key), (key,h,checks.get(key))
print('ok')
PY

# Run matched evaluation: aligned transfer + boundary intervention
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1 --output-root outputs/canonical_branch_learning_pass --run-id real_canonical_learning_20260416_external_prm800k_transfer_alignment_recovered --seed 17 --near-tie-margin 0.03 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_uncertainty_gated_blend --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1 --output-root outputs/canonical_branch_learning_pass --run-id real_canonical_learning_20260416_external_prm800k_comparator_boundary_recovered --seed 17 --near-tie-margin 0.03 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_comparator_boundary_tiebreak --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02
```

## 4) Corpus validation summary

Recovered/rebuilt canonical corpus path:
- `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1`

Validated present:
- `rows/candidate_rows.jsonl` (176 rows)
- `rows/pairwise_rows.jsonl` (216 rows)
- `rows/outside_option_rows.jsonl` (176 rows)
- `manifest.json`
- `summaries/corpus_summary.json`
- `summaries/slice_stats.json`
- `meta/checksums.json` (hashes match all three row files)
- `meta/schema.json`
- `meta/source_artifacts.json`

External PRM artifact rebuilt and present at expected path:
- `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`

## 5) Full anchor vs broad vs aligned vs boundary results

Models:
- Anchor: `reweighted::pointwise`
- Broad: `external::prm800k_pointwise_blend_from_reweighted_pointwise`
- Aligned: `external::prm800k_uncertainty_gated_blend_from_reweighted_pointwise`
- Boundary: `external::prm800k_comparator_boundary_tiebreak_from_reweighted_pointwise`

### Aggregate

- Pairwise accuracy (test):
  - anchor: **0.5000** (n=18)
  - broad: **0.5556** (n=18)
  - aligned: **0.5556** (n=18)
  - boundary: **0.5556** (n=18)
- Top-1 accuracy (test):
  - anchor: **0.0000**
  - broad: **0.2500**
  - aligned: **0.2500**
  - boundary: **0.0000**

### Hard slices

- near-tie: n=2; all four methods 1.0000
- adjacent-rank: n=0 (not measurable)
- small-margin: n=11; anchor/broad/aligned/boundary all 0.4545
- exact-promoted: n=0 (not measurable)
- exact-only: n=0 (not measurable)
- approx-only: n=0 (not measurable)

### Dataset slices (pairwise acc)

- HuggingFaceH4/MATH-500 (n=6):
  - anchor 0.5000; broad/aligned/boundary 0.3333
- openai/gsm8k (n=12):
  - anchor 0.5000; broad/aligned/boundary 0.6667

### Budget slices (pairwise acc)

- budget=2 (n=6): anchor 0.5000; broad/aligned/boundary 0.3333
- budget=3 (n=6): anchor 0.6667; broad/aligned/boundary 0.6667
- budget=4 (n=6): anchor 0.3333; broad/aligned/boundary 0.6667

## 6) Comparator-boundary diagnostics

Boundary-region movement did occur:
- eligible boundary pairs: 6 / 18 (33.33%)
- eligible pairs where external disagreed with internal: 3
- changed pair decisions: 3 / 18 (16.67%)
- changed pair decisions helpful: 2
- changed pair decisions harmful: 1
- changed pair decisions neutral: 0
- changed hard-slice pairs: 2
- changed by dataset: MATH-500=1, GSM8K=2
- changed by budget: b2=1, b4=2

Top-1 boundary movement:
- top1 changed states: 0 / 4
- helpful/harmful top1 changes: 0 / 0

## 7) Interpretation (conservative)

1. **Recovery succeeded**: canonical/internal + external artifacts are now materialized and validated in this workspace.
2. **Comparator-boundary movement is real**: boundary-eligible pair flips occurred (3 flips), including 2 directionally helpful flips.
3. **Bottleneck not solved**: despite flips, boundary method did not outperform broad/aligned on aggregate pairwise accuracy and did not improve top-1 here.
4. **Math-Shepherd still waits**: this pass completes the missing execution step, but evidence remains mixed and small-sample on key hard slices.

## 8) Files added/modified in repo for this pass

- `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_COMPARATOR_BOUNDARY_RECOVERY_EXECUTION_PASS_2026_04_16.md`
- `docs/canonical_external_supervision_prm800k_comparator_boundary_recovery_execution_pass_2026_04_16_summary.json`

(Recovered corpora/eval outputs were produced under `outputs/` and are intentionally not tracked by git per repository policy.)

## 9) Recommendation for next pass

Keep method family fixed and run one more strictly matched boundary calibration sweep (margin/uncertainty thresholds only) on a larger recovered canonical corpus to test whether helpful flip-rate can be increased without top-1 regressions before any Math-Shepherd expansion.
