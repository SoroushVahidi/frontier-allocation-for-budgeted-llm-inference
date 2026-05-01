# Dataset integration report

- Generated (UTC): `2026-04-13T21:30:10.709972+00:00`

## Summary

| Dataset | Priority | Status | Public / gated | Paper-ready now |
|---|---:|---|---|---|
| MATH (Hendrycks et al.) | A | YES | public | True |
| GPQA Diamond | A | YES | gated_terms_likely | True |
| AIME | B | PARTIAL | public | True |
| OlympiadBench | B | PARTIAL | public | True |
| NaturalPlan | C | NO | public_repo | False |

## Probe results (this environment)

These are non-secret connectivity checks only; they do not prove global availability.

- `hendrycks/competition_math`: ok=False (FileNotFoundError: Couldn't find any data file at /mmfs1/home/sv96/adaptive-reasoning-budget-allocation/hendrycks/competition_math. Couldn't find 'hendrycks/competition_math' on the Hugging Face Hub e)
- `EleutherAI/hendrycks_math`: ok=True 
- `Idavidrein/gpqa`: ok=True 
- `HuggingFaceH4/aime_2024`: ok=True 
- `Hothan/OlympiadBench`: ok=True 

## Per-dataset detail

### MATH (Hendrycks et al.) (A)
- **Could add**: YES
- **Official**: https://arxiv.org/abs/2103.03874
- **Access**: https://huggingface.co/datasets/hendrycks/competition_math
- **What was added**: HFDatasetSpec for hendrycks/competition_math; aliases to paper URL hendrycks/math; EleutherAI mirror retained.
- **Still missing**: Hub id `hendrycks/math` does not resolve; use hendrycks/competition_math or mirror. Network-dependent load in some environments.
- **Manual steps**: None for public mirror; pin HF revision for paper runs.
- **Schema/version notes**: Subject configs (algebra, geometry, ...) and test split; document chosen config in each run manifest.

### GPQA Diamond (A)
- **Could add**: YES
- **Official**: https://arxiv.org/abs/2311.12022
- **Access**: https://huggingface.co/datasets/Idavidrein/gpqa
- **What was added**: Existing spec reinforced; aliases; optional choices field in sample_hf_examples; normalization MCQ hook.
- **Still missing**: User must accept HF terms; token required when gated.
- **Manual steps**: huggingface-cli login or HF_TOKEN; accept dataset terms on the Hub.
- **Schema/version notes**: Default split train for diamond config per prior repo behavior; confirm against dataset card when reporting.

### AIME (B)
- **Could add**: PARTIAL
- **Official**: https://artificialanalysis.ai/evaluations/aime-2025
- **Access**: https://huggingface.co/datasets/HuggingFaceH4/aime_2024
- **What was added**: HFDatasetSpec for 2024-only HuggingFaceH4 card (30 problems); wired in registry and verification list.
- **Still missing**: Not a full multi-year AIME union; for broader coverage consider AI-MO/aimo-validation-aime (not wired; cite separately).
- **Manual steps**: None typically.
- **Schema/version notes**: Single-card snapshot; year field exists in rows—lock revision for paper tables.

### OlympiadBench (B)
- **Could add**: PARTIAL
- **Official**: https://arxiv.org/abs/2406.15513
- **Access**: https://huggingface.co/datasets/Hothan/OlympiadBench
- **What was added**: Canonical HF path documented as Hothan/OlympiadBench mirror; same spec as before with provenance_note.
- **Still missing**: THUDM/OlympiadBench repo id returns 404 via Hub API; treat Hothan as mirror unless upstream republishes.
- **Manual steps**: None for public load; pick config (default OE_TO_maths_en_COMP) explicitly in papers.
- **Schema/version notes**: Many configs; default single English math competition subset.

### NaturalPlan (C)
- **Could add**: NO
- **Official**: https://arxiv.org/abs/2406.04520
- **Access**: https://github.com/google-deepmind/natural-plan
- **What was added**: Documentation-only status; no raw data or loader committed.
- **Still missing**: Optional future: thin loader after license review and pinned commit policy.
- **Manual steps**: Clone upstream repo per license; pin commit; do not vendor raw data into this repo.
- **Schema/version notes**: N/A until a pinned snapshot is adopted.
