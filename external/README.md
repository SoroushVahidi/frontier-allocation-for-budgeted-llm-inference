# External baseline code status

This directory tracks **neighboring methods** for the **adaptive reasoning budget / cross-controller frontier allocation** paper track in a **conservative, license-aware** way. Unless stated otherwise:

- **No external code is vendored** or imported as a submodule in this repository.
- Each subfolder is **documentation + provenance** for a clone-and-pin workflow.
- Machine-readable clone targets: `configs/external_baselines_registry.json`
- Integration audit artifact (regenerate locally):  
  `python scripts/generate_external_baseline_integration_report.py` → `outputs/external_baseline_integration_report.{json,md}`

```bash
python scripts/list_external_baselines.py
```

---

## A. Originally tracked baselines (process search / verifiers / policy TS)

| Baseline | Canonical title | Integration | Official / best-known code | License (last check) |
|---|---|---|---|---|
| ReST-MCTS* | ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search | `import_validated` (legacy: `RUNNABLE_ADJACENT`) | https://github.com/THUDM/ReST-MCTS | Unclear in repo (see note) |
| Tree-PLV | Advancing Process Verification … Tree-Based Preference Learning | `DISCUSS_ONLY` | Not verified (ACL / unclear GitHub) | Unknown |
| PGTS | Policy Guided Tree Search for Enhanced LLM Reasoning | `DISCUSS_ONLY` | Not confirmed | Unknown |
| Scaling Automated Process Verifiers | Scaling Automated Process Verifiers for LLM Reasoning | `DISCUSS_ONLY` | Not confirmed | Unknown |

Per-baseline notes:

- `external/rest_mcts/README.md`
- `external/tree_plv/README.md`
- `external/pgts/README.md`
- `external/scaling_automated_process_verifiers/README.md`

---

## B. High-priority additions (compute-optimal TTS, solve/verify, routing, selection)

These strengthen comparisons for **fixed test-time compute**, **verifier vs generator budget**, **routing/cascading**, and **Best-of-N-style selection**.

