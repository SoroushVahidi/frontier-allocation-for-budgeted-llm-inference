# External baseline code status

This directory tracks code availability for the four main baselines in a conservative, license-aware way.

| Baseline short name | Canonical title | Code status | Official code link | License | Imported? | Reason if not imported |
|---|---|---|---|---|---|---|
| ReST-MCTS* | ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search | Official public repository found | https://github.com/THUDM/ReST-MCTS | Unclear / not declared in checked metadata | No | Repository appears public and official, but license is unclear, so direct import/submodule use was not performed. |
| Tree-PLV | Advancing Process Verification for Large Language Models via Tree-Based Preference Learning | No clearly verified official public Git repository; ACL software attachment observed | Not clearly identified (paper: https://arxiv.org/abs/2407.00390; ACL page: https://aclanthology.org/2024.emnlp-main.125/) | Unclear | No | Official maintained code repository and explicit license could not be confirmed. |
| PGTS | Policy Guided Tree Search for Enhanced LLM Reasoning | No clearly verified official public code repository | Not confirmed (paper: https://arxiv.org/abs/2502.06813; venue: https://icml.cc/virtual/2025/poster/45503) | Unknown | No | No clearly official public code repo/license found in checked sources. |
| Scaling Automated Process Verifiers | Scaling Automated Process Verifiers for LLM Reasoning | No clearly verified official public code repository | Not confirmed (paper: https://arxiv.org/abs/2410.08146; venue: https://iclr.cc/virtual/2025/poster/30649) | Unknown | No | No clearly official public code repo/license found in checked sources. |

## Per-baseline notes

- `external/rest_mcts/README.md`
- `external/tree_plv/README.md`
- `external/pgts/README.md`
- `external/scaling_automated_process_verifiers/README.md`

## Reproducibility and safety policy used

1. Prefer importing as a submodule only when official/public status and license are clear.
2. When official code or licensing is unclear, link only and document uncertainty explicitly.
3. Do not vendor/copy external code into this repository without explicit permission.
