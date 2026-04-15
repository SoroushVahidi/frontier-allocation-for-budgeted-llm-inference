# Selective distillation plan for oracle ACT-vs-STOP labels (v1)

## Purpose

This note defines the **post-generation distillation policy layer** for oracle ACT-vs-STOP labels.

It is intentionally scoped to the period **before** full pilot-scale oracle labels exist, so it provides:
- concrete bucket definitions,
- concrete student-target handling,
- and concrete validation requirements,
without claiming pilot execution or distillation gains have already happened.

This plan preserves the current default stop-vs-act controller setup as the anchor baseline for all future comparisons.

---

## Phase separation (explicit)

The oracle pipeline is two distinct phases:

1. **Oracle-label generation + validation**
   - produce contract-compliant labels (`q_act`, `q_stop`, `oracle_action_gap`, `oracle_label_act`),
   - run required quality gates,
   - block distillation when gates fail.

2. **Selective distillation** (this note)
   - map validated rows into `{accepted, borderline, rejected}` buckets,
   - apply bucket-specific training treatment,
   - evaluate distilled student against the current default anchor baseline.

No claim about distillation performance is valid until phase (2) is executed on real validated oracle outputs.

---

## 1) Label buckets

This plan uses exactly three buckets:

1. **accepted**
   - high-confidence teacher examples,
   - used for strong supervision.

2. **borderline**
   - uncertain / near-margin examples,
   - used for softer and lower-weight supervision.

3. **rejected**
   - rows failing distillation eligibility,
   - excluded from gradient updates.

---

## 2) Bucket definition policy

A row is assigned by ordered rules (first match wins).

### 2.1 Hard rejection gates (always rejected)

A row is rejected if any condition holds:

1. **Mock/non-oracle marker present** and policy says to reject mock rows.
   - examples: `mock_interface_only=true`, `non_oracle_warning` populated, manifest/row mock marker.
2. **Core fields missing or invalid** for distillation:
   - missing/non-finite `q_act`, `q_stop`, `oracle_action_gap`, invalid `oracle_label_act`.
3. **Contract inconsistency beyond tolerance**:
   - `abs((q_act - q_stop) - oracle_action_gap) > gap_consistency_tolerance`, or
   - `oracle_label_act` sign inconsistent with `oracle_action_gap`.
4. **Audit disagreement / fail status** if present in row metadata:
   - configurable blocked statuses (default: `"fail"`, `"disagree"`, `"hard_fail"`).
5. **Quality-gate fail status** if present in row metadata:
   - configurable blocked statuses (default: `"fail"`, `"blocked"`).

### 2.2 Margin-band policy (accepted vs borderline vs rejected)

For rows not hard-rejected:

- Let `abs_gap = abs(oracle_action_gap)`.
- Use per-row thresholds:
  - `accepted_min_abs_gap`
  - `borderline_min_abs_gap`
- Thresholds come from:
  1. optional **remaining-budget region override** rule (if matched), else
  2. global defaults.

Assignment:

- `abs_gap >= accepted_min_abs_gap` -> **accepted**
- `borderline_min_abs_gap <= abs_gap < accepted_min_abs_gap` -> **borderline**
- `abs_gap < borderline_min_abs_gap` -> **rejected**

### 2.3 Agreement gates inside margin buckets

If `agreement_rate` is present, bucket assignment is down-graded by agreement thresholds:

- accepted also requires `agreement_rate >= accepted_min_agreement`.
- borderline requires `agreement_rate >= borderline_min_agreement`.
- otherwise reject.

This allows conservative use of uncertainty metadata when available, while remaining compatible with rows that do not include agreement estimates.

---

## 3) Training treatment by bucket

### accepted (strong supervision)

- Keep hard ACT/STOP loss active (`hard_loss_weight = 1.0` by default).
- Keep soft teacher loss active (`soft_kl_weight = 1.0` by default).
- Keep sample in training (`sample_weight = 1.0` by default).

### borderline (uncertainty-aware supervision)

- Use reduced hard-label pressure (`hard_loss_weight < accepted`, default `0.35`).
- Keep soft supervision active (`soft_kl_weight`, default `1.0`).
- Lower sample weight overall (`sample_weight`, default `0.5`).
- Set `abstain_target = 1.0` to support future abstain/uncertainty head if introduced.

