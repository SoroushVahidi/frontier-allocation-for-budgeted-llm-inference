# Main baselines

## Canonical baseline taxonomy lock (2026-04-18 final pass)

For this repository phase, baselines are grouped as:

**Normalized v1 status matrix (machine-readable):** `outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json` — see `docs/BASELINE_REPAIR_AND_STATUS_AUDIT_20260420T225833Z.md`.

1. **Direct baselines** — genuinely close to fixed-budget next-step branch allocation / deliberate branch expansion control.
2. **Adjacent but important baselines** — reviewer-expected neighbors that are not control-space-equivalent (completion-aware PRM/verifier selection, stop-vs-continue adaptive compute, routing/cascades, and small-gap fixed-budget allocation comparators).
3. **Ingredient / framing references** — formulation and signal references that should inform framing but not be oversold as direct empirical baselines.

### Required family status table (project-locked)

| Family | Canonical paper title | Repo short name | Class | Runnable status | Essential this paper phase? | Why it matters here | Why not fully equivalent when non-direct |
|---|---|---|---|---|---|---|---|
| Deliberative planning search | Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning | qstar_deliberative_planning | **direct** | discuss-only (provenance-hardened; integration-blocked pending verified official artifacts) | **essential** | Closest published family to deliberate multi-step branch planning under budget pressure. | N/A (direct family target). |
| Completion-aware PRM/verifier | Let's Verify Step by Step | lets_verify_step_by_step | **adjacent** | partial_runnable_adjacent (official adjacent contract lane via PRM800K public assets) | **essential adjacent** | Core completion/process-evidence family relevant to bounded correction in disagreement slices. | Optimizes verifier/process scoring, not explicit next-step branch allocation over active frontier. |
| Adaptive stop-vs-continue compute | Rational Metareasoning for Large Language Models | rational_metareasoning_llm | **adjacent** | discuss-only (framing/theory) | **essential adjacent** | Provides value-of-computation framing for continuation decisions under cost. | Primarily stop/continue metareasoning framing, not direct multi-branch frontier allocation control. |
| Routing / cascades | Efficient Contextual LLM Cascades through Budget-Constrained Policy Learning | efficient_contextual_llm_cascades | **adjacent** | runnable-adjacent via cascade routing import validator | optional (essential only if scope broadens to routing-first framing) | Reviewer-expected adaptive-compute routing comparator. | Route/cascade action space differs from branch-level next-step allocation among active reasoning branches. |
| Small-gap fixed-budget allocation | Best Arm Identification: A Unified Approach to Fixed Budget and Fixed Confidence | best_arm_identification_fixed_budget | **ingredient-adjacent boundary** | discuss-only framing reference | **essential framing** | Strongest theoretical lens for hard near-tie disagreement states and gap-sensitive budget allocation. | Classical bandit abstraction is not a direct empirical LLM reasoning baseline stack. |

## ReST-MCTS*

- **Canonical title:** *ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search
- **Venue / year:** NeurIPS 2024
- **Role in our project:** Process-reward-guided tree search baseline.
- **Problem formulation:** Uses process rewards and tree search to improve reasoning trace collection and final reasoning quality.
- **Core method:** MCTS-style search guided by a process reward model, followed by self-training over collected traces.
- **Main benchmarks:** MATH, SciBench, and college-level scientific reasoning tasks.
- **Official code:** https://github.com/THUDM/ReST-MCTS
- **Data / benchmark links:** See the official repository and paper resources for benchmark setup details; exact reconstruction of full data flows may require manual verification.
- **Reproducibility caveats:** Full upstream training/evaluation reproduction remains heavyweight; this repo now supports a stabilized adjacent contract lane via `scripts/run_rest_mcts_adjacent_integration.py` plus strict import validation via `scripts/verify_rest_mcts_import.py`, with conservative claim boundaries.
- **How it differs from our target method:** It uses reward-guided search, but does not cleanly formulate marginal budget allocation over reasoning trees with strong guarantees.

## Tree-PLV

