# Main datasets

> Quick role map: For canonical role/status labels (evaluation vs external supervision vs readiness vs not integrated), see [`DATASET_STATUS.md`](DATASET_STATUS.md). This file remains the detailed dataset reference.

Dataset selection is central to adaptive test-time compute research because conclusions depend on both task difficulty and reasoning structure. For multi-step LLM reasoning, we need a mix of arithmetic, formal math, science reasoning, and planning-style tasks to evaluate where extra inference budget is most useful. The working set below is intentionally conservative and documents access uncertainty explicitly.

## Core dataset set

### Core set rationale

We treat **nine datasets as core** to match the current project scope and to cover complementary reasoning regimes: standard multi-step math (GSM8K), hard math (MATH, MATH-500, AIME, OlympiadBench, AMO-Bench), hard science reasoning (GPQA Diamond), and planning-style reasoning (NaturalPlan). LiveCodeBench remains an extended candidate to avoid over-expanding the initial core benchmark matrix with execution infrastructure.

| Dataset | Canonical name | What it measures | Why it is relevant | Official link | Access link | Public / gated status | Practical notes |
|---|---|---|---|---|---|---|---|
| GSM8K | GSM8K | Grade-school math word problems with multi-step arithmetic reasoning. | Core benchmark for multi-step reasoning, tree search, process verifiers, and adaptive compute budgeting. | https://arxiv.org/abs/2110.14168 | https://huggingface.co/datasets/openai/gsm8k | Public | Wired as `openai/gsm8k` in `experiments/hf_datasets.py`. |
| MATH | MATH | Competition math with step-by-step solutions and harder compositional reasoning. | Strong benchmark for deep multi-step reasoning and proof-like reasoning trees. | https://arxiv.org/abs/2103.03874 | https://huggingface.co/datasets/hendrycks/competition_math | Public | **Registry:** `hendrycks/competition_math` (canonical Hendrycks org id). The Hub path `hendrycks/math` does not resolve as a dataset id; use alias `math` / `MATH` → `hendrycks/competition_math`. Mirror: `EleutherAI/hendrycks_math`. |
| GPQA Diamond | GPQA Diamond | Expert-level, graduate-style science multiple-choice reasoning. | Hard-reasoning benchmark for test-time scaling, verifier quality, and budget-aware evaluation. | https://arxiv.org/abs/2311.12022 | https://huggingface.co/datasets/Idavidrein/gpqa | Gated / terms may be required | Wired as `Idavidrein/gpqa` with config `gpqa_diamond`; aliases `gpqa`, `gpqa_diamond`. Requires HF auth/terms when gated. |
| MATH-500 | MATH-500 | Curated 500-problem hard subset derived from MATH and used in verifier-era scaling analyses. | Strong fixed-size hard-math slice for comparable budgeted evaluations and quicker turnaround than full MATH. | https://github.com/openai/prm800k#math-splits | https://huggingface.co/datasets/HuggingFaceH4/MATH-500 | Public | **Canonical ID in this repo:** `HuggingFaceH4/MATH-500`; aliases `math500`, `math-500`, `MATH-500`. Candidate mirror `math-ai/math500` is tracked but not canonicalized here. |
| AIME | AIME (subset) | Olympiad-level math with integer final answers. | Very hard benchmark for high-depth reasoning and test-time compute scaling. | https://artificialanalysis.ai/evaluations/aime-2025 | https://huggingface.co/datasets/HuggingFaceH4/aime_2024 | Public (card-specific) | **Registry:** `HuggingFaceH4/aime_2024` (30 problems, 2024). Broader multi-year coverage (e.g. AI-MO/aimo-validation-aime) is not wired here—cite separately if used. |
| OlympiadBench | OlympiadBench | Olympiad-style math/physics reasoning with structured, step-aware characteristics. | Useful for long-horizon reasoning, decomposition-heavy search, and verifier-guided experiments. | https://arxiv.org/abs/2406.15513 | https://huggingface.co/datasets/Hothan/OlympiadBench | Public | **Registry:** `Hothan/OlympiadBench` (English math competition subset default). The Hub id `THUDM/OlympiadBench` is not reliably available (404 in API checks); treat Hothan as the supported HF mirror and cite the THUDM/OpenBMB paper for benchmark definition. |
| AMO-Bench | AMO-Bench | Advanced olympiad-style hard-math benchmark with parser/LLM-graded final-answer targets. | High-difficulty modern benchmark where many frontier models remain far from saturation. | https://amo-bench.github.io/ | https://huggingface.co/datasets/meituan-longcat/AMO-Bench | Public | **Registry:** `meituan-longcat/AMO-Bench`; aliases `amo-bench`, `amo_bench`, `AMO-Bench`. HF card declares MIT and test split fields `prompt`, `solution`, `answer`, `answer_type`. |
| NaturalPlan | NaturalPlan | Natural-language planning tasks with realistic constraints. | Broadens evaluation beyond pure math into planning-style reasoning under budget constraints. | https://arxiv.org/abs/2406.04520 | https://github.com/google-deepmind/natural-plan | Public (repo) | Integrated via git-clone spec key `google-deepmind/natural-plan` (alias `naturalplan`). Local clone path is required (`NATURAL_PLAN_DIR` or default `external_datasets/natural-plan`); do not vendor raw data into this repo. |

