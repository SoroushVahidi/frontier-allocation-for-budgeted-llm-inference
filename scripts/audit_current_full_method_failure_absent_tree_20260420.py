#!/usr/bin/env python3
"""Strict absent-from-tree consistency audit for current full-method 20-case failure artifact (2026-04-20)."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = REPO_ROOT / "outputs/twenty_exact_current_full_method_failures_vs_best_20260420"
CASE_DIR = ARTIFACT_ROOT / "cases"
SUMMARY_PATH = ARTIFACT_ROOT / "summary.json"
MANIFEST_PATH = ARTIFACT_ROOT / "selected_case_manifest.json"
CANONICAL_MD_PATH = REPO_ROOT / "docs/TWENTY_EXACT_CURRENT_FULL_METHOD_FAILURES_VS_BEST_2026_04_20.md"

AUDIT_OUT_ROOT = REPO_ROOT / "outputs/current_full_method_failure_absent_tree_audit_20260420"
AUDIT_DOC_PATH = REPO_ROOT / "docs/CURRENT_FULL_METHOD_FAILURE_ABSENT_TREE_AUDIT_2026_04_20.md"


@dataclass
class CaseAuditRow:
    case_id: str
    dataset: str
    example_id: str
    absent_from_our_tree: bool
    source_of_truth_field_used: str
    json_our_contains_correct_answer: bool
    json_our_correct_answer_node_ids_count: int
    json_provenance_our_correct_node_identity: str


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_markdown(md_text: str) -> dict[str, Any]:
    aggregate_absent_count = None
    m = re.search(r"- Correct answer absent from our tree: (\d+)", md_text)
    if m:
        aggregate_absent_count = int(m.group(1))

    per_case: dict[str, dict[str, Any]] = {}
    case_chunks = re.findall(r"## Case \d+: `([^`]+)`\n(.*?)(?=\n## Case \d+: `|\Z)", md_text, flags=re.S)
    for dataset_example, body in case_chunks:
        dataset, example_id = [x.strip() for x in dataset_example.split(" / ")]
        case_id = f"{dataset.replace('/', '__')}__{example_id}"

        m_present = re.search(r"6\. Correct answer in our structure: `(True|False)`", body)
        m_nodes = re.search(r"9\. Correct-answer node/sample IDs: our=`(\[[^`]*\])`", body)

        per_case[case_id] = {
            "md_correct_answer_in_our_structure": None if m_present is None else (m_present.group(1) == "True"),
            "md_our_correct_answer_nodes_text": None if m_nodes is None else m_nodes.group(1),
        }

    return {
        "aggregate_absent_count": aggregate_absent_count,
        "per_case": per_case,
    }


def _determine_absent(case_payload: dict[str, Any]) -> tuple[bool, str]:
    cmp = case_payload.get("comparison", {})
    prov = case_payload.get("provenance_labels", {})

    if isinstance(cmp.get("our_contains_correct_answer"), bool):
        return (not bool(cmp["our_contains_correct_answer"]), "comparison.our_contains_correct_answer")

    if isinstance(cmp.get("our_correct_answer_node_ids"), list):
        return (len(cmp["our_correct_answer_node_ids"]) == 0, "comparison.our_correct_answer_node_ids")

    if "our_correct_node_identity" in prov:
        return (str(prov["our_correct_node_identity"]) == "absent", "provenance_labels.our_correct_node_identity")

    raise ValueError(f"No supported source-of-truth absent field found for case {case_payload.get('case_id')}")


def run() -> None:
    if not ARTIFACT_ROOT.exists():
        raise FileNotFoundError(f"Missing artifact root: {ARTIFACT_ROOT}")

    AUDIT_OUT_ROOT.mkdir(parents=True, exist_ok=True)

    manifest = _read_json(MANIFEST_PATH)
    summary = _read_json(SUMMARY_PATH)
    md_text = CANONICAL_MD_PATH.read_text(encoding="utf-8")
    md_parsed = _parse_markdown(md_text)

    case_rows: list[CaseAuditRow] = []
    absent_case_ids: list[str] = []
    present_case_ids: list[str] = []

    for case_entry in manifest["cases"]:
        case_id = case_entry["case_id"]
        case_path = CASE_DIR / f"{case_id}.json"
        payload = _read_json(case_path)
        absent, source_field = _determine_absent(payload)

        if absent:
            absent_case_ids.append(case_id)
        else:
            present_case_ids.append(case_id)

        cmp = payload.get("comparison", {})
        prov = payload.get("provenance_labels", {})
        case_rows.append(
            CaseAuditRow(
                case_id=case_id,
                dataset=str(payload.get("dataset", "")),
                example_id=str(payload.get("example_id", "")),
                absent_from_our_tree=absent,
                source_of_truth_field_used=source_field,
                json_our_contains_correct_answer=bool(cmp.get("our_contains_correct_answer", False)),
                json_our_correct_answer_node_ids_count=len(cmp.get("our_correct_answer_node_ids", [])) if isinstance(cmp.get("our_correct_answer_node_ids"), list) else -1,
                json_provenance_our_correct_node_identity=str(prov.get("our_correct_node_identity", "")),
            )
        )

    # Deterministic ordering.
    absent_case_ids.sort()
    present_case_ids.sort()
    case_rows.sort(key=lambda r: r.case_id)

    # Consistency checks.
    summary_absent = int(summary.get("counts", {}).get("correct_answer_absent_from_our_tree", -1))
    markdown_absent = md_parsed["aggregate_absent_count"]

    md_per_case_mismatches: list[dict[str, Any]] = []
    for row in case_rows:
        md_case = md_parsed["per_case"].get(row.case_id)
        if md_case is None:
            md_per_case_mismatches.append({"case_id": row.case_id, "issue": "missing_case_in_markdown"})
            continue
        md_bool = md_case.get("md_correct_answer_in_our_structure")
        if md_bool is None:
            md_per_case_mismatches.append({"case_id": row.case_id, "issue": "missing_md_correct_answer_bool"})
            continue
        md_absent = not md_bool
        if md_absent != row.absent_from_our_tree:
            md_per_case_mismatches.append(
                {
                    "case_id": row.case_id,
                    "issue": "md_json_absent_disagreement",
                    "md_absent": md_absent,
                    "json_absent": row.absent_from_our_tree,
                }
            )

    internal_json_mismatches: list[dict[str, Any]] = []
    for row in case_rows:
        expected_contains = not row.absent_from_our_tree
        expected_identity = "exact" if expected_contains else "absent"
        if row.json_our_contains_correct_answer != expected_contains:
            internal_json_mismatches.append(
                {
                    "case_id": row.case_id,
                    "issue": "our_contains_correct_answer_inconsistent_with_audit_flag",
                    "json_our_contains_correct_answer": row.json_our_contains_correct_answer,
                    "audit_absent": row.absent_from_our_tree,
                }
            )
        if row.json_provenance_our_correct_node_identity and row.json_provenance_our_correct_node_identity != expected_identity:
            internal_json_mismatches.append(
                {
                    "case_id": row.case_id,
                    "issue": "provenance_identity_inconsistent_with_audit_flag",
                    "json_provenance_our_correct_node_identity": row.json_provenance_our_correct_node_identity,
                    "expected": expected_identity,
                }
            )

    consistency_report = {
        "audit_date": "2026-04-20",
        "artifact_root": str(ARTIFACT_ROOT.relative_to(REPO_ROOT)),
        "rules": {
            "absent_definition": "Case is absent iff per-case JSON indicates correct answer not in our tree. Priority: comparison.our_contains_correct_answer; fallback: comparison.our_correct_answer_node_ids empty; fallback: provenance_labels.our_correct_node_identity == 'absent'.",
            "do_not_infer_from_prose_only": True,
        },
        "case_count": len(case_rows),
        "computed_absent_count": len(absent_case_ids),
        "computed_present_count": len(present_case_ids),
        "computed_absent_case_ids": absent_case_ids,
        "computed_present_case_ids": present_case_ids,
        "cross_layer_consistency": {
            "summary_json_absent_count": summary_absent,
            "markdown_aggregate_absent_count": markdown_absent,
            "summary_json_matches_computed": (summary_absent == len(absent_case_ids)),
            "markdown_aggregate_matches_computed": (markdown_absent == len(absent_case_ids)),
            "markdown_per_case_json_mismatches": md_per_case_mismatches,
            "internal_json_mismatches": internal_json_mismatches,
        },
        "overall_consistent": (
            summary_absent == len(absent_case_ids)
            and markdown_absent == len(absent_case_ids)
            and len(md_per_case_mismatches) == 0
            and len(internal_json_mismatches) == 0
        ),
    }

    (AUDIT_OUT_ROOT / "absent_case_list.json").write_text(
        json.dumps(
            {
                "audit_date": "2026-04-20",
                "count": len(absent_case_ids),
                "case_ids": absent_case_ids,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (AUDIT_OUT_ROOT / "present_case_list.json").write_text(
        json.dumps(
            {
                "audit_date": "2026-04-20",
                "count": len(present_case_ids),
                "case_ids": present_case_ids,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with (AUDIT_OUT_ROOT / "full_case_audit_table.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(case_rows[0]).keys()))
        writer.writeheader()
        for row in case_rows:
            writer.writerow(asdict(row))

    (AUDIT_OUT_ROOT / "consistency_report.json").write_text(json.dumps(consistency_report, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Current full-method failure absent-tree audit (2026-04-20)")
    lines.append("")
    lines.append("## Scope")
    lines.append("- Canonical note: `docs/TWENTY_EXACT_CURRENT_FULL_METHOD_FAILURES_VS_BEST_2026_04_20.md`.")
    lines.append("- Machine-readable source: per-case JSON under `outputs/twenty_exact_current_full_method_failures_vs_best_20260420/cases/`.")
    lines.append("")
    lines.append("## Audit rule (strict)")
    lines.append("A case is counted as **absent from our tree** iff machine-readable per-case JSON says the correct answer is absent.")
    lines.append("Field priority used:")
    lines.append("1. `comparison.our_contains_correct_answer` (absent iff false).")
    lines.append("2. Else `comparison.our_correct_answer_node_ids` (absent iff empty).")
    lines.append("3. Else `provenance_labels.our_correct_node_identity` (absent iff `absent`).")
    lines.append("")
    lines.append("## Corrected absent-from-tree result")
    lines.append(f"- Computed absent count: **{len(absent_case_ids)}**.")
    lines.append(f"- Absent case IDs ({len(absent_case_ids)}): `{', '.join(absent_case_ids)}`.")
    lines.append(f"- Present case IDs ({len(present_case_ids)}): `{', '.join(present_case_ids)}`.")
    lines.append("")
    lines.append("## Consistency verdict")
    lines.append(f"- `summary.json` absent count: **{summary_absent}** ({'matches' if summary_absent == len(absent_case_ids) else 'MISMATCH'}).")
    lines.append(f"- Markdown aggregate absent count: **{markdown_absent}** ({'matches' if markdown_absent == len(absent_case_ids) else 'MISMATCH'}).")
    lines.append(f"- Markdown per-case vs JSON mismatches: **{len(md_per_case_mismatches)}**.")
    lines.append(f"- Internal JSON consistency mismatches: **{len(internal_json_mismatches)}**.")
    lines.append("")
    lines.append("## Case table (all 20)")
    lines.append("| case_id | dataset/example | absent_from_our_tree | source_of_truth_field_used |")
    lines.append("|---|---|---:|---|")
    for row in case_rows:
        lines.append(
            f"| `{row.case_id}` | `{row.dataset} / {row.example_id}` | `{str(row.absent_from_our_tree).lower()}` | `{row.source_of_truth_field_used}` |"
        )
    lines.append("")
    lines.append("## Machine-readable outputs")
    lines.append("- `outputs/current_full_method_failure_absent_tree_audit_20260420/absent_case_list.json`")
    lines.append("- `outputs/current_full_method_failure_absent_tree_audit_20260420/present_case_list.json`")
    lines.append("- `outputs/current_full_method_failure_absent_tree_audit_20260420/full_case_audit_table.csv`")
    lines.append("- `outputs/current_full_method_failure_absent_tree_audit_20260420/consistency_report.json`")

    AUDIT_DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
