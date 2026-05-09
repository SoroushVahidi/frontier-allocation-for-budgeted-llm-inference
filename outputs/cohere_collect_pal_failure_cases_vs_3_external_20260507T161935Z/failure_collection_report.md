# PAL + retry failure collection (vs three externals)

## What ran
- Bundle directory contains `cohere_real_model_cost_normalized_validation_*` run artifacts and allowlists.
- Materialization is offline from `per_example_records.jsonl`.

## Scale
- Evaluated cases (any rows): **247**
- Complete 4-method rows: **245**
- Selected failure corpus size: **45** (target 45 preferred-first, padded with secondary rich-trace cases if needed)
- Preferred failures in pool: **34**; secondary (PAL wrong, all externals wrong): **23**
- Logical Cohere calls (sum of row counters): **1893** (cap 3000)

## Selected failure case IDs
- `openai_gsm8k_1082` (preferred)
- `openai_gsm8k_1083` (preferred)
- `openai_gsm8k_1085` (preferred)
- `openai_gsm8k_1087` (preferred)
- `openai_gsm8k_1095` (preferred)
- `openai_gsm8k_1097` (preferred)
- `openai_gsm8k_1099` (preferred)
- `openai_gsm8k_1116` (preferred)
- `openai_gsm8k_1120` (preferred)
- `openai_gsm8k_1121` (preferred)
- `openai_gsm8k_1122` (preferred)
- `openai_gsm8k_1124` (preferred)
- `openai_gsm8k_1125` (preferred)
- `openai_gsm8k_1150` (preferred)
- `openai_gsm8k_1155` (preferred)
- `openai_gsm8k_1166` (preferred)
- `openai_gsm8k_1175` (preferred)
- `openai_gsm8k_1187` (preferred)
- `openai_gsm8k_1198` (preferred)
- `openai_gsm8k_1205` (preferred)
- `openai_gsm8k_1210` (preferred)
- `openai_gsm8k_1214` (preferred)
- `openai_gsm8k_1215` (preferred)
- `openai_gsm8k_1230` (preferred)
- `openai_gsm8k_1244` (preferred)
- `openai_gsm8k_1248` (preferred)
- `openai_gsm8k_1279` (preferred)
- `openai_gsm8k_1281` (preferred)
- `openai_gsm8k_1290` (preferred)
- `openai_gsm8k_1291` (preferred)
- `openai_gsm8k_1299` (preferred)
- `openai_gsm8k_1303` (preferred)
- `openai_gsm8k_1307` (preferred)
- `openai_gsm8k_1314` (preferred)
- `openai_gsm8k_1081` (secondary)
- `openai_gsm8k_1112` (secondary)
- `openai_gsm8k_1115` (secondary)
- `openai_gsm8k_1131` (secondary)
- `openai_gsm8k_1132` (secondary)
- `openai_gsm8k_1137` (secondary)
- `openai_gsm8k_1139` (secondary)
- `openai_gsm8k_1144` (secondary)
- `openai_gsm8k_1147` (secondary)
- `openai_gsm8k_1158` (secondary)
- `openai_gsm8k_1162` (secondary)

## Per-method accuracy (evaluated pool, scored rows)
- `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`: 189/247 = 0.7652
- `external_l1_max`: 182/245 = 0.7429
- `external_tale_prompt_budgeting`: 175/247 = 0.7085
- `external_s1_budget_forcing`: 184/247 = 0.7449

## PAL vs each external (pairwise)
- vs L1: external_only=23 pal_only=29 both_wrong=34 both_correct=159
- vs TALE: external_only=24 pal_only=39 both_wrong=33 both_correct=149
- vs S1: external_only=24 pal_only=30 both_wrong=33 both_correct=158

## PAL vs best external
- PAL accuracy: 0.7673; best-external accuracy: 0.8857
- Counts: {'both_correct': 183, 'both_wrong': 23, 'external_only': 34, 'pal_only': 5}

## Dominant failure patterns (heuristic tags, selected PAL-wrong cases)
- `temporal_change`: 19
- `rate_ratio`: 7
- `difference`: 6

## Incomplete 4-way rows (explicit failures, not silent skips)
- `openai_gsm8k_1101` and `openai_gsm8k_1102`: `external_l1_max` hit **Cohere read timeouts** (`RuntimeError: ... timed out`). Rows exist in `all_results.jsonl` with `status=failed` and `scored=0`. PAL, TALE, and S1 rows for those `example_id`s completed.

## Caveats
- Exact-match scoring only; no claim of statistical superiority.
- Incomplete slices (missing scored method rows) are listed in `failure_collection_summary.json` (`incomplete_case_ids`).

## More collection needed?
- **Preferred PAL-loss / external-win cases:** only **34** were available in this GSM8K suffix slice (`openai_gsm8k_1072`–`1318`) before exhausting candidates; the 45-case corpus pads with **11** secondary (PAL wrong, all externals wrong) rich-trace rows.
- To grow **preferred** failures beyond 34 without changing methods, you would need **additional datasets / IDs**, **reruns** for slices that timed out (notably `external_l1_max` on `openai_gsm8k_1101` / `1102`), or a **different seed/split policy** — not performed here.

