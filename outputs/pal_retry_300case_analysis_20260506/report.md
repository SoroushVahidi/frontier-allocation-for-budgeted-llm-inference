# PAL+retry vs external_l1_max — 300-case analysis summary (no API)

- **Analysis output path:** `outputs/pal_retry_300case_analysis_20260506`
- **Input run path:** `outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z`

## Statistical conclusion
- Gap (PAL+retry − external): **+2.67 pp** on `300` fully paired GSM8K cases.
- Wilson 95% CIs: external **[76.54%, 85.34%]**; PAL+retry **[79.43%, 87.71%]** (overlap).
- McNemar-style exact test on discordants: **p ≈ 0.322** (not significant at conventional α=0.05).
- Bootstrap (20k) paired-difference 95% CI: **[-2.00 pp, 7.33 pp]** (includes 0).
- Verdict: **PAL+retry is competitive** (rates within CI overlap); **superiority is not statistically supported** on this paired exact-match criterion.
- Evidence is **not yet “strong”** for a superiority claim, but is **adequate as a headline paired estimate** with explicit uncertainty.

## Retry contribution conclusion
- Retry **ran on ~5.3%** of rows; aggregate effect is **small** relative to overall accuracy movement.
- Per-trigger pipeline quality (`exec_ok` etc.) matters more than widening another uncapped grid without policy edits.

## Main failure modes (PAL-side heuristic labels)
- See **`external_only_failure_summary.md`**, **`pal_only_win_summary.md`**, **`both_wrong_summary.md`** for bucketed counts.

## Comparison to previous runs
- Summarized in **`comparison_to_previous_runs.md`**: prefer **this 300-case** cohort as the current best paired estimate versus mixing heterogeneous 100-case slices.

## Exactly one recommended next action
- **E. Analyze failures more deeply (offline)** — see **`recommended_next_step.md`.

## API posture
- **Keep API paused** until you either finish failure archaeology or approve a new, budgeted validation design.

## Write/commit guidance (no git actions taken here)
- Add this analysis directory to version control as documentation-only artifacts when ready: `outputs/pal_retry_300case_analysis_20260506/**`.
- In any write-up, cite **raw-metadata retry fields** and disclose the **`retry_enabled` CSV column bug** flagged in `metric_consistency_review.md`.
