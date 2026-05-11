#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import extract_final_answer
from experiments.output_layer_repair import canonicalize_answer

EXISTING_30_CASES = REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl"
GOLD_ABSENT_AUDIT = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
OUT_PATH = REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/failure_recovery_50case_exact_cases_20260510.jsonl"

SOURCE_PATHS = [
    REPO_ROOT / "outputs/cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506/pal_results.csv",
    REPO_ROOT / "outputs/production_equiv_v1_retry_commit_loss_audit_20260508T204005Z/production_equiv_loss_bank_detailed.csv",
    REPO_ROOT / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/cohere_real_model_cost_normalized_validation_20260507T161935Z/per_example_records.jsonl",
    REPO_ROOT / "outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/cumulative_pal_vs_prod_casebook.csv",
    REPO_ROOT / "outputs/pal_vs_production_equiv_casebook_live_20260508T223635Z/pal_vs_prod_casebook.csv",
]

ADDITIONAL_CASE_IDS = [
    "openai_gsm8k_1006",
    "openai_gsm8k_1027",
    "openai_gsm8k_1029",
    "openai_gsm8k_1045",
    "openai_gsm8k_1081",
    "openai_gsm8k_1112",
    "openai_gsm8k_1155",
    "openai_gsm8k_1003",
    "openai_gsm8k_1019",
    "openai_gsm8k_1035",
    "openai_gsm8k_1039",
    "openai_gsm8k_1069",
    "openai_gsm8k_1121",
    "openai_gsm8k_1025",
    "openai_gsm8k_1085",
    "openai_gsm8k_1095",
    "openai_gsm8k_1101",
    "openai_gsm8k_1187",
    "openai_gsm8k_1214",
    "openai_gsm8k_1215",
]


def read_csv_by_id(path: Path, id_keys: tuple[str, ...] = ("example_id", "case_id")) -> dict[str, dict[str, str]]:
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
            cid = str(row.get("example_id") or row.get("case_id") or "").strip()
            if cid:
                out[cid] = dict(row)
    return out


def maybe_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
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


