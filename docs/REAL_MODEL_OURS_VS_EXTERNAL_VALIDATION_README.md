# Real-model ours-vs-external validation package (canonical wrapper)

Use `scripts/run_real_model_ours_vs_external_validation.py` to produce the canonical package:

- Artifact family: `outputs/real_model_ours_vs_external_validation_<TIMESTAMP>/`
- Canonical doc: `docs/REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_<TIMESTAMP>.md`

## Dry-run

```bash
python scripts/run_real_model_ours_vs_external_validation.py --dry-run --timestamp <TIMESTAMP>
```

Dry-run probes dataset-loader readiness and writes package structure without making API calls.

## Real run (OpenAI + optional Cohere)

```bash
python scripts/run_real_model_ours_vs_external_validation.py --timestamp <TIMESTAMP>
```

Behavior:
- Checks `OPENAI_API_KEY` / `COHERE_API_KEY` presence (boolean only; never writes key values).
- Runs OpenAI canonical real-model validation first.
- Attempts Cohere run if Cohere key exists.
- Generates provider-specific outputs, combined ours-vs-external summaries, claim safety matrix, and summary markdown.

Resumable/staged controls:
- `--providers <csv>` to run only selected providers.
- `--resume` to skip already-complete dataset/seed/budget shards.
- `--max-evaluated-rows <N>` to stop early for staged API runs while preserving partial artifacts.

## Interpretation guardrails

- Headline claim is **ours family vs external baselines**, not internal variant ranking.
- Internal ordering (`strict_f3`, `strict_gate1_cap_k6`, `strict_f2`) is surface-sensitive and reported as neighbors/representatives.
- External methods are reported as **near-direct matched adapter baselines under shared substrate**, not official paper reproductions.
- If Cohere is unavailable/incomplete, report OpenAI-only evidence as bounded and keep cross-provider validation open.
