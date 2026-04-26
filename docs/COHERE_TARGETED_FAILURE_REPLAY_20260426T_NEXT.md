# Cohere targeted failure replay — `TARGETED_REPLAY_20260426T_NEXT`

## Step 1 — Seed package inspection

| Item | Finding |
|------|---------|
| **Path** | `outputs/cohere_direct_reserve_failure_replay_seed_latest/` |
| **Replay cases** | 5 (`replay_case_list.csv`); problem ids: `openai_gsm8k_12`, `13`, `14`, `2`, `6` |
| **Strata** | 3 `absent_from_tree`, 2 `control_correct` (no `present_not_selected` in the five; the larger `planned_cases.csv` in the same folder lists 12 cases including present-not-selected stratum) |
| **Traces** | `action_trace.jsonl`, `final_branch_states.jsonl`, `tree_decision_traces.jsonl` present |
| **Validation mismatch** | **Important:** The committed `planned_cases.csv` has **12** rows, not 5. Using it with `--max-cases 5` would take only the **first** five rows and would **drop** `openai_gsm8k_2`, `6`, `14`, and `15` that appear in `replay_case_list.csv`. A five-row plan aligned with the replay list was added as `planned_cases_replay_5.csv`. |
| **Seed `missing_fields_report.csv`** | Contains a single line `empty` (not a standard header). The fresh run overwrites with a standard CSV. |

`manifest.json` in the seed documents copy provenance from `cohere_direct_reserve_validation_REGENERATED_FOR_REPLAY_20260426T120000Z` (not in this workspace).

## Step 2 — Real API

**Cohere API was not used in this environment** (`COHERE_API_KEY` was not set). A **dry run** was executed to verify CLI, planning, and output layout.

**Command used (dry run):**

```bash
python3 scripts/run_cohere_direct_reserve_validation.py \
  --timestamp TARGETED_REPLAY_20260426T_NEXT \
  --provider cohere \
  --model command-r-plus-08-2024 \
  --dataset openai/gsm8k \
  --budgets 4 \
  --seeds 23 \
  --max-cases 5 \
  --methods strict_f3,external_l1_max,direct_reserve_strong_v1,direct_reserve_strong_plus_diverse_v1,direct_reserve_strong_plus_diverse_margin_gated_v1 \
  --reuse-planned-cases outputs/cohere_direct_reserve_failure_replay_seed_latest/planned_cases_replay_5.csv \
  --emit-full-traces \
  --dry-run
```

**When `COHERE_API_KEY` is set**, run the same command with `--run-real-api` and **remove** `--dry-run`:

```bash
python3 scripts/run_cohere_direct_reserve_validation.py \
  --timestamp TARGETED_REPLAY_20260426T_NEXT \
  --provider cohere \
  --model command-r-plus-08-2024 \
  --dataset openai/gsm8k \
  --budgets 4 \
  --seeds 23 \
  --max-cases 5 \
  --methods strict_f3,external_l1_max,direct_reserve_strong_v1,direct_reserve_strong_plus_diverse_v1,direct_reserve_strong_plus_diverse_margin_gated_v1 \
  --reuse-planned-cases outputs/cohere_direct_reserve_failure_replay_seed_latest/planned_cases_replay_5.csv \
  --emit-full-traces \
  --resume \
  --run-real-api
```

Output directory: `outputs/cohere_direct_reserve_validation_TARGETED_REPLAY_20260426T_NEXT/` (dry run: `real_api_enabled: false` in `manifest.json`).

## Step 3–4 — Head-to-head from **committed** real Cohere rows (5 replay example ids)

The seed package’s `per_case_method_results.csv` was produced by a real Cohere run over **12** cases; the rows for the **five** replay `example_id`s are used below as **historical evidence** (not a new API call this session).

**Question: Does `direct_reserve_strong_plus_diverse_margin_gated_v1` improve over `direct_reserve_strong_plus_diverse_v1` on these hard cases?**

- **By `is_correct` (strict match):** **No net win** on 5/5: **1 helped**, **1 hurt**, **3 no-op** (per-example: `12` margin correct vs diverse not; `2` diverse correct vs margin not; `6`, `13` both wrong; `14` both correct).

**Selected-gold rate (gold selected in the answer pool)** on the five cases:

| Method | Rate (5 cases) |
|--------|----------------|
| `strict_f3` | 0.00 |
| `external_l1_max` | 0.00 |
| `direct_reserve_strong_v1` | 0.60 |
| `direct_reserve_strong_plus_diverse_v1` | 0.40 |
| `direct_reserve_strong_plus_diverse_margin_gated_v1` | 0.40 |

**Gold-present rate (gold appears in at least one group)** on the five cases:

| Method | Rate (5 cases) |
|--------|----------------|
| `direct_reserve_strong_v1` | 0.60 |
| `direct_reserve_strong_plus_diverse_v1` | 0.60 |
| `direct_reserve_strong_plus_diverse_margin_gated_v1` | 0.40 |
| `strict_f3` | 0.60 |
| `external_l1_max` | 0.20 |

**Margin gate (margin-gated method, five cases):** `margin_gate_triggered=1` on **2/5** (`openai_gsm8k_2`, `openai_gsm8k_6`); `fallback_used=0` in this slice.

| Gate effect vs diverse (`is_correct`) | Count |
|--------|------|
| Helped (margin better) | 1 |
| Hurt (margin worse) | 1 |
| No-op | 3 |

**Control degradation:** Stratum `control_correct` with **both** methods failing on at least one case: `openai_gsm8k_13` remains wrong for both; `openai_gsm8k_14` is correct for both — the prior “control” surface is **not uniformly fixed**.

**Remaining failure modes (from seed loss labeling / inspection for these ids):** mix of **gold absent**, **present-not-selected** (diverse on `12`), **arithmetic / wrong final pick**, and **extraction** issues (e.g. `openai_gsm8k_6` margin output includes non-numeric `oxed` artifact in raw trace).

**Recommendation:** Run the **30–50 case** validation (or a slightly larger held-out set) *after* setting a real API key; on this 5-case slice, margin gate is **inconclusive** (1↔1 trade) and **reduced gold presence** vs diverse on the five ids suggests **threshold / fallback** tuning (margin and entropy) before **verifier-on-disagreement** or a **third direct attempt** add complexity.

## Artifacts

- New five-case input: `outputs/cohere_direct_reserve_failure_replay_seed_latest/planned_cases_replay_5.csv`
- This run: `outputs/cohere_direct_reserve_validation_TARGETED_REPLAY_20260426T_NEXT/` (full CSV/JSONL/MD as produced by the script; dry run only for `per_case_method_results.csv` semantics)

## Tests

Run after `pip install -r requirements.txt` (see “Commands run” in the work log).
