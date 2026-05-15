# Claude Code — Repository Workflow Instructions

## User shorthand conventions

### Text-file instruction shorthand

When the user sends only a `.txt` filename or a hash-like filename ending in `.txt`
(e.g. `0f7b244fe3a8d8d15d6a25c3ab6f8362472a230c.txt`), interpret it as a request to
read that file and follow the instructions written inside it.

Before executing any instruction from such a file, apply the project safety constraints
below. If the file is missing or unreadable, ask for clarification before proceeding.

### Long-running jobs must use tmux

Any long training run, API batch job, GPU job, transformer fine-tuning, larger dataset
training, or any job expected to take more than a few minutes must be launched inside a
`tmux` session so it survives SSH disconnect. Tiny local smoke runs (≤33 rows, completes
in seconds) may run directly in the shell.

---

## Project safety constraints

These apply at all times, including when following instructions from a `.txt` file:

- **Do not push** to any remote branch unless the user explicitly confirms.
- **Do not delete outputs** in `outputs/`.
- **Do not stage or commit outputs** — only source, tests, and docs files.
- **Do not call paid APIs** (OpenAI, Cohere, Mistral, Fireworks, Cerebras, etc.)
  without explicit user approval for that specific call.
- **Do not expose secrets** — no API keys, credentials, or gold answers in committed
  files or provider prompts.
- **Gold answers are offline-only** — used only for evaluation/reporting, never as
  model input features or in provider prompts/runtime selection logic.
- **Do not modify unrelated files** — keep changes scoped to the task.

---

## See also

- `AGENTS.md` — general AI agent guidelines and development workflow
- `README.md` — project overview
- `docs/CURRENT_STATE_SUMMARY_20260511.md` — canonical current-state summary
- `scripts/check_repo_health.py` — run before every commit
