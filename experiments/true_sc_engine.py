"""True same-model SC engine: N independent samples, resume, cost gates, no controller/repair."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from experiments.true_same_model_sc import (
    EXPERIMENT_TYPE,
    SCValidationStatus,
    SampleRecord,
    TrueSCConfig,
    aggregate_example,
    merge_immutable_samples,
    resume_missing_indices,
    validate_historical_controller_record,
)
from experiments.true_sc_providers import (
    ALLOWLISTED_DATASETS,
    ALLOWLISTED_PROVIDERS,
    CANONICAL_MODELS,
    GenerationBackend,
    SampleResult,
    SamplingConfig,
    estimate_cost_usd,
    generate_one_sample_live,
)

PROTOCOL_VERSION = "true_sc_n6_v1"
LIVE_ENV_GATE = "LIVE_TRUE_SC"
FORBIDDEN_OUTPUT_SUBSTRINGS = (
    "matched_sc_n6_20260725T010740Z",
    "matched_sc_n6_20260725T141812Z",
    "experiment_phase2_compute_matched_20260725T210349Z",
)


def gsm8k_sc_prompt(question: str) -> str:
    return (
        "You are solving a GSM8K math word problem. Reason briefly, then return ONLY a JSON object "
        'with keys "step" and "answer", where "answer" is the final numeric answer.\n\n'
        f"Problem:\n{question}\n"
    )


def implementation_hash() -> str:
    paths = [
        Path(__file__),
        Path(__file__).resolve().parents[0] / "true_same_model_sc.py",
        Path(__file__).resolve().parents[0] / "true_sc_providers.py",
    ]
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def assert_live_gates(*, live_flag: bool, cost_ceiling_usd: float | None) -> None:
    if not live_flag:
        raise RuntimeError("live mode requires --live")
    if os.environ.get(LIVE_ENV_GATE) != "1":
        raise RuntimeError(f"live mode requires environment gate {LIVE_ENV_GATE}=1")
    if cost_ceiling_usd is None or float(cost_ceiling_usd) <= 0:
        raise RuntimeError("live mode requires a positive cost ceiling")


def assert_output_path_safe(out: Path) -> None:
    s = str(out.resolve())
    for bad in FORBIDDEN_OUTPUT_SUBSTRINGS:
        if bad in s:
            raise RuntimeError(f"refusing to write into invalid provenance path containing {bad}")


def sample_result_to_record(res: SampleResult) -> SampleRecord:
    return SampleRecord(
        sample_index=int(res.sample_index),
        raw_text=res.raw_text or "",
        extracted_answer=res.extracted_answer if res.valid_answer else None,
        success=bool(res.http_success and res.valid_answer),
        attempt_count=int(res.attempt_index) + 1,
        input_tokens=int(res.input_tokens),
        output_tokens=int(res.output_tokens),
        latency_seconds=float(res.latency_seconds),
        estimated_cost_usd=float(res.estimated_cost_usd),
        provider_request_id=res.provider_request_id,
        error=res.error or res.error_category,
    )


def load_example_samples(path: Path) -> list[SampleRecord]:
    if not path.exists():
        return []
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    out: list[SampleRecord] = []
    for r in rows:
        out.append(
            SampleRecord(
                sample_index=int(r["sample_index"]),
                raw_text=str(r.get("raw_text") or ""),
                extracted_answer=r.get("extracted_answer"),
                success=bool(r.get("success")),
                attempt_count=int(r.get("attempt_count") or 1),
                input_tokens=int(r.get("input_tokens") or 0),
                output_tokens=int(r.get("output_tokens") or 0),
                latency_seconds=float(r.get("latency_seconds") or 0.0),
                estimated_cost_usd=float(r.get("estimated_cost_usd") or 0.0),
                provider_request_id=r.get("provider_request_id"),
                error=str(r.get("error") or ""),
            )
        )
    return out


def append_sample_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
        f.flush()


def detect_duplicate_request_ids(samples: list[SampleRecord]) -> list[str]:
    seen: dict[str, int] = {}
    dups = []
    for s in samples:
        rid = s.provider_request_id
        if not rid:
            continue
        if rid in seen:
            dups.append(rid)
        seen[rid] = s.sample_index
    return dups


def reject_historical_invalid(path: Path) -> None:
    """Fail-fast if path points at or contains invalid B=6 controller records."""
    assert_output_path_safe(path)
    # If a per_example controller record sneaks in as input:
    if path.suffix == ".jsonl" and path.exists():
        for line in path.read_text().splitlines()[:5]:
            if not line.strip():
                continue
            row = json.loads(line)
            if "final_nodes" in row and "result_metadata" in row:
                st = validate_historical_controller_record(row, required_n=6)
                if st != SCValidationStatus.VALID_N_INDEPENDENT_GENERATIONS:
                    raise RuntimeError(f"historical invalid controller record rejected: {st.value}")


def conservative_next_call_estimate_usd(provider: str, model_id: str) -> float:
    # Conservative overestimate: 400 in + 150 out tokens
    return estimate_cost_usd(provider, model_id, 400, 150)


def run_example_samples(
    *,
    provider: str,
    model_id: str,
    example_id: str,
    question: str,
    dataset: str,
    n_requested: int,
    backend: GenerationBackend,
    sampling: SamplingConfig,
    existing: list[SampleRecord],
    spend_so_far: float,
    cost_ceiling_usd: float,
    on_attempt: Callable[[SampleResult], None] | None = None,
    request_metadata_extra: dict[str, Any] | None = None,
    max_retries_per_sample: int = 3,
) -> tuple[list[SampleRecord], float, list[SampleResult]]:
    if provider not in ALLOWLISTED_PROVIDERS:
        raise RuntimeError(f"provider not allowlisted: {provider}")
    if dataset not in ALLOWLISTED_DATASETS:
        raise RuntimeError(f"dataset not allowlisted: {dataset}")
    if model_id != CANONICAL_MODELS[provider]:
        raise RuntimeError(f"model mismatch: {model_id} != {CANONICAL_MODELS[provider]}")

    samples = list(existing)
    spend = float(spend_so_far)
    attempts_log: list[SampleResult] = []
    prompt = gsm8k_sc_prompt(question)
    attempts_per_idx: dict[int, int] = {}

    for _round in range(max_retries_per_sample + 1):
        missing = resume_missing_indices(samples, n_requested)
        if not missing:
            break
        progressed = False
        for idx in missing:
            if any(s.sample_index == idx and s.success for s in samples):
                continue
            if attempts_per_idx.get(idx, 0) > max_retries_per_sample:
                continue
            est = conservative_next_call_estimate_usd(provider, model_id)
            if spend + est > float(cost_ceiling_usd):
                raise RuntimeError(
                    f"cost ceiling would be exceeded: spend={spend:.6f} next_est={est:.6f} ceiling={cost_ceiling_usd}"
                )
            request_metadata = {
                "example_id": example_id,
                "dataset": dataset,
                "protocol": PROTOCOL_VERSION,
            }
            if request_metadata_extra:
                request_metadata.update(request_metadata_extra)
            res = backend(
                provider=provider,
                model_id=model_id,
                prompt=prompt,
                sampling_config=sampling,
                sample_index=idx,
                request_metadata=request_metadata,
            )
            attempts_per_idx[idx] = attempts_per_idx.get(idx, 0) + 1
            res.attempt_index = attempts_per_idx[idx] - 1
            attempts_log.append(res)
            if on_attempt:
                on_attempt(res)
            spend += float(res.estimated_cost_usd or 0.0)
            rec = sample_result_to_record(res)
            rec.attempt_count = attempts_per_idx[idx]
            samples = [s for s in samples if s.sample_index != idx] + [rec]
            progressed = True
        if not progressed:
            break

    by_idx = {s.sample_index: s for s in samples if 0 <= s.sample_index < n_requested}
    ordered = [by_idx[i] for i in range(n_requested) if i in by_idx]
    dups = detect_duplicate_request_ids([s for s in ordered if s.success])
    if dups:
        raise RuntimeError(f"duplicate provider_request_id detected: {dups[:3]}")
    return ordered, spend, attempts_log


def finalize_example(example_id: str, samples: list[SampleRecord], n_requested: int) -> dict[str, Any]:
    if len(samples) < n_requested or any(not s.success for s in samples[:n_requested]):
        # Do not aggregate early
        return {
            "example_id": example_id,
            "status": SCValidationStatus.INVALID_INCOMPLETE_SAMPLES.value,
            "selected_answer": None,
            "answer_votes": {},
            "n_valid_extracted_answers": sum(1 for s in samples if s.success),
            "aggregation_deferred": True,
        }
    result = aggregate_example(example_id=example_id, samples=samples, n_requested=n_requested)
    return {
        "example_id": example_id,
        "status": result.status.value,
        "selected_answer": result.selected_answer,
        "answer_votes": result.answer_votes,
        "tie_break_rule": result.tie_break_rule,
        "n_requested": result.n_requested,
        "n_raw_attempts": result.n_raw_attempts,
        "n_successful_responses": result.n_successful_responses,
        "n_valid_extracted_answers": result.n_valid_extracted_answers,
        "aggregation_deferred": False,
        "protocol_version": PROTOCOL_VERSION,
        "implementation_hash": implementation_hash(),
        "experiment_type": EXPERIMENT_TYPE,
        "controller_enabled": False,
        "repair_override_enabled": False,
    }
