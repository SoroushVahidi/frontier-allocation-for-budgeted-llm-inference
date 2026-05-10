# PAL prompt/executor diagnosis (100-case actionable failures)

## Inputs reviewed
- `pal_wrong_casebook.csv`
- `failure_pattern_summary.csv`
- `external_only_wins.md`
- `pal_only_wins.md`
- `metric_consistency_review.md`
- `paired_statistical_tests.md`
- `report.md`
- raw `per_example_records.jsonl`

## Prompt diagnosis (`experiments/controllers.py`)
Current PAL prompt already requires `action='final'`, non-system code, `answer` variable, and `print(answer)`. However, two actionable cases still emitted empty `code`, indicating compliance weakness under real responses.

## Executor diagnosis (`experiments/pal_executor.py`)
- Sandbox was strict and blocked `int(...)`/`float(...)` casts as `call_disallowed:int`.
- One actionable failure (`openai_gsm8k_95`) is directly attributable to this over-restriction.
- Security posture remains strong (imports/eval/exec/open/dunder/attributes/loops/functions/classes rejected).

## Selection/integration diagnosis (`experiments/output_layer_repair.py`)
- Gold-free overlay logic appears consistent.
- Actionable five-case set does not primarily indicate integration defects (no dominant P6 signal).
