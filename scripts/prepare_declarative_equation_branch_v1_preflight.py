#!/usr/bin/env python3
"""
No-API preflight for declarative_equation_branch_v1.

Renders dry-run provider requests, keeps optional topology labels as offline metadata only,
and audits prompts for gold / answer-key leakage.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
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

EXPERIMENT_ID = "declarative_equation_branch_v1"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
PROMPT_TEMPLATE_PATH = REPO_ROOT / "prompts" / "declarative_equation_branch_v1.md"

_REQUIRED_OUTPUT_FIELDS = [
    "requested_target",
    "target_variable",
    "target_unit",
    "process_state",
    "source_facts",
    "variables",
    "relations",
    "equations",
    "equation_rationale",
    "solve_for",
    "solution_formula",
    "final_answer",
    "uncertainty",
    "abstain_reason",
]
_FORBIDDEN_PROMPT_RE = [
    re.compile(r"\bgold_answer\b\s*[:=]", re.I),
    re.compile(r"\banswer_key\b\s*[:=]", re.I),
    re.compile(r"\bhidden[_ -]?labels?\b\s*[:=]", re.I),
    re.compile(r"\bgold\b\s*[:=]", re.I),
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
    return Path(tempfile.gettempdir()) / "declarative_equation_branch_v1_preflight"


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
    raise ValueError(f"Unsupported topology-labels format: {path}")


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


def _build_candidate_pool_summary(values: list[str]) -> str:
    clean = [str(value).strip() for value in values if str(value).strip()]
    if not clean:
        return "(no prior candidates recorded)"
    return ", ".join(clean) + " (model-generated only; none are confirmed correct)"


def _build_prior_context(prior_bftc: dict[str, Any] | None, prior_exec: dict[str, Any] | None) -> str:
    lines: list[str] = []
    if prior_bftc:
        lines += [
            "",
            "PRIOR BFTC CONTEXT (model-generated, not confirmed correct):",
            f"  requested_target: {str(prior_bftc.get('target_identified') or prior_bftc.get('requested_target') or '')[:200]}",
            f"  prior_final_answer: {prior_bftc.get('fa_numeric', '')}",
            f"  candidate_pool_review: {str(prior_bftc.get('candidate_pool_review', ''))[:200]}",
        ]
    if prior_exec:
        lines += [
            "",
            "PRIOR EXECUTABLE-REPAIR CONTEXT (model-generated, not confirmed correct):",
            f"  requested_target: {str(prior_exec.get('requested_target', ''))[:200]}",
            f"  failed_relation: {str(prior_exec.get('failed_relation', ''))[:200]}",
            f"  repair_operation: {str(prior_exec.get('repair_operation', ''))[:200]}",
            f"  solution_formula: {str(prior_exec.get('solution_formula', ''))[:200]}",
            f"  executable_final_answer: {prior_exec.get('executable_final_answer', '')}",
        ]
    if not lines:
        return ""
    lines.append("")
    return "\n".join(lines)


def render_prompt(template: str, question: str, candidate_pool_summary: str, prior_context: str) -> str:
    rendered = template.replace("{{question}}", question)
    rendered = rendered.replace("{{candidate_pool_summary}}", candidate_pool_summary)
    rendered = rendered.replace("{{prior_context}}", prior_context)
    unresolved = re.findall(r"\{\{[^}]+\}\}", rendered)
    if unresolved:
        raise ValueError(f"Unresolved placeholders: {unresolved}")
    return rendered


def audit_prompt(text: str, case_id: str) -> dict[str, Any]:
    violations = [pattern.pattern for pattern in _FORBIDDEN_PROMPT_RE if pattern.search(text)]
    return {
        "case_id": case_id,
        "gold_free": not violations,
        "violations": violations,
        "prompt_sha256": _sha256(text),
        "prompt_length": len(text),
    }


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

    prior_bftc = _index_by_case_id(_load_optional_rows(args.prior_bftc_output))
    prior_exec = _index_by_case_id(_load_optional_rows(args.prior_executable_output))
    topology_rows = _index_by_case_id(_load_optional_rows(args.topology_labels))

    selected_cases_out: list[dict[str, Any]] = []
    provider_requests: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []

    for idx, case in enumerate(cases, start=1):
        case_id = str(case.get("case_id", f"case_{idx:04d}")).strip()
        question = str(case.get("question", "")).strip()
        candidate_pool = [str(value).strip() for value in (case.get("candidate_pool") or []) if str(value).strip()]
        prior_context = _build_prior_context(prior_bftc.get(case_id), prior_exec.get(case_id))
        prompt_text = render_prompt(
            template=template,
            question=question,
            candidate_pool_summary=_build_candidate_pool_summary(candidate_pool),
            prior_context=prior_context,
        )
        audit = audit_prompt(prompt_text, case_id)
        audits.append(audit)
        topology_metadata = _topology_metadata_without_gold(topology_rows.get(case_id))

        selected_cases_out.append(
            {
                "case_id": case_id,
                "question": question,
                "candidate_pool": candidate_pool,
                "candidate_pool_size": len(candidate_pool),
                "baseline_answer": str(case.get("baseline_answer", "")).strip(),
                "gold_absent": case.get("gold_absent"),
                "has_prior_bftc_context": case_id in prior_bftc,
                "has_prior_executable_context": case_id in prior_exec,
                "has_topology_metadata": bool(topology_metadata),
                "topology_metadata": topology_metadata,
                "prompt_sha256": audit["prompt_sha256"],
            }
        )
        provider_requests.append(
            {
                "request_id": f"{EXPERIMENT_ID}:{case_id}:{idx:05d}",
                "case_id": case_id,
                "question": question,
                "prompt_text": prompt_text,
                "candidate_pool": candidate_pool,
                "candidate_pool_size": len(candidate_pool),
                "baseline_answer": str(case.get("baseline_answer", "")).strip(),
                "gold_absent": case.get("gold_absent"),
                "has_prior_bftc_context": case_id in prior_bftc,
                "has_prior_executable_context": case_id in prior_exec,
                "topology_metadata": topology_metadata,
                "topology_metadata_in_prompt": False,
                "dry_run": True,
                "api_call_made": False,
                "prompt_sha256": audit["prompt_sha256"],
                "max_output_tokens": 2048,
                "required_output_fields": _REQUIRED_OUTPUT_FIELDS,
            }
        )

    _write_jsonl(out_dir / "selected_cases.jsonl", selected_cases_out)
    _write_jsonl(out_dir / "provider_requests_dry_run.jsonl", provider_requests)

    prompt_audit = {
        "all_gold_free": all(audit["gold_free"] for audit in audits),
        "case_count": len(audits),
        "violations": [audit for audit in audits if not audit["gold_free"]],
        "per_case": audits,
    }
    _write_json(out_dir / "prompt_audit.json", prompt_audit)

    report_lines = [
        "# Declarative Equation Branch v1 — Dry-Run Preflight Report",
        f"**Timestamp:** {_TS}",
        f"**Experiment:** {EXPERIMENT_ID}",
        "",
        "## Summary",
        f"- Cases loaded: {len(selected_cases_out)}",
        f"- Prior BFTC context available: {sum(1 for row in selected_cases_out if row['has_prior_bftc_context'])}",
        f"- Prior executable context available: {sum(1 for row in selected_cases_out if row['has_prior_executable_context'])}",
        f"- Offline topology metadata attached: {sum(1 for row in selected_cases_out if row['has_topology_metadata'])}",
        f"- All prompts gold-free: {prompt_audit['all_gold_free']}",
        "- API calls made: 0",
        "",
        "## Prompt Safety",
        "- topology metadata is attached only outside prompt_text",
        "- gold answers never enter prompts or provider requests",
        "- prompt audit checks gold / answer-key leakage patterns",
    ]
    (out_dir / "dry_run_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "selected_cases_input": str(args.selected_cases),
        "prior_bftc_output_input": str(args.prior_bftc_output) if args.prior_bftc_output else None,
        "prior_executable_output_input": str(args.prior_executable_output) if args.prior_executable_output else None,
        "topology_labels_input": str(args.topology_labels) if args.topology_labels else None,
        "cases_selected": len(selected_cases_out),
        "all_prompts_gold_free": prompt_audit["all_gold_free"],
        "gold_leakage_allowed": False,
        "api_calls_made": 0,
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
    print(f"Declarative equation branch preflight complete. {len(selected_cases_out)} cases. Output: {out_dir}", flush=True)
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="No-API preflight for declarative_equation_branch_v1.")
    parser.add_argument(
        "--selected-cases",
        type=Path,
        default=Path(tempfile.gettempdir()) / "bftc_preflight_20" / "selected_cases.jsonl",
        help="Selected cases jsonl.",
    )
    parser.add_argument("--prior-bftc-output", type=Path, default=None)
    parser.add_argument("--prior-executable-output", type=Path, default=None)
    parser.add_argument(
        "--topology-labels",
        type=Path,
        default=None,
        help="Optional topology labels jsonl/csv; metadata only, never inserted into prompt_text.",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args(argv)


if __name__ == "__main__":
    main()
