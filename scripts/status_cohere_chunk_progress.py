#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

STATUS_FIELDS = [
    "chunk_id",
    "dataset",
    "budget",
    "seed",
    "method",
    "status",
    "scored_count",
    "target_scored_count",
    "accuracy",
    "tokens",
    "estimated_cost",
    "failures",
    "skips",
    "pairwise_vs_external_l1_max_available",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def i(v: str | None) -> int:
    return int(float(v or 0))


def pick_int(row: dict[str, str], *keys: str) -> int:
    for k in keys:
        if k in row and row.get(k, "") != "":
            return i(row.get(k))
    return 0




def synthesize_slices_from_compact_ledger(out_dir: Path) -> list[dict[str, str]]:
    ledger = load_csv(out_dir / "compact_per_example_ledger.csv")
    if not ledger:
        return []
    agg: dict[tuple[str,str,str,str,str], dict[str,float]] = {}
    for r in ledger:
        k=(str(r.get("provider","cohere")),str(r.get("dataset","")),str(r.get("seed","")),str(r.get("budget","")),str(r.get("method","")))
        a=agg.setdefault(k,{"scored":0,"failed":0,"skipped":0,"exact":0.0,"tok":0.0,"cost":0.0,"lat":0.0})
        a["scored"] += int(float(r.get("scored",0) or 0))
        a["failed"] += int(float(r.get("failed",0) or 0))
        a["skipped"] += int(float(r.get("skipped",0) or 0))
        if int(float(r.get("scored",0) or 0))==1:
            a["exact"] += float(r.get("exact_match",0) or 0)
        a["tok"] += float(r.get("total_tokens",0) or 0)
        a["cost"] += float(r.get("estimated_cost_usd",0) or 0)
        a["lat"] += float(r.get("latency_seconds",0) or 0)
    out=[]
    for (prov,d,se,b,m),a in agg.items():
        scored=int(a["scored"])
        out.append({"provider":prov,"dataset":d,"seed":se,"budget":b,"method":m,"successfully_scored_examples":scored,"failed_examples":int(a["failed"]),"skipped_examples":int(a["skipped"]),"accuracy":(a["exact"]/scored if scored else "NA"),"total_tokens":a["tok"],"estimated_dollar_cost":a["cost"],"mean_latency_seconds_per_scored_example":(a["lat"]/scored if scored else 0.0)})
    return out

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--chunk-plan", required=True)
    p.add_argument("--timestamp", required=True)
    p.add_argument("--output-root", default="outputs")
    a = p.parse_args()

    plan = load_csv(Path(a.chunk_plan))
    out = Path(a.output_root) / f"cohere_real_model_cost_normalized_validation_{a.timestamp}"
    out.mkdir(parents=True, exist_ok=True)

    slices = load_csv(out / "slice_summary.csv")
    if not slices:
        slices = synthesize_slices_from_compact_ledger(out)
    pair = load_csv(out / "pairwise_comparisons.csv")

    smap = {(r.get("provider"), r.get("dataset"), r.get("seed"), r.get("budget"), r.get("method")): r for r in slices}
    pairset = {
        (r.get("provider"), r.get("dataset"), r.get("seed"), r.get("budget"), r.get("method_a"))
        for r in pair
        if r.get("method_b") == "external_l1_max"
    }

    rows = []
    for r in plan:
        key = ("cohere", r["dataset"], r["seed"], r["budget"], r["method"])
        s = smap.get(key)
        target = i(r.get("target_scored_per_slice"))
        if s is None:
            status = "planned_not_started"
            scored = 0
            failures = 0
            skips = 0
            accuracy = ""
            tokens = ""
            estimated_cost = ""
        else:
            scored = pick_int(s, "scored_examples", "successfully_scored_examples")
            failures = pick_int(s, "failed_examples")
            skips = pick_int(s, "skipped_examples")
            accuracy = s.get("accuracy", "")
            tokens = s.get("total_tokens", "")
            estimated_cost = s.get("estimated_cost_usd", s.get("estimated_dollar_cost", ""))
            status = "completed" if scored == target else ("failed" if scored == 0 and failures > 0 else "incomplete")

        rows.append(
            {
                "chunk_id": r["chunk_id"],
                "dataset": r["dataset"],
                "budget": r["budget"],
                "seed": r["seed"],
                "method": r["method"],
                "status": status,
                "scored_count": scored,
                "target_scored_count": target,
                "accuracy": accuracy,
                "tokens": tokens,
                "estimated_cost": estimated_cost,
                "failures": failures,
                "skips": skips,
                "pairwise_vs_external_l1_max_available": "yes" if key in pairset else "no",
            }
        )

    with (out / "chunk_progress_status.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=STATUS_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out / 'chunk_progress_status.csv'}")


if __name__ == "__main__":
    main()
