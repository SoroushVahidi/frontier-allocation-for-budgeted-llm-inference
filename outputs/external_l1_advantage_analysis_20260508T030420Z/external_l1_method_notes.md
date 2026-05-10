# external_l1_max Method Notes

## Where Defined
- Method registry alias is in `scripts/run_cohere_real_model_cost_normalized_validation.py` (`METHODS` maps `external_l1_max` runtime).
- Runtime strategy is constructed in `experiments/frontier_matrix_core.py` via `L1LengthControlController` when `include_external_l1_baseline=True`.
- Controller implementation is in `experiments/controllers.py` (`class L1LengthControlController`).

## High-Level Behavior
- `external_l1_max` is an inference-only length-control baseline (not RL training reproduction).
- It appends prompt style + length instruction (`Think for maximum N tokens.`), runs single-branch iterative expansion, and returns the branch prediction.
- It tracks metadata like token-budget instruction, control mode, and estimated generated token count.

## Calls / Budget vs Integrated Method
- In paired artifacts, `external_l1_max` often uses more logical API calls than PAL baseline on some cases.
- Mechanistically, allowed actions are bounded by `min(max_actions_per_problem, round(token_budget / token_per_action))` in `L1LengthControlController`.
- Integrated method path includes structural commit + optional targeted retry; external L1 path is a distinct budget-conditioned baseline path.

## Potentially Adaptable Prompt/Selection Tricks
- Explicit length-control instruction may improve decomposition completeness on some cases.
- Prompt style is configurable (`prompt_style`) and could be compared under fair, gold-free ablation.
- Any adaptation should remain inference-only and avoid hidden/training-dependent claims.

## Caveats
- Available artifacts do not expose full raw external reasoning traces; only compact node/answer summaries are present.
- Similar final answers can arise from different internal traces, so inferred mechanism remains probabilistic.
- Fair comparison should preserve equalized budget accounting and no gold-conditioned routing.
