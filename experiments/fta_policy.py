"""Failure-Trace Allocator (FTA) — public entry point.

This module exposes the canonical FTA / FIX-2+FIX-4 policy for reviewers,
reproducibility scripts, and tests. It re-exports the implementation from
`experiments/support_aware_selector.py` under stable, paper-facing names.

Paper headline results (Cohere × GSM8K):
  Final-300  (seed=71, budget=6): 260/300 = 86.67%
  Aggregate-720 (seeds 41+61+71): 581/720 = 80.69%
  Verification: outputs/fta_independent_verification_20260527/

Required disclosures:
  1. CI vs pooled ensemble includes zero — do not claim statistical superiority.
  2. Full pool generation costs 4×B=6 = 24 logical calls per example.
  3. Evaluation scope: Cohere × GSM8K only.
  4. Seed=61 component (59.17%) is failure-enriched, not a random sample.
"""

from experiments.support_aware_selector import (
    apply_combined_fix24_to_row as apply_fta_to_row,
    is_low_depth_risk as fta_fix2_trigger,
    is_external_unanimous_against_frontier as fta_fix4_trigger,
    COMBINED_FIX24_POLICY_NAME as FTA_POLICY_NAME,
)

__all__ = [
    "apply_fta_to_row",
    "fta_fix2_trigger",
    "fta_fix4_trigger",
    "FTA_POLICY_NAME",
]
