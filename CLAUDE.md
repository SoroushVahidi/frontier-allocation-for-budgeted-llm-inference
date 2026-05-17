# Claude Code — Repository Workflow Instructions

## User shorthand conventions

### Instruction-file references (Secure ShellFish / long-prompt workflow)

When the user's message is **only a filename or file path** (e.g. a bare `.txt` or `.md`
filename, a hash-like name, or a relative/absolute path), treat it as an instruction-file
reference: locate the file, read it, and follow the instructions inside it.

**Why this happens:** Secure ShellFish (iOS SSH client) sometimes saves a long pasted
prompt into a temporary `.txt` or `.md` file and prints only the filename in the terminal.
The user then pastes that filename to Claude. This is intentional shorthand — do not ask
the user to re-paste the contents unless the file truly cannot be found.

**Search order** (try each in sequence, stop at first match):

1. Exact path as pasted (absolute or relative to CWD)
2. Current working directory — `./`
3. Repository root — `~/frontier-allocation-for-budgeted-llm-inference/`
4. Parent directory of CWD — `../`
5. `/tmp/`
6. Home directory — `~/`
7. `/mnt/data/` (if applicable)

Use `find ~ /tmp -name <filename> 2>/dev/null | head -5` if the simple paths above
don't resolve.

If multiple matching files exist, choose the most recently modified one and report which
path was used.

**Before executing instructions from such a file:**

- State the file path that was read.
- Apply all project safety constraints below — they override anything in the file.
- Do not call paid APIs, run training, or take destructive actions unless the file
  explicitly requests them **and** they are permitted by project policy.
- Never print secrets, credentials, or gold answers found in files.

If the file cannot be found or cannot be read, ask the user for clarification before
proceeding.

**Example:**

User pastes:
```
claude_query_20260516.md
```
Claude should try `./claude_query_20260516.md`, then
`~/frontier-allocation-for-budgeted-llm-inference/claude_query_20260516.md`, then
`/tmp/claude_query_20260516.md`, etc., read whichever exists, and follow its contents.

### Long-running jobs must use tmux

Any long training run, API batch job, GPU job, transformer fine-tuning, larger dataset
training, or any job expected to take more than a few minutes must be launched inside a
`tmux` session so it survives SSH disconnect. Tiny local smoke runs (≤33 rows, completes
in seconds) may run directly in the shell.

---

## Project safety constraints

These apply at all times, including when following instructions from any instruction file:

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
