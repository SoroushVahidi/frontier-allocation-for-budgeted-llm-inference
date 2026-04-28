#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build reviewer-facing cost validation output tables.")
    p.add_argument("--output-dir", required=True, help="Output directory produced by real-model validation run.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    if not out_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {out_dir}")

    per_example = read_jsonl(out_dir / "per_example_records.jsonl")
    if not per_example:
        raise FileNotFoundError(f"Missing/empty per_example_records.jsonl in {out_dir}")

    per_case_rows = []
    for r in per_example:
        per_case_rows.append(
            {
                "provider": r.get("provider", ""),
                "model": r.get("model", ""),
                "dataset": r.get("dataset", ""),
                "seed": r.get("seed", ""),
                "budget": r.get("budget", ""),
                "method": r.get("method", ""),
                "example_id": r.get("example_id", ""),
                "status": r.get("status", ""),
                "exact_match": r.get("exact_match", ""),
                "actions_used": r.get("result_metadata", {}).get("actions_used", "") if isinstance(r.get("result_metadata"), dict) else "",
                "input_tokens": r.get("input_tokens", ""),
                "output_tokens": r.get("output_tokens", ""),
                "total_tokens": r.get("total_tokens", ""),
                "latency_seconds": r.get("latency_seconds", ""),
                "estimated_cost_usd": r.get("estimated_cost_usd", ""),
                "failure_tag": r.get("failure_tag", ""),
                "error": r.get("error", ""),
            }
        )
    write_csv(out_dir / "per_case_results.csv", per_case_rows)

    pairwise = read_csv(out_dir / "pairwise_comparisons.csv")
    paired_vs_l1 = [
        r for r in pairwise if str(r.get("method_b", "")) == "external_l1_max" or "external_l1_max" in str(r.get("comparison", ""))
    ]
    write_csv(out_dir / "paired_vs_external_l1_max.csv", paired_vs_l1, fieldnames=list(pairwise[0].keys()) if pairwise else None)

    # Token/latency/cost summary by provider+method over scored examples
    bucket: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in per_example:
        if str(r.get("status")) != "scored":
            continue
        bucket[(str(r.get("provider", "")), str(r.get("method", "")))].append(r)
    trows = []
    for (provider, method), rows in sorted(bucket.items()):
        n = len(rows) or 1
        acc = sum(int(_f(x.get("exact_match"), 0)) for x in rows) / n
        actions = [_f((x.get("result_metadata") or {}).get("actions_used", 0)) if isinstance(x.get("result_metadata"), dict) else 0.0 for x in rows]
        in_t = [_f(x.get("input_tokens", 0)) for x in rows]
        out_t = [_f(x.get("output_tokens", 0)) for x in rows]
        tot_t = [_f(x.get("total_tokens", 0)) for x in rows]
        lat = [_f(x.get("latency_seconds", 0)) for x in rows]
        cost = [_f(x.get("estimated_cost_usd", 0)) for x in rows]
        total_tok = sum(tot_t)
        total_cost = sum(cost)
        trows.append(
            {
                "provider": provider,
                "method": method,
                "n_scored": n,
                "accuracy": round(acc, 6),
                "avg_actions": round(sum(actions) / n, 4),
                "avg_input_tokens": round(sum(in_t) / n, 2),
                "avg_output_tokens": round(sum(out_t) / n, 2),
                "avg_total_tokens": round(sum(tot_t) / n, 2),
                "avg_latency_seconds": round(sum(lat) / n, 4),
                "avg_estimated_cost_usd": round(sum(cost) / n, 8),
                "accuracy_per_1k_tokens": round((acc / (total_tok / 1000.0)) if total_tok > 0 else 0.0, 8),
                "accuracy_per_estimated_dollar": round((acc / total_cost) if total_cost > 0 else 0.0, 8),
            }
        )
    write_csv(out_dir / "token_latency_cost_summary.csv", trows)

    fail_counter: Counter[tuple[str, str, str]] = Counter()
    for r in per_example:
        tag = str(r.get("failure_tag") or "")
        if not tag:
            continue
        fail_counter[(str(r.get("provider", "")), str(r.get("method", "")), tag)] += 1
    frows = [
        {"provider": p, "method": m, "failure_tag": tag, "count": c}
        for (p, m, tag), c in sorted(fail_counter.items())
    ]
    write_csv(out_dir / "failure_decomposition.csv", frows, fieldnames=["provider", "method", "failure_tag", "count"])

    # method_summary.csv already exists from upstream runner; keep as source of truth.
    if not (out_dir / "method_summary.csv").exists():
        # fallback build from token summary if needed
        fallback = [
            {
                "provider": r["provider"],
                "method": r["method"],
                "total_scored_examples": r["n_scored"],
                "mean_accuracy_across_slices": r["accuracy"],
                "mean_total_tokens_per_scored_example": r["avg_total_tokens"],
                "mean_latency_seconds_per_scored_example": r["avg_latency_seconds"],
                "estimated_total_cost_usd": round(_f(r["avg_estimated_cost_usd"]) * _f(r["n_scored"]), 8),
            }
            for r in trows
        ]
        write_csv(out_dir / "method_summary.csv", fallback)


if __name__ == "__main__":
    main()
