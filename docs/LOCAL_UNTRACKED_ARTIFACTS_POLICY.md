# Local Untracked Artifacts Policy

## Outputs Directory
- `outputs/` contains experiment results and generated artifacts
- These should NOT be committed to git
- Large outputs should be archived externally if needed long-term

## Experiment Scripts
- New experiment scripts should be committed after validation
- Keep scripts small and focused
- Document parameters and expected outputs

## Generated Reports
- Summarize findings in `docs/` as markdown
- Don't commit raw generated reports in bulk
- Keep only curated, final versions

## Large Artifacts
- Dataset caches, model weights, etc. should be stored outside git
- Use external storage (S3, institutional storage) for large binaries
- Document locations in `docs/` if needed for reproducibility
