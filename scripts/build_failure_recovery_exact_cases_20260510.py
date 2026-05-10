#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import extract_final_answer
from experiments.output_layer_repair import canonicalize_answer

SELECTED_MANIFEST = REPO_ROOT / "outputs/cohere_diverse_anchor_failure_recovery_30case_20260510T184818Z/manifest.json"
SUBPATTERN_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
FULL_FAILURE_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv"
TARGET_AUDIT_JSONL = REPO_ROOT / "docs/project_handoff_20260510/target_audit_diagnostic_cases.jsonl"
OUT_PATH = REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl"

PAL_RESULT_PATHS = [
    REPO_ROOT / "outputs/external_only_loss_collection_pal_vs_l1_completed_20260506T125123Z/pal_results.csv",
    REPO_ROOT / "outputs/external_only_loss_collection_pal_vs_l1_round2_20260506T130225Z/pal_results.csv",
    REPO_ROOT / "outputs/external_only_loss_collection_pal_vs_l1_round3_20260506T151731Z/pal_results.csv",
    REPO_ROOT / "outputs/cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506/pal_results.csv",
]


def read_csv_by_id(path: Path, id_keys: tuple[str, ...]) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for key in id_keys:
                cid = str(row.get(key) or "").strip()
                if cid:
                    out[cid] = dict(row)
                    break
    return out


def read_jsonl_by_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            cid = str(row.get("case_id") or row.get("example_id") or "").strip()
            if cid:
                out[cid] = row
    return out


def maybe_json(text: str) -> Any:
    try:
        return json.loads(text) if text else None
    except Exception:
        return None


def canon_gold(raw: Any, dataset: str = "openai/gsm8k") -> str:
    raw_s = str(raw or "").strip()
    if "####" in raw_s:
        raw_s = extract_final_answer(raw_s)
    can = canonicalize_answer(raw_s, dataset=dataset)
    if can is None:
        raise ValueError(f"Could not canonicalize gold answer: {raw!r}")
    return str(can)


def main() -> None:
    manifest = json.loads(SELECTED_MANIFEST.read_text(encoding="utf-8"))
    selected_ids = [str(x) for x in manifest["selected_case_ids"]]
    subpattern = read_csv_by_id(SUBPATTERN_CSV, ("case_id",))
    full_failure = read_csv_by_id(FULL_FAILURE_CSV, ("case_id",))
    target_audit = read_jsonl_by_id(TARGET_AUDIT_JSONL)
    pal_rows: dict[str, dict[str, str]] = {}
    pal_source: dict[str, str] = {}
    for path in PAL_RESULT_PATHS:
        rows = read_csv_by_id(path, ("example_id", "case_id"))
        for cid, row in rows.items():
            if cid not in pal_rows:
                pal_rows[cid] = row
                pal_source[cid] = str(path.relative_to(REPO_ROOT))

    records: list[dict[str, Any]] = []
    missing: list[str] = []
    for cid in selected_ids:
        sub = subpattern.get(cid, {})
        full = full_failure.get(cid, {})
        src_row: dict[str, Any] | None = None
        src_kind = ""
        src_path = ""
        if cid in target_audit:
            src_row = target_audit[cid]
            src_kind = "target_audit_diagnostic_cases"
            src_path = str(TARGET_AUDIT_JSONL.relative_to(REPO_ROOT))
        if cid in pal_rows:
            # Prefer PAL result rows when present because they include direct runner question/gold/prediction fields.
            src_row = pal_rows[cid]
            src_kind = "pal_results"
            src_path = pal_source[cid]
        if src_row is None:
            missing.append(cid)
            continue
        question = str(src_row.get("question") or src_row.get("problem_text") or "").strip()
        gold_raw = src_row.get("gold_answer_canonical") or src_row.get("gold_answer") or sub.get("gold")
        if not question:
            missing.append(cid)
            continue
        gold_can = canon_gold(gold_raw)
        result_md = maybe_json(str(src_row.get("result_metadata") or "")) or {}
        rec = {
            "example_id": cid,
            "dataset": "openai/gsm8k",
            "question": question,
            "problem_text": question,
            "gold_answer_canonical": gold_can,
            "gold_answer_source_raw": str(gold_raw),
            "failure_category": str(full.get("failure_family") or src_row.get("failure_family") or src_row.get("failure_tag") or sub.get("error_type") or "unknown"),
            "failure_domain": str(sub.get("question_type") or "unknown"),
            "source_artifact_path": src_path,
            "source_artifact_kind": src_kind,
            "latest_failure_method_id": str(full.get("method_id") or src_row.get("method") or src_row.get("method_id") or ""),
            "latest_method_prediction": str(sub.get("predicted") or src_row.get("selected_answer_canonical") or src_row.get("selected_answer") or src_row.get("final_answer_canonical") or ""),
            "latest_method_failure_tag": str(full.get("failure_family") or src_row.get("failure_tag") or src_row.get("failure_family") or ""),
            "gold_in_candidate_pool": str(src_row.get("gold_in_tree") or src_row.get("gold_present_in_candidate_pool") or ""),
            "candidate_answer_group_count": result_md.get("candidate_pool_answer_group_count") or result_md.get("selector_candidate_answer_group_count"),
            "answer_group_entropy": result_md.get("answer_group_entropy"),
            "frontier_collapse_detected": result_md.get("frontier_collapse_detected"),
            "direct_l1_anchor_present": result_md.get("direct_l1_anchor_present"),
            "selection_reason": "30-case failure-recovery exact replay case from invalidated Cohere diagnostic selection",
        }
        records.append(rec)
    if missing:
        raise SystemExit(f"Missing exact source rows for: {missing}")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote {len(records)} exact cases to {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
