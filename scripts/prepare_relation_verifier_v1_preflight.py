#!/usr/bin/env python3
"""
No-API preflight for relation_verifier_v1.

Builds dry-run provider requests from selected cases and prior-pilot candidate
rows. Gold is never placed in prompt_text.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "relation_verifier_v1"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
PROMPT_TEMPLATE_PATH = REPO_ROOT / "prompts" / "relation_verifier_v1.md"

_FORBIDDEN_PROMPT_RE = [
    re.compile(r"\bgold_answer\b\s*[:=]", re.I),
    re.compile(r"\banswer_key\b\s*[:=]", re.I),
    re.compile(r"\bhidden[_ -]?labels?\b\s*[:=]", re.I),
    re.compile(r"\bgold\b\s*[:=]", re.I),
    re.compile(r"\bprivate[_ -]?evaluation[_ -]?metadata\b\s*[:=]", re.I),
    re.compile(r"\bdataset[_ -]?annotations?\b\s*[:=]", re.I),
]


def _sha256(text: str) -> str:
    import hashlib

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
    return Path(tempfile.gettempdir()) / "relation_verifier_v1_preflight"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_optional_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        return _load_jsonl(path)
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"Unsupported optional-row format: {path}")


def _index_by_case_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = str(row.get("case_id", "")).strip()
        if case_id:
            out[case_id] = row
    return out


def _load_prompt_template() -> str:
    if not PROMPT_TEMPLATE_PATH.is_file():
        raise FileNotFoundError(f"Missing prompt template: {PROMPT_TEMPLATE_PATH}")
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _load_raw_response_rows(path: Path | None, source_name: str) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            case_id = str(obj.get("case_id", "")).strip()
            raw_response = obj.get("raw_response")
            parsed: dict[str, Any] | None = None
            if isinstance(raw_response, str) and raw_response.strip():
                try:
                    parsed_obj = json.loads(raw_response)
                    if isinstance(parsed_obj, dict):
                        parsed = parsed_obj
                except json.JSONDecodeError:
                    parsed = None
            elif isinstance(raw_response, dict):
                parsed = raw_response
            if case_id and parsed:
                parsed["source"] = source_name
                rows[case_id] = parsed
    return rows


def _load_source_candidates(source_dir: Path | None, source_name: str) -> dict[str, dict[str, Any]]:
    if source_dir is None or not source_dir.exists():
        return {}
    raw_path = source_dir / "raw_responses.jsonl"
    if raw_path.exists():
        return _load_raw_response_rows(raw_path, source_name)
    parsed_path = source_dir / "parsed_responses.jsonl"
    if parsed_path.exists():
        out: dict[str, dict[str, Any]] = {}
        for row in _load_jsonl(parsed_path):
            case_id = str(row.get("case_id", "")).strip()
            if case_id:
                row = dict(row)
                row["source"] = source_name
                out[case_id] = row
        return out
    return {}


def _sanitize_declarative_candidate(row: dict[str, Any], source_name: str) -> dict[str, Any]:
    return {
        "source": source_name,
        "requested_target": row.get("requested_target", ""),
        "target_variable": row.get("target_variable", ""),
        "target_unit": row.get("target_unit", ""),
        "process_state": row.get("process_state", ""),
        "source_facts": row.get("source_facts", []),
        "variables": row.get("variables", []),
        "relations": row.get("relations", []),
        "equations": row.get("equations", []),
        "solve_for": row.get("solve_for", ""),
        "solution_formula": row.get("solution_formula", ""),
        "final_answer": row.get("final_answer"),
        "uncertainty": row.get("uncertainty"),
        "abstain_reason": row.get("abstain_reason", ""),
    }


def _sanitize_bftc_candidate(row: dict[str, Any], source_name: str) -> dict[str, Any]:
    return {
        "source": source_name,
        "requested_target": row.get("requested_target", ""),
        "source_facts": row.get("source_facts", []),
        "formula_variables": row.get("formula_variables", {}),
        "solution_formula": row.get("solution_formula", ""),
        "final_answer": row.get("final_answer"),
        "confidence": row.get("confidence", ""),
    }


def _build_candidate_context(
    case_id: str,
    v2_rows: dict[str, dict[str, Any]],
    v1_rows: dict[str, dict[str, Any]],
    bftc_rows: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str, list[str]]:
    candidate_sources: list[str] = []
    supporting_sources: list[str] = []
    primary_source = ""
    primary_candidate: dict[str, Any] | None = None

    if case_id in v2_rows:
        primary_source = "declarative_v2"
        primary_candidate = _sanitize_declarative_candidate(v2_rows[case_id], primary_source)
        candidate_sources.append(primary_source)
    elif case_id in v1_rows:
        primary_source = "declarative_v1"
        primary_candidate = _sanitize_declarative_candidate(v1_rows[case_id], primary_source)
        candidate_sources.append(primary_source)
    elif case_id in bftc_rows:
        primary_source = "bftc_executable"
        primary_candidate = _sanitize_bftc_candidate(bftc_rows[case_id], primary_source)
        candidate_sources.append(primary_source)

    supporting_attempts: dict[str, Any] = {}
    for source_name, source_rows, sanitizer in [
        ("declarative_v2", v2_rows, _sanitize_declarative_candidate),
        ("declarative_v1", v1_rows, _sanitize_declarative_candidate),
        ("bftc_executable", bftc_rows, _sanitize_bftc_candidate),
    ]:
        if source_name == primary_source:
            continue
        if case_id in source_rows:
            supporting_sources.append(source_name)
            candidate_sources.append(source_name)
            supporting_attempts[source_name] = sanitizer(source_rows[case_id], source_name)

    context = {
        "primary_candidate_source": primary_source,
        "supporting_sources": supporting_sources,
        "candidate": primary_candidate or {},
        "supporting_attempts": supporting_attempts,
    }
    return context, primary_source, candidate_sources


def _topology_metadata_without_gold(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    keys = [
        "missing_edge_type",
        "needed_branch_family",
        "tree_topology_label",
        "estimated_steps_from_closest_node_to_gold",
        "label_source",
        "prompt_gold_consistency",
    ]
    return {key: row.get(key) for key in keys if key in row}


def render_prompt(template: str, question: str, requested_target: str, candidate_context: dict[str, Any]) -> str:
    rendered = template.replace("{{question}}", question)
    rendered = rendered.replace("{{requested_target}}", requested_target)
    rendered = rendered.replace("{{candidate_context_json}}", json.dumps(candidate_context, ensure_ascii=False, indent=2, default=str))
    if re.findall(r"\{\{[^}]+\}\}", rendered):
        raise ValueError("Unresolved placeholders remain in prompt template")
    return rendered


def audit_prompt(text: str, case_id: str) -> dict[str, Any]:
    violations = [pattern.pattern for pattern in _FORBIDDEN_PROMPT_RE if pattern.search(text)]
    return {
        "case_id": case_id,
        "gold_free": not violations,
        "forbidden_string_free": not violations,
        "violations": violations,
        "prompt_sha256": _sha256(text),
        "prompt_length": len(text),
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected-cases", type=Path, required=True)
    parser.add_argument("--bftc-exec-dir", type=Path, required=True)
    parser.add_argument("--declarative-v1-dir", type=Path, required=True)
    parser.add_argument("--declarative-v2-dir", type=Path, required=True)
    parser.add_argument("--topology-labels", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parse_args(argv)
    out_dir = args.out_dir or _default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    template = _load_prompt_template()
    if not args.selected_cases.is_file():
        print(f"ERROR: selected cases not found: {args.selected_cases}", file=sys.stderr)
        sys.exit(1)

    cases = _load_jsonl(args.selected_cases)
    if not cases:
        print(f"ERROR: no cases loaded from {args.selected_cases}", file=sys.stderr)
        sys.exit(1)
    cases.sort(key=lambda row: row.get("case_id", ""))
    cases = cases[: args.limit]

    topology_rows = _index_by_case_id(_load_optional_rows(args.topology_labels))
    bftc_rows = _load_source_candidates(args.bftc_exec_dir, "bftc_executable")
    v1_rows = _load_source_candidates(args.declarative_v1_dir, "declarative_v1")
    v2_rows = _load_source_candidates(args.declarative_v2_dir, "declarative_v2")

    provider_requests: list[dict[str, Any]] = []
    selected_cases_out: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    source_counter: dict[str, int] = {}

    for idx, case in enumerate(cases, start=1):
        case_id = str(case.get("case_id", f"case_{idx:04d}")).strip()
        question = str(case.get("question", "")).strip()
        candidate_context, primary_source, candidate_sources = _build_candidate_context(
            case_id=case_id,
            v2_rows=v2_rows,
            v1_rows=v1_rows,
            bftc_rows=bftc_rows,
        )
        requested_target = str(case.get("requested_target", "")).strip()
        if not requested_target:
            primary_candidate = candidate_context.get("candidate") or {}
            requested_target = str(primary_candidate.get("requested_target", "")).strip()
        prompt_text = render_prompt(template, question, requested_target, candidate_context)
        audit = audit_prompt(prompt_text, case_id)
        audits.append(audit)
        for source_name in candidate_sources:
            source_counter[source_name] = source_counter.get(source_name, 0) + 1
        topology_metadata = _topology_metadata_without_gold(topology_rows.get(case_id))

        selected_cases_out.append(
            {
                "case_id": case_id,
                "question": question,
                "requested_target": requested_target,
                "primary_candidate_source": primary_source,
                "candidate_sources": candidate_sources,
                "topology_metadata": topology_metadata,
                "prompt_sha256": audit["prompt_sha256"],
            }
        )
        provider_requests.append(
            {
                "request_id": f"{EXPERIMENT_ID}:{case_id}:{idx:05d}",
                "case_id": case_id,
                "question": question,
                "requested_target": requested_target,
                "prompt_text": prompt_text,
                "candidate_context": candidate_context,
                "primary_candidate_source": primary_source,
                "candidate_sources": candidate_sources,
                "topology_metadata": topology_metadata,
                "topology_metadata_in_prompt": False,
                "dry_run": True,
                "api_call_made": False,
                "prompt_sha256": audit["prompt_sha256"],
                "max_output_tokens": 1024,
                "required_output_fields": [
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
                ],
            }
        )

    _write_jsonl(out_dir / "selected_cases.jsonl", selected_cases_out)
    _write_jsonl(out_dir / "provider_requests_dry_run.jsonl", provider_requests)

    prompt_audit = {
        "case_count": len(audits),
        "all_gold_free": all(audit["gold_free"] for audit in audits),
        "all_forbidden_string_free": all(audit["forbidden_string_free"] for audit in audits),
        "violations": [audit for audit in audits if not audit["forbidden_string_free"]],
        "per_case": audits,
    }
    _write_json(out_dir / "prompt_audit.json", prompt_audit)

    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "selected_cases_input": str(args.selected_cases),
        "bftc_exec_dir_input": str(args.bftc_exec_dir),
        "declarative_v1_dir_input": str(args.declarative_v1_dir),
        "declarative_v2_dir_input": str(args.declarative_v2_dir),
        "topology_labels_input": str(args.topology_labels) if args.topology_labels else None,
        "case_count": len(cases),
        "provider_request_count": len(provider_requests),
        "primary_candidate_sources": source_counter,
        "all_prompts_gold_free": prompt_audit["all_gold_free"],
        "all_prompts_forbidden_string_free": prompt_audit["all_forbidden_string_free"],
        "out_dir": str(out_dir),
        "outputs": [
            "manifest.json",
            "selected_cases.jsonl",
            "provider_requests_dry_run.jsonl",
            "prompt_audit.json",
            "dry_run_report.md",
        ],
    }
    _write_json(out_dir / "manifest.json", manifest)

    report_lines = [
        "# Relation Verifier V1 - Dry-Run Preflight Report",
        f"**Timestamp:** {_TS}",
        f"**Experiment:** {EXPERIMENT_ID}",
        f"**Cases:** {len(cases)}",
        f"**Provider requests:** {len(provider_requests)}",
        f"**Gold free:** {prompt_audit['all_gold_free']}",
        f"**Forbidden-string free:** {prompt_audit['all_forbidden_string_free']}",
        "",
        "## Candidate Source Coverage",
    ]
    for source_name, count in sorted(source_counter.items()):
        report_lines.append(f"- {source_name}: {count}")
    (out_dir / "dry_run_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    main()
