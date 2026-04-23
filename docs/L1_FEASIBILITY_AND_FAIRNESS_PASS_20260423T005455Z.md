# L1 Feasibility and Fairness Pass (20260423T005455Z)

## Purpose
Bounded audit to decide whether L1 should be the next full-strength external baseline implementation target for manuscript-facing comparison.

## Exact L1 path inspected
- In-repo integration docs/config/scripts: `external/l1_length_control_rl/README.md`, `docs/l1_baseline_integration.md`, `scripts/run_l1_baseline.py`, `scripts/verify_l1_mode_b_import.py`, `configs/l1_inference_adapter_v1.json`, `configs/l1_official_full_adapter_v1.json`, `experiments/controllers.py`.
- Canonical matched-surface artifacts: `outputs/matched_surface_multiseed_main_comparison_20260423T002000Z/`.
- Official fidelity references: project page `https://cmu-l3.github.io/l1/`; official repo `https://github.com/cmu-l3/l1`.

## Feasibility classification
**not_worth_strengthening_now**

## Fairness-contract analysis
- Canonical matched surface exists and includes L1 rows, but canonical raw rows do not expose the required realized token accounting separation (requested budget vs realized reasoning tokens vs final answer tokens vs total generated tokens).
- Current MODE A lane is explicitly adapter-style (inference-only) and should not be overclaimed as official RL reproduction.
- MODE B lane is import-validated only; without supplied official artifacts it remains blocked for defensible head-to-head use.

## Backbone-match analysis
- MODE A can run on a close/same substrate backbone for fair adapter-style comparison.
- Official L1 checkpoint comparisons are not currently integrated as an in-repo runnable path on the canonical surface; any such row is adjacent/import-based and vulnerable to mismatch attacks.

## Placement recommendation
- Main table: **No**.
- Appendix only: **Not recommended as a next strengthening target in current state**.
- Related-work/discussion: **Yes (preferred now)**.

## Exact recommended manuscript wording
> We include L1 as a length-control reference with conservative scope. In this repository, the runnable L1 lane is an inference-only adapter (Exact/Max prompting) rather than official LCPO training reproduction, and official/full L1 rows require externally provided artifacts under a separate import-validated path. Given current canonical-surface token-accounting limits, we do not use this lane for strong primary claims.

## Recommendation on next full implementation target
**Do not prioritize full L1 strengthening next.**

Single biggest blocker: canonical-surface realized-length accounting and official-checkpoint comparability are not yet closed enough for reviewer-proof claims.

Next action if revisited later: first upgrade canonical matched-surface schema to record requested vs realized reasoning/final/total token counts per example and require verified official import package before re-evaluating promotion.
