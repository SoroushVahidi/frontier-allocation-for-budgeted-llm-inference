# Canonical runtime dependencies

This note records the runtime dependency interpretation for the current frontier-allocation phase.

## Purpose

The repository has both:
- a `requirements.txt` file used for practical local setup, and
- a `pyproject.toml` file used for package-style installation metadata.

When those drift, collaborators can become confused about what is truly required. This note makes the intended dependency split explicit.

## Core runtime dependencies

These should be treated as the current core runtime set for the active code surface:

- `numpy`
- `datasets`
- `huggingface_hub`
- `scikit-learn`
- `pyyaml`

Why:
- these are directly aligned with the current dataset loading, controller evaluation, router fitting, and config-handling surface.

## Optional API dependency

- `openai`

Why optional:
- some scripts support API-backed or real-model experiments, but the repository should still be locally usable for simulated/controller-side development without requiring API credentials.

## Development dependencies

- `ruff`
- `pytest`

## Practical install recommendation

For most local work, use:

```bash
pip install -r requirements.txt
```

If you want editable-package style work, also use:

```bash
pip install -e .[dev]
```

## Interpretation rule

If you see a mismatch between package metadata and actual runtime imports, treat this document plus `requirements.txt` as the practical source of truth until the metadata is fully synchronized in-place.
