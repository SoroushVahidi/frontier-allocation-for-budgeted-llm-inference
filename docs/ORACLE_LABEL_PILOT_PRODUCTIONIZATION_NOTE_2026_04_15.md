# Oracle-label pilot productionization note (2026-04-15)

## Scope

This note captures the next step after the real oracle-label generator prototype: preparing a **credible full pilot-scale HPC execution path** without claiming pilot completion.

Anchor baseline remains the current default stop-vs-act setup; this work is for label-fidelity engineering readiness, not baseline replacement.

---

## 1) What currently works in the prototype path

The current prototype path already works for bounded subsets:

- Real input consumption from pilot config + selection config + state manifest.
- Deterministic state reconstruction from manifest provenance (`source_seed`, `budget`, `episode_id`, `decision_id`, `current_branch_id`).
- Real paired ACT-vs-STOP local rollouts (`q_act`, `q_stop`, `oracle_action_gap`, `oracle_label_act`).
- Contract-compliant row outputs and generation manifest outputs expected by wrapper/validator.
- Validator behavior is correct for tiny runs:
  - schema/semantic consistency gates pass,
  - row-count gate fails as expected when run on tiny subsets.

This means we are past interface-only scaffolding: a real generator implementation exists and executes correctly on small slices.

---

## 2) What still blocks full pilot-readiness today

The following gaps still block calling the path "full pilot-ready":

1. **No deterministic sharded execution primitive in the runbook/tooling.**
   - Full pilot should not rely on a single monolithic job.
2. **No first-class shard merge/provenance check step.**
   - Need deterministic reassembly + duplicate/missing-state detection.
3. **Retry/partial-failure handling is implicit, not operationalized.**
   - A failed shard should be rerunnable without invalidating successful shards.
4. **No explicit output merge consistency contract at shard boundary.**
   - Need checks that merged outputs preserve source manifest ordering and coverage.
5. **No shard-level reproducibility bookkeeping in artifacts.**
   - Need stable shard identity and explicit source-manifest hash linkage.

---

## 3) Scaling risks that must be actively managed

### Runtime risk
- Per-state paired rollouts can become expensive at pilot scale.
- Single-job runtime increases queue risk and restart cost.

### Memory risk
- Reconstructed active snapshots + rollout loops can create memory pressure if too many states are handled in one process.

### Sharding risk
- Ad-hoc shard assignment can become non-reproducible across reruns.
- Uneven shard sizing can cause long-tail completion delays.

### Retry risk
- Without explicit shard bookkeeping, retries can produce accidental duplicate labels or overwritten provenance.

### Partial-failure risk
- Some shards may complete while others fail; pipeline must support merge-time detection and controlled blocking behavior.

### Reproducibility-across-shards risk
- If shard membership is not deterministic and source-linked, two runs with same inputs can produce incompatible output sets.

### Manifest partitioning risk
- Manifest splits that alter row content or ordering semantics can break reconstruction assumptions.

### Output merge consistency risk
- Merge can silently misorder rows, duplicate `state_id`, or drop states unless checked against source manifest.

---

## 4) Minimal productionization steps required before full pilot launch

1. **Introduce deterministic sharding utility** (implemented in this step):
   - split full state manifest into stable per-shard manifests,
   - record split provenance (source path + source hash + shard state IDs).
2. **Introduce deterministic merge utility** (implemented in this step):
   - consume per-shard label outputs,
   - detect missing shards / missing states / duplicates / unknown states,
   - reorder merged labels to match original source manifest order,
   - emit merge manifest report.
3. **Integrate sharding helper into launch runbook/HPC docs** (implemented in this step):
   - define explicit split → shard runs → merge → validator sequence.
4. **Require validator on merged artifact before any distillation gate** (already true logically, now explicit in sharded flow).
5. **Defer full pilot execution itself** until compute is available and shard job template wiring is confirmed.

These are intentionally minimal; they improve operational safety without pretending to solve all future scale engineering.

---

## 5) Safe vs unsafe claims after this productionization step

### Safe claims now
- There is now a concrete deterministic sharded execution path for oracle-label pilot runs.
- Shard provenance and merge consistency checks are explicitly represented in artifacts.
- Tiny local shard end-to-end exercises can demonstrate split → generate → merge → validate behavior.

### Still not safe claims
- Full pilot has run successfully at target scale.
- Pilot quality gates (especially row-count gate) are satisfied for full run.
- Distillation readiness is established.
- Any performance/superiority/generalization claims beyond bounded prototype behavior.

---

## Operational interpretation

After this step, the repo is **prepared for a sharded pilot launch path** (operationally credible), but is **not** claiming that production-scale label generation is complete.
