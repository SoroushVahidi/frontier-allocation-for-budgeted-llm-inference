# Final Editorial Corrections Audit

Date: 2026-08-01

Scope: final targeted correction pass for the Performance Evaluation manuscript. Work was confined to
`paper_performance_evaluation/`. No experiments, API calls, scientific results, statistics, central
claims, figures, or evidence boundaries were changed.

## Files Changed

Manuscript source:

- `main.tex`
- `main_with_titlepage.tex`
- `declarations.md`
- `refs.bib`
- `sections/02_related_work.tex`
- `sections/05_experimental_setup.tex`
- `sections/06_main_results.tex`
- `sections/07_search_vs_selection.tex`
- `sections/08_provider_analysis.tex`
- `sections/appendix.tex`
- `tables/table5_compute_matched_phase7.tex`

Supplementary/package material:

- `supplementary_material/HISTORICAL_DIAGNOSTICS_SUPPLEMENT.md`
- `supplementary_material/README.md`
- `submission_package_pass6_20260801T135817Z/latex_flat/*` source copies corresponding to the corrected manuscript
- `submission_package_pass6_20260801T135817Z/submission_assets/declarations.md`
- `submission_package_pass6_20260801T135817Z/submission_assets/title_page.tex`
- `submission_package_pass6_20260801T135817Z/anonymous_manuscript.pdf`
- `submission_package_pass6_20260801T135817Z/titlepage_manuscript.pdf`
- ZIP archives and package checksums refreshed after validation

## PEVA-Related References Added

Added three targeted references in Related Work, in one concise systems-performance paragraph.

1. Alessandro V. Papadopoulos, Laurens Versluis, Andre Bauer, Nikolas Herbst, Joakim von Kistowski,
   Ahmed Ali-Eldin, Cristina L. Abad, J. Nelson Amaral, Petr Tuma, and Alexandru Iosup,
   "Methodological Principles for Reproducible Performance Evaluation in Cloud Computing,"
   IEEE Transactions on Software Engineering, 47(8):1528--1543, 2021. DOI:
   `10.1109/TSE.2019.2927908`.
   Relevance: supports the manuscript's emphasis on explicit measurement and reporting practice for
   cloud performance evaluation.

2. Hengquan Guo, Hongchen Cao, Jingzhu He, Xin Liu, and Yuanming Shi, "POBO: Safe and optimal resource
   management for cloud microservices," Performance Evaluation, 162:102376, 2023. DOI:
   `10.1016/j.peva.2023.102376`.
   Relevance: directly anchors the paper in recent PEVA work on latency-resource uncertainty and
   resource management under dynamic cloud-service workloads.

3. Ahsan Ali, Xiaolong Ma, Syed Zawad, Paarijaat Aditya, Istemi Ekin Akkus, Ruichuan Chen, Lei Yang,
   and Feng Yan, "Enabling scalable and adaptive machine learning training via serverless computing on
   public cloud," Performance Evaluation, 167:102451, 2025. DOI: `10.1016/j.peva.2024.102451`.
   Relevance: supports PEVA fit for AI/cloud performance studies where scaling and public-cloud cost
   are part of the performance object.

The paragraph uses the citations to position the manuscript, not as ornamental citation padding.

## AI-Disclosure Changes

The declaration remains immediately before the references in both anonymous and identified manuscripts.

Heading changed to:

`Declaration of generative AI and AI-assisted technologies in the manuscript preparation process`

Declaration now separates manuscript preparation from research-process tool assistance:

- ChatGPT, Claude, and Cursor are described as assisting with drafting and revising prose during
  manuscript preparation.
- Research-process AI-assisted code inspection, code modification, and analysis organization are
  cross-referenced to the Experimental Protocol reproducibility subsection.
- The declaration states that the author reviewed and edited the tool-assisted prose and takes
  responsibility for the published content.

Methods/Reproducibility addition:

`AI-assisted code inspection, code modification, and analysis organization were human-reviewed; all reported outputs were independently verified using frozen scripts, records, and manifests.`

The text does not imply that AI systems made scientific decisions.

## Repository-Report Wording Removed

Replaced audit/process phrasing with journal-facing scientific prose:

- Obsolete submission-package assertion wording was replaced with artifact/replay-boundary wording.
- Obsolete codebase-maintenance wording was replaced with released-artifact wording.
- Obsolete protocol-registration wording was replaced with held-out protocol archival wording.
- Obsolete same-model-control wording was replaced with `Azure true-SC comparison`.
- `corrected Azure true same-model SC path` was replaced with `Azure true same-model SC control`.

Implementation-package details that remain relevant to reproducibility are expressed as replay-boundary
or supplementary-material statements.

## Repeated Caveats Consolidated

The Fireworks x GPQA protocol-blocked cell keeps one full explanation in Experimental Protocol and is
referenced briefly elsewhere.

Lower-bound Frontier token/USD telemetry keeps the main accounting explanation in Resource Accounting;
later mentions are brief cross-references or compact qualifiers.

FTA development adjacency and provider-transfer limits keep the method/setup explanation, while the
provider analysis now gives only a short transfer-evidence reminder.

## Appendix Material

Appendix J, the descriptive discovery-selection scatter diagnostic, was moved out of the manuscript
appendix into `supplementary_material/HISTORICAL_DIAGNOSTICS_SUPPLEMENT.md`. The manuscript now contains
a concise `Supplementary Diagnostics` pointer.

Appendix K was retained in the manuscript. The main text remains easier to interpret with its compute
detail and Pooled-4 tie-rule sensitivity values available in the paper, so moving it would reduce
self-contained interpretability.

All moved diagnostic values were preserved in the supplement, including `r = -0.185`, `n = 15`, the
unsupported status of the correlation, and the leave-one-out instability description.

## Table 3 Layout

Table 3 was changed from a resized fixed-width table to a `tabularx` layout with publication-size text.
Labels were shortened:

- `New model calls` to `Calls?`
- `Pool / call basis` to `Pool/call basis`
- `Structured generation policy` to `Structured generation`
- `No at selection` to `No`, with `no selector calls` moved into the basis description

All values and interpretations were preserved.

## Validation Results

Compiled successfully:

- Anonymous: `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`
- Identified: `latexmk -pdf -interaction=nonstopmode -halt-on-error main_with_titlepage.tex`
- Flat package anonymous source compiled successfully.
- Flat package identified source compiled successfully.

Final page counts:

- Anonymous manuscript: 32 pages.
- Identified manuscript with title page: 32 pages.

Validation checks:

- Zero missing citation keys.
- Zero duplicate BibTeX keys.
- Zero duplicate labels.
- Zero missing figure files.
- Zero unresolved placeholder strings found in source/PDF text scans.
- Anonymous PDF text scan found no author identity strings.
- Identified PDF retained author metadata and declarations.
- Table 3 page was visually inspected after rendering from the compiled PDF.

Remaining TeX warnings are small overfull/underfull boxes, including bibliography and Table 3 wrapping.
No fatal compile errors or unresolved references/citations were observed.

## Remaining Risks

- The paper remains a 32-page manuscript with appendices; it is self-contained but still dense.
- Closed-provider telemetry remains incomplete by design, so token/USD findings continue to be lower
  bounds where stated.
- The Fireworks x GPQA cell remains protocol-blocked and cannot be repaired without changing the
  experiment boundary.
