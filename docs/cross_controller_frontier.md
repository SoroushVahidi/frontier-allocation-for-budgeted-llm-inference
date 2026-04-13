# Cross-controller frontier allocation (new paper track)

This repository’s **new** NeurIPS-style track studies **heterogeneous controller families** under a shared inference budget: building an empirical **strategy frontier** (accuracy vs. cost) and measuring **oracle headroom** when a meta-controller could allocate budget across families. This is intentionally separate from the older **binary cheap-vs-revise routing** manuscript line, which remains in the GSM8K pilot / adaptive branch-allocation scripts without changing their defaults.

## Where the frontier scaffold lives

- Single-dataset scaffold: `scripts/run_cross_strategy_frontier_allocation.py`
- **Multi-dataset matrix (new-paper empirical pass):** `scripts/run_new_paper_frontier_matrix.py` → `outputs/new_paper_frontier_matrix/<run_id>/`
  - Manuscript-style exports: `frontier_budget_dataset_summary.csv`, `frontier_allocation_oracle_gap.csv`, `frontier_allocation_controller_selector.csv`, `anti_collapse_min_expand_comparison.csv`, `new_paper_frontier_interpretation.md`, `frontier_allocation_execution_report.json`
- Single-run outputs: `outputs/cross_strategy_frontier_allocation_controller/<run_id>/`
  - `strategy_metrics.csv`, `selector_summary.csv`, `per_example_eval.jsonl`, `note.md`

## New heterogeneous families (frontier track)

### `verifier_guided_search`

Implements **sample-then-score** test-time compute: generate multiple candidate trajectories (via the standard `expand` path), then **rank candidates with a pluggable verifier score** and select the best (not simple self-consistency majority). Default verifier is a **lightweight proxy** using the existing API `verify` path (`LLMVerifyProxyVerifier`); the abstraction in `experiments/verifiers.py` is the intended hook for PRM-style process supervision or a stronger ORM later.

- Controller: `VerifierGuidedSearchController` in `experiments/controllers.py`
- Anti-collapse: `min_expansions_per_candidate` ensures each arm receives a minimum number of expands before verifier scoring when the global budget allows.

### `program_of_thought`

PAL/PoT-inspired **code generation + local sandbox execution**: one JSON-guided code generation call, then restricted `exec` with wall-clock timeout (`experiments/code_sandbox.py`). Artifacts (code, stdout/stderr, flags) are returned in `MethodResult.metadata["pot_output"]`.

- Controller: `ProgramOfThoughtController` in `experiments/controllers.py`
- Generator hooks: `APIBranchGenerator.generate_program_of_thought_answer`, `SimulatedBranchGenerator.generate_program_of_thought_answer`

## Cost accounting (transparent proxies)

- **Verifier-guided search**: `metadata["cost_proxy"]` reports candidate generation steps (`candidate_generations`) and verifier calls (`verifier_scoring_calls`).
- **Program-of-thought**: `metadata["cost_proxy"]` uses `{code_generation: 1, sandbox_execution: 1}`; `actions_used` is capped by the run budget (default 2 units when the budget allows).

## References (implementation mapping)

- **Snell et al. (test-time compute)**: motivates allocating budget between *sampling* and *verification/scoring* rather than only scaling width; `verifier_guided_search` separates generation from verifier-ranked selection.
- **PRM800K / “Let’s Verify Step by Step”**: informs the **pluggable `CandidateVerifier` protocol** and future PRM swap-in without changing the search loop.
- **PAL / Program-of-Thought**: informs the **code + execute** interface and artifact structure; execution is intentionally lightweight and repo-local.

## Commands

**Simulator smoke (no API, seconds):**

```bash
python scripts/smoke_frontier_methods.py
```

**Small end-to-end frontier run (simulated generator, loads HF subset):**

```bash
python scripts/run_cross_strategy_frontier_allocation.py --subset-size 4 --budgets 6 --seed 0
```

**Serious multi-dataset matrix (GSM8K + MATH mirror by default; optional `--try-gpqa`):**

```bash
python scripts/run_new_paper_frontier_matrix.py \
  --subset-size 48 --budgets 6,8,10,12 \
  --datasets openai/gsm8k,EleutherAI/hendrycks_math
```

**Small OpenAI-backed pilot (requires `OPENAI_API_KEY`):**

```bash
python scripts/run_cross_strategy_frontier_allocation.py --use-openai-api --subset-size 2 --budgets 8 --seed 1 --openai-model gpt-4.1-mini
```

Same flag works on the matrix runner: `python scripts/run_new_paper_frontier_matrix.py --use-openai-api --subset-size 8 --budgets 10 --datasets openai/gsm8k`.

## Limitations

- The default verifier is a **proxy**, not a trained PRM; swap `CandidateVerifier` implementations in `experiments/verifiers.py` for stronger supervision.
- The sandbox is **research-grade** (restricted builtins, SIGALRM timeout on Unix), not a hardened production isolate.
