# PAPER_REPRODUCTION_CHECKLIST

Use this checklist before generating manuscript artifacts.

## 0) Environment and repo health

- [ ] `make setup`
- [ ] `make smoke`
- [ ] `make health`
- [ ] `make lint`
- [ ] `make test`

If any item fails, do not publish paper artifact updates until resolved or explicitly documented.

## 1) Canonical state checks

- [ ] Read `PAPER_SOURCE_OF_TRUTH.md`.
- [ ] Confirm surface separation (`strict_gate1_cap_k6` vs `strict_f3`) is preserved in target draft text.
- [ ] Confirm baseline status buckets are unchanged or re-audited.

## 2) Artifact regeneration (core)

- [ ] `python scripts/run_broader_strict_phased_default_decision_eval.py`
- [ ] `python scripts/run_paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3.py`
- [ ] `python scripts/paper/run_all_neurips_paper_artifacts.py`
- [ ] `python scripts/paper/build_claim_safety_statistical_table.py` (optional direct spot-check; canonical runner also executes it)

## 3) Artifact regeneration (supportive but recommended)

- [ ] `python scripts/run_manuscript_surface_component_ablation.py`
- [ ] `python scripts/package_strict_f3_component_ablation_paper_surface.py`
- [ ] `python scripts/build_paper_facing_baseline_tables.py`

## 4) Claim integrity checks

- [ ] All manuscript numeric claims map to canonical artifact families in `PAPER_ARTIFACT_MAP.md`.
- [ ] All speculative statements are moved to limitations/open gaps.
- [ ] Claim-safety wording uses top-cluster/surface-dependent language; no "statistical dominance" wording for `strict_f3` vs `strict_gate1_cap_k6`.
- [ ] Any missing artifacts are explicitly marked as missing.

## 5) Final pre-draft gate

- [ ] Update `PAPER_OPEN_GAPS_AND_RISKS.md` with unresolved issues.
- [ ] Update `PAPER_CLAIMS_AND_EVIDENCE_MAP.md` if claim status changes.
- [ ] Ensure draft tables do not include baselines outside allowed readiness bucket.
