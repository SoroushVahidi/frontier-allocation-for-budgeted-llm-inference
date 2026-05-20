# RelationReady Mistral Judge Adapter

## Purpose

`scripts/run_relation_verifier_mistral_judge_adapter.py` submits Mistral
chat payloads (built by `scripts/build_relation_verifier_provider_payloads.py`)
to the Mistral Chat API and normalises the responses into the
`normalized_judge_responses.jsonl` schema consumed by
`scripts/run_relation_verifier_multijudge_calibration.py`.

**Default behaviour is no-network dry-run.** Real API calls require the
explicit `--allow-api` flag.

---

## CLI

```bash
python3 scripts/run_relation_verifier_mistral_judge_adapter.py \
  --payloads-jsonl <provider_payloads.jsonl> \
  --output-dir    <output_dir> \
  --mode          dry_run | mock_api | api \
  [--mock-response-jsonl <mock.jsonl>]   # required for mock_api
  [--start-index  N]                     # zero-based start (default: 0)
  [--max-rows     N]
  [--row-ids      id1,id2,...]           # explicit allowlist; overrides start-index/max-rows
  [--allow-api]                          # required for api mode
  [--api-key-env  MISTRAL_API_KEY]       # default: MISTRAL_API_KEY
```

### Arguments

| Flag | Required | Default | Description |
|---|---|---|---|
| `--payloads-jsonl` | yes | — | `provider_payloads.jsonl` from the payload builder; non-Mistral rows are silently skipped |
| `--output-dir` | yes | — | Output directory (created if absent) |
| `--mode` | yes | — | `dry_run`, `mock_api`, or `api` |
| `--mock-response-jsonl` | mock_api only | — | JSONL of synthetic Mistral responses |
| `--start-index` | no | `0` | Zero-based index into the Mistral payload list; combined with `--max-rows` to select a slice |
| `--max-rows` | no | all | Maximum number of Mistral rows to process after applying `--start-index` |
| `--row-ids` | no | — | Comma-separated explicit `row_id` allowlist; **takes precedence over `--start-index` and `--max-rows`** |
| `--allow-api` | api mode only | false | Enables real Mistral calls |
| `--api-key-env` | no | `MISTRAL_API_KEY` | Env-var name holding the API key |

**Row selection priority:** `--row-ids` → `--start-index` + `--max-rows`.  
Example — submit only rows 6–10 (zero-based indices 5–9):
```bash
--start-index 5 --max-rows 5
```

---

## Modes

### `dry_run`

Validates each Mistral payload row without network calls.

Checks:
- `row_id`, `provider == "mistral"`, `model`, `payload`, `expected_json_schema` are all present
- Prompt (from `payload.messages[0].content`) is scanned for forbidden leakage terms

Outputs:
- `mistral_dry_run_manifest.jsonl` — one row per input with `field_issues` and `leakage_terms`
- `mistral_adapter_report.md` — summary

### `mock_api`

Feeds pre-written synthetic Mistral response text through the normalizer.
No network calls.

Mock response JSONL format (one object per line):
```json
{
  "row_id": "rrseed_ba65f6d4d5acf955",
  "response_text": "{\"relation_ready_label\": \"not_ready\", \"first_error_axis\": \"arithmetic_only_error\", \"confidence\": \"high\", \"rationale\": \"Trace adds today only.\"}"
}
```

`response_text` is the JSON string that Mistral's
`response.choices[0].message.content` field would return for a
`response_format: json_object` request.

Outputs:
- `normalized_judge_responses.jsonl`
- `mistral_adapter_report.md`

### `api`

Submits real Mistral requests. **Requires `--allow-api`.**

- API key is read from the env var named by `--api-key-env` (never hard-coded).
- Requires `pip install mistralai`; exits with a clear error if the SDK is absent.
- Writes the same output files as `mock_api`.

---

## Payload Shape

Mistral payloads use the OpenAI-compatible messages format:

```json
{
  "model": "mistral-small-latest",
  "messages": [{"role": "user", "content": "<prompt>"}],
  "temperature": 0,
  "response_format": {"type": "json_object"}
}
```

This differs from the Cohere adapter which uses `payload.message` (flat string).
The adapter extracts the prompt via `payload.messages[0].content` for leakage
scanning.

---

## Normalized Judge Response Schema

Each row in `normalized_judge_responses.jsonl`:

```json
{
  "row_id": "rrseed_ba65f6d4d5acf955",
  "judge_name": "mistral:mistral-small-latest",
  "relation_ready_label": "not_ready",
  "first_error_axis": "arithmetic_only_error",
  "confidence": "high",
  "rationale": "The trace computes only today's cookies."
}
```

`judge_name` is always `mistral:<model>` so downstream aggregation can
distinguish model versions.

This schema is directly consumable by
`run_relation_verifier_multijudge_calibration.py --mode mock_jsonl`.

---

## Safety Constraints

1. **No network calls by default** — `dry_run` and `mock_api` never touch the network.
2. **`--allow-api` gate** — `api` mode exits with a clear error if the flag is absent.
3. **API key from env only** — never hard-coded; read via `os.environ.get(api_key_env)`.
4. **No SDK at module level** — `from mistralai import Mistral` lives inside `run_api()` only, so
   tests and dry-run paths work without the SDK installed.
5. **Leakage scan** — prompts containing any of the following terms cause the row to
   be skipped and reported:
   - `gold_answer_metadata_only`
   - `relation_ready_label_manual`
   - `first_error_axis_manual`
   - `notes_manual`
   - `likely not_ready` / `likely ready` / `likely uncertain`
   - `ready candidate` / `not_ready candidate` / `uncertain candidate`
   - `good judge should label`
6. **Human labels never written to provider prompts** — the adapter reads only
   `provider_payloads.jsonl`; private calibration files are never loaded.

---

## Workflow Position

```
build_relation_verifier_provider_payloads.py
    → provider_payloads.jsonl

run_relation_verifier_mistral_judge_adapter.py  ← this script
  dry_run  → mistral_dry_run_manifest.jsonl + mistral_adapter_report.md
  mock_api → normalized_judge_responses.jsonl + mistral_adapter_report.md
  api      → normalized_judge_responses.jsonl + mistral_adapter_report.md

run_relation_verifier_multijudge_calibration.py --mode mock_jsonl
    --mock-responses-jsonl normalized_judge_responses.jsonl
    → judge_agreement_report.md
```

---

## Example — Dry Run

```bash
python3 scripts/run_relation_verifier_mistral_judge_adapter.py \
  --payloads-jsonl outputs/relation_verifier_mistral_payloads_dryrun_20260514T000000Z/provider_payloads.jsonl \
  --output-dir outputs/mistral_judge_adapter_dryrun_$(date -u +%Y%m%dT%H%M%SZ) \
  --mode dry_run \
  --max-rows 10
```

Expected output:
```
Dry-run complete: ...provider_payloads.jsonl
Output directory: ...

Mistral rows found : 10
Field issues       : 0
Leakage issues     : 0

Files written:
  - mistral_dry_run_manifest.jsonl
  - mistral_adapter_report.md

✓ No API calls were made.
✓ No provider SDK imports were used.
```

## Example — Real API Run (when approved)

```bash
export MISTRAL_API_KEY="<your-key>"

python3 scripts/run_relation_verifier_mistral_judge_adapter.py \
  --payloads-jsonl outputs/relation_verifier_mistral_payloads_dryrun_20260514T000000Z/provider_payloads.jsonl \
  --output-dir outputs/mistral_judge_adapter_live_$(date -u +%Y%m%dT%H%M%SZ) \
  --mode api \
  --allow-api \
  --max-rows 5
```
