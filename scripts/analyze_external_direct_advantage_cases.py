#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from collections import Counter
from pathlib import Path


def _to_float(v: str) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def classify_case(row: dict[str, str]) -> str:
    trace = int(row.get("trace_available", "0") or 0)
    int_exact = int(row.get("internal_exact", "0") or 0)
    ext_exact = int(row.get("external_exact", "0") or 0)
    ilat = _to_float(row.get("internal_latency_seconds", "0"))
    elat = _to_float(row.get("external_latency_seconds", "0"))
    itok = _to_float(row.get("internal_total_tokens", "0"))
    etok = _to_float(row.get("external_total_tokens", "0"))
    hint = (row.get("metadata_hint", "") or "").lower()

    if "present" in hint and "selected" in hint:
        return "possible_present_not_selected"
    if "extract" in hint or "normalize" in hint or "normalization" in hint:
        return "possible_extraction_issue"
    if (ilat > 0 and elat > 0 and ilat > elat * 1.5) or (itok > 0 and etok > 0 and itok > etok * 1.5):
        return "possible_over_exploration_commit_issue"
    if trace == 0:
        return "missing_trace_relabel_needed"
    if ext_exact == 1 and int_exact == 0:
        return "true_direct_advantage_likely"
    return "unclassifiable"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()
    inp, out = Path(args.input_dir), Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ext = list(csv.DictReader((inp / "external_win_cases.csv").open()))
    paired = list(csv.DictReader((inp / "paired_case_matrix.csv").open()))
    by_key = {(r["example_id"], r["internal_method"], r["external_method"]): r for r in paired}

    rows = []
    for r in ext:
        if r.get("failure_type") != "external_direct_advantage":
            continue
        key = (r["example_id"], r["internal_method"], r["external_method"])
        p = by_key.get(key, {})
        merged = dict(r)
        merged.update({
            "internal_latency_seconds": p.get("internal_latency_seconds", ""),
            "external_latency_seconds": p.get("external_latency_seconds", ""),
            "internal_total_tokens": p.get("internal_total_tokens", ""),
            "external_total_tokens": p.get("external_total_tokens", ""),
            "metadata_hint": p.get("metadata_hint", ""),
        })
        merged["refined_label"] = classify_case(merged)
        rows.append(merged)

    fields = sorted({k for r in rows for k in r.keys()}) if rows else ["example_id", "refined_label"]
    with (out / "external_direct_advantage_case_audit.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)

    c = Counter(r["refined_label"] for r in rows)
    summary = [{"refined_label": k, "count": v} for k, v in c.items()]
    with (out / "external_direct_advantage_summary.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["refined_label", "count"])
        w.writeheader(); w.writerows(summary)

    decision = {
        "audited_cases": len(rows),
        "counts": dict(c),
        "recommended_next_step": max(c, key=c.get) if c else "unclassifiable",
    }
    (out / "external_direct_advantage_decision.json").write_text(json.dumps(decision, indent=2))
    print(out)


if __name__ == "__main__":
    main()
