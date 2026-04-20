# Current full-method failure absent-tree audit (2026-04-20)

## Scope
- Canonical note: `docs/TWENTY_EXACT_CURRENT_FULL_METHOD_FAILURES_VS_BEST_2026_04_20.md`.
- Machine-readable source: per-case JSON under `outputs/twenty_exact_current_full_method_failures_vs_best_20260420/cases/`.

## Audit rule (strict)
A case is counted as **absent from our tree** iff machine-readable per-case JSON says the correct answer is absent.
Field priority used:
1. `comparison.our_contains_correct_answer` (absent iff false).
2. Else `comparison.our_correct_answer_node_ids` (absent iff empty).
3. Else `provenance_labels.our_correct_node_identity` (absent iff `absent`).

## Corrected absent-from-tree result
- Computed absent count: **11**.
- Absent case IDs (11): `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_21, HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_23, HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_29, HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_34, HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_11, olympiadbench__Hothan_OlympiadBench_14, olympiadbench__Hothan_OlympiadBench_27, olympiadbench__Hothan_OlympiadBench_39, openai__gsm8k__openai_gsm8k_26, openai__gsm8k__openai_gsm8k_34, openai__gsm8k__openai_gsm8k_37`.
- Present case IDs (9): `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_30, olympiadbench__Hothan_OlympiadBench_13, olympiadbench__Hothan_OlympiadBench_22, olympiadbench__Hothan_OlympiadBench_28, olympiadbench__Hothan_OlympiadBench_34, openai__gsm8k__openai_gsm8k_10, openai__gsm8k__openai_gsm8k_2, openai__gsm8k__openai_gsm8k_21, openai__gsm8k__openai_gsm8k_24`.

## Consistency verdict
- `summary.json` absent count: **11** (matches).
- Markdown aggregate absent count: **11** (matches).
- Markdown per-case vs JSON mismatches: **0**.
- Internal JSON consistency mismatches: **0**.

## Case table (all 20)
| case_id | dataset/example | absent_from_our_tree | source_of_truth_field_used |
|---|---|---:|---|
| `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_21` | `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_21` | `true` | `comparison.our_contains_correct_answer` |
| `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_23` | `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_23` | `true` | `comparison.our_contains_correct_answer` |
| `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_29` | `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_29` | `true` | `comparison.our_contains_correct_answer` |
| `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_30` | `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_30` | `false` | `comparison.our_contains_correct_answer` |
| `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_34` | `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_34` | `true` | `comparison.our_contains_correct_answer` |
| `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_11` | `HuggingFaceH4/aime_2024 / HuggingFaceH4_aime_2024_11` | `true` | `comparison.our_contains_correct_answer` |
| `olympiadbench__Hothan_OlympiadBench_13` | `olympiadbench / Hothan_OlympiadBench_13` | `false` | `comparison.our_contains_correct_answer` |
| `olympiadbench__Hothan_OlympiadBench_14` | `olympiadbench / Hothan_OlympiadBench_14` | `true` | `comparison.our_contains_correct_answer` |
| `olympiadbench__Hothan_OlympiadBench_22` | `olympiadbench / Hothan_OlympiadBench_22` | `false` | `comparison.our_contains_correct_answer` |
| `olympiadbench__Hothan_OlympiadBench_27` | `olympiadbench / Hothan_OlympiadBench_27` | `true` | `comparison.our_contains_correct_answer` |
| `olympiadbench__Hothan_OlympiadBench_28` | `olympiadbench / Hothan_OlympiadBench_28` | `false` | `comparison.our_contains_correct_answer` |
| `olympiadbench__Hothan_OlympiadBench_34` | `olympiadbench / Hothan_OlympiadBench_34` | `false` | `comparison.our_contains_correct_answer` |
| `olympiadbench__Hothan_OlympiadBench_39` | `olympiadbench / Hothan_OlympiadBench_39` | `true` | `comparison.our_contains_correct_answer` |
| `openai__gsm8k__openai_gsm8k_10` | `openai/gsm8k / openai_gsm8k_10` | `false` | `comparison.our_contains_correct_answer` |
| `openai__gsm8k__openai_gsm8k_2` | `openai/gsm8k / openai_gsm8k_2` | `false` | `comparison.our_contains_correct_answer` |
| `openai__gsm8k__openai_gsm8k_21` | `openai/gsm8k / openai_gsm8k_21` | `false` | `comparison.our_contains_correct_answer` |
| `openai__gsm8k__openai_gsm8k_24` | `openai/gsm8k / openai_gsm8k_24` | `false` | `comparison.our_contains_correct_answer` |
| `openai__gsm8k__openai_gsm8k_26` | `openai/gsm8k / openai_gsm8k_26` | `true` | `comparison.our_contains_correct_answer` |
| `openai__gsm8k__openai_gsm8k_34` | `openai/gsm8k / openai_gsm8k_34` | `true` | `comparison.our_contains_correct_answer` |
| `openai__gsm8k__openai_gsm8k_37` | `openai/gsm8k / openai_gsm8k_37` | `true` | `comparison.our_contains_correct_answer` |

## Machine-readable outputs
- `outputs/current_full_method_failure_absent_tree_audit_20260420/absent_case_list.json`
- `outputs/current_full_method_failure_absent_tree_audit_20260420/present_case_list.json`
- `outputs/current_full_method_failure_absent_tree_audit_20260420/full_case_audit_table.csv`
- `outputs/current_full_method_failure_absent_tree_audit_20260420/consistency_report.json`
