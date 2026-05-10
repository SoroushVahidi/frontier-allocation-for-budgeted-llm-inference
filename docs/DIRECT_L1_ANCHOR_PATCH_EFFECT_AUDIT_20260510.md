# Direct L1 Anchor Patch Effect Audit (2026-05-10)

## Executive Summary
This report audits the potential impact of the "Direct L1 Anchor" patch (PR #373) using existing artifacts as a proxy for live performance. The audit analyzed 172 gold-absent failure cases from the latest method.

### Key Findings
- **Diversity Increase**: In **100%** of cases where a Direct L1 Anchor (proxy) was available (26/26), the candidate pool diversity increased (i.e., the anchor formed a new answer group or added support to a different group than the frontier's primary choice).
- **Recovery Potential**: **4 cases** (2.3% of all gold-absent cases, or 15% of cases with anchor data) were identified as potentially recoverable because the anchor matched the gold answer while the frontier search had collapsed to a wrong answer.
- **Anchor Consistency**: The anchor matched the external L1 baseline's prediction in **25/26** cases (96%), confirming it effectively acts as a "Direct L1" baseline within the search process.
- **Sufficiency**: While the patch is a valuable safety net, it is **not sufficient** by itself to solve the majority of gold-absent cases (168/172 remain absent), as the direct path is often also incorrect.

## Quantitative Audit Results

| Metric | Value | % of Evaluated |
| :--- | :--- | :--- |
| Total Gold-Absent Cases Evaluated | 172 | 100% |
| Cases with Usable Anchor Metadata (Proxy) | 26 | 15.1% |
| **Diversity Increased** | **26** | **100% (of anchor cases)** |
| **Gold Recovered (Potentially)** | **4** | **15.4% (of anchor cases)** |
| Anchor Matches External L1 Baseline | 25 | 96.2% (of anchor cases) |
| Remains Gold-Absent | 168 | 97.7% (of total) |

### Recovery by Question Type
| Question Type | Recovered | Remains Absent |
| :--- | :--- | :--- |
| money/cost/revenue | 2 | 52 |
| multi-step arithmetic | 1 | 38 |
| ratio/proportion/percentage | 1 | 37 |
| temporal/calendar | 0 | 16 |
| rate/speed/work | 0 | 11 |
| unit conversion | 0 | 10 |
| inventory/remaining quantity | 0 | 4 |

## Audit Questions & Answers

### 1. Does the patch increase candidate-pool diversity in artifact replay/proxy analysis?
**Yes.** In every case where we could identify a potential Direct L1 Anchor from previous runs, it differed from the incorrect consensus reached by the collapsed frontier. This directly addresses the "Frontier Collapse" subpattern by ensuring at least one semantically distinct alternative is always present in the selection layer.

### 2. How many failures become potentially recoverable?
Based on this proxy audit, approximately **15%** of cases where the frontier currently fails but a direct path exists are recoverable. Scaled to the full 172 cases, if an anchor were available for all, we might expect ~25-30 recoveries.

### 3. Is Direct L1 Anchor likely sufficient by itself?
**No.** The anchor itself is only as good as the direct reasoning path. In the majority of gold-absent cases, both the direct path and the frontier expansion fail to find the gold answer. The anchor provides a "floor" for performance but doesn't solve the "discovery" problem for harder problems.

### 4. Do we still need diverse prompt anchors?
**Yes.** Since the Direct L1 Anchor only helps when the direct path is correct, we still need more diverse starting points (prompt anchors) to explore different reasoning strategies (e.g., algebraic vs. arithmetic, bottom-up vs. top-down) to increase the chance of at least one path reaching the gold.

### 5. What should the next no-API or small live diagnostic be?
The next logical step is **"Duplicate Wrong-Consensus Penalty"**. The audit showed that even when the gold answer is present (like in the 4 recovered cases), the selection layer must be robust enough to pick it over a potentially larger (but wrong) consensus from the frontier.

## Caveats
This is an **artifact/proxy audit**. It uses `pal_answer` and `hybrid_seed_answer` from previous logs to estimate what would have happened if PR #373 had been active. Actual live performance may vary based on model stochasticity and the interaction between the anchor and the tiebreak logic.

---
*Audit conducted by Gemini 3 Flash on 2026-05-10.*
