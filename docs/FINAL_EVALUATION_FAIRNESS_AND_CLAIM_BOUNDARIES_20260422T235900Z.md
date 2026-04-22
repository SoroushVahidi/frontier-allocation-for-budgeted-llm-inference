# Final evaluation fairness and claim boundaries (20260422T235900Z)

## What reviewers can trust

- The canonical manuscript method remains **`strict_f3`**; this pass does not supersede that lock.
- The main external comparison claim is anchored to the canonical matched near-direct surface and the strongest fair external baseline found there.
- The direct/near-direct fairness layer is now artifact-backed via `outputs/fairness_audit_direct_baselines/20260422T235900Z/` (contract matrix, claim-safety matrix, caveats, and recommendation split).
- The strongest-external loss-analysis tightening uses all available strict losses from the canonical surface (**56**) without fabrication.

## Why baselines are separated into groups

- **Near-direct (main ranking eligible):** shared matched substrate and evaluation conventions (adapter-based external lanes under aligned action-budget accounting).
- **Adjacent (appendix table):** scientifically relevant but non-equivalent control spaces (routing, verifier-centric, solve-vs-verify, search-adjacent).
- **Discussion-only (related work):** important papers lacking a fair runnable comparison lane in this repository.
- **Unofficial caveated lane:** Q*-style adapter is explicitly separated and footnoted, never merged into official Q* claims.

## Safe main claims

Use the following exact language in manuscript-facing text:

1. **Primary claim:**
   > "On the canonical matched near-direct surface, `strict_f3` outperforms the strongest fair external baseline (`external_l1_max`) by **0.161111 mean accuracy**."

2. **Scope claim:**
   > "Main-table ranking is restricted to in-house `strict_f3` plus near-direct external adapter baselines (`external_s1_budget_forcing`, `external_tale_prompt_budgeting`, `external_l1_exact`, `external_l1_max`) evaluated under shared substrate conventions."

3. **Failure-analysis claim:**
   > "Against the strongest fair external baseline, the canonical strict-loss bundle contains **56** losses for `strict_f3`, dominated by `absent_from_tree` with a secondary `present_not_selected` slice."

## Limitations and caveats

Use the following caveat language in captions/footnotes/appendix:

- "External baselines in the main table are **inference-only adapter comparisons** on a matched substrate; this is not a claim of full official training-stack reproduction."
- "Adjacent baselines are reported in a separate table and are not merged into the near-direct ranking because control spaces are non-equivalent."
- "Discussion-only papers are cited for context and blockers, not ranked as integrated empirical baselines."
- "Q*-style adapter rows, if shown, are unofficial/caveated and must not be framed as official Q* reproduction evidence."

## What remains future work

- Expand official full-stack reproductions (MODE B or paper-faithful stacks) only where provenance and runnable contracts can be validated end-to-end.
- Reduce strict losses by improving branch-generation recall (`absent_from_tree`) and branch-selection calibration (`present_not_selected`).
- Keep taxonomy-locked separation to avoid overclaims when adding future baseline families.

## Reviewer-facing recommendation

The current package is strong enough for reviewer-facing use now because it is:
- fair on the near-direct claim surface,
- taxonomy-separated for non-equivalent methods,
- caveat-explicit,
- and fully artifact-backed for reproducibility.