def first_nonempty(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def artifact_kind(path: Path) -> str:
    name = path.name
    if name.endswith("pal_results.csv"):
        return "pal_results"
    if name.endswith("per_example_records.jsonl"):
        return "per_example_records"
    if name.endswith("production_equiv_loss_bank_detailed.csv"):
        return "loss_bank_detailed"
    if "casebook" in name:
        return "casebook"
    return path.stem


def load_audit_index() -> dict[str, dict[str, str]]:
    if not GOLD_ABSENT_AUDIT.exists():
        return {}
    return read_csv_by_id(GOLD_ABSENT_AUDIT, ("case_id",))


def load_source_index() -> dict[str, tuple[dict[str, Any], Path]]:
    index: dict[str, tuple[dict[str, Any], Path]] = {}
    for path in SOURCE_PATHS:
        if not path.exists():
            continue
        rows = read_jsonl_by_id(path) if path.suffix == ".jsonl" else read_csv_by_id(path)
        for cid, row in rows.items():
            if cid not in index:
                index[cid] = (row, path)
    return index


def normalize_domain(raw: str) -> str:
    text = str(raw or "").strip()
    return text or "unknown"


def build_additional_case_row(
    case_id: str,
    source_row: dict[str, Any],
    source_path: Path,
    audit_row: dict[str, str],
) -> dict[str, Any]:
    result_md = maybe_json(source_row.get("result_metadata")) or {}
    question = first_nonempty(source_row, "question", "problem_text", "problem_text if available")
    if not question:
        raise ValueError(f"{case_id}: missing question/problem_text in {source_path}")

    gold_raw = first_nonempty(source_row, "gold_answer_canonical", "gold_answer", "gold") or str(audit_row.get("gold") or "")
    gold_can = canon_gold(gold_raw)
    failure_domain = normalize_domain(audit_row.get("question_type") or "unknown")
    candidate_groups = audit_row.get("num_candidate_groups") or result_md.get("selector_candidate_answer_group_count") or result_md.get("candidate_pool_answer_group_count")
    diversity_bucket = normalize_domain(audit_row.get("diversity_bucket") or "")
    external_contrast = normalize_domain(audit_row.get("external_contrast") or "")
    latest_prediction = first_nonempty(
        source_row,
        "selected_answer_canonical",
        "selected_answer",
        "final_answer_canonical",
        "final_answer_raw",
        "production_equiv_answer",
        "predicted",
    ) or str(audit_row.get("predicted") or "")
    failure_category = first_nonempty(
        source_row,
        "likely_failure_family",
        "failure_family",
        "failure_tag",
    ) or str(audit_row.get("error_type") or "unknown")
    source_kind = artifact_kind(source_path)
    gold_in_pool = first_nonempty(source_row, "gold_in_tree", "gold_in_candidate_pool")
    answer_group_entropy = result_md.get("direct_answer_entropy") or result_md.get("answer_group_entropy")
    frontier_collapse_detected = result_md.get("frontier_collapse_detected")
    direct_l1_anchor_present = result_md.get("direct_l1_anchor_present")
    latest_method_id = first_nonempty(source_row, "method", "method_id")

    rec: dict[str, Any] = {
        "example_id": case_id,
        "dataset": "openai/gsm8k",
        "question": question,
        "problem_text": question,
        "gold_answer_canonical": gold_can,
        "gold_answer_source_raw": gold_raw,
        "failure_category": failure_category,
        "failure_domain": failure_domain,
        "source_artifact_kind": source_kind,
        "source_artifact_path": str(source_path.relative_to(REPO_ROOT)),
        "latest_failure_method_id": latest_method_id,
        "latest_method_prediction": latest_prediction,
        "latest_method_failure_tag": failure_category,
        "gold_in_candidate_pool": gold_in_pool,
        "candidate_answer_group_count": int(candidate_groups) if str(candidate_groups).strip().isdigit() else candidate_groups or None,
        "answer_group_entropy": answer_group_entropy,
        "frontier_collapse_detected": frontier_collapse_detected,
        "direct_l1_anchor_present": direct_l1_anchor_present,
        "selection_reason": "50-case exact replay expansion from validated uncertainty-retry diagnostic selection",
        "notes": f"selected from gold_absent_subpattern_analysis_20260510.csv; diversity_bucket={diversity_bucket}; external_contrast={external_contrast}",
    }
    return rec


def main() -> None:
    existing_rows = [json.loads(line) for line in EXISTING_30_CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    existing_ids = [str(row.get("example_id") or row.get("case_id") or "").strip() for row in existing_rows]
    existing_id_set = set(existing_ids)
    if len(existing_rows) != 30:
        raise SystemExit(f"Expected 30 existing rows in {EXISTING_30_CASES}, found {len(existing_rows)}")

    audit_index = load_audit_index()
    source_index = load_source_index()

    additional_rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for case_id in ADDITIONAL_CASE_IDS:
        if case_id in existing_id_set:
            missing.append(case_id)
            continue
        audit_row = audit_index.get(case_id)
        src = source_index.get(case_id)
        if audit_row is None or src is None:
            missing.append(case_id)
            continue
        source_row, source_path = src
        additional_rows.append(build_additional_case_row(case_id, source_row, source_path, audit_row))

    if missing:
        raise SystemExit(f"Missing source rows for: {missing}")

    all_rows = existing_rows + additional_rows
    if len(all_rows) != 50:
        raise SystemExit(f"Expected 50 total rows, found {len(all_rows)}")

    seen: set[str] = set()
    duplicates: list[str] = []
    for row in all_rows:
        cid = str(row.get("example_id") or row.get("case_id") or "").strip()
        if not cid:
            raise SystemExit("Found a row without example_id")
        if cid in seen:
            duplicates.append(cid)
        seen.add(cid)
        if not str(row.get("question") or row.get("problem_text") or "").strip():
            raise SystemExit(f"{cid}: missing question/problem_text")
        if not str(row.get("gold_answer_canonical") or row.get("gold_answer") or "").strip():
            raise SystemExit(f"{cid}: missing gold answer")
        if not str(row.get("failure_domain") or "").strip():
            raise SystemExit(f"{cid}: missing failure_domain")

    if duplicates:
        raise SystemExit(f"Duplicate example_ids: {duplicates}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    domain_counts = Counter(str(row.get("failure_domain") or "unknown") for row in additional_rows)
    print(f"wrote {len(all_rows)} exact cases to {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"additional_case_count={len(additional_rows)} duplicate_count=0")
    print(f"additional_domain_distribution={dict(sorted(domain_counts.items()))}")


if __name__ == "__main__":
    main()
