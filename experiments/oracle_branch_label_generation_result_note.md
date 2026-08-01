# New-paper oracle-ish branch label generation pilot (2026-04-14)

## What was implemented

Implemented a small modular pipeline for **approximate oracle continuation labels** for unfinished frontier branches:

- `experiments/oracle_branch_labels.py`
  - decision-point snapshot selection (`simulate_decision_snapshots`)
  - bounded continuation expansion from each branch (`simulate_rollout`)
  - conservative label computation (`approximate_oracle_continuation_value`)
  - pairwise label derivation and proxy-comparison stats (`generate_oracle_branch_labels`)
  - JSONL writer utility (`write_jsonl`)
- `scripts/run_new_paper_oracle_branch_label_generation.py`
  - run orchestration and config capture
  - required artifact writing under `outputs/new_paper/oracle_branch_labels/<run_id>/`
  - run manifest and interpretation report generation

## Label meaning (honest definition)

Primary label name: `approx_oracle_continuation_value`

Definition:
- For a branch state with remaining budget, evaluate a bounded set of high-budget continuation rollouts.
- Value = **max continuation-outcome value found** across that bounded set.
- The continuation-outcome value is a bounded scalar based on terminal correctness, terminal reachability, and score trajectory.

This is an **approximate oracle-ish** label, not exact.
- Exact only for trivial cases (`branch.is_done` or zero budget), which did not occur in this pilot sample.

## Pilot run

Command:

```bash
python scripts/run_new_paper_oracle_branch_label_generation.py \
  --episodes 20 \
  --decision-budget 9 \
  --max-decisions-per-episode-to-label 3 \
  --max-branches-per-decision 3 \
  --rollouts-per-policy 3 \
  --high-budget-multiplier 1.5 \
  --seed 23
```

Run output directory:
- `outputs/new_paper/oracle_branch_labels/20260414T143819Z/`

Generated files:
- `branch_oracle_labels.jsonl`
- `pairwise_oracle_preferences.jsonl`
- `oracle_label_summary.csv`
- `run_manifest.json`
- `interpretation.md`

## What worked

- Generated bounded oracle-ish labels at scale for a small pilot subset.
- Generated pairwise preferences from continuation labels.
- Captured explicit exact-vs-approximate status.
- Added lightweight oracle-vs-proxy agreement analysis.

## What did not / limitations

- Labels are approximate (bounded policies/rollouts), not exact global continuation optima.
- Pilot distribution is shallow (mostly low-depth snapshots in this setting).
- Agreement analysis is simulator-first; real-model-backed extension remains future work.

## Feasibility and usefulness summary

From `20260414T143819Z` summary:
- decision snapshots: 60
- branch labels: 175
- pairwise labels: 170
- approximate labels: 175 / 175
- oracle-vs-proxy agreement: 0.5235
- oracle-vs-proxy disagreement: 0.4765
- confident disagreements (non-tie oracle margin): 4

Interpretation:
- Feasible to generate in bounded cost on a practical subset.
- Disagreement with proxy labels is substantial enough to justify further investigation as stronger supervision.
- Recommended next step is wider-but-still-bounded expansion (more diverse depth/budget regimes, then selective real-model episodes).
