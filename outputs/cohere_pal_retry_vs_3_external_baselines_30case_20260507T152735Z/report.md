# Cohere pilot: PAL vs three external baselines (30 cases)

This is a **small, non-definitive** paired run on GSM8K (`openai/gsm8k`). Do **not** generalize accuracy gaps beyond this slice.

## Methods

1. `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal` (PAL)
2. `external_l1_max`
3. `external_tale_prompt_budgeting`
4. `external_s1_budget_forcing`

## Design

- **Cases:** 30 deterministic IDs `openai_gsm8k_50` … `openai_gsm8k_79` (same IDs for all methods).
- **Overlap with prior 300-case PAL+retry run:** **0** (that run started at `openai_gsm8k_772`).
- **Provider / model:** Cohere `command-r-plus-08-2024`.
- **Budget:** 6 actions per slice configuration (runner `--budgets 6`).
- **Seed:** `20260501` (matches prior paired harness pattern).
- **Logical API call cap:** 900 (actual total **224**).

## Call usage

| Metric | Value |
|--------|-------|
| Rows written (`per_example_records.jsonl` / `results.jsonl`) | 120 (= 30 × 4) |
| Total Cohere logical calls (sum of `cohere_logical_api_calls`) | **224** |
| By method (logical calls) | PAL **63**, `external_l1_max` **40**, `external_tale_prompt_budgeting` **47**, `external_s1_budget_forcing` **74** |

## Per-method accuracy (exact match)

| Method | Correct | Total | Accuracy |
|--------|---------|-------|----------|
| PAL | 17 | 30 | 0.5667 |
| external_l1_max | 21 | 30 | 0.7000 |
| external_tale_prompt_budgeting | 20 | 30 | 0.6667 |
| external_s1_budget_forcing | 20 | 30 | 0.6667 |

## PAL vs each external baseline (paired)

See `pairwise_summary.json` for full contingency tables.

| Comparison | both_correct | pal_only | external_only | both_wrong | PAL − ext accuracy (pp) |
|------------|--------------:|----------:|---------------:|-----------:|--------------------------:|
| PAL vs `external_l1_max` | 16 | 1 | 5 | 8 | −13.33 |
| PAL vs `external_tale_prompt_budgeting` | 17 | 0 | 3 | 10 | −10.00 |
| PAL vs `external_s1_budget_forcing` | 15 | 2 | 5 | 8 | −10.00 |

## PAL vs best external (preference `l1` → `tale` → `s1` when multiple correct)

| Metric | Count |
|--------|------:|
| PAL correct | 17 |
| Best external correct | 24 |
| Both correct | 17 |
| PAL only | 0 |
| External only | 7 |
| Both wrong | 6 |
| PAL − best-external accuracy (pp) | −23.33 |

## Caveats

- **n = 30:** wide confidence intervals; differences are **not** statistically compelling.
- **Case slice:** early-index GSM8K examples only; not representative of the full distribution.
- **`avg_actions_used`** in `method_summary.csv` may be blank when `actions_used` is not surfaced numerically in metadata (PAL often omits a single scalar).

## Artifacts

Primary tables: `paired_casebook.csv`, `method_summary.csv`, `pairwise_summary.json`, `case_matrix.md`, `failure_notes.md`, `results.jsonl`, `call_plan.json`, `manifest.json`.

## Whether a larger run is justified

Only as **follow-up exploration**: this pilot confirms wiring and surfaces slice-specific gaps; it does **not** justify claims about overall dominance. A broader allowlist and pre-registered metrics would be needed before treating differences as meaningful.
