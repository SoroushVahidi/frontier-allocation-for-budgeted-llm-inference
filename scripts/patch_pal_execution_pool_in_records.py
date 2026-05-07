#!/usr/bin/env python3
"""Offline: patch saved PAL traces with merged execution-backed selector_candidate_pool rows (no API)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from experiments.controllers import (  # noqa: E402
    _normalize_answer,
    merge_pal_execution_into_selector_candidate_pool,
)


PAL_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"


def _recompute_selector_pool_derived_fields(pool: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "selector_candidate_pool_size": int(len(pool)),
        "selector_candidate_answer_group_count": int(
            len({_normalize_answer(x.get("predicted_answer")) or "__unknown__" for x in pool})
        ),
        "selector_candidate_pool_sources": sorted(
            {str(x.get("source_id", "")) for x in pool if str(x.get("source_id", "")).strip()}
        ),
    }


def _patch_pal_row(row: dict[str, Any]) -> tuple[dict[str, Any], int, Counter[str]]:
    """Returns (updated_row, n_candidates_added, source_metadata_suffix_counts_for_additions)."""
    md = dict(row.get("result_metadata") or {})
    if not md:
        return row, 0, Counter()

    old_pool = md.get("selector_candidate_pool")
    if not isinstance(old_pool, list):
        old_pool = []
    pal_meta = md.get("pal_execution")
    if not isinstance(pal_meta, dict):
        pal_meta = {}

    fa = str(
        row.get("final_answer_raw") or row.get("controller_final_answer_raw") or row.get("selected_answer_raw") or ""
    ).strip()
    sel_g = _normalize_answer(fa) or "__unknown__"
    actions_used = 0
    try:
        v = row.get("cohere_logical_api_calls")
        if v is not None:
            actions_used = int(v)
    except (TypeError, ValueError):
        actions_used = 0

    new_pool = merge_pal_execution_into_selector_candidate_pool(
        old_pool,
        pal_meta,
        actions_used=int(actions_used),
        selected_group_key=str(sel_g),
    )
    additions = Counter()
    if json.dumps(old_pool, sort_keys=True) == json.dumps(new_pool, sort_keys=True):
        return row, 0, Counter()

    if len(new_pool) > len(old_pool):
        for extra in new_pool[len(old_pool) :]:
            if isinstance(extra, dict):
                sm = str(extra.get("source_metadata") or "")
                suffix = sm.split(":", 1)[-1] if ":" in sm else sm
                if suffix:
                    additions[suffix] += 1

    md["selector_candidate_pool"] = new_pool
    md.update(_recompute_selector_pool_derived_fields(new_pool))

    row2 = dict(row)
    row2["result_metadata"] = md
    return row2, len(new_pool) - len(old_pool), additions


def patch_jsonl_inplace(
    path: Path,
) -> tuple[int, int, int, int, Counter[str]]:
    """Returns PAL_rows, PAL_changed, candidates_added_total, total_rows, label_counts merged."""
    total = 0
    pal_seen = 0
    pal_changed = 0
    candidates_added = 0
    all_labels: Counter[str] = Counter()

    lines_in = path.read_text(encoding="utf-8").splitlines()
    out_rows: list[dict[str, Any]] = []
    for line in lines_in:
        line = line.strip()
        if not line:
            continue
        total += 1
        row = json.loads(line)
        if str(row.get("method") or "") != PAL_METHOD:
            out_rows.append(row)
            continue
        pal_seen += 1
        old_dump = json.dumps(row, sort_keys=True)
        new_row, n_add, labels = _patch_pal_row(row)
        new_dump = json.dumps(new_row, sort_keys=True)
        if new_dump != old_dump:
            pal_changed += 1
        candidates_added += n_add
        all_labels.update(labels)
        out_rows.append(new_row)

    with path.open("w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return pal_seen, pal_changed, candidates_added, total, all_labels


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Source bundle directory (e.g. outputs/...300case.../)",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Destination bundle directory (copied then patched)",
    )
    args = ap.parse_args()
    src: Path = args.input_dir.resolve()
    dst: Path = args.output_dir.resolve()
    if not (src / "per_example_records.jsonl").is_file():
        raise SystemExit(f"missing per_example_records.jsonl under {src}")

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    jsonl = dst / "per_example_records.jsonl"
    pal_seen, pal_changed, cand_add, total, labels = patch_jsonl_inplace(jsonl)

    summary = {
        "input_dir": str(src),
        "output_dir": str(dst),
        "total_rows": int(total),
        "pal_rows_seen": int(pal_seen),
        "pal_rows_changed": int(pal_changed),
        "candidates_added": int(cand_add),
        "added_source_label_counts": dict(sorted(labels.items(), key=lambda kv: (-kv[1], kv[0]))),
    }
    (dst / "poolfix_patch_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
