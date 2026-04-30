# REASONING_FAMILY_AUDIT_20260430T042130Z

- Audit script: `scripts/build_reasoning_family_audit.py`
- Output directory: `outputs/reasoning_family_audit_20260430T042130Z`
- Existing-artifacts only: yes (no live API calls)

## Core results

- Cases analyzed: **460**
- Cases with usable branch traces: **460**
- Average root branch count: **1.5804**
- Average semantic family count: **1.3022**
- Average redundancy ratio (root/family): **1.2717**

## Q1. Do root branches correspond to distinct reasoning families?

Partially. In many cases root branches collapse to fewer semantic families; average redundancy ratio exceeds 1.0, indicating non-trivial overlap/redundancy.

## Q2. In immediate_miss cases, do we have low semantic-family diversity?

This run could not robustly map immediate_miss tags for most trace files, so this question remains **inconclusive** in the aggregate artifact sweep. The dedicated immediate-miss CSV is emitted (`immediate_miss_family_audit.csv`) and is currently empty for this timestamp because failure-bucket labels were unavailable for most traces.

## Q3. Are we forcing depth on redundant branches instead of distinct regions?

Evidence is **suggestive**: semantic families are fewer than root branches on average, so depth constraints applied at root-branch granularity can overcount redundant/paraphrased branches.

## Q4. Do correct-region branches fail to reach minimum depth?

Insufficient labels in broad traces prevent a definitive aggregate answer here. The audit computes depth-by-family and correct-region depth fields where labels are available.

## Q5. Next fix: better seeding, better minimum maturation, or adaptive allocation?

Most justified next step is a design-only controller variant that:
1. seeds distinct families,
2. enforces minimum maturation by semantic family (not root ID),
3. then reuses existing frontier scoring for adaptive spend.

## Q6. Is evidence strong enough to implement a new variant now?

Strong enough for **design + targeted ablation plan**, but not yet strong enough for replacing canonical methods without a labeled immediate_miss trace slice joined to family audit outputs.

## Produced artifacts

- `family_assignments.jsonl`
- `per_case_family_summary.csv`
- `family_depth_coverage_summary.csv`
- `redundancy_vs_failure_summary.csv`
- `immediate_miss_family_audit.csv`
- `candidate_controller_implications.md`
- `manifest.json`