- **Canonical title:** *Advancing Process Verification for Large Language Models via Tree-Based Preference Learning*
- **Venue / year:** 2024 arXiv
- **Role in our project:** State-level / step-level process verifier baseline.
- **Problem formulation:** Learns a process verifier from tree-constructed preference pairs over intermediate reasoning states.
- **Core method:** Best-first tree construction plus preference learning for step-level verification.
- **Main benchmarks:** GSM8K, MATH, CSQA, and StrategyQA.
- **Official code:** Not found in official sources.
- **Data / benchmark links:** TODO: Add verified links to the paper's benchmark/task pages after manual source confirmation.
- **Reproducibility caveats:** The paper is public, but no official code was identified.
- **How it differs from our target method:** It improves step-level verification, but does not directly solve budgeted online compute allocation over reasoning trees.

## PGTS

- **Canonical title:** *Policy Guided Tree Search for Enhanced LLM Reasoning*
- **Venue / year:** ICML 2025
- **Role in our project:** Learned controller / policy-guided tree-search baseline.
- **Problem formulation:** Casts reasoning as a tree-structured sequential decision problem where a policy decides how search proceeds.
- **Core method:** RL-style learned policy over actions such as expand, branch, backtrack, and terminate.
- **Main benchmarks:** Mathematical reasoning, logical deduction, and planning benchmarks (exact full list should be verified from canonical materials).
- **Official code:** Not clearly found in official sources.
- **Data / benchmark links:** TODO: Add authoritative benchmark links once the canonical artifact page and any official repository are confirmed.
- **Reproducibility caveats:** Benchmark details and official code availability are not fully clear from currently surfaced sources.
- **How it differs from our target method:** It learns a search controller, but our target is a cleaner formal budget-allocation problem with stronger theoretical emphasis.

## Scaling Automated Process Verifiers

- **Canonical title:** *Scaling Automated Process Verifiers for LLM Reasoning*
- **Venue / year:** ICLR 2025
- **Role in our project:** Fixed-budget guided search / process-verifier baseline.
- **Problem formulation:** Trains automated process verifiers that provide dense progress signals for search and reinforcement learning.
- **Core method:** Process Advantage Verifiers (PAVs) used for test-time search and online reinforcement learning.
- **Main benchmarks:** Reasoning benchmarks discussed in the paper; exact full benchmark list should be manually verified before final tabulation.
- **Official code:** Not found in official sources.
- **Data / benchmark links:** TODO: Add verified benchmark and artifact links from official paper/repository pages.
- **Reproducibility caveats:** The canonical paper is clear, but official public code was not identified.
- **How it differs from our target method:** It is a strong fixed-budget process-verifier baseline, but it does not explicitly formulate marginal compute allocation over intermediate reasoning states as the central optimization problem.

## Baseline coverage summary

These four baselines form a strong comparison set because they collectively span (i) reward-guided search, (ii) step-level verifier learning, (iii) policy-based search control, and (iv) automated verifier-guided fixed-budget reasoning. This coverage aligns well with the nearest methodological neighbors to adaptive test-time compute allocation while preserving a clear boundary around methods that do not make marginal budget allocation itself the primary optimization objective.

## Extended external index (new paper track)

For **compute-optimal test-time scaling**, **solve-vs-verify budget trade-offs**, **routing/cascading**, **Best-of-N / MoB-style selection**, and optional community tree-search references, see the audited link-only registry:

- **`external/README.md`** — master table (sections A–C) + per-baseline README paths
- **`configs/external_baselines_registry.json`** — machine-readable clone URLs (no vendored code)
- **`python scripts/generate_external_baseline_integration_report.py`** → `outputs/external_baseline_integration_report.{json,md}`

This extends the comparison set beyond the original four **without** implying that every linked repository is author-official for every cited paper; each `external/<name>/README.md` states license and uncertainty explicitly.

## Working novelty boundary

- Our intended method treats marginal compute allocation across intermediate reasoning states as the central optimization target, rather than only improving search heuristics or verifier quality.
- Our intended framing emphasizes explicit online budget allocation under constrained test-time compute, rather than fixed-budget execution with improved guidance signals alone.
- Our intended project aims for a cleaner formal problem statement around allocation decisions over reasoning trees, with stronger theoretical emphasis.
- Our intended comparison axis distinguishes *where* extra compute is allocated in the tree, not only *how* candidate steps are scored or selected.

## s1 integration status for this repository (2026-04 fair split)

To keep comparisons reviewer-defensible, this repo now distinguishes two s1 modes:

