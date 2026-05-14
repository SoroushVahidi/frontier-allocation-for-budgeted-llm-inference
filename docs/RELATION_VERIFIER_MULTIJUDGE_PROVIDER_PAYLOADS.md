# RelationReady Multi-Judge — Provider Payload Builder

## Purpose

`scripts/build_relation_verifier_provider_payloads.py` converts a
`judge_requests.jsonl` file (produced by
`scripts/build_relation_verifier_multijudge_label_requests.py`) into a
`provider_payloads.jsonl` file that contains one ready-to-send chat payload per
`(request, provider)` pair.

**This script is a dry-run-only tool.** It never makes network calls, never
imports provider SDKs, and never includes gold answers or human labels in any
payload.

---

## CLI Usage

```bash
python3 scripts/build_relation_verifier_provider_payloads.py \
  --requests-jsonl <judge_requests.jsonl> \
  --output-dir <output_dir> \
  --providers cohere,mistral,fireworks,cerebras,azure_openai \
  --temperature 0 \
  --max-rows 10
```

### Arguments

| Flag | Required | Default | Description |
|---|---|---|---|
| `--requests-jsonl` | yes | — | Path to `judge_requests.jsonl` |
| `--output-dir` | yes | — | Directory for output files (created if absent) |
| `--providers` | no | all five | Comma-separated list of providers |
| `--temperature` | no | `0` | Sampling temperature written into every payload |
| `--max-rows` | no | all | Process at most N input rows |
| `--model-override PROVIDER=MODEL` | no | — | Override default model for one provider; repeatable |

### Supported providers

`cohere`, `mistral`, `fireworks`, `cerebras`, `azure_openai`

### Default models

| Provider | Default model |
|---|---|
| cohere | `command-r-plus-08-2024` |
| mistral | `mistral-small-latest` |
| fireworks | `accounts/fireworks/models/llama-v3p1-8b-instruct` |
| cerebras | `llama3.1-8b` |
| azure_openai | `gpt-4o-mini` |

Override with `--model-override cohere=command-r-plus-04-2024`.

---

## Output Files

Both files are written to `--output-dir`.

### `provider_payloads.jsonl`

One JSON object per line, one per `(request, provider)` pair.

```json
{
  "row_id": "rrseed_ba65f6d4d5acf955",
  "provider": "cohere",
  "model": "command-r-plus-08-2024",
  "temperature": 0,
  "dry_run": true,
  "api_call_made": false,
  "prompt_sha256": "fcc42d...",
  "payload": { ... provider-specific chat object ... },
  "expected_json_schema": { ... }
}
```

`prompt_sha256` is the SHA-256 hex digest of the prompt string as UTF-8, useful
for deduplication and audit trails.

`expected_json_schema` is copied verbatim from the source request; it describes
the JSON structure the judge model should return.

### `build_report.md`

Human-readable summary including:

- Input / output row counts
- Models used per provider
- Leakage scan results (any row with forbidden terms is skipped and listed)
- Field-issue summary
- Confirmation that no API calls were made

---

## Provider Payload Shapes

### cohere — Cohere Chat API

```json
{
  "model": "command-r-plus-08-2024",
  "message": "<prompt text>",
  "temperature": 0,
  "response_format": {"type": "json_object"}
}
```

Uses `message` (singular) per the Cohere Chat API.

### mistral / fireworks / azure_openai — OpenAI-compatible Chat API

```json
{
  "model": "mistral-small-latest",
  "messages": [{"role": "user", "content": "<prompt text>"}],
  "temperature": 0,
  "response_format": {"type": "json_object"}
}
```

### cerebras — OpenAI-compatible Chat API (no JSON mode)

```json
{
  "model": "llama3.1-8b",
  "messages": [{"role": "user", "content": "<prompt text>"}],
  "temperature": 0
}
```

Cerebras does not support `response_format`, so the field is omitted.

---

## Label Convention: `ready` Means Final-Selection-Ready

In this pilot, `ready` means the visible candidate trace AND answer are
acceptable for final selection — not merely that the semantic relation is
plausible. A candidate with the correct semantic structure but a wrong
numerical answer is `not_ready` with `first_error_axis = arithmetic_only_error`.

The judge prompt encodes this explicitly:

> *ready: the trace correctly represents the semantic relation AND the answer is
> acceptable for final selection; a numerically wrong answer with correct semantic
> structure is still not_ready.*

Future datasets may split `semantic_relation_ready` from `final_answer_correct`,
but the schema is unchanged in this pilot.

---

## Safety Constraints

The script enforces the following constraints at build time:

1. **No network calls** — no `urllib`, `requests`, `httpx`, or SDK calls.
2. **No provider SDK imports** — `import cohere`, `import openai`, etc. are
   absent from the script.
3. **No gold answer leakage** — any prompt containing terms such as
   `relation_ready_label_manual`, `first_error_axis_manual`, `notes_manual`,
   `human_relation_ready_label`, `likely not_ready`, `good judge should label`,
   etc. is **skipped** and logged in `build_report.md`.
4. **No private-label fields in output** — `provider_payloads.jsonl` contains
   only the prompt (via the inner payload), `row_id`, provider metadata, SHA-256
   digest, and the expected schema.

---

## Workflow Position

```
build_relation_verifier_multijudge_label_requests.py
    → judge_requests.jsonl

build_relation_verifier_provider_payloads.py          ← this script
    → provider_payloads.jsonl  (dry run; no API calls)

[future] live runner sends provider_payloads.jsonl rows to each provider
    → raw_judge_responses.jsonl

run_relation_verifier_multijudge_calibration.py  (mock_jsonl mode)
    → normalized_judge_responses.jsonl
    → judge_agreement_report.md
```

---

## Example

```bash
python3 scripts/build_relation_verifier_provider_payloads.py \
  --requests-jsonl outputs/relation_verifier_multijudge_requests_clean2_20260513T151307Z/judge_requests.jsonl \
  --output-dir outputs/relation_verifier_provider_payloads_dryrun_$(date -u +%Y%m%dT%H%M%SZ) \
  --providers cohere,mistral,fireworks,cerebras,azure_openai \
  --temperature 0 \
  --max-rows 10
```

Expected terminal output (33-row input, 10-row cap, 5 providers):

```
Build complete: ...judge_requests.jsonl
Output directory: ...

Input rows       : 10
Skipped rows     : 0
Providers        : 5
Payloads emitted : 50

Files written:
  - provider_payloads.jsonl
  - build_report.md

✓ No API calls were made.
✓ No provider SDK imports were used.
✓ Gold answers and human labels were not included in any payload.
```
