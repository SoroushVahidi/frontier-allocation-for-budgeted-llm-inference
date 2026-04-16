#!/usr/bin/env python3
"""Audit exact-vs-approx pair disagreements with slice summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _pair_key(state_id: str, bi: str, bj: str) -> tuple[str, str, str]:
    a, b = sorted([str(bi), str(bj)])
    return (str(state_id), a, b)


def _norm_pref(row: dict[str, Any]) -> int:
    return int(row.get("preference", row.get("label", 0)))


def _bucket_margin(m: float) -> str:
    am = abs(m)
    if am <= 0.03:
        return "near_tie_0_03"
    if am <= 0.08:
        return "low_0_03_0_08"
    if am <= 0.15:
        return "mid_0_08_0_15"
    return "high_gt_0_15"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit exact-vs-approx pair disagreement")
    p.add_argument("--approx-labels-dir", required=True)
    p.add_argument("--exact-labels-dir", required=True)
    p.add_argument("--output-dir", required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    approx_pairs = _read_jsonl(Path(args.approx_labels_dir) / "pairwise_labels.jsonl")
    exact_pairs = _read_jsonl(Path(args.exact_labels_dir) / "pairwise_labels.jsonl")
    approx_states = _read_jsonl(Path(args.approx_labels_dir) / "state_summaries.jsonl")

    branch_count = {
        str(s.get("state_id")): int(s.get("branch_count", s.get("num_branches", s.get("frontier_size", 0))))
        for s in approx_states
    }

    exact_map = {_pair_key(str(r["state_id"]), str(r["branch_i"]), str(r["branch_j"])): r for r in exact_pairs}
    rows: list[dict[str, Any]] = []
    for a in approx_pairs:
        k = _pair_key(str(a["state_id"]), str(a["branch_i"]), str(a["branch_j"]))
        if k not in exact_map:
            continue
        e = exact_map[k]
        ap = _norm_pref(a)
        ep = _norm_pref(e)
        m = float(a.get("margin", 0.0))
        rows.append(
            {
                "state_id": str(a["state_id"]),
                "dataset": str(a.get("dataset_name", "unknown")),
                "budget": int(a.get("remaining_budget", 0)),
                "pair_type": str(a.get("pair_type", "generic")),
                "margin_bucket": _bucket_margin(m),
                "branch_count": int(branch_count.get(str(a["state_id"]), 0)),
                "approx_pref": ap,
                "exact_pref": ep,
                "agree": int(ap == ep),
            }
        )

    def agg(key: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for r in rows:
            k = str(r[key])
            blk = out.setdefault(k, {"n": 0, "agree": 0})
            blk["n"] += 1
            blk["agree"] += int(r["agree"])
        for v in out.values():
            v["agreement"] = v["agree"] / max(1, v["n"])
        return out

    summary = {
        "pairs_compared": len(rows),
        "overall_agreement": sum(r["agree"] for r in rows) / max(1, len(rows)),
        "by_dataset": agg("dataset"),
        "by_budget": agg("budget"),
        "by_margin_bucket": agg("margin_bucket"),
        "by_pair_type": agg("pair_type"),
        "by_branch_count": agg("branch_count"),
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "exact_vs_approx_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Exact-vs-approx pair disagreement audit",
        "",
        f"- approx: `{args.approx_labels_dir}`",
        f"- exact: `{args.exact_labels_dir}`",
        f"- pairs_compared: `{summary['pairs_compared']}`",
        f"- overall_agreement: `{summary['overall_agreement']:.4f}`",
        "",
    ]
    for title, key in [
        ("Dataset", "by_dataset"),
        ("Budget", "by_budget"),
        ("Margin bucket", "by_margin_bucket"),
        ("Pair type", "by_pair_type"),
        ("Branch count", "by_branch_count"),
    ]:
        lines.append(f"## {title}")
        for name, vals in summary[key].items():
            lines.append(f"- {name}: n={vals['n']}, agreement={vals['agreement']:.4f}")
        lines.append("")

    (out_dir / "exact_vs_approx_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(out_dir), "pairs_compared": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
