# ReST-MCTS* external code note

- **Canonical title:** ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search
- **Paper:** https://arxiv.org/abs/2406.03816
- **Official paper link status:** Confirmed (arXiv).
- **Official code link:** https://github.com/THUDM/ReST-MCTS
- **Repository status:** Exists, appears official (matches arXiv-linked code URL), and is publicly reachable.
- **Venue / year:** NeurIPS 2024
- **License:** **Unclear / not declared** in repository metadata at verification time (`license: null` via GitHub API; no top-level `LICENSE` file observed).
- **Import status:** Runnable-adjacent via strict import validation (no vendored code; no direct reproduction claim).
- **Reason:** This repo keeps conservative boundaries: adjacent-only verified import of upstream-produced artifacts, without claiming full in-repo reproduction or control-equivalence.

## Canonical adjacent protocol in this repo

- Integration note: `docs/rest_mcts_integration.md`
- Validator: `scripts/verify_rest_mcts_import.py`
- Status artifacts:
  - `outputs/external_baseline_completeness/rest_mcts_status.json`
  - `outputs/external_baseline_completeness/rest_mcts_status.md`

## Setup notes (upstream)

If you want to run upstream code locally, clone directly from the official repository and follow its instructions:

1. `git clone https://github.com/THUDM/ReST-MCTS.git`
2. Review upstream documentation and dependency files (e.g., `requirements_mistral.txt`, `requirements_sciglm.txt`) before environment setup.
3. Verify license terms manually if you plan to redistribute or vendor any part of the code.

## Verification notes (this repo)

- Public accessibility verified using `git ls-remote`.
- License metadata checked via GitHub API.
