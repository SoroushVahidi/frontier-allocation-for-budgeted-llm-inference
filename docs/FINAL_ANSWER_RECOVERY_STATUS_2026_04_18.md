# Final-answer recovery status (2026-04-18)

## Scope

This bounded instrumentation pass fixes a branch-observability bottleneck: branch reasoning text was often present while branch final-answer text / normalized answer were missing at contested states used for oracle-mismatch diagnosis.

## What changed

1. **Branch emission now performs explicit final-answer capture + normalization.**
   - At branch observability record build time, if direct final-answer text is missing, we attempt bounded recovery from existing reasoning/branch text using `extract_final_answer`.
   - Capture metadata records whether answer text is direct vs completion-derived.

2. **Bounded optional completion step for contested worst-case states.**
   - In worst-failure casebook construction, selected contested method/oracle branches can run an explicit bounded completion recovery step (toggleable).
   - Recovered answer text is normalized and stored in per-case diagnostics.

3. **Machine-readable recoverability diagnostics.**
   - New per-run final-answer recovery bundle under:
     - `outputs/final_answer_recovery/<run_id>/manifest.json`
     - `outputs/final_answer_recovery/<run_id>/recoverability_diagnostics.json`
     - `outputs/final_answer_recovery/<run_id>/contested_case_recovery.jsonl`
   - Branch observability summary now distinguishes:
     - direct final-answer recoverable
     - completion-derived final-answer recoverable

## Bounded real run

Command run:

```bash
python scripts/run_worst_real_failure_casebook_with_reasoning.py \
  --subset-size 5 --seed 19 --budget 5 --init-branches 3 --max-branches 4 \
  --provider openai --model gpt-4.1-mini --allow-sim-fallback --top-k 5
```

Run ID:
- `worst_real_failure_observability_20260418T022231Z`

Outputs:
- `outputs/branch_observability/worst_real_failure_observability_20260418T022231Z/`
- `outputs/final_answer_recovery/worst_real_failure_observability_20260418T022231Z/`

## Recovery counts on selected contested cases

From `recoverability_diagnostics.json` + casebook summary:
- Contested cases selected: **5**
- Direct method final-answer recovery: **0/5**
- Direct oracle final-answer recovery: **0/5**
- Method recovered final-answer (direct-or-completion): **5/5**
- Oracle recovered final-answer (direct-or-completion): **5/5**

## Adjudication readiness

For this bounded run, this is **enough to adjudicate semantic mismatch cases** because both method and oracle branches retain recoverable final-answer text and normalized answers across all selected contested states.

