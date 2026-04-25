# SAFE_CLAIMS_FOR_NEURIPS_2026

Conservative claim policy for manuscript text as of 2026-04-25.

## 1) Claims supported by current canonical evidence
- The repository supports reproducible, matched-contract evaluation for budgeted LLM inference.
- Canonical paper-facing tables/plots/figures are reproducibly generated from committed scripts.
- Method comparisons can be stated safely on the matched evaluation surface defined in canonical artifact docs.
- The project provides auditable evidence bundles (tables, fairness checks, and artifact maps) appropriate for bounded claims.

## 2) Claims supported only as diagnostic observations
- Real-model validations (OpenAI/Cohere) provide useful stress-test evidence, but should be framed as diagnostic/supporting evidence.
- Some diagnostic variants (direction guard, typed strategy seeded, family-normalized reranking, shallow probes) provide mechanism insights, not final promoted-method evidence.
- Loss-case analysis indicates recurring failure mechanisms around selection and tree coverage.

## 3) Claims not currently supported
- **Not supported:** robust superiority over all external baselines.
- **Not supported:** universal provider-agnostic dominance in real-model comparisons.
- **Not supported:** that diagnostic variants have repaired the full 150-loss-case set.
- **Not supported:** that current branch-level trace coverage is complete for older historical runs.

## 4) Required explicit caveats
- Do **not** claim robust superiority over external baselines unless matched and canonical evidence directly supports it.
- Real-model comparisons currently include slices where an external baseline outperforms our method.
- Diagnostic variants have not yet repaired the 150 loss cases.
- Loss analysis indicates two key failure modes: **present-not-selected** and **absent-from-tree**.
- Older runs did not always save full branch traces; some deep trace claims require reruns.

## 5) Unsafe phrases to avoid
Avoid terms such as:
- “robustly superior,”
- “universally better,”
- “state-of-the-art across settings,”
- “fully solved,”
- “decisive dominance,”
- “complete trace-level proof across all runs.”

## 6) Recommended manuscript wording
Prefer language such as:
- “on the matched canonical surface, results indicate …”
- “diagnostic real-model evidence suggests …”
- “evidence is mixed and highlights failure modes …”
- “current results support bounded claims under explicit contracts …”
- “future work is required for robust cross-provider and loss-case closure.”

## 7) Practical pre-submission claim gate
Before adding any new claim:
1. Map claim to a canonical artifact path.
2. Verify contract match (dataset/provider/budget/seed semantics).
3. Confirm wording reflects bounded, conservative interpretation.
4. If evidence is diagnostic-only, label it explicitly as diagnostic.
