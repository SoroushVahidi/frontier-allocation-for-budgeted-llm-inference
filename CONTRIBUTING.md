# Contributing

This is an early-stage research repository. Contributions and collaboration are by invitation only at this stage.

---

## Lightweight Workflow

1. **Discuss before coding**: Open an issue or discuss with collaborators before starting significant work.

2. **Branch naming**: Use descriptive branch names, e.g., `theory/noise-model`, `experiments/gsm8k-baseline`, `docs/related-work`.

3. **Commits**: Write clear, concise commit messages. Prefer small, focused commits over large ones.

4. **Pull requests**: Open a pull request for review before merging into `main`. Add a short description of what changed and why.

5. **No fake results**: Do not commit placeholder or fabricated experimental results. Use `TODO` markers or notes instead.

6. **No large binary files**: Do not commit model weights, large datasets, or raw outputs. Use `.gitignore` and external storage. Run artifacts belong under **`outputs/`** (ignored); the legacy **`output/`** tree is also ignored—do not re-add it to version control.

7. **Secrets**: Never commit `.env`, tokens, or credential files. Verification scripts should only write summaries under `outputs/`.

8. **Documentation first**: When adding a new experiment or theory direction, start with a markdown note before writing code.

---

## Code Style

- Python code is formatted with `ruff` (run `make format`).
- Keep scripts minimal and well-commented.
- Prefer readability over cleverness.

---

## Questions

Reach out to the project maintainer before making significant changes to the formulation or structure.
