# Value-aware exact-heavy validation status (2026-04-19)

Primary artifact directory:
- `outputs/branch_label_bruteforce_learning/value_aware_exact_heavy_validation_20260419`

This pass used the matched 5-regime comparison on a larger bounded run (`max_frontier_states=180`) with an exact-heavy filtered slice and explicit reliability / ambiguity diagnostics.

## Required question answers (bounded evidence only)

1. **Does stabilized continuation-minus-commit beat old default on this larger exact-heavy slice?**
   - **No in this run** on pairwise test accuracy: baseline default = `0.8333` vs stabilized = `0.6667`.
   - Expand-vs-commit metrics were tied/uninformative across methods in this slice (`accuracy_test=0.0`, same regret), so pairwise slices dominate interpretation.

2. **Where did gains come from (value-aware, ambiguity-aware, stabilization)?**
   - On this run, value-aware and baseline were tied (`0.8333` pairwise).
   - Adding ambiguity-aware components dropped to `0.6667` and stayed there for decomposed/stabilized variants.
   - In stabilization ablation, repeated estimation helped over no-stabilization (`0.75` vs `0.625` pairwise), while paired-only gave no gain; reliability weighting did not improve over repeated-only in this bounded setting.

3. **Is target variance still the main bottleneck?**
   - **Partially, but not isolated as sole bottleneck here.**
   - Ablation says repeated estimation matters directionally, but reliability diagnostics collapsed to high-reliability-only test rows in this slice, limiting separability of variance vs policy effects.

4. **Is near-tie handling still main residual weakness?**
   - **Yes directionally.**
   - Far-margin is saturated (`1.0`) while near-tie remains lower (`0.6` for stabilized; `0.8` for baseline in this slice).
   - Ambiguity policy sweep (downweight/filter/val-F1 defer-threshold) produced no movement, suggesting current ambiguity policy knobs are underpowered in this bounded setup.

5. **Should repo promote stabilized value-aware as learner-side default now?**
   - **Not yet based on this pass alone.**
   - Prior bounded evidence was positive, but this stronger exact-heavy pass did not reproduce dominance over baseline on main pairwise test metric.
   - Recommendation: keep as a candidate regime, not default lock-in, until a larger exact-heavy replay with stronger test support confirms robustness.

6. **Does learner-side gain transfer to broader diversity/aggregation family?**
   - **Not tested in this pass due pipeline infeasibility.**
   - Existing broad-family confirmation path requires external API execution and has no clean local hook to swap learner-side scoring artifacts in a strictly auditable bounded run.

## Bottleneck status + single best next step

- Learner-side bottleneck is **still partially resolved**.
- New main bottleneck: **near-tie robustness under exact-heavy filtering**, with weak sensitivity to current ambiguity-policy controls.
- Single best next step: run one larger matched replay with higher held-out pair count (same regimes) while explicitly optimizing near-tie objective under a hard far-margin non-regression constraint.
