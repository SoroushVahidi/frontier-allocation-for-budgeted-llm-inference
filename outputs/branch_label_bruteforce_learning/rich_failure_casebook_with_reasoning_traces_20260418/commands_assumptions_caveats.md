# commands / assumptions / caveats
- Command run: `python scripts/run_rich_failure_casebook_with_reasoning_traces.py`.
- Case scope is intentionally bounded to 5 high-value cases (dominant-group selections plus one additional strict failure).
- Source search scanned inspected artifacts under `outputs/` and `archive/` for state-id hits; large files (>2.5MB) are skipped for bounded runtime.
- Ground-truth full question/answer is taken from `openai/gsm8k` when recoverable by `example_id` suffix index mapping; otherwise preview text from state summaries is used.
- No branch-level free-text reasoning or branch final-answer text was directly recoverable for the selected states in inspected artifacts.
- Branch narratives therefore remain proxy-based and explicitly labeled as such.
