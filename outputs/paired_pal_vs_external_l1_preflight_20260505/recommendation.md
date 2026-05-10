# Paired PAL vs external_l1_max — no-API preflight (2026-05-05)

## Scope

Offline inventory + deterministic cohort sizing only. **No Cohere/OpenAI API calls** were executed as part of this preflight. GSM8K rows were reconstructed using **local HF dataset cache** with `HF_DATASETS_OFFLINE=1` / `HF_HUB_OFFLINE=1`.

## Deterministic workspace

- Repo/worktree: ``
- Pool matches `load_pilot_examples("openai/gsm8k", subset_size=2048, seed=20260501)` (effective pool size **1319**).

## Fresh cohort availability

- Distinct excluded IDs (targeted harvesting): **111**
- Fresh candidates remaining in the deterministic pool: **1208**

## Empirical cost model (PR #357)

Source: `outputs/cohere_paired_pal_vs_external_l1_fresh_20260505T222840Z/paired_summary.json`.

- Completed paired rows: **43**
- Row-sum logical calls (both methods, completed rows only): **250**
- Observed global branching-cap consumption proxy: **360**
- Average row-sum per paired row (both methods): **5.8140**
- Average cap-proxy per paired row: **8.3721**
- **Cap caveat:** row-sum understates authoritative global cap consumption; plan budgets using cap-proxy (or enforce stricter caps), not row-sum alone.

## Planned batch targets (linear extrapolation from PR357 averages)

| paired rows | est row-sum logical calls (both methods) | est cap-proxy consumption |
|---:|---:|---:|
| 50 | 290.70 | 418.60 |
| 100 | 581.40 | 837.21 |
| 150 | 872.09 | 1255.81 |
| 200 | 1162.79 | 1674.42 |

## Approximate max paired rows vs total API caps (floor using cap-proxy / pair)

| cap | ~max paired rows (floor) |
|---:|---:|
| 500 | 59 |
| 750 | 89 |
| 1000 | 119 |
| 1500 | 179 |

## Method registry check (`--validate-methods-only`)

**Result: FAILED** for `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`.

PAL suffix ID used by the paired pilot bundles is **not** registered in `scripts/run_cohere_real_model_cost_normalized_validation.py` (nearest match drops `_pal`). Address before relying on that validator for PAL parity checks.

## Recommendation

**Pick paired rows next:** **100** (best compromise after **n=43**) — requires ~**837** cap-proxy units (~**581** row-sum calls).

**Proposed `max_total_api_calls`:** **1000–1100** (explicitly above the PR357 **360** cap class).

**Not recommended now:** **200** paired rows under a **1500** cap-proxy budget (needs ~**1674**).

**If capped at 500:** choose **50** paired rows (floor ~**59**).

**Statistical usefulness:** **n=100** narrows uncertainty vs **n=43** but remains pilot-scale.

**Risks:** cap saturation/partial pairing; orphan rows; per-method imbalance on retries; duplicated IDs if allowlists drift; metric/tooling mismatch (**PAL** registry gap).

**API next?** Only **after** resolving the registry/tooling mismatch **or** documenting an approved alternate validation entrypoint for `_pal`.
