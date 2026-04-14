# Pairwise branch-comparison diagnostic audit note (new-paper track)

This note tracks the **lightweight diagnostic-only** audit for why current pairwise branch-comparison is still limited.

## Command (cheap run)

```bash
python scripts/run_new_paper_pairwise_diagnostic_audit.py \
  --episodes 220 \
  --budget 8
```

## Latest diagnostic run

- Run dir: `outputs/new_paper/pairwise_diagnostic_audit/20260414T140600Z`
- Main artifacts:
  - `pairwise_diagnostic_summary.md`
  - `pairwise_diagnostic_summary.json`
  - `lightweight_diagnostics.csv`

## Key findings

- Biggest weakness in this pass: **pair-confidence low dynamic range** (confidence clustered in a narrow high band, weak separation power).
- Related issue: pairwise labels are still strongly tied to crude score-like proxies (`node_3_score` agreement is high), indicating limited incremental information from richer pair context.
- External warm-start remains useful as a weak prior but still mismatched to project-specific pairwise/allocation targets.

## Practical next lightweight step

- Keep compute cheap and try only:
  1. confidence recalibration / wider confidence spread for pair selection, and
  2. soft-targeting or dropping uncertain pairs (`tie_or_uncertain==1`) before re-checking the same diagnostics.

## What to avoid next

- Avoid heavy external multitask training and large API-backed evaluations until label-quality/confidence diagnostics improve.
