# Current method summary and gaps

## Purpose

This note is the compact repository-facing summary of the **current canonical function stack**.

It is intentionally aligned with the current phase:
- fixed-budget next-step branch allocation,
- target/objective consolidation,
- continuation-value core plus bounded completion-aware correction.

It is not a broad new-method proposal.

## Current canonical method picture

The current strongest repository-wide decomposition is:

1. **Core objective**: maximize final decision quality under fixed budget.
2. **Core expansion score**: continuation-centered branch utility (current default: multistep-k3 family).
3. **Core incumbent/commit-quality score**: bounded completion/current-branch quality evidence.
4. **Core decision rule**: metalevel expand-vs-commit comparison with bounded local correction in disagreement slices.
5. **Local modifiers only**: near-tie/instability/uncertainty gates and bounded policy overlays.

In short:

> **fixed-budget utility objective + continuation-centered expansion + bounded completion-aware incumbent correction + explicit expand-vs-commit metarule.**

## What remains strong

### 1) Framing
The frontier-allocation / next-step branch-allocation framing remains the right project center.

### 2) Expansion signal
Continuation-value-centered supervision remains the strongest default core signal.

### 3) Hard-slice insight
Near-tie and disagreement slices continue to show distinct behavior; bounded completion-aware evidence is real and useful there.

### 4) Observability
Fresh observability-enabled runs now support semantic mismatch adjudication rather than proxy-only diagnosis.

## What is now demoted from canonical default role

The following are still useful artifacts but no longer the top-level repository default:
- broad nearby target-family sweeps as the default next move,
- treating completion-aware scoring as a global replacement objective,
- treating instability/defer mechanisms as the primary optimization target,
- older pairwise+fallback-only summaries as repository-wide canonical framing.

## Main unresolved gap

The key unresolved gap is now narrow and explicit:

> **freeze and validate the exact metalevel decision definition for hard close-call states among expand(i), expand(j), and commit-now/defer.**

Concretely this includes:
- formal commit-now thresholding relative to best expansion,
- bounded correction conditions for continuation-vs-completion disagreement,
- calibration of local ambiguity gates without objective drift.

## Recommended immediate next work

1. Keep the canonical function split fixed across docs/scripts.
2. Continue disagreement-slice adjudication using observability-enabled case evidence.
3. Stabilize a single explicit metalevel decision template (expand-vs-commit with bounded correction).
4. Treat exploratory target families as diagnostics unless and until they beat the canonical stack on accepted metrics.

## Cross-reference

For the canonical function inventory and classification table, use:
- `docs/FUNCTIONS_AND_OBJECTIVES_STATUS_2026_04_18.md`
- `outputs/function_audit_20260418/function_inventory.json`
- `outputs/function_audit_20260418/canonical_function_stack.json`
