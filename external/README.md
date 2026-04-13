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
| Snell et al. compute-optimal TTS (ICLR 2025) | Optimal test-time compute scaling | `LINK_ONLY` | **Paper:** OpenReview `4FWAwZtd2n`. **Code:** see note — [RyanLiu112/compute-optimal-tts](https://github.com/RyanLiu112/compute-optimal-tts) is MIT but titles a *different* paper; verify author release. | **MIT** (on linked repo) |
| When To Solve, When To Verify | SC vs GenRM under budget | `LINK_ONLY` | https://github.com/nishadsinghi/sc-genrm-scaling (linked from arXiv abstract) | **Apache-2.0** |
| Cascade routing (ICML 2025) | Unified routing + cascading | `LINK_ONLY` | https://github.com/eth-sri/cascade-routing | **Apache-2.0** |
| MoB (Majority-of-the-Bests) | Bootstrapped Best-of-N improvement | `LINK_ONLY` | https://github.com/arakhsha/mob | **MIT** (repo); paper CC BY-NC-SA on OpenReview |

Per-baseline notes:

- `external/compute_optimal_tts/README.md`
- `external/when_solve_when_verify/README.md`
- `external/cascade_routing/README.md`
- `external/mob_majority_of_bests/README.md`

---

## C. Optional / community / unclear-license references

| Baseline | Integration | Code | License | Notes |
|---|---|---|---|---|
| MCTS + LLM (community) | `optional_partial` | https://github.com/NumberChiffre/mcts-llm | MIT | Not bound to a single canonical paper in this README; cite carefully. |
| LLM_Tree_Search (Waterhorse) | `discuss_only` | https://github.com/waterhorse1/LLM_Tree_Search | **Unclear** | Do not submodule until license confirmed. |
| BEST-Route (Microsoft) | `LINK_ONLY` | https://github.com/microsoft/best-route-llm | MIT (API); re-verify `LICENSE` in clone | Routing baseline. |
| OpenR | `LINK_ONLY` | https://github.com/openreasoner/openr | MIT | Optional ecosystem / process reasoning stack. |

---

## Reproducibility and safety policy

1. Prefer **clone + pin commit** next to this repo, not inside `external/` as copied trees.
2. When official code or licensing is unclear, **link only** and document uncertainty (see section A and Waterhorse entry).
3. Do not mirror large upstream repositories into this git history without explicit license permission.
4. For the **new paper track**, prioritize baselines in **section B** for empirical comparability with **frontier allocation** and **heterogeneous controller families**; use section A for **related work** and section C **selectively**.
