#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def i(x, d=0):
    try:
        return int(float(x))
    except Exception:
        return d


def to_key(r: dict) -> tuple[str, str, str, str]:
    return (str(r.get("dataset", "")), str(r.get("seed", "")), str(r.get("budget", "")), str(r.get("example_id", "")))


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bottleneck audit for Cohere DR-v2 vs external_l1_max using existing artifacts.")
    ap.add_argument("--input-dirs", required=True, help="Comma-separated artifact directories.")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--fallback-doc", default="docs/COHERE_DIRECT_RESERVE_V2_LOCAL_PARTIAL_AUDIT_20260428T223833Z.md")
    return ap.parse_args()


def infer_from_doc(doc: Path) -> dict:
    out = {"paired_delta": None, "matched": 0}
    if not doc.exists():
        return out
    txt = doc.read_text(encoding="utf-8")
    m = re.search(r"Paired exact-match delta:\s*([+-]?\d+(?:\.\d+)?)", txt)
    n = re.search(r"Matched DR-v2 vs external_l1_max paired cases:\s*(\d+)", txt)
    if m:
        out["paired_delta"] = float(m.group(1))
    if n:
        out["matched"] = int(n.group(1))
    return out


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    input_dirs = [Path(x.strip()) for x in args.input_dirs.split(",") if x.strip()]
    per_case: list[dict] = []
    token_rows: list[dict] = []
    discovered: list[str] = []

    for d in input_dirs:
        d = d if d.is_absolute() else REPO_ROOT / d
        if not d.exists():
            continue
        discovered.append(str(d))

        rows = read_csv(d / "per_case_results.csv")
        if not rows:
            for r in read_jsonl(d / "per_example_records.jsonl"):
                rows.append(
                    {
                        "dataset": r.get("dataset", ""),
                        "seed": r.get("seed", ""),
                        "budget": r.get("budget", ""),
                        "method": r.get("method", ""),
                        "example_id": r.get("example_id", ""),
                        "status": r.get("status", ""),
                        "exact_match": r.get("exact_match", ""),
                        "is_correct": r.get("exact_match", ""),
                    }
                )
        per_case += rows
        token_rows += read_csv(d / "token_latency_cost_summary.csv")

    scored = []
    for r in per_case:
        st = str(r.get("status", "")).strip().lower()
        if st and st != "scored":
            continue
        scored.append(r)

    by_method: dict[str, list[dict]] = defaultdict(list)
    for r in scored:
        by_method[str(r.get("method", ""))].append(r)

    dr_rows = by_method.get("direct_reserve_semantic_frontier_v2", [])
    l1_rows = by_method.get("external_l1_max", [])
    dr_map = {to_key(r): r for r in dr_rows}
    l1_map = {to_key(r): r for r in l1_rows}
    keys = sorted(set(dr_map) & set(l1_map))
    deltas = [i(dr_map[k].get("exact_match", dr_map[k].get("is_correct", 0))) - i(l1_map[k].get("exact_match", l1_map[k].get("is_correct", 0))) for k in keys]

    paired_delta = mean(deltas) if deltas else None
    if paired_delta is None:
        doc_fallback = infer_from_doc((REPO_ROOT / args.fallback_doc) if not Path(args.fallback_doc).is_absolute() else Path(args.fallback_doc))
        if doc_fallback["paired_delta"] is not None:
            paired_delta = doc_fallback["paired_delta"]
            keys = [()] * int(doc_fallback["matched"])  # count-only fallback

    budget_break, seed_break, dataset_break = defaultdict(list), defaultdict(list), defaultdict(list)
    for k, d in zip(keys, deltas):
        if len(k) == 4:
            ds, sd, b, _ = k
            budget_break[b].append(d)
            seed_break[sd].append(d)
            dataset_break[ds].append(d)

    tmap = {r.get("method", ""): r for r in token_rows}
    cost_delta = action_delta = token_delta = None
    if "direct_reserve_semantic_frontier_v2" in tmap and "external_l1_max" in tmap:
        a = tmap["direct_reserve_semantic_frontier_v2"]
        b = tmap["external_l1_max"]
        cost_delta = f(a.get("avg_estimated_cost_usd", 0.0)) - f(b.get("avg_estimated_cost_usd", 0.0))
        action_delta = f(a.get("avg_actions", 0.0)) - f(b.get("avg_actions", 0.0))
        token_delta = f(a.get("avg_total_tokens", 0.0)) - f(b.get("avg_total_tokens", 0.0))

    bottlenecks = {
        "data_sample_instability": bool(len(keys) < 50),
        "algorithm_weakness_possible": bool(paired_delta is not None and paired_delta < 0),
        "extraction_canonicalization_issue": "unknown_from_current_artifacts",
        "cost_action_inefficiency": bool((paired_delta is not None and paired_delta <= 0) and (action_delta is not None and action_delta > 0)),
        "proposal_quality_issue": "unknown_from_current_artifacts",
        "final_selection_commit_issue": "unknown_from_current_artifacts",
        "external_l1_stronger_possible": bool(paired_delta is not None and paired_delta < 0),
    }

    recommendation = []
    if bottlenecks["data_sample_instability"]:
        recommendation.append("run_larger_controlled_paired_validation")
    if bottlenecks["cost_action_inefficiency"]:
        recommendation.append("design_cheaper_commit_stop_rule")
    if bottlenecks["algorithm_weakness_possible"] and not bottlenecks["cost_action_inefficiency"]:
        recommendation.append("prioritize_branch_or_selection_diagnosis")
    if not recommendation:
        recommendation.append("insufficient_evidence_collect_targeted_fields")

    summary = {
        "status": "diagnostic_partial_not_headline",
        "input_dirs_requested": [str(x) for x in input_dirs],
        "input_dirs_discovered": discovered,
        "n_scored_rows": len(scored),
        "n_matched_cases": len(keys),
        "paired_delta_dr_v2_minus_external_l1_max": paired_delta,
        "dataset_breakdown_delta": {k: mean(v) for k, v in dataset_break.items()},
        "budget_breakdown_delta": {k: mean(v) for k, v in budget_break.items()},
        "seed_breakdown_delta": {k: mean(v) for k, v in seed_break.items()},
        "cost_delta_usd": cost_delta,
        "action_delta": action_delta,
        "token_delta": token_delta,
        "bottleneck_hypotheses": bottlenecks,
        "decision_recommendation": recommendation,
    }

    (out_dir / "bottleneck_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    with (out_dir / "method_accuracy_snapshot.csv").open("w", encoding="utf-8", newline="") as fcsv:
        w = csv.DictWriter(fcsv, fieldnames=["method", "n_scored", "accuracy"])
        w.writeheader()
        for m, rows in sorted(by_method.items()):
            acc = mean([i(r.get("exact_match", r.get("is_correct", 0))) for r in rows]) if rows else 0.0
            w.writerow({"method": m, "n_scored": len(rows), "accuracy": round(acc, 6)})

    md = [
        "# DR-v2 bottleneck audit summary",
        "",
        f"- matched_cases: {len(keys)}",
        f"- paired_delta_dr_v2_minus_external_l1_max: {paired_delta}",
        f"- cost_delta_usd: {cost_delta}",
        f"- action_delta: {action_delta}",
        f"- recommendation: {', '.join(recommendation)}",
        "",
        "This output is diagnostic-only and not manuscript headline evidence.",
    ]
    (out_dir / "bottleneck_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()
