# PAL frontier structural-target replay v1 Result (2026-05-11)

## What Was Implemented

The offline replay experiment `pal_frontier_structural_target_replay_v1` adds a deterministic candidate-level structural feature layer and selector ablations over archived PAL failure artifacts.

Implemented / extended files:

- `experiments/selector_error_features.py`
- `experiments/gsm8k_structural_validate.py`
- `scripts/evaluate_gsm8k_structural_validator.py`
- `tests/test_gsm8k_structural_validate.py`

New candidate-level fields:

- `target_tuple`
- `entity_unit_ledger_proxy`
- `final_answer_role`
- `last_operation_family`
- `target_alignment_score`
- `intermediate_answer_penalty`
- `duplicate_wrong_signature`
- `structural_selector_score`

## Output Path

Fresh output bundle:

- `outputs/gsm8k_structural_validator_eval_20260507/pal_frontier_structural_target_replay_v1_20260511T222238Z/`

Key files:

- `replay_report.md`
- `replay_summary.json`
- `candidate_feature_rows.csv`
- `candidate_feature_rows.jsonl`

## Key Replay Numbers

From `replay_summary.json`:

- Primary slice loaded: `158`
- Primary replay-ready cases in current bundle: `58`
- Focus slice loaded: `100`
- Focus replay-ready cases in current bundle: `0`
- Secondary slice loaded: `55`
- Secondary replay-ready cases in current bundle: `30`
- Guardrail 30-case slice loaded: `30`
- Direct L1 strong-seed diagnostic loaded: `15`
- Target-audit reference loaded: `18`
- Candidate feature rows emitted: `185`

Selector ablation on the replay-ready primary slice:

- baseline selector accuracy: `0.0`
- combined structural selector accuracy: `0.13793103448275862`
- improvements vs baseline: `8`
- regressions vs baseline: `0`

## Interpretation

What this supports:

- Deterministic structural replay and logging.
- Candidate-level feature construction without gold leakage.
- Offline selector ablation analysis on replay-ready cases.

What this does not support:

- Runtime promotion.
- A claim that the focus wrong-supported-consensus slice is solved.
- A claim that the candidate-generation bottleneck is removed.
- A claim that this experiment beats `external_l1_max` overall.

If you need the exact per-slice breakdown, use the replay report and summary JSON rather than inferring from this note.
