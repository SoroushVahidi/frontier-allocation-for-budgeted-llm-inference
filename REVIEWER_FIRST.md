# Reviewer first: reproduction and claim-scope guide

This page is the shortest reviewer-facing path through the repository. It intentionally avoids historical run folders unless a canonical document promotes them.

**Canonical current state:** [`docs/CURRENT_CANONICAL_STATE_20260527.md`](docs/CURRENT_CANONICAL_STATE_20260527.md)

## What this repository claims safely (2026-05-27 update)

The project studies frontier allocation and final-answer selection under explicit inference-budget contracts. The current headline contribution is **FTA / FIX-2+FIX-4 (Failure-Trace Allocator)**.

Safe current claims:

- **FTA / FIX-2+FIX-4 achieves 86.67% (260/300) on Final-300** (Cohere × GSM8K, seed=71, budget=6); independently reproduced from raw per-example records.
- **FTA achieves 80.69% (581/720) on Aggregate-720** (seeds 41+61+71); source-stratified CI lower bounds vs L1/S1/TALE/best-external all strictly positive.
- FTA gate features (override_reason, frontier_support, external unanimity) are gold-free at runtime; leakage audit PASS.
- FTA adds zero model calls at selection time after candidates are generated.
- D9 gated selector achieves CV 50.18%±2.52% vs frontier 34.36% (+15.82pp) on 550 multi-provider D6 pools; 0 false overrides.
- `external_l1_max` (L1) is the primary external comparator: 83.00% on Final-300, 77.64% on Aggregate-720. FTA leads L1 with CI [+0.33, +7.00] (Final-300) and positive stratified CI on Aggregate-720.
- Timestamped `outputs/` folders are provenance; use canonical docs and manifests before citing numbers.

Required disclosures (must state in paper):

- CI vs pooled ensemble (frontier+L1+S1+TALE majority) **includes zero** at both Final-300 and Aggregate-720 — do not claim statistical superiority over pooled ensembles.
- Full pool generation costs 4×B=6 = 24 logical calls per example (FTA itself adds 0 post-generation calls).
- Evaluation scope: Cohere × GSM8K only; not extrapolated to MATH-500.

Unsafe without additional evidence:

- FTA statistical superiority over the pooled ensemble (CI includes zero).
- FTA results on benchmarks other than Cohere × GSM8K.
- D8.1 selector results as independent held-out end-to-end accuracy.
- D6 standalone as a positive net-gain method.

For the compact claim checklist, see `docs/CLAIMS.md` and `docs/CURRENT_CANONICAL_STATE_20260527.md` Section 6.

## Minimal setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

Paid/API verifier tooling is optional and intentionally not installed by default:

```bash
python -m pip install -e .[dev,api]
```

## Reviewer-safe checks

These commands should not require paid API calls:

```bash
make health
make reviewer-test
make selector-test
```

Optional broader local check:

```bash
python -m pytest -q
```

## Paper artifact regeneration

Canonical paper-facing artifacts are regenerated with:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Canonical output roots:

- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

## Required reading before writing or reviewing claims

1. `docs/CLAIMS.md`
2. `START_HERE_CURRENT.md`
3. `docs/PAPER_SOURCE_OF_TRUTH.md`
4. `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
5. `docs/CURRENT_PROJECT_STATUS.md`
6. `docs/CURRENT_EXTERNAL_BASELINE_GAP.md`
7. `docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md`
8. `docs/ARTIFACT_STATUS_TABLE.md`

## Selector/API separation

Use `scripts/run_outcome_verifier_answer_group_selector.py` for dry-run call-plan, heuristic, or cached-score selector evaluation. Use the dedicated scoring script for paid/API verifier score generation:

```bash
python scripts/run_outcome_verifier_scoring.py --help
```

Do not treat missing-score fallback behavior as a real selected-verifier comparison.
