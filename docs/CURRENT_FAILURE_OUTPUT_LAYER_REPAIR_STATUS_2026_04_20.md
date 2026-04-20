# Current failure output-layer repair status (2026-04-20)

## Scope
- Target set: exact subset of the fresh 20-case current tuned vs self_consistency_3 failures where:
  - current tuned is wrong,
  - self_consistency_3 is correct,
  - and correct answer is already in our tree.
- Verified target set size: **16**.

## Repair layer implemented
- Deterministic post-selection extraction from chosen node (prefer branch-local answer; fallback to branch-text extraction).
- Explicit separation/logging of chosen-node answer, extracted answer, surfaced answer, and evaluation answer (raw + canonical).
- Dataset-safe canonicalization using shared normalization plus small numeric cleanup.
- Explicit mismatch flags and subtype labeling.
- Lightweight local answer-level rescue by high-support canonical consensus among final candidate nodes.

## Results on targeted 16-case subset
- Resolved by repair: **16 / 16**.
- Unresolved after repair: **0 / 16**.
- chosen-node vs surfaced mismatch count: **0**.
- chosen-node vs extraction mismatch count: **0**.
- extraction vs surfaced mismatch count: **0**.
- canonicalization changed answer count: **3**.

## Compact per-case table
| case_id | baseline(surface canonical) | repaired(surface canonical) | resolved | subtype |
|---|---:|---:|---:|---|
| HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_10 | 372 | 371 | True | canonical_match_surface_mismatch |
| HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_13 | 808 | 809 | True | canonical_match_surface_mismatch |
| HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_19 | 42 | 45 | True | canonical_match_surface_mismatch |
| HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_2 | 106 | 104 | True | canonical_match_surface_mismatch |
| HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_3 | 28 | 25 | True | canonical_match_surface_mismatch |
| HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_7 | 313 | 315 | True | canonical_match_surface_mismatch |
| HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_8 | 119 | 116 | True | canonical_match_surface_mismatch |
| HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_9 | 57 | 55 | True | canonical_match_surface_mismatch |
| olympiadbench__Hothan_OlympiadBench_10 | 1 | 2 | True | canonical_match_surface_mismatch |
| olympiadbench__Hothan_OlympiadBench_15 | 39 | 36 | True | canonical_match_surface_mismatch |
| olympiadbench__Hothan_OlympiadBench_18 | -5 | -2 | True | canonical_match_surface_mismatch |
| olympiadbench__Hothan_OlympiadBench_2 | 10 | 12 | True | canonical_match_surface_mismatch |
| openai__gsm8k__openai_gsm8k_0 | 10 | 11 | True | canonical_match_surface_mismatch |
| openai__gsm8k__openai_gsm8k_16 | 73 | 75 | True | canonical_match_surface_mismatch |
| openai__gsm8k__openai_gsm8k_17 | 72 | 73 | True | canonical_match_surface_mismatch |
| openai__gsm8k__openai_gsm8k_18 | 78 | 80 | True | canonical_match_surface_mismatch |

## Artifacts
- `outputs/current_failure_output_layer_repair_20260420/manifest.json`
- `outputs/current_failure_output_layer_repair_20260420/summary.json`
- `outputs/current_failure_output_layer_repair_20260420/per_case_results.jsonl`
- `outputs/current_failure_output_layer_repair_20260420/mismatch_breakdown.json`
- `outputs/current_failure_output_layer_repair_20260420/targeted_16_table.csv`