- **MODE A (primary fair matched-substrate path):** inference-only s1 budget forcing on the same base model family as our method, no extra s1K post-training (`adapter_based` / `near_direct` in v1 taxonomy — not a claim of reproducing the full upstream s1 training stack).
- **MODE B (secondary, separately labeled):** full/official s1 path including post-training where feasible; **import-validated reporting only** (`import_validated`), not control-equivalent to MODE A frontier comparisons.

Implementation references:
- `docs/s1_baseline_integration.md`
- `configs/s1_budget_forcing_inference_only_v1.json`
- `configs/s1_full_or_official_adapter_v1.json`
- `scripts/run_s1_budget_forcing_baseline.py`
- `scripts/run_s1_baseline_comparison_bundle.py`

Reporting policy:
- Always report fixed-budget quality and cost-quality frontier summaries.
- Always keep MODE A and MODE B claims separated in text/tables.

## TALE integration status for this repository (2026-04 fair split)

TALE (Token-Budget-Aware LLM Reasoning) is integrated as a **published adjacent adaptive-budget baseline** with explicit mode separation:

- **MODE A (`prompt_budgeting_inference_only`)**: runnable in-repo TALE-style prompt/inference token-budgeting adapter (primary fair comparison path; `adapter_based` / `near_direct`).
- **MODE B (`official_full_adapter`)**: secondary official/full adapter reporting path (may include TALE-PT/post-training; `import_validated`, not merged with MODE A as control-equivalent).

Implementation references:
- `docs/tale_baseline_integration.md`
- `configs/tale_prompt_budgeting_v1.json`
- `configs/tale_official_adapter_v1.json`
- `scripts/run_tale_baseline.py`
- `scripts/run_tale_comparison_bundle.py`

Methodological caveat:
- TALE is per-instance token budgeting, while our primary method is frontier stop-vs-act allocation; report matched-compute comparisons and avoid direct control-equivalence claims.

## L1 integration status for this repository (2026-04 fair split)

L1 (*Controlling How Long A Reasoning Model Thinks With Reinforcement Learning*) is integrated as a **direct / near-direct budget-control baseline** with explicit mode separation:

- **MODE A (`inference_only_adapter`)**: runnable in-repo L1-style length-conditioning adapter supporting both `external_l1_exact` (exact target length) and `external_l1_max` (max-length bound); `adapter_based` / `near_direct`.
- **MODE B (`official_full_adapter`)**: secondary official/full adapter reporting path (may include RL-trained L1 checkpoints; `import_validated` via `scripts/verify_l1_mode_b_import.py` when importing official packages; not control-equivalent to MODE A).

Implementation references:
- `docs/l1_baseline_integration.md`
- `configs/l1_inference_adapter_v1.json`
- `configs/l1_official_full_adapter_v1.json`
- `scripts/run_l1_baseline.py`
- `scripts/run_l1_comparison_bundle.py`

Methodological caveat:
- L1 controls token-length generation behavior, while our primary method controls frontier stop-vs-act allocation decisions; keep matched-budget reporting explicit and avoid strict control-equivalence claims.

## verifier_guided_search (internal baseline)

- **Role:** Fixed-budget internal simulator baseline implemented in the frontier evaluation stack (not an external paper reproduction).
- **v1 taxonomy:** `runnable_direct` with `control_equivalence: adjacent` versus external PRM / “Let’s Verify Step by Step” claims — cite as an **implementation neighbor** only.
- **Evidence:** Appears in committed full-method comparison bundles (for example `outputs/full_method_comparison_bundle/20260419T214335Z/aggregate_comparison_summary.json`); regenerate comparisons via `scripts/run_full_method_comparison_bundle.py` when updating tables.


## External baseline completeness (reviewer-defensible, 2026-04-16 pass)

### compute_optimal_tts status update (2026-04-16)

- `compute_optimal_tts` is now tracked as **`blocked`** (not vague link-only) because the target paper in this repo is OpenReview `4FWAwZtd2n` (ICLR 2025), while the linked codebase self-identifies around arXiv `2502.06703`; official equivalence is unverified.
- A conservative provenance+blocker protocol is now the canonical integration artifact for this baseline:
  - `docs/compute_optimal_tts_integration.md`
  - `outputs/external_baseline_completeness/compute_optimal_tts_status.json`
  - `outputs/external_baseline_completeness/compute_optimal_tts_status.md`
