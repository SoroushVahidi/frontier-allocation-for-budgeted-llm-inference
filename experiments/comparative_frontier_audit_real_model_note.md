# Real-model comparative frontier audit (new-paper track)

The audit runner supports a **single remote backend per run** (matched budget, same model for expand/verify/PoT).

## Command

```bash
# Loads keys from repo-root `.env` via python-dotenv (same process).
python scripts/run_comparative_frontier_audit.py \
  --api-backend openai \
  --model gpt-4.1-mini \
  --subset-size 10 \
  --budgets 8,10 \
  --datasets openai/gsm8k,EleutherAI/hendrycks_math
```

Alternatives: `--api-backend groq` (needs `GROQ_API_KEY`), `--api-backend gemini` (needs `GOOGLE_API_KEY` or `GEMINI_API_KEY`). `--use-openai-api` is a shortcut for `--api-backend openai`.

## Example committed run (OpenAI)

- **`outputs/comparative_frontier_audit/20260413T221305Z/`** — `gpt-4.1-mini`, GSM8K only, `subset_size=4`, budget `8` (pilot-scale; see `run_manifest.json` and `main_drawbacks_report.md`).

Earlier runs under the same directory without `api_backend: openai` are **simulator-backed** (see manifests).

## Runtime

Full eight-family × multi-budget × multi-dataset audits are **API-heavy** (many sequential calls per example). Expect long wall times or reduce `--subset-size` / `--budgets` first.

## Related

- Simulator + audit mechanics: `experiments/comparative_frontier_audit_result_note.md`
- Implementation: `scripts/run_comparative_frontier_audit.py`, `experiments/frontier_matrix_core.py` (`resolve_api_key_for_provider`, `api_provider` on the generator factory).
