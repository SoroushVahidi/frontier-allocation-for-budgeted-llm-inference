# PAPER_SOURCE_OF_TRUTH

This file defines the authoritative evidence hierarchy for anonymous review.

## Evidence hierarchy

1. **Paper-facing canonical evidence** (eligible for headline claims)
2. **Appendix/supporting evidence** (robustness, diagnostics, context)
3. **Exploratory/provenance-only evidence** (negative/partial/historical)
4. **Non-review/private/local-only artifacts** (never claim-bearing)

## Canonical paper-facing outputs

Canonical paper tables/figures are generated from:
- `scripts/paper/run_all_neurips_paper_artifacts.py`

Canonical output directories:
- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

## Method-surface contract (claim-critical)

- Manuscript-facing matched-surface representative: `strict_f3`.
- Broader operational default on a different surface: `strict_gate1_cap_k6`.
- The `strict_f3` vs `strict_gate1_cap_k6` matched-surface margin is currently fragile/non-decisive and should not be phrased as decisive superiority.

## Claim eligibility rules

A claim is paper-facing only if:
- it is supported by the canonical output directories above,
- its comparison uses an explicit matched contract (e.g., matched maximum action-budget contract and matched-action adapters), and
- wording matches `docs/CLAIM_BOUNDARIES.md`.

## Real-model evidence rule

Real-model provider runs are **supporting/diagnostic real-model audits** only. They are **not evidence of universal dominance** and are **not token/latency/cost matched unless explicitly stated**.

### Cost-normalized Cohere validation slices (diagnostic)

Bundles such as `outputs/cohere_real_model_cost_normalized_validation_<timestamp>/` are **diagnostic** unless a canonical promotion doc explicitly upgrades them.

**Mock-backed vs verifier-backend provenance:** Some selectors support a mock verifier default (e.g. DR-v2 outcome-verifier rerank). Treat timestamps where the verifier backend env was **unset** as **mock-backed diagnostic provenance** only. A separate timestamp with `DR_V2_OV_RERANK_VERIFIER_BACKEND=cohere` is required before claiming a **real Cohere outcome-verifier** backend experiment. See `docs/OUTPUTS_ARTIFACT_INDEX.md`.

## Non-review/private/local-only class

Artifacts in local-only folders, machine-specific caches, temporary debug outputs, and private execution environments are non-review evidence. They must never be used as claim-bearing manuscript evidence unless promoted through canonical documented regeneration.
