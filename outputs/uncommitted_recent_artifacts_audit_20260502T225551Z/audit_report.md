# Machine-readable audit summary

**Human narrative:** [`docs/UNCOMMITTED_RECENT_ARTIFACTS_AUDIT_20260502.md`](../../docs/UNCOMMITTED_RECENT_ARTIFACTS_AUDIT_20260502.md)

**Key outcomes (repo state immediately before corrective commit captured `21186a1`; this bundle ships with summaries now on `main`):**

1. **`outputs/strategy_seeded_discovery_on_66_gold_absent_20260502T222129Z`** — dense tracked curated artifacts; residual JSONLs + logs ignored **by `.gitignore` policy**.
2. **`outputs/main3_external_vs_best3_internal_100case_20260502T203851Z`** — **small summaries were fully untracked**; heavyweight JSONLs/logs ignored locally.
3. **`logs/slurm/*`** — uniformly **untracked** (operational clutter).
4. **`outputs/cohere_real_model_cost_normalized_validation_FINCHK_20260502T225251Z`** — ignored raw tree (**`per_example_records.jsonl`** rule umbrella).
5. **Follow-on commit recommendation:** add **seven** **`main3_*203851Z`** summary files **+** audit doc **+** this CSV/TXT bundle.

See sibling CSV/TXT artifacts for enumerated paths.
