# Submission Asset Audit - Pass 5

Date: 2026-08-01

## Official-Requirement Status

The Performance Evaluation Guide for Authors remains the journal-specific authority:
https://www.sciencedirect.com/journal/performance-evaluation/publish/guide-for-authors

Direct retrieval of that guide was blocked in this environment. Elsevier-wide requirements were
checked against official Elsevier/support pages and recorded in `JOURNAL_REQUIREMENTS.md`.

## Assets Finalized or Updated

| Asset | Status |
|---|---|
| `highlights.txt` | Finalized with five concise bullets, each under 85 characters. Requirement level for Performance Evaluation remains unresolved. |
| `cover_letter.md` | Updated to match manuscript title and avoid unsupported declaration claims. Originality/exclusivity statement requires author confirmation. |
| `declarations.md` | Updated with distinct placeholders for acknowledgments, funding, competing interests, data/code availability, API credits, and generative-AI tool names if required. |
| `title_page.tex` | Updated title, abstract wording, keywords, and corresponding-author marker. Author names, order, affiliations, email, ORCID remain placeholders. |
| `main.tex` | Anonymous full manuscript with placeholders for acknowledgments, funding, competing interests, data availability, and Elsevier AI disclosure section. |
| `main_with_titlepage.tex` | Converted to full title-page manuscript build using `title_page.tex`, not a placeholder body. |
| `JOURNAL_REQUIREMENTS.md` | Rewritten for Pass 5 with resolved vs unresolved Elsevier/Performance Evaluation items. |

## Metadata Requiring Author Confirmation

- Legal author names and author order.
- Affiliations.
- Corresponding author email and any submission-system phone/address fields.
- ORCID identifiers.
- Exact acknowledgments text, kept distinct for:
  - emotional/personal support;
  - academic or advisory assistance;
  - software/tooling support;
  - company-provided API credits.
- Funding declaration, including funder names and grant numbers, or explicit no-specific-grant text.
- Competing-interest declaration.
- Exact data/code availability statement, including repository, DOI, archive, supplement, or access restrictions.
- Whether company-provided API credits should be acknowledged only or also disclosed as funding/resource support.
- Exact generative-AI tool/service names if Elsevier's submission fields request them.
- Confirmation that the manuscript is not under consideration elsewhere and has not been previously published in the submitted form.

## Highlights and Graphical Abstract

- Highlights: prepared and ready to upload if Performance Evaluation requires or accepts them.
- Graphical abstract: not prepared. Requirement/optional status could not be verified from the
  official Performance Evaluation Guide in this environment and remains unresolved.

## Journal Requirements Still Unresolved

- Accepted article type.
- Highlights requirement level for Performance Evaluation.
- Graphical abstract requirement level.
- PE-specific abstract length/format beyond the provisional 200-word constraint.
- PE-specific keyword rule beyond the provisional maximum of six.
- PE-specific reference style; manuscript currently uses `elsarticle-num`.
- PE-specific declaration order/placement.
- PE-specific manuscript length guidance.
- PE-specific figure/table upload item types and naming conventions.

## Pass 6 Notes

- Do not rebuild the supplementary package until Pass 6.
- Pass 6 should flatten LaTeX source paths if the Elsevier submission system requires no subfolders.
- Pass 6 should decide whether to export the TikZ protocol schematic as a separate PDF artwork file
  or keep it as LaTeX source in the submission archive.
