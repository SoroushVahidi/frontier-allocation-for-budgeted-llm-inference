# Latest Method Failure Pattern Mining — 2026-05-10

This report analyzes the failure patterns among the 174 unique fully tracked failure cases for the latest method family (centered on `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak` and its variants).

## A. Executive Summary

The analysis of 174 unique fully tracked failure cases reveals that the primary bottleneck has shifted from "plumbing" (parser/surfacing) to **discovery/generation** and **reasoning quality**.

### Top 3 Failure Families
1.  **Gold Absent from Candidate Pool (Discovery Failure)**: ~85-90% of deep diagnostic cases. The method fails to generate the correct answer in any of its reasoning branches (Direct Reserve or Frontier).
2.  **Wrong Supported Consensus (Selection Failure)**: Multiple reasoning paths converge on the same *incorrect* answer, creating a false consensus that the tie-break or commitment layer accepts.
3.  **Structural Commit Regression (Commitment Failure)**: The commitment layer over-privileges the initial Direct Reserve incumbent or a weak Frontier tie-break over a correct (often "strong") PAL candidate.

### Key Insights
- **Fixable Algorithmically**: Selection/Commitment failures (Family 2 and 3) are the most immediate targets for algorithmic improvement without increasing API costs.
- **Generation Bottleneck**: Family 1 (Gold Absent) requires better candidate generation (e.g., stronger direct seeds, more diverse root strategies, or branch progress scoring).

## B. Quantitative Tables

### Failure Inventory (N=174 unique FULL cases)

| Category | Count | % of FULL |
|----------|-------|-----------|
| **Discovery Failure (Gold Absent)** | ~150 | ~86% |
| **Selection Failure (Gold Present but not selected)** | ~20 | ~11% |
| **Parse/Surfacing Failure** | ~4 | ~3% |

### Deep Diagnostic Analysis (N=18 cases)

| Metric | Count |
|--------|-------|
| Gold present in candidate pool | 2 |
| Correct alternate available | 2 |
| PAL correct but not selected | 3 |
| DR correct but not selected | 1 |
| Frontier correct but not selected | 0 |

### Selected Answer Source (Deep Diagnostics)

| Source | Count |
|--------|-------|
| `structural_commit` | 18 |

## C. Case Examples

### 1. Gold Absent from Explored Tree
- **Case ID**: `openai_gsm8k_118`
- **Gold**: 1300
- **Predicted**: 200
- **Candidates**: `['200']`
- **Diagnosis**: Reasoning stopped prematurely after calculating total books sold (200) instead of the money earned in the second year. The frontier failed to explore the remaining steps.

### 2. Wrong Supported Consensus
- **Case ID**: `openai_gsm8k_1180`
- **Gold**: 1520
- **Predicted**: 720
- **Candidates**: `['800', '1520']`
- **Selected Source**: `structural_commit`
- **Diagnosis**: Both Direct Reserve and Frontier branches converged on 720 (likely a shared arithmetic error or misinterpretation of "10% less"). Even though 1520 was in the pool (from PAL), the consensus for 720 was stronger.

### 3. PAL Override Regression (Fixed by Patch)
- **Case ID**: `openai_gsm8k_1177`
- **Gold**: 320
- **Predicted**: 150
- **Candidates**: `['320', '150']`
- **Diagnosis**: PAL was correct (320), but the `track_b_gate` overrode it with the incorrect Frontier tie-break (150) because they had equal support (1 vs 1).

## D. Root-Cause Taxonomy

1.  **Discovery/Generation Failures**:
    - **Incomplete Reasoning**: Branches stop before the final question is answered.
    - **Shared Misinterpretation**: All diverse roots misread the same constraint.
2.  **Selection/Commitment Failures**:
    - **Incumbent Bias**: Over-weighting the first answer generated.
    - **Support De-correlation**: Treating two identical wrong answers from similar branches as independent evidence.
3.  **Arithmetic/Reasoning-Quality Failures**:
    - **Operation Inversion**: Subtracting instead of adding (or vice versa).
    - **Unit/Rate Mistake**: Confusing "toys per hour" with "total toys".

## E. Proposed Algorithmic Improvements

| Proposed Fix | Target Family | Expected Benefit | Risk |
|--------------|---------------|------------------|------|
| **Stronger Direct Hybrid Seed** | Gold Absent | Higher chance of getting gold into the pool by adding one "standard" L1-style reasoning path. | Increased budget usage per case. |
| **PAL-Preserving Commitment Rule** | Selection Failure | Prevents overriding "strong" PAL results unless Frontier support is significantly higher (e.g., margin > 1). | Potential to keep a wrong PAL answer. |
| **Duplicate Wrong-Consensus Penalty** | Selection Failure | Detects when multiple traces are semantically identical (same arithmetic) and reduces their combined support weight. | High implementation complexity (requires semantic comparison). |
| **Frontier Branch Progress Scoring** | Gold Absent | Allocates more budget to branches that show "equation progress" or "numeric leaf maturation". | Requires reliable progress detection. |

## F. Recommended Next Action

**Highest Priority: Stronger Direct Seed / Direct Hybrid.**

Evidence from `wrong_casebook.csv` and `target_audit_diagnostic_cases.jsonl` shows that the current diverse roots often "over-think" or "over-decompose" simple problems, leading to gold-absent trees. Adding a single, high-quality "Direct Hybrid" seed (L1-style) as an incumbent would provide a stable anchor that the Frontier can then attempt to improve upon, rather than relying solely on diverse decompositions that might all fail.

### Candidate Patch Plan (Direct Hybrid Integration)
- **Files**: `experiments/strategy_seeded_semantic_diversity_frontier_v1.py`
- **Function**: `DirectReserveDiverseRootFrontierV1GuardedController.run`
- **Change**: Integrate the `direct_hybrid_seed` logic (from `direct_hybrid` variant) into the main guarded controller.
- **Regression Tests**: `openai_gsm8k_118`, `800` (check if gold enters the pool).
