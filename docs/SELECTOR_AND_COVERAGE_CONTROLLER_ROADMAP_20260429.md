# Selector and coverage controller roadmap (2026-04-29)

Purpose: one ordered map of **final-answer selection** vs **exploration/coverage** work. Final selectors fix wrong commits when evidence exists; coverage controllers change what the tree contains.

**Do not overclaim:** statuses below are engineering/planning labels unless a completed validation doc promotes them.

---

## A. Outcome-verifier answer-group rerank

**Method ID:** `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`

| Aspect | Status |
|--------|--------|
| Implementation | Live-runnable in `build_frontier_strategies(...)`; logic in `experiments/answer_grouped_outcome_verifier.py` + `DirectReserveFrontierGateV2OutcomeVerifierRerankV1Controller`. |
| Verifier backends | Default env uses mock; real runs must set `DR_V2_OV_RERANK_VERIFIER_BACKEND=cohere` (and optional `DR_V2_OV_RERANK_COHERE_MODEL=...`). |
| Target failure mode | **Present-not-selected:** gold-equivalent answer appears among DR-v2 candidates but DR-v2’s base selector picks wrong. |
| Evidence | Paired 100-case Cohere GSM8K budget-4 seed-11 **pending completion** for Cohere-backed verifier; treat mock-only timestamps as diagnostic provenance only. |

---

## B. PRM-style step-verifier rerank

**Method ID (planned):** `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`

| Aspect | Status |
|--------|--------|
| Implementation | **Not** registered as a live final-answer selector in this checkout; existing PRM-related code is branch/process scoring, not this roadmap item. |
| Target failure mode | **Polished wrong traces:** fluent reasoning with subtle step errors where coarse outcome verification is noisy. |
| Next step | Spec + live wiring only after A has a completed, interpreted evidence package. |

---

## C. Pairwise / Bradley–Terry answer-group rerank

**Method ID (notes):** `direct_reserve_semantic_frontier_v2_pairwise_bt_answer_group_rerank_v1`

| Aspect | Status |
|--------|--------|
| Implementation | **Notes / proposed only**; BT-family objects in repo are primarily **branch scorers**, not final answer-group selectors. |
| Target failure mode | **Poorly calibrated absolute verifier scores:** pairwise comparisons may stabilize ranks when scalar verdicts are unstable. |
| Next step | Keep separate from A/B until hypothesis is explicit (pairs over answer groups vs traces). |

---

## D. Coverage-aware commit controller

**Method family (future):** `direct_reserve_semantic_frontier_v2_coverage_aware_commit_v1` (name illustrative)

| Aspect | Status |
|--------|--------|
| Role | **Not** “another reranker after candidates exist.” Intended to improve **exploration / branching / reserve policy** when the correct answer is often **absent from the explored tree**. |
| Relationship to A–C | A–C assume multi-candidate or rerankable surface; D addresses **coverage and commit-before-discovery** failures upstream. |
| Status | Future controller family / notes or scaffold only in this checkout—do not conflate with selector-only fixes. |

---

## Ordering discipline

1. Close evidence on **A** with a **Cohere-backed** verifier run (distinct timestamp from mock-backed provenance).
2. Only then justify **B** (step-level cost/complexity).
3. Use **C** if absolute verifier scores prove unreliable in audit.
4. Use **D** when diagnostics show **absent-from-tree** dominates for a method family.

See also: `docs/SELECTOR_REGISTRY_CANONICAL_20260429.md`, `docs/METHOD_REGISTRY_CANONICAL_20260429.md`.
