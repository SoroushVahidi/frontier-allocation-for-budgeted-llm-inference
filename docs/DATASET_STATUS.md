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

### Top-priority expansion candidates (2026-04-17 bounded integration pass)

The following high-priority expansion datasets are now tracked in the dataset registry/tooling and have bounded access checks:
- DROP (`allenai/drop` key with current loader path fallback to `ucinlp/drop`)
- MuSR (`TAUR-Lab/MuSR`)
- BIG-Bench Hard (`openeval/BIG-Bench-Hard`)
- AQuA (`deepmind/aqua_rat`, replacing non-canonical shorthand `aqua_rat`)

Readiness report and artifacts:
- `docs/TOP_PRIORITY_DATASET_EXPANSION_READINESS_2026_04_17.md`
- `outputs/dataset_expansion_20260417/`

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
