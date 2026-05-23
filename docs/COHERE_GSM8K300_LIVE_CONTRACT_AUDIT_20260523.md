Cohere GSM8K-300 Live Run — Contract Audit (2026-05-23)

Scope: read-only audit comparing the completed live Cohere run to canonical Final-300/Aggregate-720 evidence.

Canonical artifact used for example-level match:
- outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/runner_output/cohere_real_model_cost_normalized_validation_final_fix24_live_20260519/per_example_records.jsonl

Live artifact:
- outputs/live_validation_hardening_frozen_agreement_policy_20260523/cohere_real_model_cost_normalized_validation_20260523T131849Z/per_example_records.jsonl

Core match results:
- Canonical per-example records were found.
- Example-ID overlap: 0 / 300.
- Canonical IDs are `openai_gsm8k_train_*`; live IDs are `openai_gsm8k_*`.
- Frontier sample-order overlap by exact position: 0 / 300.
- Therefore, the two runs are **not contract-matched** for direct example-level comparison.

Accuracy context (canonical vs live):
- Frontier: 230/300 (76.67%) vs 223/300 (74.33%)
- L1: 249/300 (83.00%) vs 216/300 (72.00%)
- S1: 246/300 (82.00%) vs 220/300 (73.33%)
- TALE: 235/300 (78.33%) vs 205/300 (68.33%)

Interpretation of the L1 drop:
- The primary identifiable reason is different sampled examples (and likely different split membership), not a same-example degradation.
- Because the samples do not match, this audit cannot isolate prompt/config/parser effects as the main cause.
- A same-example rerun is required to attribute residual differences to prompt/model/parser/code-path changes.

Scientific usability conclusion:
- **Contract status:** not contract-matched to this canonical Final-300 artifact.
- **Comparability:** aggregate percentage comparison is only suggestive; it is not a clean like-for-like Final-300 comparison.
- **Recommended action:** run one Cohere validation with canonical example selection (same exact 300 IDs/order) before making scientific claims about uplift/drop vs Final-300; then compare with Mistral/Cerebras when complete.

Key audit outputs:
- outputs/cohere_gsm8k300_live_contract_audit_20260523/canonical_example_match_manifest.json
- outputs/cohere_gsm8k300_live_contract_audit_20260523/canonical_vs_live_example_overlap.csv
- outputs/cohere_gsm8k300_live_contract_audit_20260523/canonical_vs_live_method_correctness_diff.csv
- outputs/cohere_gsm8k300_live_contract_audit_20260523/l1_drop_example_level_diagnostic.csv
- outputs/cohere_gsm8k300_live_contract_audit_20260523/canonical_artifact_search_log.txt
- outputs/cohere_gsm8k300_live_contract_audit_20260523/canonical_match_conclusion.md
