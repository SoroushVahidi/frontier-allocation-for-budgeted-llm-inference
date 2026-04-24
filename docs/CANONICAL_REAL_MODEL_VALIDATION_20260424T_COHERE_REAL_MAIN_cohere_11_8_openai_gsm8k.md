# Canonical real-model validation (bounded, manuscript-facing)

## Real-model audit snapshot
- Existing repository evidence includes bounded real-model passes (OpenAI/Cohere/Gemini/Groq paths), but no single canonical paper-facing package with strict_f3 + internal neighbor + simple baseline + fair external baseline on one explicit contract.
- This run closes that packaging gap with one explicit bounded contract and full provenance.

## Exact contract
- Provider/model: `cohere/command-r-plus-08-2024`
- Datasets: ['openai/gsm8k']
- Subset size per dataset per seed: 20
- Seeds: [11]
- Budgets: [8]
- Methods: ['strict_f3', 'strict_gate1_cap_k6', 'strict_f2', 'external_l1_max', 'self_consistency_3']
- Prompting/decoding: APIBranchGenerator JSON protocols, temperature/max token limits set in command.
- Answer extraction/grading: deterministic choose_repair_answer + canonicalize_answer.
- Retry/error handling: provider-level retries inside APIBranchGenerator, per-example failures logged to retry_error_log.csv.

## Main bounded findings
- `external_l1_max` accuracy=0.7500, absent_from_tree_rate=0.2500, output_layer_mismatch_rate=0.0000
- `self_consistency_3` accuracy=0.6842, absent_from_tree_rate=0.3158, output_layer_mismatch_rate=0.0000
- `strict_f2` accuracy=0.6667, absent_from_tree_rate=0.3333, output_layer_mismatch_rate=0.0000
- `strict_f3` accuracy=0.6000, absent_from_tree_rate=0.1500, output_layer_mismatch_rate=0.0000
- `strict_gate1_cap_k6` accuracy=0.5500, absent_from_tree_rate=0.3000, output_layer_mismatch_rate=0.0000

## Interpretation guardrails
- This is bounded validation (single backbone, small subset) and should be treated as directional evidence.
- Broader decisive claims still require larger multi-backbone, larger-sample replications.

## Artifact directory
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_8_openai_gsm8k/`
