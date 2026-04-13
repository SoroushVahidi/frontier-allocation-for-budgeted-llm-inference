# Main datasets

Dataset selection is central to adaptive test-time compute research because conclusions depend on both task difficulty and reasoning structure. For multi-step LLM reasoning, we need a mix of arithmetic, formal math, science reasoning, and planning-style tasks to evaluate where extra inference budget is most useful. The working set below is intentionally conservative and documents access uncertainty explicitly.

## Core dataset set

### Core set rationale

We treat **six datasets as core** to match the current project scope and to cover complementary reasoning regimes: standard multi-step math (GSM8K), hard math (MATH, AIME, OlympiadBench), hard science reasoning (GPQA Diamond), and planning-style reasoning (NaturalPlan). A seventh candidate (LiveCodeBench) is tracked as extended coverage to avoid over-expanding the initial core benchmark matrix.

| Dataset | Canonical name | What it measures | Why it is relevant | Official link | Access link | Public / gated status | Practical notes |
|---|---|---|---|---|---|---|---|
| GSM8K | GSM8K | Grade-school math word problems with multi-step arithmetic reasoning. | Core benchmark for multi-step reasoning, tree search, process verifiers, and adaptive compute budgeting. | https://arxiv.org/abs/2110.14168 | https://huggingface.co/datasets/openai/gsm8k | Public | Wired as `openai/gsm8k` in `experiments/hf_datasets.py`. |
| MATH | MATH | Competition math with step-by-step solutions and harder compositional reasoning. | Strong benchmark for deep multi-step reasoning and proof-like reasoning trees. | https://arxiv.org/abs/2103.03874 | https://huggingface.co/datasets/hendrycks/competition_math | Public | **Registry:** `hendrycks/competition_math` (canonical Hendrycks org id). The Hub path `hendrycks/math` does not resolve as a dataset id; use alias `math` / `MATH` → `hendrycks/competition_math`. Mirror: `EleutherAI/hendrycks_math`. |
| GPQA Diamond | GPQA Diamond | Expert-level, graduate-style science multiple-choice reasoning. | Hard-reasoning benchmark for test-time scaling, verifier quality, and budget-aware evaluation. | https://arxiv.org/abs/2311.12022 | https://huggingface.co/datasets/Idavidrein/gpqa | Gated / terms may be required | Wired as `Idavidrein/gpqa` with config `gpqa_diamond`; aliases `gpqa`, `gpqa_diamond`. Requires HF auth/terms when gated. |
| AIME | AIME (subset) | Olympiad-level math with integer final answers. | Very hard benchmark for high-depth reasoning and test-time compute scaling. | https://artificialanalysis.ai/evaluations/aime-2025 | https://huggingface.co/datasets/HuggingFaceH4/aime_2024 | Public (card-specific) | **Registry:** `HuggingFaceH4/aime_2024` (30 problems, 2024). Broader multi-year coverage (e.g. AI-MO/aimo-validation-aime) is not wired here—cite separately if used. |
| OlympiadBench | OlympiadBench | Olympiad-style math/physics reasoning with structured, step-aware characteristics. | Useful for long-horizon reasoning, decomposition-heavy search, and verifier-guided experiments. | https://arxiv.org/abs/2406.15513 | https://huggingface.co/datasets/Hothan/OlympiadBench | Public | **Registry:** `Hothan/OlympiadBench` (English math competition subset default). The Hub id `THUDM/OlympiadBench` is not reliably available (404 in API checks); treat Hothan as the supported HF mirror and cite the THUDM/OpenBMB paper for benchmark definition. |
| NaturalPlan | NaturalPlan | Natural-language planning tasks with realistic constraints. | Broadens evaluation beyond pure math into planning-style reasoning under budget constraints. | https://arxiv.org/abs/2406.04520 | https://github.com/google-deepmind/natural-plan | Public (repo) | **Not** in `HF_DATASET_SPECS`; clone upstream per license and pin commit—do not vendor raw data into this repo. |

## Extended or optional dataset coverage

| Dataset | Canonical name | What it measures | Why it is relevant | Official link | Access link | Public / gated status | Practical notes |
|---|---|---|---|---|---|---|---|
| LiveCodeBench | LiveCodeBench | Contamination-conscious coding benchmark with execution-based evaluation. | Extends reasoning-tree evaluation into coding and algorithmic reasoning settings. | https://livecodebench.github.io | https://github.com/LiveCodeBench/LiveCodeBench | Public | Good optional extension after core runs stabilize; requires code-execution-aware evaluation setup. |

We keep LiveCodeBench in extended coverage (rather than core) to preserve the requested six-dataset core set and to avoid mixing code-execution infrastructure into the first wave of math/science/planning experiments.

## Recommended first experimental subset

A practical first subset is **GSM8K + MATH + GPQA Diamond** (see registry keys above). Lock HF revisions in run manifests before headline numbers. Generate a local status report (not committed by default): `python scripts/generate_dataset_integration_report.py` → `outputs/dataset_integration_report.{json,md}`.
