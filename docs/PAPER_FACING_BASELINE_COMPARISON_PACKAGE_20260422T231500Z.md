# Paper-facing baseline comparison package (20260422T231500Z)

Our manuscript method is **strict_f3** because the repository finalized strict_f3 as the single canonical in-house winner on the strongest current canonical matched in-house ranking surface, and current-status docs explicitly lock 'our method' to strict_f3.

The near-direct ranking is separated from adjacent published baselines because near-direct methods share a matched comparison substrate while adjacent methods have meaningful but non-equivalent control spaces (e.g., routing, verifier/process-guidance, or solve-vs-verify contracts), so merging them into one leaderboard would overstate fairness.

Discussion-only papers are separated again because they are scientifically important but not honestly runnable enough in the current repository to claim integrated empirical baseline status; they should be cited with blockers and safe wording rather than ranked.

The strongest fair external baseline story on the canonical matched surface is: `external_l1_max` is the top near-direct external comparator, but strict_f3 still leads by 0.161111 mean accuracy, so the paper can make a clear 'best fair external competitor' comparison without mixing taxonomy buckets.

The main remaining failure mechanism story from current strict loss analysis is that strict_f3 has 56 strict loss examples currently available against the strongest fair external baseline, dominated by absent_from_tree cases with a secondary present_not_selected slice, across a dataset mix led by GSM8K and MATH-500 plus AIME-2024 coverage.

## Canonical output bundle
- `outputs/paper_facing_baseline_tables/20260422T231500Z/`

## Simple scaling axis explicitness update (2026-04-22)
- The near-direct package explicitly treats `external_s1_budget_forcing` as the reviewer-facing representative for simple inference-time scaling in the matched adapter lane.
- Coverage audit artifact: `outputs/simple_scaling_baseline_coverage_audit/20260422T235959Z/coverage_decision.json` and `outputs/paper_facing_baseline_tables/20260422T231500Z/simple_scaling_axis_explicit_note.md`.
- No additional Best-of-N/self-consistency direct baseline was added in this pass to avoid redundant baseline sprawl.

