# Dataset access guide

This guide describes a conservative, reproducible access workflow for the current dataset plan. It is documentation-only: **do not commit raw dataset dumps to this repository** and do not assume access terms are uniform across datasets.

## Hugging Face datasets

Primary Hugging Face datasets in scope (wired in `experiments/hf_datasets.py`):
- `openai/gsm8k`
- `hendrycks/competition_math` (canonical MATH; aliases: `math`, `MATH`, `hendrycks/math`)
- `EleutherAI/hendrycks_math` (MATH mirror)
- `Idavidrein/gpqa` (config `gpqa_diamond`; gated; aliases: `gpqa`, `gpqa_diamond`)
- `HuggingFaceH4/aime_2024` (AIME 2024 slice; aliases: `aime`, `aime_2024`)
- `Hothan/OlympiadBench` (OlympiadBench mirror; `THUDM/OlympiadBench` Hub id not verified)
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

# One-example smoke per dataset key (writes JSON summary only; no raw data in git)
python scripts/dataset_smoke_sample.py --output-dir outputs/dataset_smoke

# Paper integration status report (JSON + Markdown under outputs/)
python scripts/generate_dataset_integration_report.py

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

GitHub-hosted resources in current scope (no HF loader in-repo; no raw data committed):
- NaturalPlan: https://github.com/google-deepmind/natural-plan — **documentation-only** in this repo; clone upstream and pin a commit for experiments.
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
- For AIME, this repository wires **`HuggingFaceH4/aime_2024`** as a concrete 2024 slice; broader AIME unions require a separate policy and citation.
- Store only small metadata/manifests in-repo; keep raw data external.
- Never commit raw downloaded dataset files into git.

## TODO checklist before first experiments

- [ ] Confirm final core-vs-extended dataset split in the experiment plan.
- [ ] Verify GPQA Diamond access approval and any term constraints.
- [ ] Freeze exact dataset revisions/snapshots (HF revisions, Git commit hashes, or release IDs).
- [ ] Finalize AIME canonical source and year-subset policy (2024 vs 2025 vs combined).
- [ ] Define metric mapping per dataset (exact match, multiple-choice accuracy, execution-based, etc.).
- [ ] Add reproducible data-fetch scripts that reference only official sources.

## New-paper external reasoning-supervision candidates (integration prep)

The new-paper track now includes lightweight integration (no raw data commits) for these external reasoning-supervision datasets:

- `tasksource/PRM800K` (step-level PRM-style supervision)
- `peiyi9979/Math-Shepherd` (step-level supervision; `trl-lib/math_shepherd` documented as an easy variant swap)
- `openbmb/UltraInteract_pair` (pairwise chosen/rejected interaction supervision)
- `openbmb/UltraInteract_sft` (SFT trajectory supervision)

Use these scripts:

```bash
# Access + schema smoke check
python scripts/verify_external_reasoning_datasets.py \
  --output-dir outputs/external_reasoning_datasets/latest_verify

# Full comparison report (JSON/MD/CSV under run-id folder)
python scripts/generate_external_reasoning_dataset_integration_report.py
```

Artifacts are written under `outputs/external_reasoning_datasets/<run_id>/` and include:
- `dataset_integration_report.json`
- `dataset_integration_report.md`
- `dataset_comparison_summary.csv`

Notes:
- Integration is preparation-only and does **not** imply final-method training usage.
- Licenses and gating flags are pulled from Hugging Face card metadata when available; verify again before release.
- Keep download-on-demand behavior; do not commit raw dataset dumps.

## Remaining-candidate expansion status (2026-04-14)

The integration layer now also attempts the remaining requested candidate family. Integrated and loader-verified in this environment:

- `BlackSnowDot/DeepStep-Math-5K`
- `TIGER-Lab/WebInstruct-verified`
- `BAAI/JudgeLM-data-collection-v1.0`
- `BAAI/JudgeLM-100K`
- `lmsys/mt_bench_human_judgments` (MT-Bench human-judgment source)
- `prometheus-eval/Feedback-Collection`
- `prometheus-eval/Preference-Collection`
- `HuggingFaceH4/s1k_r1_math_verify` (math_verify-style public release)
- `SejinKimm/ARCTraj`

Attempted but not integrated:

- **PairS** (`cambridgeltl/PairS`): GitHub code repository found, but no canonical standalone dataset artifact / stable HF mirror identified.
- **AgentPRM / InversePRM**: `Jolandaaa/agentprm` exists but was gated/inaccessible in this environment; no stable public `inverseprm` dataset artifact found.

Use the full report script for machine-readable integrated/not-integrated audit output:

```bash
python scripts/generate_external_reasoning_dataset_integration_report.py \
  --run-id <run_id>
```

Artifacts include:
- `dataset_integration_report.json`
- `dataset_integration_report.md`
- `dataset_integration_report.csv`
- `dataset_access_status.json`
