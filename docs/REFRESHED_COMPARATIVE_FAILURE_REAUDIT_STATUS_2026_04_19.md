# Refreshed comparative failure re-audit status (2026-04-19)

## Scope
This pass is diagnosis-only (no new method family), using a fresh matched re-evaluation and casebook extraction on the exact-answer math-ready bundle surface.

- Our method under audit: `broad_diversity_aggregation_strong_v1`
- Canonical baselines compared: `self_consistency_3`, `adaptive_min_expand_1`, `selective_sc_hybrid_v1`, `broad_diversity_aggregation_v1`
- Diagnostic reference baseline: `broad_diversity_aggregation_strong_v1_diversity_needed_gate`
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`, `olympiadbench`
- Seeds: `11, 23, 37`
- Budgets: `4, 6, 8`

Artifacts: `outputs/refreshed_comparative_failure_casebook_20260419/`

## Direct answers

### 1) What is the dominant bottleneck now?
`wrong_commit_timing` is now clearly dominant (253 / 298 loss cases).

### 2) What are the top 2–3 failure groups now?
1. `wrong_commit_timing` (253)
2. `ambiguity_near_tie_failure` (29)
3. `incomplete_or_non_terminal` (8)

`insufficient_diversity_realized` is no longer dominant (1 case only), and aggregation-instability is not top-3 in this refreshed taxonomy.

### 3) What kinds of examples characterize each top group?
- `wrong_commit_timing`: broad spread across all datasets; many examples where gold appears in our support pool but selection/commit finalization misses it.
- `ambiguity_near_tie_failure`: repeated low-margin two-group cases with unstable top-group margins and close alternatives.
- `incomplete_or_non_terminal`: concentrated in harder long-form math examples where our run often returns `None`/non-terminal while a baseline returns a terminal numeric answer.

### 4) What pattern hypotheses emerged?
- Commit/selection calibration appears more bottlenecked than raw exploration coverage.
- Near-tie support margins are too brittle in some high-ambiguity arithmetic/geometry items.
- Some failures look like completion/verification gaps rather than branch discovery gaps.
- The audit repeatedly suggests “correct surfaced but not selected” in important subsets.

### 5) Single best next method idea to test
A bounded **commit-readiness + near-tie selection stabilizer** inside the same broad family:
- delay or soften commit when support margin is near-zero,
- add a small tie-aware final selector for two-group near ties,
- preserve current diversity behavior (since low-diversity is no longer dominant).

