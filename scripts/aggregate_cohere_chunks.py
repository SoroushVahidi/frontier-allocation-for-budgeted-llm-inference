#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

FINALITY_FIELDS = [
    "provider",
    "dataset",
    "seed",
    "budget",
    "method",
    "scored_examples",
    "target_scored_count",
    "failed_examples",
    "skipped_examples",
    "accuracy",
    "total_tokens",
    "estimated_cost_usd",
    "avg_latency_seconds",
    "is_final",
]
METHOD_FIELDS = ["method", "final_slices", "mean_accuracy", "total_tokens", "total_cost_usd", "mean_latency_seconds"]
PAIR_FIELDS = [
    "provider",
    "dataset",
    "seed",
    "budget",
    "method_a",
    "method_b",
    "accuracy_delta_a_minus_b",
    "n_paired_examples",
    "ci95_lo",
    "ci95_hi",
    "ci95_status",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_i(v: str | None) -> int:
    return int(float(v or 0))


def to_f(v: str | None) -> float:
    return float(v or 0)


def pick_int(row: dict[str, str], *keys: str) -> int:
    for k in keys:
        if k in row and row.get(k, "") != "":
            return to_i(row.get(k))
    return 0


def pick_str(row: dict[str, str], *keys: str) -> str:
    for k in keys:
        if k in row and row.get(k, "") != "":
            return row.get(k, "")
    return ""




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

    out = Path(a.output_root) / f"cohere_real_model_cost_normalized_validation_{a.timestamp}"
    out.mkdir(parents=True, exist_ok=True)
    plan = load_csv(Path(a.chunk_plan))
    slices = load_csv(out / "slice_summary.csv")
    if not slices:
        slices = synthesize_slices_from_compact_ledger(out)
    pairs = load_csv(out / "pairwise_comparisons.csv")
    target = {(r["dataset"], r["budget"], r["seed"], r["method"]): to_i(r.get("target_scored_per_slice")) for r in plan}

    final, not_final = [], []
    for s in slices:
        k = (s.get("dataset", ""), s.get("budget", ""), s.get("seed", ""), s.get("method", ""))
        t = target.get(k, 0)
        scored = pick_int(s, "scored_examples", "successfully_scored_examples")
        row = {
            "provider": s.get("provider", ""),
            "dataset": s.get("dataset", ""),
            "seed": s.get("seed", ""),
            "budget": s.get("budget", ""),
            "method": s.get("method", ""),
            "scored_examples": str(scored),
            "failed_examples": str(pick_int(s, "failed_examples")),
            "skipped_examples": str(pick_int(s, "skipped_examples")),
            "accuracy": s.get("accuracy", ""),
            "total_tokens": pick_str(s, "total_tokens"),
            "estimated_cost_usd": pick_str(s, "estimated_cost_usd", "estimated_dollar_cost"),
            "avg_latency_seconds": pick_str(s, "avg_latency_seconds", "mean_latency_seconds_per_scored_example"),
            "target_scored_count": t,
            "is_final": "yes" if t > 0 and scored == t else "no",
        }
        (final if row["is_final"] == "yes" else not_final).append(row)

    with (out / "codex_per_slice_finality.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FINALITY_FIELDS)
        w.writeheader()
        w.writerows(final + not_final)

    by_method = defaultdict(lambda: {"n": 0, "acc": [], "tok": 0.0, "cost": 0.0, "lat": []})
    for s in final:
        bm = by_method[s["method"]]
        bm["n"] += 1
        bm["acc"].append(to_f(s.get("accuracy")))
        bm["tok"] += to_f(s.get("total_tokens"))
        bm["cost"] += to_f(s.get("estimated_cost_usd"))
        bm["lat"].append(to_f(s.get("avg_latency_seconds")))

    mrows = []
    for method, v in by_method.items():
        mrows.append({"method": method, "final_slices": v["n"], "mean_accuracy": sum(v["acc"]) / len(v["acc"]), "total_tokens": v["tok"], "total_cost_usd": v["cost"], "mean_latency_seconds": sum(v["lat"]) / len(v["lat"]) if v["lat"] else 0.0})

    with (out / "codex_method_summary_final_only.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=METHOD_FIELDS)
        w.writeheader()
        w.writerows(mrows)

    pairrows = []
    for p0 in pairs:
        if p0.get("method_b") == "external_l1_max":
            n = to_i(p0.get("n_paired_examples"))
            status = "unavailable_no_matched_differences" if n <= 0 else "unavailable_not_computed_in_chunk_aggregate"
            pairrows.append(
                {
                    "provider": p0.get("provider", ""),
                    "dataset": p0.get("dataset", ""),
                    "seed": p0.get("seed", ""),
                    "budget": p0.get("budget", ""),
                    "method_a": p0.get("method_a", ""),
                    "method_b": p0.get("method_b", ""),
                    "accuracy_delta_a_minus_b": p0.get("accuracy_delta_a_minus_b", ""),
                    "n_paired_examples": n,
                    "ci95_lo": "",
                    "ci95_hi": "",
                    "ci95_status": status,
                }
            )
    with (out / "codex_pairwise_vs_external_l1_max.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=PAIR_FIELDS)
        w.writeheader()
        w.writerows(pairrows)

    with (out / "codex_failed_or_incomplete_slices.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FINALITY_FIELDS)
        w.writeheader()
        w.writerows(not_final)

    md = Path("docs") / f"CODEX_LOCAL_COHERE_AGGREGATE_{a.timestamp}.md"
    md.write_text(
        f"# Codex local aggregate ({a.timestamp})\n\nFinal slices: {len(final)} / {len(target)} planned.\n\nPartial run only unless all planned slices final.\n",
        encoding="utf-8",
    )
    print(f"wrote aggregate artifacts under {out} and {md}")


if __name__ == "__main__":
    main()
