# Cohere production-key runtime verification pass (2026-04-17)

Run ID: `cohere_production_key_verification_20260417`

## Runtime key usage check
- Runtime key path inspected: `os.environ['COHERE_API_KEY'] (same path used by scripts/cohere_adjudicate_hard_pairs.py)`.
- Key present: `True`.
- Safe key fingerprint: prefix `Eai5wb`, suffix `JSj0`, sha256_12 `4d3d5d714cd6`, length `40`.
- Cached/old-key inference: No evidence of cached key in-process; client is instantiated directly from current os.environ value

## Tiny live Cohere probe
- Model: `command-r-plus-08-2024`.
- Success: `True`.
- Latency ms: `391.32`.
- 429 observed: `False`.
- Error (if any): `None` / `None`.

## Bounded burst test
- Requested count: `8`; executed: `8`.
- Successes: `8`; failures: `0`.
- 429 observed: `False`; stopped early: `False`.
- Latency min/avg/max (ms): `180.52` / `249.21` / `327.99`.

## Final readiness decision
- Ready for rerunning bounded Cohere hard-pair adjudication: `True`.
- Decision reason: `bounded_probe_ok`.
- Details: Probe and bounded burst completed without 429

## Artifacts
- `outputs/cohere_runtime_verification/cohere_production_key_verification_20260417/safe_key_fingerprint.json`
- `outputs/cohere_runtime_verification/cohere_production_key_verification_20260417/probe_result.json`
- `outputs/cohere_runtime_verification/cohere_production_key_verification_20260417/burst_test_summary.json`
- `outputs/cohere_runtime_verification/cohere_production_key_verification_20260417/final_status.json`
- `outputs/cohere_runtime_verification/cohere_production_key_verification_20260417/verification_full.json`
