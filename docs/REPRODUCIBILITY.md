# Reproducibility

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

## Offline Checks

```bash
make health
make test
```

These commands do not call external APIs.

## Manuscript Compilation

```bash
cd paper_performance_evaluation
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error main_with_titlepage.tex
```

The manuscript source and prebuilt submission package are included under
`paper_performance_evaluation/`.

## Live API Boundary

No live or paid API calls are required to inspect the released manuscript, tables, figures, or
claim-evidence maps. Live regeneration of proprietary closed-API outputs is outside the public
release boundary.

