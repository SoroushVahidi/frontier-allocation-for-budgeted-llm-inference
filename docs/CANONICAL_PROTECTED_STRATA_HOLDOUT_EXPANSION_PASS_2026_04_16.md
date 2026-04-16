# Canonical protected-strata holdout expansion pass (2026-04-16)

## Objective
Run one **bounded holdout-support expansion** pass that increases support in high-value protected strata (especially exact-promoted/near-boundary and low-budget/extreme-low-budget boundary slices) while keeping:
- branch-priority next-step allocation task fixed,
- method family fixed (anchor, broad PRM blend, aligned PRM blend, boundary PRM variant),
- external PRM artifact path fixed at `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`,
- boundary-sensitive protocol fixed at `scripts/run_canonical_boundary_sensitive_evaluation.py`.

## Chosen bounded strategy
This pass adds a single narrow strategy: **split-seed selection for protected-strata support**, implemented in:
- `scripts/run_protected_strata_holdout_expansion.py`

The strategy is:
1. Keep corpus content fixed.
2. Scan split seeds over a bounded range.
3. Score candidate seeds by protected-strata support emphasis:
   - exact-promoted / near-boundary
   - low-budget / near-boundary
   - extreme-low-budget / boundary-eligible
4. Select one seed.
5. Materialize a split-frozen corpus and write a reusable manifest-backed held-out definition with per-row protected-strata assignments.

## Baseline protected-strata deficits (from latest boundary-sensitive summary)
Baseline counts taken from:
- `docs/canonical_external_supervision_prm800k_boundary_sensitive_evaluation_pass_2026_04_16_summary.json`

### Support snapshot
- total test pairs: 30
- total top-1 states: 9
- near-tie: 12
- adjacent-rank: 18
- small-margin: 22
- exact-promoted: 2
- exact-only: 2
- approx-only: 28
- low-budget (<=2): 8
- extreme low-budget (budget=1): 2
- boundary-eligible: 4

### Required protected strata
- exact-promoted / near-boundary: 1
- exact-promoted / non-boundary: 1
- approximate / near-boundary: 3
- approximate / non-boundary: 25
- low-budget / near-boundary: 1
- low-budget / non-boundary: 7
- extreme low-budget / boundary-eligible: not explicitly reported in prior summary (implied sparse given `budget=1` total of 2 and boundary-eligible total of 4).

### Underpowered strata diagnosis
Using a practical minimum support threshold of `n>=5`, currently underpowered:
- exact-promoted / near-boundary
- exact-promoted / non-boundary
- approximate / near-boundary
- low-budget / near-boundary
- likely extreme low-budget / boundary-eligible

## Commands run in this pass
```bash
python -m py_compile scripts/run_protected_strata_holdout_expansion.py
python scripts/run_protected_strata_holdout_expansion.py --help | head -n 60
python scripts/run_protected_strata_holdout_expansion.py \
  --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 \
  --output-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_protected_strata_holdout_v1 \
  --output-manifest-json outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_manifest.json \
  --output-holdout-jsonl outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_holdout.jsonl \
  --output-audit-json outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_audit.json \
  --baseline-seed 17 --seed-min 1 --seed-max 128 \
  --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0
```

## Execution status
The corpus path required for this pass is not present in this checkout, so the expansion and downstream boundary-sensitive re-evaluation could not be executed in this environment.

Observed blocker:
- `FileNotFoundError: canonical corpus rows/ missing required jsonl files`

## Files added/modified
- Added: `scripts/run_protected_strata_holdout_expansion.py`
- Modified: `scripts/README.md`
- Added: `docs/CANONICAL_PROTECTED_STRATA_HOLDOUT_EXPANSION_PASS_2026_04_16.md`
- Added: `docs/canonical_protected_strata_holdout_expansion_pass_2026_04_16_summary.json`

## Reproducible outputs (when corpus exists)
The new script writes:
- split-frozen expanded corpus directory
- frozen protected holdout JSONL with:
  - pivot/group keys,
  - stratum assignments,
  - exact/approx provenance,
  - exact-promoted flag,
  - remaining-budget buckets,
  - boundary-eligibility indicators
- machine-readable audit JSON (baseline vs selected seed counts + full seed scan)
- pass manifest JSON

## Conservative interpretation
- This change implements the requested **single bounded support-expansion mechanism** without model-family changes.
- The scientific question (whether broader protected-strata support reveals broad-vs-aligned separation) remains unresolved until the canonical corpus artifacts are available and the pass is re-run end-to-end.
- Recommendation on Math-Shepherd remains: **wait** pending successful execution of this protected-strata expansion and paired uncertainty rerun.
