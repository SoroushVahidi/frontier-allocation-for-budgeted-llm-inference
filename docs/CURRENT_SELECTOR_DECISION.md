# Current Selector Decision

Selected selector: `outcome_verifier_answer_group_selector_v1`

Selected scorer: `cached_jsonl` (margin `0.0`)

Current-correct risk cannot be fully validated from committed artifacts in this branch.

Run command:
```bash
python scripts/run_outcome_verifier_answer_group_selector.py --input outputs/unified_selector_evidence_20260501T145906Z/unified_candidate_trace_enriched.jsonl --output-dir outputs/outcome_verifier_answer_group_selector_selected --selector-name outcome_verifier_answer_group_selector_v1 --scorer-mode cached_jsonl --min-verifier-margin 0.0 --require-trace-for-override --dedupe-verifier-items --no-gold-features
```