## Extended or optional dataset coverage

| Dataset | Canonical name | What it measures | Why it is relevant | Official link | Access link | Public / gated status | Practical notes |
|---|---|---|---|---|---|---|---|
| LiveCodeBench | LiveCodeBench | Contamination-conscious coding benchmark with execution-based evaluation. | Extends reasoning-tree evaluation into coding and algorithmic reasoning settings. | https://livecodebench.github.io | https://github.com/LiveCodeBench/LiveCodeBench | Public | Good optional extension after core runs stabilize; requires code-execution-aware evaluation setup. |

We keep LiveCodeBench in extended coverage (rather than core) to avoid mixing code-execution infrastructure into the first wave of math/science/planning experiments.

## Recommended first experimental subset

A practical first subset is **GSM8K + MATH + GPQA Diamond** (see registry keys above). Lock HF revisions in run manifests before headline numbers. Generate a local status report (not committed by default): `python scripts/generate_dataset_integration_report.py` → `outputs/dataset_integration_report.{json,md}`.

## New-paper track: external reasoning-supervision data (preparation layer)

To support upcoming branch-level supervision experiments without prematurely committing to one source, the repository now integrates four external datasets as **candidate supervision sources**:

| Dataset key | HF dataset ID | Supervision type | Planned role in this repo |
|---|---|---|---|
| `prm800k` | `tasksource/PRM800K` | `step_supervision` | PRM-style step-level scoring and branch-quality supervision prototypes |
| `math_shepherd` | `peiyi9979/Math-Shepherd` (swap option: `trl-lib/math_shepherd`) | `step_supervision` | Math-domain step correctness supervision candidates |
| `ultrainteract_pair` | `openbmb/UltraInteract_pair` | `pairwise_preference` | Pairwise ranking signals for branch-comparison methods |
| `ultrainteract_sft` | `openbmb/UltraInteract_sft` | `trajectory_supervision` | SFT trajectory data for future trajectory-aware scoring |

These are integrated in a license-aware, download-on-demand way only (see `experiments/external_reasoning_datasets.py` and `configs/external_reasoning_datasets_registry.json`). They are **not** yet evidence of being used in the final method.

### Expanded external reasoning-supervision set (new-paper prep)

Beyond the initial four integrations, the new-paper prep layer now includes additional public candidates for judge/verifier/process supervision and trajectory data: `DeepStep-Math-5K`, `WebInstruct-verified`, `JudgeLM-data-collection-v1.0`, `JudgeLM-100K`, `lmsys/mt_bench_human_judgments`, `prometheus-eval/Feedback-Collection`, `prometheus-eval/Preference-Collection`, `HuggingFaceH4/s1k_r1_math_verify`, and `SejinKimm/ARCTraj`.

Non-integrated candidates are tracked explicitly in the candidate audit output (currently: PairS dataset artifact unresolved; AgentPRM gated + no clear InversePRM dataset release).
