# Oracle-label generator prototype v1 (real but limited)

## Purpose

This note describes the **first real oracle-label generator prototype**.

It is intentionally limited and should be interpreted as a contract-exercising implementation step, not a full production heavy run.

---

## 1) What this prototype actually computes

For each selected pilot state, the prototype computes real paired ACT-vs-STOP rollout estimates:
- `q_act`: mean rollout value when forcing ACT on the current branch at step 1,
- `q_stop`: mean rollout value when forcing STOP-here-now (skip current branch at step 1) with preserved/reallocated compute,
- `oracle_action_gap = q_act - q_stop`,
- `oracle_label_act = 1 if oracle_action_gap > 0 else 0`.

It uses paired common-random-number rollouts per state (`paired_randomness_used = true`).

---

## 2) What parts of the oracle design are implemented now

Implemented now:
- real (non-mock) local paired rollouts,
- ACT/STOP first-step intervention semantics,
- horizon/depth/rollout-count controls from pilot config,
- contract-compliant output artifacts:
  - `oracle_stop_vs_act_labels.jsonl`,
  - `oracle_label_manifest.json`,
- compatibility with existing validator + HPC wrapper output expectations.

---

## 3) What is still approximate / missing

Still limited:
- snapshot reconstruction is replay-based from deterministic manifest provenance (seed/budget/episode/decision/branch), not a fully serialized simulator state dump,
- rollout teacher is still the existing local simulation machinery, not a separately engineered large-scale oracle backend,
- prototype is CPU-oriented and intended for small subsets,
- distributed fault tolerance / sharded large-scale orchestration is not implemented here,
- this is not yet the full HPC production generator.

---

## 4) Intended subset / scale

This prototype is intended for bounded runs (e.g., `--max-states` small) to verify:
- real-generation correctness,
- contract adherence,
- validator compatibility,
- provenance capture.

It is not intended to claim completion of the full ~1200-state heavy pilot at production scale.

---

## 5) Safe vs unsafe claims after running this prototype

Safe claims:
- the contract is exercised by a real generator,
- real paired ACT/STOP oracle-gap labels can be produced on a bounded subset,
- outputs integrate with existing validator and wrapper flow.

Unsafe claims:
- full pilot completion,
- distillation readiness at scale,
- superiority over anchor baseline,
- broad generalization or manuscript-level performance conclusions.
