# Brute-force branch-comparison label generator

## Purpose

This pipeline generates auditable supervision for the core allocation question:

> under remaining budget `B`, which active branch deserves the **next unit of compute**?

It creates three linked target families per frontier state:

1. **Absolute per-branch next-allocation value estimate**
2. **Pairwise branch preference labels**
3. **Branch-vs-outside-option gaps**

This is a branch-allocation target builder (not a stop-centric target builder).

## Script

- `scripts/run_bruteforce_branch_label_generator.py`

## Output artifacts (all under `outputs/branch_label_bruteforce/<run_id>/`)

- `raw_rollouts.jsonl`: expensive rollout-level records for every candidate/continuation sample.
- `state_summaries.jsonl`: one row per frontier state with winner and mode metadata.
- `candidate_labels.jsonl`: one row per (state, candidate branch), including absolute and outside-option labels, plus `features_branch_v1` branch-state features for downstream learning.
- `pairwise_labels.jsonl`: pairwise preferences for each branch pair in a state.
- `progress.json`: resume/progress status.
- `manifest.json`: config dump, counts, file checksums, version metadata.
- `report.md`: human-readable run summary and safe interpretation note.

## Label semantics

For state `s` with remaining budget `B` and active branches `b`:

- `estimated_value_if_allocate_next(b)` approximates
  - spend 1 unit now on `b`
  - then allocate remaining `B-1` units by brute-force (exact) or bounded search (approx)
  - maximize downstream utility estimate.

- Pairwise labels are derived from these per-branch values:
  - `preference = 1` means `branch_i > branch_j`.

- Outside option is the best alternative branch in the same frontier state:
  - `outside_option_value = max_{j != i} estimated_value_if_allocate_next(j)`
  - `branch_vs_outside_gap = estimated_value_if_allocate_next(i) - outside_option_value`.

## Exact vs approximate modes

### Exact mode

Used when feasible on tiny states.

- Enumerates all integer allocations of `B-1` budget units across branches (all compositions).
- Evaluates each allocation via repeated expensive rollout samples.
- Picks the highest-valued continuation exactly over that finite allocation set.

Guardrails:

- `--max-exact-branches`
- `--max-exact-remaining-budget`

If a state exceeds these bounds, the run automatically falls back to approximate mode.

### Approximate mode

Used for larger states.

- Samples bounded subsets of possible `B-1` allocations (`--max-allocation-samples`).
- Runs repeated expensive rollout estimates per sampled allocation.
- Uses the best sampled continuation as a bounded near-brute-force estimate.

## Reproducibility and auditability

- Deterministic seed flow for state capture and rollout seeds.
- Full config written into `manifest.json`.
- SHA256 checksums for all primary output JSONL files.
- Resume support via `--resume` and `state_summaries.jsonl` state-id skipping.
- Version marker: `branch_label_bruteforce_v1`.

## Safe claims

Safe:

- these are expensive simulated continuation labels for branch-comparison supervision,
- they are budget-conditioned and opportunity-cost-aware within each frontier state,
- exact mode is exact only for the explicitly enumerated finite allocation space.

Not safe:

- claiming real-model global oracle truth,
- claiming exactness outside configured exact-feasibility bounds,
- claiming universal optimality across all datasets/controllers without matched evaluation.

## Quick pilot run

```bash
python scripts/run_bruteforce_branch_label_generator.py \
  --run-id pilot_small \
  --max-frontier-states 12 \
  --episodes-per-example 1 \
  --frontier-budget 5 \
  --min-remaining-budget 2 \
  --max-remaining-budget 4 \
  --rollout-samples-per-candidate 6 \
  --max-allocation-samples 12
```

## Long heavy run

```bash
python scripts/run_bruteforce_branch_label_generator.py \
  --run-id heavy_bruteforce_gsm8k \
  --dataset-name openai/gsm8k \
  --max-frontier-states 2000 \
  --episodes-per-example 3 \
  --frontier-budget 10 \
  --min-remaining-budget 2 \
  --max-remaining-budget 6 \
  --init-branches 5 \
  --max-branches-per-state 5 \
  --rollout-samples-per-candidate 64 \
  --max-allocation-samples 256 \
  --seed 17
```

To force exact mode where feasible:

```bash
python scripts/run_bruteforce_branch_label_generator.py \
  --run-id exact_tiny \
  --exact-mode \
  --max-exact-branches 4 \
  --max-exact-remaining-budget 5
```

Resume a long run:

```bash
python scripts/run_bruteforce_branch_label_generator.py --run-id heavy_bruteforce_gsm8k --resume
```
