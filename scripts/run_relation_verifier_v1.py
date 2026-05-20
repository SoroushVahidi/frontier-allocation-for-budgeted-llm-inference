#!/usr/bin/env python3
"""
Runner for relation_verifier_v1.

Dry-run is the default. Live mode requires --allow-api. Gold labels are used
only post-hoc if a casebook is supplied.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "relation_verifier_v1"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

_REQUIRED_FIELDS = [
    "target_relation_correct",
    "target_variable_correct",
    "source_facts_sufficient",
    "equations_match_source_facts",
    "process_state_correct",
    "unit_scale_correct",
    "arithmetic_executable",
    "error_type",
    "failed_relation",
    "repair_hint",
    "confidence",
]
_ALLOWED_ERROR_TYPES = {
    "none",
    "wrong_relation",
    "wrong_target_variable",
    "missing_source_fact",
    "wrong_process_state",
    "unit_scale_error",
    "arithmetic_error",
    "format_error",
    "uncertain",
}
_FORBIDDEN_PROMPT_RE = [
    re.compile(r"\bgold_answer\b\s*[:=]", re.I),
    re.compile(r"\banswer_key\b\s*[:=]", re.I),
    re.compile(r"\bhidden[_ -]?labels?\b\s*[:=]", re.I),
    re.compile(r"\bgold\b\s*[:=]", re.I),
    re.compile(r"\bprivate[_ -]?evaluation[_ -]?metadata\b\s*[:=]", re.I),
    re.compile(r"\bdataset[_ -]?annotations?\b\s*[:=]", re.I),
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _default_out_dir() -> Path:
    return Path(os.environ.get("TMPDIR", "/tmp")) / "relation_verifier_v1_dry_run"


def _audit_prompt_for_gold(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _FORBIDDEN_PROMPT_RE)


def _extract_json(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text:
        return None, "empty_response"
    stripped = text.strip()
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj, "direct"
    except json.JSONDecodeError:
        pass
    fence = re.sub(r"```(?:json)?\s*", "", stripped)
    fence = re.sub(r"```\s*$", "", fence).strip()
    try:
        obj = json.loads(fence)
        if isinstance(obj, dict):
            return obj, "fence_stripped"
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj, "extracted"
        except json.JSONDecodeError:
            pass
    return None, "parse_failed"


def _load_provider_requests(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_gold_labels(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            case_id = str(row.get("case_id", "")).strip()
            if not case_id:
                continue
            value = row.get("gold_answer") or row.get("gold") or row.get("correct_answer") or ""
            out[case_id] = str(value).strip()
    return out


def _safe_repr(obj: Any, limit: int = 400) -> str:
    try:
        text = repr(obj)
    except Exception as exc:
        text = f"<repr_failed:{type(exc).__name__}>"
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def _public_attrs(obj: Any, limit: int = 40) -> list[str]:
    try:
        attrs = [name for name in dir(obj) if not name.startswith("_")]
    except Exception:
        return []
    return sorted(attrs)[:limit]


def _to_mapping(obj: Any) -> Mapping[str, Any] | None:
    if isinstance(obj, Mapping):
        return obj
    for attr_name in ("model_dump", "dict"):
        method = getattr(obj, attr_name, None)
        if callable(method):
            try:
                value = method()
            except Exception:
                continue
            if isinstance(value, Mapping):
                return value
    return None


def _get_field(obj: Any, field: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(field)
    return getattr(obj, field, None)


def _extract_text_from_content_blocks(content: Any, source: str) -> tuple[str, str, str | None]:
    if isinstance(content, str):
        return content, source, None if content.strip() else f"empty_text:{source}"
    if isinstance(content, list):
        parts: list[str] = []
        for idx, block in enumerate(content):
            if isinstance(block, str):
                if block.strip():
                    parts.append(block)
                continue
            text = _get_field(block, "text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
                continue
            nested = _get_field(block, "content")
            if isinstance(nested, str) and nested.strip():
                parts.append(nested)
        if parts:
            return "\n".join(parts), source, None
        return "", source, f"empty_text:{source}"
    return "", source, f"unsupported_content:{source}"


def _extract_cohere_text(response: Any) -> tuple[str, str, str | None]:
    checks: list[tuple[str, Any]] = [
        ("response.text", _get_field(response, "text")),
        ("response.message", _get_field(response, "message")),
        ("response.content", _get_field(response, "content")),
    ]
    response_mapping = _to_mapping(response)
    if response_mapping is not None:
        checks.extend(
            [
                ("dict.text", response_mapping.get("text")),
                ("dict.message", response_mapping.get("message")),
                ("dict.content", response_mapping.get("content")),
                ("dict.generations", response_mapping.get("generations")),
                ("dict.response", response_mapping.get("response")),
            ]
        )
    generations = _get_field(response, "generations")
    if generations is not None:
        checks.append(("response.generations", generations))
    nested_response = _get_field(response, "response")
    if nested_response is not None:
        checks.append(("response.response", nested_response))

    first_issue: str | None = None
    for source, value in checks:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value, source, None
            if first_issue is None:
                first_issue = f"empty_text:{source}"
            continue
        if source.endswith("message"):
            message_text = _get_field(value, "text")
            if isinstance(message_text, str) and message_text.strip():
                return message_text, f"{source}.text", None
            message_content = _get_field(value, "content")
            if message_content is not None:
                text, content_source, issue = _extract_text_from_content_blocks(message_content, f"{source}.content")
                if text:
                    return text, content_source, None
                if issue and first_issue is None:
                    first_issue = issue
            message_message = _get_field(value, "message")
            if isinstance(message_message, str) and message_message.strip():
                return message_message, f"{source}.message", None
        if source.endswith("content"):
            text, content_source, issue = _extract_text_from_content_blocks(value, source)
            if text:
                return text, content_source, None
            if issue and first_issue is None:
                first_issue = issue
            continue
        if source.endswith("generations") and isinstance(value, list) and value:
            first = value[0]
            text = _get_field(first, "text")
            if isinstance(text, str) and text.strip():
                return text, f"{source}[0].text", None
            if first_issue is None:
                first_issue = f"empty_text:{source}[0].text"
            continue
        if source.endswith("response"):
            nested_text = _get_field(value, "text")
            if isinstance(nested_text, str) and nested_text.strip():
                return nested_text, f"{source}.text", None
            nested_message = _get_field(value, "message")
            if nested_message is not None:
                message_text = _get_field(nested_message, "text")
                if isinstance(message_text, str) and message_text.strip():
                    return message_text, f"{source}.message.text", None
                message_content = _get_field(nested_message, "content")
                if message_content is not None:
                    text, content_source, issue = _extract_text_from_content_blocks(
                        message_content, f"{source}.message.content"
                    )
                    if text:
                        return text, content_source, None
                    if issue and first_issue is None:
                        first_issue = issue
        mapping_value = _to_mapping(value)
        if mapping_value is not None and "text" in mapping_value:
            mapped_text = mapping_value.get("text")
            if isinstance(mapped_text, str) and mapped_text.strip():
                return mapped_text, f"{source}.text", None
            if first_issue is None:
                first_issue = f"empty_text:{source}.text"
    return "", "unavailable", first_issue or "no_text_found"


def _casebook_lookup_candidates(case_id: str) -> list[str]:
    normalized = str(case_id).strip()
    candidates = [normalized]
    if normalized.startswith("openai_"):
        candidates.append(normalized[len("openai_") :])
    elif normalized:
        candidates.append(f"openai_{normalized}")
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _lookup_gold_label(case_id: str, gold_labels: dict[str, str]) -> tuple[str, str | None]:
    for candidate_id in _casebook_lookup_candidates(case_id):
        if candidate_id in gold_labels:
            return gold_labels[candidate_id], candidate_id
    return "", None


def _validate_response(obj: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    result: dict[str, Any] = {}
    if not isinstance(obj, dict):
        return {
            "schema_ok": False,
            "issues": ["response_not_object"],
        }
    for field in _REQUIRED_FIELDS:
        if field not in obj:
            issues.append(f"missing_field:{field}")
    bool_fields = [
        "target_relation_correct",
        "target_variable_correct",
        "source_facts_sufficient",
        "equations_match_source_facts",
        "process_state_correct",
        "unit_scale_correct",
        "arithmetic_executable",
    ]
    for field in bool_fields:
        value = obj.get(field)
        if not isinstance(value, bool):
            issues.append(f"invalid_bool:{field}")
            value = bool(value) if value is not None else False
        result[field] = value
    error_type = str(obj.get("error_type", "")).strip()
    if error_type not in _ALLOWED_ERROR_TYPES:
        issues.append("invalid_error_type")
    confidence = obj.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        issues.append("invalid_confidence")
        confidence = 0.0
    else:
        confidence = float(confidence)
    result.update(
        {
            "error_type": error_type if error_type in _ALLOWED_ERROR_TYPES else "format_error",
            "failed_relation": str(obj.get("failed_relation", "")).strip(),
            "repair_hint": str(obj.get("repair_hint", "")).strip(),
            "confidence": confidence,
            "schema_ok": not issues,
            "issues": issues,
        }
    )
    return result


def parse_relation_verifier_response(obj: dict[str, Any]) -> dict[str, Any]:
    return _validate_response(obj)


def _call_cohere(client: Any, model: str, prompt: str, max_tokens: int, temperature: float) -> tuple[str, dict[str, Any], dict[str, Any]]:
    response = client.chat(
        model=model,
        message=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text, extraction_source, extraction_issue = _extract_cohere_text(response)
    usage: dict[str, Any] = {}
    usage_obj = _get_field(response, "usage") or _get_field(response, "meta")
    if usage_obj:
        try:
            usage = json.loads(json.dumps(usage_obj, default=str))
        except Exception:
            usage = {"raw": _safe_repr(usage_obj)}
    diagnostics = {
        "response_type": type(response).__name__,
        "response_public_attrs": _public_attrs(response),
        "response_repr": _safe_repr(response),
        "extraction_source": extraction_source,
        "extraction_issue": extraction_issue,
    }
    return text, usage, diagnostics


def _process_case(
    *,
    req: dict[str, Any],
    gold_labels: dict[str, str],
    client: Any | None,
    model: str,
    max_tokens: int,
    temperature: float,
    call_index: int,
    dry_run: bool,
) -> tuple[dict[str, Any], int]:
    case_id = str(req.get("case_id", "")).strip()
    prompt_text = str(req.get("prompt_text", ""))
    gold_label, gold_label_case_id = _lookup_gold_label(case_id, gold_labels)
    result: dict[str, Any] = {
        "call_index": call_index,
        "case_id": case_id,
        "question": req.get("question", ""),
        "requested_target": req.get("requested_target", ""),
        "prompt_text": prompt_text,
        "prompt_sha256": _sha256(prompt_text),
        "primary_candidate_source": req.get("primary_candidate_source", ""),
        "candidate_sources": req.get("candidate_sources", []),
        "topology_metadata": req.get("topology_metadata", {}),
        "gold_in_prompt": _audit_prompt_for_gold(prompt_text),
        "gold_label_available": bool(gold_label_case_id),
        "gold_label": gold_label if gold_label_case_id else None,
        "casebook_match_id": gold_label_case_id,
    }

    if dry_run:
        result.update(
            {
                "call_ok": None,
                "api_call_made": False,
                "raw_response": None,
                "parse_ok": None,
                "schema_ok": None,
                "target_relation_correct": None,
                "target_variable_correct": None,
                "source_facts_sufficient": None,
                "equations_match_source_facts": None,
                "process_state_correct": None,
                "unit_scale_correct": None,
                "arithmetic_executable": None,
                "error_type": None,
                "failed_relation": None,
                "repair_hint": None,
                "confidence": None,
                "issues": ["dry_run"],
            }
        )
        return result, 0

    result["api_call_made"] = True
    try:
        raw_text, usage, diagnostics = _call_cohere(client, model, prompt_text, max_tokens, temperature)
        result["raw_response"] = raw_text
        result["usage"] = usage
        result.update(diagnostics)
        result["call_ok"] = True
        result["call_error"] = None
    except Exception as exc:
        result.update(
            {
                "raw_response": "",
                "usage": {},
                "response_type": None,
                "response_public_attrs": [],
                "response_repr": None,
                "extraction_source": "call_failed",
                "extraction_issue": f"call_failed:{type(exc).__name__}",
                "call_ok": False,
                "call_error": f"{type(exc).__name__}: {str(exc)[:200]}",
                "parse_ok": False,
                "schema_ok": False,
                "target_relation_correct": False,
                "target_variable_correct": False,
                "source_facts_sufficient": False,
                "equations_match_source_facts": False,
                "process_state_correct": False,
                "unit_scale_correct": False,
                "arithmetic_executable": False,
                "error_type": "format_error",
                "failed_relation": "",
                "repair_hint": "",
                "confidence": 0.0,
                "issues": ["call_failed"],
            }
        )
        return result, 1

    obj, parse_method = _extract_json(result["raw_response"])
    result["parse_ok"] = obj is not None
    result["parse_method"] = parse_method
    if obj is None:
        issue_tag = f"json_parse_failed:{parse_method}"
        result.update(
            {
                "schema_ok": False,
                "target_relation_correct": False,
                "target_variable_correct": False,
                "source_facts_sufficient": False,
                "equations_match_source_facts": False,
                "process_state_correct": False,
                "unit_scale_correct": False,
                "arithmetic_executable": False,
                "error_type": "format_error",
                "failed_relation": "",
                "repair_hint": "",
                "confidence": 0.0,
                "issues": [issue_tag],
            }
        )
        return result, 1

    parsed = parse_relation_verifier_response(obj)
    result.update(parsed)
    issues = list(parsed.get("issues", []))
    if not parsed.get("schema_ok", False) and "schema_invalid" not in issues:
        issues.append("schema_invalid")
    result["issues"] = issues
    result["call_ok"] = True
    result["api_call_made"] = True
    return result, 1


def _summarize_results(
    *,
    results: list[dict[str, Any]],
    n_loaded: int,
    total_api_calls: int,
    args: argparse.Namespace,
    gold_labels: dict[str, str],
    gold_in_any_prompt: bool,
    report_name: str,
) -> dict[str, Any]:
    counts = Counter()
    error_counts = Counter()
    for row in results:
        if row.get("parse_ok") is True:
            counts["json_parse_ok_count"] += 1
        if row.get("schema_ok") is True:
            counts["schema_ok_count"] += 1
        if row.get("target_relation_correct") is True:
            counts["target_relation_correct_count"] += 1
        if row.get("target_variable_correct") is True:
            counts["target_variable_correct_count"] += 1
        if row.get("source_facts_sufficient") is True:
            counts["source_facts_sufficient_count"] += 1
        if row.get("equations_match_source_facts") is True:
            counts["equations_match_source_facts_count"] += 1
        if row.get("process_state_correct") is True:
            counts["process_state_correct_count"] += 1
        if row.get("unit_scale_correct") is True:
            counts["unit_scale_correct_count"] += 1
        if row.get("arithmetic_executable") is True:
            counts["arithmetic_executable_count"] += 1
        if row.get("gold_label_available") is True:
            counts["gold_label_available_count"] += 1
        error_value = row.get("error_type")
        if isinstance(error_value, str):
            error = error_value.strip()
            if error:
                error_counts[error] += 1
        for issue in row.get("issues", []):
            if isinstance(issue, str):
                counts["issue_summary:" + issue.split(":", 1)[0]] += 1

    issue_summary: dict[str, int] = {}
    for row in results:
        for issue in row.get("issues", []):
            if isinstance(issue, str):
                key = issue.split(":", 1)[0]
                issue_summary[key] = issue_summary.get(key, 0) + 1
    if not issue_summary and total_api_calls == 0:
        issue_summary["dry_run"] = n_loaded

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "mode": "live" if args.allow_api else "dry_run",
        "model": args.model,
        "provider": "cohere",
        "provider_requests_input": str(args.provider_requests),
        "casebook_input": str(args.casebook) if args.casebook else None,
        "cases_in_requests": n_loaded,
        "cases_attempted": n_loaded,
        "api_calls_made": total_api_calls,
        "calls_attempted": total_api_calls,
        "calls_succeeded": sum(1 for row in results if row.get("call_ok") is True),
        "json_parse_ok_count": counts.get("json_parse_ok_count", 0),
        "schema_ok_count": counts.get("schema_ok_count", 0),
        "target_relation_correct_count": counts.get("target_relation_correct_count", 0),
        "target_variable_correct_count": counts.get("target_variable_correct_count", 0),
        "source_facts_sufficient_count": counts.get("source_facts_sufficient_count", 0),
        "equations_match_source_facts_count": counts.get("equations_match_source_facts_count", 0),
        "process_state_correct_count": counts.get("process_state_correct_count", 0),
        "unit_scale_correct_count": counts.get("unit_scale_correct_count", 0),
        "arithmetic_executable_count": counts.get("arithmetic_executable_count", 0),
        "gold_label_available_count": counts.get("gold_label_available_count", 0),
        "gold_label_coverage": f"{counts.get('gold_label_available_count', 0)}/{n_loaded}" if n_loaded else "0/0",
        "error_type_counts": dict(error_counts),
        "issue_summary": issue_summary if issue_summary else {"dry_run": n_loaded} if total_api_calls == 0 else {},
        "gold_labels_available": len(gold_labels),
        "gold_in_any_prompt": gold_in_any_prompt,
        "verifier_precision": None,
        "verifier_recall": None,
        "out_dir": str(args.out_dir),
        "outputs": [
            "manifest.json",
            "raw_responses.jsonl",
            "parsed_responses.jsonl",
            "relation_verifier_rows.jsonl",
            "pilot_summary.json",
            report_name,
        ],
    }
    return summary


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-requests", type=Path, required=True)
    parser.add_argument("--casebook", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--allow-api", action="store_true")
    parser.add_argument("--model", type=str, default="command-r-plus-08-2024")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parse_args(argv)
    out_dir = args.out_dir or _default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.provider_requests.is_file():
        print(f"ERROR: provider requests not found: {args.provider_requests}", file=sys.stderr)
        sys.exit(1)

    requests = _load_provider_requests(args.provider_requests)
    gold_labels = _load_gold_labels(args.casebook) if args.casebook and args.casebook.is_file() else {}
    gold_in_any_prompt = any(_audit_prompt_for_gold(str(req.get("prompt_text", ""))) for req in requests)
    dry_run = not args.allow_api

    results: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    parsed_rows: list[dict[str, Any]] = []
    total_api_calls = 0

    client: Any | None = None
    if args.allow_api:
        api_key = os.environ.get("COHERE_API_KEY")
        if not api_key:
            print("ERROR: COHERE_API_KEY is missing", file=sys.stderr)
            sys.exit(1)
        try:
            import cohere

            client = cohere.Client(api_key=api_key)
        except Exception as exc:
            print(f"ERROR: failed to initialize Cohere client: {type(exc).__name__}: {exc}", file=sys.stderr)
            sys.exit(1)

    for idx, req in enumerate(requests, start=1):
        result, api_calls = _process_case(
            req=req,
            gold_labels=gold_labels,
            client=client,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            call_index=idx,
            dry_run=dry_run,
        )
        total_api_calls += api_calls
        results.append(result)
        raw_rows.append(
            {
                "case_id": result.get("case_id", ""),
                "call_index": result.get("call_index"),
                "call_ok": result.get("call_ok"),
                "raw_response": result.get("raw_response"),
                "call_error": result.get("call_error"),
                "usage": result.get("usage"),
                "response_type": result.get("response_type"),
                "response_public_attrs": result.get("response_public_attrs"),
                "response_repr": result.get("response_repr"),
                "extraction_source": result.get("extraction_source"),
                "extraction_issue": result.get("extraction_issue"),
            }
        )
        parsed_rows.append(
            {
                "case_id": result.get("case_id", ""),
                "call_index": result.get("call_index"),
                "parse_ok": result.get("parse_ok"),
                "schema_ok": result.get("schema_ok"),
                "target_relation_correct": result.get("target_relation_correct"),
                "target_variable_correct": result.get("target_variable_correct"),
                "source_facts_sufficient": result.get("source_facts_sufficient"),
                "equations_match_source_facts": result.get("equations_match_source_facts"),
                "process_state_correct": result.get("process_state_correct"),
                "unit_scale_correct": result.get("unit_scale_correct"),
                "arithmetic_executable": result.get("arithmetic_executable"),
                "error_type": result.get("error_type"),
                "failed_relation": result.get("failed_relation"),
                "repair_hint": result.get("repair_hint"),
                "confidence": result.get("confidence"),
                "issues": result.get("issues", []),
            }
        )

    report_name = "live_report.md" if args.allow_api else "dry_run_report.md"
    summary = _summarize_results(
        results=results,
        n_loaded=len(requests),
        total_api_calls=total_api_calls,
        args=args,
        gold_labels=gold_labels,
        gold_in_any_prompt=gold_in_any_prompt,
        report_name=report_name,
    )

    _write_jsonl(out_dir / "raw_responses.jsonl", raw_rows)
    _write_jsonl(out_dir / "parsed_responses.jsonl", parsed_rows)
    _write_jsonl(out_dir / "relation_verifier_rows.jsonl", results)
    _write_json(out_dir / "pilot_summary.json", summary)
    _write_json(out_dir / "manifest.json", summary)

    report_lines = [
        "# Relation Verifier V1 - Dry-Run Report" if not args.allow_api else "# Relation Verifier V1 - Live Report",
        f"**Timestamp:** {_TS}",
        f"**Experiment:** {EXPERIMENT_ID}",
        f"**Mode:** {'live' if args.allow_api else 'dry_run'}",
        f"**Cases:** {len(requests)}",
        f"**Calls attempted / succeeded:** {summary['calls_attempted']}/{summary['calls_succeeded']}",
        f"**JSON parse ok:** {summary['json_parse_ok_count']}",
        f"**Schema ok:** {summary['schema_ok_count']}",
        f"**Issue summary:** {json.dumps(summary['issue_summary'], ensure_ascii=False)}",
    ]
    (out_dir / report_name).write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    main()
