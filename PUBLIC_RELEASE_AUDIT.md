# Public Release Audit

Date: 2026-08-01

Target public URL:
`https://github.com/SoroushVahidi/frontier-allocation-for-budgeted-llm-inference`

## Decision

The historical GitHub repository at the target URL was not suitable for direct public release.
It had already been public when this audit began, so it was immediately made private. The public
release is therefore prepared as a fresh, single-history release repository at the same target URL,
after preserving the historical repository as a private archive.

## Blocking Issues Found In Historical Repository

- Reachable Git history contained old venue-specific and review-workflow material, including
  manuscript migration records and private review-package traces.
- GitHub pull-request history contained extensive internal working history. Because pull requests
  remain visible when a repository is public, a force-pushed clean branch would not be sufficient.
- Tracked files included a private review PDF and old manuscript/workflow directories unrelated to
  the Performance Evaluation public artifact.
- Working-tree scans found local paths, old venue labels, reviewer-era terminology, and generated
  artifacts that were inappropriate for a permanent public repository.
- Ignored local files included virtual environments, large local output workspaces, caches, and
  credentials-adjacent files that were not included in the public release.

## Resolution

- Historical repository visibility was changed to private before publication proceeded.
- A new clean release tree was built from the current source and manuscript artifacts.
- Historical review packages, old venue directories, migration notes, local caches, generated
  experiment workspaces, and unneeded internal scripts/tests were excluded.
- The public release retains the manuscript, submission package, supplementary material, core
  implementation modules, a compact canonical output audit, prompt templates, public documentation,
  and a small offline CI-safe test suite.
- The Performance Evaluation manuscript data/code availability statement now identifies the public
  GitHub repository and states that GSM8K, MATH-500, GPQA-Diamond, and StrategyQA are publicly
  available datasets.

## Secret And Confidentiality Audit

Historical-repository scan:

- Full reachable Git history, tracked files, ignored files, release artifacts, scripts,
  supplementary material, generated outputs, documentation, notebooks, examples, actions, and
  commit messages were inspected.
- No high-confidence private key, GitHub token, OpenAI key, Google key, Hugging Face token, AWS key,
  OAuth token, private certificate, password, or credential file was confirmed.
- Generic secret-assignment matches were reviewed as placeholders, dummy examples, variable names,
  or configuration-key names. Raw candidate strings are intentionally not reproduced in this audit.

Clean-release scan:

- No high-confidence secret patterns were found in the clean public release tree or ZIP contents.
- No `.env`, private key, certificate, credential file, editor backup, temporary file, Python
  bytecode cache, or local absolute path remains in the release tree.
- No old venue/private-workflow references remain in the clean release scan.

## Large Files And Redistributable Content

- Clean public release size before Git publication: approximately 7.4 MB.
- No file larger than 5 MB remains in the clean public release tree.
- The release includes generated figure PDFs, manuscript PDFs, and submission ZIPs needed for
  publication inspection.
- No copyrighted third-party article PDF, private review PDF, or non-redistributable dataset dump is
  included.

## Documentation Audit

- `README.md` gives the public artifact scope, installation, offline checks, manuscript compile
  commands, reproducibility boundary, dataset list, license, and citation pointer.
- `docs/REPRODUCIBILITY.md`, `docs/REPOSITORY_LAYOUT.md`, `docs/DATASETS.md`,
  `docs/ARTIFACT_MAP.md`, and `docs/PUBLICATION_PACKAGE.md` document the release surface for
  external readers.
- `LICENSE` is MIT for released code.
- `CITATION.cff` points to the public repository URL and manuscript title.
- GitHub Actions run only offline health and regression checks.

## Manuscript And Package Audit

- `paper_performance_evaluation/main.tex` and `main_with_titlepage.tex` include the public
  repository URL in Data availability.
- Both manuscript PDFs compile to 34 pages.
- Source and supplementary ZIPs were rebuilt and extraction-tested.
- Supplementary checksums validate successfully.
- The title-page manuscript uses the public author name; affiliation, corresponding email, ORCID,
  funding, competing-interest wording, acknowledgments, and optional DOI remain author-confirmation
  fields.

## Validation Commands

- `python3 scripts/check_repo_health.py`: passed.
- `python3 -m pytest -q tests/test_frontier_router.py tests/test_support_aware_selector.py tests/test_check_repo_health_paths.py`: 84 passed.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`: passed.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error main_with_titlepage.tex`: passed.
- `unzip -t performance_evaluation_submission_source.zip`: passed.
- `unzip -t performance_evaluation_supplementary_material.zip`: passed.
- `sha256sum -c CHECKSUMS_SHA256.txt`: passed.

## Publication Result

- Historical repository archived privately as
  `SoroushVahidi/frontier-allocation-for-budgeted-llm-inference-private-archive-20260801`.
- Fresh public repository created at
  `https://github.com/SoroushVahidi/frontier-allocation-for-budgeted-llm-inference`.
- Public release commit and push are recorded in the final response.
