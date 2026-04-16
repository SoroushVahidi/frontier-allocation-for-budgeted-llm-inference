# Current bottlenecks (canonical)

## Primary bottleneck

The primary bottleneck is **supervision target quality / proxy-label mismatch** for the **next-step branch-allocation decision**.

## Why this dominates now

The project is no longer blocked mainly by lack of infrastructure. The repo already contains controllers, audits, dataset tooling, oracle-label pilot paths, and real-model pilot pathways.

The weaker point is that current labels or target approximations still do not capture the decision we care about with enough fidelity:

> **Which active branch should receive the next unit of compute?**

A local “continue this branch or not” question can still be useful, but only as a simplified proxy for the richer allocation problem.

## How the bottleneck appears in practice

- noisy branch-comparison targets,
- unstable near-threshold local decisions,
- shallow local comparator definitions,
- limited calibration transfer across budgets / seeds / datasets,
- controller wins that are promising but not yet consistently robust,
- under-spend or misallocated spend even when budget headroom exists.

## Explicit non-bottlenecks for the current phase

The main problem is **not** primarily:
- infrastructure completeness,
- lack of additional controller variants,
- lack of heavier models,
- or inability to run broader sweeps.

These may matter later, but they are not the highest-leverage next fix.

## Canonical near-term response

1. Improve branch-comparison and next-step allocation target design.
2. Make local comparator semantics more opportunity-cost-aware.
3. Continue uncertainty-aware filtering / reweighting.
4. Re-run matched controller comparisons against strong heuristics and BT baseline.
5. Use broader scaling only after target-quality improvements are visible.

## Practical consequence

The next efficient progress is expected to come from **better branch-allocation supervision and cleaner comparator design**, not from immediately scaling compute or model size.

## Evidence update from medium brute-force label run (2026-04-16)

- The supervision-data bottleneck has been **materially reduced but not removed** by a real medium-scale GSM8K run (`outputs/branch_label_bruteforce/gsm8k_medium_20260416/`), with hundreds of candidate/pairwise labels.
- Approximate labels show strong bounded alignment to exact tiny-state labels (winner agreement 0.956 on overlapping feasible states), supporting approximate mode as a practical supervision source.
- Remaining bottleneck shape: many non-negligible near-tie/low-margin comparisons and only moderate downstream pilot learner accuracy, indicating target noise/calibration issues still matter.
- Therefore the bottleneck status is best described as **partially resolved**.
