# Component Ablation Strict-F3 Paper Surface (20260422T180445Z)

This package is a non-duplicative consolidation of an existing strict_f3 manuscript-surface ablation run.

## Provenance
- Source outputs: `outputs/manuscript_surface_component_ablation_20260422T172218Z`
- Source reports: `docs/MANUSCRIPT_SURFACE_COMPONENT_ABLATION_REPORT_2026_04_22.md`, `docs/MANUSCRIPT_SURFACE_COMPONENT_ABLATION_20260422T172218Z.md`
- Evaluation rerun: `False`

## Surface
- Canonical source: `outputs/canonical_full_method_ranking_20260421T212948Z`
- Method lock: `strict_f3`
- Datasets: openai/gsm8k, HuggingFaceH4/MATH-500, HuggingFaceH4/aime_2024
- Seeds: 11, 23
- Budgets: 4, 6, 8

## Key findings carried forward
- Largest accuracy drop from full strict_f3: `no_repeat_expansion_control`
- Largest absent_from_tree worsening: `no_repeat_expansion_control`
- Output repair appears secondary on this bounded manuscript surface.
- Narrative support status: partial (component behavior is variant-dependent).
