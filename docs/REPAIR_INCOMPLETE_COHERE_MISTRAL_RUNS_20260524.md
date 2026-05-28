# Repair Incomplete Cohere/Mistral Runs (2026-05-24)

## Summary
- Diagnosed first-method-only failure mode for both runs.
- Verified original frontier rows are clean and reusable.
- Prepared method-safe repair case/allowlist files.
- Launched missing-method-only repair jobs in detached tmux.
- Active Cerebras run was observed and left untouched.

## Diagnosis
- Root cause: allowlist rows missing method fields defaulted to frontier in runner allowlist loader, then non-frontier methods were skipped by per-method allowlist gating.
- Details and evidence: `outputs/repair_incomplete_cohere_mistral_runs_20260524/incomplete_run_diagnosis.md`

## Incomplete Counts
- Cohere incomplete run: 47/188 rows present, 141 missing.
- Mistral incomplete run: 300/1200 rows present, 900 missing.
- Integrity summaries:
  - `outputs/repair_incomplete_cohere_mistral_runs_20260524/cohere_incomplete_integrity_summary.json`
  - `outputs/repair_incomplete_cohere_mistral_runs_20260524/mistral_incomplete_integrity_summary.json`

## Repair Call Plans
- Cohere: `outputs/repair_incomplete_cohere_mistral_runs_20260524/cohere_missing_methods_repair_call_plan.json`
- Mistral: `outputs/repair_incomplete_cohere_mistral_runs_20260524/mistral_missing_methods_repair_call_plan.json`
- Dry-run safety plans:
  - `outputs/repair_incomplete_cohere_mistral_runs_20260524/cohere_missing_methods_repair_dry_run_plan.json`
  - `outputs/repair_incomplete_cohere_mistral_runs_20260524/mistral_missing_methods_repair_dry_run_plan.json`

## Launch Status
- Cohere session: `cohere_repair_missing_20260524T003751Z`
- Mistral session: `mistral_repair_missing_20260524T003751Z`
- Cohere log: `outputs/repair_incomplete_cohere_mistral_runs_20260524/cohere_missing_methods_repair_20260524T003751Z.log`
- Mistral log: `outputs/repair_incomplete_cohere_mistral_runs_20260524/mistral_missing_methods_repair_20260524T003751Z.log`
- Cohere PID: `2282436`
- Mistral PID: `2282436`
- Launch status files:
  - `outputs/repair_incomplete_cohere_mistral_runs_20260524/cohere_repair_launch_status.json`
  - `outputs/repair_incomplete_cohere_mistral_runs_20260524/mistral_repair_launch_status.json`

## Current Status (Snapshot)
- Cohere rows currently written: 10
- Cohere methods seen so far: ['external_l1_max']
- Mistral rows currently written: 100
- Mistral methods seen so far: ['external_l1_max']
- Mistral 429 retry events observed so far: 38

## Post-Completion Actions
- Follow merge plan: `outputs/repair_incomplete_cohere_mistral_runs_20260524/merge_plan_after_missing_method_repair.md`
- Merge original frontier rows with repair missing-method rows.
- Verify full 4-method completeness and dedup integrity.
- Only then run selector replay.

## Cerebras Safety
- Active Cerebras process detected in `ps` and left untouched.
- No tmux attach/kill/restart performed for Cerebras session.
