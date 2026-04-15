# Oracle-label heavy generator path note (2026-04-15)

## Scope

This note describes the production-readiness pass that upgrades the real oracle-label generator from prototype usage to a **shard-scale heavy execution path** for the planned HPC pilot.

It does **not** claim the full pilot has already run.

---

## 1) What the current prototype already does correctly

The existing real prototype already demonstrates:

- real ACT-vs-STOP paired rollout label generation,
- deterministic state reconstruction from pilot-state manifest provenance,
- contract-compliant output fields (`q_act`, `q_stop`, `oracle_action_gap`, `oracle_label_act`, etc.),
- compatibility with current validator gates,
- successful tiny-subset execution proving the path is no longer mock-only.

---

## 2) Why that path is still prototype-level

The prototype remains limited for production pilot execution because it lacks operational safeguards expected for long shard jobs:

- no built-in resume/restart behavior,
- no per-state failure capture policy,
- no dedicated progress checkpoint artifact,
- limited shard provenance binding (split-manifest verification),
- limited explicit partial-failure semantics for HPC rerun workflows.

So it is correct algorithmically, but still thin operationally.

---

## 3) Production-scale concerns handled in this pass

This pass targets concrete execution concerns:

1. **Shard-scale determinism**
   - deterministic row processing order,
   - optional split-manifest + shard-name verification.
2. **Retry safety**
   - resumable mode that skips already emitted `state_id` rows.
3. **Partial failure visibility**
   - per-state error JSONL capture,
   - error counters and policy controls.
4. **Progress/provenance durability**
   - periodic atomic progress JSON,
   - richer run manifest metadata (state-manifest hash, shard metadata, completion stats).
5. **Contract compatibility**
   - preserves existing required output row schema and validator assumptions.

---

## 4) Exact implementation scope of this pass

Implemented now:

- a new heavy-path generator entrypoint:
  - `scripts/run_oracle_label_generator_heavy.py`
- heavy-path operational features:
  - `--resume`
  - `--continue-on-state-error`
  - `--max-state-errors`
  - `--allow-partial-output` (debug-only escape hatch)
  - `--progress-out` (atomic progress checkpoint)
  - `--state-errors-out` (row-level error capture)
  - shard metadata options (`--shard-name`, `--shard-id`, `--split-manifest`, `--expected-state-count`)
- preserved ACT-vs-STOP semantics and output contract compatibility.

Also updated docs/runbook/index references to include the new heavy path.

---

## 5) What still remains before actual full HPC pilot execution

Still required after this pass:

1. **Actual cluster run execution** across all target shards.
2. **Observed runtime/memory envelope validation** on the real HPC environment.
3. **Merged full-pilot artifact validation** with row-count gate and all quality gates passing at pilot scale.
4. **Only then**: distillation/evaluation steps and any claims beyond operational readiness.

So after this pass, the generator path is materially closer to production launch, but pilot completion is still an empirical run-time milestone, not a coding milestone.