- Manuscript-safe usage now: discussion-only adjacent baseline until paper↔repo mapping is author-verified and a fair matched-cost adapter protocol is implemented.


For manuscript-safe claims, treat external baselines as follows:

- **Usable now for primary matched-substrate comparisons (MODE A adapters only; v1 `adapter_based` / `near_direct`):**
  - s1 via `configs/s1_budget_forcing_inference_only_v1.json` + `scripts/run_s1_budget_forcing_baseline.py`
  - TALE via `configs/tale_prompt_budgeting_v1.json` + `scripts/run_tale_baseline.py`
  - L1 via `configs/l1_inference_adapter_v1.json` + `scripts/run_l1_baseline.py`
- **MODE B (import-validated only; v1 `import_validated` / `adjacent`):** s1, TALE, and L1 share the same pattern: usable **only** when valid official/full packages are supplied and pass `scripts/verify_s1_mode_b_import.py`, `scripts/verify_tale_mode_b_import.py`, or `scripts/verify_l1_mode_b_import.py` respectively (TALE MODE B additionally enforces TALE-vs-TALE-PT variant separation). Otherwise runs remain blocked pending `official.results_path`.
- **BEST-Route:** adjacent baseline with strict import-validation lane (`scripts/verify_best_route_import.py`) plus a focused runtime pass (`scripts/run_best_route_runtime_stabilization_pass.py`) that demonstrates a stable tiny synthetic router run under non-upstream compatibility pins; full official benchmark-faithful stack reproduction remains unclaimed.
- **when_solve_when_verify:** v1 `official` + `import_validated` via `scripts/verify_when_solve_when_verify_import.py`, with canonical adjacent contract runner `scripts/run_when_solve_when_verify_adjacent_integration.py` and `configs/when_solve_when_verify_adjacent_comparison_contract_v1.json` (fixed-budget solve-vs-verify adjacent slices only; not frontier-allocation direct).
- **cascade_routing:** v1 `import_validated` via `scripts/verify_cascade_routing_import.py`.
- **mob_majority_of_bests:** v1 `import_validated` via `scripts/verify_mob_import.py`.
- **rest_mcts:** stabilized partial-runnable adjacent lane via `scripts/run_rest_mcts_adjacent_integration.py` + `configs/rest_mcts_adjacent_comparison_contract_v2.json` with canonical outputs under `outputs/rest_mcts_adjacent_integration/<run_id>/`, plus strict import validation via `scripts/verify_rest_mcts_import.py`; no full ReST-MCTS training loop in-repo.
- **openr:** v1 `import_validated` via `scripts/verify_openr_import.py`.

Companion artifacts:
- `docs/external_baseline_completeness_report.md`
- `docs/BASELINE_REPAIR_AND_STATUS_AUDIT_20260420T225833Z.md`
- `outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json`
- `outputs/external_baseline_completeness_summary.json`
- `outputs/external_baseline_completeness_summary.csv`
- `outputs/external_baseline_runnability/<run_id>/verification_summary.json`

Safe wording rule:
- Do **not** claim full official reproduction for any baseline unless the official training/inference stack is actually run in this repo and auditable from artifacts.


## Final baseline-scope guardrail (2026-04-18)

- Do not reframe this baseline section as a generic routing paper, generic adaptive-TTC survey, or best-of-N paper.
- Keep the center on **fixed-budget next-step branch allocation**, **continuation-value core**, and **bounded completion-aware correction in near-tie disagreement slices**.
- Preserve status honesty with explicit labels: `runnable_direct`, `runnable_adjacent`, `adapter_based`, `import_validated`, `discuss_only`, `blocked`.

## Q*-family separation update (2026-04-22 unofficial adapter lane)

The repository now keeps a strict two-lane Q*-family split:

1. **Official paper record** — `qstar_deliberative_planning`
   - remains `discuss_only` and provenance-hardened,
   - no verified official runnable artifact path is claimed.

2. **Unofficial runnable comparator** — `qstar_style_adapter`
   - contract: `configs/qstar_style_adapter_contract_v1.json`
   - runner: `scripts/run_qstar_style_adapter.py`
   - artifacts: `outputs/qstar_style_adapter/<run_id>/`
   - role: caveated conceptual-family stress test only.

Table guardrail:
- If reported, label as **"Q*-style adapter (unofficial, caveated)"**.
- Do not place this lane in tables that imply official Q* reproduction.
