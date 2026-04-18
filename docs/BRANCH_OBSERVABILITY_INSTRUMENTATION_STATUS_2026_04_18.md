# Branch observability instrumentation status (2026-04-18)

## Scope

This pass adds forward-looking branch-level observability to the frontier/target-construction pipeline so future failure diagnosis can directly recover branch-semantic artifacts (when present in source traces), instead of relying only on proxy signals.

## Insertion-point summary

Primary insertion point selected:

1. `experiments/frontier_target_construction.py`
   - `_collect_frontier_states_from_trace_rows`: now captures branch-level free-text fields (`branch_text_raw`, `branch_reasoning_text_raw`, `branch_final_answer_text_raw`) and preserves `generation_metadata`, plus dataset/example provenance fields when provided by trace rows.
   - `run_frontier_target_construction`: now assembles branch-trace observability records at state/branch granularity and writes a first-class branch-observability bundle under `outputs/branch_observability/<run_id>/`.

Reason this point was chosen:
- It is the earliest reliable place where replayed branch material from trace JSONL rows is available before downstream target construction drops semantic text detail.
- It already owns state materialization and manifest writing, making provenance + recoverability accounting minimally invasive and auditable.

## New branch-observability artifacts

Reusable writer:
- `experiments/branch_observability.py`

Per-branch fields now preserved in `branch_trace_records.jsonl`:
- `dataset_name`
- `example_id`
- `state_id`
- `branch_id`
- `branch_text_raw`
- `branch_reasoning_text_raw`
- `branch_final_answer_text_raw`
- `branch_final_answer_normalized`
- `answer_normalization_metadata`:
  - `normalization_success`
  - `normalization_method`
  - `normalization_confidence`
  - `normalization_failure_reason`
  - `ground_truth_answer_normalized`
  - `matches_ground_truth` (if ground truth exists)
- `extracted_numbers` (numeric tokens from reasoning/branch text)
- `branch_role_summary`
- `generation_metadata`
- `provenance_source` (explicit source keys + state provenance)
- `recoverability_flags` (machine-readable recoverable/unavailable reason per field)

Bundle layout now produced:
- `outputs/branch_observability/<run_id>/manifest.json`
- `outputs/branch_observability/<run_id>/branch_trace_records.jsonl`
- `outputs/branch_observability/<run_id>/per_state_index.json`
- `outputs/branch_observability/<run_id>/recoverability_summary.json`
- `outputs/branch_observability/<run_id>/commands_assumptions_caveats.md`

## Capture points in pipeline

- **State materialization from trace JSONL**:
  branch-level semantic fields are copied into `FrontierState.active_branches` snapshots if present.
- **Bundle emission**:
  after target construction rows are created, all active branches across captured states are written as branch observability records with explicit provenance and recoverability status.

## Bounded smoke run

Smoke script added:
- `scripts/run_branch_observability_smoke.py`

Command run:
- `python scripts/run_branch_observability_smoke.py`

Smoke run writes:
- Frontier package:
  - `outputs/frontier_target_construction/branch_observability_smoke_20260418T013025Z/`
- Branch observability bundle:
  - `outputs/branch_observability/branch_observability_smoke_20260418T013025Z/`

Smoke result:
- Recoverable branch text records: 2/2
- Recoverable branch reasoning records: 2/2
- Recoverable branch final-answer text records: 2/2
- Recoverable normalized answers: 2/2

## What remains unrecoverable

- Historical runs without stored branch free-text remain unrecoverable at branch-semantic level; this pass is forward-looking and does not reconstruct missing historical text.
- Synthetic simulator path does not generate true free-text reasoning traces; those fields remain null with explicit reasons unless trace inputs provide them.

## Caveats

- Normalization currently uses `extract_final_answer` heuristic.
- Extraction confidence is method-based (currently deterministic confidence for successful heuristic extraction), not model-calibrated confidence.
- “Matches ground truth” is only evaluated when a ground-truth answer is provided in trace source rows.

## Hard conclusion

For future instrumentation-enabled runs that carry branch text/final-answer fields in trace sources, branch-level reasoning text and branch final answers are now directly recoverable with explicit state/branch/example/dataset provenance, normalization metadata, and recoverability accounting.
