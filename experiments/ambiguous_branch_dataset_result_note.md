# Ambiguous branch dataset result note (new-paper track)

Date: 2026-04-14  
Run: `outputs/new_paper/ambiguous_branch_dataset/20260414T235500Z`

## Goal
Build a bounded, text-only supervision/evaluation asset focused on hard branch comparisons:
- near-ties,
- weak separation / uncertainty,
- proxy-vs-oracle-ish disagreement,
- proxy-BT vs Rao-Kupper disagreement.

## Inputs audited and used
- Pairwise data path:
  - `scripts/build_v3_ranking_dataset.py`
  - `scripts/build_bt_pairwise_branch_dataset.py`
- Pairwise models:
  - `scripts/train_bt_pairwise_branch_scorer.py` (BT baseline + Rao-Kupper tie-aware)
- Oracle-ish branch/pair labels:
  - `scripts/run_new_paper_oracle_branch_label_generation.py`
- Existing near-tie extraction logic referenced for hard-signal criteria:
  - `scripts/run_new_paper_near_tie_pair_pipeline.py`
- Prior context notes:
  - `experiments/tie_aware_bt_result_note.md`
  - `experiments/tie_aware_bt_stability_result_note.md`
  - `experiments/raokupper_resolution_audit_result_note.md`

## Curated dataset artifact set
- `ambiguous_branch_pairs.jsonl`
- `ambiguous_branch_pairs_summary.csv`
- `ambiguous_branch_dataset_schema.json`
- `method_agreement_on_ambiguous_pairs.csv`
- `ambiguous_slice_comparison.md`
- `interpretation.md`
- `run_manifest.json`

All under: `outputs/new_paper/ambiguous_branch_dataset/20260414T235500Z/`.

## Counts and composition
- Curated pairs: **520**
- Source mix:
  - pairwise BT dataset: **426**
  - oracle pairwise labels: **94**
- Quality tiers:
  - Tier A: **46**
  - Tier B: **223**
  - Tier C: **251**
- Dominant inclusion reasons:
  - `near_tie`: **487**
  - `bt_raokupper_disagree`: **182**
  - `proxy_oracle_disagree`: **63**
  - `raokupper_oracle_disagree`: **45**
  - `bt_oracle_disagree`: **42**

## Hard-slice evaluation (oracle-referenced non-tie pairs)
- Oracle-referenced evaluated pairs: **60**
- Agreement with oracle-ish reference:
  - proxy preference: **0.383**
  - proxy BT: **0.300**
  - Rao-Kupper: **0.250**

Interpretation: both learned lightweight methods struggle on this hard slice; in this bounded run Rao-Kupper does not outperform proxy BT here.

## Direct decision answers
- Can we isolate a high-value ambiguous set from existing artifacts? **Yes.**
- Are the cases numerous enough and clean enough to matter? **Numerous enough for targeted evaluation, but still noisy (not gold).**
- Does proxy BT fail enough to justify targeted supervision? **Yes on oracle-referenced hard slice (low agreement).**
- Does Rao-Kupper help on these cases? **Not in this bounded comparison; it was below proxy BT on oracle-referenced hard cases.**
- Is this likely the best next low-compute asset? **Yes, as an evaluation/inspection and targeted-supervision resource (not as immediate default-switch evidence).**

## Conservative conclusion
This dataset should be treated as a **high-value hard-case curation asset**, not a gold benchmark. Its strongest immediate value is:
1. targeted diagnostics,
2. manual pair inspection,
3. future low-compute supervision experiments focused on ambiguous comparisons.