### rejected

- Drop from optimization (`sample_weight = 0.0`, hard/soft weights `0.0`).
- Keep row in distillation-prep artifact for provenance and auditability.

This preserves a strict no-train path for low-trust rows while still exposing exclusion reasons.

---

## 4) Student targets to preserve from oracle labels

Distillation-prep rows must preserve:

1. **Hard target**
   - `hard_label_act` (`oracle_label_act` copied after consistency check).

2. **Margin target**
   - `oracle_action_gap` (signed) and `abs_oracle_action_gap`.

3. **Soft target**
   - `teacher_prob_act` derived from gap + temperature transform,
   - plus optional raw teacher uncertainty fields if available (`agreement_rate`, `gap_std`, CI).

4. **Audit / quality metadata**
   - row-level audit and quality fields when present,
   - bucket decision reason,
   - source/provenance markers (including mock markers).

These fields make future training objective experiments possible without rebuilding the preprocessing layer.

---

## 5) Validation required before claiming selective distillation helped

No benefit claim is valid unless all checks below pass on real (non-mock) pilot labels:

1. **Generation quality prerequisites**
   - oracle generation gates pass (schema, consistency, paired-randomness, row-count, etc.).

2. **Preprocessing integrity checks**
   - deterministic bucket assignment with fixed policy config,
   - explicit bucket counts and reasons,
   - non-zero accepted bucket count,
   - rejected bucket not trivially 0% unless justified by thresholds.

3. **Training/eval protocol checks**
   - compare against the unchanged default stop-vs-act anchor baseline,
   - same dataset split, same budget protocol, same evaluation script family,
   - at least one sensitivity run for borderline weights/thresholds.

4. **Outcome checks**
   - improvement must appear on declared primary metrics,
   - no severe regression on core safety/robustness diagnostics,
   - report confidence intervals or multi-seed spread where feasible.

---

## 6) Safe vs unsafe claims at current state

### Safe now (after implementing this plan + scaffold)

- Distillation policy is explicitly specified and reproducible.
- The repository can convert contract-compliant oracle rows into distillation-ready rows with selective buckets.
- Oracle generation and oracle distillation phases are now separated in repo process definition.

### Still unsafe now (before real pilot generation + training)

- Any claim that selective distillation improves controller performance.
- Any claim that accepted/borderline thresholds are empirically optimal.
- Any claim that oracle phase is complete beyond operational readiness.

---

## Default v1 policy values (conservative)

- Global thresholds:
  - `accepted_min_abs_gap = 0.12`
  - `borderline_min_abs_gap = 0.04`
- Agreement thresholds (when present):
  - `accepted_min_agreement = 0.70`
  - `borderline_min_agreement = 0.55`
- Region override example (low remaining budget):
  - tighter acceptance threshold (`accepted_min_abs_gap = 0.16`) for `remaining_budget <= 1`.

These defaults are intentionally conservative and should be tuned only after pilot evidence exists.

---

## Operational scaffolding (implemented now)

The policy above is implemented by:

- config: `configs/stop_vs_act_oracle_selective_distillation_v1.json`
- preprocessing tool: `scripts/build_stop_vs_act_oracle_distillation_dataset.py`

Typical invocation after pilot generation/validation:

```bash
python scripts/build_stop_vs_act_oracle_distillation_dataset.py \
  --labels-jsonl <oracle_stop_vs_act_labels.jsonl> \
  --manifest-json <oracle_label_manifest.json> \
  --policy-config configs/stop_vs_act_oracle_selective_distillation_v1.json \
  --output-jsonl <distillation_ready_labels.jsonl> \
  --summary-json <distillation_bucket_summary.json>
```

Optional strict gate for CI/protocol checks:

```bash
python scripts/build_stop_vs_act_oracle_distillation_dataset.py \
  --labels-jsonl <oracle_stop_vs_act_labels.jsonl> \
  --manifest-json <oracle_label_manifest.json> \
  --output-jsonl <distillation_ready_labels.jsonl> \
  --fail-on-any-rejected
```

This does **not** mean rejected rows are always undesirable. The flag is only for strict diagnostics in controlled runs.
