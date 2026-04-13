# Documentation index

Use this page to navigate research notes without hunting filenames.

## Paper-facing anchors (stable-ish)

| Document | Role |
|----------|------|
| [`problem_statement.md`](problem_statement.md) | Problem formulation |
| [`related_work.md`](related_work.md) | Related work sketch |
| [`research_plan.md`](research_plan.md) | Research plan |
| [`main_baselines.md`](main_baselines.md) | Baseline set + link to `external/` |
| [`main_datasets.md`](main_datasets.md) | Dataset priorities |
| [`datasets_access.md`](datasets_access.md) | HF access and verification workflow |
| [`cross_controller_frontier.md`](cross_controller_frontier.md) | Frontier allocation / heterogeneous controllers track |

## Direction and manuscript support

| Document | Role |
|----------|------|
| [`PAPER_DIRECTION_NOTES.md`](PAPER_DIRECTION_NOTES.md) | High-level paper direction |
| [`NEXT_PAPER_SUMMARY_AND_GOALS.md`](NEXT_PAPER_SUMMARY_AND_GOALS.md) | Summary and goals |

## Working notes (dated 2026-04)

These are time-stamped memos (audits, source checks, status). Prefer the anchors above for external readers; use these for provenance and iteration history.

| File | Topic |
|------|--------|
| [`repository_audit_2026-04-13.md`](repository_audit_2026-04-13.md) | Repo audit snapshot |
| [`research_status_2026-04-13.md`](research_status_2026-04-13.md) | Research status |
| [`current_experimental_status_2026-04-13.md`](current_experimental_status_2026-04-13.md) | Experiments status |
| [`project_direction_neurips_2026-04-13.md`](project_direction_neurips_2026-04-13.md) | Venue/direction |
| [`next_research_step_2026-04-13.md`](next_research_step_2026-04-13.md) | Next step |
| [`next_experiment_pass_multi_action_2026-04-13.md`](next_experiment_pass_multi_action_2026-04-13.md) | Experiment pass |
| [`real_api_pilot_notes_2026-04-13.md`](real_api_pilot_notes_2026-04-13.md) | Real API pilot |
| [`hf_status_2026-04-13.md`](hf_status_2026-04-13.md) | HF access status |
| [`conversation_summary_2026-04-12.md`](conversation_summary_2026-04-12.md) | Conversation summary |
| [`theorem_program_2026-04-13.md`](theorem_program_2026-04-13.md) | Theorem program |
| [`theory_backbones_2026-04-13.md`](theory_backbones_2026-04-13.md) | Theory backbones |
| [`manuscript_support_index_2026-04-13.md`](manuscript_support_index_2026-04-13.md) | Index of support notes |
| [`safe_claims_2026-04-13.md`](safe_claims_2026-04-13.md) | Safe claims |
| [`safe_manuscript_claims_2026-04-13.md`](safe_manuscript_claims_2026-04-13.md) | Manuscript-safe claims |
| [`learned_scorer_lessons_2026-04-13.md`](learned_scorer_lessons_2026-04-13.md) | Learned scorer |
| [`metareasoning_voc_foundations_2026-04-13.md`](metareasoning_voc_foundations_2026-04-13.md) | Metareasoning / VoC |
| [`metareasoning_source_verification_2026-04-13.md`](metareasoning_source_verification_2026-04-13.md) | Metareasoning sources |
| [`bai_source_verification_2026-04-13.md`](bai_source_verification_2026-04-13.md) | BAI sources |
| [`adaptive_submodularity_source_verification_2026-04-13.md`](adaptive_submodularity_source_verification_2026-04-13.md) | Submodularity sources |
| [`knapsack_source_verification_2026-04-13.md`](knapsack_source_verification_2026-04-13.md) | Knapsack sources |
| [`branch_scoring_references_2026-04-13.bib`](branch_scoring_references_2026-04-13.bib) | BibTeX snippet |

## Generated and local-only

- Experiment artifacts: `outputs/` (see root `.gitignore`).
- Integration reports: run `python scripts/generate_dataset_integration_report.py` and `python scripts/generate_external_baseline_integration_report.py` to refresh JSON/Markdown under `outputs/`.
