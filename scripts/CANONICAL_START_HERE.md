# Canonical scripts start here

Fastest script-level entry path aligned with current canonical docs.

Companion manuscript snapshot: `docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`.

## First, keep method-surface scope explicit

- Manuscript-facing matched-surface internal winner: `strict_f3`
- Broader operational default on a different surface: `strict_gate1_cap_k6`

Script outputs should never blur this distinction.

## Minimal runnable sequence

From repo root:

```bash
make setup
make check
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Compatibility alias (kept for older references):

```bash
python scripts/paper/run_all_neurips_artifacts.py
```

## Core entry points by use-case

### Paper artifacts
- `paper/run_all_neurips_paper_artifacts.py` (primary)
- `paper/run_all_neurips_artifacts.py` (compatibility alias)

### Broader operational default evidence path
- `run_broader_strict_phased_default_decision_eval.py`
- `build_canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics.py`

### Manuscript-facing matched-surface path
- `run_matched_surface_multiseed_main_comparison.py`
- `run_paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3.py`

### Repo health
- `check_repo_health.py`
- `smoke_test.py`

## Interpretation discipline

- Run scripts from canonical docs outward, not from arbitrary historical notes.
- If a script produces exploratory outputs, keep interpretation scoped and non-headline unless promoted by canonical docs.
- Keep real-model/diagnostic outputs appendix-bounded unless canonical docs explicitly promote them.
- Keep `scripts/README.md` as the full script index; keep this file intentionally short.
