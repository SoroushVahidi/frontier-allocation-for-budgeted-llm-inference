#!/usr/bin/env python3
"""Targeted output-layer repair pass for current tuned vs self_consistency failures."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer, classify_mismatch_subtype

INPUT_DIR = REPO_ROOT / "outputs/twenty_exact_current_tuned_vs_self_consistency_failures_20260420"
CASES_DIR = INPUT_DIR / "cases"
OUT_DIR = REPO_ROOT / "outputs/current_failure_output_layer_repair_20260420"
DOC_PATH = REPO_ROOT / "docs/CURRENT_FAILURE_OUTPUT_LAYER_REPAIR_STATUS_2026_04_20.md"


def _load_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in sorted(CASES_DIR.glob("*.json")):
        rows.append(json.loads(p.read_text(encoding="utf-8")))
    if len(rows) != 20:
        raise RuntimeError(f"Expected 20 cases from canonical artifact; found {len(rows)}")
    return rows


def _target_subset(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        baseline_wrong = not bool(r.get("recorded_surface_outcome", {}).get("our_correct", True))
        sc_correct = bool(r.get("recorded_surface_outcome", {}).get("self_consistency_correct", False))
        correct_in_tree = bool(r.get("comparison", {}).get("our_contains_correct_answer", False))
        if baseline_wrong and sc_correct and correct_in_tree:
            out.append(r)
    return out


def main() -> None:
    all_cases = _load_cases()
    targeted = _target_subset(all_cases)
    if len(targeted) != 16:
        raise RuntimeError(f"Targeted subset must contain 16 cases; found {len(targeted)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_case_rows: list[dict[str, Any]] = []

    for row in targeted:
        dataset = str(row["dataset"])
        case_id = str(row["case_id"])
        gt_raw = str(row["ground_truth_answer"])
        gt_can = canonicalize_answer(gt_raw, dataset=dataset)

        our = row["rerun_observability"]["our"]
        meta = our.get("metadata", {})
        final_nodes = list(our.get("final_nodes", []))
        selected_group_hint = meta.get("selected_group")

        repaired = choose_repair_answer(
            final_nodes=final_nodes,
            selected_group_hint=selected_group_hint,
            dataset=dataset,
            enable_rescue=True,
        )

        baseline_surface_raw = row.get("recorded_surface_outcome", {}).get("our_answer")
        baseline_surface_can = canonicalize_answer(None if baseline_surface_raw is None else str(baseline_surface_raw), dataset=dataset)

        eval_raw = repaired["surfaced_final_answer_raw"]
        eval_can = canonicalize_answer(eval_raw, dataset=dataset)

        chosen_raw = repaired["chosen_final_node_answer_raw"]
        extracted_raw = repaired["extracted_final_answer_raw"]
        surfaced_raw = repaired["surfaced_final_answer_raw"]
        chosen_can = repaired["chosen_final_node_answer_canonical"]
        extracted_can = repaired["extracted_final_answer_canonical"]
        surfaced_can = repaired["surfaced_final_answer_canonical"]

        chosen_vs_extraction = chosen_can != extracted_can
        chosen_vs_surface = chosen_can != surfaced_can
        extraction_vs_surface = extracted_can != surfaced_can
        canonicalization_changed = any(
            raw is not None and canonicalize_answer(raw, dataset=dataset) != raw.strip()
            for raw in [chosen_raw, extracted_raw, surfaced_raw]
        )
        canonical_matches_gt = surfaced_can == gt_can
        surface_was_correct = baseline_surface_can == gt_can

        entry = {
            "case_id": case_id,
            "dataset": dataset,
            "example_id": row["example_id"],
            "ground_truth_answer_raw": gt_raw,
            "ground_truth_answer_canonical": gt_can,
            "baseline_surface_answer_raw": baseline_surface_raw,
            "baseline_surface_answer_canonical": baseline_surface_can,
            **repaired,
            "evaluation_answer_raw": eval_raw,
            "evaluation_answer_canonical": eval_can,
            "chosen_node_vs_extraction_mismatch": bool(chosen_vs_extraction),
            "chosen_node_vs_surface_mismatch": bool(chosen_vs_surface),
            "extraction_vs_surface_mismatch": bool(extraction_vs_surface),
            "canonicalization_changed_answer": bool(canonicalization_changed),
            "canonical_answer_matches_ground_truth": bool(canonical_matches_gt),
            "surface_was_correct": bool(surface_was_correct),
            "resolved_by_repair": bool((not surface_was_correct) and canonical_matches_gt),
        }
        entry["mismatch_subtype_label"] = classify_mismatch_subtype(entry)
        per_case_rows.append(entry)

    subtype_counts = Counter(r["mismatch_subtype_label"] for r in per_case_rows)
    mismatch_breakdown = {
        "total_cases": len(per_case_rows),
        "chosen_node_vs_extraction_mismatch": int(sum(1 for r in per_case_rows if r["chosen_node_vs_extraction_mismatch"])),
        "chosen_node_vs_surface_mismatch": int(sum(1 for r in per_case_rows if r["chosen_node_vs_surface_mismatch"])),
        "extraction_vs_surface_mismatch": int(sum(1 for r in per_case_rows if r["extraction_vs_surface_mismatch"])),
        "canonicalization_changed_answer": int(sum(1 for r in per_case_rows if r["canonicalization_changed_answer"])),
        "canonical_answer_matches_ground_truth": int(sum(1 for r in per_case_rows if r["canonical_answer_matches_ground_truth"])),
        "resolved_by_repair": int(sum(1 for r in per_case_rows if r["resolved_by_repair"])),
        "unresolved_after_repair": int(sum(1 for r in per_case_rows if not r["resolved_by_repair"])),
        "subtype_counts": dict(subtype_counts),
    }

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_artifact": str(INPUT_DIR.relative_to(REPO_ROOT)),
        "targeting_rule": {
            "current_tuned_wrong": True,
            "self_consistency_3_correct": True,
            "our_contains_correct_answer": True,
        },
        "total_input_cases": len(all_cases),
        "targeted_cases": len(per_case_rows),
        "resolved_by_repair": mismatch_breakdown["resolved_by_repair"],
        "unresolved_after_repair": mismatch_breakdown["unresolved_after_repair"],
        "primary_question": "Out of the 16 current-loss cases where the correct answer is already in our tree, how many are resolved by the new output-layer repair?",
        "mismatch_breakdown": mismatch_breakdown,
    }

    manifest = {
        "name": "current_failure_output_layer_repair_20260420",
        "created_at_utc": summary["timestamp_utc"],
        "inputs": [
            "outputs/twenty_exact_current_tuned_vs_self_consistency_failures_20260420/cases/*.json",
            "outputs/twenty_exact_current_tuned_vs_self_consistency_failures_20260420/summary.json",
        ],
        "outputs": [
            "outputs/current_failure_output_layer_repair_20260420/manifest.json",
            "outputs/current_failure_output_layer_repair_20260420/summary.json",
            "outputs/current_failure_output_layer_repair_20260420/per_case_results.jsonl",
            "outputs/current_failure_output_layer_repair_20260420/mismatch_breakdown.json",
            "outputs/current_failure_output_layer_repair_20260420/targeted_16_table.csv",
            "docs/CURRENT_FAILURE_OUTPUT_LAYER_REPAIR_STATUS_2026_04_20.md",
        ],
    }

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "mismatch_breakdown.json").write_text(json.dumps(mismatch_breakdown, indent=2) + "\n", encoding="utf-8")

    with (OUT_DIR / "per_case_results.jsonl").open("w", encoding="utf-8") as f:
        for r in per_case_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    header = ["case_id", "dataset", "example_id", "baseline_surface_answer_canonical", "evaluation_answer_canonical", "resolved_by_repair", "mismatch_subtype_label"]
    lines = [",".join(header)]
    for r in per_case_rows:
        lines.append(
            ",".join(
                [
                    str(r["case_id"]),
                    str(r["dataset"]),
                    str(r["example_id"]),
                    str(r.get("baseline_surface_answer_canonical")),
                    str(r.get("evaluation_answer_canonical")),
                    str(r.get("resolved_by_repair")),
                    str(r.get("mismatch_subtype_label")),
                ]
            )
        )
    (OUT_DIR / "targeted_16_table.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    md_lines = [
        "# Current failure output-layer repair status (2026-04-20)",
        "",
        "## Scope",
        "- Target set: exact subset of the fresh 20-case current tuned vs self_consistency_3 failures where:",
        "  - current tuned is wrong,",
        "  - self_consistency_3 is correct,",
        "  - and correct answer is already in our tree.",
        f"- Verified target set size: **{len(per_case_rows)}**.",
        "",
        "## Repair layer implemented",
        "- Deterministic post-selection extraction from chosen node (prefer branch-local answer; fallback to branch-text extraction).",
        "- Explicit separation/logging of chosen-node answer, extracted answer, surfaced answer, and evaluation answer (raw + canonical).",
        "- Dataset-safe canonicalization using shared normalization plus small numeric cleanup.",
        "- Explicit mismatch flags and subtype labeling.",
        "- Lightweight local answer-level rescue by high-support canonical consensus among final candidate nodes.",
        "",
        "## Results on targeted 16-case subset",
        f"- Resolved by repair: **{mismatch_breakdown['resolved_by_repair']} / {len(per_case_rows)}**.",
        f"- Unresolved after repair: **{mismatch_breakdown['unresolved_after_repair']} / {len(per_case_rows)}**.",
        f"- chosen-node vs surfaced mismatch count: **{mismatch_breakdown['chosen_node_vs_surface_mismatch']}**.",
        f"- chosen-node vs extraction mismatch count: **{mismatch_breakdown['chosen_node_vs_extraction_mismatch']}**.",
        f"- extraction vs surfaced mismatch count: **{mismatch_breakdown['extraction_vs_surface_mismatch']}**.",
        f"- canonicalization changed answer count: **{mismatch_breakdown['canonicalization_changed_answer']}**.",
        "",
        "## Compact per-case table",
        "| case_id | baseline(surface canonical) | repaired(surface canonical) | resolved | subtype |",
        "|---|---:|---:|---:|---|",
    ]
    for r in per_case_rows:
        md_lines.append(
            f"| {r['case_id']} | {r.get('baseline_surface_answer_canonical')} | {r.get('evaluation_answer_canonical')} | {r.get('resolved_by_repair')} | {r.get('mismatch_subtype_label')} |"
        )
    md_lines.extend(
        [
            "",
            "## Artifacts",
            "- `outputs/current_failure_output_layer_repair_20260420/manifest.json`",
            "- `outputs/current_failure_output_layer_repair_20260420/summary.json`",
            "- `outputs/current_failure_output_layer_repair_20260420/per_case_results.jsonl`",
            "- `outputs/current_failure_output_layer_repair_20260420/mismatch_breakdown.json`",
            "- `outputs/current_failure_output_layer_repair_20260420/targeted_16_table.csv`",
        ]
    )
    DOC_PATH.write_text("\n".join(md_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
