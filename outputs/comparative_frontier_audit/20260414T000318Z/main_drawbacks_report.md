# Main drawbacks report — comparative frontier audit (`20260414T000318Z`)

## Scope

- **New-paper track**: matched-budget comparison of in-repo controller families on the same eval slices and budgets.
- **Primary “ours” method** (proposed adaptive anti-collapse allocator): `adaptive_min_expand_1`.
- **Backend**: **real API** — `openai` model `gpt-4.1-mini` (expand/verify/PoT share this generator).
- **External baselines** (cascade routing, MoB, paper-linked codebases): **not runnable inside this repository**; see `run_manifest.json` → `external_baselines_not_integrated`.

## 1) Where the primary method wins (accuracy vs listed baselines)

- Head-to-head cells (dataset × budget × baseline): **wins=0**, **losses=4**, **ties=1** (see `comparison_summary.csv`).

| Baseline | Mean Δ acc (ours − baseline) |
|---|---|
| `program_of_thought` | -0.6667 |
| `reasoning_beam2` | -0.2500 |
| `reasoning_greedy` | -0.7500 |
| `self_consistency_3` | -0.6667 |
| `verifier_guided_search` | 0.0000 |

## 2) Where the primary method loses

Any negative mean Δ in the table above indicates systematic losses against that baseline on average over the audited cells.

## 3) Oracle gap (headroom — not ‘our bug’ alone)

- Mean **gap to oracle** for `adaptive_min_expand_1`: **0.7500** (oracle = best per-example strategy across all eight families).
- Tightest baseline to oracle on average: **`reasoning_greedy`** (mean gap ≈ **0.0000**).
- Large oracle gaps for **everyone** suggest diverse per-example winners (frontier heterogeneity), not only a failure of the adaptive policy.

## 4) Budget usage / under-spend / exhaustion

- `adaptive_min_expand_1` mean realized **avg_actions / budget**: 0.931 (see `method_metrics.csv`).
- Mean **budget_exhaustion_rate** for `adaptive_min_expand_1`: **0.7500**.

## 5) Verifier-guided search & program-of-thought (maturity)

- **verifier_guided_search**: uses **LLM verify** as ranking proxy on the same backend — meaningful for routing test-time compute, but still **not** a trained PRM.
- **program_of_thought**: uses **codegen + sandbox** on the same API path; quality depends on model and JSON fidelity (see `method_metrics.csv`).

## 6) Inferred drawbacks (evidence-based — check CSVs)

1. **Gap to oracle**: Primary method leaves substantial per-example headroom vs the best-of-frontier upper bound — allocation may be **suboptimal vs an oracle meta-policy** (see `oracle_gap_summary.csv`).
2. **Head-to-head**: Primary method loses more cells than it wins against the listed baselines — **marginal ranking in this API-backed run** may favor simpler families (beam / self-consistency / VGS) in several regimes.
3. **Anti-collapse knob**: Mean gap-to-oracle across budgets/datasets: k=0 → 1.000, k=1 → 0.750, k=2 → 0.500. If k=1 is not uniformly best, **min-expand is regime-dependent** (see ablation in `method_metrics.csv`).

## Scale honesty

- Subset size / budgets / datasets: see `run_manifest.json`.
- Even with a real API, small `--subset-size` and few budgets yield **pilot-scale** statistical power; scale up for publication-grade means.

