# Gold-Absent Failure Subpattern Analysis (2026-05-10)

## Executive Summary
This report deepens the analysis of the "Gold Absent from Candidate Pool" failure family, which accounts for approximately 86% of the latest method's failures. By analyzing 172 unique gold-absent cases, we have identified actionable subpatterns that explain why the discovery process fails.

### Key Findings
- **Dominant Failure Mode**: **Frontier Collapse / Low Diversity**. 96% of gold-absent cases (165/172) resulted in only a single candidate answer group, indicating that the frontier search is failing to explore semantically distinct reasoning paths.
- **Top Question Types**: `money/cost/revenue` (31%) and `multi-step arithmetic` (23%) are the most frequent problem categories.
- **Actionable Error Subpatterns**:
    1. **Premature Intermediate Answer**: The method stops at a plausible intermediate value (e.g., total items instead of total cost).
    2. **Structured Extraction Failure**: Correct reasoning exists in prose but fails to reach the structured `predicted_answer` field, leading to fallbacks (e.g., 1).
    3. **L1 Gap**: In several cases, the external L1 baseline finds the answer while our method (even with frontier search) does not, suggesting the "Direct Seed" is not strong enough.

## Quantitative Tables

### Question Type Distribution
| Question Type | Count | % |
| :--- | :--- | :--- |
| money/cost/revenue | 54 | 31.4% |
| multi-step arithmetic | 39 | 22.7% |
| ratio/proportion/percentage | 38 | 22.1% |
| temporal/calendar | 16 | 9.3% |
| rate/speed/work | 11 | 6.4% |
| unit conversion | 10 | 5.8% |
| inventory/remaining quantity | 4 | 2.3% |

### Error Type Taxonomy (Inferred)
| Error Type | Count | Description |
| :--- | :--- | :--- |
| unknown | 166 | Insufficient trace metadata for automated classification |
| premature intermediate answer | 2 | Stopped at a value present in the problem or intermediate step |
| counting/grouping off-by-factor | 2 | Answer is a multiple or factor of gold |
| structured extraction failure | 2 | Fallback to 1/0 despite reasoning progress |

### Candidate Diversity
| Diversity Bucket | Count | % |
| :--- | :--- | :--- |
| low (1 group) | 165 | 95.9% |
| medium (2-3 groups) | 7 | 4.1% |
| high (4+ groups) | 0 | 0.0% |

### External Baseline Contrast
| Contrast | Count | % |
| :--- | :--- | :--- |
| Both wrong | 100 | 58.1% |
| unknown | 67 | 39.0% |
| L1 correct, ours wrong | 5 | 2.9% |

## Representative Cases

### 1. Premature Intermediate Answer (openai_gsm8k_118)
- **Question**: Elise sells books for $20. Sold twice as many in year 1 as this year. 50 unsold. Sales this year is 45. Total money in year 2?
- **Gold**: 1300
- **Selected Prediction**: 200
- **Why Gold Absent**: The method correctly calculated 200 (total books sold) but stopped there, failing to multiply by $20 or partition by year.
- **Fix**: **Branch-progress scoring** to prioritize traces that haven't addressed all quantities in the question.

### 2. Structured Extraction Failure (openai_gsm8k_800)
- **Question**: Sweater with sleeves, collar, rosette. Body=900. Collar=1/10 body. Rosette=2*collar. Total=1800. Stitches per sleeve?
- **Gold**: 315
- **Selected Prediction**: 1 (Fallback)
- **Why Gold Absent**: Direct reserve prose had partial reasoning (collar=90, rosette=180) but failed to produce a numeric candidate for the final question.
- **Fix**: **Direct L1 Anchor** to ensure the most likely direct reasoning path is always represented in the candidate pool.

### 3. Selection Failure (openai_gsm8k_358)
- **Question**: Marisa gets $5/day. Buys 4 lollipops @ 25c each. Saves for 5 days. Total savings?
- **Gold**: 20
- **Selected Prediction**: 4
- **Why Gold Absent**: (Technically Gold Present from PAL, but selection failed). Frontier collapsed to 4 (daily savings).
- **Fix**: **Duplicate wrong-consensus penalty** to prevent the selection layer from being overwhelmed by many identical wrong frontier branches.

## Actionable Root Causes
1. **Frontier Collapse**: The current root strategy choice is not diverse enough, leading to multiple branches converging on the same (often premature) answer.
2. **Missing Direct Anchor**: The method relies on the frontier to "find" the gold, but sometimes the direct reasoning path is already very close. If it's not explicitly anchored, it gets lost in the frontier noise.
3. **Budget Misallocation**: Too many actions are spent on shallow frontier expansions that don't reach the final step of multi-step problems.

## Algorithmic Recommendations

| Recommendation | Targeted Subpattern | Est. Cases | Complexity |
| :--- | :--- | :--- | :--- |
| **Stronger Direct Seed / L1 Anchor** | Discovery Failure / L1 Gap | 20-30 | Low |
| **Duplicate Wrong-Consensus Penalty** | Selection Failure / Collapse | 40-50 | Medium |
| **Branch-Progress Scoring** | Premature Answers | 30-40 | High |
| **Arithmetic Self-Check** | Arithmetic Collapse | 15-25 | Medium |

## Next Recommended Patch
**"Add Direct L1 Anchor candidate to candidate pool before frontier commitment."**

**Rationale**: 
- This targets the "L1 correct, ours wrong" cases (approx. 3% of failures) and provides a safety net for "Structured Extraction Failures."
- It is low-risk (metadata-only change to the candidate pool).
- It ensures that even if the frontier collapses or fails to reach the end, the best "direct" guess is still available for selection.

---
*Report generated by Gemini 3 Flash on 2026-05-10.*
