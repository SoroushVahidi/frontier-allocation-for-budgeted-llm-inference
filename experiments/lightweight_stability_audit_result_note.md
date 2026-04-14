# Lightweight stability audit result note (new-paper, 2026-04-14)

This pass stays entirely on the **new-paper track** and is intentionally bounded/cheap.
No heavy training, no API-backed evaluation, and no binary artifacts were created.

## 1) Audit of current lightweight branch-scoring improvements

Reviewed prior tracked notes and scripts:
- `experiments/lightweight_algorithm_audit_result_note.md`
- `experiments/near_tie_improvement_result_note.md`
- `experiments/near_tie_tiebreaker_result_note.md`
- `experiments/near_tie_tiebreaker_calibration_result_note.md`
- `scripts/run_new_paper_near_tie_pair_pipeline.py`
- `scripts/run_new_paper_near_tie_tiebreaker.py`
- `scripts/run_new_paper_near_tie_tiebreaker_calibration.py`

### Clean common setup selected for multi-seed comparison
To minimize confounds, all variants were compared under a shared bounded protocol:
- same dataset family (`openai/gsm8k` pilot subset)
- same controller budget (`10`)
- same per-seed ranking dataset size (`180` episodes)
- same per-seed controller eval size (`28` examples)
- same near-tie extraction pipeline (`min-signals=1`)
- matched seed list for all methods (`61,62,63,64`)

This keeps the audit focused on **stability/variance** rather than method invention.

## 2) Bounded multi-seed stability run

Output root:
- `outputs/new_paper/lightweight_stability_audit/20260414T193900Z/`

Compared variants:
- `adaptive_bt_pairwise` (baseline proxy BT)
- `adaptive_bt_pairwise_oversample` (near-tie hard-pair oversampling)
- `adaptive_bt_pairwise_two_stage_prev_best` (previous two-stage setting)
- `adaptive_bt_pairwise_two_stage_cal_sweep_least_harm` (calibration sweep least-harm setting: decision stump, compact features, margin 0.06)
- `adaptive_bt_pairwise_oracle` reference row (cheap proxy-oracle-trained BT row)

## 3) Direct answers to the stability questions

### Which variant is most stable?
By raw controller-accuracy standard deviation in this bounded run,
`adaptive_bt_pairwise_oversample` had the smallest std (`0.0505`) — but its **mean delta vs baseline was negative** (`-0.0446`), so this is "stable but stably worse."

Among non-negative-mean variants, the least-harm calibration two-stage variant is the safer experimental branch:
- `adaptive_bt_pairwise_two_stage_cal_sweep_least_harm`
  - mean delta vs baseline: `+0.0446`
  - wins/losses: `2 / 2`
  - near-tie pair mean delta: `+0.0029` (small)

### Was the earlier two-stage +0.10 gain real or likely noise?
Likely **seed-sensitive / small-sample noise**.
- previous-best two-stage now has only small mean uplift (`+0.0179`) with split wins/losses (`2 / 2`) and high delta variance.
- this does **not** support a robust large gain claim.

### Is oversampling consistently harmful?
In this run it is **mostly harmful**:
- wins/losses vs baseline: `1 / 3`
- mean controller delta: `-0.0446`
- mean near-tie slice delta also slightly negative.

So not "always" harmful in every seed, but net-negative and unreliable.

### Is there any robust enough lightweight branch to keep?
Conservative take:
- keep `adaptive_bt_pairwise` as default baseline.
- keep the **least-harm calibrated two-stage** as the only lightweight experimental branch worth continuing, because it is closest to neutral/positive without clear systematic damage.
- treat hard oversampling as a likely dead end unless a strictly bounded reformulation reverses net-negative multi-seed behavior.

## 4) Decision framing for next step

- **Baseline default:** `adaptive_bt_pairwise`
- **Experimental branch worth keeping:** `adaptive_bt_pairwise_two_stage_cal_sweep_least_harm` (diagnostic continuation only)
- **Dead end / stop spending on for now:** hard near-tie oversampling as currently configured

Main value of this pass: clarifying what **not** to over-interpret from single-run gains and where to stop tuning.
