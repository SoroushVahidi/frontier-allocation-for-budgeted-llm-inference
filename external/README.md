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
| ReST-MCTS* | ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search | `LINK_ONLY` | https://github.com/THUDM/ReST-MCTS | Unclear in repo (see note) |
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
| When To Solve, When To Verify | SC vs GenRM under budget | `LINK_ONLY` | https://github.com/nishadsinghi/sc-genrm-scaling (linked from arXiv abstract) | **Apache-2.0** |
| Cascade routing (ICML 2025) | Unified routing + cascading | `LINK_ONLY` | https://github.com/eth-sri/cascade-routing | **Apache-2.0** |
| MoB (Majority-of-the-Bests) | Bootstrapped Best-of-N improvement | `LINK_ONLY` | https://github.com/arakhsha/mob | **MIT** (repo); paper CC BY-NC-SA on OpenReview |
| s1: Simple test-time scaling (EMNLP 2025) | Test-time budget forcing / thinking-length scaling | `MODE_A_COMPLETE_MODE_B_PARTIAL` | https://github.com/simplescaling/s1 | **Apache-2.0** |
| TALE (Token-Budget-Aware LLM Reasoning) | Per-instance token-budget-aware reasoning | `MODE_A_COMPLETE_MODE_B_PARTIAL` | https://github.com/GeniusHTX/TALE | Unknown (re-check upstream) |
| L1 (LCPO length control) | RL-trained controllable reasoning length (Exact/Max) | `MODE_A_COMPLETE_MODE_B_PARTIAL` | https://github.com/cmu-l3/l1 | **Apache-2.0** |

Per-baseline notes:

- `external/compute_optimal_tts/README.md`
- `docs/compute_optimal_tts_integration.md`
- `external/when_solve_when_verify/README.md`
- `external/cascade_routing/README.md`
- `external/mob_majority_of_bests/README.md`
- `external/s1_simple_test_time_scaling/README.md`
- `external/tale_token_budget_aware_reasoning/README.md`
- `external/l1_length_control_rl/README.md`

---

## C. Optional / community / unclear-license references

| Baseline | Integration | Code | License | Notes |
|---|---|---|---|---|
| MCTS + LLM (community) | `LINK_ONLY` | https://github.com/NumberChiffre/mcts-llm | MIT | Not bound to a single canonical paper in this README; cite carefully. |
| LLM_Tree_Search (Waterhorse) | `discuss_only` | https://github.com/waterhorse1/LLM_Tree_Search | **Unclear** | Do not submodule until license confirmed. |
| BEST-Route (Microsoft) | `BLOCKED` | https://github.com/microsoft/best-route-llm | MIT (API); re-verify `LICENSE` in clone | Routing baseline. |
| OpenR | `LINK_ONLY` | https://github.com/openreasoner/openr | MIT | Optional ecosystem / process reasoning stack. |

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
- MODE B (`official_full_adapter`): partial adapter/reporting path for official/full L1 outputs; may include RL-trained checkpoints and is not apples-to-apples.
- Canonical integration doc: `docs/l1_baseline_integration.md`.


## D. Reviewer-defensible completeness snapshot (2026-04-16 pass)

This pass makes the currently integrated baselines fully auditable and keeps comparability claims conservative:

- **s1 / TALE / L1**: `MODE_A_COMPLETE_MODE_B_PARTIAL` with runnable MODE A scripts in-repo; s1 and TALE MODE B are usable via strict verified official import (TALE includes variant-separation checks), while L1 MODE B remains blocked without imported official/full outputs.
- **BEST-Route**: currently **`BLOCKED` for fair in-repo comparison claims**, not because upstream code is missing, but because the upstream response-bank + reward-model + router-training workflow is not yet mapped to this repo's frontier/action substrate under a shared cost protocol.

Use these artifacts to audit runnability and status:

- `python scripts/verify_external_baseline_runnability.py`
- `python scripts/generate_external_baseline_completeness_report.py`
- `docs/external_baseline_completeness_report.md`
- `outputs/external_baseline_completeness_summary.{json,csv}`

### Completeness classes used in this repo

- `runnable_direct`
- `runnable_adjacent`
- `mode_a_only`
- `mode_b_partial`
- `link_only`
- `discuss_only`
- `blocked`
