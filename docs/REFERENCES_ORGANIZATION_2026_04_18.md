# References organization (2026-04-18)

## Purpose

This note explains how to think about the repository’s reference base and where different kinds of references belong.

The repository now contains several kinds of references:
- canonical paper-neighbor references,
- dataset references,
- external baseline references,
- exploratory literature takeaways,
- and historical/provenance references.

This note organizes them so future collaborators know where to look.

## Main reference categories

### 1. Canonical project-shaping references
Use these to understand the current paper story and nearest methodological neighbors:
- `docs/main_baselines.md`
- `docs/cross_controller_frontier.md`
- `docs/CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md`
- `docs/PAPER_POSITIONING_NOTE.md`

These are the best places for references that directly shape how the project should be written and compared.

### 2. Dataset references
Use these for benchmark/task provenance and access:
- `docs/main_datasets.md`
- `docs/datasets_access.md`
- `docs/DATASET_EXPANSION_PRIORITIES_2026_04_17.md`
- `datasets/` materials and dataset integration reports under `outputs/`

### 3. External baseline references and integration status
Use these for method-neighbor baselines and reproducibility status:
- `docs/external_baseline_completeness_report.md`
- `external/README.md`
- `configs/external_baselines_registry.json`
- `outputs/external_baseline_completeness_summary.{json,csv}`

### 4. Target-design / ambiguity / research-takeaway references
Use these for current research directions that inform target design, abstention, value supervision, and selective relabeling:
- `docs/RESEARCH_TAKEAWAYS_ON_TARGET_DESIGN_AND_SELECTIVE_ALLOCATION_2026_04_18.md`
- `docs/RESEARCH_TAKEAWAYS_ON_VALUE_TARGETS_AND_ABSTENTION_2026_04_18.md`
- `outputs/research_takeaways/`

These are useful for method design and future experiments, but should be cited carefully and filtered before manuscript use.

### 5. Historical / provenance references
Use these only to understand how the repository evolved, not as the current canonical interpretation.

See:
- `docs/HISTORICAL_AND_ARCHIVE_POLICY.md`
- `archive/`

## Recommended reference discipline

### Canonical manuscript references should come from
- canonical docs,
- main baseline notes,
- dataset notes,
- and verified external-baseline materials.

### Experimental ideation references may additionally come from
- research-takeaway notes,
- bounded literature syntheses,
- and exploratory method notes.

### Do not treat all references equally
The repository now contains both:
- manuscript-facing references,
- and experiment-design idea references.

They are not the same thing.

## Safe practical rule

When a reference is used in paper writing, first ask:
1. is it a direct methodological neighbor,
2. is it already represented in canonical docs or verified baseline notes,
3. or is it only a design-direction source from research takeaways?

If it is only a design-direction source, it may still be very useful, but it should be filtered more carefully before manuscript citation.

## Recommended next cleanup habit

When new literature or external methods are investigated, record them in one of these places:
- canonical paper-neighbor docs if they are central,
- external-baseline completeness notes if they are comparison baselines,
- research-takeaway notes if they mainly shape future target-design ideas,
- historical/provenance notes only if they are superseded.

## Safe summary

A safe repository-facing summary is:

> The reference base is already rich, but it is now important to distinguish clearly between canonical manuscript-shaping references, experimental design-direction references, and historical/provenance references so that future work stays organized and paper claims stay clean.
