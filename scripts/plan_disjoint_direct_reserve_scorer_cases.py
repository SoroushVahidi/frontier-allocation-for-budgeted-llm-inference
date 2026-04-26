#!/usr/bin/env python3
"""Plan a truly disjoint Cohere direct-reserve scorer validation slice."""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.output_layer_repair import canonicalize_answer
DEFAULT_LOSS = "outputs/matched_surface_multiseed_main_comparison_20260423T203259Z/raw_case_results.csv"
TARGET_STRATA = {
    "absent_from_tree": "absent",
    "present_not_selected": "present-not-selected",
    "control_correct": "control",
}
CASE_CSV_NAMES = {
    "planned_cases.csv",
    "per_case_method_results.csv",
    "replay_case_list.csv",
    "case_level_selection.csv",
}
CASE_CSV_TOKENS = ("case", "result", "replay", "selection", "candidate")
PLANNED_FIELDS = [
    "case_idx",
    "example_id",
    "dataset",
    "question",
    "gold_answer_raw",
    "gold_answer",
    "seed",
    "budget",
    "stratum",
    "source_path",
    "excluded_overlap",
]
CANDIDATE_FIELDS = [
    "example_id",
    "dataset",
    "question",
    "gold_answer_raw",
    "gold_answer",
    "stratum",
    "source_path",
]
EXCLUDED_FIELDS = ["source_label", "source_root", "source_csv", "problem_id"]
OVERLAP_FIELDS = [
    "source_label",
    "first_slice_excluded_ids",
    "second_slice_excluded_ids",
    "new_planned_ids",
    "source_excluded_ids",
    "overlap_count_with_source",
    "overlap_ids_with_source",
    "total_overlap_count",
    "total_overlap_ids",
]
STRATUM_FIELDS = ["stratum", "label", "requested", "available_after_exclusion", "planned"]


def _path(text: str | Path) -> Path:
    p = Path(text)
    return p if p.is_absolute() else REPO_ROOT / p


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    extra = [k for row in rows for k in row.keys() if k not in fields]
    fieldnames = fields + sorted(set(extra))
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _norm_answer(raw: Any, dataset: str) -> str:
    txt = str(raw or "").strip()
    if not txt:
        return "NA"
    try:
        return str(canonicalize_answer(txt, dataset=dataset))
    except Exception:
        return txt


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _infer_stratum(row: dict[str, str]) -> str:
    failure = str(row.get("failure_type", "") or row.get("stratum", "")).strip().lower()
    if _truthy(row.get("absent_from_tree")) or "absent" in failure:
        return "absent_from_tree"
    if _truthy(row.get("present_not_selected")) or "present_not_selected" in failure or "present-not-selected" in failure:
        return "present_not_selected"
    if _truthy(row.get("is_correct")) or failure in {"", "correct", "control", "control_correct", "none", "na"}:
        return "control_correct"
    return "unknown"


def _problem_id(row: dict[str, str]) -> str:
    for key in ("example_id", "problem_id", "gsm8k_id"):
        val = str(row.get(key, "") or "").strip()
        if val:
            return val
    return ""


def _case_csvs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file() and root.suffix == ".csv":
        return [root]
    out: list[Path] = []
    for path in root.rglob("*.csv"):
        name = path.name.lower()
        if name in CASE_CSV_NAMES or any(tok in name for tok in CASE_CSV_TOKENS):
            out.append(path)
    return sorted(out)


def collect_excluded(dirs: list[str]) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    rows: list[dict[str, Any]] = []
    by_source: dict[str, set[str]] = {}
    for idx, raw in enumerate(dirs, start=1):
        root = _path(raw)
        label = "first_slice" if idx == 1 else "second_slice" if idx == 2 else f"source_{idx}"
        ids: set[str] = set()
        for csv_path in _case_csvs(root):
            for row in _read_csv(csv_path):
                pid = _problem_id(row)
                if not pid:
                    continue
                ids.add(pid)
                rows.append(
                    {
                        "source_label": label,
                        "source_root": str(root),
                        "source_csv": str(csv_path),
                        "problem_id": pid,
                    }
                )
        by_source[label] = ids
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        deduped[(str(row["source_label"]), str(row["problem_id"]))] = row
    return list(deduped.values()), by_source


