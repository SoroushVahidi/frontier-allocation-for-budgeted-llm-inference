#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SELECTOR_METHODS = {
    "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
    "direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1",
}


def _as_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _get_verifier_calls(md: dict[str, Any]) -> int:
    return _as_int(md.get("verifier_calls", md.get("prm_step_verifier_calls", 0)), 0)


def run_diag(artifact_dir: Path, ts: str) -> dict[str, Any]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    rec = artifact_dir / "per_example_records.jsonl"
    rows: list[dict[str, Any]] = []
    if rec.exists():
        for ln in rec.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                row = json.loads(ln)
            except Exception:
                continue
            if row.get("method") in SELECTOR_METHODS:
                rows.append(row)

    by_method = Counter()
    candidate_count = Counter()
    answer_group_count = Counter()
    extraction_sources = Counter()
    fallback_reasons = Counter()
    ov_applied = Counter()
    prm_applied = Counter()
    verifier_calls = Counter()
    backend_values = Counter()
    gold_present = Counter()
    recovered = Counter()

    for r in rows:
        m = str(r.get("method", ""))
        by_method[m] += 1
        md = r.get("metadata", {}) if isinstance(r.get("metadata", {}), dict) else {}
        if not md and isinstance(r.get("result_metadata", {}), dict):
            md = r.get("result_metadata", {})
        c = _as_int(md.get("candidate_count", 0), 0)
        g = _as_int(md.get("answer_group_count", 0), 0)
        candidate_count[c] += 1
        answer_group_count[g] += 1
        fallback_reasons[str(md.get("fallback_reason", "") or "")] += 1
        ov_applied[bool(md.get("ov_rerank_applied", False))] += 1
        prm_applied[bool(md.get("prm_rerank_applied", False))] += 1
        verifier_calls[_get_verifier_calls(md)] += 1

        srcs = md.get("candidate_extraction_sources", [])
        if isinstance(srcs, list):
            for s in srcs:
                extraction_sources[str(s)] += 1
        elif srcs:
            extraction_sources[str(srcs)] += 1

        if "verifier_backend" in md:
            backend_values[str(md.get("verifier_backend", ""))] += 1
        if "prm_step_verifier_backend" in md:
            backend_values[str(md.get("prm_step_verifier_backend", ""))] += 1

        gold_present["ov"] += _as_int(md.get("ov_rerank_gold_present_in_candidates", 0), 0)
        gold_present["prm"] += _as_int(md.get("prm_gold_present_in_candidates", 0), 0)
        recovered["ov"] += _as_int(md.get("ov_rerank_recovered_present_not_selected", 0), 0)
        recovered["prm"] += _as_int(md.get("prm_recovered_present_not_selected", 0), 0)

    summary = {
        "artifact_dir": str(artifact_dir),
        "timestamp": ts,
        "rows_total": len(rows),
        "rows_by_method": dict(by_method),
        "candidate_count_distribution": dict(candidate_count),
        "answer_group_count_distribution": dict(answer_group_count),
        "candidate_extraction_sources_distribution": dict(extraction_sources),
        "fallback_reason_distribution": dict(fallback_reasons),
        "ov_rerank_applied": dict(ov_applied),
        "prm_rerank_applied": dict(prm_applied),
        "verifier_calls_distribution": dict(verifier_calls),
        "backend_values": dict(backend_values),
        "gold_present_in_candidates": dict(gold_present),
        "recovered_present_not_selected": dict(recovered),
        "candidate_count_gt_1": sum(v for k, v in candidate_count.items() if int(k) > 1),
        "answer_group_count_gt_1": sum(v for k, v in answer_group_count.items() if int(k) > 1),
    }

    out_json = artifact_dir / f"selector_candidate_surface_summary_{ts}.json"
    out_csv = artifact_dir / f"selector_candidate_surface_rows_{ts}.csv"
    out_md = Path("docs") / f"SELECTOR_CANDIDATE_SURFACE_DIAGNOSIS_{ts}.md"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "example_id",
                "method",
                "candidate_count",
                "answer_group_count",
                "candidate_extraction_sources",
                "fallback_reason",
                "ov_rerank_applied",
                "prm_rerank_applied",
                "verifier_calls",
                "backend",
            ],
        )
        w.writeheader()
        for r in rows:
            md = r.get("metadata", {}) if isinstance(r.get("metadata", {}), dict) else {}
            if not md and isinstance(r.get("result_metadata", {}), dict):
                md = r.get("result_metadata", {})
            w.writerow(
                {
                    "example_id": r.get("example_id", ""),
                    "method": r.get("method", ""),
                    "candidate_count": _as_int(md.get("candidate_count", 0), 0),
                    "answer_group_count": _as_int(md.get("answer_group_count", 0), 0),
                    "candidate_extraction_sources": json.dumps(md.get("candidate_extraction_sources", [])),
                    "fallback_reason": md.get("fallback_reason", ""),
                    "ov_rerank_applied": bool(md.get("ov_rerank_applied", False)),
                    "prm_rerank_applied": bool(md.get("prm_rerank_applied", False)),
                    "verifier_calls": _get_verifier_calls(md),
                    "backend": md.get("verifier_backend", md.get("prm_step_verifier_backend", "")),
                }
            )

    out_md.write_text("# Selector Candidate Surface Diagnosis\n\n```json\n" + json.dumps(summary, indent=2) + "\n```\n", encoding="utf-8")
    print(out_json)
    print(out_csv)
    print(out_md)
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--artifact-dir", required=True)
    p.add_argument("--timestamp", required=True)
    args = p.parse_args()
    run_diag(Path(args.artifact_dir), args.timestamp)


if __name__ == "__main__":
    main()
