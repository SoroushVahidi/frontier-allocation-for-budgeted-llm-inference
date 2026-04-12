# Dataset access guide

This guide describes a conservative, reproducible access workflow for the current dataset plan. It is documentation-only: **do not commit raw dataset dumps to this repository** and do not assume access terms are uniform across datasets.

## Hugging Face datasets

Primary Hugging Face datasets in scope:
- GSM8K: https://huggingface.co/datasets/openai/gsm8k
- MATH: https://huggingface.co/datasets/hendrycks/math
- GPQA Diamond: https://huggingface.co/datasets/Idavidrein/gpqa (likely gated)
- OlympiadBench: https://huggingface.co/datasets/THUDM/OlympiadBench

### Practical setup notes

1. Install and authenticate as needed:
   - `pip install datasets huggingface_hub`
   - `huggingface-cli login` (required for gated datasets and recommended for stable access)
2. Pin tooling versions in your experiment environment for reproducibility.
3. Record dataset revision/version metadata when first pulled.

### Lightweight loading examples

```python
from datasets import load_dataset

# Public examples
gsm8k = load_dataset("openai/gsm8k", "main")
math_ds = load_dataset("hendrycks/math")
olympiad = load_dataset("THUDM/OlympiadBench")

# GPQA Diamond (access may require login + accepted terms)
# gpqa = load_dataset("Idavidrein/gpqa")
```

## GitHub-hosted datasets / benchmark repos

GitHub-hosted resources in current scope:
- NaturalPlan: https://github.com/google-deepmind/natural-plan
- LiveCodeBench (extended/optional): https://github.com/LiveCodeBench/LiveCodeBench

Practical notes:
- Prefer pinning a commit hash/tag when setting up experiments.
- Keep a manifest of the exact benchmark revision used in each run.
- For execution-based benchmarks (e.g., LiveCodeBench), isolate execution and track runtime environment details.

## Gated datasets and access considerations

- **GPQA Diamond** is currently treated as gated/terms-controlled in this plan.
- Access may require Hugging Face authentication and explicit acceptance of dataset terms.
- Do not mirror gated data into this repo.
- **TODO:** before first GPQA experiment, log the exact approved access path and any usage restrictions in project-internal run notes.

## Reproducibility notes

- Distinguish evaluation modes clearly:
  - **Exact-match style** (common for GSM8K/MATH/AIME-like setups)
  - **Execution-based** (relevant for coding benchmarks like LiveCodeBench)
- Track benchmark freshness and contamination risk, especially for coding or continuously updated benchmarks.
- For AIME, canonical sourcing can vary by year and pipeline.
  - **TODO:** standardize the canonical AIME source/version policy for this repository before reporting headline numbers.
- Store only small metadata/manifests in-repo; keep raw data external.

## TODO checklist before first experiments

- [ ] Confirm final core-vs-extended dataset split in the experiment plan.
- [ ] Verify GPQA Diamond access approval and any term constraints.
- [ ] Freeze exact dataset revisions/snapshots (HF revisions, Git commit hashes, or release IDs).
- [ ] Finalize AIME canonical source and year-subset policy (2024 vs 2025 vs combined).
- [ ] Define metric mapping per dataset (exact match, multiple-choice accuracy, execution-based, etc.).
- [ ] Add reproducible data-fetch scripts that reference only official sources.
