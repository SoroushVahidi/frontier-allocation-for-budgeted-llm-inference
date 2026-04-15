# Main baselines

These baselines cover key neighboring approaches to adaptive test-time compute allocation in multi-step LLM reasoning: process-reward-guided tree search, step-level process verification, policy-guided tree search, and fixed-budget guided search with automated process verifiers. Together, they provide a focused comparison set spanning search guidance, intermediate-state scoring, and learned decision control under compute constraints.

## ReST-MCTS*

- **Canonical title:** *ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search
- **Venue / year:** NeurIPS 2024
- **Role in our project:** Process-reward-guided tree search baseline.
- **Problem formulation:** Uses process rewards and tree search to improve reasoning trace collection and final reasoning quality.
- **Core method:** MCTS-style search guided by a process reward model, followed by self-training over collected traces.
- **Main benchmarks:** MATH, SciBench, and college-level scientific reasoning tasks.
- **Official code:** https://github.com/THUDM/ReST-MCTS
- **Data / benchmark links:** See the official repository and paper resources for benchmark setup details; exact reconstruction of full data flows may require manual verification.
- **Reproducibility caveats:** Code is public, but generated traces and the exact full data pipeline may require careful reconstruction.
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

- **MODE A (primary apples-to-apples):** inference-only s1 budget forcing on the same base model family as our method, no extra s1K post-training.
- **MODE B (secondary, separately labeled):** full/official s1 path including post-training where feasible; not apples-to-apples with unchanged-base-model controller comparisons.

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

- **MODE A (`prompt_budgeting_inference_only`)**: runnable in-repo TALE-style prompt/inference token-budgeting adapter (primary fair comparison path).
- **MODE B (`official_full_adapter`)**: secondary official/full adapter reporting path (may include TALE-PT/post-training; not apples-to-apples).

Implementation references:
- `docs/tale_baseline_integration.md`
- `configs/tale_prompt_budgeting_v1.json`
- `configs/tale_official_adapter_v1.json`
- `scripts/run_tale_baseline.py`
- `scripts/run_tale_comparison_bundle.py`

Methodological caveat:
- TALE is per-instance token budgeting, while our primary method is frontier stop-vs-act allocation; report matched-compute comparisons and avoid direct control-equivalence claims.
