# Current bottlenecks (canonical)

## Primary bottleneck

The primary bottleneck is **supervision target quality / proxy-label mismatch** for allocation decisions.

## Why this dominates now

The project is no longer blocked mainly by lack of infrastructure. The repo already contains controllers, audits, dataset tooling, oracle-label pilot paths, and real-model pilot pathways.

The weaker point is that current labels or target approximations still do not capture the local decision we care about with enough fidelity:

> **Should the next unit of compute be spent here, or preserved for later use elsewhere?**

## How the bottleneck appears in practice

- noisy ACT-vs-STOP deltas,
- unstable near-threshold behavior,
- shallow STOP semantics,
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

1. Improve action-conditional target design for stop-vs-act.
2. Make STOP semantics more opportunity-cost-aware.
3. Continue uncertainty-aware filtering / reweighting.
4. Re-run matched controller comparisons against strong heuristics and BT baseline.
5. Use broader scaling only after target-quality improvements are visible.

## Practical consequence

The next efficient progress is expected to come from **better local supervision and cleaner comparator design**, not from immediately scaling compute or model size.
