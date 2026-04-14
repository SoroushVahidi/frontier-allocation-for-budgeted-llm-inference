# Main drawbacks report — comparative frontier audit (`20260414T001932Z`)

## Scope

- **New-paper track**: matched-budget comparison of in-repo controller families on the same eval slices and budgets.
- **Primary “ours” method** (proposed adaptive anti-collapse allocator): `adaptive_min_expand_1`.
- **Backend**: **real API** — `openai` model `gpt-4.1-mini` (expand/verify/PoT share this generator).
- **External baselines** (cascade routing, MoB, paper-linked codebases): **not runnable inside this repository**; see `run_manifest.json` → `external_baselines_not_integrated`.

## 1) Where the primary method wins (accuracy vs listed baselines)

- Head-to-head cells (dataset × budget × baseline): **wins=0**, **losses=0**, **ties=0** (see `comparison_summary.csv`).
## 2) Where the primary method loses

Any negative mean Δ in the table above indicates systematic losses against that baseline on average over the audited cells.

## 3) Oracle gap (headroom — not ‘our bug’ alone)

- Large oracle gaps for **everyone** suggest diverse per-example winners (frontier heterogeneity), not only a failure of the adaptive policy.

## 4) Budget usage / under-spend / exhaustion


## 5) Verifier-guided search & program-of-thought (maturity)

- **verifier_guided_search**: uses **LLM verify** as ranking proxy on the same backend — meaningful for routing test-time compute, but still **not** a trained PRM.
- **program_of_thought**: uses **codegen + sandbox** on the same API path; quality depends on model and JSON fidelity (see `method_metrics.csv`).

## 6) Inferred drawbacks (evidence-based — check CSVs)

1. **No strong automated verdict** from aggregate rules — inspect `comparison_summary.csv` and per-dataset splits manually.

## Blocked datasets

- **hendrycks/competition_math**: FileNotFoundError: Couldn't find any data file at /workspace/adaptive-reasoning-budget-allocation/hendrycks/competition_math. Couldn't find 'hendrycks/competition_math' on the Hugging Face Hub either: LocalEntryNotFoundError: An error happened while trying to locate the file on the Hub and we cannot find the requested files in the local cache. Please check your connection and try again or make sure your Internet connection is on.

## Scale honesty

- Subset size / budgets / datasets: see `run_manifest.json`.
- Even with a real API, small `--subset-size` and few budgets yield **pilot-scale** statistical power; scale up for publication-grade means.

