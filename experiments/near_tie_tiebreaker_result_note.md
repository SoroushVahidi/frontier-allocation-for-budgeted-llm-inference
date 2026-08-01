# Near-tie two-stage tie-breaker result note (new-paper, 2026-04-14)

This pass stays fully on the **new-paper track**.
All artifacts are text-only (csv/json/jsonl/md), with bounded synthetic/simulator-backed runs.

## Quick audit of prior near-tie outputs

Audited prior near-tie pass from:
- `scripts/run_new_paper_near_tie_pair_pipeline.py`
- `scripts/run_new_paper_near_tie_improvement.py`
- `experiments/near_tie_improvement_result_note.md`

Prior findings (oversampling attempt):
- Near-tie/hard pairs were very common (~70%+ in sampled pairwise data).
- Hard-pair oversampling helped near-tie slice slightly.
- But it hurt overall controller-level accuracy.

Those observations motivated a selective two-stage path instead of global oversampling.

## New run roots

- Main run: `outputs/new_paper/near_tie_tiebreaker/20260414T174315Z/`
- Near-tie pair artifacts: `outputs/new_paper/near_tie_pairs/20260414T174315Z/`

## Method implemented

Two-stage selective scorer:
1. **Stage 1 (baseline)**: existing BT scalar scorer ranks branches globally.
2. **Stage 2 (tie-breaker)**: only if top-2 Stage-1 scores are within a small margin (`near_tie_margin=0.06`), invoke a lightweight logistic tie-breaker trained only on near-tie train pairs.

Reference variants included:
- Baseline BT
- Global near-tie oversampling BT (previous style)
- Two-stage selective tie-breaker (new)
- Oracle-style BT reference strategy (same harness reference row)

## Core outputs

- `method_metrics.csv`
- `near_tie_tiebreaker_comparison.csv`
- `failure_slice_summary.csv`
- `run_manifest.json`
- `interpretation.md`

All under: `outputs/new_paper/near_tie_tiebreaker/20260414T174315Z/`.

## Explicit answers

### 1) Does a selective tie-breaker work better than global oversampling?
**Yes in this bounded run** at controller level.
- Oversample vs baseline controller delta: `+0.0333`
- Two-stage vs baseline controller delta: `+0.1000`

### 2) Does it improve the near-tie slice?
**No in this run (pairwise near-tie slice)**.
- Near-tie test pair delta vs baseline:
  - Oversample: `-0.0213`
  - Two-stage: `-0.0081` (less harmful than oversample, but still negative)

### 3) Does it avoid hurting overall controller accuracy?
**Yes in this run**, unlike the previous oversampling failure note.
- Two-stage improved overall controller accuracy by `+0.1000` vs baseline.

### 4) What features matter most inside the tie-breaker?
Top absolute-weight features were mostly trajectory-delta and late-node structure:
- `diff::edge_1_score_delta`
- `diff::node_3_distance_to_terminal_est`
- `abs_diff::node_3_score`
- `abs_diff::parent_relative_score`
- `diff::edge_2_score_delta`

### 5) Is this now a better lightweight improvement than previous oversampling?
**Tentatively yes as a next lightweight branch-scoring direction**, because it improves overall controller behavior while being selective and cheap.

But be conservative: near-tie pair-slice accuracy still did not improve vs baseline in this particular run, so this should remain an iterative branch (threshold/features calibration) rather than immediate default.

## Conservative decision

- Keep the two-stage tie-breaker branch for follow-up calibration.
- Do **not** yet declare near-tie slice resolved.
- Continue using the near-tie diagnostics pipeline as the primary guardrail.
