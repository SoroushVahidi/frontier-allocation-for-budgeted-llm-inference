# Post-readiness failure report — semantic diversity Cohere-10

## Summary

- **Job**: Slurm `1011283` (completed `FAILED`, bat exit **2**).
- **Readiness**: **Passed** (stdout shows `smoke_test: success model=command-r-plus-08-2024`).
- **Stage**: **Live diagnostic runner**, first controller invocation after readiness (`scripts/run_semantic_diversity_controller_diagnostic.py`).

## Failure

- **Type**: `AttributeError: 'NoneType' object has no attribute 'strip'` in `experiments/controllers.py::_normalize_answer`.
- **Caller**: `DirectReserveGateRerankController.run`, loop over `direct_answers` when building `prompt_style_groups` (`enumerate(direct_answers)`), if an answer entry is `None`.

## Contributing factor

- **`loss_cases_absent_from_tree.jsonl`** rows often have empty `question` / `gold_answer`. Those rows still yielded empty-string generations or incomplete traces that surfaced as **`None`** in `direct_answers`.

## Partial artifacts

- `outputs/semantic_diversity_controller_diagnostic_20260427T215100Z/selected_cases.jsonl` — written before crash (included incomplete rows).
- `outputs/semantic_diversity_controller_diagnostic_20260427T215100Z/run_failure_issue.md` — traceback excerpt.

## Fix applied (code)

1. **`_normalize_answer`**: accept **`None`** and return `""` (do not alter canonical numeric normalization when given strings).
2. **Live selection**: keep only rows with **`_loss_row_has_question_and_gold`** before `_select_live_cases` prioritization.

## Recommended rerun

After fixes landed:

```bash
export COHERE_API_KEY="..."   # same shell as sbatch
sbatch batch/run_semantic_diversity_cohere10_<timestamp>.sbatch
```

(Intended command is identical inside the sbatch script.)
