# Track B vs PAL baseline — capped Cohere A/B pilot

**Slice:** openai/gsm8k shuffled index slice 80-109 (30 cases), seed=20260501, budget=6. Excludes prior bands: 50-79, 772-1071, 1072-1318. Note: planned 1319-1348 unavailable (HF test split yields indices 0-1318 only).

## Caveats

- Pilot only (n=30 paired cases); not evidence of robust superiority.
- Pairwise metrics use exact-match on surfaced finals after evaluator repairs.

## Headline metrics

- Baseline accuracy: **0.6667** (20/30)
- Track B accuracy: **0.7333** (22/30)
- Logical API calls (sum across scored rows): **130** / cap **300**

## Pairwise summary

```json
{
  "slice_description": "openai/gsm8k shuffled index slice 80-109 (30 cases), seed=20260501, budget=6. Excludes prior bands: 50-79, 772-1071, 1072-1318. Note: planned 1319-1348 unavailable (HF test split yields indices 0-1318 only).",
  "cases_in_pairwise": 30,
  "both_correct": 18,
  "baseline_only": 2,
  "track_b_only": 4,
  "both_wrong": 6,
  "track_b_minus_baseline_case_count": 2,
  "track_b_minus_baseline_pp": 0.06666666666666667,
  "track_b_override_count": 4,
  "override_helpful_count": 0,
  "override_harmful_count": 1,
  "override_neutral_count": 3,
  "total_logical_api_calls_observed": 130,
  "hard_logical_call_cap": 300
}
```

## Override-specific outcomes (when `track_b_gate_override_applied`)

- Helpful (baseline wrong → Track B correct): **0**
- Harmful (baseline correct → Track B wrong): **1**
- Neutral (same correctness class): **3**

## Larger run?

- Consider a wider slice with the same logical-call discipline if accuracy delta and override behavior warrant it.
