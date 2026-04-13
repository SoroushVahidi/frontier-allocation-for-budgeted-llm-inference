# Dataset access guide

This guide describes a conservative, reproducible access workflow for the current dataset plan. It is documentation-only: **do not commit raw dataset dumps to this repository** and do not assume access terms are uniform across datasets.

## Hugging Face datasets

Primary Hugging Face datasets in scope (wired in code):
- `openai/gsm8k`
- `EleutherAI/hendrycks_math`
- `Idavidrein/gpqa` (gated)
- `Hothan/OlympiadBench`
- `livecodebench/code_generation_lite` (optional / secondary)

### Practical setup notes

1. Install and authenticate as needed:
   - `pip install datasets huggingface_hub`
   - use `HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN` from environment, or run `huggingface-cli login` (required for gated datasets)
2. Pin tooling versions in your experiment environment for reproducibility.
3. Record dataset revision/version metadata when first pulled.

### Lightweight loading examples

```bash
# Verify access (writes JSON/CSV/MD summary only)
python scripts/verify_hf_dataset_access.py --output-dir outputs/hf_dataset_access

# Pilot loader config can choose HF source directly
python scripts/run_pilot_gsm8k.py --config configs/pilot_gsm8k.yaml
```

Verification output now includes:
- presence/absence of `HF_TOKEN` and `HUGGINGFACE_HUB_TOKEN` (never token values),
- GPQA datasets-loader status,
- GPQA pandas `hf://` fallback status (`pd.read_csv("hf://datasets/Idavidrein/gpqa/gpqa_extended.csv")`),
- final GPQA accessibility verdict.

### Verified status snapshot (2026-04-13, fresh-session check)

From `python scripts/verify_hf_dataset_access.py --output-dir outputs/hf_dataset_access_fresh_session`:
- ✅ `openai/gsm8k`: datasets loader works (`config=main`, `split=test`)
- ✅ `EleutherAI/hendrycks_math`: datasets loader works (`config=algebra`, `split=test`)
- ✅ `Idavidrein/gpqa`: datasets loader works (`config=gpqa_diamond`, `split=train`), and pandas `hf://` fallback also works
- ✅ `Hothan/OlympiadBench`: datasets loader works (`config=OE_TO_maths_en_COMP`, `split=train`)
- ⚠️ `livecodebench/code_generation_lite`: fails in this environment due to loader incompatibility (`Dataset scripts are no longer supported`)

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
- Loader/verifier behavior: if GPQA access is denied, emit a clear failure entry while continuing checks for other datasets.
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
- Never commit raw downloaded dataset files into git.

## TODO checklist before first experiments

- [ ] Confirm final core-vs-extended dataset split in the experiment plan.
- [ ] Verify GPQA Diamond access approval and any term constraints.
- [ ] Freeze exact dataset revisions/snapshots (HF revisions, Git commit hashes, or release IDs).
- [ ] Finalize AIME canonical source and year-subset policy (2024 vs 2025 vs combined).
- [ ] Define metric mapping per dataset (exact match, multiple-choice accuracy, execution-based, etc.).
- [ ] Add reproducible data-fetch scripts that reference only official sources.