def collect_pool(paths: list[str], dataset: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in paths:
        path = _path(raw)
        for row in _read_csv(path):
            ds = str(row.get("dataset") or dataset).strip()
            if ds != dataset:
                continue
            pid = _problem_id(row)
            question = str(row.get("question") or row.get("problem") or row.get("prompt") or "").strip()
            gold_raw = str(row.get("gold_answer") or row.get("ground_truth") or row.get("answer") or row.get("target") or "").strip()
            if not pid or not question or not gold_raw:
                continue
            rows.append(
                {
                    "example_id": pid,
                    "dataset": ds,
                    "question": question,
                    "gold_answer_raw": gold_raw,
                    "gold_answer": _norm_answer(gold_raw, ds),
                    "stratum": _infer_stratum(row),
                    "source_path": str(path),
                }
            )
    return rows


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        pid = str(row.get("example_id", ""))
        if pid in seen:
            continue
        seen.add(pid)
        out.append(row)
    return out


def select_cases(
    pool: list[dict[str, Any]],
    max_cases: int,
    absent: int,
    present: int,
    control: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    unique = _dedupe(pool)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unique:
        buckets[str(row.get("stratum", "unknown"))].append(row)
    for rows in buckets.values():
        rng.shuffle(rows)

    plan: list[dict[str, Any]] = []
    selected: set[str] = set()
    for stratum, need in (
        ("absent_from_tree", absent),
        ("present_not_selected", present),
        ("control_correct", control),
    ):
        for row in buckets.get(stratum, [])[: max(0, need)]:
            if len(plan) >= max_cases:
                break
            plan.append(row)
            selected.add(str(row["example_id"]))

    fallback = [row for row in unique if str(row["example_id"]) not in selected]
    rng.shuffle(fallback)
    for row in fallback:
        if len(plan) >= max_cases:
            break
        plan.append(row)
    return plan


def _ids_csv(ids: set[str]) -> str:
    return ";".join(sorted(ids))


def overlap_rows(by_source: dict[str, set[str]], planned_ids: set[str]) -> list[dict[str, Any]]:
    first_ids = by_source.get("first_slice", set())
    second_ids = by_source.get("second_slice", set())
    union = set().union(*by_source.values()) if by_source else set()
    rows: list[dict[str, Any]] = []
    for label, ids in by_source.items():
        overlap = planned_ids & ids
        rows.append(
            {
                "source_label": label,
                "first_slice_excluded_ids": _ids_csv(first_ids),
                "second_slice_excluded_ids": _ids_csv(second_ids),
                "new_planned_ids": _ids_csv(planned_ids),
                "source_excluded_ids": _ids_csv(ids),
                "overlap_count_with_source": len(overlap),
                "overlap_ids_with_source": _ids_csv(overlap),
                "total_overlap_count": len(planned_ids & union),
                "total_overlap_ids": _ids_csv(planned_ids & union),
            }
        )
    if not rows:
        rows.append(
            {
                "source_label": "none",
                "first_slice_excluded_ids": "",
                "second_slice_excluded_ids": "",
                "new_planned_ids": _ids_csv(planned_ids),
                "source_excluded_ids": "",
                "overlap_count_with_source": 0,
                "overlap_ids_with_source": "",
                "total_overlap_count": 0,
                "total_overlap_ids": "",
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--exclude-output", action="append", default=[], help="Prior scorer validation output directory to exclude.")
    p.add_argument("--loss-artifact", action="append", default=[], help=f"Planning source CSV. Default: {DEFAULT_LOSS}")
    p.add_argument("--max-cases", type=int, default=20)
    p.add_argument("--allow-over-30", action="store_true", help="Explicitly allow --max-cases above 30.")
    p.add_argument("--absent-count", type=int, default=7)
    p.add_argument("--present-count", type=int, default=6)
    p.add_argument("--control-count", type=int, default=7)
    p.add_argument("--seed", type=int, default=37)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--budget", type=int, default=4)
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--output-dir", default="")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.budget != 4:
        raise SystemExit("Refusing plan: budget must be 4 for this diagnostic scorer validation.")
    if args.max_cases > 30 and not args.allow_over_30:
        raise SystemExit("Refusing plan: --max-cases has a hard cap of 30 unless --allow-over-30 is set.")
    max_cases = max(0, int(args.max_cases))
    loss_artifacts = args.loss_artifact or [DEFAULT_LOSS]
    out_dir = _path(args.output_dir) if args.output_dir else REPO_ROOT / "outputs" / f"direct_reserve_disjoint_case_plan_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    excluded_rows, by_source = collect_excluded(args.exclude_output)
    excluded_ids = {str(r["problem_id"]) for r in excluded_rows}
    pool = collect_pool(loss_artifacts, args.dataset)
    unique_pool = _dedupe(pool)
    after = [row for row in unique_pool if str(row["example_id"]) not in excluded_ids]
    planned_base = select_cases(after, max_cases, args.absent_count, args.present_count, args.control_count, args.seed)
    planned_ids = {str(row["example_id"]) for row in planned_base}
    reports = overlap_rows(by_source, planned_ids)
    total_overlap = max(int(row["total_overlap_count"]) for row in reports) if reports else 0
    if total_overlap:
        _write_csv(out_dir / "excluded_problem_ids.csv", excluded_rows, EXCLUDED_FIELDS)
        _write_csv(out_dir / "candidate_pool_after_exclusion.csv", after, CANDIDATE_FIELDS)
        _write_csv(out_dir / "overlap_report.csv", reports, OVERLAP_FIELDS)
        raise SystemExit(f"Refusing to write planned_cases.csv: planned IDs overlap excluded IDs ({total_overlap}).")

    planned: list[dict[str, Any]] = []
    for idx, row in enumerate(planned_base, start=1):
        planned.append(
            {
                "case_idx": idx,
                "example_id": row["example_id"],
                "dataset": row["dataset"],
                "question": row["question"],
                "gold_answer_raw": row["gold_answer_raw"],
                "gold_answer": row["gold_answer"],
                "seed": args.seed,
                "budget": args.budget,
                "stratum": row.get("stratum", "unknown"),
                "source_path": row.get("source_path", ""),
                "excluded_overlap": 0,
            }
        )

    requested = {
        "absent_from_tree": args.absent_count,
        "present_not_selected": args.present_count,
        "control_correct": args.control_count,
    }
    available_counts = Counter(str(row.get("stratum", "unknown")) for row in after)
    planned_counts = Counter(str(row.get("stratum", "unknown")) for row in planned)
    stratum_rows = [
        {
            "stratum": stratum,
            "label": TARGET_STRATA.get(stratum, stratum),
            "requested": requested.get(stratum, 0),
            "available_after_exclusion": available_counts.get(stratum, 0),
            "planned": planned_counts.get(stratum, 0),
        }
        for stratum in ("absent_from_tree", "present_not_selected", "control_correct", "unknown")
    ]
    status = "ok" if len(planned) >= min(max_cases, sum(requested.values())) else "insufficient_disjoint_candidates"
    manifest = {
        "status": status,
        "dataset": args.dataset,
        "budget": args.budget,
        "seed": args.seed,
        "max_cases": max_cases,
        "loss_artifacts": loss_artifacts,
        "exclude_outputs": args.exclude_output,
        "n_excluded_problem_ids": len(excluded_ids),
        "n_candidate_problem_ids": len(unique_pool),
        "n_candidates_after_exclusion": len(after),
        "n_planned_problem_ids": len(planned_ids),
        "total_overlap_count": total_overlap,
    }

    _write_csv(out_dir / "planned_cases.csv", planned, PLANNED_FIELDS)
    _write_csv(out_dir / "excluded_problem_ids.csv", excluded_rows, EXCLUDED_FIELDS)
    _write_csv(out_dir / "candidate_pool_after_exclusion.csv", after, CANDIDATE_FIELDS)
    _write_csv(out_dir / "stratum_counts.csv", stratum_rows, STRATUM_FIELDS)
    _write_csv(out_dir / "overlap_report.csv", reports, OVERLAP_FIELDS)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(
        "\n".join(
            [
                "# Direct-reserve disjoint scorer case plan",
                "",
                f"- Status: `{status}`",
                f"- Dataset: `{args.dataset}`",
                f"- Budget: `{args.budget}`",
                f"- Seed: `{args.seed}`",
                f"- Excluded problem IDs: {len(excluded_ids)}",
                f"- Candidate problem IDs before exclusion: {len(unique_pool)}",
                f"- Candidate problem IDs after exclusion: {len(after)}",
                f"- Planned problem IDs: {len(planned_ids)}",
                f"- Total overlap with excluded sources: {total_overlap}",
                "",
                "This utility is diagnostic-only and does not call any model API.",
                "If `status` is `insufficient_disjoint_candidates`, expand the planning source before reusing old IDs.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out_dir} (status={status}, planned={len(planned_ids)}, excluded={len(excluded_ids)}, overlap={total_overlap})")


if __name__ == "__main__":
    main()
