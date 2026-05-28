# PAPER_SOURCE_OF_TRUTH

**Last updated:** 2026-05-28 — FTA canonical. Prior `strict_f3` content archived below.

This file defines the authoritative evidence hierarchy for the manuscript submission.

## Current manuscript method

**Failure-Trace Allocator (FTA)** — implementation: `apply_combined_fix24_to_row()` in
`experiments/support_aware_selector.py` (also accessible via `experiments/fta_policy.py`).

| Result | Value | Evidence |
|---|---|---|
| Final-300 (seed=71, Cohere × GSM8K, budget=6) | **86.67% (260/300)** | Independently verified |
| Aggregate-720 (seeds 41+61+71) | **80.69% (581/720)** | Source-stratified CI lo > 0 vs all externals |
| Leakage audit | **PASS** | Gate features gold-free at runtime |
| Post-generation model calls | **0** | Selection only |

Primary verification artifact:
`outputs/fta_independent_verification_20260527/run_20260527T003000Z/FTA_INDEPENDENT_VERIFICATION_REPORT.md`

## Evidence hierarchy

1. **Paper-facing canonical evidence** (eligible for headline claims)
2. **Appendix/supporting evidence** (robustness, diagnostics, context; e.g. D9 gated selector CV)
3. **Exploratory/provenance-only evidence** (negative/partial/historical)
4. **Non-review/private/local-only artifacts** (never claim-bearing)

## Canonical paper-facing outputs

Canonical paper tables/figures are generated from:
```bash
python scripts/paper/reproduce_current_manuscript_artifacts.py
# or equivalently:
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Canonical output directories:
- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

## Method contract (claim-critical)

- Manuscript-facing method: **FTA / FIX-2+FIX-4** (`direct_reserve_semantic_frontier_v2` + gate).
- Budget contract: each candidate-producing method runs with B=6 logical calls. FTA is a
  post-generation selector — it adds zero model calls after candidates exist.
- Full pool (frontier + L1 + S1 + TALE) generation costs **4 × B = 24 logical calls per example**.

## Claim eligibility rules

A claim is paper-facing only if:
- it is supported by the canonical output directories above or by
  `docs/CURRENT_CANONICAL_STATE_20260527.md`,
- its comparison uses an explicit matched inference-budget contract, and
- it respects the required disclosures in Section 5 of `docs/CURRENT_CANONICAL_STATE_20260527.md`.

## Real-model evidence rule

Real-model provider runs are **supporting/diagnostic audits** only. They are **not evidence of
universal dominance** and are **not token/latency/cost matched unless explicitly stated**.

Artifacts in local-only folders, machine-specific caches, temporary debug outputs, or private
execution environments are non-review evidence. They must never be used as claim-bearing
manuscript evidence unless promoted through canonical documented regeneration.

## Historical content (archived 2026-05-28)

Prior manuscript-facing method was `strict_f3`. That claim is superseded by FTA. The
`strict_f3` vs `strict_gate1_cap_k6` margin was non-decisive and must not appear in the
current manuscript. See `archive/` for historical scripts.
