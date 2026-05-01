#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

DR_METHOD_CANDIDATES = [
    "direct_reserve_semantic_frontier_v2",
    "direct_reserve_semantic_frontier_v2_selection_fix_v1",
    "direct_reserve_strong_plus_diverse_margin_gated_v1",
    "direct_reserve_strong_plus_diverse_v1",
    "direct_reserve_strong_v1",
    "strict_f3",
]

SIGNAL_FILENAMES = {
    "per_example_records.jsonl",
    "per_case_method_results.csv",
    "final_branch_states.jsonl",
    "answer_group_summary.csv",
    "answer_group_table.csv",
    "candidate_branch_table.csv",
}

SIGNAL_TEXT_PATTERNS = [
    "selector_candidate_pool",
    "candidate_groups",
    "raw_support_count_by_answer_group",
]


@dataclass
class ScanResult:
    artifact_path: str
    usable: int
    rejection_reason: str
    paired_example_count: int
    dr_method: str
    dr_v2_accuracy: float
    external_l1_max_accuracy: float
    oracle_selector_accuracy: float
    oracle_minus_l1: float
    oracle_minus_dr: float
    gold_present_but_dr_wrong_count: int
    gold_absent_count: int
    candidate_answer_group_count_mean: float
    candidate_answer_group_count_median: float
    candidate_answer_group_count_max: int
    trace_completeness_notes: str
    reconstructed_path: str


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _norm(v: Any) -> str:
    t = str(v or "").strip()
    return t if t else "NA"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _discover_candidate_dirs(roots: list[Path]) -> list[Path]:
    dirs: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.name in SIGNAL_FILENAMES:
                dirs.add(p.parent)
                continue
            if p.suffix.lower() not in {".json", ".jsonl", ".csv", ".md", ".txt"}:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if any(tok in text for tok in SIGNAL_TEXT_PATTERNS):
                dirs.add(p.parent)
    return sorted(dirs)


def _choose_dr_method(methods: set[str]) -> str:
    for m in DR_METHOD_CANDIDATES:
        if m in methods:
            return m
    return ""


def _group_rows_by_example(
    rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str, int, int], dict[str, dict[str, str]]], str]:
    by_key: dict[tuple[str, str, int, int], dict[str, dict[str, str]]] = {}
    methods = {str(r.get("method", "")) for r in rows}
    dr_method = _choose_dr_method(methods)
    for r in rows:
        key = (
            _norm(r.get("dataset", "NA")),
            _norm(r.get("example_id", "NA")),
            _safe_int(r.get("seed", 0), 0),
            _safe_int(r.get("budget", 0), 0),
        )
        by_key.setdefault(key, {})[_norm(r.get("method", ""))] = r
    return by_key, dr_method


def _collect_candidate_groups(
    artifact_dir: Path,
) -> dict[tuple[str, str, int, int], list[dict[str, Any]]]:
    out: dict[tuple[str, str, int, int], list[dict[str, Any]]] = {}
    for fn in ("answer_group_summary.csv", "answer_group_table.csv"):
        p = artifact_dir / fn
        if not p.exists():
            continue
        for r in _read_csv(p):
            key = (
                _norm(r.get("dataset", "NA")),
                _norm(r.get("example_id", "NA")),
                _safe_int(r.get("seed", 0), 0),
                _safe_int(r.get("budget", 0), 0),
            )
            out.setdefault(key, []).append(
                {
                    "normalized_answer": _norm(r.get("answer_group", r.get("normalized_answer"))),
                    "support": _safe_int(r.get("support", r.get("support_count", 0)), 0),
                    "source_method": _norm(r.get("method", "NA")),
                }
            )
    return out


