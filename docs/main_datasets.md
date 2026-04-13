# Main datasets

Dataset selection is central to adaptive test-time compute research because conclusions depend on both task difficulty and reasoning structure. For multi-step LLM reasoning, we need a mix of arithmetic, formal math, science reasoning, and planning-style tasks to evaluate where extra inference budget is most useful. The working set below is intentionally conservative and documents access uncertainty explicitly.

## Core dataset set

### Core set rationale

We treat **six datasets as core** to match the current project scope and to cover complementary reasoning regimes: standard multi-step math (GSM8K), hard math (MATH, AIME, OlympiadBench), hard science reasoning (GPQA Diamond), and planning-style reasoning (NaturalPlan). A seventh candidate (LiveCodeBench) is tracked as extended coverage to avoid over-expanding the initial core benchmark matrix.

| Dataset | Canonical name | What it measures | Why it is relevant | Official link | Access link | Public / gated status | Practical notes |
|---|---|---|---|---|---|---|---|
| GSM8K | GSM8K | Grade-school math word problems with multi-step arithmetic reasoning. | Core benchmark for multi-step reasoning, tree search, process verifiers, and adaptive compute budgeting. | https://arxiv.org/abs/2110.14168 | https://huggingface.co/datasets/openai/gsm8k | Public | Loadable via Hugging Face `datasets`; suitable for exact-match metrics and token-budget experiments. |
| MATH | MATH | Competition math with step-by-step solutions and harder compositional reasoning. | Strong benchmark for deep multi-step reasoning and proof-like reasoning trees. | https://arxiv.org/abs/2103.03874 | https://huggingface.co/datasets/hendrycks/math | Public | Hugging Face access is straightforward; useful for verifier-guided and budget-aware reasoning studies. |
| GPQA Diamond | GPQA Diamond | Expert-level, graduate-style science multiple-choice reasoning. | Hard-reasoning benchmark for test-time scaling, verifier quality, and budget-aware evaluation. | https://arxiv.org/abs/2311.12022 | https://huggingface.co/datasets/Idavidrein/gpqa | Gated / terms may be required | Likely requires Hugging Face login and acceptance of terms; often used in lm-eval-style evaluation flows. |
| AIME | AIME (2024/2025 subsets as appropriate) | Olympiad-level math with integer final answers. | Very hard benchmark for high-depth reasoning and test-time compute scaling. | https://artificialanalysis.ai/evaluations/aime-2025 | https://evalscope.readthedocs.io/en/latest/get_started/supported_dataset/llm.html | Public (source path may vary) | Benchmark sourcing can vary by release year and host pipeline. **TODO:** verify preferred canonical access path/versioning protocol for this repo. |
| OlympiadBench | OlympiadBench | Olympiad-style math/physics reasoning with structured, step-aware characteristics. | Useful for long-horizon reasoning, decomposition-heavy search, and verifier-guided experiments. | https://arxiv.org/abs/2406.15513 | https://huggingface.co/datasets/THUDM/OlympiadBench | Public | Accessible via Hugging Face; appropriate for difficult structured reasoning experiments. |
| NaturalPlan | NaturalPlan | Natural-language planning tasks with realistic constraints. | Broadens evaluation beyond pure math into planning-style reasoning under budget constraints. | https://arxiv.org/abs/2406.04520 | https://github.com/google-deepmind/natural-plan | Public | Repository-hosted task/data assets; useful for anytime reasoning and planning-style allocation analysis. |

## Extended or optional dataset coverage

| Dataset | Canonical name | What it measures | Why it is relevant | Official link | Access link | Public / gated status | Practical notes |
|---|---|---|---|---|---|---|---|
| LiveCodeBench | LiveCodeBench | Contamination-conscious coding benchmark with execution-based evaluation. | Extends reasoning-tree evaluation into coding and algorithmic reasoning settings. | https://livecodebench.github.io | https://github.com/LiveCodeBench/LiveCodeBench | Public | Good optional extension after core runs stabilize; requires code-execution-aware evaluation setup. |

We keep LiveCodeBench in extended coverage (rather than core) to preserve the requested six-dataset core set and to avoid mixing code-execution infrastructure into the first wave of math/science/planning experiments.

## Recommended first experimental subset

A practical first subset is **GSM8K + MATH + GPQA Diamond**. This trio provides a strong progression from standard multi-step arithmetic to harder formal math and expert science reasoning, while keeping the initial implementation and evaluation loop manageable. It also gives early signal on whether adaptive budget allocation generalizes across difficulty tiers and answer formats (free-form math vs. multiple-choice science). **TODO:** once access is confirmed, lock exact splits/versions and evaluation scripts before large-scale runs.
