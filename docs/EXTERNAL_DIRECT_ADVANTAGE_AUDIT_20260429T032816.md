# External Direct Advantage Audit

1. Audited external_direct_advantage cases: 31.
2. Likely true direct advantage: 11.
3. Missing-trace artifacts: 20.
4. Possible present-not-selected: 0.
5. Possible extraction issue: 0.
6. Possible commit/over-exploration issue: 0.
7. Recommended bottleneck change: **Yes** — from broad `collect_trace_complete_losses` to a **narrow trace completion target for external_direct_advantage rows currently lacking trace support**.
8. Exact next evidence/action: run a bounded, case-ID-targeted trace completion pass for those 20 missing-trace rows (same provider/dataset/budget/seed envelope), then rerun this audit and only then decide whether direct-first routing or selection-focused algorithm work is justified.

Current interpretation: `external_direct_advantage` is presently dominated by missing-trace relabel needs rather than confirmed intrinsic external superiority.
