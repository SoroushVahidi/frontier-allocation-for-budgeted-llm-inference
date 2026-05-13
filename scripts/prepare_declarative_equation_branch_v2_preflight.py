#!/usr/bin/env python3
"""
No-API preflight for declarative_equation_branch_v2.

Renders dry-run provider requests and keeps optional topology / prior-v1 metadata
outside prompt_text.
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

EXPERIMENT_ID = "declarative_equation_branch_v2"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
PROMPT_TEMPLATE_PATH = REPO_ROOT / "prompts" / "declarative_equation_branch_v2.md"

_REQUIRED_OUTPUT_FIELDS = [
    "requested_target",
    "target_variable",
    "target_unit",
    "process_state",
    "source_facts",
    "variables",
    "relations",
    "equations",
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
    return Path(tempfile.gettempdir()) / "declarative_equation_branch_v2_preflight"


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


def _build_candidate_pool_summary(values: list[str]) -> str:
    clean = [str(value).strip() for value in values if str(value).strip()]
    if not clean:
        return "(no prior candidates recorded)"
    return ", ".join(clean) + " (model-generated only; none are confirmed correct)"


def render_prompt(template: str, question: str, candidate_pool_summary: str) -> str:
    rendered = template.replace("{{question}}", question)
    rendered = rendered.replace("{{candidate_pool_summary}}", candidate_pool_summary)
    unresolved = re.findall(r"\{\{[^}]+\}\}", rendered)
    if unresolved:
        raise ValueError(f"Unresolved placeholders: {unresolved}")
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


def _prior_v1_metadata_without_gold(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    keys = [
        "requested_target",
        "target_variable",
        "target_unit",
        "process_state",
        "solution_formula",
        "final_answer",
        "uncertainty",
        "abstain_reason",
        "schema_ok",
        "issue_summary",
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

    topology_rows = _index_by_case_id(_load_optional_rows(args.topology_labels))
    prior_v1_rows = _index_by_case_id(_load_optional_rows(args.prior_v1_output))

    selected_cases_out: list[dict[str, Any]] = []
    provider_requests: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []

    for idx, case in enumerate(cases, start=1):
        case_id = str(case.get("case_id", f"case_{idx:04d}")).strip()
        question = str(case.get("question", "")).strip()
        candidate_pool = [str(value).strip() for value in (case.get("candidate_pool") or []) if str(value).strip()]
        prompt_text = render_prompt(
            template=template,
            question=question,
            candidate_pool_summary=_build_candidate_pool_summary(candidate_pool),
        )
        audit = audit_prompt(prompt_text, case_id)
        audits.append(audit)
        topology_metadata = _topology_metadata_without_gold(topology_rows.get(case_id))
        prior_v1_metadata = _prior_v1_metadata_without_gold(prior_v1_rows.get(case_id))

        selected_cases_out.append(
            {
                "case_id": case_id,
                "question": question,
                "candidate_pool": candidate_pool,
                "candidate_pool_size": len(candidate_pool),
                "baseline_answer": str(case.get("baseline_answer", "")).strip(),
                "gold_absent": case.get("gold_absent"),
                "has_topology_metadata": bool(topology_metadata),
                "has_prior_v1_metadata": bool(prior_v1_metadata),
                "topology_metadata": topology_metadata,
                "prior_v1_metadata": prior_v1_metadata,
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
                "topology_metadata": topology_metadata,
                "prior_v1_metadata": prior_v1_metadata,
                "topology_metadata_in_prompt": False,
                "prior_v1_metadata_in_prompt": False,
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
        "all_forbidden_string_free": all(audit["forbidden_string_free"] for audit in audits),
        "case_count": len(audits),
        "violations": [audit for audit in audits if not audit["forbidden_string_free"]],
        "per_case": audits,
    }
    _write_json(out_dir / "prompt_audit.json", prompt_audit)

    report_lines = [
        "# Declarative Equation Branch v2 — Dry-Run Preflight Report",
        f"**Timestamp:** {_TS}",
        f"**Experiment:** {EXPERIMENT_ID}",
        "",
        "## Summary",
        f"- Cases loaded: {len(selected_cases_out)}",
        f"- Offline topology metadata attached: {sum(1 for row in selected_cases_out if row['has_topology_metadata'])}",
        f"- Offline prior v1 metadata attached: {sum(1 for row in selected_cases_out if row['has_prior_v1_metadata'])}",
        f"- All prompts gold-free: {prompt_audit['all_gold_free']}",
        f"- All prompts forbidden-string-free: {prompt_audit['all_forbidden_string_free']}",
        "- API calls made: 0",
        "",
        "## Prompt Safety",
        "- topology metadata is attached only outside prompt_text",
        "- prior v1 outputs are attached only outside prompt_text",
        "- prompt audit checks gold / answer-key / forbidden-string leakage",
    ]
    (out_dir / "dry_run_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "selected_cases_input": str(args.selected_cases),
        "topology_labels_input": str(args.topology_labels) if args.topology_labels else None,
        "prior_v1_output_input": str(args.prior_v1_output) if args.prior_v1_output else None,
        "cases_selected": len(selected_cases_out),
        "all_prompts_gold_free": prompt_audit["all_gold_free"],
        "all_prompts_forbidden_string_free": prompt_audit["all_forbidden_string_free"],
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
    print(f"Declarative equation branch v2 preflight complete. {len(selected_cases_out)} cases. Output: {out_dir}", flush=True)
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="No-API preflight for declarative_equation_branch_v2.")
    parser.add_argument("--selected-cases", type=Path, required=True, help="Selected cases jsonl.")
    parser.add_argument("--topology-labels", type=Path, default=None)
    parser.add_argument("--prior-v1-output", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args(argv)


if __name__ == "__main__":
    main()
