#!/usr/bin/env python3
"""Mine hard branch-comparison regions for targeted exact relabeling."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _pair_key(state_id: str, bi: str, bj: str) -> tuple[str, str, str]:
    a, b = sorted([str(bi), str(bj)])
    return (str(state_id), a, b)


def _stable01(text: str) -> float:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:12], 16) / float(16**12)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mine hard regions for exact relabeling")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_targets")
    p.add_argument("--run-id", required=True)
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--small-margin-threshold", type=float, default=0.08)
    p.add_argument("--high-std-threshold", type=float, default=0.08)
    p.add_argument("--low-confidence-threshold", type=float, default=0.58)
    p.add_argument("--max-candidates", type=int, default=220)
    p.add_argument("--exact-reference-dir", default="")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    labels_dir = Path(args.labels_dir)
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = _read_jsonl(labels_dir / "candidate_labels.jsonl")
    pairs = _read_jsonl(labels_dir / "pairwise_labels.jsonl")
    states = _read_jsonl(labels_dir / "state_summaries.jsonl")

    cand_map = {(str(c["state_id"]), str(c["branch_id"])): c for c in candidates}
    state_meta = {
        str(s["state_id"]): {
            "dataset_name": str(s.get("dataset_name", "unknown")),
            "remaining_budget": int(s.get("remaining_budget", 0)),
            "branch_count": int(s.get("branch_count", s.get("num_branches", 0))),
            "original_mode": str(s.get("candidate_mode", "unknown")),
        }
        for s in states
    }

    exact_pref_map: dict[tuple[str, str, str], int] = {}
    if args.exact_reference_dir:
        ep = Path(args.exact_reference_dir) / "pairwise_labels.jsonl"
        if ep.exists():
            for row in _read_jsonl(ep):
                key = _pair_key(str(row["state_id"]), str(row["branch_i"]), str(row["branch_j"]))
                exact_pref_map[key] = int(row.get("preference", row.get("label", 0)))

    mined_rows: list[dict[str, Any]] = []
    for row in pairs:
        sid = str(row["state_id"])
        bi = str(row["branch_i"])
        bj = str(row["branch_j"])
        ci = cand_map.get((sid, bi), {})
        cj = cand_map.get((sid, bj), {})
        vi = float(ci.get("estimated_value_if_allocate_next", 0.0))
        vj = float(cj.get("estimated_value_if_allocate_next", 0.0))
        margin = float(row.get("margin", vi - vj))
        margin_abs = abs(margin)
        std_i = float(ci.get("allocation_value_std", 0.0))
        std_j = float(cj.get("allocation_value_std", 0.0))
        pair_std = 0.5 * (std_i + std_j)

        ranked = sorted(
            [(str(c.get("branch_id", "")), float(c.get("estimated_value_if_allocate_next", 0.0))) for c in candidates if str(c.get("state_id")) == sid],
            key=lambda x: x[1],
            reverse=True,
        )
        branch_rank = {bid: i for i, (bid, _) in enumerate(ranked)}
        adjacent = abs(branch_rank.get(bi, 999) - branch_rank.get(bj, 999)) == 1

        conf = 1.0 - _stable01(f"{sid}|{bi}|{bj}|learner_proxy")
        disagreement_proxy = (pair_std / max(1e-6, margin_abs + 1e-6))

        reasons: list[str] = []
        score = 0.0
        if margin_abs <= float(args.near_tie_margin):
            reasons.append("near_tie")
            score += 4.0
        if margin_abs <= float(args.small_margin_threshold):
            reasons.append("small_abs_margin")
            score += 1.5
        if pair_std >= float(args.high_std_threshold):
            reasons.append("high_pair_uncertainty_std")
            score += 2.0
        if adjacent:
            reasons.append("adjacent_rank_pair")
            score += 1.8
        if disagreement_proxy >= 0.7:
            reasons.append("approx_exact_disagreement_risk_proxy")
            score += min(2.5, disagreement_proxy)
        if conf <= float(args.low_confidence_threshold):
            reasons.append("low_learner_confidence_proxy")
            score += 1.0

        base_pref = int(row.get("preference", row.get("label", 0)))
        ref_pref = exact_pref_map.get(_pair_key(sid, bi, bj))
        if ref_pref is not None and ref_pref != base_pref:
            reasons.append("known_exact_disagreement")
            score += 3.0

        if not reasons:
            continue

        meta = state_meta.get(sid, {})
        mined_rows.append(
            {
                "state_id": sid,
                "example_id": str(row.get("example_id", "")),
                "dataset_name": str(row.get("dataset_name", meta.get("dataset_name", "unknown"))),
                "remaining_budget": int(row.get("remaining_budget", meta.get("remaining_budget", 0))),
                "branch_i": bi,
                "branch_j": bj,
                "pair_type": "adjacent_rank" if adjacent else "generic",
                "margin": margin,
                "margin_abs": margin_abs,
                "pair_uncertainty_std_mean": pair_std,
                "disagreement_risk_proxy": disagreement_proxy,
                "learner_confidence_proxy": conf,
                "priority_score": score,
                "mined_reasons": reasons,
                "source_labels_dir": str(labels_dir),
                "source_pair_label": base_pref,
                "original_regime": "all_pairs_approx",
                "original_mode": str(meta.get("original_mode", "unknown")),
                "exact_reference_agreement": None if ref_pref is None else int(ref_pref == base_pref),
            }
        )

    mined_rows = sorted(mined_rows, key=lambda r: float(r["priority_score"]), reverse=True)
    mined_rows = mined_rows[: max(1, int(args.max_candidates))]

    _write_jsonl(out_dir / "mined_hard_candidates.jsonl", mined_rows)

    reason_counts: dict[str, int] = {}
    dataset_counts: dict[str, int] = {}
    budget_counts: dict[str, int] = {}
    pair_type_counts: dict[str, int] = {}
    for row in mined_rows:
        dataset_counts[row["dataset_name"]] = dataset_counts.get(row["dataset_name"], 0) + 1
        budget_key = str(row["remaining_budget"])
        budget_counts[budget_key] = budget_counts.get(budget_key, 0) + 1
        pair_type_counts[row["pair_type"]] = pair_type_counts.get(row["pair_type"], 0) + 1
        for rs in row["mined_reasons"]:
            reason_counts[rs] = reason_counts.get(rs, 0) + 1

    summary = {
        "run_id": args.run_id,
        "labels_dir": str(labels_dir),
        "mined_pairs": len(mined_rows),
        "priority_score_mean": mean([float(r["priority_score"]) for r in mined_rows]) if mined_rows else 0.0,
        "reason_counts": reason_counts,
        "dataset_counts": dataset_counts,
        "budget_counts": budget_counts,
        "pair_type_counts": pair_type_counts,
        "config": {
            "near_tie_margin": args.near_tie_margin,
            "small_margin_threshold": args.small_margin_threshold,
            "high_std_threshold": args.high_std_threshold,
            "low_confidence_threshold": args.low_confidence_threshold,
            "max_candidates": args.max_candidates,
            "exact_reference_dir": args.exact_reference_dir,
        },
    }
    (out_dir / "hard_region_mining_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# Hard-region mining summary",
        "",
        f"- labels_dir: `{labels_dir}`",
        f"- mined_pairs: `{summary['mined_pairs']}`",
        f"- mean_priority_score: `{summary['priority_score_mean']:.4f}`",
        "",
        "## Reason counts",
    ]
    for k, v in sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True):
        md.append(f"- {k}: {v}")
    md.extend(["", "## Dataset counts"])
    for k, v in sorted(dataset_counts.items()):
        md.append(f"- {k}: {v}")
    (out_dir / "hard_region_mining_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "mined_pairs": len(mined_rows)}, indent=2))


if __name__ == "__main__":
    main()
