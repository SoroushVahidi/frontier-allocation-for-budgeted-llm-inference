# REPOSITORY_POLISH_AUDIT_20260427T180600Z

Repository polish audit performed while leaving the active Cohere terminal run untouched.

## 1) Canonical paper-facing files

- Primary claim-bearing outputs:
  - `outputs/paper_tables/`
  - `outputs/paper_plot_data/`
  - `outputs/paper_figures/`
- Canonical generation path:
  - `scripts/paper/run_all_neurips_paper_artifacts.py`
- Claim boundary references:
  - `docs/PAPER_SOURCE_OF_TRUTH.md`
  - `docs/CLAIM_BOUNDARIES_CURRENT.md`
  - `docs/SAFE_CLAIMS_FOR_NEURIPS_2026.md`

## 2) Diagnostic/provenance-only files

- Cohere and real-provider audits are numerous and should remain diagnostic unless explicitly promoted:
  - `outputs/real_model_ours_vs_external_validation_*/`
  - `outputs/cohere_absent_from_tree_loss_diagnostics_*/`
  - `outputs/cohere_trace_complete_loss_subset_*/`
  - `outputs/cohere_direct_reserve_validation_*/`
- Many timestamped docs in `docs/` are historical run reports; useful provenance, but high noise for paper-facing navigation.

## 3) Anonymous-review files

- Anonymous package exists at `neurips2026_anonymous_artifact/`.
- Anonymous subtree appears structurally clean for artifact packaging, but still includes numerous external-code URLs for baseline provenance (expected).

## 4) Stale/confusing docs and outputs

- `docs/` contains a very large number of timestamped status notes from multiple phases; discovery cost is high.
- Several similarly named claim/status docs can confuse paper-facing vs diagnostic scope.
- Recommendation: keep historical docs, but route readers through a smaller front-door set (`PAPER_ARTIFACTS_README`, `PAPER_SOURCE_OF_TRUTH`, `CLAIM_BOUNDARIES_CURRENT`).

## 5) Canonical vs diagnostic scripts

- **Canonical/paper-facing scripts**: mainly under `scripts/paper/` and selected registry/report scripts.
- **Diagnostic scripts**: many `run_*` and `build_*` scripts tied to specific timestamps, stress tests, and provider audits (especially Cohere and frontier-gate diagnostics).
- Recommendation: maintain current scripts, but keep "canonical path" docs explicit and short.

## 6) Claim-language consistency scan

Phrases scanned: `matched-budget`, `robustly superior`, `universally better`, `state-of-the-art`, `decisive dominance`, `correct answer is already present`, `official reproduction`, `full systems-cost`, `token/latency/cost matched`.

Assessment:

- **Safe**:
  - caveat language such as "not an official reproduction",
  - "not token/latency/cost matched unless explicitly stated",
  - explicit diagnostics-only language for real-provider runs.
- **Needs replacement / tightening (paper-facing phrasing)**:
  - prefer `matched-action adapters` over `matched-budget adapter baselines`,
  - prefer `matched maximum action-budget contract` for main comparison wording.
- **Diagnostic/provenance-only**:
  - most historical occurrences in old docs/scripts/outputs are provenance-only and should not drive manuscript claims.

## 7) Wording consistency status

- Current docs use both "matched-budget" and "matched action-budget" language.
- Action taken in this polish pass:
  - added `docs/CLAIM_BOUNDARIES_CURRENT.md`,
  - added `docs/PAPER_ARTIFACTS_README.md`,
  - updated key claim-boundary docs to prioritize matched-action wording while preserving caveats.

## 8) Identity/anonymity risks

- No direct `Soroush`/`Vahidi`/`NJIT` strings found in anonymous artifact subtree during this scan.
- No `github.com/SoroushVahidi` links found in anonymous artifact subtree during this scan.
- External baseline repository URLs are present in anonymous files and generally acceptable as method provenance.

## 9) Files that should not be in anonymous supplement (policy)

- Local runtime diagnostics that contain environment-specific execution details.
- Provider-key readiness issue files tied to local runtime context.
- Non-canonical exploratory outputs not needed for reviewer reproduction.

## 10) Recommended cleanup actions

1. Keep historical diagnostics, but avoid promoting them in top-level paper-facing navigation.
2. Continue using `matched maximum action-budget contract` and `matched-action adapters` in paper-facing docs.
3. Keep real-provider/Cohere evidence explicitly diagnostic until promotion criteria are met.
4. Add a pre-release anonymous hygiene check as part of packaging routine.
