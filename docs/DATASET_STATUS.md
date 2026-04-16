# Dataset status (evaluation vs supervision vs readiness)

This note clarifies dataset roles for the repository. For the latest full code-vs-doc/readiness audit, see `docs/CURRENT_DATASET_AUDIT_STATUS.md` (2026-04-16).

## A) Main evaluation datasets (current benchmark-facing set)

These are the primary datasets used for evaluating controller/frontier behavior:
- GSM8K
- MATH (canonical + mirror wiring)
- MATH-500 (canonical HF id wiring)
- GPQA Diamond
- AIME 2024 slice
- OlympiadBench mirror
- AMO-Bench
- NaturalPlan (git-clone-based integration path)
- LiveCodeBench (optional/extended)

References: `docs/main_datasets.md`, `docs/datasets_access.md`, `experiments/hf_datasets.py`.

## B) External reasoning-supervision datasets (new-paper prep layer)

These are integrated mainly for branch/process supervision experiments and warm-start:
- PRM800K
- Math-Shepherd
- UltraInteract (pair + sft)
- DeepStep-Math-5K
- WebInstruct-verified
- JudgeLM datasets
- MT-Bench human judgments
- Prometheus collections
- math_verify release
- ARCTraj
- APPS (verifier-backed coding dataset; partially integrated)

Status: **integration/preparation sources**; not equivalent to final-method evidence.

## C) Readiness-ranked integrated sources

Use `docs/new_paper_dataset_readiness_2026-04-14.md` for tiered “use now / backup / low-priority” recommendations.

## D) Not integrated / currently low priority

Current examples noted in repository docs:
- PairS (no canonical standalone dataset artifact confirmed)
- AgentPRM / InversePRM (gated or no stable public artifact)

## E) Practical interpretation rule

- Evaluation claims should be tied to section (A).
- Supervision/pretraining/warm-start claims should be tied to section (B).
- Do not present section (B) integration status alone as proof of controller-level gains.
