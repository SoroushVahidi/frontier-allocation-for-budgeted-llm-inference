#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_ROOT = REPO_ROOT / "outputs"

DR_METHOD_PREFERENCE = [
    "direct_reserve_semantic_frontier_v2",
    "direct_reserve_semantic_frontier_v2_selection_fix_v1",
    "direct_reserve_strong_plus_diverse_margin_gated_v1",
    "direct_reserve_strong_plus_diverse_v1",
    "direct_reserve_strong_v1",
    "strict_f3",
]


@dataclass
class ArtifactEval:
    artifact_dir: Path
    paired_example_count: int
    dr_v2_accuracy: float
    external_l1_max_accuracy: float
    oracle_selector_accuracy: float
    oracle_minus_l1: float
    oracle_minus_dr: float
    gold_present_but_dr_wrong_count: int
    gold_absent_count: int
    candidate_group_count_mean: float
    candidate_group_count_median: float
    candidate_group_count_max: int
    trace_completeness: float
    dr_method: str
    rejection_reason: str
    reconstructed_examples: list[dict[str, Any]]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _norm(v: Any) -> str:
    t = str(v or "").strip()
    return t if t else "NA"


def _discover_artifacts(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        if (p / "per_case_method_results.csv").exists() and (p / "answer_group_summary.csv").exists():
            candidates.append(p)
    return candidates


def _choose_dr_method(rows: list[dict[str, str]]) -> str:
    present = {str(r.get("method", "")) for r in rows}
    for method in DR_METHOD_PREFERENCE:
        if method in present:
            return method
    return ""


def evaluate_artifact(artifact_dir: Path) -> ArtifactEval:
    method_rows = _read_csv(artifact_dir / "per_case_method_results.csv")
    group_rows = _read_csv(artifact_dir / "answer_group_summary.csv")
    if not method_rows:
        return ArtifactEval(
            artifact_dir=artifact_dir,
            paired_example_count=0,
            dr_v2_accuracy=0.0,
            external_l1_max_accuracy=0.0,
            oracle_selector_accuracy=0.0,
            oracle_minus_l1=0.0,
            oracle_minus_dr=0.0,
            gold_present_but_dr_wrong_count=0,
            gold_absent_count=0,
            candidate_group_count_mean=0.0,
            candidate_group_count_median=0.0,
            candidate_group_count_max=0,
            trace_completeness=0.0,
            dr_method="",
            rejection_reason="empty_per_case_method_results",
            reconstructed_examples=[],
        )

    dr_method = _choose_dr_method(method_rows)
    if not dr_method:
        return ArtifactEval(
            artifact_dir=artifact_dir,
            paired_example_count=0,
            dr_v2_accuracy=0.0,
            external_l1_max_accuracy=0.0,
            oracle_selector_accuracy=0.0,
            oracle_minus_l1=0.0,
            oracle_minus_dr=0.0,
            gold_present_but_dr_wrong_count=0,
            gold_absent_count=0,
            candidate_group_count_mean=0.0,
            candidate_group_count_median=0.0,
            candidate_group_count_max=0,
            trace_completeness=0.0,
            dr_method="",
            rejection_reason="no_dr_like_method",
            reconstructed_examples=[],
        )

    by_example: dict[str, dict[str, dict[str, str]]] = {}
    meta: dict[str, dict[str, str]] = {}
    for r in method_rows:
        ex = str(r.get("example_id", ""))
        m = str(r.get("method", ""))
        by_example.setdefault(ex, {})[m] = r
        meta[ex] = r

    group_by_example: dict[str, list[dict[str, str]]] = {}
    for r in group_rows:
        group_by_example.setdefault(str(r.get("example_id", "")), []).append(r)

    reconstructed: list[dict[str, Any]] = []
    dr_correct = 0
    l1_correct = 0
    oracle_correct = 0
    gold_present_but_dr_wrong = 0
    gold_absent = 0
    paired = 0
    group_counts: list[int] = []
    complete_rows = 0

    for ex, methods in by_example.items():
        dr_row = methods.get(dr_method)
        l1_row = methods.get("external_l1_max")
        if not dr_row or not l1_row:
            continue
        paired += 1
        gold = _norm(dr_row.get("gold_answer"))
        dr_ans = _norm(dr_row.get("normalized_selected_answer", dr_row.get("final_selected_answer")))
        l1_ans = _norm(l1_row.get("normalized_selected_answer", l1_row.get("final_selected_answer")))
        groups = []
        unique_groups = set()
        for g in group_by_example.get(ex, []):
            ans = _norm(g.get("answer_group"))
            unique_groups.add(ans)
            groups.append(
                {
                    "normalized_answer": ans,
                    "support": _safe_int(g.get("support"), 0),
                    "method": _norm(g.get("method")),
                }
            )
        if not groups:
            groups = [{"normalized_answer": dr_ans, "support": 1, "method": dr_method}]
            unique_groups = {dr_ans}

        has_gold = gold in unique_groups and gold != "NA"
        oracle_ans = gold if has_gold else dr_ans

        dr_ok = int(dr_ans == gold and gold != "NA")
        l1_ok = int(l1_ans == gold and gold != "NA")
        oracle_ok = int(oracle_ans == gold and gold != "NA")
        dr_correct += dr_ok
        l1_correct += l1_ok
        oracle_correct += oracle_ok
        if dr_ok == 0 and has_gold:
            gold_present_but_dr_wrong += 1
        if not has_gold:
            gold_absent += 1
        group_counts.append(len(unique_groups))

        seed = _safe_int(meta[ex].get("seed"), 0)
        budget = _safe_int(meta[ex].get("budget"), 0)
        if seed >= 0 and budget >= 0 and meta[ex].get("question", ""):
            complete_rows += 1
        reconstructed.append(
            {
                "example_id": ex,
                "dataset": _norm(meta[ex].get("dataset")),
                "seed": seed,
                "budget": budget,
                "question": _norm(meta[ex].get("question")),
                "gold_answer": gold,
                "current_dr_v2_answer": dr_ans,
                "external_l1_max_answer": l1_ans,
                "current_dr_v2_correct": dr_ok,
                "external_l1_max_correct": l1_ok,
                "oracle_selector_answer": oracle_ans,
                "oracle_selector_correct": oracle_ok,
                "candidate_groups": groups,
            }
        )

    if paired == 0:
        return ArtifactEval(
            artifact_dir=artifact_dir,
            paired_example_count=0,
            dr_v2_accuracy=0.0,
            external_l1_max_accuracy=0.0,
            oracle_selector_accuracy=0.0,
            oracle_minus_l1=0.0,
            oracle_minus_dr=0.0,
            gold_present_but_dr_wrong_count=0,
            gold_absent_count=0,
            candidate_group_count_mean=0.0,
            candidate_group_count_median=0.0,
            candidate_group_count_max=0,
            trace_completeness=0.0,
            dr_method=dr_method,
            rejection_reason="zero_paired_examples",
            reconstructed_examples=[],
        )

    dr_acc = dr_correct / paired
    l1_acc = l1_correct / paired
    oracle_acc = oracle_correct / paired
    return ArtifactEval(
        artifact_dir=artifact_dir,
        paired_example_count=paired,
        dr_v2_accuracy=dr_acc,
        external_l1_max_accuracy=l1_acc,
        oracle_selector_accuracy=oracle_acc,
        oracle_minus_l1=oracle_acc - l1_acc,
        oracle_minus_dr=oracle_acc - dr_acc,
        gold_present_but_dr_wrong_count=gold_present_but_dr_wrong,
        gold_absent_count=gold_absent,
        candidate_group_count_mean=float(mean(group_counts)) if group_counts else 0.0,
        candidate_group_count_median=float(median(group_counts)) if group_counts else 0.0,
        candidate_group_count_max=max(group_counts) if group_counts else 0,
        trace_completeness=(complete_rows / paired) if paired else 0.0,
        dr_method=dr_method,
        rejection_reason="",
        reconstructed_examples=reconstructed,
    )


def _rank_key(x: ArtifactEval) -> tuple[int, float, int, float]:
    return (
        int(x.oracle_minus_l1 > 0),
        x.oracle_minus_l1,
        x.paired_example_count,
        x.trace_completeness,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    p.add_argument("--artifacts-root", default=str(OUTPUTS_ROOT))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = _discover_artifacts(Path(args.artifacts_root).resolve())
    evals = [evaluate_artifact(p) for p in artifacts]
    evals.sort(key=_rank_key, reverse=True)

    rows: list[dict[str, Any]] = []
    for i, e in enumerate(evals, start=1):
        rows.append(
            {
                "rank": i,
                "artifact_dir": str(e.artifact_dir),
                "paired_example_count": e.paired_example_count,
                "dr_method": e.dr_method,
                "dr_v2_accuracy": e.dr_v2_accuracy,
                "external_l1_max_accuracy": e.external_l1_max_accuracy,
                "oracle_selector_accuracy": e.oracle_selector_accuracy,
                "oracle_minus_l1": e.oracle_minus_l1,
                "oracle_minus_dr": e.oracle_minus_dr,
                "gold_present_but_dr_wrong_count": e.gold_present_but_dr_wrong_count,
                "gold_absent_count": e.gold_absent_count,
                "candidate_answer_group_count_mean": e.candidate_group_count_mean,
                "candidate_answer_group_count_median": e.candidate_group_count_median,
                "candidate_answer_group_count_max": e.candidate_group_count_max,
                "trace_completeness": e.trace_completeness,
                "rejection_reason": e.rejection_reason,
            }
        )

    scan_csv = out_dir / "artifact_scan.csv"
    with scan_csv.open("w", encoding="utf-8", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        else:
            f.write("rank,artifact_dir,rejection_reason\n")

    best = evals[0] if evals else None
    positive = bool(
        best
        and best.paired_example_count > 0
        and best.oracle_minus_l1 > 0
        and best.oracle_minus_dr > 0
        and not best.rejection_reason
    )
    best_dir = out_dir / "best_selector_artifact"
    if positive and best is not None:
        best_dir.mkdir(parents=True, exist_ok=True)
        with (best_dir / "per_example_records.jsonl").open("w", encoding="utf-8") as f:
            for r in best.reconstructed_examples:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    report_lines = [
        "# L1 Defeat Selector Artifact Scan",
        "",
        f"- created_at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"- artifacts_scanned: {len(evals)}",
        f"- output_dir: `{out_dir}`",
        "",
    ]
    if best is None:
        report_lines.append("- no artifacts discovered")
    else:
        report_lines.extend(
            [
                "## Top Artifact",
                f"- artifact: `{best.artifact_dir}`",
                f"- paired_example_count: {best.paired_example_count}",
                f"- dr_method: `{best.dr_method}`",
                f"- dr_v2_accuracy: {best.dr_v2_accuracy:.4f}",
                f"- external_l1_max_accuracy: {best.external_l1_max_accuracy:.4f}",
                f"- oracle_selector_accuracy: {best.oracle_selector_accuracy:.4f}",
                f"- oracle_minus_l1: {best.oracle_minus_l1:.4f}",
                f"- oracle_minus_dr: {best.oracle_minus_dr:.4f}",
                f"- gold_present_but_dr_wrong_count: {best.gold_present_but_dr_wrong_count}",
                f"- gold_absent_count: {best.gold_absent_count}",
                f"- candidate_answer_group_count_mean: {best.candidate_group_count_mean:.2f}",
                f"- candidate_answer_group_count_median: {best.candidate_group_count_median:.2f}",
                f"- candidate_answer_group_count_max: {best.candidate_group_count_max}",
                f"- trace_completeness: {best.trace_completeness:.4f}",
                f"- positive_l1_defeat_artifact: {'yes' if positive else 'no'}",
            ]
        )
    (out_dir / "artifact_scan_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Wrote {scan_csv}")
    print(f"Wrote {out_dir / 'artifact_scan_report.md'}")
    if positive:
        print(f"Reconstructed best artifact: {best_dir / 'per_example_records.jsonl'}")
    else:
        print("No positive L1-defeat artifact found.")


if __name__ == "__main__":
    main()
