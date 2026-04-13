# When To Solve, When To Verify (Singhi et al.)

- **Canonical title:** *When To Solve, When To Verify: Compute-Optimal Problem Solving and Generative Verification for LLM Reasoning*
- **Paper:** https://arxiv.org/abs/2504.01005
- **Official code (linked from arXiv abstract v2):** https://github.com/nishadsinghi/sc-genrm-scaling
- **License (GitHub API, verification time):** **Apache-2.0**
- **Import status:** **Linked only** — no submodule, no vendored code in this repo.
- **Role for this project:** Baseline for **splitting fixed inference budget** between solution generation (e.g. self-consistency) and **generative verification (GenRM)**; directly relevant to verifier-guided search and frontier methods.

## Setup notes (upstream)

```bash
git clone https://github.com/nishadsinghi/sc-genrm-scaling.git
```

Follow upstream README for vLLM / Large Language Monkeys dependencies.

## Integration scaffold (this repo)

- Registry entry: `configs/external_baselines_registry.json` → `when_solve_when_verify`
- This directory contains **documentation only**.
