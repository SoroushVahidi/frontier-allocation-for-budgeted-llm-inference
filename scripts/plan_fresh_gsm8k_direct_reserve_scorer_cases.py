#!/usr/bin/env python3
"""Plan fresh unseen GSM8K cases for diagnostic direct-reserve scorer validation."""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.hf_datasets import resolve_dataset_spec
from experiments.output_layer_repair import canonicalize_answer
from experiments.data import extract_final_answer

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
    "normalized_gold_answer",
    "seed",
    "budget",
    "stratum",
    "source_path",
    "excluded_overlap",
]
CANDIDATE_FIELDS = [
    "example_id",
    "dataset",
    "split",
    "question",
    "gold_answer_raw",
    "gold_answer",
    "normalized_gold_answer",
    "stratum",
    "source_path",
]
EXCLUDED_FIELDS = ["source_label", "source_root", "source_csv", "problem_id"]
OVERLAP_FIELDS = [
    "total_excluded_ids",
    "source_label",
    "new_planned_ids",
    "source_excluded_ids",
    "overlap_count_with_source",
    "overlap_ids_with_source",
    "overlap_count_prior_scorer_slice_1",
    "overlap_count_prior_scorer_slice_2",
    "overlap_count_replay_seed",
    "total_overlap_count",
    "total_overlap_ids",
]
SAMPLED_FIELDS = ["case_idx", "example_id", "stratum"]


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
    extra = [k for row in rows for k in row if k not in fields]
    fieldnames = fields + sorted(set(extra))
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _norm_answer(raw: Any, dataset: str) -> str:
    txt = str(raw or "").strip()
    if not txt:
        return "NA"
    if dataset == "openai/gsm8k":
        txt = extract_final_answer(txt)
    try:
        return str(canonicalize_answer(txt, dataset=dataset))
    except Exception:
        return txt


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
        if idx == 1:
            label = "prior_scorer_slice_1"
        elif idx == 2:
            label = "prior_scorer_slice_2"
        elif "replay" in root.name.lower():
            label = "replay_seed"
        else:
            label = f"source_{idx}"
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


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        val = row.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def load_synthetic_examples(path_text: str, dataset: str, split: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = _path(path_text)
    if path.suffix == ".jsonl":
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        records = _read_csv(path)
    pool: list[dict[str, Any]] = []
    for idx, row in enumerate(records):
        pid = str(row.get("example_id") or f"{dataset.replace('/', '_')}_{idx}").strip()
        question = _pick(row, ("question", "problem", "prompt"))
        answer = _pick(row, ("answer", "gold_answer", "ground_truth", "target"))
        if not pid or not question or not answer:
            continue
        norm = _norm_answer(answer, dataset)
        pool.append(
            {
                "example_id": pid,
                "dataset": dataset,
                "split": split,
                "question": question,
                "gold_answer_raw": answer,
                "gold_answer": norm,
                "normalized_gold_answer": norm,
                "stratum": str(row.get("stratum") or "fresh_gsm8k_unseen"),
                "source_path": str(path),
            }
        )
    return pool, {"loader": "synthetic_input", "path": str(path), "ok": True}


def load_hf_gsm8k(dataset: str, split: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spec = resolve_dataset_spec(dataset)
    try:
        from datasets import load_dataset  # type: ignore
    except Exception as exc:
        return [], {
            "loader": "huggingface_datasets",
            "ok": False,
            "error": f"datasets import failed: {type(exc).__name__}: {exc}",
            "setup": "Install dev/runtime deps, e.g. `.venv/bin/python -m pip install -r requirements-dev.txt`, then rerun the planner.",
        }
    try:
        if spec.default_config is None:
            ds = load_dataset(spec.repo_id, split=split)
        else:
            ds = load_dataset(spec.repo_id, spec.default_config, split=split)
    except Exception as exc:
        return [], {
            "loader": "huggingface_datasets",
            "ok": False,
            "dataset": dataset,
            "split": split,
            "error": f"{type(exc).__name__}: {exc}",
            "setup": "Ensure network/Hugging Face access works, then rerun this planner. GSM8K is public and should not require a token.",
        }

    pool: list[dict[str, Any]] = []
    for idx, row in enumerate(ds):
        if not isinstance(row, dict):
            continue
        question = _pick(row, spec.question_fields)
        answer = _pick(row, spec.answer_fields)
        if not question or not answer:
            continue
        norm = _norm_answer(answer, dataset)
        pool.append(
            {
                "example_id": f"{dataset.replace('/', '_')}_{idx}",
                "dataset": dataset,
                "split": split,
                "question": question,
                "gold_answer_raw": answer,
                "gold_answer": norm,
                "normalized_gold_answer": norm,
                "stratum": "fresh_gsm8k_unseen",
                "source_path": f"hf://datasets/{spec.repo_id}/{split}",
            }
        )
    return pool, {
        "loader": "huggingface_datasets",
        "ok": True,
        "dataset": dataset,
        "repo_id": spec.repo_id,
        "config": spec.default_config or "",
        "split": split,
        "n_loaded": len(pool),
    }


def sample_cases(pool: list[dict[str, Any]], max_cases: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    unique = {str(row["example_id"]): row for row in pool}
    rows = list(unique.values())
    rng.shuffle(rows)
    return rows[:max_cases]


def _ids_csv(ids: set[str]) -> str:
    return ";".join(sorted(ids))


def build_overlap_rows(by_source: dict[str, set[str]], planned_ids: set[str]) -> list[dict[str, Any]]:
    union = set().union(*by_source.values()) if by_source else set()
    source_overlaps = {label: planned_ids & ids for label, ids in by_source.items()}
    rows: list[dict[str, Any]] = []
    for label, ids in by_source.items():
        rows.append(
            {
                "total_excluded_ids": len(union),
                "source_label": label,
                "new_planned_ids": _ids_csv(planned_ids),
                "source_excluded_ids": _ids_csv(ids),
                "overlap_count_with_source": len(source_overlaps.get(label, set())),
                "overlap_ids_with_source": _ids_csv(source_overlaps.get(label, set())),
                "overlap_count_prior_scorer_slice_1": len(source_overlaps.get("prior_scorer_slice_1", set())),
                "overlap_count_prior_scorer_slice_2": len(source_overlaps.get("prior_scorer_slice_2", set())),
                "overlap_count_replay_seed": len(source_overlaps.get("replay_seed", set())),
                "total_overlap_count": len(planned_ids & union),
                "total_overlap_ids": _ids_csv(planned_ids & union),
            }
        )
    if not rows:
        rows.append(
            {
                "total_excluded_ids": 0,
                "source_label": "none",
                "new_planned_ids": _ids_csv(planned_ids),
                "source_excluded_ids": "",
                "overlap_count_with_source": 0,
                "overlap_ids_with_source": "",
                "overlap_count_prior_scorer_slice_1": 0,
                "overlap_count_prior_scorer_slice_2": 0,
                "overlap_count_replay_seed": 0,
                "total_overlap_count": 0,
                "total_overlap_ids": "",
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--split", default="test", choices=("test", "train"))
    p.add_argument("--max-cases", type=int, default=20)
    p.add_argument("--allow-over-30", action="store_true")
    p.add_argument("--seed", type=int, default=43)
    p.add_argument("--budget", type=int, default=4)
    p.add_argument("--exclude-output", action="append", default=[])
    p.add_argument("--output-dir", default="")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--synthetic-input", default="", help="CSV/JSONL GSM8K-like source for no-network tests.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.dataset != "openai/gsm8k":
        raise SystemExit("This fresh planner is intentionally scoped to --dataset openai/gsm8k.")
    if args.budget != 4:
        raise SystemExit("Refusing plan: budget must be 4 for this diagnostic scorer validation.")
    if args.max_cases > 30 and not args.allow_over_30:
        raise SystemExit("Refusing plan: --max-cases has a hard cap of 30 unless --allow-over-30 is set.")

    out_dir = _path(args.output_dir) if args.output_dir else REPO_ROOT / "outputs" / f"fresh_gsm8k_direct_reserve_scorer_plan_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    excluded_rows, by_source = collect_excluded(args.exclude_output)
    excluded_ids = {str(row["problem_id"]) for row in excluded_rows}

    if args.synthetic_input:
        pool, load_report = load_synthetic_examples(args.synthetic_input, args.dataset, args.split)
    else:
        pool, load_report = load_hf_gsm8k(args.dataset, args.split)

    fresh_pool = [row for row in pool if str(row["example_id"]) not in excluded_ids]
    sampled = sample_cases(fresh_pool, max(0, args.max_cases), args.seed)
    planned_ids = {str(row["example_id"]) for row in sampled}
    overlap = build_overlap_rows(by_source, planned_ids)
    total_overlap = max(int(row["total_overlap_count"]) for row in overlap) if overlap else 0
    if total_overlap:
        _write_csv(out_dir / "excluded_problem_ids.csv", excluded_rows, EXCLUDED_FIELDS)
        _write_csv(out_dir / "fresh_candidate_pool.csv", fresh_pool, CANDIDATE_FIELDS)
        _write_csv(out_dir / "sampled_problem_ids.csv", [], SAMPLED_FIELDS)
        _write_csv(out_dir / "overlap_report.csv", overlap, OVERLAP_FIELDS)
        raise SystemExit(f"Refusing to write planned_cases.csv: fresh plan overlaps excluded IDs ({total_overlap}).")

    planned: list[dict[str, Any]] = []
    for idx, row in enumerate(sampled, start=1):
        planned.append(
            {
                "case_idx": idx,
                "example_id": row["example_id"],
                "dataset": row["dataset"],
                "question": row["question"],
                "gold_answer_raw": row["gold_answer_raw"],
                "gold_answer": row["gold_answer"],
                "normalized_gold_answer": row["normalized_gold_answer"],
                "seed": args.seed,
                "budget": args.budget,
                "stratum": row.get("stratum", "fresh_gsm8k_unseen"),
                "source_path": row.get("source_path", ""),
                "excluded_overlap": 0,
            }
        )

    status = "ok" if load_report.get("ok") and len(planned) >= args.max_cases else "insufficient_fresh_candidates"
    if not load_report.get("ok"):
        status = "gsm8k_load_failed"
    manifest = {
        "status": status,
        "dataset": args.dataset,
        "split": args.split,
        "budget": args.budget,
        "seed": args.seed,
        "max_cases": args.max_cases,
        "n_loaded_problem_ids": len({str(row["example_id"]) for row in pool}),
        "n_excluded_problem_ids": len(excluded_ids),
        "n_fresh_candidates": len(fresh_pool),
        "n_planned_problem_ids": len(planned_ids),
        "total_overlap_count": total_overlap,
        "load_report": load_report,
        "exclude_outputs": args.exclude_output,
    }

    sampled_rows = [{"case_idx": row["case_idx"], "example_id": row["example_id"], "stratum": row["stratum"]} for row in planned]
    _write_csv(out_dir / "planned_cases.csv", planned, PLANNED_FIELDS)
    _write_csv(out_dir / "excluded_problem_ids.csv", excluded_rows, EXCLUDED_FIELDS)
    _write_csv(out_dir / "fresh_candidate_pool.csv", fresh_pool, CANDIDATE_FIELDS)
    _write_csv(out_dir / "sampled_problem_ids.csv", sampled_rows, SAMPLED_FIELDS)
    _write_csv(out_dir / "overlap_report.csv", overlap, OVERLAP_FIELDS)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readme_lines = [
        "# Fresh GSM8K direct-reserve scorer case plan",
        "",
        f"- Status: `{status}`",
        f"- Dataset: `{args.dataset}`",
        f"- Split: `{args.split}`",
        f"- Budget: `{args.budget}`",
        f"- Seed: `{args.seed}`",
        f"- Loader: `{load_report.get('loader', 'unknown')}`",
        f"- Loaded problem IDs: {manifest['n_loaded_problem_ids']}",
        f"- Excluded problem IDs: {len(excluded_ids)}",
        f"- Fresh candidates after exclusion: {len(fresh_pool)}",
        f"- Planned problem IDs: {len(planned_ids)}",
        f"- Total overlap with excluded sources: {total_overlap}",
        "",
        "This planner is diagnostic-only and does not call model APIs.",
    ]
    if not load_report.get("ok"):
        readme_lines.extend(
            [
                "",
                f"Setup needed: {load_report.get('setup', 'Fix GSM8K loading and rerun the planner.')}",
            ]
        )
    (out_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_dir} (status={status}, planned={len(planned_ids)}, excluded={len(excluded_ids)}, overlap={total_overlap})")


if __name__ == "__main__":
    main()
