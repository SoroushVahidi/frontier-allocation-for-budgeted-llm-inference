# Real Cohere tiny trace learned-scorer decision (20260425T_REAL_COHERE_TINY)

## Run configuration
- Script: `scripts/run_bounded_real_trace_collection.py`
- Provider/model: `cohere` / `command-r-plus-08-2024`
- Dataset: `openai/gsm8k`
- Planned strata: 3 absent-from-tree, 3 present-not-selected, 3 control-correct
- Budgets: `4`
- Seeds: `11`
- Max cases: `9`
- Full traces: enabled
- Resume: enabled
- Real API flag: enabled

## Did the run actually use the Cohere API?
Yes. `run_manifest.json` reports `run_real_api_requested=true` and `real_api_enabled=true`.

## Collection outputs
- Trace directory: `outputs/bounded_real_trace_collection_20260425T_REAL_COHERE_TINY`
- Traced real examples: **9** (`per_case_results.csv` rows)
- Branch rows collected: **18** (`branch_table.csv` rows)
- Answer-group rows collected: **9** (`answer_group_table.csv` rows)

## Trace-level learned-scorer dataset summary
Built with:
`python scripts/build_trace_level_learned_branch_scorer_dataset.py --timestamp 20260425T_REAL_COHERE_TINY --trace-dir outputs/bounded_real_trace_collection_20260425T_REAL_COHERE_TINY`

From `outputs/trace_level_learned_branch_scorer_dataset_20260425T_REAL_COHERE_TINY`:
- Traced examples/cases: **9**
- Candidate branches (training rows): **18**
- Gold-present cases: **0**
- Gold-absent cases: **9**
- Present-not-selected cases (realized in this run): **0** (cannot be observed without any gold-present cases)
- Control cases in planning strata: **3** (all also gold-absent under current gold matching)
- `source_type` distribution: `trace_level_branch=18` (proxy rows = 0)
- Data-quality flag:
  - No positive/gold candidate rows (`n_gold_rows=0`, `gold_row_rate=0.0`)

## Learned scorer training/eval decision
### Training
Skipped intentionally. Rule applied: do not train a learned scorer when real trace dataset has zero positive/gold candidates.

### Evaluation
Skipped intentionally because scorer training did not run and no predictions artifact was produced.

## Coverage vs selection diagnosis
For this tiny real Cohere run (`n=9`):
- All cases are currently measured as **gold-absent** in candidate pool (`gold_present_cases=0/9`).
- Therefore selection improvements cannot be validated on this run.
- Current bottleneck remains **coverage generation**, not branch reranking/selection.

## Control degradation check
No learned scorer was trained or applied, so there are no learned-scorer degradation cases to report.

## Decision
1. Runtime learned-scorer integration is **not justified yet** from this run.
2. Next bottleneck is still **coverage generation**.
3. Next diagnostic step should focus on improving direct-reserve/branch generation coverage before reranking.
4. Keep `strict_f3` canonical unchanged.

## If/when to revisit learned reranking
Revisit scorer training after collecting a bounded real trace slice that yields a non-trivial number of gold-present cases (e.g., enough to compute gold-present selection accuracy and present-not-selected reduction with non-zero denominator).
