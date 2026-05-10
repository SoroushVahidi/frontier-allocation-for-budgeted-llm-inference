# Exact-Case Replay Fix for Failure-Recovery Diagnostics (2026-05-10)

## Executive summary

This change fixes the no-API replay contract needed before any future Cohere rerun of the 30-case diverse-anchor failure-recovery diagnostic. The previous live run completed under cap, but it was invalidated because the selected failure artifact IDs were passed through a shuffled `openai/gsm8k` pilot loader. In that loader, IDs such as `openai_gsm8k_6` are sample-local IDs after shuffling, not stable source-artifact IDs. As a result, the runner loaded different questions/golds than the intended failure artifacts.

No paid/API calls were made for this fix.

## Root cause of the invalidated live run

The invalidated run selected 30 failure artifact IDs from latest tracked failure artifacts, then supplied those IDs to `scripts/run_cohere_real_model_cost_normalized_validation.py` through the allowlist path. The runner still called the shuffled Hugging Face pilot loader (`load_pilot_examples(...)`), which creates `example_id` values after selecting a shuffled subset. Therefore an allowlisted ID could exist in the runner output while referring to a different shuffled example than the failure artifact.

Concrete prior example: the selected artifact case `openai_gsm8k_6` had artifact gold `310`, but the runner-loaded case had gold `32`. That made all raw live metrics unusable for the intended failure-recovery question.

## Files/functions changed

### `scripts/run_cohere_real_model_cost_normalized_validation.py`

Added exact replay support:

- CLI flags:
  - `--exact-cases-jsonl`
  - `--validate-exact-cases-only`
  - `--expected-exact-case-count`
- Exact-case helper functions:
  - `_normalize_exact_question(...)`
  - `load_exact_case_rows(...)`
  - `exact_case_rows_to_examples(...)`
  - `validate_exact_case_examples(...)`
  - `resolve_examples_for_dataset(...)`
  - `validate_exact_cases_only(...)`
- Runtime path: when `--exact-cases-jsonl` is supplied, examples are built directly from that JSONL as `PilotExample` rows and the shuffled dataset loader is bypassed.
- Safety path: exact cases are validated before API execution; mismatches raise before model calls.
- The diverse-anchor method ID remains registered in `METHODS` for no-API method-resolution checks and future runs.

### `scripts/build_failure_recovery_exact_cases_20260510.py`

Added a reproducible no-API artifact builder for the intended 30 failure-recovery cases. It joins the invalidated run selection with available source artifacts and writes the exact replay JSONL.

### `tests/test_exact_case_replay_20260510.py`

Added no-API tests for deterministic exact-case loading, mismatch detection, valid-case validation, selected-case count preservation, shuffled-loader bypass, and method-resolution for both direct-hybrid and diverse-anchor methods.

## Exact-case JSONL path

```text
docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl
```

The file contains 30 rows. Each row includes:

- `example_id`
- `question` / `problem_text`
- `gold_answer_canonical`
- `failure_category`
- `failure_domain`
- `source_artifact_path`
- latest-method prediction/failure metadata when available

## Validation command before future API use

Run this exact no-API validation command before any future Cohere rerun:

```bash
python3 scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp exact_case_validation_20260510 \
  --providers cohere \
  --datasets openai/gsm8k \
  --budgets 4 \
  --seeds 11 \
  --methods direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid,direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor \
  --exact-cases-jsonl docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl \
  --expected-exact-case-count 30 \
  --validate-exact-cases-only
```

Observed result in this change:

```text
exact_case_count=30 mismatch_count=0 api_calls_made=0 shuffled_loader_used=false
```

## No-API test results

Commands run while preparing this fix:

```bash
python3 -m pytest -q tests/test_exact_case_replay_20260510.py
```

Result: `6 passed`.

The required broader checks were also run before commit; see the PR/final response for exact pass/fail status.

## Why this prevents another wrong-case API spend

Future exact-case diagnostics can pass `--exact-cases-jsonl`. In that mode, the runner constructs examples directly from the JSONL and does not call the shuffled Hugging Face pilot loader. The validation mode checks count, IDs, normalized question text, canonical gold answers, and no-API method resolvability. If any mismatch exists, the command exits nonzero before provider readiness checks or model execution.

This means the next paid run can be gated by an explicit no-API validation step that proves the runner will use the exact intended failure cases.

## Remaining caveats

- The exact JSONL is a replay artifact assembled from available project artifacts. It should remain the source of truth for this specific 30-case diagnostic.
- Some source artifacts have inconsistent historical method metadata; the exact replay file preserves available latest-method prediction/failure fields but the next live run should score recovery only from the paired rerun outputs.
- This does not rerun Cohere and does not answer the recovery question. It only fixes the infrastructure needed to rerun safely.
- A valid targeted failure-recovery run still cannot prove broad accuracy or superiority over `external_l1_max`; it can only measure recovery on selected prior failures.

## Recommended next Cohere rerun plan (do not run without explicit approval)

After the no-API validation command above passes, rerun the original paired 30-case Cohere diagnostic using exact-case mode:

```bash
python3 scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp cohere_exact_failure_recovery_30case_YYYYMMDDTHHMMSSZ \
  --providers cohere \
  --datasets openai/gsm8k \
  --budgets 4 \
  --seeds 11 \
  --methods direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid,direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor \
  --target-scored-per-slice 30 \
  --max-examples 30 \
  --exact-cases-jsonl docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl \
  --max-total-api-calls 300
```

Recommended cap: keep the same hard cap of 300 logical Cohere calls. Do not run this without explicit paid-API approval.
