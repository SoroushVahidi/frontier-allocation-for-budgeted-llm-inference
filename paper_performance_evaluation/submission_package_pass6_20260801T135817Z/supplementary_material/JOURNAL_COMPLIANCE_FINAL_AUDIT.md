# Journal Compliance Final Audit

Date: 2026-08-01

Sources checked were official Elsevier or Performance Evaluation pages where
accessible. Performance Evaluation's ScienceDirect guide-for-authors page was
discoverable but not fully accessible in this environment, so journal-specific
items not confirmed from accessible official text are marked unresolved.

## Official Sources Used

- Performance Evaluation journal page: https://shop.elsevier.com/journals/performance-evaluation/0166-5316
- Elsevier Guide for Authors hub: https://www.elsevier.com/subject/next/guide-for-authors
- Elsevier LaTeX instructions: https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions
- Elsevier highlights help: https://www.elsevier.support/publishing/answer/how-do-i-include-highlights-with-my-manuscript
- Elsevier generative-AI journal policy: https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals
- Elsevier artwork checklist: https://www.elsevier.com/about/policies-and-standards/author/artwork-and-media-instructions/artwork-formats-checklist
- Elsevier graphical abstract guidance: https://www.elsevier.com/researcher/author/tools-and-resources/graphical-abstract
- Elsevier data statement page: https://www.elsevier.com/researcher/author/tools-and-resources/research-data/data-statement

## Confirmed Requirements

| Item | Status | Action |
| --- | --- | --- |
| Scope fit | Confirmed from Performance Evaluation journal page | Manuscript framed as performance measurement/protocol study. |
| Broad article type | Confirmed broadly: original work, tutorials, surveys | Prepared as original measurement/protocol article. |
| Keywords | Confirmed from Elsevier guide hub: up to six keywords | Five keywords retained. |
| Abstract style | Confirmed generally: self-contained; avoid undefined abbreviations | Abstract defines LLM, Pooled-4, FTA and is self-contained. |
| Highlights format | Confirmed: 3-5 bullets, <=85 characters each | `highlights.txt` has five bullets, all <=85 characters. |
| Generative-AI disclosure | Confirmed: separate section before references | Section included before references in both manuscript variants. |
| LaTeX source flattening | Confirmed: Editorial Manager cannot process LaTeX subfolders | Flat source package prepared. |
| Artwork formats | Confirmed acceptable formats include PDF | Separate figure PDFs prepared; TikZ schematic exported as PDF. |
| Graphical abstract dimensions | Confirmed generally if graphical abstract is used | No graphical abstract prepared; requirement level unresolved. |
| Acknowledgments location | Confirmed generally before references | Acknowledgments/funding/declarations placed before references. |

## Unresolved Journal-Specific Items

| Item | Reason unresolved | Prepared fallback |
| --- | --- | --- |
| Performance Evaluation exact review model | ScienceDirect guide not accessible here | Anonymous and title-page variants both compiled. |
| Performance Evaluation abstract hard limit | Not accessible from PE-specific guide | Abstract kept concise and self-contained. |
| Performance Evaluation exact keyword count | Not accessible from PE-specific guide | Five keywords, within general Elsevier maximum of six. |
| Highlights requirement level | Elsevier says required for some journals, optional for others | Highlights prepared. |
| Graphical abstract requirement level | PE-specific guide not accessible | No graphical abstract; protocol schematic can serve as artwork, not graphical abstract. |
| PE-specific bibliography style | Not accessible from PE-specific guide | `elsarticle-num` retained; source includes alternate Elsevier styles. |
| PE-specific manuscript-length guidance | Not accessible from PE-specific guide | Manuscript reduced from 36 to 34 pages in preprint format. |
| PE-specific declarations order | Not accessible from PE-specific guide | General Elsevier order followed before references. |
| Supplementary-material naming | Not accessible from PE-specific guide | Package named for Performance Evaluation and inventoried. |

## Citation Validation

- Citation groups were reduced or kept at four citations or fewer.
- Citation contexts were checked against the local bibliography titles and primary-source identity.
- Primary sources are used for datasets, methods, consensus/self-consistency, routers, and performance-measurement references.
- No bibliography metadata was altered during Pass 6.
- Remaining BibTeX warnings are empty-page-field warnings for existing entries, not undefined citations.

## Declaration Fields

Still requiring author confirmation:

- Legal author names and order.
- Affiliations and corresponding author email.
- ORCID/phone/address fields if the submission system requests them.
- Funding statement or explicit no-specific-funding statement.
- Competing-interest statement.
- Data/code availability URL or DOI.
- Exact acknowledgment wording for emotional support, academic/advisory help, software support, and API credits.
- Exact names of AI tools/services if the submission form requires tool-level identification.

