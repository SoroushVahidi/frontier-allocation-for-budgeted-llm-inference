# Cohere API key issue report

- Timestamp (UTC): 20260427T183000Z
- Runtime context (detected): `ssh`
- Model: `command-r-plus-08-2024`
- `COHERE_API_KEY` presence: `present`
- Failure class: `package_or_import_error`

## What happened
- Cohere readiness/smoke test failed before rerun.

## How to fix
- Install/upgrade the Cohere SDK dependency used by the repo.
- Set key format (placeholder only):
```bash
export COHERE_API_KEY="..."
```

## Exact rerun command
```bash
python scripts/run_cohere_trace_complete_loss_subset.py --timestamp 20260427T183000Z --model "command-r-plus-08-2024" --max-cases 30
```

## Sanitized error
```text
Traceback (most recent call last):
  File "/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/scripts/run_cohere_direct_reserve_validation.py", line 758, in <module>
    main()
  File "/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/scripts/run_cohere_direct_reserve_validation.py", line 376, in main
    res = ctrl.run(str(row["question"]), str(row["gold_answer_raw"]))
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/experiments/controllers.py", line 5457, in run
    g = _normalize_answer(answer) or "__unknown__"
        ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/experiments/controllers.py", line 6606, in _normalize_answer
    stripped = text.strip()
               ^^^^^^^^^^
AttributeError: 'NoneType' object has no attribute 'strip'

```
