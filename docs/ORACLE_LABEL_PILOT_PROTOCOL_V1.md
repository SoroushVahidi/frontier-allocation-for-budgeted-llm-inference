# Oracle-label pilot protocol v1 (execution-ready, small first run)

## Purpose

This protocol defines the **first small offline oracle-label pilot** for stop-vs-act supervision.

It is execution-ready but intentionally limited in scope. It does **not** claim the heavy phase has already run.

---

## 1) Exact label to generate

For each sampled stop-vs-act decision state, generate:
- `q_act`: teacher estimate of value if we spend one action on the current branch now,
- `q_stop`: teacher estimate of value if we do not spend on the current branch now and preserve/reallocate that compute,
- `oracle_action_gap = q_act - q_stop`,
- `oracle_label_act = 1 if oracle_action_gap > 0 else 0`.

Optional confidence metadata should be included when available (`gap_std`, `gap_ci_low`, `gap_ci_high`, `agreement_rate`).

---

## 2) ACT path

From the same snapshot `(state, remaining_budget)`:
1. force one action on `current_branch_id` at step 1,
2. then continue for horizon `h` under the teacher allocation policy,
3. keep global budget accounting unchanged from the snapshot semantics.

---

## 3) STOP path

From the same snapshot `(state, remaining_budget)`:
1. do **not** spend on `current_branch_id` at step 1,
2. preserve that compute and let the same teacher policy allocate it naturally,
3. continue for the same horizon `h` under the same budget accounting.

STOP is explicitly a **preserve-and-reallocate** counterfactual, not branch-local inactivity.

---

## 4) Teacher/oracle procedure

Teacher mode for pilot v1:
- `offline_policy_coupled_oracle_rollout`
- paired common-random-number rollouts per state for ACT/STOP futures,
- deeper rollouts than lightweight passes,
- same initial snapshot, same policy family, same horizon, same budget context.

Per-state estimation rule:
- run `N` paired rollouts,
- estimate `q_act = mean(V_act)` and `q_stop = mean(V_stop)`,
- set `oracle_action_gap = q_act - q_stop`,
- store uncertainty diagnostics (at least rollout count and gap standard deviation if possible).

---

## 5) Pilot horizon/budget regime

Use a small but meaningful regime that is heavier than current lightweight labels but still pilot-sized:
- budgets: `{10, 14}`,
- horizon `h = 6`,
- rollout depth cap: `<= 9`,
- paired rollouts per state: `N = 64`.

Rationale: enough to test fidelity mechanics without launching a broad heavy sweep.

---

## 6) Pilot subset size

First pilot target subset:
- total states: `1,200` (about `600` per budget),
- 2–3 seeds (recommended: 2 for first execution, 3 if capacity allows),
- stratify by remaining budget deciles and branch competitiveness (`gap_to_best_other_gain`) so labels are not concentrated in easy states.

If compute is tight, minimum acceptable subset is `600` states.

---

## 7) Required emitted artifacts

Pilot run should emit:
1. `oracle_stop_vs_act_labels.jsonl` — row-wise oracle labels,
2. `oracle_label_manifest.json` — exact run settings / provenance,
3. `oracle_label_quality_report.json` — validation + quality gates,
4. `oracle_label_failures.jsonl` (optional but recommended) — rows failing schema or consistency checks.

Required per-row fields (minimum):
- `state_id`, `example_id`, `budget`, `remaining_budget`, `current_branch_id`,
- `q_act`, `q_stop`, `oracle_action_gap`, `oracle_label_act`,
- `horizon`, `rollout_depth`, `teacher_mode`, `paired_randomness_used`.

---

## 8) Pre-distillation label quality gates

Do **not** trust pilot labels for distillation unless all required gates pass:
- schema validity rate: `>= 99%`,
- action-gap consistency (`abs((q_act-q_stop)-oracle_action_gap)` within tolerance): `>= 99%`,
- label-sign consistency with action gap: `>= 99%`,
- paired-randomness usage recorded and true for `>= 95%` rows,
- non-missing `q_act/q_stop/oracle_action_gap`: `>= 99%`,
- subset coverage target reached (`>= 600` rows minimum, `1200` preferred).

If gates fail, fix generator/instrumentation before distillation training.

---

## 9) Safe vs unsafe claims after pilot

Safe after a successful pilot:
- oracle-label generation pipeline is operational on a small run,
- schema/provenance/quality checks are reproducible,
- pilot labels are plausible enough for a first distillation trial.

Not safe after pilot alone:
- that oracle-distilled controller is better than current default,
- that gains generalize across larger budgets/datasets,
- that heavy-label phase is complete.

Those require downstream training/evaluation and larger-scale replication.

---

## Immediate sequence

Before HPC returns:
1. finalize pilot config,
2. validate config + schema tooling locally,
3. lock quality-gate thresholds.

When heavier compute is available:
1. run pilot label generation once,
2. run validation/report utility,
3. only then run first oracle-distillation training/eval against the current default anchor baseline.
