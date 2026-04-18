# References organization (2026-04-18)

## Purpose

This note explains how to think about the repository’s reference base and where different kinds of references belong.

The repository now contains several kinds of references:
- canonical project-shaping references,
- direct / near-direct empirical baseline references,
- adjacent method-neighbor references,
- ingredient / idea references,
- frontier-track references,
- dataset references,
- and historical / provenance references.

This note organizes them so future collaborators know where to look.

## Current single best reference audit

If you want the shortest current reference-facing answer, start with:

- `docs/REFERENCES_AUDIT_AND_CURATION_2026_04_18.md`

That note explains:
- which references are central now,
- which ones are idea-only,
- which ones are empirical baselines,
- which ones are adjacent but not control-space-equivalent,
- and which ones are currently low-priority or unsafe to foreground.

## Main reference categories

### 1. Canonical project-shaping references
Use these to understand the current paper story and nearest conceptual/methodological neighbors:
- `docs/CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md`
- `docs/PAPER_POSITIONING_NOTE.md`
- `docs/REFERENCES_AUDIT_AND_CURATION_2026_04_18.md`
- `docs/cross_controller_frontier.md`

These are the best places for references that directly shape how the project should be written and compared.

### 2. Direct / near-direct empirical baseline references
Use these for reviewer-facing comparisons and runnability status:
- `docs/main_baselines.md`
- `docs/external_baseline_completeness_report.md`
- `external/README.md`
- `configs/external_baselines_registry.json`

These are the most important places for methods that might appear in tables or comparison bundles.

### 3. Dataset references
Use these for benchmark/task provenance and access:
- `docs/main_datasets.md`
- `docs/datasets_access.md`
- `docs/DATASET_EXPANSION_PRIORITIES_2026_04_17.md`
- `datasets/` materials and dataset integration reports under `outputs/`

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
- canonical project-shaping docs,
- the current references supplement,
- the central references audit,
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
- baseline/comparison references,
- idea/ingredient references,
- and provenance references.

They are not the same thing.

## Safe practical rule

When a reference is used in paper writing, first ask:
1. is it part of the current core conceptual frame,
2. is it a direct / near-direct baseline or only an adjacent one,
3. is it only an ingredient / design-direction source,
4. or is it historical/provenance only?

If it is only a design-direction source, it may still be very useful, but it should be filtered more carefully before manuscript citation.

## Recommended next cleanup habit

When new literature or external methods are investigated, record them in one of these places:
- canonical project-shaping docs if they are central,
- external-baseline completeness notes if they are comparison baselines,
- research-takeaway notes if they mainly shape future target-design ideas,
- historical/provenance notes only if they are superseded,
- and the central references audit if they materially change relevance or category boundaries.

## Safe summary

A safe repository-facing summary is:

> The reference base is already rich, but it must now be treated as a curated system rather than a flat list. The main organizational task is to distinguish clearly between canonical project-shaping references, direct/adjacent baseline references, ingredient/design-direction references, and historical/provenance references so that future work stays organized and paper claims stay clean.
