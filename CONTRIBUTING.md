# Contributing

This is an early-stage research repository. Contributions and collaboration are by invitation only at this stage.

## Lightweight workflow

1. **Read the canonical docs first**: start with `README.md`, `docs/CANONICAL_START_HERE.md`, and `docs/CANONICAL_INSTALL_AND_DEV.md` before making structural changes.
2. **Discuss before coding**: open an issue or discuss with collaborators before starting significant work.
3. **Branch naming**: use descriptive branch names, e.g. `theory/noise-model`, `experiments/gsm8k-baseline`, `docs/related-work`.
4. **Commits**: write clear, concise commit messages. Prefer small, focused commits over large ones.
5. **Pull requests**: open a pull request for review before merging into `main`. Add a short description of what changed and why.
6. **No fake results**: do not commit placeholder or fabricated experimental results. Use `TODO` markers or notes instead.
7. **No large binary files**: do not commit model weights, large datasets, or raw outputs. Use `.gitignore` and external storage. Run artifacts belong under `outputs/`.
8. **Secrets**: never commit `.env`, tokens, or credential files. Verification scripts should only write summaries under `outputs/`.
9. **Documentation first**: when adding a new experiment or theory direction, start with a markdown note before writing code.

## Local checks

Before opening a PR, run:

```bash
make health
make lint
make test
```

If you changed formatting-sensitive Python files, also run:

```bash
make format
```

## Code style

- Python code is formatted with `ruff`.
- Keep scripts minimal and well-commented.
- Prefer readability over cleverness.
- Update the repo front-door docs when the project phase changes materially.

## Questions

Reach out to the project maintainer before making significant changes to the formulation or structure.
