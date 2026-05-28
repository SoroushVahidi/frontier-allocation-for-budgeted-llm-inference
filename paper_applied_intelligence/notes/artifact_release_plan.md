# Artifact Release Plan

## Release policy

- The full development repository remains private during review.
- A cleaned public artifact release will be published upon acceptance.
- A persistent identifier is preferred (Zenodo DOI target).
- Reviewer-access package can be provided on request before public release.

## Planned contents of cleaned release

- evaluation scripts needed to reproduce reported tables and figures
- processed CSV artifacts used for final claims
- bootstrap CI summary outputs
- win/loss/tie summaries
- figure source CSVs and plotting scripts
- manuscript-facing table-generation scripts where applicable

## Explicit exclusions

- API keys, credentials, `.env` files, or private tokens
- private/internal notes not intended for release
- raw restricted provider outputs (if license or policy restricted)
- caches, temporary files, and local build artifacts
- unrelated `outputs/` runs not part of the curated release
