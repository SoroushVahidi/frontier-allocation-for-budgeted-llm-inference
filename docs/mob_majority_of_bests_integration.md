# mob_majority_of_bests integration note (reviewer-defensible)

## Scope

This note defines the conservative integration level used in this repository for **Majority of the Bests (MoB)**.

## Upstream artifacts audited

- Repo: https://github.com/arakhsha/mob
- README: https://github.com/arakhsha/mob/blob/main/README.md
- Paper (OpenReview): https://openreview.net/forum?id=aEAbRPXV37
- NeurIPS poster page: https://neurips.cc/virtual/2025/poster/117285

Upstream workflow shape (as documented upstream):

1. load benchmark/model/reward datasets from packaged `data/*.jsonl.gz`,
2. run algorithm comparisons via `main.py` over BoN/SC/WBoN/MoB variants,
3. export aggregate and optional per-doc CSV outputs under `outputs/output_data/`,
4. optionally generate paper tables via `scripts/make_tables.py`.

## Integration decision in this repository

**Status: `runnable_adjacent` (verified import only).**

What is now unblocked:

- Strict import validator:
  - `scripts/verify_mob_import.py`
- Machine-readable status artifacts:
  - `outputs/external_baseline_completeness/mob_majority_of_bests_status.json`
  - `outputs/external_baseline_completeness/mob_majority_of_bests_status.md`

What is still intentionally not claimed:

- Direct in-repo reproduction of the full upstream benchmark + table-generation stack.
- Control-space equivalence between upstream MoB best-of-N selection and this repo's frontier/action-native controllers.

## Import contract (conservative)

Required package files:

- `metadata.json`
- `results.csv`

Validator requires:

- explicit workflow-stage declarations,
- benchmark/generator-model/reward-model/`num_samples` identity checks,
- algorithm coverage including `bon` and at least one MoB variant,
- numeric sanity checks on accuracy and trial counts,
- explicit `adjacent_only` comparability scope.

This protocol enables reviewer-auditable adjacent comparisons without overclaiming direct reproduction.

## Manuscript-safe wording

Safe now:

- "MoB is integrated via a validated adjacent import protocol."
- "Imported MoB outputs are used only in adjacent-comparison scope."

Not safe now:

- "MoB is fully reproduced in this repository."
- "MoB is directly control-equivalent to frontier/action-native controllers."
