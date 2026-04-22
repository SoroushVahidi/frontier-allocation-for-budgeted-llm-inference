# Contributing

This repository is research-heavy and intentionally preserves both **current canonical material** and **historical provenance**. The goal of this guide is to keep new additions organized without flattening the research trail.

Contributions and collaboration are still effectively by maintainer coordination, but this file now also serves as the repository’s placement and maintenance guide.

## First read

Before adding or reorganizing anything, read:
1. `README.md`
2. `docs/README.md`
3. `docs/REPO_MAP.md`
4. `docs/CANONICAL_INSTALL_AND_DEV.md`
5. `scripts/README.md`

## Core organizational rule

Every new file should have an obvious home and an obvious interpretation label.

Use these labels consistently:
- **Canonical**: defines the current repo-wide project identity or current paper-facing interpretation.
- **Exploratory**: active side branch, bounded experiment, or mechanism-specific note.
- **Historical**: provenance-only material that should not redefine the current project story.

If a new note or artifact is not meant to be canonical, do not wire it into the front door as if it is.

## Where things should go

### `docs/`
Use for:
- canonical project notes,
- current status summaries,
- experiment-family indexes,
- baseline/reference memos,
- methodological audit notes,
- exploratory analysis writeups.

Do not put runnable code here.

### `scripts/`
Use for:
- runnable entry points,
- dataset/baseline preparation utilities,
- report builders,
- evaluation orchestration.

Prefer script names that make scope obvious. Good patterns include:
- `run_<experiment_family>.py`
- `build_<artifact_family>.py`
- `generate_<status_or_report>.py`
- `verify_<integration_or_contract>.py`

### `experiments/`
Use for reusable implementation modules that scripts call.

Prefer placing logic here when it is shared by multiple scripts or is substantial enough to deserve tests.

### `outputs/`
Use for generated artifacts only.

New output families should usually follow:
- `outputs/<artifact_family>/<timestamp>/...`

If a family is intended to be paper-facing or canonical, document it in:
- `outputs/README.md`
- and the relevant current docs index in `docs/`.

### `references/`
Use for literature notes, paper summaries, and reference-facing provenance.

### `external/`
Use for integration-facing material tied to external baselines, adapters, or imported packages.

### `archive/`
Use for historical material that should be preserved but not treated as current canonical guidance.

## When you add a new canonical file

If a change materially affects the current project story, update the front door together:
- `README.md`
- `docs/README.md`
- `docs/REPO_MAP.md`
- `docs/CANONICAL_INSTALL_AND_DEV.md`
- `scripts/README.md`
- `outputs/README.md` when output interpretation changed

Do not update just one index and leave the others stale.

## Workflow expectations

1. Discuss before making large structural changes.
2. Use descriptive branch names.
3. Prefer small, focused commits over large mixed commits.
4. Open a pull request before merging into `main`.
5. Do not commit fabricated or placeholder results as if they were final evidence.
6. Never commit secrets, credentials, or large raw artifacts that do not belong in version control.

## Minimum maintenance before committing

Run:

```bash
make smoke
make health
make lint
make test
```

For the most common consolidated check:

```bash
make check
```

## Naming and placement preferences

- Prefer explicit names over vague names like `notes.md` or `temp_results.md`.
- Keep date-stamped status notes in `docs/` when they are part of the research trail.
- Keep repository-wide summaries undated when they are meant to stay canonical for a longer phase.
- Do not create a new top-level directory unless an existing one is clearly wrong.
- Do not mix generated artifacts with hand-written notes.

## Output and manuscript discipline

- Do not treat arbitrary output folders as manuscript-ready evidence unless they are linked from the current canonical docs.
- If an artifact family becomes paper-facing, add a short interpretation note for it.
- Preserve provenance, but keep the current paper story anchored to the current canonical indexes.

## Historical cleanup rule

When a formerly important file becomes provenance-only, move or label it so that readers do not mistake it for current truth. If the content still matters, keep it accessible through an exploratory or historical index rather than deleting context.

## Small changes are preferred

This repository evolves quickly. Favor small, reviewable cleanup commits that improve:
- navigation,
- interpretation clarity,
- reproducibility,
- and consistency between docs, scripts, and outputs.

Large reorganizations are only worth doing when they clearly reduce confusion without obscuring provenance.
