# Discovery failure taxonomy (gold-absent and coverage bottleneck)

Stable vocabulary for separating **discovery/coverage failures** from **selector mistakes** vs **runtime safety** issues. Mirrors language used across **`summary.json`**, pairwise diagnostics, and path-gap tooling.

Canonical **proxy diagnostic bundle (preferred):** **`outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/`** (Slurm **1018287**) — **`path_gap_summary.json`** carries explicit **`caveat`** strings: **estimate / proxy**, not observed gold trajectory unless otherwise proven.

Companion: **`docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md`**, **`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`**.

---

## Top-level buckets

| Category | Meaning |
|----------|---------|
| **Discovery failure** | Gold reasoning / answer **not reachable** within the recorder’s frontier under evaluated policy (**gold‑absent** from aggregated candidate representations / groups / tree summaries as defined by that CSV row). |
| **Selector failure** | Gold appears **eligible** post-discovery (candidate pool / trace contract) yet **wrong branch is committed** (**gold‑present-but-not‑selected**, verifier-selector recoverable regimes). |
| **Runtime safety / break failure** | System **incorrectly overrides** when incumbent was right, or violates budget / safety contract—track separately from frontier coverage statistics. |

**88-loss decomposition reference (`1018248` fully scored rerun):**

- `discovery_failure_count` / `gold_absent_count` = **66**
- `gold_present_but_not_selected_count` = **`selector_recoverable_count`** = **22**

Treat labels as **diagnostic-contract definitions** anchored to each manifest—not universal philosophy.

---

## Discovery sub‑tags (engineering vocabulary)

Operational phrases used in narratives and tooling—**overlap allowed**.

| Tag | Typical interpretation |
|-----|-----------------------|
| **Root-seeding failure** | Solver never obtains a plausible root derivation / foothold aligning with GSM8k gold structure. |
| **Wrong semantic diversity / wrong decomposition** | Diversity controller explores **orthogonal semantic families** that **avoid** fruitful factorization paths. |
| **Insufficient depth** | Budget/policy stops before branching depth statistically associated with reachable gold (**path-gap proxies** approximate this — see warning below). |
| **Premature commit** | Search stops allocating / commits answer before exploring branches that materially change outcome — distinct from verifier selection when commit policy is upstream of selector. |
| **Repeated-family overexpansion** | Anti-collapse bookkeeping shows **duplicate strategy families without productive spread** (**`repeated_same_family_expansion_count`**, **`branch_family_count`**, **`semantic_family`** diagnostics vary by exporter). |
| **Answer extraction / canonicalization mismatch** | Model produced acceptable reasoning fragment but normalized final string disagrees vs gold extractor—classify separately from qualitative “no idea”. |
| **Trace-missing / unclassifiable** | Instrumentation lacked mergeable trace ⇒ treat row as **`unknown`/requires manual review.** |
| **Definition / alignment mismatch** | **Baseline vs challenger** keyed on different **`gold`** presence detectors (cache join, verifier pool)—flag before interpreting pilot deltas (**`1018304`** caveat). |

---

## Field cheat‑sheet

Use row-level diagnostics only with each artifact’s **`README` / manifest / CSV header** authoritative definitions.

| Field (symbolic) | Typical role |
|------------------|----------------|
| **`gold_present_in_candidate_groups` / `_in_tree`** | Binary or graded signal from trace join—**upstream of selector**. |
| **`discovery_failure_gold_absent`** | Bundle-specific label implying gold absent classification under contract. |
| **`branch_count`**, **`candidate_group_count`** | Expansion breadth / pool multiplicity proxies. |
| **`branch_family_count`**, semantic family counters | Exploration diversity vs collapse. |
| **`answer_entropy`**, score spreads | Confidence / dispersion signals (often noisy). |
| **`repeated_same_family_expansion_count`** | Repeated-family heuristic without progress. |
| **`commit_step`**, **`budget_exhausted_or_early_commit`** | Policy position when search stopped (**path-gap proxies** ingest these columns). |

---

## Proxy-warning: **`estimated_missing_depth_to_gold`**, **`estimated_missing_actions_to_gold`**

Fields with **`estimated_*`** wording in **`per_case_path_gap_diagnostic`** exports are:

- **Heuristic projections** anchored to proxy classifiers—not guaranteed equal to minimal gold-path actions unless a dataset gold reasoning trace was surfaced and matched algorithmically **under provenance**.
- Quote only with **`path_gap_summary.json` caveat** acknowledgement.

Violating this rule inflates appendix claims into false observational causal statements.
