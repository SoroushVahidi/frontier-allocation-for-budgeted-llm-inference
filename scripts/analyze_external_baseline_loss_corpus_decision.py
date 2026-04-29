#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def read_csv(path: Path):
    with path.open() as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()
    inp = Path(args.input_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    external_win = read_csv(inp / "external_win_cases.csv")
    paired = read_csv(inp / "paired_case_matrix.csv")
    by_method = read_csv(inp / "loss_case_summary_by_method.csv")
    by_family = read_csv(inp / "loss_case_summary_by_external_family.csv")
    by_failure = read_csv(inp / "loss_case_summary_by_failure_type.csv")
    gap = read_csv(inp / "baseline_family_gap_report.csv")
    manifest = json.loads((inp / "loss_case_collection_manifest.json").read_text())

    fam = Counter(r["external_family"] for r in external_win)
    method = Counter(r["internal_method"] for r in external_win)
    fail = Counter(r["failure_type"] for r in external_win)
    traced = sum(int(r.get("trace_available", "0") or 0) for r in external_win)

    top_family = fam.most_common(1)[0][0] if fam else "none"
    top_failure = fail.most_common(1)[0][0] if fail else "none"
    top_internal = method.most_common(1)[0][0] if method else "none"

    bottleneck = "length-control robustness and answer-selection calibration"
    if top_failure in {"present_not_selected", "absent_from_frontier"}:
        bottleneck = "frontier coverage/selection policy"

    decision = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(inp),
        "counts": {"paired": len(paired), "external_win": len(external_win), "traced_external_win": traced},
        "top_external_family": top_family,
        "top_failure_type": top_failure,
        "top_losing_internal_method": top_internal,
        "recommended_next_bottleneck": bottleneck,
        "coverage_gaps": [r for r in gap if r.get("meets_threshold") == "0"],
        "manifest": manifest,
    }
    (out / "decision_summary.json").write_text(json.dumps(decision, indent=2))

    md = [
        "# External Baseline Loss Corpus Decision",
        "",
        f"- Paired cases: {len(paired)}",
        f"- External-win cases: {len(external_win)}",
        f"- Traced external-win cases: {traced}",
        f"- Most frequent winning external family: **{top_family}**",
        f"- Most frequent losing internal method: **{top_internal}**",
        f"- Dominant failure mode: **{top_failure}**",
        f"- Recommended next algorithmic bottleneck: **{bottleneck}**",
        "",
        "## Coverage gaps",
    ]
    for r in gap:
        md.append(f"- {r['metric']}: {r['count']}/{r['threshold']} (meets={r['meets_threshold']})")
    (out / "decision_note.md").write_text("\n".join(md) + "\n")

    with (out / "decision_table.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["dimension", "value"])
        w.writeheader()
        w.writerows([
            {"dimension": "top_external_family", "value": top_family},
            {"dimension": "top_failure_type", "value": top_failure},
            {"dimension": "top_losing_internal_method", "value": top_internal},
            {"dimension": "recommended_next_bottleneck", "value": bottleneck},
        ])

    print(out)


if __name__ == "__main__":
    main()
