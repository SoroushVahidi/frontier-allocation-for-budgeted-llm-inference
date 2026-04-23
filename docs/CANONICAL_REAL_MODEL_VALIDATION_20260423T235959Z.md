# Canonical real-model validation (bounded, manuscript-facing)

## Real-model audit snapshot
- Existing repository evidence includes bounded real-model passes (OpenAI/Cohere/Gemini/Groq paths), but no single canonical paper-facing package with strict_f3 + internal neighbor + simple baseline + fair external baseline on one explicit contract.
- This run closes that packaging gap with one explicit bounded contract and full provenance.

## Exact contract
- Provider/model: `openai/gpt-4.1-mini`
- Datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']
- Subset size per dataset per seed: 2
- Seeds: [11]
- Budgets: [4]
- Methods: ['strict_f3', 'strict_gate1_cap_k6', 'strict_f2', 'external_l1_max']
- Prompting/decoding: APIBranchGenerator JSON protocols, temperature/max token limits set in command.
- Answer extraction/grading: deterministic choose_repair_answer + canonicalize_answer.
- Retry/error handling: provider-level retries inside APIBranchGenerator, per-example failures logged to retry_error_log.csv.

## Main bounded findings
- `external_l1_max` accuracy=0.5000, absent_from_tree_rate=0.5000, output_layer_mismatch_rate=0.0000
- `strict_f3` accuracy=0.3333, absent_from_tree_rate=0.6667, output_layer_mismatch_rate=0.0000
- `strict_f2` accuracy=0.0000, absent_from_tree_rate=1.0000, output_layer_mismatch_rate=0.0000
- `strict_gate1_cap_k6` accuracy=0.0000, absent_from_tree_rate=1.0000, output_layer_mismatch_rate=0.0000

## Interpretation guardrails
- This is bounded validation (single backbone, small subset) and should be treated as directional evidence.
- Broader decisive claims still require larger multi-backbone, larger-sample replications.

## Artifact directory
- `outputs/canonical_real_model_validation_20260423T235959Z/`
