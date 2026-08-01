# External warm-start branch scorer result note

This note tracks the first new-paper experiment comparing:
- internal-only branch scorer,
- external warm-start scorer,
- external warm-start + internal adaptation,
- oracle upper bound.

## Experiment commands

### Smoke

```bash
python scripts/run_new_paper_external_warmstart_branch_scorer.py \
  --episodes 120 \
  --budget 8 \
  --internal-dataset-episodes 220 \
  --internal-dataset-budget 8
```

### Meaningful simulator-backed comparison

```bash
python scripts/run_new_paper_external_warmstart_branch_scorer.py \
  --episodes 700 \
  --budget 10 \
  --internal-dataset-episodes 900 \
  --internal-dataset-budget 10
```

### Small real-model-backed attempt

```bash
python scripts/run_new_paper_external_warmstart_branch_scorer.py \
  --episodes 40 \
  --budget 6 \
  --internal-dataset-episodes 160 \
  --internal-dataset-budget 6 \
  --real-model-smoke
```

## Scope and honesty

- Uses Tier-1 readiness recommendations in v1:
  - `deepstep_math_5k`
  - `math_verify_s1k_r1`
  - `ultrainteract_pair`
- Uses HF streaming fallback if prepared preview files are unavailable.
- Keeps judge-style Tier-1 datasets (`mt_bench_human_judgments`, `prometheus_preference_collection`) out of v1 to keep this first pass simple/auditable.
- External supervision here is a **partial match** used for warm-start only; final frontier-allocation labels still require repo-specific supervision.

## Internal branch-scorer plug-in audit (new-paper track)

Cleanest insertion point is the existing model-map based scorer path:
- Build/run internal branch-ranking data with `scripts/build_v3_ranking_dataset.py`.
- Train/export scalar logistic weights in v7 feature space.
- Inject scorer variants through `model_map` keys consumed by `simulate_controller(...)`.

This preserves:
- existing `adaptive_learned_branch_score_*` controller comparison flow,
- scalar inference interface (`model_priority(...)`),
- oracle / relative-rank baselines for direct gap comparisons.

## Latest meaningful run

- Run dir: `outputs/new_paper/external_warmstart_branch_scorer/20260414T135210Z`
- Key outcomes:
  - `adaptive_relative_rank`: `0.6143`
  - `adaptive_learned_branch_score_internal_only`: `0.5986`
  - `adaptive_learned_branch_score_external_warmstart`: `0.6029`
  - `adaptive_learned_branch_score_external_plus_internal`: `0.5957`
- Holdout transfer snapshot:
  - `internal_only`: `0.6157`
  - `external_warmstart_only`: `0.5744`
  - `external_warmstart_plus_internal`: `0.5949`
- Read: `interpretation.md`, `warmstart_comparison.csv`, `oracle_gap_summary.csv` in the run directory.

## Interim conclusion

- External warm-start improved over internal-only in this run (`+0.0043`) but did **not** beat the current best heuristic baseline.
- External-only data is not sufficient by itself for this branch-allocation setting.
- Internal adaptation mattered, but naive warm-start + adaptation underperformed internal-only in holdout transfer here.
- Next default direction: keep internal supervision central and use external datasets as optional warm-start regularization, not a replacement.
