# Cohere MATH-500 Failure Analysis and SymPy Validation

Date: 2026-05-25

---

## Overview

Full failure-learning analysis of the Cohere × MATH-500 300-case baseline pool.
Includes agreement-only selector analysis, learned selector evaluation, symbolic
agreement evaluation, and Phase 1 offline SymPy validation.

This is exploratory/regime-learning work. No results here are promoted to paper claims.

---

## Cohere MATH-500 baseline

| Metric | Value |
|---|---|
| N | 300 |
| Agreement-only accuracy | 33.0% (99/300) |
| Pooled4 (all-sources majority) | ~31.7% |
| Best raw single source | ~29% |
| Oracle ceiling (Cohere-only) | ~46.3% (139/300) |
| True all-sources-wrong | ~161/300 = 53.7% |
| Normalization-fixable | ~4 cases |

The dominant failure mode is **candidate pool failure**: 53.7% of examples have no correct
answer anywhere in the Cohere pool, regardless of selector choice. This ceiling cannot be
overcome by selector improvement alone.

---

## Selector evaluation

### Agreement-only selector (baseline)
- 99/300 = 33.0%
- Selects the plurality-majority answer when one exists; falls back to arbitrary source

### Symbolic agreement selector (SymPy-merged voting)
- Merges answers that are symbolically equivalent via SymPy before majority vote
- Result: **net −3 vs. agreement-only** (9 regressions, 6 recoveries)
- **NOT PROMOTED** — regressions exceed recoveries; SymPy merging causes false positives

### Stronger normalization for scoring
- LaTeX cleanup, SymPy simplification in the scoring layer
- Rescued ~4 normalization-fixable cases (+1.3pp oracle ceiling lift)
- **PROMOTED for scoring layer** — small but genuine improvement; no regressions

### Learned meta-router
- XGBoost-based router trained on Cohere-only pool features (70% CV accuracy)
- Key predictive features: `cur_has_majority`, `pairwise_lc_agree_count`, answer type, subject, level
- **DEFERRED** — N=300 is too small for reliable learned-router deployment;
  no better fallback exists for the predicted-failure cases even if the prediction is correct

---

## Subject-level failure analysis

| Subject | N | All-wrong | All-wrong % | Oracle | Oracle % |
|---|---:|---:|---:|---:|---:|
| Algebra | 70 | 24 | 34% | 46 | 66% |
| Intermediate Algebra | 69 | 50 | **72%** | 19 | 28% |
| Prealgebra | 41 | 18 | 44% | 23 | 56% |
| Number Theory | 34 | 19 | 56% | 15 | 44% |
| Precalculus | 33 | 22 | **67%** | 11 | 33% |
| Counting & Probability | 27 | 18 | 67% | 9 | 33% |
| Geometry | 26 | 14 | 54% | 12 | 46% |

**Intermediate Algebra (72% all-wrong) and Precalculus (67% all-wrong) are the primary
targets for candidate pool expansion.** These subjects have the highest pool failure rates
and the most to gain from additional providers or LLM+SymPy.

---

## Difficulty-level analysis

| Level | N | All-wrong | All-wrong % |
|---|---:|---:|---:|
| 1 (easiest) | 22 | 7 | 32% |
| 2 | 57 | 20 | 35% |
| 3 | 56 | 24 | 43% |
| 4 | 80 | 50 | 62% |
| 5 (hardest) | 85 | 64 | **75%** |

Level-5 problems have 75% all-wrong rate — structurally unsolvable by the current pool.

---

## Phase 1 SymPy offline validation

Applied SymPy equivalence checking to all 1200 (source, gold) pairs where source was scored
incorrect (4 sources × 300 examples = 1200; 880 wrong pairs tested after excluding 320
correct).

