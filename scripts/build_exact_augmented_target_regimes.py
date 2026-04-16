#!/usr/bin/env python3
"""Build exact-augmented regimes by promoting targeted exact hard-region pairs."""

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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _pair_key(state_id: str, bi: str, bj: str) -> tuple[str, str, str]:
    a, b = sorted([str(bi), str(bj)])
    return (str(state_id), a, b)


def _pair_type_for_state_pairs(cands: list[dict[str, Any]]) -> dict[tuple[str, str, str], str]:
    out: dict[tuple[str, str, str], str] = {}
    by_state: dict[str, list[dict[str, Any]]] = {}
    for c in cands:
        by_state.setdefault(str(c["state_id"]), []).append(c)
    for sid, rows in by_state.items():
        ranked = sorted(rows, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0)), reverse=True)
        if not ranked:
            continue
        top_bid = str(ranked[0]["branch_id"])
        for i in range(len(ranked)):
            for j in range(i + 1, len(ranked)):
                bi = str(ranked[i]["branch_id"])
                bj = str(ranked[j]["branch_id"])
                k = _pair_key(sid, bi, bj)
                ptype = "generic"
                if bi == top_bid or bj == top_bid:
                    ptype = "top_vs_rest"
                if j == i + 1:
                    ptype = "adjacent_rank"
                out[k] = ptype
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build exact-augmented target regimes")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--exact-expansion-dir", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_targets")
    p.add_argument("--run-id", required=True)
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--high-margin-threshold", type=float, default=0.08)
    p.add_argument("--max-pair-std", type=float, default=0.08)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    labels_dir = Path(args.labels_dir)
    exact_dir = Path(args.exact_expansion_dir)
    out_root = Path(args.output_dir) / args.run_id
    out_root.mkdir(parents=True, exist_ok=True)

    candidates = _read_jsonl(labels_dir / "candidate_labels.jsonl")
    pairs = _read_jsonl(labels_dir / "pairwise_labels.jsonl")
    states = _read_jsonl(labels_dir / "state_summaries.jsonl")

    cand_map = {(str(c["state_id"]), str(c["branch_id"])): c for c in candidates}
    exact_pairs = _read_jsonl(exact_dir / "exact_pairwise_labels.jsonl") if (exact_dir / "exact_pairwise_labels.jsonl").exists() else []
    exact_map = {
        _pair_key(str(r["state_id"]), str(r["branch_i"]), str(r["branch_j"])): r
        for r in exact_pairs
    }

    pair_type_map = _pair_type_for_state_pairs(candidates)

    promoted: list[dict[str, Any]] = []
    for row in pairs:
        sid = str(row["state_id"])
        bi = str(row["branch_i"])
        bj = str(row["branch_j"])
        k = _pair_key(sid, bi, bj)
        out = dict(row)

        if k in exact_map:
            ex = exact_map[k]
            out["branch_i"] = str(ex.get("branch_i", bi))
            out["branch_j"] = str(ex.get("branch_j", bj))
            out["preference"] = int(ex.get("preference", ex.get("label", row.get("preference", row.get("label", 0)))))
            out["label"] = int(out["preference"])
            out["margin"] = float(ex.get("margin", row.get("margin", 0.0)))
            out["label_source"] = "exact_promoted_hard_region"
            out["mined_reasons"] = ex.get("mined_reasons", [])
            out["replaced_approx_label"] = True
        else:
            out["label_source"] = "approx_original"
            out["replaced_approx_label"] = False
            out["mined_reasons"] = []

        ci = cand_map.get((sid, str(out["branch_i"])), {})
        cj = cand_map.get((sid, str(out["branch_j"])), {})
        std_i = float(ci.get("allocation_value_std", 0.0))
        std_j = float(cj.get("allocation_value_std", 0.0))
        margin = float(out.get("margin", 0.0))
        out["margin_abs"] = abs(margin)
        out["near_tie_flag"] = bool(abs(margin) <= float(args.near_tie_margin))
        out["pair_uncertainty_std_mean"] = 0.5 * (std_i + std_j)
        out["pair_type"] = pair_type_map.get(k, "generic")
        promoted.append(out)

    baseline_rows: list[dict[str, Any]] = []
    for row in pairs:
        sid = str(row["state_id"])
        bi = str(row["branch_i"])
        bj = str(row["branch_j"])
        k = _pair_key(sid, bi, bj)
        ci = cand_map.get((sid, bi), {})
        cj = cand_map.get((sid, bj), {})
        margin = float(row.get("margin", 0.0))
        b = dict(row)
        b["label_source"] = "approx_original"
        b["replaced_approx_label"] = False
        b["mined_reasons"] = []
        b["margin_abs"] = abs(margin)
        b["near_tie_flag"] = bool(abs(margin) <= float(args.near_tie_margin))
        b["pair_uncertainty_std_mean"] = 0.5 * (
            float(ci.get("allocation_value_std", 0.0)) + float(cj.get("allocation_value_std", 0.0))
        )
        b["pair_type"] = pair_type_map.get(k, "generic")
        baseline_rows.append(b)

    regimes: dict[str, list[dict[str, Any]]] = {
        "all_pairs_approx": baseline_rows,
        "promoted_exact_hard_region": promoted,
        "promoted_exact_top_vs_rest": [r for r in promoted if str(r.get("pair_type")) == "top_vs_rest"],
        "promoted_exact_high_margin_only": [r for r in promoted if float(r.get("margin_abs", 0.0)) >= float(args.high_margin_threshold)],
        "promoted_exact_uncertainty_filtered": [
            r for r in promoted
            if float(r.get("pair_uncertainty_std_mean", 0.0)) <= float(args.max_pair_std) and not bool(r.get("near_tie_flag", False))
        ],
    }

    manifest: dict[str, Any] = {
        "run_id": args.run_id,
        "labels_dir": str(labels_dir),
        "exact_expansion_dir": str(exact_dir),
        "regimes": {},
        "config": {
            "near_tie_margin": args.near_tie_margin,
            "high_margin_threshold": args.high_margin_threshold,
            "max_pair_std": args.max_pair_std,
        },
    }

    for regime, rows in regimes.items():
        d = out_root / f"regime_{regime}"
        d.mkdir(parents=True, exist_ok=True)
        _write_jsonl(d / "candidate_labels.jsonl", candidates)
        _write_jsonl(d / "pairwise_labels.jsonl", rows)
        _write_jsonl(d / "state_summaries.jsonl", states)

        promoted_count = sum(1 for r in rows if bool(r.get("replaced_approx_label", False)))
        summary = {
            "pairs": len(rows),
            "promoted_exact_pairs": promoted_count,
            "promoted_exact_rate": promoted_count / max(1, len(rows)),
            "near_tie_rate": sum(1 for r in rows if bool(r.get("near_tie_flag", False))) / max(1, len(rows)),
            "adjacent_rank_rate": sum(1 for r in rows if str(r.get("pair_type", "")) == "adjacent_rank") / max(1, len(rows)),
        }
        (d / "target_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        manifest["regimes"][regime] = {"output_dir": str(d), "summary": summary}

    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"output_dir": str(out_root), "regimes": list(regimes.keys())}, indent=2))


if __name__ == "__main__":
    main()
