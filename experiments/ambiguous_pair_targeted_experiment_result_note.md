# Ambiguous-pair targeted experiment result note (new-paper track)

Date: 2026-04-15  
Run: `outputs/new_paper/ambiguous_pair_targeted_experiment/20260415T003000Z`

## Goal
Test one cheap targeted adaptation path that uses the curated ambiguous-branch dataset for hard-case improvement:
- keep baseline path intact,
- compare proxy BT, Rao-Kupper, and a targeted variant,
- check hard-slice gains vs any overall regressions.

## Targeted method tested
- Start from curated ambiguous dataset asset generated inside this run.
- Build a reweighted train set by duplicating ambiguous train pairs (`repeat_factor=4`).
- Train a lightweight BT model on that reweighted set (`targeted_bt_reweighted`).
- Keep comparison baselines unchanged:
  - proxy BT
  - Rao-Kupper (`tie_or_uncertain`)

## Main outputs
- `method_metrics.csv`
- `ambiguous_slice_comparison.csv`
- `overall_vs_ambiguous_summary.csv`
- `run_manifest.json`
- `interpretation.md`

## Key results
- Oracle-referenced ambiguous slice (n=39):
  - proxy BT agreement: **0.410**
  - Rao-Kupper agreement: **0.359**
  - targeted BT reweighted agreement: **0.462**
- Overall bounded controller mean accuracy (2 seeds, subset 18):
  - proxy BT: **0.556**
  - Rao-Kupper: **0.472**
  - targeted BT reweighted: **0.500**

## Direct answers
- Can curated ambiguous data improve the hard slice? **Yes (in this run, targeted > proxy BT > Rao-Kupper on ambiguous oracle-referenced pairs).**
- Does targeted adaptation help more than earlier lightweight patches? **On this hard slice, yes vs Rao-Kupper and proxy BT; but evidence is still small/bounded.**
- Does it hurt overall performance? **Yes, slight overall regression vs proxy BT in this bounded controller check.**
- Is the dataset mainly evaluation-only or also adaptation-useful? **Both; strongest immediate value is evaluation/diagnostics, with adaptation signal that currently trades off against overall performance.**
- Should this be the main next low-compute direction? **Yes, but as constrained hard-slice adaptation work with explicit guardrails against overall regression.**

## Conservative conclusion
This run suggests the ambiguous dataset is a useful **training/evaluation** resource, not just evaluation-only. However, the tested reweighting path improves hard cases while losing some overall accuracy. The next low-compute step should stay in this direction but focus on safer adaptation policies (e.g., weaker weighting, gating, or selective deployment) to preserve overall performance.
