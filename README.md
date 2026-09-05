# Frontier Allocation for Budgeted LLM Inference

This repository contains code, manuscript source, and release artifacts for the
Performance Evaluation manuscript:

**Nominal Budgets and Realized Resources in Closed-API Large-Language-Model Inference:
A Performance Evaluation Protocol**

The project studies how nominal inference budgets differ from realized resources in closed-API
large language model (LLM) evaluation. It separates discovery from final-answer selection,
records successful completions, retries, tokens, latency, and cost where available, and reports
blocked outcomes instead of silently dropping them.

> **Note:** this is a separate project/manuscript from
> [-adaptive-llm-inference](https://github.com/SoroushVahidi/-adaptive-llm-inference)
> (adaptive test-time compute routing, submitted to Knowledge-Based Systems). This
> repository studies nominal-vs-realized budget accounting for closed-API inference,
> submitted to *Performance Evaluation*.

## What Is Included

- `experiments/`: core controller, selector, normalization, and accounting code.
- `scripts/`: offline replay and repository validation entry points.
- `configs/`: configuration files and adapter contracts.
- `tests/`: lightweight offline regression tests.
- `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/`: compact canonical matrix audit.
- `paper_performance_evaluation/`: LaTeX manuscript source, compiled PDFs, figures, highlights,
  declarations draft, and submission package.

Historical private review packages, venue-specific migration notes, local logs, credentials,
virtual environments, and generated experiment workspaces are intentionally not part of this
public release.

## Installation

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

The default installation supports offline replay, audits, tests, and manuscript inspection. Live
provider integrations require additional optional dependencies and credentials, but live API calls
are not required for the released manuscript artifacts.

## Offline Checks

```bash
make health
make test
```

These commands do not call external APIs.

## Manuscript

Compile from the manuscript directory:

```bash
cd paper_performance_evaluation
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error main_with_titlepage.tex
```

Precompiled PDFs and the submission source ZIP are included for convenience.

## Reproducibility Boundary

The manuscript reports deterministic replay over frozen records and audits. This repository
contains the compact public release artifacts needed to inspect the reported tables, manuscript
source, and claim-evidence mapping. It does not contain credentials and does not require paid or
live API calls.

The datasets named in the manuscript are publicly available:

- GSM8K
- MATH-500
- GPQA-Diamond
- StrategyQA

## License And Citation

Code is released under the MIT License. See `CITATION.cff` for citation metadata.

