# Supplementary Reproducibility Package

**Manuscript:** Selective Deferral for Budgeted LLM Answer Selection: Failure-Trace Signals under Matched-Budget Evaluation  
**Package built:** 2026-05-21  
**Purpose:** Reviewer-facing reproducibility materials for the MLJ submission.

---

## What is included

- `docs/` — Claims documentation, evidence maps, current-state summary, and artifact status tables. These document the provenance and scope of all reported claims.
- `scripts/paper/` — Table and figure data-generation scripts used to produce the paper's reported results from processed artifacts.
- `outputs/paper_tables/` — Processed CSV table data corresponding to reported tables and figures.
- `outputs/paper_plot_data/` — Plot data CSVs used to generate the manuscript figures.
- `tables/` — LaTeX source for the reproducibility and supporting appendix tables included in the submitted manuscript.

## Reproducing reported tables and figures

The reported tables (Table 1–9, Appendix A) can be verified offline using the processed CSV files in `outputs/paper_tables/` and `outputs/paper_plot_data/` together with the scripts in `scripts/paper/`. No API calls are required to inspect or verify the reported numbers from these processed artifacts.

Full re-execution of the evaluation pipeline (generating new candidate answers) requires commercial API access to Cohere `command-r-plus-08-2024` and may produce slightly different results due to API non-determinism.

## What is not included

- No `.env` files, API keys, credentials, or secrets.
- No raw provider logs or large unprocessed `outputs/` directories.
- No private local notes or cache files.

## Release policy

Upon acceptance, the implementation and processed evaluation artifacts will be published in a versioned public repository with a persistent identifier (Zenodo DOI). Additional processed artifacts can be provided to reviewers upon request.
