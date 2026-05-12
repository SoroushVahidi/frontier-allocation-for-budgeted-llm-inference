#!/usr/bin/env python3
"""Label PAL failure mechanisms across multiple providers.

The default mode is a deterministic no-API dry run. Live provider calls require
`--allow-api`, explicit providers, and a hard total call cap. The script keeps
the prompt packet gold-free unless `--include-gold-for-labeling` is set.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_FAILURE_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv"
DEFAULT_GOLD_ABSENT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
DEFAULT_ANCHOR_EFFECT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_20260510.csv"
DEFAULT_TARGET_AUDIT_JSONL = REPO_ROOT / "docs/project_handoff_20260510/target_audit_diagnostic_cases.jsonl"
DEFAULT_DIAGNOSTIC_30_JSONL = REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl"
DEFAULT_TARGET_STAGED_15_JSONL = REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl"
DEFAULT_OUTPUTS_ROOT = REPO_ROOT / "outputs"
DEFAULT_OUTPUT_PREFIX = "failure_mechanism_multi_api_"
DEFAULT_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
DEFAULT_SUBSETS = (
    "diagnostic_30",
    "wrong_supported_consensus_97",
    "pal_still_failing_157",
    "direct_l1_anchor_potential_43",
    "target_staged_15",
)
DEFAULT_PROVIDERS = ("cohere", "fireworks")
SUPPORTED_PROVIDERS = ("openai", "cohere", "cerebras", "fireworks", "mistral")
DEFAULT_MODELS = {
    "openai": "gpt-4.1-mini",
    "cohere": "command-r-plus-08-2024",
    "cerebras": "llama3.1-8b",
    "fireworks": "accounts/fireworks/models/glm-5",
    "mistral": "mistral-small-latest",
}
DEFAULT_PROMPT_TEMPLATE_ID = "failure_mechanism_multi_api_v1"
LABEL_FIELDS = [
    "case_id",
    "primary_label",
    "secondary_labels",
    "selector_vs_generation",
    "candidate_pool_status",
    "confidence",
    "evidence",
    "recommended_fix_family",
]
PRIMARY_LABELS = {
    "wrong_target_variable",
    "premature_intermediate_answer",
    "wrong_entity_or_unit",
    "wrong_time_or_state",
    "wrong_relation",
    "wrong_operator",
    "ratio_or_percentage_base_error",
    "PAL_code_grounding_error",
    "PAL_execution_failure",
    "pure_arithmetic_error",
    "correct_candidate_present_not_selected",
    "all_candidates_wrong",
    "candidate_pool_missing",
    "metadata_insufficient",
    "unknown",
}
SECONDARY_LABELS = PRIMARY_LABELS
SELECTOR_VS_GENERATION = {
    "selector_failure",
    "generation_failure",
    "mixed",
    "metadata_insufficient",
    "unknown",
}
POOL_STATUS = {"gold_present", "gold_absent", "no_candidate_pool", "unknown"}
FIX_FAMILIES = {
    "target_schema",
    "equation_relation",
    "unit_ledger",
    "PAL_grounding",
    "selector_structural",
    "candidate_generation_diversity",
    "richer_logging",
    "unknown",
}
PATTERN_FAILURE_STAGES = {
    "target_extraction",
    "relation_mapping",
    "operator_choice",
    "PAL_grounding",
    "candidate_generation",
    "selector",
    "metadata",
    "unknown",
}
FORBIDDEN_PROMPT_TOKENS = ("gold_answer", "answer_key")
TRUE_TOKENS = {"1", "true", "t", "yes", "y", "on"}
FALSE_TOKENS = {"0", "false", "f", "no", "n", "off", "none", "nan", "unknown"}
PROVIDER_ENV_VARS = {
    "openai": ("OPENAI_API_KEY",),
    "cohere": ("COHERE_API_KEY", "CO_API_KEY"),
    "cerebras": ("CEREBRAS_API_KEY",),
    "fireworks": ("FIREWORKS_API_KEY", "OPENAI_API_KEY"),
    "mistral": ("MISTRAL_API_KEY",),
}
PROVIDER_READINESS_VALUES = {
    "ready",
    "auth_error",
    "rate_limited",
    "model_not_found",
    "parse_error",
    "unknown_error",
    "dry_run",
    "config_check",
}
PATTERN_DISCOVERY_CASE_KEYS = (
    "case_id",
    "question",
    "model_final_prediction",
    "candidate_answers",
    "candidate_answer_groups",
    "answer_group_support_counts",
    "selector_candidate_pool",
    "direct_reserve_answer",
    "frontier_candidate_answer",
    "selector_metadata",
    "action_trace_summary",
    "pal_exec_summary",
    "structural_fields",
    "failure_audit_labels",
    "primary_subset",
    "subset_memberships",
)

PATTERN_DISCOVERY_MAX_TOKENS = {
    "openai": 4096,
    "cohere": 4096,
    "cerebras": 4096,
    "fireworks": 4096,
    "mistral": 4096,
}

LABEL_MODE_MAX_TOKENS = {
    "openai": 512,
    "cohere": 512,
    "cerebras": 512,
    "fireworks": 512,
    "mistral": 512,
}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_truthy(value: Any) -> bool:
    text = _stringify(value).lower()
    if not text:
        return False
    if text in TRUE_TOKENS:
        return True
    if text in FALSE_TOKENS:
        return False
    return bool(text)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        text = _stringify(value)
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _max_tokens_for_mode(provider: str, mode: str) -> int:
    provider = provider.lower().strip()
    if mode == "pattern_discovery":
        return PATTERN_DISCOVERY_MAX_TOKENS.get(provider, 1536)
    return LABEL_MODE_MAX_TOKENS.get(provider, 512)


class ProviderRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        url: str = "",
        http_status: int | None = None,
        response_body: str = "",
        headers: dict[str, str] | None = None,
        retry_after: str = "",
    ) -> None:
        super().__init__(message)
        self.url = url
        self.http_status = http_status
        self.response_body = response_body
        self.headers = headers or {}
        self.retry_after = retry_after


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return _stringify(value)


def _maybe_parse_jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)) or value is None:
        return value
    text = _stringify(value)
    if not text:
        return ""
    if text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except Exception:
            return text
    return text


def _latest_file(root: Path, pattern: str) -> Path | None:
    candidates = list(root.rglob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime, str(path)))


def _case_id_from_payload(payload: dict[str, Any]) -> str:
    return _stringify(payload.get("case_id") or payload.get("example_id"))


def _load_case_map(rows: Iterable[dict[str, Any]], key_field: str = "case_id") -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = _stringify(row.get(key_field) or row.get("example_id"))
        if case_id and case_id not in by_id:
            by_id[case_id] = dict(row)
    return by_id


def _load_jsonl_case_map(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    by_id: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl_rows(path):
        case_id = _case_id_from_payload(row)
        if case_id and case_id not in by_id:
            by_id[case_id] = dict(row)
    return by_id


def _load_structural_feature_map(structural_csv: Path | None, outputs_root: Path) -> tuple[dict[str, dict[str, Any]], Path | None]:
    if structural_csv is None or not structural_csv.is_file():
        structural_csv = _latest_file(outputs_root, "candidate_feature_rows.csv")
    if structural_csv is None or not structural_csv.is_file():
        return {}, None

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _read_csv_rows(structural_csv):
        case_id = _stringify(row.get("case_id") or row.get("example_id"))
        if case_id:
            grouped[case_id].append(row)

    out: dict[str, dict[str, Any]] = {}
    for case_id, rows in grouped.items():
        def score_row(row: dict[str, str]) -> tuple[float, str, str]:
            return (
                _safe_float(row.get("structural_selector_score"), default=float("-inf")),
                _stringify(row.get("candidate_answer")),
                _stringify(row.get("group_key")),
            )

        best = max(rows, key=score_row)
        candidate_rows = sorted(rows, key=lambda row: (-_safe_float(row.get("structural_selector_score")), _stringify(row.get("candidate_answer")), _stringify(row.get("group_key"))))
        out[case_id] = {
            "source_path": str(structural_csv),
            "row_count": len(rows),
            "top_candidate": _jsonable(best),
            "candidate_rows": [_jsonable(row) for row in candidate_rows[:5]],
            "target_tuple": _maybe_parse_jsonish(best.get("target_tuple")),
            "entity_unit_ledger_proxy": _maybe_parse_jsonish(best.get("entity_unit_ledger_proxy")),
            "final_answer_role": _stringify(best.get("final_answer_role")),
            "last_operation_family": _stringify(best.get("last_operation_family")),
            "target_alignment_score": _safe_float(best.get("target_alignment_score"), 0.0),
            "intermediate_answer_penalty": _safe_float(best.get("intermediate_answer_penalty"), 0.0),
            "duplicate_wrong_signature": _stringify(best.get("duplicate_wrong_signature")),
            "structural_selector_score": _safe_float(best.get("structural_selector_score"), 0.0),
        }
    return out, structural_csv


def _load_failure_map(path: Path) -> dict[str, dict[str, Any]]:
    return _load_case_map(_read_csv_rows(path))


def _load_gold_absent_map(path: Path) -> dict[str, dict[str, Any]]:
    return _load_case_map(_read_csv_rows(path))


def _load_anchor_map(path: Path) -> dict[str, dict[str, Any]]:
    return _load_case_map(_read_csv_rows(path))


def _load_target_audit_map(path: Path) -> dict[str, dict[str, Any]]:
    return _load_jsonl_case_map(path)


def _normalize_local_path(path_text: str) -> Path | None:
    text = _stringify(path_text)
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _load_optional_csv_case_map(path: Path, *, key_field: str = "case_id") -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    return _load_case_map(_read_csv_rows(path), key_field=key_field)


def _load_failure_artifact_bundle_map(failure_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    bundles: dict[str, dict[str, Any]] = {}
    for row in failure_rows:
        artifact_source = _stringify(row.get("artifact_source"))
        if not artifact_source or artifact_source in bundles:
            continue
        artifact_path = _normalize_local_path(artifact_source)
        if artifact_path is None or not artifact_path.is_file() or artifact_path.suffix.lower() != ".csv":
            bundles[artifact_source] = {}
            continue
        bundle_dir = artifact_path.parent
        bundles[artifact_source] = {
            "artifact_path": str(artifact_path),
            "result_rows": _load_optional_csv_case_map(artifact_path, key_field="example_id"),
            "selected_case_rows": _load_optional_csv_case_map(bundle_dir / "selected_cases.csv", key_field="example_id"),
            "pal_discovery_rows": _load_optional_csv_case_map(bundle_dir / "pal_discovery3_audit.csv", key_field="example_id"),
            "pal_retry_rows": _load_optional_csv_case_map(bundle_dir / "pal_retry_audit.csv", key_field="example_id"),
        }
    return bundles


def _artifact_case_context(
    artifact_bundles: dict[str, dict[str, Any]],
    *,
    artifact_source: str,
    case_id: str,
) -> dict[str, Any]:
    bundle = artifact_bundles.get(_stringify(artifact_source), {})
    if not bundle:
        return {}
    result_row = dict(bundle.get("result_rows", {}).get(case_id, {}) or {})
    selected_case_row = dict(bundle.get("selected_case_rows", {}).get(case_id, {}) or {})
    pal_discovery_row = dict(bundle.get("pal_discovery_rows", {}).get(case_id, {}) or {})
    pal_retry_row = dict(bundle.get("pal_retry_rows", {}).get(case_id, {}) or {})
    result_metadata = _maybe_parse_jsonish(result_row.get("result_metadata"))
    if not isinstance(result_metadata, dict):
        result_metadata = {}
    final_nodes = _maybe_parse_jsonish(result_row.get("final_nodes"))
    if not isinstance(final_nodes, list):
        final_nodes = []
    return {
        "artifact_path": _stringify(bundle.get("artifact_path")),
        "result_row": result_row,
        "selected_case_row": selected_case_row,
        "pal_discovery_row": pal_discovery_row,
        "pal_retry_row": pal_retry_row,
        "result_metadata": result_metadata,
        "final_nodes": final_nodes,
    }


def _coerce_string_list(value: Any) -> list[str]:
    parsed = _maybe_parse_jsonish(value)
    if isinstance(parsed, list):
        values: list[str] = []
        for item in parsed:
            if isinstance(item, dict):
                candidate = (
                    _stringify(item.get("normalized_answer"))
                    or _stringify(item.get("predicted_answer"))
                    or _stringify(item.get("candidate_answer"))
                    or _stringify(item.get("answer"))
                )
                if candidate:
                    values.append(candidate)
                continue
            text = _stringify(item)
            if text:
                values.append(text)
        return values
    text = _stringify(parsed)
    return [text] if text else []


def _coerce_support_map(value: Any) -> dict[str, float]:
    parsed = _maybe_parse_jsonish(value)
    if not isinstance(parsed, dict):
        return {}
    support_map: dict[str, float] = {}
    for key, support in parsed.items():
        key_text = _stringify(key)
        if key_text:
            support_map[key_text] = _safe_float(support, 0.0)
    return support_map


def _compact_trace_excerpt(action_trace: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for step in action_trace[:limit]:
        if not isinstance(step, dict):
            continue
        reasoning_text = _stringify(step.get("reasoning_text") or step.get("step") or step.get("response_text"))
        if len(reasoning_text) > 240:
            reasoning_text = reasoning_text[:237] + "..."
        out.append(
            {
                "branch_id": _stringify(step.get("branch_id")),
                "source": _stringify(step.get("source")),
                "action": _stringify(step.get("action")),
                "reasoning_text": reasoning_text,
                "extracted_answer": _stringify(step.get("extracted_answer") or step.get("predicted_answer")),
                "target_alignment_category": _stringify(step.get("target_alignment_category")),
            }
        )
    return out


def _action_trace_present(summary: dict[str, Any]) -> bool:
    for key, value in summary.items():
        if key == "trace_excerpt":
            if isinstance(value, list) and value:
                return True
            continue
        if _stringify(value):
            return True
    return False


def _pal_execution_present(summary: dict[str, Any]) -> bool:
    for value in summary.values():
        if isinstance(value, dict):
            if any(_stringify(inner) for inner in value.values()):
                return True
            continue
        if _stringify(value):
            return True
    return False


def _compute_packet_completeness_summary(
    case_packets: list[dict[str, Any]],
    *,
    min_completeness: float,
) -> dict[str, Any]:
    total = len(case_packets)
    subset_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def mark(subset: str, field: str, present: bool) -> None:
        subset_counts[subset]["case_count"] += 0
        if present:
            subset_counts[subset][field] += 1

    question_present = 0
    prediction_present = 0
    candidate_pool_present = 0
    action_trace_present = 0
    pal_execution_present = 0
    structural_fields_present = 0
    empty_packet_count = 0

    for packet in case_packets:
        subset = _stringify(packet.get("primary_subset")) or "unknown"
        subset_counts[subset]["case_count"] += 1

        has_question = bool(_stringify(packet.get("question")))
        has_prediction = bool(_stringify(packet.get("model_final_prediction")))
        has_candidate_pool = bool(packet.get("candidate_answers") or packet.get("candidate_answer_groups") or packet.get("selector_candidate_pool"))
        has_action_trace = _action_trace_present(packet.get("action_trace_summary") or {})
        has_pal_execution = _pal_execution_present(packet.get("pal_exec_summary") or {})
        has_structural = bool(packet.get("structural_fields"))

        question_present += int(has_question)
        prediction_present += int(has_prediction)
        candidate_pool_present += int(has_candidate_pool)
        action_trace_present += int(has_action_trace)
        pal_execution_present += int(has_pal_execution)
        structural_fields_present += int(has_structural)

        subset_counts[subset]["question_present_count"] += int(has_question)
        subset_counts[subset]["prediction_present_count"] += int(has_prediction)
        subset_counts[subset]["candidate_pool_present_count"] += int(has_candidate_pool)
        subset_counts[subset]["action_trace_present_count"] += int(has_action_trace)
        subset_counts[subset]["pal_execution_present_count"] += int(has_pal_execution)
        subset_counts[subset]["structural_fields_present_count"] += int(has_structural)

        if not any((has_question, has_prediction, has_candidate_pool, has_action_trace, has_pal_execution, has_structural)):
            empty_packet_count += 1
            subset_counts[subset]["empty_packet_count"] += 1

    def rate(count: int) -> float:
        return round(count / max(1, total), 6)

    per_subset: dict[str, dict[str, Any]] = {}
    for subset, counts in subset_counts.items():
        subset_total = counts.get("case_count", 0)
        per_subset[subset] = {
            "case_count": subset_total,
            "question_present_rate": round(counts.get("question_present_count", 0) / max(1, subset_total), 6),
            "prediction_present_rate": round(counts.get("prediction_present_count", 0) / max(1, subset_total), 6),
            "candidate_pool_present_rate": round(counts.get("candidate_pool_present_count", 0) / max(1, subset_total), 6),
            "action_trace_present_rate": round(counts.get("action_trace_present_count", 0) / max(1, subset_total), 6),
            "pal_execution_present_rate": round(counts.get("pal_execution_present_count", 0) / max(1, subset_total), 6),
            "structural_fields_present_rate": round(counts.get("structural_fields_present_count", 0) / max(1, subset_total), 6),
            "empty_packet_count": counts.get("empty_packet_count", 0),
        }

    warnings: list[str] = []
    if total:
        if rate(question_present) < min_completeness:
            warnings.append(
                f"question_present_rate={rate(question_present):.3f} is below min completeness {min_completeness:.3f}"
            )
        if rate(prediction_present) < min_completeness:
            warnings.append(
                f"prediction_present_rate={rate(prediction_present):.3f} is below min completeness {min_completeness:.3f}"
            )

    return {
        "case_count": total,
        "min_packet_completeness": round(min_completeness, 6),
        "question_present_rate": rate(question_present),
        "prediction_present_rate": rate(prediction_present),
        "candidate_pool_present_rate": rate(candidate_pool_present),
        "action_trace_present_rate": rate(action_trace_present),
        "pal_execution_present_rate": rate(pal_execution_present),
        "structural_fields_present_rate": rate(structural_fields_present),
        "empty_packet_count": empty_packet_count,
        "per_subset": per_subset,
        "warnings": warnings,
    }


def _read_case_ids_from_jsonl(path: Path) -> list[str]:
    ids: list[str] = []
    if not path.is_file():
        return ids
    for row in _read_jsonl_rows(path):
        case_id = _case_id_from_payload(row)
        if case_id:
            ids.append(case_id)
    return ids


def _select_rows_by_score(rows: list[dict[str, Any]], *, limit: int, key_fn) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=key_fn)
    if limit > 0:
        ordered = ordered[:limit]
    return ordered


def _select_pal_still_failing_case_ids(failure_rows: list[dict[str, Any]], *, limit: int = 157, method: str = DEFAULT_METHOD) -> tuple[list[str], dict[str, Any]]:
    selected = [
        row
        for row in failure_rows
        if _stringify(row.get("method_id")) == method and _stringify(row.get("evidence_completeness")).upper() == "FULL"
    ]
    selected = sorted(selected, key=lambda row: (_stringify(row.get("case_id")), _stringify(row.get("artifact_source"))))
    raw_count = len(selected)
    selected = selected[:limit] if limit > 0 else selected
    return [_stringify(row.get("case_id")) for row in selected if _stringify(row.get("case_id"))], {
        "subset": "pal_still_failing_157",
        "raw_count": raw_count,
        "selected_count": len(selected),
        "approximate": raw_count != len(selected),
        "selection_logic": "method_id == default PAL method; evidence_completeness == FULL; sorted by case_id then artifact_source; trimmed to 157 if needed",
    }


def _select_wrong_supported_consensus_case_ids(gold_rows: list[dict[str, Any]], *, limit: int = 97) -> tuple[list[str], dict[str, Any]]:
    selected = [row for row in gold_rows if _stringify(row.get("external_contrast")).lower() == "both wrong"]
    selected = sorted(
        selected,
        key=lambda row: (
            _safe_float(row.get("num_candidate_groups"), 0.0),
            _stringify(row.get("diversity_bucket")),
            _stringify(row.get("case_id")),
        ),
    )
    raw_count = len(selected)
    selected = selected[:limit] if limit > 0 else selected
    return [_stringify(row.get("case_id")) for row in selected if _stringify(row.get("case_id"))], {
        "subset": "wrong_supported_consensus_97",
        "raw_count": raw_count,
        "selected_count": len(selected),
        "approximate": raw_count != len(selected),
        "selection_logic": "gold_absent rows with external_contrast == 'Both wrong'; sorted by num_candidate_groups, diversity_bucket, case_id; trimmed to 97 if needed",
    }


def _select_direct_l1_anchor_potential_case_ids(anchor_rows: list[dict[str, Any]], *, limit: int = 43) -> tuple[list[str], dict[str, Any]]:
    selected = [row for row in anchor_rows if _is_truthy(row.get("anchor_matches_l1_max")) or _is_truthy(row.get("external_l1_exact"))]
    selected = sorted(
        selected,
        key=lambda row: (
            -int(_is_truthy(row.get("anchor_matches_l1_max"))),
            -int(_is_truthy(row.get("external_l1_exact"))),
            -int(_is_truthy(row.get("gold_recovered"))),
            -int(_is_truthy(row.get("diversity_increased"))),
            _stringify(row.get("case_id")),
        ),
    )
    raw_count = len(selected)
    selected = selected[:limit] if limit > 0 else selected
    return [_stringify(row.get("case_id")) for row in selected if _stringify(row.get("case_id"))], {
        "subset": "direct_l1_anchor_potential_43",
        "raw_count": raw_count,
        "selected_count": len(selected),
        "approximate": raw_count != len(selected),
        "selection_logic": "anchor-effect rows with anchor_matches_l1_max or external_l1_exact truthy; sorted by strong-match flags then case_id; trimmed to 43 if needed",
    }


def _select_exact_case_ids(jsonl_path: Path, subset_name: str) -> tuple[list[str], dict[str, Any]]:
    case_ids = _read_case_ids_from_jsonl(jsonl_path)
    return case_ids, {
        "subset": subset_name,
        "raw_count": len(case_ids),
        "selected_count": len(case_ids),
        "approximate": False,
        "selection_logic": f"exact case ids loaded from {jsonl_path}",
    }


def _build_subset_specs(
    *,
    failure_rows: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
    anchor_rows: list[dict[str, Any]],
    diagnostic_30_jsonl: Path,
    target_staged_15_jsonl: Path,
    subsets: list[str],
) -> list[dict[str, Any]]:
    subset_specs: list[dict[str, Any]] = []
    subset_set = {subset.strip() for subset in subsets if subset.strip()}

    if "diagnostic_30" in subset_set:
        case_ids, meta = _select_exact_case_ids(diagnostic_30_jsonl, "diagnostic_30")
        subset_specs.append({**meta, "case_ids": case_ids})
    if "target_staged_15" in subset_set:
        case_ids, meta = _select_exact_case_ids(target_staged_15_jsonl, "target_staged_15")
        subset_specs.append({**meta, "case_ids": case_ids})
    if "pal_still_failing_157" in subset_set:
        case_ids, meta = _select_pal_still_failing_case_ids(failure_rows)
        subset_specs.append({**meta, "case_ids": case_ids})
    if "wrong_supported_consensus_97" in subset_set:
        case_ids, meta = _select_wrong_supported_consensus_case_ids(gold_rows)
        subset_specs.append({**meta, "case_ids": case_ids})
    if "direct_l1_anchor_potential_43" in subset_set:
        case_ids, meta = _select_direct_l1_anchor_potential_case_ids(anchor_rows)
        subset_specs.append({**meta, "case_ids": case_ids})

    unknown = subset_set - {spec["subset"] for spec in subset_specs}
    if unknown:
        raise ValueError(
            f"Unknown subset(s): {', '.join(sorted(unknown))}. Supported: {', '.join(DEFAULT_SUBSETS)}"
        )
    return subset_specs


def _order_case_ids_for_union(subset_specs: list[dict[str, Any]]) -> tuple[list[str], dict[str, list[dict[str, Any]]], dict[str, str]]:
    memberships: dict[str, list[dict[str, Any]]] = defaultdict(list)
    primary_subset: dict[str, str] = {}
    ordered_case_ids: list[str] = []
    seen: set[str] = set()

    priority = {subset: idx for idx, subset in enumerate(DEFAULT_SUBSETS)}
    for spec in sorted(subset_specs, key=lambda item: (priority.get(item["subset"], 999), item["subset"])):
        subset = spec["subset"]
        for rank, case_id in enumerate(spec["case_ids"], start=1):
            membership = {
                "subset": subset,
                "rank": rank,
                "approximate": bool(spec.get("approximate")),
                "selection_logic": spec.get("selection_logic", ""),
            }
            memberships[case_id].append(membership)
            if case_id not in primary_subset:
                primary_subset[case_id] = subset
            if case_id not in seen:
                seen.add(case_id)
                ordered_case_ids.append(case_id)
    return ordered_case_ids, memberships, primary_subset


def _build_case_packet(
    *,
    case_id: str,
    subset_memberships: list[dict[str, Any]],
    primary_subset: str,
    failure_map: dict[str, dict[str, Any]],
    gold_map: dict[str, dict[str, Any]],
    anchor_map: dict[str, dict[str, Any]],
    target_audit_map: dict[str, dict[str, Any]],
    structural_map: dict[str, dict[str, Any]],
    artifact_bundles: dict[str, dict[str, Any]],
    include_gold_for_labeling: bool,
) -> dict[str, Any]:
    failure_row = failure_map.get(case_id, {})
    gold_row = gold_map.get(case_id, {})
    anchor_row = anchor_map.get(case_id, {})
    target_row = target_audit_map.get(case_id, {})
    structural_row = structural_map.get(case_id, {})
    artifact_source = _stringify(failure_row.get("artifact_source"))
    artifact_context = _artifact_case_context(artifact_bundles, artifact_source=artifact_source, case_id=case_id)
    artifact_row = artifact_context.get("result_row", {})
    selected_case_row = artifact_context.get("selected_case_row", {})
    pal_discovery_row = artifact_context.get("pal_discovery_row", {})
    pal_retry_row = artifact_context.get("pal_retry_row", {})
    result_metadata = artifact_context.get("result_metadata", {})
    final_nodes = artifact_context.get("final_nodes", [])

    question = (
        _stringify(target_row.get("question"))
        or _stringify(target_row.get("problem_text"))
        or _stringify(artifact_row.get("question"))
        or _stringify(selected_case_row.get("question"))
        or _stringify(failure_row.get("problem_text"))
    )
    selected_prediction = (
        _stringify(target_row.get("selected_answer"))
        or _stringify(failure_row.get("selected_answer"))
        or _stringify(artifact_row.get("final_answer_raw"))
        or _stringify(result_metadata.get("final_answer"))
        or _stringify(artifact_row.get("repair_answer_raw"))
        or _stringify(artifact_row.get("selected_answer_raw"))
        or _stringify(target_row.get("predicted"))
        or _stringify(gold_row.get("predicted"))
    )
    reference_answer = (
        _stringify(target_row.get("gold_answer"))
        or _stringify(failure_row.get("gold_answer"))
        or _stringify(artifact_row.get("gold_answer"))
        or _stringify(selected_case_row.get("gold_answer"))
        or _stringify(gold_row.get("gold"))
    )
    answer_group_support_counts = _coerce_support_map(result_metadata.get("answer_group_support_counts"))
    selector_candidate_pool = _coerce_string_list(result_metadata.get("selector_candidate_pool"))
    if not selector_candidate_pool:
        selector_candidate_pool = _coerce_string_list(pal_discovery_row.get("pal_selector_candidate_pool_json"))
    direct_reserve_answer = _stringify(target_row.get("direct_reserve_answer")) or _stringify(result_metadata.get("direct_reserve_answer"))
    if not direct_reserve_answer:
        for attempt in result_metadata.get("direct_reserve_attempts", []) or []:
            if isinstance(attempt, dict):
                direct_reserve_answer = _stringify(attempt.get("extracted_answer") or attempt.get("predicted_answer"))
                if direct_reserve_answer:
                    break
    if not direct_reserve_answer:
        for row in final_nodes:
            if isinstance(row, dict) and "direct_reserve" in _stringify(row.get("branch_id") or row.get("source_metadata")):
                direct_reserve_answer = _stringify(row.get("predicted_answer") or row.get("trace_extracted_answer"))
                if direct_reserve_answer:
                    break
    frontier_candidate_answer = _stringify(target_row.get("frontier_answer")) or _stringify(result_metadata.get("frontier_candidate_answer"))
    if not frontier_candidate_answer:
        selector_pool_values = _coerce_string_list(result_metadata.get("selector_candidate_pool"))
        frontier_candidate_answer = selector_pool_values[0] if selector_pool_values else ""

    candidate_answers: list[str] = []
    candidate_groups: list[dict[str, Any]] = []
    if isinstance(target_row.get("candidate_answers"), list):
        candidate_answers.extend(_stringify(value) for value in target_row.get("candidate_answers", []) if _stringify(value))
    if isinstance(target_row.get("candidate_sources"), list):
        sources = [value for value in target_row.get("candidate_sources", []) if _stringify(value)]
    else:
        sources = []
    candidate_support_counts = target_row.get("candidate_support_counts")
    if isinstance(candidate_support_counts, dict):
        for candidate, support in candidate_support_counts.items():
            if _stringify(candidate):
                candidate_groups.append(
                    {
                        "candidate_answer": _stringify(candidate),
                        "support_count": _safe_float(support, 0.0),
                        "source_family": "",
                    }
                )
    if answer_group_support_counts:
        for candidate, support in answer_group_support_counts.items():
            candidate_groups.append(
                {
                    "candidate_answer": candidate,
                    "support_count": support,
                    "source_family": "selector_answer_group",
                }
            )

    for key in ("direct_reserve_answer", "frontier_answer", "tiebreak_answer", "pal_answer", "selected_answer"):
        candidate = _stringify(target_row.get(key))
        if candidate:
            candidate_answers.append(candidate)
    for candidate in selector_candidate_pool:
        candidate_answers.append(candidate)
    for key in ("final_answer_raw", "repair_answer_raw", "controller_final_answer_raw"):
        candidate = _stringify(artifact_row.get(key))
        if candidate:
            candidate_answers.append(candidate)
    for key in ("direct_reserve_answer", "frontier_candidate_answer", "pal_candidate_answer", "pal_answer", "final_answer"):
        candidate = _stringify(result_metadata.get(key))
        if candidate:
            candidate_answers.append(candidate)
    for row in final_nodes:
        if not isinstance(row, dict):
            continue
        candidate = _stringify(row.get("predicted_answer") or row.get("trace_extracted_answer"))
        if candidate:
            candidate_answers.append(candidate)
    for candidate in _coerce_string_list(pal_discovery_row.get("pal_final_nodes_normalized_answers_json")):
        candidate_answers.append(candidate)
    if structural_row:
        top_candidate = structural_row.get("top_candidate", {})
        if isinstance(top_candidate, dict):
            candidate = _stringify(top_candidate.get("candidate_answer"))
            if candidate:
                candidate_answers.append(candidate)
        for row in structural_row.get("candidate_rows", []):
            if isinstance(row, dict):
                candidate = _stringify(row.get("candidate_answer"))
                if candidate:
                    candidate_answers.append(candidate)
                candidate_groups.append(
                    {
                        "group_key": _stringify(row.get("group_key")),
                        "candidate_answer": candidate,
                        "source_family": _stringify(row.get("source_family")),
                        "candidate_role": _stringify(row.get("candidate_role")),
                        "support_count": _safe_float(row.get("support_count"), 0.0),
                        "candidate_pool_size": _safe_float(row.get("candidate_pool_size"), 0.0),
                        "structural_selector_score": _safe_float(row.get("structural_selector_score"), 0.0),
                    }
                )
    candidate_answers = sorted(dict.fromkeys([cand for cand in candidate_answers if cand]))
    candidate_groups = sorted(
        {json.dumps(group, sort_keys=True): group for group in candidate_groups}.values(),
        key=lambda row: (
            -_safe_float(row.get("structural_selector_score"), 0.0),
            _stringify(row.get("candidate_answer")),
            _stringify(row.get("group_key")),
        ),
    )

    selector_metadata = {
        "selected_answer": selected_prediction,
        "selected_source": (
            _stringify(target_row.get("selected_source"))
            or _stringify(failure_row.get("selected_source"))
            or _stringify(artifact_row.get("final_answer_source"))
            or _stringify(pal_retry_row.get("retry_selected_source"))
        ),
        "structural_commit_reason": _stringify(target_row.get("structural_commit_reason")),
        "direct_reserve_answer": direct_reserve_answer,
        "frontier_answer": frontier_candidate_answer,
        "tiebreak_answer": _stringify(target_row.get("tiebreak_answer")),
        "correct_alternate_available": _stringify(target_row.get("correct_alternate_available")),
        "gold_present_in_candidate_pool": _stringify(target_row.get("gold_present_in_candidate_pool")),
        "selector_candidate_pool_size": len(selector_candidate_pool),
        "answer_group_support_counts": answer_group_support_counts,
    }
    action_trace = result_metadata.get("action_trace")
    if not isinstance(action_trace, list):
        action_trace = result_metadata.get("frontier_candidate_metadata", {}).get("action_trace") if isinstance(result_metadata.get("frontier_candidate_metadata"), dict) else []
    if not isinstance(action_trace, list):
        action_trace = []
    action_trace_summary = {
        "failure_family": _stringify(failure_row.get("failure_family")) or _stringify(target_row.get("failure_category")) or _stringify(artifact_row.get("failure_tag")),
        "failure_category": _stringify(target_row.get("failure_category")),
        "latest_method_failure_tag": _stringify(target_row.get("latest_method_failure_tag")) or _stringify(artifact_row.get("failure_tag")),
        "selection_reason": _stringify(target_row.get("selection_reason")) or _stringify(failure_row.get("notes")) or _stringify(result_metadata.get("override_reason")),
        "short_diagnosis": _stringify(target_row.get("short_diagnosis")),
        "likely_mismatch_subtype": _stringify(target_row.get("likely_mismatch_subtype")),
        "final_answer_source": _stringify(artifact_row.get("final_answer_source")),
        "frontier_candidate_maturity": _stringify(result_metadata.get("frontier_candidate_maturity")),
        "frontier_candidate_support": _stringify(result_metadata.get("frontier_candidate_support")),
        "selector_candidate_pool_size": _stringify(result_metadata.get("selector_candidate_pool_size")),
        "action_trace_step_count": len(action_trace),
        "trace_excerpt": _compact_trace_excerpt(action_trace),
    }
    pal_execution = result_metadata.get("pal_execution_result")
    if not isinstance(pal_execution, dict):
        pal_execution = result_metadata.get("pal_execution") if isinstance(result_metadata.get("pal_execution"), dict) else {}
    pal_execution_status = _stringify(target_row.get("pal_execution_status"))
    if not pal_execution_status and pal_execution:
        if _is_truthy(pal_execution.get("pal_exec_ok")):
            pal_execution_status = "success"
        elif _stringify(pal_execution.get("pal_error_type")) or _stringify(pal_execution.get("pal_error_message_sanitized")):
            pal_execution_status = "error"
    pal_exec_summary = {
        "pal_answer": _stringify(target_row.get("pal_answer")) or _stringify(result_metadata.get("pal_candidate_answer")) or _stringify(result_metadata.get("pal_answer")),
        "pal_execution_status": pal_execution_status,
        "pal_stdout": _stringify(target_row.get("pal_stdout")) or _stringify(pal_execution.get("pal_stdout")),
        "pal_code": _stringify(target_row.get("pal_code")),
        "pal_parse_ok": _stringify(pal_execution.get("pal_parse_ok")),
        "pal_safety_ok": _stringify(pal_execution.get("pal_safety_ok")),
        "pal_exec_ok": _stringify(pal_execution.get("pal_exec_ok")),
        "pal_error_type": _stringify(pal_execution.get("pal_error_type")),
        "pal_error_message": _stringify(pal_execution.get("pal_error_message_sanitized")),
        "pal_retry_reason": _stringify(pal_retry_row.get("pal_retry_reason")),
        "retry_selected_source": _stringify(pal_retry_row.get("retry_selected_source")),
    }
    failure_audit_labels = {
        "question_type": _stringify(gold_row.get("question_type")),
        "error_type": _stringify(gold_row.get("error_type")),
        "num_candidate_groups": _safe_float(gold_row.get("num_candidate_groups"), 0.0),
        "diversity_bucket": _stringify(gold_row.get("diversity_bucket")),
        "external_contrast": _stringify(gold_row.get("external_contrast")),
        "candidate_pool_status": _stringify(target_row.get("gold_present_in_candidate_pool")) or _stringify(gold_row.get("external_contrast")),
        "direct_l1_anchor_potential": int(_is_truthy(anchor_row.get("anchor_matches_l1_max")) or _is_truthy(anchor_row.get("external_l1_exact"))),
        "anchor_matches_l1_max": int(_is_truthy(anchor_row.get("anchor_matches_l1_max"))),
        "external_l1_exact": int(_is_truthy(anchor_row.get("external_l1_exact"))),
        "gold_recovered": int(_is_truthy(anchor_row.get("gold_recovered"))),
        "diversity_increased": int(_is_truthy(anchor_row.get("diversity_increased"))),
        "distance_bucket": _stringify(gold_row.get("distance_bucket")),
        "rel_error": _stringify(gold_row.get("rel_error")),
    }
    structural_fields = dict(structural_row)

    packet = {
        "case_id": case_id,
        "primary_subset": primary_subset,
        "subset_memberships": subset_memberships,
        "question": question,
        "model_final_prediction": selected_prediction,
        "candidate_answers": candidate_answers,
        "candidate_answer_groups": candidate_groups,
        "answer_group_support_counts": answer_group_support_counts,
        "selector_candidate_pool": selector_candidate_pool,
        "direct_reserve_answer": direct_reserve_answer,
        "frontier_candidate_answer": frontier_candidate_answer,
        "selector_metadata": selector_metadata,
        "action_trace_summary": action_trace_summary,
        "pal_exec_summary": pal_exec_summary,
        "structural_fields": structural_fields,
        "failure_audit_labels": failure_audit_labels,
        "source_artifacts": {
            "failure_csv": artifact_source,
            "target_audit_jsonl": _stringify(target_row.get("source_artifact_path")),
            "structural_csv": _stringify(structural_row.get("source_path")),
            "artifact_bundle": _stringify(artifact_context.get("artifact_path")),
            "exact_subset_sources": [membership.get("subset") for membership in subset_memberships if membership.get("subset") in {"diagnostic_30", "target_staged_15"}],
        },
        "internal_scoring_metadata": {
            "gold_answer": reference_answer,
        },
        "prompt_template_id": DEFAULT_PROMPT_TEMPLATE_ID,
        "include_gold_for_labeling": bool(include_gold_for_labeling),
        "gold_assisted": bool(include_gold_for_labeling),
    }
    if include_gold_for_labeling and reference_answer:
        packet["reference_answer"] = reference_answer
    return packet


def _build_prompt_payload(packet: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "case_id": packet["case_id"],
        "question": packet.get("question", ""),
        "model_final_prediction": packet.get("model_final_prediction", ""),
        "candidate_answers": packet.get("candidate_answers", []),
        "candidate_answer_groups": packet.get("candidate_answer_groups", []),
        "answer_group_support_counts": packet.get("answer_group_support_counts", {}),
        "selector_candidate_pool": packet.get("selector_candidate_pool", []),
        "direct_reserve_answer": packet.get("direct_reserve_answer", ""),
        "frontier_candidate_answer": packet.get("frontier_candidate_answer", ""),
        "selector_metadata": packet.get("selector_metadata", {}),
        "action_trace_summary": packet.get("action_trace_summary", {}),
        "pal_exec_summary": packet.get("pal_exec_summary", {}),
        "structural_fields": packet.get("structural_fields", {}),
        "failure_audit_labels": packet.get("failure_audit_labels", {}),
        "prompt_template_id": packet.get("prompt_template_id", DEFAULT_PROMPT_TEMPLATE_ID),
        "primary_subset": packet.get("primary_subset", ""),
        "subset_memberships": packet.get("subset_memberships", []),
    }
    if packet.get("include_gold_for_labeling") and packet.get("reference_answer"):
        payload["reference_answer"] = packet["reference_answer"]
    return payload


def _render_prompt(packet: dict[str, Any]) -> str:
    payload = _build_prompt_payload(packet)
    prompt_lines = [
        "You are labeling PAL failure mechanisms from trace-grounded evidence.",
        "Return JSON only. Do not use any reference answer or label metadata beyond the packet.",
        "",
        "Return exactly these keys:",
        ", ".join(LABEL_FIELDS),
        "",
        "Allowed label values:",
        f"- primary_label: {', '.join(sorted(PRIMARY_LABELS))}",
        f"- secondary_labels: list of primary_label values",
        f"- selector_vs_generation: {', '.join(sorted(SELECTOR_VS_GENERATION))}",
        f"- candidate_pool_status: {', '.join(sorted(POOL_STATUS))}",
        f"- recommended_fix_family: {', '.join(sorted(FIX_FAMILIES))}",
        "",
        "Evidence packet:",
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        "",
        "Rules:",
        "- Keep the answer short and trace-grounded.",
        "- Set confidence to a number between 0 and 1.",
        "- Secondary labels must be a JSON array.",
        "- If evidence is sparse, use metadata_insufficient or unknown where appropriate.",
    ]
    return "\n".join(prompt_lines).rstrip() + "\n"


def _parse_label_json(text: str) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(text)
    except Exception as exc:
        return None, f"json_parse_error:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return None, "json_not_object"

    normalized = {
        "case_id": _stringify(payload.get("case_id")),
        "primary_label": _stringify(payload.get("primary_label")),
        "secondary_labels": [_stringify(item) for item in (payload.get("secondary_labels") or []) if _stringify(item)],
        "selector_vs_generation": _stringify(payload.get("selector_vs_generation")),
        "candidate_pool_status": _stringify(payload.get("candidate_pool_status")),
        "confidence": _safe_float(payload.get("confidence"), default=-1.0),
        "evidence": _stringify(payload.get("evidence")),
        "recommended_fix_family": _stringify(payload.get("recommended_fix_family")),
    }

    errors: list[str] = []
    if normalized["primary_label"] not in PRIMARY_LABELS:
        errors.append("invalid_primary_label")
    if any(label not in SECONDARY_LABELS for label in normalized["secondary_labels"]):
        errors.append("invalid_secondary_label")
    if normalized["selector_vs_generation"] not in SELECTOR_VS_GENERATION:
        errors.append("invalid_selector_vs_generation")
    if normalized["candidate_pool_status"] not in POOL_STATUS:
        errors.append("invalid_candidate_pool_status")
    if normalized["recommended_fix_family"] not in FIX_FAMILIES:
        errors.append("invalid_recommended_fix_family")
    if not (0.0 <= normalized["confidence"] <= 1.0):
        errors.append("invalid_confidence")
    if not normalized["evidence"]:
        errors.append("missing_evidence")

    normalized["secondary_labels"] = sorted(dict.fromkeys(normalized["secondary_labels"]))
    normalized["label_valid"] = not errors
    normalized["label_errors"] = errors
    return normalized, ""


def _load_cohere_client() -> Any:
    import cohere  # type: ignore

    api_key = os.getenv("COHERE_API_KEY", "").strip() or os.getenv("CO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("COHERE_API_KEY (or CO_API_KEY) is not set; cannot run with --allow-api.")
    if hasattr(cohere, "ClientV2"):
        return cohere.ClientV2(api_key=api_key)
    return cohere.Client(api_key)


def _load_openai_client() -> Any:
    from openai import OpenAI  # type: ignore

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set; cannot run with --allow-api.")
    return OpenAI(api_key=api_key)


def _response_choices(response: Any) -> list[Any]:
    if isinstance(response, dict):
        choices = response.get("choices")
        return choices if isinstance(choices, list) else []
    choices = getattr(response, "choices", [])
    return choices if isinstance(choices, list) else []


def _choice_message_content(choice: Any) -> Any:
    if isinstance(choice, dict):
        message = choice.get("message")
        if isinstance(message, dict):
            return message.get("content", "")
        return ""
    message = getattr(choice, "message", None)
    if message is None:
        return ""
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", "")


def _extract_response_finish_reason(response: Any) -> str:
    choices = _response_choices(response)
    if not choices:
        return ""
    choice = choices[0]
    if isinstance(choice, dict):
        return _stringify(choice.get("finish_reason"))
    return _stringify(getattr(choice, "finish_reason", ""))


def _response_json_preview(response: Any, *, max_len: int = 1200) -> str:
    if response is None:
        return ""
    try:
        if isinstance(response, (dict, list)):
            return _sanitize_error_message(json.dumps(response, ensure_ascii=False, sort_keys=True), max_len=max_len)
    except Exception:
        pass
    return _sanitize_error_message(_stringify(response), max_len=max_len)


def _extract_openai_text(response: Any) -> str:
    choices = _response_choices(response)
    if not choices:
        return ""
    content = _choice_message_content(choices[0])
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text:
                parts.append(str(text))
            elif isinstance(item, dict):
                text_value = item.get("text")
                if text_value:
                    parts.append(str(text_value))
                elif item.get("type") == "text" and item.get("content"):
                    parts.append(str(item["content"]))
        return "".join(parts).strip()
    return _stringify(content)


def _post_json_request(
    *,
    url: str,
    api_key: str,
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read().decode("utf-8", errors="replace")
            response_headers = {key: value for key, value in response.headers.items()}
            http_status = getattr(response, "status", None) or response.getcode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        error_headers = {key: value for key, value in exc.headers.items()} if getattr(exc, "headers", None) else {}
        retry_after = error_headers.get("Retry-After") or error_headers.get("retry-after") or ""
        message = f"HTTP error from {url}: {exc.code} {detail}"
        if retry_after:
            message += f" retry_after={retry_after}"
        raise ProviderRequestError(
            message,
            url=url,
            http_status=exc.code,
            response_body=detail,
            headers=error_headers,
            retry_after=retry_after,
        ) from exc
    except urllib.error.URLError as exc:
        raise ProviderRequestError(f"Network error calling {url}: {exc}", url=url) from exc
    try:
        parsed = json.loads(payload)
    except Exception as exc:
        raise ProviderRequestError(
            f"Unable to parse JSON response from {url}",
            url=url,
            http_status=http_status,
            response_body=payload,
            headers=response_headers,
            retry_after=response_headers.get("Retry-After") or response_headers.get("retry-after") or "",
        ) from exc
    return parsed, {
        "response_http_status": http_status,
        "raw_response_body_snippet": _sanitize_error_message(payload, max_len=1200),
        "response_content_type": response_headers.get("Content-Type", ""),
        "response_finish_reason": _extract_response_finish_reason(parsed),
        "response_json_preview": _response_json_preview(parsed, max_len=1200),
        "retry_after": response_headers.get("Retry-After") or response_headers.get("retry-after") or "",
    }


def _sanitize_error_message(text: str, *, max_len: int = 500) -> str:
    clean = _stringify(text)
    for key in ("COHERE_API_KEY", "CEREBRAS_API_KEY", "FIREWORKS_API_KEY", "OPENAI_API_KEY", "CO_API_KEY", "MISTRAL_API_KEY"):
        value = os.getenv(key, "")
        if value:
            clean = clean.replace(value, "[REDACTED]")
    if len(clean) > max_len:
        clean = clean[: max_len - 3] + "..."
    return clean


def _provider_env_presence(provider: str) -> dict[str, bool]:
    return {env_name: bool(os.getenv(env_name, "").strip()) for env_name in PROVIDER_ENV_VARS.get(provider, ())}


def _provider_env_ready(provider: str) -> bool:
    presence = _provider_env_presence(provider)
    if not presence:
        return False
    return any(presence.values())


def _extract_http_status(error_text: str) -> int | None:
    match = re.search(r"\b([1-5][0-9]{2})\b", error_text or "")
    if match:
        try:
            return int(match.group(1))
        except Exception:
            return None
    return None


def _extract_error_code(error_text: str) -> str:
    text = error_text or ""
    for pattern in (
        r"error code:\s*([A-Z0-9_\-]+)",
        r'"code"\s*:\s*"([^"]+)"',
        r"code\s*[:=]\s*([A-Z0-9_\-]+)",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _stringify(match.group(1))
    return ""


def _extract_retry_after(error_text: str) -> str:
    match = re.search(r"retry_after\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)", error_text or "", flags=re.IGNORECASE)
    if match:
        return _stringify(match.group(1))
    return ""


def _short_error_message(error_text: str, *, max_len: int = 220) -> str:
    clean = _sanitize_error_message(error_text, max_len=1000)
    if "HTTP error from " in clean:
        clean = clean.split(": ", 1)[-1]
    clean = re.sub(r"[\r\n\t]+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[: max_len - 3] + "..."
    return clean


def _classify_provider_readiness(*, label_status: str, api_error: str = "", label_parse_error: str = "") -> str:
    status = _stringify(label_status).lower()
    if status == "parsed":
        return "ready"
    if status == "dry_run":
        return "dry_run"
    if status == "config_check":
        return "config_check"
    if status == "parse_error" or _stringify(label_parse_error):
        return "parse_error"

    text = _stringify(api_error).lower()
    http_status = _extract_http_status(text)
    if http_status in {401, 403} or any(token in text for token in ("unauthorized", "forbidden", "invalid api key", "1010")):
        return "auth_error"
    if http_status == 429 or any(token in text for token in ("rate limit", "too many requests", "quota")):
        return "rate_limited"
    if http_status == 404 or any(token in text for token in ("not found", "not deployed", "inaccessible")):
        return "model_not_found"
    return "unknown_error"


def _provider_error_details(*, label_status: str, api_error: str = "", label_parse_error: str = "") -> dict[str, Any]:
    readiness = _classify_provider_readiness(label_status=label_status, api_error=api_error, label_parse_error=label_parse_error)
    if readiness == "ready":
        return {
            "provider_readiness": readiness,
            "provider_http_status": None,
            "provider_error_code": "",
            "provider_error_message_short": "",
            "provider_retry_after": "",
        }
    short_message = _short_error_message(api_error or label_parse_error or label_status)
    return {
        "provider_readiness": readiness,
        "provider_http_status": _extract_http_status(api_error),
        "provider_error_code": _extract_error_code(api_error),
        "provider_error_message_short": short_message,
        "provider_retry_after": _extract_retry_after(api_error),
    }


def _provider_config_summary(*, providers: list[str], provider_models: dict[str, str]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for provider in providers:
        env_presence = _provider_env_presence(provider)
        model = _stringify(provider_models.get(provider))
        model_required = provider in {"openai", "cerebras", "fireworks", "mistral"}
        summary[provider] = {
            "selected": True,
            "model": model,
            "model_required": model_required,
            "env_presence": env_presence,
            "env_ready": _provider_env_ready(provider),
            "model_ready": bool(model),
            "config_ready": bool(model) and _provider_env_ready(provider),
        }
    return summary


def _provider_readiness_summary(parsed_rows: list[dict[str, Any]], providers: list[str]) -> dict[str, Any]:
    provider_counts: dict[str, Counter[str]] = {provider: Counter() for provider in providers}
    provider_errors: dict[str, list[dict[str, Any]]] = {provider: [] for provider in providers}
    for row in parsed_rows:
        provider = _stringify(row.get("provider"))
        if provider not in provider_counts:
            continue
        readiness = _stringify(row.get("provider_readiness")) or _classify_provider_readiness(
            label_status=_stringify(row.get("label_status")),
            api_error=_stringify(row.get("api_error")),
            label_parse_error=_stringify(row.get("label_parse_error")),
        )
        provider_counts[provider][readiness] += 1
        if readiness != "ready":
            provider_errors[provider].append(
                {
                    "case_id": _stringify(row.get("case_id")),
                    "request_id": _stringify(row.get("request_id")),
                    "label_status": _stringify(row.get("label_status")),
                    "provider_readiness": readiness,
                    "provider_http_status": row.get("provider_http_status"),
                    "provider_error_code": _stringify(row.get("provider_error_code")),
                    "provider_error_message_short": _stringify(row.get("provider_error_message_short")),
                    "provider_retry_after": _stringify(row.get("provider_retry_after")),
                }
            )
    return {
        "provider_readiness_counts": {provider: dict(sorted(counter.items(), key=lambda item: (-item[1], item[0]))) for provider, counter in provider_counts.items()},
        "provider_error_samples": {provider: errors[:5] for provider, errors in provider_errors.items() if errors},
    }


def _build_pattern_case_packet(packet: dict[str, Any]) -> dict[str, Any]:
    compact = {key: _jsonable(packet.get(key)) for key in PATTERN_DISCOVERY_CASE_KEYS}
    compact["structural_fields"] = compact.get("structural_fields", {})
    compact["candidate_answer_groups"] = compact.get("candidate_answer_groups", [])[:5]
    compact["candidate_answers"] = compact.get("candidate_answers", [])[:8]
    compact["subset_memberships"] = compact.get("subset_memberships", [])
    audit = compact.get("failure_audit_labels", {})
    if isinstance(audit, dict):
        sanitized_audit: dict[str, Any] = {}
        for key, value in audit.items():
            key_text = _stringify(key)
            if "gold" in key_text.lower():
                continue
            if isinstance(value, str):
                value = value.replace("gold_absent", "reference_absent").replace("gold_present", "reference_present")
            sanitized_audit[key_text] = value
        compact["failure_audit_labels"] = sanitized_audit
    return compact


def _sanitize_pattern_prompt_key(key: Any) -> str:
    text = _stringify(key)
    if not text:
        return text
    sanitized = text
    replacements = (
        ("gold_answer", "reference_answer"),
        ("answer_key", "reference_label"),
        ("gold_present", "reference_present"),
        ("gold_absent", "reference_absent"),
        ("gold", "reference"),
    )
    for needle, replacement in replacements:
        sanitized = sanitized.replace(needle, replacement)
        sanitized = sanitized.replace(needle.upper(), replacement.upper())
        sanitized = sanitized.replace(needle.title(), replacement.title())
    return sanitized


def _sanitize_pattern_prompt_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized_dict: dict[str, Any] = {}
        for key, inner_value in value.items():
            sanitized_key = _sanitize_pattern_prompt_key(key)
            if not sanitized_key:
                continue
            sanitized_dict[sanitized_key] = _sanitize_pattern_prompt_value(inner_value)
        return sanitized_dict
    if isinstance(value, list):
        return [_sanitize_pattern_prompt_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_pattern_prompt_value(item) for item in value]
    if isinstance(value, str):
        sanitized = value
        replacements = (
            ("gold_answer", "reference_answer"),
            ("answer_key", "reference_label"),
            ("gold_present", "reference_present"),
            ("gold_absent", "reference_absent"),
            ("gold", "reference"),
        )
        for needle, replacement in replacements:
            sanitized = sanitized.replace(needle, replacement)
            sanitized = sanitized.replace(needle.upper(), replacement.upper())
            sanitized = sanitized.replace(needle.title(), replacement.title())
        return sanitized
    return value


def _build_pattern_batch_id(*, provider: str, case_packets: list[dict[str, Any]]) -> str:
    case_ids = [packet["case_id"] for packet in case_packets]
    case_digest = _sha256_text("|".join(case_ids))[:12] if case_ids else "empty"
    return f"{provider}:{len(case_ids)}:{case_digest}"


def _build_pattern_batch_packet(
    *,
    provider: str,
    model: str,
    batch_id: str,
    case_packets: list[dict[str, Any]],
    include_gold_for_labeling: bool,
) -> dict[str, Any]:
    compact_cases = [_build_pattern_case_packet(packet) for packet in case_packets]
    batch_packet = {
        "provider": provider,
        "model": model,
        "batch_id": batch_id,
        "cases_reviewed": [packet["case_id"] for packet in case_packets],
        "case_count": len(case_packets),
        "cases": compact_cases,
        "mode": "pattern_discovery",
        "prompt_template_id": "failure_mechanism_multi_api_pattern_v1",
        "include_gold_for_labeling": bool(include_gold_for_labeling),
        "gold_assisted": bool(include_gold_for_labeling),
        "non_cohere_policy": "Allowed only for pattern discovery, not for algorithm comparison.",
        "not_accuracy_comparison": True,
    }
    return batch_packet


def _render_pattern_prompt(batch_packet: dict[str, Any]) -> str:
    payload = _sanitize_pattern_prompt_value(
        {
        "provider": batch_packet.get("provider", ""),
        "model": batch_packet.get("model", ""),
        "batch_id": batch_packet.get("batch_id", ""),
        "cases_reviewed": batch_packet.get("cases_reviewed", []),
        "case_count": batch_packet.get("case_count", 0),
        "cases": batch_packet.get("cases", []),
        "mode": "pattern_discovery",
        }
    )
    prompt_lines = [
        "You are discovering recurring detailed failure patterns inside a batch of PAL failure traces.",
        "This is not an accuracy comparison.",
        "OpenAI, Cohere, Cerebras, Fireworks, and Mistral are allowed only for pattern discovery, not for algorithm comparison.",
        "Return exactly one JSON object and nothing else.",
        "Do not emit markdown, code fences, preambles, or trailing prose.",
        "Do not use reference-answer information or hidden labels unless explicitly present in the batch packet; by default they are absent.",
        "Report observed patterns, not just inferred reasons.",
        "Distinguish supporting cases from negative or uncertain cases.",
        "Every pattern must cite case IDs and trace-grounded evidence.",
        "",
        "Return exactly this JSON schema:",
        json.dumps(
            {
                "provider": "openai|cohere|cerebras|fireworks|mistral",
                "model": "string",
                "batch_id": "string",
                "cases_reviewed": ["case_id"],
                "top_patterns": [
                    {
                        "pattern_name": "string",
                        "description": "string",
                        "supporting_case_ids": ["case_id"],
                        "negative_or_uncertain_case_ids": ["case_id"],
                        "confidence": 0.0,
                        "evidence_summary": "short trace-grounded explanation",
                        "likely_failure_stage": "target_extraction|relation_mapping|operator_choice|PAL_grounding|candidate_generation|selector|metadata|unknown",
                    }
                ],
                "recommended_taxonomy_changes": ["string"],
                "what_extra_metadata_is_needed": ["string"],
                "do_not_claim": ["string"],
            },
            indent=2,
            sort_keys=True,
        ),
        "",
        "Batch packet:",
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        "",
        "Rules:",
        "- Focus on recurring detailed patterns within the batch.",
        "- Provide short, trace-grounded evidence summaries.",
        "- Confidence must be a number between 0 and 1.",
        "- Use negative_or_uncertain_case_ids when a case weakens or does not clearly support the pattern.",
        "- Do not present this as an accuracy comparison or benchmark ranking.",
    ]
    return "\n".join(prompt_lines).rstrip() + "\n"


def _parse_pattern_discovery_json(text: str) -> tuple[dict[str, Any] | None, str]:
    payload, parse_error = _parse_json_object_with_fallback(text)
    if payload is None:
        return None, parse_error
    if not isinstance(payload, dict):
        return None, "json_not_object"

    normalized_patterns: list[dict[str, Any]] = []
    raw_patterns = payload.get("top_patterns") or []
    if not isinstance(raw_patterns, list):
        return None, "invalid_top_patterns"

    for item in raw_patterns:
        if not isinstance(item, dict):
            return None, "invalid_pattern_item"
        normalized_patterns.append(
            {
                "pattern_name": _stringify(item.get("pattern_name")),
                "description": _stringify(item.get("description")),
                "supporting_case_ids": sorted({_stringify(case_id) for case_id in (item.get("supporting_case_ids") or []) if _stringify(case_id)}),
                "negative_or_uncertain_case_ids": sorted({_stringify(case_id) for case_id in (item.get("negative_or_uncertain_case_ids") or []) if _stringify(case_id)}),
                "confidence": _safe_float(item.get("confidence"), default=-1.0),
                "evidence_summary": _stringify(item.get("evidence_summary")),
                "likely_failure_stage": _stringify(item.get("likely_failure_stage")),
            }
        )

    normalized = {
        "provider": _stringify(payload.get("provider")),
        "model": _stringify(payload.get("model")),
        "batch_id": _stringify(payload.get("batch_id")),
        "cases_reviewed": sorted({_stringify(case_id) for case_id in (payload.get("cases_reviewed") or []) if _stringify(case_id)}),
        "top_patterns": normalized_patterns,
        "recommended_taxonomy_changes": [_stringify(item) for item in (payload.get("recommended_taxonomy_changes") or []) if _stringify(item)],
        "what_extra_metadata_is_needed": [_stringify(item) for item in (payload.get("what_extra_metadata_is_needed") or []) if _stringify(item)],
        "do_not_claim": [_stringify(item) for item in (payload.get("do_not_claim") or []) if _stringify(item)],
    }

    errors: list[str] = []
    if normalized["provider"] not in SUPPORTED_PROVIDERS:
        errors.append("invalid_provider")
    if not normalized["model"]:
        errors.append("missing_model")
    if not normalized["batch_id"]:
        errors.append("missing_batch_id")
    if not normalized["cases_reviewed"]:
        errors.append("missing_cases_reviewed")
    for pattern in normalized_patterns:
        if not pattern["pattern_name"]:
            errors.append("missing_pattern_name")
        if not pattern["description"]:
            errors.append("missing_pattern_description")
        if not pattern["evidence_summary"]:
            errors.append("missing_pattern_evidence")
        if pattern["likely_failure_stage"] not in PATTERN_FAILURE_STAGES:
            errors.append("invalid_likely_failure_stage")
        if not (0.0 <= pattern["confidence"] <= 1.0):
            errors.append("invalid_pattern_confidence")
    normalized["pattern_valid"] = not errors
    normalized["pattern_errors"] = errors
    normalized["label_valid"] = not errors
    normalized["label_errors"] = errors
    return normalized, ""


def _summarize_pattern_discovery(parsed_rows: list[dict[str, Any]], providers: list[str]) -> dict[str, Any]:
    provider_pattern_name_counts: dict[str, Counter[str]] = {provider: Counter() for provider in providers}
    provider_supporting_counts: dict[str, Counter[str]] = {provider: Counter() for provider in providers}
    provider_stage_counts: dict[str, Counter[str]] = {provider: Counter() for provider in providers}
    provider_ambiguous_case_ids: dict[str, set[str]] = {provider: set() for provider in providers}
    provider_hypothesis_names: dict[str, set[str]] = {provider: set() for provider in providers}
    global_pattern_name_to_providers: dict[str, set[str]] = defaultdict(set)

    for row in parsed_rows:
        provider = _stringify(row.get("provider"))
        if provider not in provider_pattern_name_counts:
            continue
        if not row.get("label_valid"):
            continue
        for pattern in row.get("top_patterns", []) or []:
            if not isinstance(pattern, dict):
                continue
            name = _stringify(pattern.get("pattern_name"))
            stage = _stringify(pattern.get("likely_failure_stage")) or "unknown"
            support_ids = [_stringify(case_id) for case_id in (pattern.get("supporting_case_ids") or []) if _stringify(case_id)]
            ambiguous_ids = [_stringify(case_id) for case_id in (pattern.get("negative_or_uncertain_case_ids") or []) if _stringify(case_id)]
            if name:
                provider_pattern_name_counts[provider][name] += 1
                provider_supporting_counts[provider][name] += len(support_ids)
                provider_hypothesis_names[provider].add(name)
                global_pattern_name_to_providers[name].add(provider)
            provider_stage_counts[provider][stage] += 1
            provider_ambiguous_case_ids[provider].update(ambiguous_ids)

    stage_distribution = {
        provider: dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))
        for provider, counter in provider_stage_counts.items()
    }
    unique_hypotheses = {
        provider: sorted(
            name for name in provider_hypothesis_names[provider] if global_pattern_name_to_providers.get(name) == {provider}
        )
        for provider in providers
    }

    return {
        "provider_pattern_name_counts": {provider: dict(sorted(counter.items(), key=lambda item: (-item[1], item[0]))) for provider, counter in provider_pattern_name_counts.items()},
        "provider_supporting_case_counts": {provider: dict(sorted(counter.items(), key=lambda item: (-item[1], item[0]))) for provider, counter in provider_supporting_counts.items()},
        "provider_likely_failure_stage_distribution": stage_distribution,
        "provider_ambiguous_case_ids": {provider: sorted(case_ids) for provider, case_ids in provider_ambiguous_case_ids.items()},
        "provider_unique_hypotheses": unique_hypotheses,
        "provider_total_pattern_rows": {
            provider: sum(provider_pattern_name_counts[provider].values()) for provider in providers
        },
    }


def _strip_code_fences(text: str) -> str:
    stripped = _stringify(text)
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _parse_json_object_with_fallback(text: str) -> tuple[dict[str, Any] | None, str]:
    candidate = _strip_code_fences(text)
    if not candidate:
        return None, "json_parse_error:empty_response"
    try:
        payload = json.loads(candidate)
        if isinstance(payload, dict):
            return payload, ""
        return None, "json_not_object"
    except Exception as exc:
        direct_error = f"json_parse_error:{type(exc).__name__}"

    decoder = json.JSONDecoder()
    search_space = candidate
    start = search_space.find("{")
    while start != -1:
        try:
            payload, _ = decoder.raw_decode(search_space[start:])
        except json.JSONDecodeError:
            start = search_space.find("{", start + 1)
            continue
        if isinstance(payload, dict):
            return payload, ""
        start = search_space.find("{", start + 1)
    return None, direct_error


def _provider_hypothesis_snapshots(parsed_rows: list[dict[str, Any]], providers: list[str]) -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for provider in providers:
        rows = [row for row in parsed_rows if _stringify(row.get("provider")) == provider]
        valid_rows = [row for row in rows if row.get("label_valid")]
        if valid_rows:
            row = valid_rows[0]
            top_patterns = []
            for pattern in (row.get("top_patterns") or [])[:3]:
                if not isinstance(pattern, dict):
                    continue
                top_patterns.append(
                    {
                        "pattern_name": _stringify(pattern.get("pattern_name")),
                        "likely_failure_stage": _stringify(pattern.get("likely_failure_stage")),
                        "confidence": _safe_float(pattern.get("confidence"), 0.0),
                        "supporting_case_ids": [_stringify(case_id) for case_id in (pattern.get("supporting_case_ids") or []) if _stringify(case_id)],
                        "negative_or_uncertain_case_ids": [
                            _stringify(case_id)
                            for case_id in (pattern.get("negative_or_uncertain_case_ids") or [])
                            if _stringify(case_id)
                        ],
                    }
                )
            snapshots[provider] = {
                "available": True,
                "provider": provider,
                "model": _stringify(row.get("model")),
                "label_status": _stringify(row.get("label_status")),
                "top_patterns": top_patterns,
            }
            continue
        status_row = rows[0] if rows else {}
        snapshots[provider] = {
            "available": False,
            "provider": provider,
            "model": _stringify(status_row.get("model")),
            "label_status": _stringify(status_row.get("label_status")) or "missing",
            "provider_readiness": _stringify(status_row.get("provider_readiness")),
            "provider_error_message_short": _stringify(status_row.get("provider_error_message_short")),
            "top_patterns": [],
        }
    return snapshots


def _dominant_manual_stage(
    mismatch_counts: Counter[str],
    family_counts: Counter[str],
    theme_counts: Counter[str],
) -> str:
    mismatch_text = " ".join(mismatch_counts.keys()).lower()
    family_text = " ".join(family_counts.keys()).lower()
    if "target" in mismatch_text or "target" in family_text:
        return "target_extraction"
    if "selector" in family_text:
        return "selector"
    if theme_counts.get("ratio_percent"):
        return "relation_mapping"
    if theme_counts.get("state_transition"):
        return "operator_choice"
    return "candidate_generation"


def _build_codex_manual_hypothesis(
    *,
    trace_packets_path: Path,
    providers: list[str],
    provider_snapshots: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not trace_packets_path.is_file():
        return {
            "available": False,
            "analyst": "codex_gpt_manual",
            "reason": f"missing_trace_packets:{trace_packets_path}",
        }

    case_map: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl_rows(trace_packets_path):
        for case in row.get("cases", []) or []:
            if not isinstance(case, dict):
                continue
            case_id = _stringify(case.get("case_id"))
            if case_id and case_id not in case_map:
                case_map[case_id] = case

    if not case_map:
        return {
            "available": False,
            "analyst": "codex_gpt_manual",
            "reason": "empty_case_batch",
        }

    theme_counts: Counter[str] = Counter()
    mismatch_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    low_diversity_case_ids: list[str] = []
    theme_support_case_ids: dict[str, list[str]] = defaultdict(list)

    for case_id, case in case_map.items():
        question = _stringify(case.get("question")).lower()
        failure_audit = case.get("failure_audit_labels") or {}
        action_summary = case.get("action_trace_summary") or {}

        num_candidate_groups = _safe_float(failure_audit.get("num_candidate_groups"), 0.0)
        if num_candidate_groups <= 1.0:
            low_diversity_case_ids.append(case_id)

        mismatch = _stringify(action_summary.get("likely_mismatch_subtype"))
        family = _stringify(action_summary.get("failure_family") or action_summary.get("failure_category"))
        if mismatch:
            mismatch_counts[mismatch] += 1
        if family:
            family_counts[family] += 1

        case_themes: set[str] = set()
        if any(token in question for token in ("percent", "%", "ratio", "twice", "half", "per", "rate")):
            case_themes.add("ratio_percent")
        if any(token in question for token in ("after", "before", "remaining", "left", "now", "later", "still")):
            case_themes.add("state_transition")
        if any(token in question for token in ("difference", "more than", "less than", "how many more")):
            case_themes.add("target_difference")
        if any(token in question for token in ("total", "altogether", "combined", "in all")):
            case_themes.add("final_total_target")
        if "average" in question:
            case_themes.add("average_target")

        for theme in case_themes:
            theme_counts[theme] += 1
            theme_support_case_ids[theme].append(case_id)

    dominant_theme = theme_counts.most_common(1)[0][0] if theme_counts else "mixed"
    dominant_stage = _dominant_manual_stage(mismatch_counts, family_counts, theme_counts)
    supporting_case_ids = sorted(
        dict.fromkeys(theme_support_case_ids.get(dominant_theme, [])[:8] or low_diversity_case_ids[:8] or list(case_map.keys())[:8])
    )
    uncertain_case_ids = sorted(dict.fromkeys(case_id for case_id in case_map if case_id not in supporting_case_ids))[:8]
    low_diversity_share = len(low_diversity_case_ids) / max(1, len(case_map))
    confidence = min(
        0.85,
        round(
            0.35
            + 0.3 * (theme_counts.get(dominant_theme, 0) / max(1, len(case_map)))
            + 0.2 * low_diversity_share
            + 0.1 * (sum(mismatch_counts.values()) > 0),
            2,
        ),
    )

    description = (
        f"Manual Codex/GPT read: the batch looks dominated by a `{dominant_theme}`-flavored "
        f"`{dominant_stage}` failure, with low candidate diversity making the wrong interpretation sticky."
    )
    evidence_summary = (
        f"{theme_counts.get(dominant_theme, 0)}/{len(case_map)} cases match the dominant `{dominant_theme}` theme; "
        f"{len(low_diversity_case_ids)}/{len(case_map)} show <=1 candidate group in the audit metadata. "
        f"Top mismatch/family hints: mismatch={dict(mismatch_counts.most_common(3))}, family={dict(family_counts.most_common(3))}."
    )

    overlap_notes: list[str] = []
    for provider in providers:
        snapshot = provider_snapshots.get(provider, {})
        top_pattern = ((snapshot.get("top_patterns") or [{}])[0]) if snapshot.get("available") else {}
        pattern_name = _stringify(top_pattern.get("pattern_name"))
        if pattern_name:
            overlap_notes.append(f"{provider}: top pattern `{pattern_name}`")
        else:
            overlap_notes.append(
                f"{provider}: unavailable ({_stringify(snapshot.get('label_status')) or _stringify(snapshot.get('provider_readiness')) or 'missing'})"
            )

    return {
        "available": True,
        "analyst": "codex_gpt_manual",
        "hypothesis_name": f"{dominant_theme}_driven_{dominant_stage}",
        "description": description,
        "supporting_case_ids": supporting_case_ids,
        "negative_or_uncertain_case_ids": uncertain_case_ids,
        "confidence": confidence,
        "likely_failure_stage": dominant_stage,
        "dominant_question_themes": dict(theme_counts.most_common()),
        "dominant_mismatch_hints": dict(mismatch_counts.most_common()),
        "dominant_family_hints": dict(family_counts.most_common()),
        "evidence_summary": evidence_summary,
        "comparison_context": overlap_notes,
        "caution": "Preliminary manual hypothesis only. Do not treat this smoke as a final pattern claim or an accuracy comparison.",
    }


def _build_hypothesis_comparison(
    *,
    providers: list[str],
    provider_snapshots: dict[str, dict[str, Any]],
    codex_manual_hypothesis: dict[str, Any],
) -> dict[str, Any]:
    comparison_rows: list[dict[str, Any]] = []
    for provider in providers:
        snapshot = provider_snapshots.get(provider, {})
        comparison_rows.append(
            {
                "name": provider,
                "available": bool(snapshot.get("available")),
                "top_pattern_names": [
                    _stringify(pattern.get("pattern_name"))
                    for pattern in (snapshot.get("top_patterns") or [])
                    if _stringify(pattern.get("pattern_name"))
                ],
                "top_failure_stages": [
                    _stringify(pattern.get("likely_failure_stage"))
                    for pattern in (snapshot.get("top_patterns") or [])
                    if _stringify(pattern.get("likely_failure_stage"))
                ],
                "status": _stringify(snapshot.get("label_status")) or _stringify(snapshot.get("provider_readiness")),
            }
        )
    comparison_rows.append(
        {
            "name": "codex_gpt_manual",
            "available": bool(codex_manual_hypothesis.get("available")),
            "top_pattern_names": [_stringify(codex_manual_hypothesis.get("hypothesis_name"))],
            "top_failure_stages": [_stringify(codex_manual_hypothesis.get("likely_failure_stage"))],
            "status": "manual_local_analysis",
        }
    )
    return {
        "hypotheses": comparison_rows,
        "claim_boundary": "Tiny smoke only. Compare hypotheses qualitatively; do not treat this as a final pattern finding or an accuracy comparison.",
    }


def _exception_api_meta(exc: Exception, *, provider: str, model: str, requested_max_output_tokens: int) -> dict[str, Any]:
    meta = {
        "provider": provider,
        "model": model,
        "requested_max_output_tokens": requested_max_output_tokens,
    }
    if isinstance(exc, ProviderRequestError):
        meta.update(
            {
                "response_http_status": exc.http_status,
                "raw_response_body_snippet": _sanitize_error_message(exc.response_body, max_len=1200),
                "retry_after": _stringify(exc.retry_after),
                "response_content_type": _stringify(exc.headers.get("Content-Type")),
            }
        )
    return meta


def _call_provider_api(
    *,
    provider: str,
    model: str,
    prompt: str,
    mode: str = "label",
    max_output_tokens: int | None = None,
) -> tuple[str, dict[str, Any]]:
    provider = provider.lower().strip()
    max_tokens = max_output_tokens if max_output_tokens and max_output_tokens > 0 else _max_tokens_for_mode(provider, mode)
    if provider == "openai":
        client = _load_openai_client()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return _extract_openai_text(response), {
            "provider": provider,
            "model": model,
            "base_url": "https://api.openai.com/v1",
            "requested_max_output_tokens": max_tokens,
            "response_finish_reason": _extract_response_finish_reason(response),
            "response_json_preview": _response_json_preview(response, max_len=1200),
        }

    if provider == "cohere":
        client = _load_cohere_client()
        request_kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            response = client.chat(**request_kwargs)
        except TypeError:
            request_kwargs.pop("response_format", None)
            response = client.chat(**request_kwargs)
        except Exception as exc:
            error_text = _stringify(exc).lower()
            if "response_format" not in error_text and "json_object" not in error_text:
                raise
            request_kwargs.pop("response_format", None)
            response = client.chat(**request_kwargs)
        text = ""
        message = getattr(response, "message", None)
        if message is not None and getattr(message, "content", None) is not None:
            content = message.content
            if isinstance(content, list) and content:
                parts: list[str] = []
                for item in content:
                    text_piece = _stringify(getattr(item, "text", ""))
                    if not text_piece and isinstance(item, dict):
                        text_piece = _stringify(item.get("text"))
                    if text_piece:
                        parts.append(text_piece)
                text = "".join(parts)
            else:
                text = _stringify(content)
        else:
            text = _stringify(getattr(response, "text", ""))
        return text.strip(), {
            "provider": provider,
            "model": model,
            "requested_max_output_tokens": max_tokens,
            "response_finish_reason": _extract_response_finish_reason(response),
            "response_json_preview": _response_json_preview(response, max_len=1200),
        }

    if provider == "cerebras":
        api_key = os.getenv("CEREBRAS_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("CEREBRAS_API_KEY is not set; cannot run with --allow-api.")
        response, transport_meta = _post_json_request(
            url="https://api.cerebras.ai/v1/chat/completions",
            api_key=api_key,
            body={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        return _extract_openai_text(response), {
            "provider": provider,
            "model": model,
            "base_url": "https://api.cerebras.ai/v1",
            "requested_max_output_tokens": max_tokens,
            **transport_meta,
        }

    if provider == "fireworks":
        api_key = os.getenv("FIREWORKS_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("FIREWORKS_API_KEY (or OPENAI_API_KEY) is not set; cannot run with --allow-api.")
        response, transport_meta = _post_json_request(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            api_key=api_key,
            body={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        return _extract_openai_text(response), {
            "provider": provider,
            "model": model,
            "base_url": "https://api.fireworks.ai/inference/v1",
            "requested_max_output_tokens": max_tokens,
            **transport_meta,
        }

    if provider == "mistral":
        api_key = os.getenv("MISTRAL_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY is not set; cannot run with --allow-api.")
        response, transport_meta = _post_json_request(
            url="https://api.mistral.ai/v1/chat/completions",
            api_key=api_key,
            body={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": max_tokens,
            },
        )
        return _extract_openai_text(response), {
            "provider": provider,
            "model": model,
            "base_url": "https://api.mistral.ai/v1",
            "requested_max_output_tokens": max_tokens,
            **transport_meta,
        }

    raise ValueError(f"Unknown provider: {provider}")


def _normalize_providers(text: str, *, allow_api: bool) -> list[str]:
    providers = [provider.strip().lower() for provider in _stringify(text).split(",") if provider.strip()]
    if providers:
        unknown = [provider for provider in providers if provider not in SUPPORTED_PROVIDERS]
        if unknown:
            raise ValueError(f"Unknown provider(s): {', '.join(sorted(unknown))}. Supported: {', '.join(SUPPORTED_PROVIDERS)}")
        return providers
    if allow_api:
        raise ValueError("--providers is required when --allow-api is set.")
    return list(DEFAULT_PROVIDERS)


def _parse_provider_caps(values: list[str]) -> dict[str, int]:
    caps: dict[str, int] = {}
    for raw in values:
        text = _stringify(raw)
        if not text:
            continue
        if "=" not in text:
            raise ValueError(f"Invalid --provider-cap value {raw!r}; expected provider=cap")
        provider, cap_text = text.split("=", 1)
        provider = provider.strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unknown provider in --provider-cap: {provider}")
        try:
            cap = int(cap_text)
        except Exception as exc:
            raise ValueError(f"Invalid cap for provider {provider}: {cap_text!r}") from exc
        if cap <= 0:
            raise ValueError(f"Cap for provider {provider} must be positive")
        caps[provider] = cap
    return caps


def _derive_even_caps(*, total: int, providers: list[str]) -> dict[str, int]:
    if total < len(providers):
        raise ValueError("max-calls-total must be at least the number of providers when deriving an even split")
    base = total // len(providers)
    remainder = total % len(providers)
    caps: dict[str, int] = {}
    for index, provider in enumerate(providers):
        caps[provider] = base + (1 if index < remainder else 0)
    return caps


def _build_provider_request(
    *,
    provider: str,
    model: str,
    case_packet: dict[str, Any],
    prompt_text: str,
    request_index: int,
    provider_cap: int,
    max_output_tokens: int,
    dry_run: bool,
    include_gold_for_labeling: bool,
) -> dict[str, Any]:
    request_id = f"{provider}:{case_packet['case_id']}:{request_index:05d}"
    request = {
        "request_id": request_id,
        "case_id": case_packet["case_id"],
        "primary_subset": case_packet["primary_subset"],
        "subset_memberships": case_packet["subset_memberships"],
        "provider": provider,
        "model": model,
        "prompt_template_id": case_packet["prompt_template_id"],
        "prompt_text": prompt_text,
        "prompt_sha256": _sha256_text(prompt_text),
        "request_sha256": _sha256_text(json.dumps({
            "case_id": case_packet["case_id"],
            "provider": provider,
            "model": model,
            "prompt_sha256": _sha256_text(prompt_text),
            "provider_cap": provider_cap,
            "include_gold_for_labeling": include_gold_for_labeling,
            "max_output_tokens": max_output_tokens,
        }, sort_keys=True)),
        "provider_cap": provider_cap,
        "max_output_tokens": max_output_tokens,
        "dry_run": bool(dry_run),
        "include_gold_for_labeling": bool(include_gold_for_labeling),
        "api_call_made": 0,
    }
    return request


def _build_pattern_provider_request(
    *,
    provider: str,
    model: str,
    batch_packet: dict[str, Any],
    prompt_text: str,
    request_index: int,
    provider_cap: int,
    max_output_tokens: int,
    dry_run: bool,
) -> dict[str, Any]:
    request_id = f"{provider}:{batch_packet['batch_id']}:{request_index:05d}"
    request = {
        "request_id": request_id,
        "batch_id": batch_packet["batch_id"],
        "provider": provider,
        "model": model,
        "mode": "pattern_discovery",
        "prompt_template_id": batch_packet.get("prompt_template_id", "failure_mechanism_multi_api_pattern_v1"),
        "prompt_text": prompt_text,
        "prompt_sha256": _sha256_text(prompt_text),
        "request_sha256": _sha256_text(json.dumps({
            "batch_id": batch_packet["batch_id"],
            "provider": provider,
            "model": model,
            "prompt_sha256": _sha256_text(prompt_text),
            "provider_cap": provider_cap,
            "max_output_tokens": max_output_tokens,
        }, sort_keys=True)),
        "provider_cap": provider_cap,
        "max_output_tokens": max_output_tokens,
        "dry_run": bool(dry_run),
        "api_call_made": 0,
        "batch_case_count": batch_packet.get("case_count", 0),
        "cases_reviewed": batch_packet.get("cases_reviewed", []),
    }
    return request


def _compute_label_frequency_summary(parsed_rows: list[dict[str, Any]], providers: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metric_fields = [
        "primary_label",
        "selector_vs_generation",
        "candidate_pool_status",
        "recommended_fix_family",
    ]
    total_by_metric: dict[str, Counter[str]] = {metric: Counter() for metric in metric_fields}
    provider_metric: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in parsed_rows:
        if not row.get("label_valid"):
            continue
        provider = _stringify(row.get("provider"))
        for metric in metric_fields:
            value = _stringify(row.get(metric))
            if value:
                total_by_metric[metric][value] += 1
                provider_metric[(provider, metric)][value] += 1
    for metric, counter in total_by_metric.items():
        total = sum(counter.values())
        for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
            rows.append(
                {
                    "scope": "overall",
                    "provider": "",
                    "metric": metric,
                    "label": label,
                    "count": count,
                    "share": round(count / max(1, total), 6),
                }
            )
    for provider in providers:
        for metric in metric_fields:
            counter = provider_metric.get((provider, metric), Counter())
            total = sum(counter.values())
            for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
                rows.append(
                    {
                        "scope": "provider",
                        "provider": provider,
                        "metric": metric,
                        "label": label,
                        "count": count,
                        "share": round(count / max(1, total), 6),
                    }
                )
    return rows


def _summarize_agreement(case_matrix_rows: list[dict[str, Any]], providers: list[str], parsed_rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_case: dict[str, dict[str, Any]] = defaultdict(dict)
    for row in parsed_rows:
        case_id = _stringify(row.get("case_id"))
        provider = _stringify(row.get("provider"))
        if case_id and provider:
            per_case[case_id][provider] = row

    provider_label_counts: dict[str, Counter[str]] = {provider: Counter() for provider in providers}
    for row in parsed_rows:
        if not row.get("label_valid"):
            continue
        provider = _stringify(row.get("provider"))
        label = _stringify(row.get("primary_label"))
        if provider and label:
            provider_label_counts.setdefault(provider, Counter())[label] += 1

    all_agree = 0
    partial_agree = 0
    disagreements = 0
    missing = 0
    for row in case_matrix_rows:
        status = _stringify(row.get("agreement_status"))
        if status == "all_agree":
            all_agree += 1
        elif status == "partial_agree":
            partial_agree += 1
        elif status == "missing":
            missing += 1
        else:
            disagreements += 1

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "providers": providers,
        "case_count": len(case_matrix_rows),
        "parsed_label_row_count": len(parsed_rows),
        "all_agree_case_count": all_agree,
        "partial_agree_case_count": partial_agree,
        "disagreement_case_count": disagreements,
        "missing_label_case_count": missing,
        "provider_label_counts": {provider: dict(sorted(counter.items(), key=lambda item: (-item[1], item[0]))) for provider, counter in provider_label_counts.items()},
    }


def _build_case_label_matrix(
    *,
    case_packets: list[dict[str, Any]],
    parsed_rows: list[dict[str, Any]],
    providers: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parsed_by_case_provider: dict[tuple[str, str], dict[str, Any]] = {}
    for row in parsed_rows:
        parsed_by_case_provider[(_stringify(row.get("case_id")), _stringify(row.get("provider")))] = row

    matrix_rows: list[dict[str, Any]] = []
    disagreement_rows: list[dict[str, Any]] = []

    for packet in case_packets:
        row: dict[str, Any] = {
            "case_id": packet["case_id"],
            "primary_subset": packet["primary_subset"],
            "subset_memberships": json.dumps(packet["subset_memberships"], sort_keys=True),
            "label_count": 0,
            "missing_provider_count": 0,
            "agreement_status": "missing",
            "consensus_primary_label": "",
            "provider_labels_json": "",
        }
        primary_labels: list[str] = []
        provider_labels_payload: dict[str, Any] = {}
        missing_providers: list[str] = []
        for provider in providers:
            parsed = parsed_by_case_provider.get((packet["case_id"], provider))
            provider_labels_payload[provider] = parsed or {}
            label = _stringify(parsed.get("primary_label")) if parsed else ""
            confidence = parsed.get("confidence") if parsed else ""
            row[f"{provider}_primary_label"] = label
            row[f"{provider}_confidence"] = confidence
            row[f"{provider}_candidate_pool_status"] = _stringify(parsed.get("candidate_pool_status")) if parsed else ""
            row[f"{provider}_selector_vs_generation"] = _stringify(parsed.get("selector_vs_generation")) if parsed else ""
            if label:
                primary_labels.append(label)
            else:
                missing_providers.append(provider)
        row["label_count"] = len(primary_labels)
        row["missing_provider_count"] = len(missing_providers)
        row["provider_labels_json"] = json.dumps(provider_labels_payload, sort_keys=True)

        if len(primary_labels) == len(providers) and len(set(primary_labels)) == 1:
            row["agreement_status"] = "all_agree"
            row["consensus_primary_label"] = primary_labels[0]
        elif len(set(primary_labels)) <= 1 and primary_labels:
            row["agreement_status"] = "partial_agree"
            row["consensus_primary_label"] = primary_labels[0]
        elif primary_labels:
            row["agreement_status"] = "disagreement"
            row["consensus_primary_label"] = Counter(primary_labels).most_common(1)[0][0]
        else:
            row["agreement_status"] = "missing"
            row["consensus_primary_label"] = ""
        matrix_rows.append(row)

        if row["agreement_status"] in {"disagreement", "missing"}:
            disagreement_rows.append(
                {
                    "case_id": packet["case_id"],
                    "primary_subset": packet["primary_subset"],
                    "agreement_status": row["agreement_status"],
                    "consensus_primary_label": row["consensus_primary_label"],
                    "missing_providers": "|".join(missing_providers),
                    "provider_labels_json": row["provider_labels_json"],
                }
            )

    return matrix_rows, disagreement_rows


def _selected_request_limit(
    *,
    allow_api: bool,
    max_calls_total: int,
    providers: list[str],
    explicit_provider_caps: dict[str, int],
) -> dict[str, int]:
    if not allow_api:
        return {provider: 0 for provider in providers}
    if explicit_provider_caps:
        missing = [provider for provider in providers if provider not in explicit_provider_caps]
        if missing:
            raise ValueError(
                f"--provider-cap must be supplied for every selected provider when explicit caps are used; missing: {', '.join(missing)}"
            )
        return dict(explicit_provider_caps)
    return _derive_even_caps(total=max_calls_total, providers=providers)


def _build_outputs(
    *,
    case_packets: list[dict[str, Any]],
    providers: list[str],
    provider_models: dict[str, str],
    provider_caps: dict[str, int],
    allow_api: bool,
    include_gold_for_labeling: bool,
    max_calls_total: int,
    prompt_packets: list[dict[str, Any]],
    request_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    parsed_rows: list[dict[str, Any]],
    packet_completeness_summary: dict[str, Any],
    output_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    case_matrix_rows, disagreement_rows = _build_case_label_matrix(case_packets=case_packets, parsed_rows=parsed_rows, providers=providers)
    frequency_rows = _compute_label_frequency_summary(parsed_rows, providers)
    agreement_summary = _summarize_agreement(case_matrix_rows, providers, parsed_rows)
    readiness_summary = _provider_readiness_summary(parsed_rows, providers)
    agreement_summary.update(
        {
            "allow_api": allow_api,
            "include_gold_for_labeling": include_gold_for_labeling,
            "max_calls_total": max_calls_total,
            "provider_caps": provider_caps,
            "provider_models": provider_models,
            "planned_request_count": len(request_rows),
            "raw_label_row_count": len(raw_rows),
            "parsed_label_row_count": len(parsed_rows),
            "case_matrix_row_count": len(case_matrix_rows),
            "disagreement_case_count": len(disagreement_rows),
            "packet_completeness_summary": packet_completeness_summary,
        }
    )
    agreement_summary.update(readiness_summary)

    _write_jsonl(output_dir / "trace_packets.jsonl", prompt_packets)
    _write_jsonl(output_dir / "provider_requests_dry_run.jsonl", request_rows)
    _write_jsonl(output_dir / "raw_provider_labels.jsonl", raw_rows)
    _write_jsonl(output_dir / "parsed_labels.jsonl", parsed_rows)
    _write_json(output_dir / "agreement_summary.json", agreement_summary)
    _write_json(output_dir / "packet_completeness_summary.json", packet_completeness_summary)
    _write_csv(
        output_dir / "label_frequency_summary.csv",
        frequency_rows,
        ["scope", "provider", "metric", "label", "count", "share"],
    )
    _write_csv(
        output_dir / "case_label_matrix.csv",
        case_matrix_rows,
        [
            "case_id",
            "primary_subset",
            "subset_memberships",
            *[f"{provider}_primary_label" for provider in providers],
            *[f"{provider}_confidence" for provider in providers],
            *[f"{provider}_candidate_pool_status" for provider in providers],
            *[f"{provider}_selector_vs_generation" for provider in providers],
            "label_count",
            "missing_provider_count",
            "agreement_status",
            "consensus_primary_label",
            "provider_labels_json",
        ],
    )
    _write_csv(
        output_dir / "disagreement_cases.csv",
        disagreement_rows,
        ["case_id", "primary_subset", "agreement_status", "consensus_primary_label", "missing_providers", "provider_labels_json"],
    )
    _write_json(output_dir / "manifest.json", manifest)
    return agreement_summary


def _build_pattern_outputs(
    *,
    batch_packets: list[dict[str, Any]],
    providers: list[str],
    provider_models: dict[str, str],
    provider_caps: dict[str, int],
    allow_api: bool,
    include_gold_for_labeling: bool,
    max_calls_total: int,
    prompt_packets: list[dict[str, Any]],
    request_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    parsed_rows: list[dict[str, Any]],
    packet_completeness_summary: dict[str, Any],
    output_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    pattern_summary = _summarize_pattern_discovery(parsed_rows, providers)
    readiness_summary = _provider_readiness_summary(parsed_rows, providers)
    pattern_summary.update(
        {
            "mode": "pattern_discovery",
            "allow_api": allow_api,
            "include_gold_for_labeling": include_gold_for_labeling,
            "max_calls_total": max_calls_total,
            "provider_caps": provider_caps,
            "provider_models": provider_models,
            "planned_request_count": len(request_rows),
            "requested_case_count": manifest.get("requested_case_count", pattern_summary.get("selected_case_count", 0)),
            "expected_request_count": len(providers),
            "raw_label_row_count": len(raw_rows),
            "parsed_label_row_count": len(parsed_rows),
            "batch_count": len(batch_packets),
            "provider_batch_count": len(providers),
            "selected_case_count": batch_packets[0].get("case_count", 0) if batch_packets else 0,
            "cases_reviewed": batch_packets[0].get("cases_reviewed", []) if batch_packets else [],
            "api_call_count": sum(1 for row in raw_rows if _is_truthy(row.get("api_call_made"))),
            "packet_completeness_summary": packet_completeness_summary,
        }
    )
    pattern_summary.update(readiness_summary)

    _write_jsonl(output_dir / "trace_packets.jsonl", prompt_packets)
    _write_jsonl(output_dir / "provider_requests_dry_run.jsonl", request_rows)
    _write_jsonl(output_dir / "raw_provider_labels.jsonl", raw_rows)
    _write_jsonl(output_dir / "parsed_labels.jsonl", parsed_rows)
    _write_json(output_dir / "pattern_summary.json", pattern_summary)
    _write_json(output_dir / "packet_completeness_summary.json", packet_completeness_summary)
    report_lines = [
        "# Multi-API Failure Mechanism Pattern Discovery",
        "",
        "## Run Mode",
        "",
        f"- mode: `pattern_discovery`",
        f"- allow_api: `{allow_api}`",
        f"- dry_run: `{not allow_api or not request_rows or all(row.get('dry_run') for row in request_rows)}`",
        f"- include_gold_for_labeling: `{include_gold_for_labeling}`",
        f"- max_calls_total: `{max_calls_total}`",
        f"- providers: `{', '.join(providers)}`",
        f"- provider_caps: `{json.dumps(provider_caps, sort_keys=True)}`",
        "",
        "## Batch Counts",
        "",
        f"- selected_case_count: `{pattern_summary.get('selected_case_count', 0)}`",
        f"- requested_case_count: `{manifest.get('requested_case_count', pattern_summary.get('selected_case_count', 0))}`",
        f"- batch_count: `{pattern_summary.get('batch_count', 0)}`",
        f"- provider_batch_count: `{pattern_summary.get('provider_batch_count', 0)}`",
        f"- planned_request_count: `{pattern_summary.get('planned_request_count', 0)}`",
        f"- expected_request_count: `{pattern_summary.get('planned_request_count', 0)}`",
        f"- api_call_count: `{sum(1 for row in raw_rows if _is_truthy(row.get('api_call_made')))}`",
        "",
        "## Provider Config",
        "",
    ]
    provider_config_summary = manifest.get("provider_config_summary", {})
    for provider in providers:
        config = provider_config_summary.get(provider, {})
        report_lines.append(
            f"- `{provider}`: env_ready `{config.get('env_ready')}`; model `{config.get('model')}`; config_ready `{config.get('config_ready')}`"
        )
        env_presence = config.get("env_presence", {})
        if isinstance(env_presence, dict):
            for env_name, present in sorted(env_presence.items()):
                report_lines.append(f"  - {env_name}: `{present}`")
    report_lines.extend(
        [
            "",
            "## Packet Completeness",
            "",
            f"- question_present_rate: `{packet_completeness_summary.get('question_present_rate', 0.0)}`",
            f"- prediction_present_rate: `{packet_completeness_summary.get('prediction_present_rate', 0.0)}`",
            f"- candidate_pool_present_rate: `{packet_completeness_summary.get('candidate_pool_present_rate', 0.0)}`",
            f"- action_trace_present_rate: `{packet_completeness_summary.get('action_trace_present_rate', 0.0)}`",
            f"- pal_execution_present_rate: `{packet_completeness_summary.get('pal_execution_present_rate', 0.0)}`",
            f"- structural_fields_present_rate: `{packet_completeness_summary.get('structural_fields_present_rate', 0.0)}`",
            f"- empty_packet_count: `{packet_completeness_summary.get('empty_packet_count', 0)}`",
            f"- per_subset: `{json.dumps(packet_completeness_summary.get('per_subset', {}), sort_keys=True)}`",
            "",
            "## Pattern Summary",
            "",
            f"- provider_pattern_name_counts: `{json.dumps(pattern_summary.get('provider_pattern_name_counts', {}), sort_keys=True)}`",
            f"- provider_supporting_case_counts: `{json.dumps(pattern_summary.get('provider_supporting_case_counts', {}), sort_keys=True)}`",
            f"- provider_likely_failure_stage_distribution: `{json.dumps(pattern_summary.get('provider_likely_failure_stage_distribution', {}), sort_keys=True)}`",
            f"- provider_ambiguous_case_ids: `{json.dumps(pattern_summary.get('provider_ambiguous_case_ids', {}), sort_keys=True)}`",
            f"- provider_unique_hypotheses: `{json.dumps(pattern_summary.get('provider_unique_hypotheses', {}), sort_keys=True)}`",
            "",
            "## Provider Readiness",
            "",
        ]
    )
    readiness_counts = pattern_summary.get("provider_readiness_counts", {})
    readiness_samples = pattern_summary.get("provider_error_samples", {})
    for provider in providers:
        provider_counts = readiness_counts.get(provider, {})
        report_lines.append(f"- `{provider}`: `{json.dumps(provider_counts, sort_keys=True)}`")
        for sample in readiness_samples.get(provider, []):
            report_lines.append(
                "  - "
                + json.dumps(
                    {
                        "batch_id": sample.get("case_id"),
                        "label_status": sample.get("label_status"),
                        "provider_readiness": sample.get("provider_readiness"),
                        "provider_http_status": sample.get("provider_http_status"),
                        "provider_error_code": sample.get("provider_error_code"),
                        "provider_error_message_short": sample.get("provider_error_message_short"),
                    },
                    sort_keys=True,
                )
            )
    report_lines.extend(
        [
            "",
            "## Warnings",
            "",
        ]
    )
    for warning in packet_completeness_summary.get("warnings", []):
        report_lines.append(f"- {warning}")
    report_lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Pattern discovery batches are hypotheses until manually audited.",
            "- Non-Cohere providers are allowed here only for pattern discovery, not for algorithm comparison.",
            "- The pattern prompt is gold-free unless `--include-gold-for-labeling` is set.",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")
    _write_json(output_dir / "manifest.json", manifest)
    return pattern_summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failure-csv", default=str(DEFAULT_FAILURE_CSV), help="Failure audit CSV.")
    parser.add_argument("--gold-absent-csv", default=str(DEFAULT_GOLD_ABSENT_CSV), help="Gold-absent audit CSV.")
    parser.add_argument("--anchor-effect-csv", default=str(DEFAULT_ANCHOR_EFFECT_CSV), help="Anchor-effect CSV.")
    parser.add_argument("--target-audit-jsonl", default=str(DEFAULT_TARGET_AUDIT_JSONL), help="Target audit JSONL with richer trace fields.")
    parser.add_argument("--diagnostic-30-jsonl", default=str(DEFAULT_DIAGNOSTIC_30_JSONL), help="Exact 30-case diagnostic JSONL.")
    parser.add_argument("--target-staged-15-jsonl", default=str(DEFAULT_TARGET_STAGED_15_JSONL), help="Exact 15-case target-staged JSONL.")
    parser.add_argument("--structural-feature-csv", default="", help="Optional structural feature CSV; defaults to latest candidate_feature_rows.csv under outputs.")
    parser.add_argument("--outputs-root", default=str(DEFAULT_OUTPUTS_ROOT), help="Outputs root for auto-discovery.")
    parser.add_argument("--subsets", "--subset", default=",".join(DEFAULT_SUBSETS), help="Comma-separated subset list.")
    parser.add_argument("--providers", default="", help="Comma-separated providers. Required in API mode.")
    parser.add_argument("--mode", choices=["label", "pattern_discovery"], default="label", help="Label each case or discover patterns across a batch.")
    parser.add_argument("--openai-model", default=DEFAULT_MODELS["openai"], help="OpenAI model name.")
    parser.add_argument("--cohere-model", default=DEFAULT_MODELS["cohere"], help="Cohere model name.")
    parser.add_argument("--cerebras-model", default="", help="Cerebras model name. Required for live API mode.")
    parser.add_argument("--fireworks-model", default="", help="Fireworks model name. Required for live API mode.")
    parser.add_argument("--mistral-model", default=DEFAULT_MODELS["mistral"], help="Mistral model name.")
    parser.add_argument("--provider-cap", action="append", default=[], help="Repeatable provider cap in the form provider=cap.")
    parser.add_argument("--limit", type=int, default=0, help="Optional deterministic case limit applied after subset construction.")
    parser.add_argument(
        "--min-packet-completeness",
        type=float,
        default=0.75,
        help="Warn when question or prediction completeness falls below this present-rate threshold.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=0,
        help="Optional output token override for provider calls. Defaults to mode/provider-specific caps.",
    )
    parser.add_argument("--max-calls-total", type=int, default=0, help="Hard total call cap. Required in API mode.")
    parser.add_argument("--allow-api", action="store_true", help="Allow provider API calls.")
    parser.add_argument(
        "--check-provider-config",
        action="store_true",
        help="Report provider env/model configuration without sending requests.",
    )
    parser.add_argument("--include-gold-for-labeling", action="store_true", help="Include reference answers in prompt packets and mark outputs gold-assisted.")
    parser.add_argument("--output-dir", default="", help="Output directory override.")
    parser.add_argument("--timestamp", default=_utc_stamp(), help="UTC timestamp suffix for the default output directory.")
    parser.add_argument("--dry-run", "--validate-only", action="store_true", dest="dry_run", help="No-API dry run only.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    failure_csv = Path(args.failure_csv).expanduser()
    gold_absent_csv = Path(args.gold_absent_csv).expanduser()
    anchor_effect_csv = Path(args.anchor_effect_csv).expanduser()
    target_audit_jsonl = Path(args.target_audit_jsonl).expanduser()
    diagnostic_30_jsonl = Path(args.diagnostic_30_jsonl).expanduser()
    target_staged_15_jsonl = Path(args.target_staged_15_jsonl).expanduser()
    structural_feature_csv = Path(args.structural_feature_csv).expanduser() if args.structural_feature_csv else None
    outputs_root = Path(args.outputs_root).expanduser()
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else outputs_root / f"{DEFAULT_OUTPUT_PREFIX}{args.timestamp}"

    for path, label in [
        (failure_csv, "failure CSV"),
        (gold_absent_csv, "gold-absent CSV"),
        (anchor_effect_csv, "anchor-effect CSV"),
        (target_audit_jsonl, "target audit JSONL"),
        (diagnostic_30_jsonl, "diagnostic-30 JSONL"),
        (target_staged_15_jsonl, "target-staged JSONL"),
    ]:
        if not path.is_file():
            raise FileNotFoundError(f"Missing required {label}: {path}")

    providers = _normalize_providers(args.providers, allow_api=bool(args.allow_api))
    subsets = [subset.strip() for subset in _stringify(args.subsets).split(",") if subset.strip()]
    failure_rows = _read_csv_rows(failure_csv)
    gold_rows = _read_csv_rows(gold_absent_csv)
    anchor_rows = _read_csv_rows(anchor_effect_csv)
    failure_map = _load_failure_map(failure_csv)
    gold_map = _load_gold_absent_map(gold_absent_csv)
    anchor_map = _load_anchor_map(anchor_effect_csv)
    target_audit_map = _load_target_audit_map(target_audit_jsonl)
    structural_map, resolved_structural_csv = _load_structural_feature_map(structural_feature_csv, outputs_root)
    artifact_bundles = _load_failure_artifact_bundle_map(failure_rows)

    subset_specs = _build_subset_specs(
        failure_rows=failure_rows,
        gold_rows=gold_rows,
        anchor_rows=anchor_rows,
        diagnostic_30_jsonl=diagnostic_30_jsonl,
        target_staged_15_jsonl=target_staged_15_jsonl,
        subsets=subsets,
    )
    ordered_case_ids, memberships, primary_subsets = _order_case_ids_for_union(subset_specs)
    prelimit_unique_case_count = len(ordered_case_ids)
    limit_value = int(args.limit or 0)
    if limit_value < 0:
        raise ValueError("--limit must be non-negative")
    if limit_value > 0:
        ordered_case_ids = ordered_case_ids[:limit_value]
    case_packets = [
        _build_case_packet(
            case_id=case_id,
            subset_memberships=memberships[case_id],
            primary_subset=primary_subsets[case_id],
            failure_map=failure_map,
            gold_map=gold_map,
            anchor_map=anchor_map,
            target_audit_map=target_audit_map,
            structural_map=structural_map,
            artifact_bundles=artifact_bundles,
            include_gold_for_labeling=bool(args.include_gold_for_labeling),
        )
        for case_id in ordered_case_ids
    ]
    min_packet_completeness = float(args.min_packet_completeness or 0.0)
    if min_packet_completeness < 0.0 or min_packet_completeness > 1.0:
        raise ValueError("--min-packet-completeness must be between 0 and 1")
    packet_completeness_summary = _compute_packet_completeness_summary(
        case_packets,
        min_completeness=min_packet_completeness,
    )

    prompt_packets = []
    for packet in case_packets:
        prompt_text = _render_prompt(packet)
        prompt_packets.append({**packet, "prompt": prompt_text, "prompt_sha256": _sha256_text(prompt_text)})

    explicit_caps = _parse_provider_caps(args.provider_cap)
    max_calls_total = int(args.max_calls_total or 0)
    allow_api = bool(args.allow_api)
    check_provider_config = bool(args.check_provider_config)
    dry_run = bool(args.dry_run) or not allow_api or check_provider_config
    if allow_api and not check_provider_config and max_calls_total <= 0:
        raise ValueError("--allow-api requires a positive --max-calls-total")
    provider_caps = _selected_request_limit(
        allow_api=allow_api,
        max_calls_total=max_calls_total,
        providers=providers,
        explicit_provider_caps=explicit_caps,
    )
    provider_models = {
        "openai": _stringify(args.openai_model) or DEFAULT_MODELS["openai"],
        "cohere": _stringify(args.cohere_model) or DEFAULT_MODELS["cohere"],
        "cerebras": _stringify(args.cerebras_model),
        "fireworks": _stringify(args.fireworks_model),
        "mistral": _stringify(args.mistral_model) or DEFAULT_MODELS["mistral"],
    }
    if not allow_api or check_provider_config:
        provider_models["openai"] = provider_models["openai"] or DEFAULT_MODELS["openai"]
    if not allow_api or check_provider_config:
        provider_models["cerebras"] = provider_models["cerebras"] or DEFAULT_MODELS["cerebras"]
        provider_models["fireworks"] = provider_models["fireworks"] or DEFAULT_MODELS["fireworks"]
        provider_models["mistral"] = provider_models["mistral"] or DEFAULT_MODELS["mistral"]
    provider_config_summary = _provider_config_summary(providers=providers, provider_models=provider_models)

    mode = _stringify(args.mode).lower()
    max_output_tokens_override = int(args.max_output_tokens or 0)
    if max_output_tokens_override < 0:
        raise ValueError("--max-output-tokens must be non-negative")
    provider_max_output_tokens = {
        provider: (
            max_output_tokens_override
            if max_output_tokens_override > 0
            else _max_tokens_for_mode(provider, mode)
        )
        for provider in providers
    }

    if check_provider_config:
        output_dir.mkdir(parents=True, exist_ok=True)
        config_manifest = {
            "experiment_id": "failure_mechanism_multi_api_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "script": "scripts/label_failure_mechanisms_multi_api.py",
            "allow_api": False,
            "dry_run": True,
            "check_provider_config": True,
            "api_clients_constructed": False,
            "max_calls_total": max_calls_total,
            "limit": limit_value,
            "providers": providers,
            "provider_models": provider_models,
            "provider_max_output_tokens": provider_max_output_tokens,
            "max_output_tokens_override": max_output_tokens_override,
            "provider_caps": {provider: 0 for provider in providers},
            "provider_config_summary": provider_config_summary,
            "packet_completeness_summary": packet_completeness_summary,
            "include_gold_for_labeling": bool(args.include_gold_for_labeling),
            "gold_assisted": bool(args.include_gold_for_labeling),
            "subset_specs": subset_specs,
            "subset_names": subsets,
            "subset_case_counts": {spec["subset"]: len(spec["case_ids"]) for spec in subset_specs},
            "prelimit_unique_case_count": prelimit_unique_case_count,
            "requested_case_count": prelimit_unique_case_count,
            "selected_case_count": len(case_packets),
            "unique_case_count": len(case_packets),
            "planned_request_count": len(case_packets) * len(providers),
            "api_call_count": 0,
            "failure_csv": str(failure_csv),
            "gold_absent_csv": str(gold_absent_csv),
            "anchor_effect_csv": str(anchor_effect_csv),
            "target_audit_jsonl": str(target_audit_jsonl),
            "diagnostic_30_jsonl": str(diagnostic_30_jsonl),
            "target_staged_15_jsonl": str(target_staged_15_jsonl),
            "structural_feature_csv": str(resolved_structural_csv) if resolved_structural_csv else "",
            "output_files": ["manifest.json", "report.md", "packet_completeness_summary.json"],
            "label_schema": {
                "fields": LABEL_FIELDS,
                "primary_label_values": sorted(PRIMARY_LABELS),
                "secondary_label_values": sorted(SECONDARY_LABELS),
                "selector_vs_generation_values": sorted(SELECTOR_VS_GENERATION),
                "candidate_pool_status_values": sorted(POOL_STATUS),
                "recommended_fix_family_values": sorted(FIX_FAMILIES),
            },
            "selection_notes": [
                "diagnostic_30 and target_staged_15 are exact JSONL slices.",
                "pal_still_failing_157 is derived from the full failure CSV and trimmed to 157 if necessary.",
                "wrong_supported_consensus_97 is derived from the gold-absent CSV rows with external_contrast == Both wrong and trimmed to 97 if necessary.",
                "direct_l1_anchor_potential_43 is derived from the anchor-effect CSV rows with strong anchor evidence and trimmed to 43 if necessary.",
            ],
            "no_api_clients_constructed": True,
            "prelimit_unique_case_count": prelimit_unique_case_count,
            "limit": limit_value,
        }
        _write_json(output_dir / "manifest.json", config_manifest)
        config_report_lines = [
            "# Multi-API Failure Mechanism Labeling Plan",
            "",
            "## Run Mode",
            "",
            f"- allow_api: `False`",
            f"- dry_run: `True`",
            f"- check_provider_config: `True`",
            f"- api_clients_constructed: `False`",
            f"- limit: `{limit_value}`",
            f"- providers: `{', '.join(providers)}`",
            f"- provider_models: `{json.dumps(provider_models, sort_keys=True)}`",
            "",
            "## Provider Config",
            "",
        ]
        for provider in providers:
            config = provider_config_summary.get(provider, {})
            config_report_lines.append(
                f"- `{provider}`: env_ready `{config.get('env_ready')}`; model `{config.get('model')}`; config_ready `{config.get('config_ready')}`"
            )
            env_presence = config.get("env_presence", {})
            if isinstance(env_presence, dict):
                for env_name, present in sorted(env_presence.items()):
                    config_report_lines.append(f"  - {env_name}: `{present}`")
        config_report_lines.extend(
            [
                "",
                "## Slices",
                "",
            ]
        )
        for spec in subset_specs:
            config_report_lines.append(
                f"- `{spec['subset']}`: raw `{spec['raw_count']}` -> selected `{spec['selected_count']}`; approximate `{spec['approximate']}`"
            )
        config_report_lines.extend(
            [
                "",
                "## Counts",
                "",
                f"- prelimit_unique_case_count: `{prelimit_unique_case_count}`",
                f"- requested_case_count: `{prelimit_unique_case_count}`",
                f"- selected_case_count: `{len(case_packets)}`",
                f"- unique_case_count: `{len(case_packets)}`",
                f"- planned_request_count: `{len(case_packets) * len(providers)}`",
                "",
                "## Packet Completeness",
                "",
                f"- question_present_rate: `{packet_completeness_summary.get('question_present_rate', 0.0)}`",
                f"- prediction_present_rate: `{packet_completeness_summary.get('prediction_present_rate', 0.0)}`",
                f"- candidate_pool_present_rate: `{packet_completeness_summary.get('candidate_pool_present_rate', 0.0)}`",
                f"- action_trace_present_rate: `{packet_completeness_summary.get('action_trace_present_rate', 0.0)}`",
                f"- pal_execution_present_rate: `{packet_completeness_summary.get('pal_execution_present_rate', 0.0)}`",
                f"- structural_fields_present_rate: `{packet_completeness_summary.get('structural_fields_present_rate', 0.0)}`",
                f"- empty_packet_count: `{packet_completeness_summary.get('empty_packet_count', 0)}`",
                f"- per_subset: `{json.dumps(packet_completeness_summary.get('per_subset', {}), sort_keys=True)}`",
                "",
                "## Notes",
                "",
                "- This is a provider-config dry-check only; no requests were sent.",
                "- The prompt packet is still rendered gold-free unless `--include-gold-for-labeling` is set.",
            ]
        )
        if packet_completeness_summary.get("warnings"):
            config_report_lines.extend(["", "## Warnings", ""])
            for warning in packet_completeness_summary.get("warnings", []):
                config_report_lines.append(f"- {warning}")
        (output_dir / "report.md").write_text("\n".join(config_report_lines).rstrip() + "\n", encoding="utf-8")
        _write_json(output_dir / "packet_completeness_summary.json", packet_completeness_summary)
        print(json.dumps(config_manifest, indent=2, sort_keys=True))
        return 0

    if mode == "pattern_discovery":
        if allow_api:
            missing_models = [provider for provider in providers if not provider_models.get(provider)]
            if missing_models:
                raise ValueError(
                    "Pattern discovery live mode requires explicit models for selected providers; missing: "
                    + ", ".join(sorted(missing_models))
                )
            missing_env = [provider for provider in providers if not _provider_env_ready(provider)]
            if missing_env:
                raise ValueError(
                    "Pattern discovery live mode requires provider environment variables for selected providers; missing or empty env for: "
                    + ", ".join(sorted(missing_env))
                )
            if max_calls_total < len(providers):
                raise RuntimeError(
                    "Hard call cap is too small for one batch request per selected provider in pattern discovery mode."
                )

        output_dir.mkdir(parents=True, exist_ok=True)
        batch_packets: list[dict[str, Any]] = []
        prompt_packets: list[dict[str, Any]] = []
        request_rows: list[dict[str, Any]] = []
        raw_rows: list[dict[str, Any]] = []
        parsed_rows: list[dict[str, Any]] = []
        total_calls = 0
        provider_call_counts: Counter[str] = Counter()
        provider_request_counts: Counter[str] = Counter()
        api_clients_constructed = False

        if allow_api and not dry_run:
            api_clients_constructed = True

        for provider in providers:
            batch_id = _build_pattern_batch_id(provider=provider, case_packets=case_packets)
            batch_packet = _build_pattern_batch_packet(
                provider=provider,
                model=provider_models[provider],
                batch_id=batch_id,
                case_packets=case_packets,
                include_gold_for_labeling=bool(args.include_gold_for_labeling),
            )
            batch_packets.append(batch_packet)
            prompt_text = _render_pattern_prompt(batch_packet)
            prompt_packets.append({**batch_packet, "prompt": prompt_text, "prompt_sha256": _sha256_text(prompt_text)})
            provider_request_counts[provider] += 1
            request_row = _build_pattern_provider_request(
                provider=provider,
                model=provider_models[provider],
                batch_packet=batch_packet,
                prompt_text=prompt_text,
                request_index=provider_request_counts[provider],
                provider_cap=provider_caps.get(provider, 0),
                max_output_tokens=provider_max_output_tokens[provider],
                dry_run=dry_run,
            )
            request_rows.append(request_row)

            if dry_run:
                raw_rows.append(
                    {
                        "request_id": request_row["request_id"],
                        "case_id": batch_id,
                        "batch_id": batch_id,
                        "provider": provider,
                        "model": provider_models[provider],
                        "mode": "pattern_discovery",
                        "cases_reviewed": batch_packet["cases_reviewed"],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": True,
                        "api_call_made": 0,
                        "raw_label_text": "",
                        "raw_label_sha256": "",
                        "raw_response_json": "",
                        "api_error": "",
                        "provider_readiness": "dry_run",
                        "provider_http_status": "",
                        "provider_error_code": "",
                        "provider_error_message_short": "",
                    }
                )
                parsed_rows.append(
                    {
                        "request_id": request_row["request_id"],
                        "case_id": batch_id,
                        "batch_id": batch_id,
                        "provider": provider,
                        "model": provider_models[provider],
                        "mode": "pattern_discovery",
                        "cases_reviewed": batch_packet["cases_reviewed"],
                        "top_patterns": [],
                        "recommended_taxonomy_changes": [],
                        "what_extra_metadata_is_needed": [],
                        "do_not_claim": [],
                        "prompt_template_id": request_row["prompt_template_id"],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": True,
                        "api_call_made": 0,
                        "label_status": "dry_run",
                        "pattern_valid": False,
                        "pattern_errors": ["dry_run"],
                        "label_valid": False,
                        "label_errors": ["dry_run"],
                        "provider_readiness": "dry_run",
                        "provider_http_status": "",
                        "provider_error_code": "",
                        "provider_error_message_short": "",
                    }
                )
                continue

            total_calls += 1
            provider_call_counts[provider] += 1
            try:
                raw_text, api_meta = _call_provider_api(
                    provider=provider,
                    model=provider_models[provider],
                    prompt=prompt_text,
                    mode="pattern_discovery",
                    max_output_tokens=provider_max_output_tokens[provider],
                )
                parsed_pattern, parse_error = _parse_pattern_discovery_json(raw_text)
                if parsed_pattern is None:
                    provider_details = _provider_error_details(
                        label_status="parse_error",
                        api_error=raw_text,
                        label_parse_error=parse_error,
                    )
                    raw_rows.append(
                        {
                            "request_id": request_row["request_id"],
                            "case_id": batch_id,
                            "batch_id": batch_id,
                            "provider": provider,
                            "model": provider_models[provider],
                            "mode": "pattern_discovery",
                            "cases_reviewed": batch_packet["cases_reviewed"],
                            "prompt_sha256": request_row["prompt_sha256"],
                            "request_sha256": request_row["request_sha256"],
                            "dry_run": False,
                            "api_call_made": 1,
                            "raw_label_text": raw_text,
                            "raw_label_sha256": _sha256_text(raw_text),
                            "raw_response_json": json.dumps({**api_meta, **provider_details}, sort_keys=True),
                            "api_error": "",
                            **provider_details,
                        }
                    )
                    parsed_rows.append(
                        {
                            "request_id": request_row["request_id"],
                            "case_id": batch_id,
                            "batch_id": batch_id,
                            "provider": provider,
                            "model": provider_models[provider],
                            "mode": "pattern_discovery",
                            "cases_reviewed": batch_packet["cases_reviewed"],
                            "top_patterns": [],
                            "recommended_taxonomy_changes": [],
                            "what_extra_metadata_is_needed": [],
                            "do_not_claim": [],
                            "prompt_template_id": request_row["prompt_template_id"],
                            "prompt_sha256": request_row["prompt_sha256"],
                            "request_sha256": request_row["request_sha256"],
                            "dry_run": False,
                            "api_call_made": 1,
                            "label_status": "parse_error",
                            "label_parse_error": parse_error,
                            "pattern_valid": False,
                            "pattern_errors": [parse_error],
                            "label_valid": False,
                            "label_errors": [parse_error],
                            **provider_details,
                        }
                    )
                    continue

                provider_details = _provider_error_details(
                    label_status="parsed" if parsed_pattern.get("label_valid") else "parse_error",
                    api_error="",
                    label_parse_error="" if parsed_pattern.get("label_valid") else "invalid_pattern_schema",
                )
                label_status = "parsed" if parsed_pattern.get("label_valid") else "parse_error"
                raw_rows.append(
                    {
                        "request_id": request_row["request_id"],
                        "case_id": batch_id,
                        "batch_id": batch_id,
                        "provider": provider,
                        "model": provider_models[provider],
                        "mode": "pattern_discovery",
                        "cases_reviewed": batch_packet["cases_reviewed"],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": False,
                        "api_call_made": 1,
                        "raw_label_text": raw_text,
                        "raw_label_sha256": _sha256_text(raw_text),
                        "raw_response_json": json.dumps({**api_meta, **provider_details}, sort_keys=True),
                        "api_error": "",
                        **provider_details,
                    }
                )
                parsed_rows.append(
                    {
                        "request_id": request_row["request_id"],
                        "case_id": batch_id,
                        "batch_id": batch_id,
                        "provider": provider,
                        "model": provider_models[provider],
                        "mode": "pattern_discovery",
                        "cases_reviewed": batch_packet["cases_reviewed"],
                        "top_patterns": parsed_pattern["top_patterns"],
                        "recommended_taxonomy_changes": parsed_pattern["recommended_taxonomy_changes"],
                        "what_extra_metadata_is_needed": parsed_pattern["what_extra_metadata_is_needed"],
                        "do_not_claim": parsed_pattern["do_not_claim"],
                        "prompt_template_id": request_row["prompt_template_id"],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": False,
                        "api_call_made": 1,
                        "label_status": label_status,
                        "pattern_valid": bool(parsed_pattern.get("pattern_valid")),
                        "pattern_errors": list(parsed_pattern.get("pattern_errors") or []),
                        "label_valid": bool(parsed_pattern.get("label_valid")),
                        "label_errors": list(parsed_pattern.get("label_errors") or []),
                        **provider_details,
                    }
                )
            except Exception as exc:
                error_text = _sanitize_error_message(str(exc))
                provider_details = _provider_error_details(label_status="api_error", api_error=error_text)
                raw_rows.append(
                    {
                        "request_id": request_row["request_id"],
                        "case_id": batch_id,
                        "batch_id": batch_id,
                        "provider": provider,
                        "model": provider_models[provider],
                        "mode": "pattern_discovery",
                        "cases_reviewed": batch_packet["cases_reviewed"],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": False,
                        "api_call_made": 1,
                        "raw_label_text": "",
                        "raw_label_sha256": "",
                        "raw_response_json": json.dumps(
                            {
                                "error": error_text,
                                **_exception_api_meta(
                                    exc,
                                    provider=provider,
                                    model=provider_models[provider],
                                    requested_max_output_tokens=provider_max_output_tokens[provider],
                                ),
                                **provider_details,
                            },
                            sort_keys=True,
                        ),
                        "api_error": error_text,
                        **provider_details,
                    }
                )
                parsed_rows.append(
                    {
                        "request_id": request_row["request_id"],
                        "case_id": batch_id,
                        "batch_id": batch_id,
                        "provider": provider,
                        "model": provider_models[provider],
                        "mode": "pattern_discovery",
                        "cases_reviewed": batch_packet["cases_reviewed"],
                        "top_patterns": [],
                        "recommended_taxonomy_changes": [],
                        "what_extra_metadata_is_needed": [],
                        "do_not_claim": [],
                        "prompt_template_id": request_row["prompt_template_id"],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": False,
                        "api_call_made": 1,
                        "label_status": "api_error",
                        "api_error": error_text,
                        "pattern_valid": False,
                        "pattern_errors": [error_text],
                        "label_valid": False,
                        "label_errors": [error_text],
                        **provider_details,
                    }
                )

        manifest = {
            "experiment_id": "failure_mechanism_multi_api_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "script": "scripts/label_failure_mechanisms_multi_api.py",
            "mode": "pattern_discovery",
            "allow_api": allow_api,
            "dry_run": dry_run,
            "check_provider_config": check_provider_config,
            "api_clients_constructed": api_clients_constructed,
            "max_calls_total": max_calls_total,
            "limit": limit_value,
            "providers": providers,
            "provider_models": provider_models,
            "provider_max_output_tokens": provider_max_output_tokens,
            "max_output_tokens_override": max_output_tokens_override,
            "provider_caps": provider_caps,
            "provider_config_summary": provider_config_summary,
            "packet_completeness_summary": packet_completeness_summary,
            "include_gold_for_labeling": bool(args.include_gold_for_labeling),
            "gold_assisted": bool(args.include_gold_for_labeling),
            "subset_specs": subset_specs,
            "subset_names": subsets,
            "subset_case_counts": {spec["subset"]: len(spec["case_ids"]) for spec in subset_specs},
            "prelimit_unique_case_count": prelimit_unique_case_count,
            "requested_case_count": prelimit_unique_case_count,
            "selected_case_count": len(case_packets),
            "unique_case_count": len(case_packets),
            "batch_count": len(batch_packets),
            "provider_batch_count": len(providers),
            "planned_request_count": len(request_rows),
            "expected_request_count": len(providers),
            "api_call_count": total_calls,
            "failure_csv": str(failure_csv),
            "gold_absent_csv": str(gold_absent_csv),
            "anchor_effect_csv": str(anchor_effect_csv),
            "target_audit_jsonl": str(target_audit_jsonl),
            "diagnostic_30_jsonl": str(diagnostic_30_jsonl),
            "target_staged_15_jsonl": str(target_staged_15_jsonl),
            "structural_feature_csv": str(resolved_structural_csv) if resolved_structural_csv else "",
            "output_files": [
                "manifest.json",
                "trace_packets.jsonl",
                "provider_requests_dry_run.jsonl",
                "raw_provider_labels.jsonl",
                "parsed_labels.jsonl",
                "pattern_summary.json",
                "packet_completeness_summary.json",
                "report.md",
            ],
            "pattern_schema": {
                "provider_values": sorted(SUPPORTED_PROVIDERS),
                "failure_stage_values": sorted(PATTERN_FAILURE_STAGES),
            },
            "selection_notes": [
                "diagnostic_30 and target_staged_15 are exact JSONL slices.",
                "pal_still_failing_157 is derived from the full failure CSV and trimmed to 157 if necessary.",
                "wrong_supported_consensus_97 is derived from the gold-absent CSV rows with external_contrast == Both wrong and trimmed to 97 if necessary.",
                "direct_l1_anchor_potential_43 is derived from the anchor-effect CSV rows with strong anchor evidence and trimmed to 43 if necessary.",
                "Pattern discovery batches are hypotheses until manually audited.",
            ],
            "no_api_clients_constructed": not api_clients_constructed,
        }

        _build_pattern_outputs(
            batch_packets=batch_packets,
            providers=providers,
            provider_models=provider_models,
            provider_caps=provider_caps,
            allow_api=allow_api,
            include_gold_for_labeling=bool(args.include_gold_for_labeling),
            max_calls_total=max_calls_total,
            prompt_packets=prompt_packets,
            request_rows=request_rows,
            raw_rows=raw_rows,
            parsed_rows=parsed_rows,
            packet_completeness_summary=packet_completeness_summary,
            output_dir=output_dir,
            manifest=manifest,
        )
        return 0

    if allow_api:
        missing_models = [provider for provider in providers if provider in {"cerebras", "fireworks"} and not provider_models.get(provider)]
        if missing_models:
            raise ValueError(
                "Live API mode requires explicit --cerebras-model and --fireworks-model for selected providers; missing: "
                + ", ".join(sorted(missing_models))
            )
        missing_env = [provider for provider in providers if not _provider_env_ready(provider)]
        if missing_env:
            raise ValueError(
                "Live API mode requires provider environment variables for selected providers; missing or empty env for: "
                + ", ".join(sorted(missing_env))
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    request_rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    parsed_rows: list[dict[str, Any]] = []
    total_calls = 0
    provider_call_counts: Counter[str] = Counter()
    provider_request_counts: Counter[str] = Counter()
    api_clients_constructed = False

    if allow_api and not dry_run:
        api_clients_constructed = True

    for packet in case_packets:
        prompt_text = _render_prompt(packet)
        for provider in providers:
            if not dry_run and total_calls >= max_calls_total:
                raise RuntimeError(f"Hard call cap reached before processing {packet['case_id']} / {provider}")
            provider_request_counts[provider] += 1
            request_row = _build_provider_request(
                provider=provider,
                model=provider_models[provider],
                case_packet=packet,
                prompt_text=prompt_text,
                request_index=provider_request_counts[provider],
                provider_cap=provider_caps.get(provider, 0),
                max_output_tokens=provider_max_output_tokens[provider],
                dry_run=dry_run,
                include_gold_for_labeling=bool(args.include_gold_for_labeling),
            )
            request_rows.append(request_row)
            if dry_run:
                raw_row = {
                    "request_id": request_row["request_id"],
                    "case_id": packet["case_id"],
                    "provider": provider,
                    "model": provider_models[provider],
                    "prompt_sha256": request_row["prompt_sha256"],
                    "request_sha256": request_row["request_sha256"],
                    "dry_run": True,
                    "api_call_made": 0,
                    "raw_label_text": "",
                    "raw_label_sha256": "",
                    "raw_response_json": "",
                    "api_error": "",
                    "provider_readiness": "dry_run",
                    "provider_http_status": "",
                    "provider_error_code": "",
                    "provider_error_message_short": "",
                }
                parsed_row = {
                    "request_id": request_row["request_id"],
                    "case_id": packet["case_id"],
                    "provider": provider,
                    "model": provider_models[provider],
                    "subset_memberships": json.dumps(packet["subset_memberships"], sort_keys=True),
                    "primary_subset": packet["primary_subset"],
                    "prompt_template_id": packet["prompt_template_id"],
                    "prompt_sha256": request_row["prompt_sha256"],
                    "request_sha256": request_row["request_sha256"],
                    "dry_run": True,
                    "api_call_made": 0,
                    "label_status": "dry_run",
                    "primary_label": "",
                    "secondary_labels": [],
                    "selector_vs_generation": "",
                    "candidate_pool_status": "",
                    "confidence": "",
                    "evidence": "",
                    "recommended_fix_family": "",
                    "label_valid": False,
                    "label_errors": ["dry_run"],
                    "provider_readiness": "dry_run",
                    "provider_http_status": "",
                    "provider_error_code": "",
                    "provider_error_message_short": "",
                }
                raw_rows.append(raw_row)
                parsed_rows.append(parsed_row)
                continue

            total_calls += 1
            provider_call_counts[provider] += 1
            try:
                raw_text, api_meta = _call_provider_api(
                    provider=provider,
                    model=provider_models[provider],
                    prompt=prompt_text,
                    mode=mode,
                    max_output_tokens=provider_max_output_tokens[provider],
                )
                parsed_label, parse_error = _parse_label_json(raw_text)
                if parsed_label is None:
                    provider_details = _provider_error_details(
                        label_status="parse_error",
                        api_error=raw_text,
                        label_parse_error=parse_error,
                    )
                    parsed_row = {
                        "request_id": request_row["request_id"],
                        "case_id": packet["case_id"],
                        "provider": provider,
                        "model": provider_models[provider],
                        "subset_memberships": json.dumps(packet["subset_memberships"], sort_keys=True),
                        "primary_subset": packet["primary_subset"],
                        "prompt_template_id": packet["prompt_template_id"],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": False,
                        "api_call_made": 1,
                        "label_status": "parse_error",
                        "label_parse_error": parse_error,
                        "primary_label": "",
                        "secondary_labels": [],
                        "selector_vs_generation": "",
                        "candidate_pool_status": "",
                        "confidence": "",
                        "evidence": "",
                        "recommended_fix_family": "",
                        "label_valid": False,
                        "label_errors": [parse_error],
                        **provider_details,
                    }
                    raw_rows.append(
                        {
                            "request_id": request_row["request_id"],
                            "case_id": packet["case_id"],
                            "provider": provider,
                            "model": provider_models[provider],
                            "prompt_sha256": request_row["prompt_sha256"],
                            "request_sha256": request_row["request_sha256"],
                            "dry_run": False,
                            "api_call_made": 1,
                            "raw_label_text": raw_text,
                            "raw_label_sha256": _sha256_text(raw_text),
                            "raw_response_json": json.dumps({**api_meta, **provider_details}, sort_keys=True),
                            "api_error": "",
                            **provider_details,
                        }
                    )
                    parsed_rows.append(parsed_row)
                    continue

                provider_details = _provider_error_details(
                    label_status="parsed" if parsed_label.get("label_valid") else "parse_error",
                    api_error="",
                    label_parse_error="" if parsed_label.get("label_valid") else "invalid_label_schema",
                )
                label_status = "parsed" if parsed_label.get("label_valid") else "parse_error"
                raw_rows.append(
                    {
                        "request_id": request_row["request_id"],
                        "case_id": packet["case_id"],
                        "provider": provider,
                        "model": provider_models[provider],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": False,
                        "api_call_made": 1,
                        "raw_label_text": raw_text,
                        "raw_label_sha256": _sha256_text(raw_text),
                        "raw_response_json": json.dumps({**api_meta, **provider_details}, sort_keys=True),
                        "api_error": "",
                        **provider_details,
                    }
                )
                parsed_rows.append(
                    {
                        "request_id": request_row["request_id"],
                        "case_id": packet["case_id"],
                        "provider": provider,
                        "model": provider_models[provider],
                        "subset_memberships": json.dumps(packet["subset_memberships"], sort_keys=True),
                        "primary_subset": packet["primary_subset"],
                        "prompt_template_id": packet["prompt_template_id"],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": False,
                        "api_call_made": 1,
                        "label_status": label_status,
                        **parsed_label,
                        "label_parse_error": "" if label_status == "parsed" else "invalid_label_schema",
                        **provider_details,
                    }
                )
            except Exception as exc:
                error_text = _sanitize_error_message(str(exc))
                provider_details = _provider_error_details(label_status="api_error", api_error=error_text)
                raw_rows.append(
                    {
                        "request_id": request_row["request_id"],
                        "case_id": packet["case_id"],
                        "provider": provider,
                        "model": provider_models[provider],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": False,
                        "api_call_made": 1,
                        "raw_label_text": "",
                        "raw_label_sha256": "",
                        "raw_response_json": json.dumps(
                            {
                                "error": error_text,
                                **_exception_api_meta(
                                    exc,
                                    provider=provider,
                                    model=provider_models[provider],
                                    requested_max_output_tokens=provider_max_output_tokens[provider],
                                ),
                                **provider_details,
                            },
                            sort_keys=True,
                        ),
                        "api_error": error_text,
                        **provider_details,
                    }
                )
                parsed_rows.append(
                    {
                        "request_id": request_row["request_id"],
                        "case_id": packet["case_id"],
                        "provider": provider,
                        "model": provider_models[provider],
                        "subset_memberships": json.dumps(packet["subset_memberships"], sort_keys=True),
                        "primary_subset": packet["primary_subset"],
                        "prompt_template_id": packet["prompt_template_id"],
                        "prompt_sha256": request_row["prompt_sha256"],
                        "request_sha256": request_row["request_sha256"],
                        "dry_run": False,
                        "api_call_made": 1,
                        "label_status": "api_error",
                        "api_error": error_text,
                        "primary_label": "",
                        "secondary_labels": [],
                        "selector_vs_generation": "",
                        "candidate_pool_status": "",
                        "confidence": "",
                        "evidence": "",
                        "recommended_fix_family": "",
                        "label_valid": False,
                        "label_errors": [error_text],
                        **provider_details,
                    }
                )

    manifest = {
        "experiment_id": "failure_mechanism_multi_api_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/label_failure_mechanisms_multi_api.py",
        "allow_api": allow_api,
        "dry_run": dry_run,
        "check_provider_config": check_provider_config,
        "api_clients_constructed": api_clients_constructed,
        "max_calls_total": max_calls_total,
        "limit": limit_value,
        "providers": providers,
        "provider_models": provider_models,
        "provider_max_output_tokens": provider_max_output_tokens,
        "max_output_tokens_override": max_output_tokens_override,
        "provider_caps": provider_caps,
        "provider_config_summary": provider_config_summary,
        "packet_completeness_summary": packet_completeness_summary,
        "include_gold_for_labeling": bool(args.include_gold_for_labeling),
        "gold_assisted": bool(args.include_gold_for_labeling),
        "subset_specs": subset_specs,
        "subset_names": subsets,
        "subset_case_counts": {spec["subset"]: len(spec["case_ids"]) for spec in subset_specs},
        "prelimit_unique_case_count": prelimit_unique_case_count,
        "requested_case_count": prelimit_unique_case_count,
        "selected_case_count": len(case_packets),
        "unique_case_count": len(case_packets),
        "planned_request_count": len(request_rows),
        "expected_request_count": len(case_packets) * len(providers),
        "api_call_count": total_calls,
        "failure_csv": str(failure_csv),
        "gold_absent_csv": str(gold_absent_csv),
        "anchor_effect_csv": str(anchor_effect_csv),
        "target_audit_jsonl": str(target_audit_jsonl),
        "diagnostic_30_jsonl": str(diagnostic_30_jsonl),
        "target_staged_15_jsonl": str(target_staged_15_jsonl),
        "structural_feature_csv": str(resolved_structural_csv) if resolved_structural_csv else "",
        "output_files": [
            "manifest.json",
            "trace_packets.jsonl",
            "provider_requests_dry_run.jsonl",
            "raw_provider_labels.jsonl",
            "parsed_labels.jsonl",
            "agreement_summary.json",
            "packet_completeness_summary.json",
            "label_frequency_summary.csv",
            "case_label_matrix.csv",
            "disagreement_cases.csv",
            "report.md",
        ],
        "label_schema": {
            "fields": LABEL_FIELDS,
            "primary_label_values": sorted(PRIMARY_LABELS),
            "secondary_label_values": sorted(SECONDARY_LABELS),
            "selector_vs_generation_values": sorted(SELECTOR_VS_GENERATION),
            "candidate_pool_status_values": sorted(POOL_STATUS),
            "recommended_fix_family_values": sorted(FIX_FAMILIES),
        },
        "selection_notes": [
            "diagnostic_30 and target_staged_15 are exact JSONL slices.",
            "pal_still_failing_157 is derived from the full failure CSV and trimmed to 157 if necessary.",
            "wrong_supported_consensus_97 is derived from the gold-absent CSV rows with external_contrast == Both wrong and trimmed to 97 if necessary.",
            "direct_l1_anchor_potential_43 is derived from the anchor-effect CSV rows with strong anchor evidence and trimmed to 43 if necessary.",
        ],
        "no_api_clients_constructed": not api_clients_constructed,
    }

    agreement_summary = _build_outputs(
        case_packets=case_packets,
        providers=providers,
        provider_models=provider_models,
        provider_caps=provider_caps,
        allow_api=allow_api,
        include_gold_for_labeling=bool(args.include_gold_for_labeling),
        max_calls_total=max_calls_total,
        prompt_packets=prompt_packets,
        request_rows=request_rows,
        raw_rows=raw_rows,
        parsed_rows=parsed_rows,
        packet_completeness_summary=packet_completeness_summary,
        output_dir=output_dir,
        manifest=manifest,
    )

    report_lines = [
        "# Multi-API Failure Mechanism Labeling Plan",
        "",
        "## Run Mode",
        "",
        f"- allow_api: `{allow_api}`",
        f"- dry_run: `{dry_run}`",
        f"- api_clients_constructed: `{api_clients_constructed}`",
        f"- include_gold_for_labeling: `{bool(args.include_gold_for_labeling)}`",
        f"- max_calls_total: `{max_calls_total}`",
        f"- limit: `{limit_value}`",
        f"- providers: `{', '.join(providers)}`",
        f"- provider_caps: `{json.dumps(provider_caps, sort_keys=True)}`",
        "",
        "## Inputs",
        "",
        f"- failure_csv: `{failure_csv}`",
        f"- gold_absent_csv: `{gold_absent_csv}`",
        f"- anchor_effect_csv: `{anchor_effect_csv}`",
        f"- target_audit_jsonl: `{target_audit_jsonl}`",
        f"- diagnostic_30_jsonl: `{diagnostic_30_jsonl}`",
        f"- target_staged_15_jsonl: `{target_staged_15_jsonl}`",
        f"- structural_feature_csv: `{resolved_structural_csv}`",
        "",
        "## Provider Config",
        "",
    ]
    for provider in providers:
        config = provider_config_summary.get(provider, {})
        report_lines.append(
            f"- `{provider}`: env_ready `{config.get('env_ready')}`; model `{config.get('model')}`; config_ready `{config.get('config_ready')}`"
        )
        env_presence = config.get("env_presence", {})
        if isinstance(env_presence, dict):
            for env_name, present in sorted(env_presence.items()):
                report_lines.append(f"  - {env_name}: `{present}`")
    report_lines.extend(
        [
            "",
            "## Selected Slices",
            "",
        ]
    )
    for spec in subset_specs:
        report_lines.append(
            f"- `{spec['subset']}`: raw `{spec['raw_count']}` -> selected `{spec['selected_count']}`; approximate `{spec['approximate']}`"
        )
        report_lines.append(f"  - logic: {spec['selection_logic']}")
    report_lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- requested_case_count: `{prelimit_unique_case_count}`",
            f"- selected_case_count: `{len(case_packets)}`",
            f"- unique_case_count: `{len(case_packets)}`",
            f"- planned_request_count: `{len(request_rows)}`",
            f"- expected_request_count: `{len(case_packets) * len(providers)}`",
            f"- api_call_count: `{total_calls}`",
            "",
            "## Packet Completeness",
            "",
            f"- question_present_rate: `{packet_completeness_summary.get('question_present_rate', 0.0)}`",
            f"- prediction_present_rate: `{packet_completeness_summary.get('prediction_present_rate', 0.0)}`",
            f"- candidate_pool_present_rate: `{packet_completeness_summary.get('candidate_pool_present_rate', 0.0)}`",
            f"- action_trace_present_rate: `{packet_completeness_summary.get('action_trace_present_rate', 0.0)}`",
            f"- pal_execution_present_rate: `{packet_completeness_summary.get('pal_execution_present_rate', 0.0)}`",
            f"- structural_fields_present_rate: `{packet_completeness_summary.get('structural_fields_present_rate', 0.0)}`",
            f"- empty_packet_count: `{packet_completeness_summary.get('empty_packet_count', 0)}`",
            f"- per_subset: `{json.dumps(packet_completeness_summary.get('per_subset', {}), sort_keys=True)}`",
            "",
            "## Agreement Snapshot",
            "",
            f"- all_agree_case_count: `{agreement_summary['all_agree_case_count']}`",
            f"- partial_agree_case_count: `{agreement_summary['partial_agree_case_count']}`",
            f"- disagreement_case_count: `{agreement_summary['disagreement_case_count']}`",
            f"- missing_label_case_count: `{agreement_summary['missing_label_case_count']}`",
            "",
            "## Provider Readiness",
            "",
        ]
    )
    readiness_counts = agreement_summary.get("provider_readiness_counts", {})
    readiness_samples = agreement_summary.get("provider_error_samples", {})
    for provider in providers:
        provider_counts = readiness_counts.get(provider, {})
        report_lines.append(f"- `{provider}`: `{json.dumps(provider_counts, sort_keys=True)}`")
        for sample in readiness_samples.get(provider, []):
            report_lines.append(
                "  - "
                + json.dumps(
                    {
                        "case_id": sample.get("case_id"),
                        "label_status": sample.get("label_status"),
                        "provider_readiness": sample.get("provider_readiness"),
                        "provider_http_status": sample.get("provider_http_status"),
                        "provider_error_code": sample.get("provider_error_code"),
                        "provider_error_message_short": sample.get("provider_error_message_short"),
                    },
                    sort_keys=True,
                )
            )
    report_lines.extend(
        [
            "",
            "## Warnings",
            "",
        ]
    )
    for warning in packet_completeness_summary.get("warnings", []):
        report_lines.append(f"- {warning}")
    report_lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Default mode is no-API dry-run.",
            "- Live mode requires `--allow-api`, explicit providers, selected models for Cerebras/Fireworks, provider env vars, and a total call cap.",
            "- The prompt packet is gold-free unless `--include-gold-for-labeling` is set.",
            "- `--check-provider-config` reports provider env/model readiness without sending requests.",
            "- Approximate slices are documented in the manifest and report because the raw audits do not recover the target counts exactly.",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
