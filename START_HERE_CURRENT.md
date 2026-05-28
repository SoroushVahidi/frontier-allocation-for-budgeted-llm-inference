# Start here — current front door (updated 2026-05-27)

Short orientation for humans and agents. Historical and timestamped material stays in place; this file points to **current** interpretation and safe next actions.

> **Note:** Content below this line dated "2026-05-11" is historical background. See canonical current state below.

---

## Canonical current state (2026-05-27)

**Read first:** [`docs/CURRENT_CANONICAL_STATE_20260527.md`](docs/CURRENT_CANONICAL_STATE_20260527.md)
**Full results:** [`docs/LATEST_RESULTS_AND_CLAIMS.md`](docs/LATEST_RESULTS_AND_CLAIMS.md)

### Current verified evidence at a glance

**Canonical paper result — FTA / FIX-2+FIX-4 (Failure-Trace Allocator):**
- Final-300 (seed=71, Cohere × GSM8K, budget=6): **86.67%** (260/300) — independently verified
- Aggregate-720 (seeds 41+61+71): **80.69%** (581/720) — source-stratified CI lo > 0 vs all externals
- Gate: FIX-2=63, FIX-4=3, no-gate=234; FIX-4 causes 0 regressions
- Leakage audit: PASS — gate features gold-free at runtime; 0 post-generation model calls
- Implementation: `experiments/support_aware_selector.py`

**Supporting evidence — D9 gated selector:**
- 5-fold grouped CV: **50.18% ± 2.52%** vs frontier 34.36% (+15.82pp)
- Gate: 0 false overrides across all tested thresholds
- D6 standalone is negative; D9 gate is required for a positive outcome

**Required paper disclosures:**
1. CI vs pooled ensemble includes zero — do not claim statistical superiority over pooled ensembles
2. Full pool generation = 4×B=6 = 24 logical calls per example
3. Evaluation: Cohere × GSM8K only; do not extrapolate to MATH-500
4. Seed=61 (59.17%) in aggregate-720 is failure-enriched, not typical

### Current project question

Under explicit inference budgets, how should compute be allocated across reasoning paths, and how should the **final answer** be chosen from the explored frontier? Active work separates:

1. **discovery/coverage:** getting the correct answer into the explored candidate pool
2. **selection/replay:** choosing among existing candidates without gold leakage

Do not revert to the older binary cheap-vs-revise routing story.

### Current best external baselines

- **`external_l1_max`** (L1): 83.00% on Final-300; 77.64% on Agg-720
- **`external_s1_budget_forcing`** (S1): 82.00% on Final-300; 77.08% on Agg-720
- **`external_tale_prompt_budgeting`** (TALE): 78.33% on Final-300; 75.14% on Agg-720
- **Pooled ensemble** (frontier+L1+S1+TALE majority): 84.33% on Final-300; 79.86% on Agg-720

FTA beats all individual externals with positive CI lower bounds. FTA leads the pooled ensemble by point estimate only (CI includes zero — must disclose).

### Current priority: paper finalization

**No API calls needed.** All canonical numbers are verified. Write the manuscript using FTA as the main result and D9 as supporting multi-provider evidence.

For D9/D6 expansion work (secondary): see `docs/CURRENT_CANONICAL_STATE_20260527.md` Section 7.

---

## Historical front door content (2026-05-11, kept for provenance)

> The content below is from the 2026-05-11 handoff. All PAL+retry results, old internal lines,
> bottleneck hypotheses, and method tables below are **historical only** and are superseded by
> the FTA canonical result (260/300 = 86.67%). **Do not use these numbers as the paper headline.**
>
> See `docs/CURRENT_CANONICAL_STATE_20260527.md` for the current truth.
>
> Historical handoff doc: [`docs/CODEX_WEB_HANDOFF_20260510.md`](docs/CODEX_WEB_HANDOFF_20260510.md) ·
> Historical method status: [`docs/CURRENT_APPROACHES_STATUS_20260505.md`](docs/CURRENT_APPROACHES_STATUS_20260505.md)

## Read next (current, reviewer-facing)

| Order | File |
|------:|------|
| 1 | `docs/CURRENT_CANONICAL_STATE_20260527.md` |
| 2 | `docs/CLAIMS.md` |
| 3 | `docs/LATEST_RESULTS_AND_CLAIMS.md` |
| 4 | `docs/PAPER_SOURCE_OF_TRUTH.md` |
| 5 | `docs/CURRENT_EXTERNAL_BASELINE_GAP.md` |
| 6 | `docs/ARTIFACT_STATUS_TABLE.md` |
| 7 | `docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md` |

## Reviewer-safe checks

```bash
make health
make reviewer-test
make selector-test
```

Paper artifact regeneration:

```bash
python scripts/paper/reproduce_current_manuscript_artifacts.py
```

## Provenance warning

Timestamped directories under `outputs/` are scientific provenance. Do not delete or reinterpret
numeric folders without reading their manifests, summary JSON/MD, and docs classification.
Older runs may be mock-backed, cache-limited, old-method-only, or superseded.