| Baseline | Topic | Integration | Official / cited code | License (GitHub API) |
|---|---|---|---|---|
| Snell et al. compute-optimal TTS (ICLR 2025) | Optimal test-time compute scaling | `BLOCKED` | **Paper:** OpenReview `4FWAwZtd2n`. **Code in registry:** [RyanLiu112/compute-optimal-tts](https://github.com/RyanLiu112/compute-optimal-tts) self-identifies with arXiv `2502.06703`; official mapping to target paper remains unverified. | **MIT** (on linked repo) |
| When To Solve, When To Verify | SC vs GenRM under budget | `import_validated` (legacy: `RUNNABLE_ADJACENT`) | https://github.com/nishadsinghi/sc-genrm-scaling (linked from arXiv abstract) | **Apache-2.0** |
| Cascade routing (ICML 2025) | Unified routing + cascading | `import_validated` (legacy: `RUNNABLE_ADJACENT`) | https://github.com/eth-sri/cascade-routing | **Apache-2.0** |
| MoB (Majority-of-the-Bests) | Bootstrapped Best-of-N improvement | `import_validated` (legacy: `RUNNABLE_ADJACENT`) | https://github.com/arakhsha/mob | **MIT** (repo); paper CC BY-NC-SA on OpenReview |
| s1: Simple test-time scaling (EMNLP 2025) | Test-time budget forcing / thinking-length scaling | `MODE_A_COMPLETE_MODE_B_PARTIAL` (v1: MODE A `adapter_based`, MODE B `import_validated`) | https://github.com/simplescaling/s1 | **Apache-2.0** |
| TALE (Token-Budget-Aware LLM Reasoning) | Per-instance token-budget-aware reasoning | `MODE_A_COMPLETE_MODE_B_PARTIAL` (v1: MODE A `adapter_based`, MODE B `import_validated`) | https://github.com/GeniusHTX/TALE | Unknown (re-check upstream) |
| L1 (LCPO length control) | RL-trained controllable reasoning length (Exact/Max) | `MODE_A_COMPLETE_MODE_B_PARTIAL` (v1: MODE A `adapter_based`, MODE B `import_validated`) | https://github.com/cmu-l3/l1 | **Apache-2.0** |

Per-baseline notes:

- `external/compute_optimal_tts/README.md`
- `docs/compute_optimal_tts_integration.md`
- `external/when_solve_when_verify/README.md`
- `docs/when_solve_when_verify_integration.md`
- `external/cascade_routing/README.md`
- `docs/cascade_routing_integration.md`
- `external/mob_majority_of_bests/README.md`
- `docs/mob_majority_of_bests_integration.md`
- `external/s1_simple_test_time_scaling/README.md`
- `external/tale_token_budget_aware_reasoning/README.md`
- `external/l1_length_control_rl/README.md`

---

## C. Optional / community / unclear-license references

| Baseline | Integration | Code | License | Notes |
|---|---|---|---|---|
| MCTS + LLM (community) | `discuss_only` (was `LINK_ONLY`) | https://github.com/NumberChiffre/mcts-llm | MIT | Not bound to a single canonical paper in this README; cite carefully. |
| LLM_Tree_Search (Waterhorse) | `discuss_only` | https://github.com/waterhorse1/LLM_Tree_Search | **Unclear** | Do not submodule until license confirmed. |
| BEST-Route (Microsoft) | `import_validated` (legacy: `RUNNABLE_ADJACENT`) | https://github.com/microsoft/best-route-llm | MIT (API); re-verify `LICENSE` in clone | Routing baseline via verified import-only adjacent protocol. |
| OpenR | `import_validated` (legacy: `RUNNABLE_ADJACENT`) | https://github.com/openreasoner/openr | MIT | Optional ecosystem / process reasoning stack via verified import-only adjacent protocol. |

---

## Reproducibility and safety policy

1. Prefer **clone + pin commit** next to this repo, not inside `external/` as copied trees.
2. When official code or licensing is unclear, **link only** and document uncertainty (see section A and Waterhorse entry).
3. Do not mirror large upstream repositories into this git history without explicit license permission.
4. For the **new paper track**, prioritize baselines in **section B** for empirical comparability with **frontier allocation** and **heterogeneous controller families**; use section A for **related work** and section C **selectively**.


### s1 fairness split note (new canonical)

- MODE A (`inference_only`): implemented runnable in-repo adapter for budget forcing on unchanged base model family.
- MODE B (`full_or_official`): strict official/full results import + verification path; usable when a valid package is provided, blocked/rejected otherwise.
- Canonical integration doc: `docs/s1_baseline_integration.md`.


### TALE fairness split note (new canonical)

- MODE A (`prompt_budgeting_inference_only`): runnable TALE-style in-repo prompt token-budgeting adapter.
- MODE B (`official_full_adapter`): strict official/full TALE results import + verification path with explicit TALE-vs-TALE-PT variant identity; usable when valid package is provided.
- Canonical integration doc: `docs/tale_baseline_integration.md`.

### L1 fairness split note (new canonical)

- MODE A (`inference_only_adapter`): runnable in-repo L1-style inference adapter with LCPO-Exact-style and LCPO-Max-style conditioning.
- MODE B (`official_full_adapter`): partial adapter/reporting path for official/full L1 outputs; may include RL-trained checkpoints; import contract via `scripts/verify_l1_mode_b_import.py` (not control-equivalent to MODE A).
- Canonical integration doc: `docs/l1_baseline_integration.md`.


## D. Reviewer-defensible completeness snapshot (2026-04-20 repair pass)

Canonical **v1** matrix: `outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json` and `docs/BASELINE_REPAIR_AND_STATUS_AUDIT_20260420T225833Z.md`.

This pass keeps comparability claims conservative:

- **s1 / TALE / L1**: legacy registry token `MODE_A_COMPLETE_MODE_B_PARTIAL`; v1 labels are MODE A `adapter_based` / `near_direct` and MODE B `import_validated` / `adjacent`. L1 MODE B now has parity import checking via `scripts/verify_l1_mode_b_import.py`.
- **BEST-Route / when_solve_when_verify / cascade / MoB / ReST-MCTS* / OpenR:** v1 **`import_validated`** adjacent neighbors (strict import validators). Historical `outputs/external_baseline_completeness/*_status.json` files may still say `runnable_adjacent` for the same operational class.

Use these artifacts to audit runnability and status:

- `python scripts/verify_external_baseline_runnability.py`
- `python scripts/generate_external_baseline_completeness_report.py`
- `python scripts/build_baseline_repair_and_status_audit.py`
- `docs/external_baseline_completeness_report.md`
- `outputs/external_baseline_completeness_summary.{json,csv}`

### Canonical v1 `status` values (registry + docs)

- `runnable_direct`
- `runnable_adjacent`
- `adapter_based`
- `import_validated`
- `discuss_only`
- `blocked`
- `broken_needs_repair`

Legacy tokens (`mode_a_only`, `mode_b_partial`, older `link_only` rows) may still appear in CSV columns named `category`; prefer `status_v1_*` columns in `outputs/external_baseline_completeness_summary.csv` and the baseline repair matrix.


---

## Required baseline families for current paper phase (2026-04-18 lock)

This repo keeps the baseline universe aligned to **fixed-budget next-step branch allocation**:

| Family | Canonical title | Class | Current external status | Essential? |
|---|---|---|---|---|
| qstar_deliberative_planning | Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning | direct | discuss-only (not-yet-integrated) | yes |
| lets_verify_step_by_step | Let's Verify Step by Step | adjacent completion-aware PRM/verifier | discuss-only | yes (adjacent) |
| rational_metareasoning_llm | Rational Metareasoning for Large Language Models | adjacent stop-vs-continue | discuss-only | yes (adjacent) |
| efficient_contextual_llm_cascades | Efficient Contextual LLM Cascades through Budget-Constrained Policy Learning | adjacent routing/cascade | import_validated (via cascade import validation) | optional unless scope broadens |
| best_arm_identification_fixed_budget | Best Arm Identification: A Unified Approach to Fixed Budget and Fixed Confidence | ingredient-adjacent boundary | discuss-only framing | yes (near-tie framing) |

Honesty rule: these entries are included for baseline completeness and reviewer expectation management; discuss-only entries are **not** presented as runnable in-repo baselines.
