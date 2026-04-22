# NeurIPS Figure and Table Caption Stubs

This file is a lightweight drafting aid for manuscript text. For the authoritative emitted artifact list and regeneration policy, use `docs/NEURIPS_PAPER_ARTIFACTS.md`.

## Main Figures

- **Figure 1.** Fixed-budget frontier allocation setup: questions induce active branches, controllers allocate next-step compute under budget, answer-group-aware commit control selects the final answer.
- **Figure 2.** Macro-averaged budget-performance frontier across GSM8K, MATH-500, and GPQA on the matched manuscript surface; oracle rows provide upper-bound context while manuscript-facing and baseline methods remain mixed rather than universally dominant.
- **Figure 3.** Failure decomposition on the matched manuscript surface from defeat-case subtype proxies, separating tree-generation-like failures from output-layer-like failures; main-paper comparator set is intentionally compact for readability.

## Main Tables

- **Table 1.** Benchmark/method surface used for paper-facing analysis, including datasets, budgets, and canonical metrics.
- **Table 2.** Main frontier comparison at representative budgets with best baseline, promoted line, and oracle context.
- **Table 3.** Oracle headroom summary reporting fixed-baseline gap, promoted-method gap, and promoted/oracle ratio.
- **Table 4.** Anti-collapse summary combining performance and concentration/diversity diagnostics.
- **Table 5.** Failure decomposition summary (proxy basis) across datasets.
- **Table 6.** Robustness and limitations summary, including dataset/budget support and current caveats.
- **Table 7.** Integrated-controller toggle ablation summary on the strict-phased broader matched surface (engineering/implementation decomposition; not the same contract as Appendix Figure A4 / `strict_f3` manuscript-surface component ablation).
- **Table 8.** Compact manuscript-facing method naming/comparison contract (internal labels + display names + role in the paper-facing story).
- **Table 9.** Compact surface-sensitivity decision contract: manuscript-facing winner (`strict_f3`) vs broader operational default (`strict_gate1_cap_k6`) on its separate surface.
- **Table 10.** Compact per-seed stability packaging for `strict_f3` vs `strict_gate1_cap_k6` from existing manuscript decision-bundle artifacts.

## Appendix Figures

- **Appendix Figure A1.** Oracle gap / regret on the matched manuscript surface, with appendix-context baselines beyond the main-paper comparator set where needed for interpretability without crowding the main figure.
- **Appendix Figure A2.** Anti-collapse diagnostic comparison on the matched manuscript surface. Left: repeated same-family case rate (lower indicates less branch-family concentration). Right: average expansions per case (context for interpreting near-zero repetition rates in shallow external trajectories). Methods shown: Strict-F3, Strict-Gate1-Cap-K6, and L1-Max.
- **Appendix Figure A3.** Allocation-composition diagnostic on the matched manuscript surface. Left: stacked average expansions + average verifications with total average actions marker. Right: verification share of actions (%). Methods shown: Strict-F3, Strict-Gate1-Cap-K6, and L1-Max.
- **Appendix Figure A4.** Strict-F3 component-ablation deltas on the matched manuscript-facing surface, plotted as accuracy differences (percentage points) relative to Full Strict-F3. Colors separate Full method, component-removal ablations, and reduced variants. Largest drop appears when repeat-expansion control is removed.
