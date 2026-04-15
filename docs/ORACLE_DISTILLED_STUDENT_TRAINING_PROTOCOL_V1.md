# Oracle-distilled stop-vs-act student training protocol v1

## Purpose

This protocol defines the **first real post-pilot training/evaluation path** for the oracle-distilled stop-vs-act student.

It is operational now, but real performance claims still require:
1. real oracle label generation,
2. validator quality-gate pass,
3. selective-distillation preprocessing on non-mock rows,
4. and evaluation against the unchanged default anchor baseline.

---

## 1) Student model in this phase

Student family: the existing lightweight stop-vs-act model family from `experiments.stop_vs_act_controller`.

Initial model choices:
- logistic (default),
- gbdt (optional).

Inference remains **binary ACT vs STOP** using a probability threshold (`decision_threshold`, default `0.5`).

---

## 2) Inputs consumed

Primary input:
- distillation-ready JSONL from `scripts/build_stop_vs_act_oracle_distillation_dataset.py`.

Required fields consumed from each row:
- `hard_label_act`, `teacher_prob_act`, `bucket`, `sample_weight`, `state_id`, `provenance`.

Features:
- preferred: stop-vs-act feature columns directly in row (if present),
- default path: join by `state_id` to `pilot_state_manifest.jsonl` `features` map.

So the training path can be executed as soon as distillation rows + state manifest are available.

---

## 3) Accepted / borderline / rejected handling

Training bucket policy is configurable:
- accepted-only (`--train-buckets accepted`),
- accepted+borderline (`--train-buckets accepted,borderline`) default,
- rejected rows are excluded by default because they typically have zero sample weight and fail trust criteria.

Mechanics in v1:
- rows with `sample_weight <= 0` are dropped from training,
- borderline rows are marked `is_uncertain=1` for existing uncertainty-aware learner options,
- per-row sample weights can be enabled (`--use-sample-weight`).

---

## 4) Binary inference and borderline supervision

Yes, inference remains binary ACT/STOP in v1.

Borderline supervision is used during training via:
1. reduced sample weights (from distillation dataset policy),
2. uncertainty marker (`is_uncertain=1`) so existing uncertain policies (`downweight`, `filter`, etc.) can be reused,
3. optional confidence scaling from `teacher_prob_act`.

This keeps deployment behavior simple while still using uncertainty-aware supervision during fitting.

---

## 5) Losses / weights / targets in v1

v1 is intentionally minimal and reuses existing training internals:

- Primary supervised target: `hard_label_act`.
- Optional row weighting:
  - base from `sample_weight`,
  - optional confidence multiplier from `teacher_prob_act` distance to 0.5.
- Uncertainty policy path: existing `uncertain_policy` option in `fit_stop_vs_act_model`.

No separate soft-label KL head is added in v1; this is deferred to a later version if needed.

---

## 6) Required post-pilot comparisons

Once real validated pilot labels exist, run at least:

1. **Anchor comparison**
   - oracle-distilled student vs unchanged default stop-vs-act anchor baseline.

2. **Bucket policy comparison**
   - accepted-only vs accepted+borderline.

3. **Selective filtering effect**
   - weighted selective training vs weaker filtering alternatives.

Artifacts to produce:
- per-run `oracle_distilled_student_summary.json`,
- multi-run `oracle_distilled_student_comparison.csv` and summary JSON/MD.

---

## 7) Safe vs unsafe claims

Safe after implementing this path:
- repository has a runnable oracle-distilled student train/eval path,
- accepted-only vs accepted+borderline comparison can be executed reproducibly,
- pipeline can be smoke-tested in non-claim mode on mock/test inputs.

Not safe until real pilot labels + evaluation:
- claims of improved accuracy/robustness vs current default anchor baseline,
- claims that selective distillation policy is empirically superior,
- claims that post-pilot phase succeeded at real label quality standards.

---

## Operational scripts

- Train/eval one run:
  - `scripts/train_oracle_distilled_stop_vs_act_student.py`
- Compare multiple runs:
  - `scripts/compare_oracle_distilled_stop_vs_act_runs.py`

These scripts include explicit `non_claim_mode` signaling when mock/non-oracle provenance is detected.
