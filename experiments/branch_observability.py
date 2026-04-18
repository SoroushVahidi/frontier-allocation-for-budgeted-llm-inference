"""Branch-level observability helpers for frontier/branch-allocation pipelines."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from experiments.data import extract_final_answer


NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_numbers(text: str | None) -> list[float]:
    if not text:
        return []
    values: list[float] = []
    for match in NUMBER_PATTERN.findall(text):
        cleaned = match.replace(",", "").strip()
        if not cleaned:
            continue
        try:
            values.append(float(cleaned))
        except ValueError:
            continue
    return values


def _as_non_empty_text(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _first_text(row: dict[str, Any], keys: list[str]) -> tuple[str | None, str | None]:
    for key in keys:
        value = _as_non_empty_text(row.get(key))
        if value is not None:
            return value, key
    return None, None


def _recoverability(field_text: str | None, *, unavailable_reason: str) -> dict[str, Any]:
    if field_text is not None:
        return {"recoverable": True, "unavailable_reason": None}
    return {"recoverable": False, "unavailable_reason": unavailable_reason}


def branch_role_summary(branch: dict[str, Any]) -> str:
    tags: list[str] = []
    depth = int(branch.get("depth", 0))
    verify_count = int(branch.get("verify_count", 0))
    stalled_steps = int(branch.get("stalled_steps", 0))
    if depth > 0:
        tags.append("deeper_branch")
    if verify_count > 0:
        tags.append("contains_verify_steps")
    if stalled_steps > 0:
        tags.append("stalled_recently")
    if not tags:
        tags.append("early_branch")
    return ", ".join(tags)


def normalize_branch_answer(final_answer_text: str | None) -> dict[str, Any]:
    if final_answer_text is None:
        return {
            "normalized_answer": None,
            "normalization_success": False,
            "normalization_method": "unavailable",
            "normalization_confidence": 0.0,
            "normalization_failure_reason": "branch_final_answer_text_raw_unavailable",
        }
    normalized = extract_final_answer(final_answer_text)
    success = bool(str(normalized).strip())
    return {
        "normalized_answer": normalized if success else None,
        "normalization_success": bool(success),
        "normalization_method": "extract_final_answer",
        "normalization_confidence": 1.0 if success else 0.0,
        "normalization_failure_reason": None if success else "extract_final_answer_returned_empty",
    }


def build_branch_trace_record(
    *,
    dataset_name: str | None,
    example_id: str | None,
    state_id: str,
    branch: dict[str, Any],
    state_provenance: dict[str, Any],
    generation_metadata: dict[str, Any] | None = None,
    ground_truth_answer: str | None = None,
) -> dict[str, Any]:
    branch_id = str(branch.get("branch_id", ""))
    branch_text_raw, branch_text_source = _first_text(
        branch,
        keys=["branch_text_raw", "branch_text", "text", "trace_text"],
    )
    reasoning_text_raw, reasoning_source = _first_text(
        branch,
        keys=["branch_reasoning_text_raw", "reasoning_text", "reasoning", "analysis_text"],
    )
    final_answer_text_raw, final_source = _first_text(
        branch,
        keys=["branch_final_answer_text_raw", "final_answer_text", "final_answer", "answer_text"],
    )
    if branch_text_raw is None and reasoning_text_raw is not None and final_answer_text_raw is not None:
        branch_text_raw = f"{reasoning_text_raw}\nFinal answer: {final_answer_text_raw}"
        branch_text_source = "composed_from_reasoning_and_final_answer"

    normalized = normalize_branch_answer(final_answer_text_raw)
    numbers_text = reasoning_text_raw or branch_text_raw
    extracted_numbers = _extract_numbers(numbers_text)

    normalized_gt = extract_final_answer(ground_truth_answer) if ground_truth_answer else None
    matches_ground_truth = (
        bool(normalized["normalization_success"])
        and normalized_gt is not None
        and str(normalized["normalized_answer"]) == str(normalized_gt)
    )

    return {
        "dataset_name": dataset_name,
        "example_id": example_id,
        "state_id": state_id,
        "branch_id": branch_id,
        "branch_text_raw": branch_text_raw,
        "branch_reasoning_text_raw": reasoning_text_raw,
        "branch_final_answer_text_raw": final_answer_text_raw,
        "branch_final_answer_normalized": normalized["normalized_answer"],
        "answer_normalization_metadata": {
            "normalization_success": normalized["normalization_success"],
            "normalization_method": normalized["normalization_method"],
            "normalization_confidence": normalized["normalization_confidence"],
            "normalization_failure_reason": normalized["normalization_failure_reason"],
            "ground_truth_answer_normalized": normalized_gt,
            "matches_ground_truth": matches_ground_truth if normalized_gt is not None else None,
        },
        "extracted_numbers": extracted_numbers,
        "branch_role_summary": branch_role_summary(branch),
        "generation_metadata": generation_metadata or {},
        "provenance_source": {
            "state_provenance": state_provenance,
            "branch_text_source_key": branch_text_source,
            "reasoning_text_source_key": reasoning_source,
            "final_answer_text_source_key": final_source,
        },
        "recoverability_flags": {
            "branch_text_raw": _recoverability(branch_text_raw, unavailable_reason="no_branch_text_fields_in_source"),
            "branch_reasoning_text_raw": _recoverability(
                reasoning_text_raw,
                unavailable_reason="no_branch_reasoning_fields_in_source",
            ),
            "branch_final_answer_text_raw": _recoverability(
                final_answer_text_raw,
                unavailable_reason="no_branch_final_answer_fields_in_source",
            ),
            "branch_final_answer_normalized": {
                "recoverable": bool(normalized["normalization_success"]),
                "unavailable_reason": None if normalized["normalization_success"] else normalized["normalization_failure_reason"],
            },
            "extracted_numbers": {
                "recoverable": bool(extracted_numbers),
                "unavailable_reason": None if extracted_numbers else "no_numeric_tokens_found_in_branch_text",
            },
        },
    }


def write_branch_observability_bundle(
    *,
    output_root: Path,
    run_id: str,
    records: list[dict[str, Any]],
    commands_assumptions_caveats: list[str],
    context_manifest: dict[str, Any],
) -> dict[str, Any]:
    bundle_dir = output_root / run_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    records_path = bundle_dir / "branch_trace_records.jsonl"
    with records_path.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row) + "\n")

    per_state: dict[str, dict[str, Any]] = {}
    recoverability = {
        "total_records": len(records),
        "branch_text_recoverable": 0,
        "branch_reasoning_recoverable": 0,
        "branch_final_answer_recoverable": 0,
        "normalized_answer_recoverable": 0,
    }
    for row in records:
        sid = str(row.get("state_id", ""))
        per_state.setdefault(sid, {"branch_ids": [], "example_id": row.get("example_id"), "dataset_name": row.get("dataset_name")})
        per_state[sid]["branch_ids"].append(row.get("branch_id"))
        flags = row.get("recoverability_flags", {})
        if bool(flags.get("branch_text_raw", {}).get("recoverable")):
            recoverability["branch_text_recoverable"] += 1
        if bool(flags.get("branch_reasoning_text_raw", {}).get("recoverable")):
            recoverability["branch_reasoning_recoverable"] += 1
        if bool(flags.get("branch_final_answer_text_raw", {}).get("recoverable")):
            recoverability["branch_final_answer_recoverable"] += 1
        if bool(flags.get("branch_final_answer_normalized", {}).get("recoverable")):
            recoverability["normalized_answer_recoverable"] += 1

    per_state_path = bundle_dir / "per_state_index.json"
    per_state_path.write_text(json.dumps({"states": per_state}, indent=2) + "\n", encoding="utf-8")

    summary = {
        **recoverability,
        "distinct_states": len(per_state),
        "created_at_utc": _utc_now(),
    }
    summary_path = bundle_dir / "recoverability_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    caveats_path = bundle_dir / "commands_assumptions_caveats.md"
    caveats_path.write_text("\n".join(commands_assumptions_caveats) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "created_at_utc": _utc_now(),
        "bundle_type": "branch_observability_v1",
        "context_manifest": context_manifest,
        "outputs": {
            "branch_trace_records": str(records_path),
            "per_state_index": str(per_state_path),
            "recoverability_summary": str(summary_path),
            "commands_assumptions_caveats": str(caveats_path),
        },
        "counts": summary,
    }
    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {
        "bundle_dir": str(bundle_dir),
        "manifest_path": str(manifest_path),
        "recoverability_summary": summary,
    }
