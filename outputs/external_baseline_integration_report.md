# External baseline integration report

- Generated (UTC): `2026-04-13T21:35:25.511064+00:00`

## Priority candidates (new paper track)

| Baseline | Code | License | Status | Paper-ready |
|---|---|---|---|---|
| compute_optimal_tts | [link](https://github.com/RyanLiu112/compute-optimal-tts) | MIT on RyanLiu112 repo (GitHub API); Snell author code not verified here | LINK_ONLY | True |
| when_solve_when_verify | [link](https://github.com/nishadsinghi/sc-genrm-scaling) | Apache-2.0 (GitHub API metadata) | LINK_ONLY | True |
| cascade_routing | [link](https://github.com/eth-sri/cascade-routing) | Apache-2.0 (GitHub API metadata) | LINK_ONLY | True |
| mob_majority_of_bests | [link](https://github.com/arakhsha/mob) | MIT (repo); paper on OpenReview CC BY-NC-SA 4.0 | LINK_ONLY | True |
| mcts_llm_community | [link](https://github.com/NumberChiffre/mcts-llm) | MIT (GitHub API metadata) | LINK_ONLY | False |
| llm_tree_search_waterhorse | [link](https://github.com/waterhorse1/LLM_Tree_Search) | Unclear / not declared in GitHub API at verification time | DISCUSS_ONLY | False |
| best_route_microsoft | [link](https://github.com/microsoft/best-route-llm) | MIT (GitHub API); re-verify LICENSE file on default branch | LINK_ONLY | True |
| openr | [link](https://github.com/openreasoner/openr) | MIT (GitHub API metadata) | LINK_ONLY | False |

### Detail

#### compute_optimal_tts
- **Paper:** Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Parameters for Reasoning (Snell et al., ICLR 2025)
- **Link:** https://openreview.net/forum?id=4FWAwZtd2n
- **Code:** https://github.com/RyanLiu112/compute-optimal-tts
- **could_add_to_repository:** PARTIAL
- **integration_status:** LINK_ONLY
- **Added:** external/compute_optimal_tts/README.md; registry entry; explicit non-overclaim note
- **Missing:** Confirmed author-official repo for Snell et al.; RyanLiu112 repo README titles a different paper—treat as related MIT implementation, not verified author release; wrapper/adapter in this repo.
- **Reason:** Central reference for compute-optimal test-time scaling; cite Snell et al.; clone related repo only with correct attribution.

#### when_solve_when_verify
- **Paper:** When To Solve, When To Verify: Compute-Optimal Problem Solving and Generative Verification for LLM Reasoning
- **Link:** https://arxiv.org/abs/2504.01005
- **Code:** https://github.com/nishadsinghi/sc-genrm-scaling
- **could_add_to_repository:** YES
- **integration_status:** LINK_ONLY
- **Added:** external/when_solve_when_verify/README.md; registry entry
- **Missing:** No adapter; heavy upstream deps (vLLM / LLM Monkeys stack per upstream).
- **Reason:** Direct solve-vs-verify budget trade-off; arXiv links code explicitly.

#### cascade_routing
- **Paper:** A Unified Approach to Routing and Cascading for LLMs
- **Link:** https://proceedings.mlr.press/v267/dekoninck25a.html
- **Code:** https://github.com/eth-sri/cascade-routing
- **could_add_to_repository:** YES
- **integration_status:** LINK_ONLY
- **Added:** external/cascade_routing/README.md; registry entry
- **Missing:** No unified runner with this repo’s pilots; compare in separate environment.
- **Reason:** Strong routing/cascading baseline for heterogeneous models under cost constraints.

#### mob_majority_of_bests
- **Paper:** Majority of the Bests: Improving Best-of-N via Bootstrapping
- **Link:** https://openreview.net/forum?id=ZVtHNM3Dd2
- **Code:** https://github.com/arakhsha/mob
- **could_add_to_repository:** PARTIAL
- **integration_status:** LINK_ONLY
- **Added:** external/mob_majority_of_bests/README.md; registry entry; license duality noted
- **Missing:** Confirm camera-ready / venue page code URL if it differs from arakhsha/mob.
- **Reason:** Best-of-N family competitor for test-time selection under imperfect rewards.

#### mcts_llm_community
- **Paper:** (Community repo) MCTS + LLM — not a single canonical paper binding
- **Link:** https://github.com/NumberChiffre/mcts-llm
- **Code:** https://github.com/NumberChiffre/mcts-llm
- **could_add_to_repository:** PARTIAL
- **integration_status:** LINK_ONLY
- **Added:** external/mcts_llm_community/README.md; optional registry entry
- **Missing:** Official paper linkage; use only with correct citations to primary MCTS+LLM literature.
- **Reason:** Use cautiously; engineering reference more than a named paper baseline.

#### llm_tree_search_waterhorse
- **Paper:** AlphaZero-like Tree-Search for LLMs (see upstream repo citation)
- **Link:** https://github.com/waterhorse1/LLM_Tree_Search
- **Code:** https://github.com/waterhorse1/LLM_Tree_Search
- **could_add_to_repository:** NO
- **integration_status:** DISCUSS_ONLY
- **Added:** external/llm_tree_search_waterhorse/README.md; registry marked discuss_only
- **Missing:** Explicit OSS license file for safe redistribution or submodule policy.
- **Reason:** License ambiguity blocks conservative integration.

#### best_route_microsoft
- **Paper:** BEST-Route (Microsoft; see upstream README for full title)
- **Link:** https://github.com/microsoft/best-route-llm
- **Code:** https://github.com/microsoft/best-route-llm
- **could_add_to_repository:** YES
- **integration_status:** LINK_ONLY
- **Added:** external/best_route_microsoft/README.md; registry entry
- **Missing:** Adapter; confirm default branch and LICENSE path in clone.
- **Reason:** Microsoft OSS routing baseline; relevant to frontier/model routing story.

#### openr
- **Paper:** OpenReasoner / OpenR (see upstream)
- **Link:** https://github.com/openreasoner/openr
- **Code:** https://github.com/openreasoner/openr
- **could_add_to_repository:** YES
- **integration_status:** LINK_ONLY
- **Added:** external/openr/README.md; registry entry
- **Missing:** Narrow experiment integration; large stack.
- **Reason:** Useful ecosystem reference; optional depending on evaluation scope.

## Legacy tracked baselines (original four)

- **rest_mcts**: LINK_ONLY — https://github.com/THUDM/ReST-MCTS
- **tree_plv**: DISCUSS_ONLY — Not verified (ACL attachment / unclear GitHub)
- **pgts**: DISCUSS_ONLY — Not confirmed
- **scaling_automated_process_verifiers**: DISCUSS_ONLY — Not confirmed