# cascade_routing integration note (reviewer-defensible)

## Scope

This note defines the conservative integration level used in this repository for **Cascade Routing** (*A Unified Approach to Routing and Cascading for LLMs*).

## Upstream artifacts audited

- Repo: https://github.com/eth-sri/cascade-routing
- README: https://github.com/eth-sri/cascade-routing/blob/main/README.md
- Paper (ICML 2025 / PMLR): https://proceedings.mlr.press/v267/dekoninck25a.html
- OpenReview: https://openreview.net/forum?id=rgDwRdMwoS
- ETH SRI publication page: https://www.sri.inf.ethz.ch/publications/dekoninck2024cascaderouting

Upstream workflow shape (as documented upstream):

1. query generation / model outputs collection (or downloading provided raw data),
2. dataset preprocessing (`scripts/preprocess.py`),
3. routing/cascading experiment runs (`scripts/main.sh`),
4. postprocessing in notebook form (`notebooks/postprocess.ipynb`).

## Integration decision in this repository

**Status: `runnable_adjacent` (verified import only).**

What is now unblocked:

- Strict import validator:
  - `scripts/verify_cascade_routing_import.py`
- Machine-readable status artifacts:
  - `outputs/external_baseline_completeness/cascade_routing_status.json`
  - `outputs/external_baseline_completeness/cascade_routing_status.md`

What is still intentionally not claimed:

- Direct in-repo reproduction of the full upstream generation + benchmark + postprocessing stack.
- Control-space equivalence between upstream routing/cascading and this repo's frontier/action-native controllers.

## Import contract (conservative)

Required package files:

- `metadata.json`
- `results.csv`

Validator requires:

- explicit upstream workflow-stage declarations,
- strategy coverage including `routing`, `cascading`, and `cascade_routing`,
- dataset/split consistency,
- numeric sanity checks for cost/quality metrics,
- explicit `adjacent_only` comparability scope.

This protocol enables reviewer-auditable adjacent comparisons without overclaiming direct reproduction.

## Manuscript-safe wording

Safe now:

- "Cascade Routing is integrated via a validated adjacent import protocol."
- "Imported Cascade Routing outputs are used only in adjacent-comparison scope."

Not safe now:

- "Cascade Routing is fully reproduced in this repository."
- "Cascade Routing is directly control-equivalent to frontier/action-native controllers."
