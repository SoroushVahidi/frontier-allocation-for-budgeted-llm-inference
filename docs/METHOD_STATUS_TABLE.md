# Method status table

Conservative classification of **important method and selector names** appearing in current docs and scripts. For implementation detail, see `docs/METHOD_REGISTRY_CANONICAL_20260429.md` and the runtime strategy registry in code.

**Legend — `status`:** canonical (paper-facing or default contract), active (live engineering target), diagnostic (bounded / negative / mock-prone), historical, excluded (not in live builder), broken (known bad), external baseline.

**Legend — `paper_claim_eligible`:** whether headline manuscript claims are safe **without extra caveats**; most real-model rows are **limited** or **unknown** until promoted in `docs/PAPER_SOURCE_OF_TRUTH.md`.

| method_name | family | status | runtime_runnable | paper_claim_eligible | latest_known_evidence | safe_use | do_not_use_reason or caveat | relevant docs/artifacts |
|-------------|--------|--------|------------------|----------------------|------------------------|----------|------------------------------|-------------------------|
| `external_l1_max` | External L1 literature-style baseline | external baseline | yes | limited (as comparator) | Strong on multiple real-model GSM8K-style slices vs internal methods in diagnostic bundles | Primary comparator; anchor for “beat L1” framing | Do not invert into “we dominate L1” without matched, fully scored evidence | `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`, `outputs/cohere_real_model_cost_normalized_validation_*` |
| `external_l1_exact` | External L1 exact-length variant | external baseline | yes | limited | Fairness / manuscript tables | Compare under explicit length contract | Not interchangeable with `external_l1_max` as the single headline external | `outputs/l1_baseline/`, matched-surface docs |
| `strict_f3` | Strict phased F3 / broad_diversity + anti-collapse + hard early depth-3 | canonical (matched surface) | yes | yes (matched surface only) | `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md` etc. | Manuscript-facing internal representative on **matched** contract | Fragile margin vs `strict_gate1_cap_k6`; not “decisive superiority” wording | `docs/PAPER_SOURCE_OF_TRUTH.md`, paper tables |
| `strict_gate1_cap_k6` | Strict phased gate1 + cap k=6 / broad_diversity family | canonical (operational default surface) | yes | yes (broader surface) | Default strict-phased eval path | Broader operational default | Different surface than `strict_f3`; keep distinction explicit | `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md` |
| `strict_f2` | Strict phased depth-2 variant | diagnostic / secondary | yes | limited | Below `external_l1_max` on diagnostic slices | Secondary ablation / depth control | Not promoted as main internal winner | `docs/METHOD_REGISTRY_CANONICAL_20260429.md` |
| `broad_diversity_aggregation_*` (long runtime strings) | Controller scaffolding: diversity + answer-group + anti-collapse + refinement | active (components) | yes (via `strict_f3` / `strict_gate1_cap_k6` aliases) | mechanistic only | Component ablations, strict-phased bundles | Explain mechanism under budget | Do not cite raw string as user-facing method name; use `strict_f3` / `strict_gate1_cap_k6` | `scripts/run_cohere_real_model_cost_normalized_validation.py`, `experiments/frontier_matrix_core.py` |
| `strict_f3_anti_collapse_weak_v1` | Anti-collapse variant | diagnostic | yes | no | Casebook / trace collectors | Narrow diagnostics | Superseded paths for headline claims | `scripts/collect_external_loss_casebook.py` |
| `direct_reserve_semantic_frontier_v1` | DR semantic frontier v1 | historical | yes | no | Below external L1 in past evals | Legacy reference | Prefer v2 family | Registry |
| `direct_reserve_semantic_frontier_v2` | DR semantic frontier v2 (“DR-v2”) | active | yes | limited | ~0.56 vs ~0.72 L1 on cited 100-case references (diagnostic, not dominance) | Main generator for candidate pools and L1-defeat engineering | **Does not prove broad superiority over `external_l1_max`** | `docs/METHOD_EVIDENCE_AND_FAILURE_SUMMARY_20260429.md`, cost-normalized outputs |
| `direct_reserve_semantic_frontier_v2_thresholded_ordered` | Ordered thresholded diagnostic controller | excluded | no (not in live strategy builder per registry) | no | Diagnostic-only registry row | Offline/diagnostic only | Not live-runnable in standard builder | `docs/METHOD_REGISTRY_CANONICAL_20260429.md` |
| `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` | DR-v2 + inline outcome-verifier rerank (method row) | active | yes | unknown | Runnable; Cohere-backed 100-case headline still gated in claims map | Experiments vs DR-v2 baseline | Mock-backed runs ≠ Cohere verifier evidence | `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`, `tests/test_answer_grouped_outcome_verifier.py` |
| `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1` | DR-v2 + PRM-style step verifier rerank | active | yes | unknown | Tests + validation hooks; completed real-model 100-case not asserted here | PRM baseline / alternative rerank | Mock default not Cohere evidence; JSON fragility | `tests/test_prm_step_verifier_rerank.py`, registry |
| `outcome_verifier_answer_group_selector_v1` | Post-hoc answer-group outcome verifier selector | canonical for **recovery track** | yes | limited | Selected on 47-case recovery package; audited | **Recovery selector-evidence track**; rerun with cached scores | **Not runtime-promoted**; not L1 defeat; requires matched slices for comparisons | `configs/selected_selector_current.json`, `docs/CURRENT_SELECTOR_DECISION.md`, `outputs/final_selector_decision_20260501T175547Z/` |
| `trace_quality_heuristic` | Verifier **scorer mode** (heuristic, not Cohere) | diagnostic | yes (as `--scorer-mode`) | no | Runner-up vs cached Cohere on recovery package | Cheap offline comparison; ablations | Not the selected production scorer for recovery track | `scripts/run_outcome_verifier_answer_group_selector.py` |
| `conservative_trace_support_selector_v1` | Non-API conservative selector | diagnostic | yes | no | Rejected fallback on recovery package (0 net fixes) | Negative baseline / safety | Do not present as competitive selector | `outputs/conservative_trace_support_selector_*`, tests |
| `self_consistency_majority_selector` | Literature majority-vote selector | active (baseline) | yes | limited | Implemented for matched-slice comparison | No-API baseline over **existing pools** | Not a new method contribution; compare only matched paired slices | `docs/LITERATURE_SELECTOR_BASELINES.md`, `scripts/run_self_consistency_majority_selector.py` |

## Important distinctions (read twice)

1. **`outcome_verifier_answer_group_selector_v1`** is the **current selected selector for the recovery selector-evidence track**. It is **not** automatically **runtime-promoted** to the main controller, and it is **not** evidence of beating **`external_l1_max`** on broad slices.
2. **`external_l1_max`** is the **baseline to beat** in much of the real-model narrative; repository docs **forbid** careless dominance claims (`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`).
3. **`direct_reserve_semantic_frontier_v2`** is a **central active internal generator family**, but **current evidence does not establish broad superiority over `external_l1_max`**.

## PRM / process-rerank naming

- **Live final-answer PRM rerank row:** `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`.
- Other **PRM partial-scoring / branch** machinery may exist as **diagnostic** or historical paths—do not conflate with the live final-answer PRM selector row; see `docs/METHOD_REGISTRY_CANONICAL_20260429.md` (“PRM partial-scoring variants”).

## Anti-collapse / answer-group preservation

These appear primarily as **components inside** the long `broad_diversity_aggregation_*` runtime strings backing `strict_f3` / `strict_gate1_cap_k6`, not as separate promoted paper method IDs. Treat as **mechanistic** contributions unless a dedicated promotion doc says otherwise.
