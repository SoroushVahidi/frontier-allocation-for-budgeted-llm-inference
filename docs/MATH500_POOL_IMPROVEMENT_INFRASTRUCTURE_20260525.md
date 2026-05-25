# MATH-500 Pool Improvement Infrastructure

Date: 2026-05-25

---

## Overview

This document records the infrastructure created to support multi-provider candidate pool
improvement on the MATH-500 benchmark, starting from the Cohere-only 300-case baseline.

---

## MATH-500 metadata recovery

HuggingFace MATH-500 dataset fields available locally:
- `subject` — MATH subject category (7 categories)
- `level` — difficulty 1–5
- `solution` — canonical solution text
- `unique_id` — stable string identifier (e.g. `HuggingFaceH4_MATH-500_0`)

All 300 cases in the shared exact-cases file were successfully joined 300/300 with subject
and level metadata from the local HuggingFace cache
(`~/.cache/huggingface/hub/datasets--HuggingFaceH4--MATH-500/`).

---

## 300-case subset distribution

| Subject | N | % |
|---|---:|---:|
| Algebra | 70 | 23.3% |
| Intermediate Algebra | 69 | 23.0% |
| Prealgebra | 41 | 13.7% |
| Number Theory | 34 | 11.3% |
| Precalculus | 33 | 11.0% |
| Counting & Probability | 27 | 9.0% |
| Geometry | 26 | 8.7% |
| **Total** | **300** | 100% |

| Level | N | % |
|---|---:|---:|
| 1 (easiest) | 22 | 7.3% |
| 2 | 57 | 19.0% |
| 3 | 56 | 18.7% |
| 4 | 80 | 26.7% |
| 5 (hardest) | 85 | 28.3% |
| **Levels 4–5** | **165** | **55.0%** |

The subset is harder than the full 500-case MATH-500: 55% of cases are at levels 4–5.

---

## Output files (local, not committed)

- `outputs/math500_pool_improvement_infrastructure_20260525/math500_shared_exact_cases_with_metadata.jsonl`
  — 300 cases with `subject`, `level`, `solution`, `unique_id` joined
- `outputs/math500_pool_improvement_infrastructure_20260525/cohere_math500_case_table_with_metadata.csv`
  — Cohere 300-case table enriched with subject/level metadata

---

## Candidate pool improvement strategy

Pool improvement must be tracked separately from selector improvement:

| What | Metric | How to measure |
|---|---|---|
| **Pool improvement** | Oracle ceiling lift | More providers → more cases where ≥1 source is correct |
| **Selector improvement** | Recovery rate | More cases where selector picks the correct source |
| **Pool failure reduction** | Δ all_sources_wrong | New providers rescue previously all-wrong cases |
| **Selector regression** | Regression count | New selection rule picks wrong when old rule was right |

A selector that recovers pool failures but also introduces regressions may show net zero
improvement even though the pool ceiling rose.

---

## Candidate-action table design

One row per `(example_id, provider, action_name)`. Extensible: add new providers/actions
without rebuilding old rows.

Key columns: `example_id`, `provider`, `action_name`, `action_answer`, `action_correct`,
`action_cost_tokens`, `method_family`.

Action families: `direct_reserve_*, external_l1_*, external_s1_*, external_tale_*`.

---

## LLM+SymPy candidate source

Four variants designed for future piloting (lower priority than multi-provider generation):

| Variant | Description | Status |
|---|---|---|
| A | SymPy normalizes existing LLM answer | NOT JUSTIFIED (Phase 1: 0 genuine rescues) |
| B | LLM writes equation; SymPy solves | PILOT NEEDED (50 cases: Int. Algebra + Precalculus, all-wrong, levels 3–5) |
| C | LLM generates canonical form; SymPy validates | FUTURE WORK |
| D | Full fallback chain (Variant B primary, Variant A fallback) | RECOMMENDED when piloting |

---

## Pool-vs-selector ablation requirement

Before claiming selector improvement on a multi-provider pool, the paper must separate:

1. **Oracle ceiling lift** — how many more cases are solvable with the new pool?
2. **All-wrong reduction** — how many previously all-wrong cases are now rescuable?
3. **Selector recovery rate** — what fraction of rescuable cases does the selector find?
4. **Selector regression** — what fraction of previously-correct cases does the new selector break?

LOPO (Leave-One-Provider-Out) validation is required before claiming generalization.
Bootstrap 95% CI (B=10,000) is required on all headline metrics.

---

## See also

- `docs/FIXED_POOL_STABLE_LABEL_SCHEMA_20260525.md` — label schema for fixed-pool learning
- `docs/COHERE_MATH500_FAILURE_LEARNING_20260525.md` — Cohere-only pool analysis
- `docs/PROVIDER_READINESS_20260525.md` — provider status for multi-provider generation
