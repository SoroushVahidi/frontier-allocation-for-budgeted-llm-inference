# Short Job Execution Policy (2026-04-29)

## Rule

For short jobs, do **not** send batch jobs to Wulver/Slurm by default.

Short checks and small selector validations should be run directly in an interactive/local shell whenever feasible.

## Use direct execution for

- unit tests;
- lightweight registry validation;
- `--validate-methods-only` checks;
- smoke runs with `--target-scored-per-slice 1` or similarly tiny settings;
- small no-API dry runs;
- quick script/import/path checks;
- short diagnostic commands expected to finish quickly.

Examples:

```bash
python -m pytest -q tests/test_answer_grouped_outcome_verifier.py
python -m pytest -q tests/test_frontier_router.py tests/test_check_repo_health_paths.py
python scripts/check_repo_health.py
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --providers cohere \
  --datasets openai/gsm8k \
  --budgets 4 \
  --seeds 11 \
  --methods external_l1_max,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1 \
  --target-scored-per-slice 1 \
  --max-examples 1 \
  --validate-methods-only
```

## Use Wulver/Slurm batch only for

- long real-model API runs;
- multi-slice or multi-seed experiments;
- large 100-case or larger evaluations when runtime/cost/continuation needs justify batching;
- jobs requiring stable long-running sessions;
- experiments where chunking/resumability matters.

## Practical workflow

1. Run short local/interactive checks first.
2. Only submit Slurm/batch jobs after the method is registered, unit-tested, and dry-run validated.
3. For real Cohere/OpenAI experiments, prefer completed scored rows and compact ledger exports over markdown-only progress notes.

## Claim-safety note

Short interactive runs are useful for validation and debugging, but they are not sufficient for manuscript-facing claims unless promoted through the repository's canonical evidence workflow.
