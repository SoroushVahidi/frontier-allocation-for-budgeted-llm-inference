# MULTISTEP branch-utility target bounded follow-up validation status (2026-04-17)

## Canonical framing and bounded scope
This pass stays in canonical **fixed-budget branch-allocation / frontier-allocation** framing and evaluates only the target-horizon fidelity question for deciding which active branch should receive the next unit of compute.

No broad redesign was introduced.

## Insertion points inspected and final implementation choice
Inspected insertion points:
1. `scripts/build_bruteforce_target_regimes.py` (existing multistep target regime path and regime output writer).
2. `scripts/run_multistep_branch_utility_target_experiment.py` (bounded runner already used for k1/k3).
3. `experiments/bruteforce_branch_allocator.py` (reused canonical table prep + model train/eval path without framework drift).
4. Existing output artifacts under `outputs/branch_label_bruteforce_targets/*multistep*` and `outputs/branch_label_bruteforce_learning/*multistep*`.

Final implementation choice:
- Keep the existing multistep path.
- Add **k2** into default regime list in the regime builder.
- Extend the bounded multistep runner to execute a matched 4-mode pass (`baseline_current_matched`, `multistep_k1`, `multistep_k2`, `multistep_k3`) and emit additional diagnostics:
  - horizon trend,
  - per-seed instability summary,
  - k1-vs-k3 statewise disagreement concentration,
  - support-size diagnostics,
  - stricter matched canonical slice summary.

## Exact horizons tested
- `multistep_branch_utility_target_k1`
- `multistep_branch_utility_target_k2`
- `multistep_branch_utility_target_k3`
- matched baseline: `all_pairs` as `baseline_current_matched`

## Exact stricter matched canonical validation used
Stricter matched canonical check = evaluate the same matched run on a stricter canonical hard slice:
- `near_tie_flag == True` **and** `pair_type == adjacent_rank`.

This keeps labels/seed splits matched while tightening to a harder interpretation slice to reduce ambiguity from easier pairs.

## Commands run
```bash
python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417/regime_all_pairs_approx \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id multistep_branch_utility_target_validation_20260417 \
  --pair-strategies all_pairs,multistep_branch_utility_target_k1,multistep_branch_utility_target_k2,multistep_branch_utility_target_k3 \
  --near-tie-margin 0.03

python scripts/run_multistep_branch_utility_target_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/multistep_branch_utility_target_validation_20260417 \
  --run-id multistep_branch_utility_target_validation_eval_20260417 \
  --output-root outputs/branch_label_bruteforce_learning \
  --seeds 11,29,47 \
  --feature-set v3 \
  --near-tie-margin 0.03
```

## Main metrics (matched aggregate)
From `outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_validation_eval_20260417/aggregate_comparison_summary.json`:

- `baseline_current_matched`
  - accepted accuracy: **0.5595**
  - near-tie accepted accuracy: **0.2000**
  - adjacent-rank accepted accuracy: **0.5460**
  - strict matched slice accepted accuracy: **0.1667**
- `multistep_k1`
  - accepted accuracy: **0.5952** (delta vs baseline: +0.0357)
  - near-tie accepted accuracy: **0.2000** (delta: +0.0000)
  - adjacent-rank accepted accuracy: **0.4794** (delta: -0.0667)
  - strict matched slice accepted accuracy: **0.1667** (delta: +0.0000)
- `multistep_k2`
  - accepted accuracy: **0.6230** (delta: +0.0635)
  - near-tie accepted accuracy: **0.6000** (delta: +0.4000)
  - adjacent-rank accepted accuracy: **0.5270** (delta: -0.0190)
  - strict matched slice accepted accuracy: **0.5833** (delta: +0.4167)
- `multistep_k3`
  - accepted accuracy: **0.7063** (delta: +0.1468)
  - near-tie accepted accuracy: **0.6000** (delta: +0.4000)
  - adjacent-rank accepted accuracy: **0.6381** (delta: +0.0921)
  - strict matched slice accepted accuracy: **0.5833** (delta: +0.4167)

### Horizon trend check
- accepted accuracy: k1 **0.5952** → k2 **0.6230** → k3 **0.7063** (monotone increase)
- near-tie accepted accuracy: k1 **0.2000** → k2 **0.6000** → k3 **0.6000** (step-up at k2, then flat)
- adjacent-rank accepted accuracy: k1 **0.4794** → k2 **0.5270** → k3 **0.6381** (monotone increase)

Per-seed instability remains high (accepted-accuracy std):
- baseline: **0.1378**
- k1: **0.2189**
- k2: **0.2409**
- k3: **0.3051**

## Hard-state disagreement analysis (k1 vs k3 best branch)
From `disagreement_diagnostics.json`:
- seed 11:
  - overall disagreement: **1/3 (0.3333)**
  - near-tie states: **1/2 (0.5000)**
  - non-near-tie states: **0/1 (0.0000)**
- seed 29:
  - overall disagreement: **1/3 (0.3333)**
  - near-tie states: **1/2 (0.5000)**
  - non-near-tie states: **0/1 (0.0000)**
- seed 47:
  - overall disagreement: **0/2 (0.0000)**
  - near-tie states: **0/1 (0.0000)**
  - non-near-tie states: **0/1 (0.0000)**

Interpretation: observed k1-vs-k3 target disagreements, where present, are concentrated in near-tie/hard states rather than non-near-tie states, but state denominators are very small.

## Support diagnostics and small-support caveat check
From `support_diagnostics.json`:
- states (test): **3, 3, 2** by seed.
- candidate rows (test): **8, 10, 5** by seed.
- pair rows (test): **7, 12, 4** by seed.
- near-tie test pairs: **2, 5, 1** by seed.
- strict matched slice pairs (`near_tie && adjacent_rank`): **2, 4, 1** by seed.

Explicit caveat:
- all promising hard-slice improvements are supported by tiny denominators; this remains a fragility risk.

## Assumptions and caveats
Assumptions:
1. `best_followup_allocation` index order aligns with per-state candidate branch order.
2. Multistep target is proxy-based and bounded, not exact forced-k continuation rollout.
3. Evaluation is interpreted only within this matched setting (no cross-condition comparisons).

Caveats:
1. Extremely small test supports across seeds make metrics high-variance.
2. Hard-slice gains are directionally encouraging but not yet robust.
3. Disagreement-rate concentration signal is plausible but underpowered.

## Hard conclusion
**Conclusion: promising but not yet trustworthy.**

Reasoning against the success bar:
- Positive: k1→k2→k3 trend is monotone for accepted accuracy, and k1-vs-k3 disagreements are concentrated in hard/near-tie states when disagreements occur.
- Positive: k3 gains survive the stricter matched canonical slice in this bounded run.
- Blocking issue: supports are too small (especially hard-slice denominators), so one-seed/small-sample fragility is still plausible.

Go/no-go decision for this pass:
- **Go as a leading *hypothesis* direction for larger matched follow-up, not as a solved result.**
