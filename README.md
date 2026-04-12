# Adaptive Reasoning Budget Allocation

> **Status: Early-stage research. The problem formulation is under active development and subject to change.**

## Short Description

This repository supports research into how to allocate a fixed inference-time compute budget across intermediate reasoning states (or reasoning-tree nodes) in large language models (LLMs). The goal is to improve the chance of reaching a correct final solution when local value estimates are noisy.

This is a theory + experiments project aimed at a TCS/AI research paper. It is not a product or application.

---

## Current Research Question

> *Given a fixed inference budget, how should compute be allocated across partially explored reasoning states to maximize the probability of reaching a correct final answer, when local value estimates are noisy?*

---

## Initial Motivation

Recent work has shown that allocating more compute at inference time can significantly improve LLM reasoning quality (e.g., chain-of-thought, tree-of-thought, best-of-N). However, most existing approaches use fixed or heuristic compute schedules. There is limited theoretical understanding of:

- How to optimally allocate a fixed budget across competing reasoning branches.
- How noise in local value estimates (e.g., from a verifier or reward model) affects allocation decisions.
- Whether adaptive strategies provably outperform static baselines under realistic conditions.

This project aims to fill that gap.

---

## Planned Directions

- Formal model of the budget allocation problem over a reasoning tree.
- Analysis of greedy, uniform, and adaptive allocation policies under noisy value estimates.
- Empirical evaluation on math reasoning benchmarks (GSM8K, MATH, AIME-style problems).
- Matched-budget comparisons to isolate the effect of allocation strategy.
- Connections to bandit theory, search algorithms, and prior work on verifier-guided decoding.

---

## Repository Structure

```
adaptive-reasoning-budget-allocation/
├── README.md                  # This file
├── LICENSE
├── CONTRIBUTING.md
├── TODO.md
├── Makefile
├── pyproject.toml
├── requirements.txt
├── .gitignore
│
├── docs/
│   ├── problem_statement.md   # Current candidate problem formulation
│   ├── related_work.md        # Literature map (in progress)
│   └── research_plan.md       # Milestones and next steps
│
├── theory/
│   └── README.md              # Formal models, lemmas, theorem sketches
│
├── experiments/
│   └── README.md              # Planned benchmark experiments
│
├── configs/
│   └── README.md              # Experiment configuration files
│
├── scripts/
│   └── smoke_test.py          # Minimal repo smoke test
│
├── references/
│   └── README.md              # How references and notes are tracked
│
└── outputs/                   # Gitignored experiment outputs
```

---

## Setup Instructions

**Requirements:** Python 3.10+

```bash
# Clone the repository
git clone https://github.com/SoroushVahidi/adaptive-reasoning-budget-allocation.git
cd adaptive-reasoning-budget-allocation

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
make setup

# Verify everything works
make smoke
```

---

## Early Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Repository setup, literature review | In progress |
| 1 | Problem formalization, toy experiments | Planned |
| 2 | Theoretical analysis (greedy vs. adaptive policies) | Planned |
| 3 | Benchmark experiments (GSM8K, MATH) | Planned |
| 4 | Paper writing | Planned |

---

## Notes

- The problem formulation is not final. Notation, objectives, and assumptions will evolve as the research progresses.
- This is a private early-stage research repository. Do not share results or drafts without permission.
- See `TODO.md` for the current task list.
