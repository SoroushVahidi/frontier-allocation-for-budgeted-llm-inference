# Final Submission Audit

Date: 2026-08-01

Scope: final pre-submission editorial, layout, compliance, package, and anonymity audit for the
Performance Evaluation conversion. Work was restricted to `paper_performance_evaluation/`. No
experiments, API calls, scientific-value edits, commits, or pushes were performed.

## Overall Readiness

Submission readiness: ready for author-confirmed submission, with administrative placeholders still
open.

Confidence: high for manuscript coherence, numerical consistency, package compilability, and
anonymous-review cleanliness; medium for journal-specific administrative requirements because the
Performance Evaluation ScienceDirect Guide for Authors page was discoverable but not fully
machine-readable in this environment.

## Continuous-Paper Review

- Abstract is self-contained: it defines the closed-API budgeted-inference setting, nominal budget,
  realized resources, identical-pool control, protocol-blocked cell, matrix size, principal
  numerical results, and contribution boundary.
- Introduction now has a complete roadmap including the offline counterfactual section.
- Related work, framework/method, setup, results, limitations, discussion, and conclusion have
  distinct roles and do not read as a repository report.
- Novelty is framed as a performance-evaluation protocol and measurement/accounting contribution,
  not as a general claim that Frontier or FTA is superior.
- Statistical claims remain bounded to paired McNemar/Holm tests, bootstrap intervals, and
  descriptive checks as stated in the manuscript.
- Limitations remain concrete and evidence-bounded: provider/dataset scope, protocol-blocked
  Fireworks x GPQA, adapter fidelity, incomplete token/USD telemetry, and proprietary-regeneration
  limits.

## Repetition Audit

Automated repeated-sentence scan over `main.pdf` found no repeated sentence with nine or more words
after numeric normalization. Manual continuous read found no remaining repeated caveat that should
be removed without harming local comprehension.

Canonical locations remain:

- Nominal versus realized resources: Sections 3 and 9, summarized in Discussion.
- Frontier/FTA as controlled case-study objects: Introduction and Method.
- Incomplete token/USD telemetry: Setup, Resource Accounting, and Limitations with short
  cross-references only.
- Single-cell self-consistency scope: Section 6.3 and Appendix O.
- Adapter fidelity: Setup, Table 1, Limitations, and Appendix C.
- Blocked Fireworks x GPQA: Setup and Table 2.
- Provider-transfer reversal: Section 8.
- Held-out selector choosing Pooled-4: Section 7.3.
- No general superiority claim: abstract boundary, method scope, limitations, and conclusion.

## Figure And Table Audit

- Figures retained: 5 total. All are referenced in prose.
- Tables retained: 10 total. All are referenced in prose.
- No figure or table was scientifically altered in this pass.
- Figure readability: acceptable for Elsevier preprint PDF; no clipping, overlap, missing file, or
  unreadable legends detected in the compiled PDF.
- Table readability: dense appendix tables still produce underfull warnings, but content remains
  readable at publication scale and no table requires a font reduction below acceptable readability.
- Captions are publication-facing and state scope/caveats where the figure/table could otherwise be
  overread.

## Journal-Compliance Checklist

Official sources checked on 2026-08-01:

- Performance Evaluation Elsevier shop page: confirms scope in modeling, measurement, and
  evaluation of computing and communication systems, including measurement techniques and
  AI-based services. URL: https://shop.elsevier.com/journals/performance-evaluation/0166-5316
- Elsevier highlights support page: confirms 3--5 highlights, maximum 85 characters each unless a
  journal guide says otherwise. URL:
  https://www.elsevier.support/publishing/answer/how-do-i-include-highlights-with-my-manuscript
- Elsevier LaTeX instructions: confirms use of `elsarticle`, source archive requirements, and that
  Editorial Manager cannot process LaTeX submissions with subfolders. URL:
  https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions
- Elsevier graphical abstract guidance: confirms separate graphical-abstract upload conventions,
  preferred dimensions, and file types when a graphical abstract is submitted. URL:
  https://www.elsevier.com/researcher/author/tools-and-resources/graphical-abstract
