# Public Repository Checklist

Date: 2026-08-01

## Release Scope

- [x] Historical repository and GitHub PR/issue history audited before publication.
- [x] Historical repository made private after public-history blockers were found.
- [x] Clean public release tree prepared without old branches or tags.
- [x] Historical private review packages excluded.
- [x] Old venue-specific workflow files excluded.
- [x] Local generated workspaces and caches excluded.
- [x] Credentials and environment files excluded; `.env.example` retained.

## Confidentiality

- [x] Full reachable historical Git history inspected.
- [x] Tracked files inspected.
- [x] Ignored files inspected.
- [x] Release artifacts and ZIP contents inspected.
- [x] Documentation, scripts, tests, notebooks, examples, and actions inspected.
- [x] Commit messages inspected.
- [x] No confirmed API keys, passwords, OAuth tokens, SSH keys, private certificates, provider
  account IDs, billing identifiers, confidential emails, or private reviewer material included in
  the clean release.
- [x] No absolute local paths remain in the clean public release.

## Public Documentation

- [x] README complete for external readers.
- [x] Installation instructions present.
- [x] Offline reproducibility commands present and tested.
- [x] Repository layout documented.
- [x] Dataset availability documented.
- [x] LICENSE present.
- [x] CITATION.cff present and uses the public repository URL.
- [x] No old venue/private-workflow references remain in clean-release scan.

## Manuscript And Supplement

- [x] Data availability states that GSM8K, MATH-500, GPQA-Diamond, and StrategyQA are publicly
  available datasets.
- [x] Code availability includes
  `https://github.com/SoroushVahidi/frontier-allocation-for-budgeted-llm-inference`.
- [x] Anonymous manuscript compiled.
- [x] Title-page manuscript compiled.
- [x] Submission source ZIP rebuilt and extraction-tested.
- [x] Supplementary ZIP rebuilt and extraction-tested.
- [x] Supplementary checksums validated.
- [x] Scientific values were not changed.

## Tests

- [x] `python3 scripts/check_repo_health.py`
- [x] `python3 -m pytest -q tests/test_frontier_router.py tests/test_support_aware_selector.py tests/test_check_repo_health_paths.py`
- [x] `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`
- [x] `latexmk -pdf -interaction=nonstopmode -halt-on-error main_with_titlepage.tex`

## Remaining Author Confirmation

- [ ] Final affiliation and corresponding author email.
- [ ] ORCID/phone/address fields if required by the submission system.
- [ ] Funding statement or explicit no-specific-funding statement.
- [ ] Competing-interest statement.
- [ ] Acknowledgments wording and names.
- [ ] Repository DOI if a DOI is minted.

## Publication

- [x] Historical repository archived privately.
- [x] Fresh public repository created at target URL.
- [x] Public release committed on `main`.
- [x] Public release pushed to GitHub.
- [x] GitHub visibility verified public.
