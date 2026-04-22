# NeurIPS Figure and Table Caption Stubs

## Main Figures

- **Figure 1.** Fixed-budget frontier allocation setup: questions induce active branches, controllers allocate next-step compute under budget, answer-group-aware commit control selects the final answer.
- **Figure 2.** Macro-averaged budget-performance frontier across GSM8K, MATH-500, and GPQA; oracle provides upper-bound context while promoted and baseline methods remain mixed rather than universally dominant.
- **Figure 3.** Macro gap-to-oracle by budget, consistent with Figure 2 and highlighting remaining headroom for non-oracle methods.
- **Figure 4.** Allocation composition for the promoted line, showing expansion-versus-verification budget usage across compute budgets.
- **Figure 5.** Anti-collapse diagnostics (entropy and concentration) indicating how controller behavior changes with budget and method choice.
- **Figure 6.** Failure decomposition from defeat-case subtype proxies, separating tree-generation-like failures from output-layer-like failures.
- **Figure 7.** Per-dataset frontier summary across canonical multi-dataset surface, showing dataset-dependent rankings and no universal winner claim.

## Main Tables

- **Table 1.** Benchmark/method surface used for paper-facing analysis, including datasets, budgets, and canonical metrics.
- **Table 2.** Main frontier comparison at representative budgets with best baseline, promoted line, and oracle context.
- **Table 3.** Oracle headroom summary reporting fixed-baseline gap, promoted-method gap, and promoted/oracle ratio.
- **Table 4.** Anti-collapse summary combining performance and concentration/diversity diagnostics.
- **Table 5.** Failure decomposition summary (proxy basis) across datasets.
- **Table 6.** Robustness and limitations summary, including dataset/budget support and current caveats.

## Appendix Figures

- **Appendix Figure A2.** Anti-collapse diagnostic comparison on the matched manuscript surface. Left: repeated same-family case rate (lower indicates less branch-family concentration). Right: average expansions per case (context for interpreting near-zero repetition rates in shallow external trajectories). Methods shown: Strict-F3, Strict-Gate1-Cap-K6, and L1-Max.
- **Appendix Figure A3.** Allocation-composition diagnostic on the matched manuscript surface. Left: stacked average expansions + average verifications with total average actions marker. Right: verification share of actions (%). Methods shown: Strict-F3, Strict-Gate1-Cap-K6, and L1-Max.
- **Appendix Figure A4.** Strict-F3 component-ablation deltas on the matched manuscript-facing surface, plotted as accuracy differences (percentage points) relative to Full Strict-F3. Colors separate Full method, component-removal ablations, and reduced variants. Largest drop appears when repeat-expansion control is removed.
- **Appendix Figure (Output-layer repair).** On the subset where correct internal reasoning is already present in the tree, deterministic output-layer repair materially improves surfaced-answer correctness; on the full current 20-case failure slice, the remaining unresolved portion indicates a broader upstream tree-generation bottleneck.