- Elsevier generative-AI policy: confirms the required declaration title/placement pattern and
  prohibits general-purpose generative-AI image tools for graphical abstracts. URL:
  https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals

Checklist:

- Article type: manuscript fits Performance Evaluation scope as an original methodological /
  measurement article; exact Editorial Manager article-type menu remains unresolved until login.
- Review model: unresolved from official accessible source.
- Abstract limit: unresolved for Performance Evaluation-specific hard limit; current abstract is
  concise and self-contained.
- Keywords: five keywords provided; exact PE-specific count unresolved.
- Highlights: `highlights.txt` has five bullets, each <=85 characters.
- Graphical abstract: no graphical abstract prepared; status remains unresolved because PE-specific
  requirement could not be confirmed. If required, do not use a general-purpose generative-AI image
  tool.
- Bibliography style: numbered Elsevier style used with bundled `elsarticle-num.bst`; exact
  PE-specific style unresolved from accessible official source.
- Declarations: acknowledgments, funding, competing interest, data availability, and generative-AI
  disclosure are present as separate manuscript sections/placeholders.
- LaTeX source: flat uploadable source package prepared because Elsevier states subfolders cannot be
  processed by Editorial Manager.
- Figures/tables: source package includes figures, tables, bibliography, `.bbl`, and `.bst` files.
- Manuscript length: no accessible PE-specific hard limit found; final PDF is 34 pages in Elsevier
  preprint formatting.

## Compile And Validation Results

Root manuscript:

- `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`: success.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error main_with_titlepage.tex`: success.
- `main.pdf`: 34 pages; metadata author `Anonymous Author(s)`.
- `main_with_titlepage.pdf`: 34 pages; title-page metadata uses public author name with affiliation details pending author confirmation.

Flat package source:

- `latex_flat/main.tex`: success, 34 pages.
- `latex_flat/main_with_titlepage.tex`: success, 34 pages.

Validation:

- Undefined references/citations: zero.
- Duplicate labels: zero.
- Missing figure files: zero.
- Unreferenced figures/tables/equations: zero.
- Bad rendered strings checked and absent: `Appendix Appendix`, doubled paragraph punctuation,
  concatenated arXiv/venue strings.
- Anonymous manuscript text/metadata scan: no placeholder author string, ORCID placeholder,
  placeholder email, or local username.
- Package ZIP extraction: no errors.
- Supplementary ZIP extraction: no errors.
- Supplementary checksums: all OK.
- Secret/path scan: no absolute local paths or secret-like strings found; one benign manifest line
  says the supplement scan found no prior-venue private-workflow wording.

## Page Count

- Final anonymous manuscript PDF: 34 pages.
- Final title-page manuscript PDF: 34 pages.
- Main narrative through conclusion: 22 pages in the compiled PDF.
- Declarations and references: pages 22--26 depending on float/page break.
- Appendix: pages 27--34.

## Remaining Weaknesses And Editorial Risks

- The study is still a protocol and measurement paper over a finite 15-cell closed-API matrix, not a
  broad algorithmic superiority result; editors or referees may ask for more budgets, more providers, or
  real-time regeneration.
- Fireworks x GPQA remains protocol-blocked rather than scored; this is methodologically correct but
  may attract questions.
- L1/S1/TALE are closed-API adapters, not official reproductions.
- Token/USD telemetry and paid retries remain lower bounds in parts of the matrix.
- The single-cell same-model self-consistency comparison does not constitute a full self-consistency
  bakeoff.
- Administrative fields still need author confirmation before submission.

## Author Confirmation Required

- Legal author names and order.
- Affiliations and corresponding author email.
- ORCID/phone/address fields if required by Editorial Manager.
- Funding statement or explicit no-specific-funding statement.
- Competing-interest statement.
- Data/code availability URL or DOI.
- Final acknowledgments, keeping emotional support, academic/advisory assistance, software support,
  and API credits distinct.
- Exact names of generative-AI tools/services if Elsevier's submission form requires them.