def evaluate_artifact(artifact_dir: Path, out_dir: Path) -> ScanResult:
    per_case = artifact_dir / "per_case_method_results.csv"
    if not per_case.exists():
        return ScanResult(
            artifact_path=str(artifact_dir),
            usable=0,
            rejection_reason="missing_per_case_method_results",
            paired_example_count=0,
            dr_method="",
            dr_v2_accuracy=0.0,
            external_l1_max_accuracy=0.0,
            oracle_selector_accuracy=0.0,
            oracle_minus_l1=0.0,
            oracle_minus_dr=0.0,
            gold_present_but_dr_wrong_count=0,
            gold_absent_count=0,
            candidate_answer_group_count_mean=0.0,
            candidate_answer_group_count_median=0.0,
            candidate_answer_group_count_max=0,
            trace_completeness_notes="missing per_case_method_results.csv",
            reconstructed_path="",
        )

    rows = _read_csv(per_case)
    if not rows:
        return ScanResult(
            artifact_path=str(artifact_dir),
            usable=0,
            rejection_reason="empty_per_case_method_results",
            paired_example_count=0,
            dr_method="",
            dr_v2_accuracy=0.0,
            external_l1_max_accuracy=0.0,
            oracle_selector_accuracy=0.0,
            oracle_minus_l1=0.0,
            oracle_minus_dr=0.0,
            gold_present_but_dr_wrong_count=0,
            gold_absent_count=0,
            candidate_answer_group_count_mean=0.0,
            candidate_answer_group_count_median=0.0,
            candidate_answer_group_count_max=0,
            trace_completeness_notes="empty per_case_method_results.csv",
            reconstructed_path="",
        )

    by_key, dr_method = _group_rows_by_example(rows)
    if not dr_method:
        return ScanResult(
            artifact_path=str(artifact_dir),
            usable=0,
            rejection_reason="no_dr_v2_like_method_found",
            paired_example_count=0,
            dr_method="",
            dr_v2_accuracy=0.0,
            external_l1_max_accuracy=0.0,
            oracle_selector_accuracy=0.0,
            oracle_minus_l1=0.0,
            oracle_minus_dr=0.0,
            gold_present_but_dr_wrong_count=0,
            gold_absent_count=0,
            candidate_answer_group_count_mean=0.0,
            candidate_answer_group_count_median=0.0,
            candidate_answer_group_count_max=0,
            trace_completeness_notes="no DR-like method row",
            reconstructed_path="",
        )

    groups_by_key = _collect_candidate_groups(artifact_dir)
    records: list[dict[str, Any]] = []
    group_counts: list[int] = []
    paired = 0
    dr_correct = 0
    l1_correct = 0
    oracle_correct = 0
    gold_present_but_dr_wrong = 0
    gold_absent = 0
    complete_count = 0

    for key, method_map in by_key.items():
        dr_row = method_map.get(dr_method)
        l1_row = method_map.get("external_l1_max")
        if not dr_row or not l1_row:
            continue
        paired += 1
        dataset, example_id, seed, budget = key
        question = _norm(dr_row.get("question", "NA"))
        gold = _norm(dr_row.get("gold_answer", "NA"))
        dr_ans = _norm(dr_row.get("normalized_selected_answer", dr_row.get("final_selected_answer", "NA")))
        l1_ans = _norm(l1_row.get("normalized_selected_answer", l1_row.get("final_selected_answer", "NA")))

        groups = groups_by_key.get(key, [])
        if not groups:
            groups = [{"normalized_answer": dr_ans, "support": 1, "source_method": dr_method}]
        unique_answers = sorted({str(g.get("normalized_answer", "NA")) for g in groups})
        group_counts.append(len(unique_answers))

        has_gold = gold in unique_answers and gold != "NA"
        oracle_ans = gold if has_gold else dr_ans
        dr_ok = int(dr_ans == gold and gold != "NA")
        l1_ok = int(l1_ans == gold and gold != "NA")
        oracle_ok = int(oracle_ans == gold and gold != "NA")
        dr_correct += dr_ok
        l1_correct += l1_ok
        oracle_correct += oracle_ok
        if has_gold and dr_ok == 0:
            gold_present_but_dr_wrong += 1
        if not has_gold:
            gold_absent += 1

        if question != "NA" and dataset != "NA":
            complete_count += 1
        records.append(
            {
                "dataset": dataset,
                "example_id": example_id,
                "seed": seed,
                "budget": budget,
                "question": question,
                "gold_answer": gold,
                "current_dr_v2_method": dr_method,
                "current_dr_v2_answer": dr_ans,
                "external_l1_max_answer": l1_ans,
                "oracle_selector_answer": oracle_ans,
                "current_dr_v2_correct": dr_ok,
                "external_l1_max_correct": l1_ok,
                "oracle_selector_correct": oracle_ok,
                "candidate_groups": groups,
                "source_artifact_path": str(artifact_dir),
            }
        )

    if paired == 0:
        return ScanResult(
            artifact_path=str(artifact_dir),
            usable=0,
            rejection_reason="zero_paired_examples",
            paired_example_count=0,
            dr_method=dr_method,
            dr_v2_accuracy=0.0,
            external_l1_max_accuracy=0.0,
            oracle_selector_accuracy=0.0,
            oracle_minus_l1=0.0,
            oracle_minus_dr=0.0,
            gold_present_but_dr_wrong_count=0,
            gold_absent_count=0,
            candidate_answer_group_count_mean=0.0,
            candidate_answer_group_count_median=0.0,
            candidate_answer_group_count_max=0,
            trace_completeness_notes="no shared DR/L1 examples",
            reconstructed_path="",
        )

    recon_dir = out_dir / "reconstructed_artifacts"
    recon_dir.mkdir(parents=True, exist_ok=True)
    recon_path = recon_dir / f"{artifact_dir.name}_per_example_records.jsonl"
    with recon_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    dr_acc = dr_correct / paired
    l1_acc = l1_correct / paired
    oracle_acc = oracle_correct / paired
    trace_note = f"question+dataset present for {complete_count}/{paired}"
    return ScanResult(
        artifact_path=str(artifact_dir),
        usable=1,
        rejection_reason="",
        paired_example_count=paired,
        dr_method=dr_method,
        dr_v2_accuracy=dr_acc,
        external_l1_max_accuracy=l1_acc,
        oracle_selector_accuracy=oracle_acc,
        oracle_minus_l1=oracle_acc - l1_acc,
        oracle_minus_dr=oracle_acc - dr_acc,
        gold_present_but_dr_wrong_count=gold_present_but_dr_wrong,
        gold_absent_count=gold_absent,
        candidate_answer_group_count_mean=float(mean(group_counts)) if group_counts else 0.0,
        candidate_answer_group_count_median=float(median(group_counts)) if group_counts else 0.0,
        candidate_answer_group_count_max=max(group_counts) if group_counts else 0,
        trace_completeness_notes=trace_note,
        reconstructed_path=str(recon_path),
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--search-roots", nargs="+", default=["outputs", "archive", "logs"])
    p.add_argument("--output-dir", required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = (REPO_ROOT / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    roots = [(REPO_ROOT / r).resolve() for r in args.search_roots]
    candidate_dirs = _discover_candidate_dirs(roots)
    results = [evaluate_artifact(p, out_dir) for p in candidate_dirs]
    results.sort(key=lambda r: (r.usable, r.oracle_minus_l1, r.paired_example_count), reverse=True)

    rows = [r.__dict__ for r in results]
    csv_path = out_dir / "artifact_scan.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        else:
            f.write("artifact_path,usable,rejection_reason\n")

    report = [
        "# Selector Headroom Artifact Scan",
        "",
        f"- search_roots: {', '.join(str(x) for x in roots)}",
        f"- candidate_dirs: {len(candidate_dirs)}",
        f"- usable: {sum(r.usable for r in results)}",
        f"- rejected: {sum(1 for r in results if not r.usable)}",
    ]
    if results:
        best = results[0]
        report.extend(
            [
                "",
                "## Top Artifact",
                f"- path: `{best.artifact_path}`",
                f"- usable: {best.usable}",
                f"- paired_example_count: {best.paired_example_count}",
                f"- dr_v2_accuracy: {best.dr_v2_accuracy:.4f}",
                f"- external_l1_max_accuracy: {best.external_l1_max_accuracy:.4f}",
                f"- oracle_selector_accuracy: {best.oracle_selector_accuracy:.4f}",
                f"- oracle_minus_l1: {best.oracle_minus_l1:.4f}",
                f"- oracle_minus_dr: {best.oracle_minus_dr:.4f}",
            ]
        )
    (out_dir / "artifact_scan_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Wrote {csv_path}")
    print(f"Wrote {out_dir / 'artifact_scan_report.md'}")


if __name__ == "__main__":
    main()