| Metric | Count |
|---|---:|
| Wrong pairs tested | 880 |
| **Genuine SymPy symbolic rescues** | **0** |
| **Genuine numeric rescues** | **0** |
| Apparent rescues (data artifacts) | 10 |
| SymPy parse failures (source) | 29 |
| SymPy parse failures (gold) | 15 |
| SymPy timeouts (3s SIGALRM) | 5 |

**Result: 0 genuine rescues.** Wrong answers in the Cohere pool are genuinely wrong —
not just mis-formatted correct answers.

### Variant A (SymPy normalizes existing LLM answer): NOT JUSTIFIED

Phase 1 proves Variant A adds 0 genuine rescues. Wrong answers are wrong, not
mis-formatted. SymPy as a normalizer of existing outputs adds no value here.

### Variant B (LLM writes equation; SymPy solves): PILOT NEEDED

Variant B requires a live pilot run because existing Cohere runs use prompts that ask for
a final numeric answer, not for explicit equation setup. Cannot validate offline.

**Recommended pilot: 50 cases — 25 Intermediate Algebra + 25 Precalculus, all-wrong,
levels 3–5.** Success threshold: ≥3 unique correct rescues, 0 regressions, <10% timeout.

### Variant D (full fallback chain): RECOMMENDED if piloting

1. Prompt LLM to write the key equation explicitly
2. Parse with `sympy.parse_latex` → `sympy.solve()`
3. If solve succeeds: use SymPy result as candidate answer
4. If solve fails: use `sympy.simplify` on LLM's stated final answer (Variant A fallback)
5. If all SymPy fails: use LLM's raw final answer

---

## Data artifact warning

**10 cases in the Cohere MATH-500 case table have a construction inconsistency:**
`frontier_answer` in the CSV equals `gold_answer` (exact integer match) but
`frontier_correct = 0`.

Root cause: the case table stores a different extraction of the frontier answer than what
the scorer used. The source JSONL (`selected_answer_canonical`) is authoritative.

**Action required before downstream ML training:**
Flag or exclude these 10 cases, or rebuild the case table from the canonical JSONL.

Affected IDs:
- `HuggingFaceH4_MATH-500_11`
- `HuggingFaceH4_MATH-500_193`
- `HuggingFaceH4_MATH-500_222`
- `HuggingFaceH4_MATH-500_236`
- `HuggingFaceH4_MATH-500_251`
- `HuggingFaceH4_MATH-500_255`
- `HuggingFaceH4_MATH-500_256`
- `HuggingFaceH4_MATH-500_258`
- `HuggingFaceH4_MATH-500_287`
- `HuggingFaceH4_MATH-500_297`

---

## Promotion decisions summary

| Component | Decision | Reason |
|---|---|---|
| Stronger normalization (scoring layer) | **PROMOTE** | +4 rescued, +1.3pp oracle lift, no regressions |
| Symbolic agreement selector | **DO NOT PROMOTE** | Net −3 (9 regressions, 6 recoveries) |
| Learned meta-router | **DEFER** | N too small; no better fallback for predicted-failure cases |
| SymPy Variant A (normalize existing) | **NOT JUSTIFIED** | 0 genuine rescues confirmed |
| SymPy Variant B/D pilot | **LOWER PRIORITY** | Multi-provider pool expansion is higher leverage first |

---

## Recommended next steps

1. **Multi-provider MATH-500 generation first** — Azure + Cloudrift + Cerebras MATH-500 300-case
   runs will raise oracle ceiling more than selector improvements on a pool-failure-dominated dataset
2. **After 3-provider pool**: compute complementarity matrix, oracle ceiling lift, ablation
3. **LLM+SymPy Variant B/D pilot later** (50 cases) — if oracle ceiling is still insufficient

---

## Local output directories (not committed)

- `outputs/cohere_math500_failure_learning_20260525/` — full workbench including all metrics, promotion decisions, learned selector interpretation
- `outputs/math500_sympy_offline_validation_20260525/` — SymPy validation results by answer type and subject
