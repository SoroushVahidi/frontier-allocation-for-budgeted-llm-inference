#!/usr/bin/env python3
"""Build reproducible target-fidelity pair-construction regimes from brute-force labels."""

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
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _pair_key(state_id: str, bi: str, bj: str) -> tuple[str, str, str]:
    a, b = sorted([str(bi), str(bj)])
    return (str(state_id), a, b)


def _canonical_label_for_pair(bi: str, bj: str, winner: str) -> int:
    return 1 if winner == bi else 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build target-fidelity pair regimes")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_targets")
    p.add_argument("--run-id", required=True)
    p.add_argument(
        "--pair-strategies",
        default="all_pairs,top_vs_rest,adjacent_rank,high_margin_only,uncertainty_filtered,quality_mixed_trust",
        help="comma-separated strategies",
    )
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--high-margin-threshold", type=float, default=0.08)
    p.add_argument("--max-pair-std", type=float, default=0.08)
    p.add_argument("--exact-labels-dir", default="")
    p.add_argument("--promote-exact-over-approx", action="store_true")
    p.add_argument("--min-relative-margin", type=float, default=0.0)
    p.add_argument("--tie-abs-margin-threshold", type=float, default=0.03)
    p.add_argument("--tie-relative-margin-threshold", type=float, default=0.15)
    p.add_argument("--tie-std-threshold", type=float, default=0.08)
    p.add_argument("--tie-use-near-tie-flag", action="store_true")
    p.add_argument("--tie-include-approx", action="store_true")
    p.add_argument("--tie-require-exact-or-mixed", action="store_true")
    p.add_argument("--low-trust-near-tie-approx-weight", type=float, default=0.35)
    p.add_argument("--medium-trust-approx-weight", type=float, default=0.7)
    p.add_argument("--exact-trust-weight", type=float, default=1.15)
    p.add_argument("--low-trust-std-threshold", type=float, default=0.08)
    return p.parse_args()


def _augment_pair_row(
    row: dict[str, Any],
    *,
    cand_i: dict[str, Any],
    cand_j: dict[str, Any],
    near_tie_margin: float,
    pair_type: str,
) -> dict[str, Any]:
    out = dict(row)
    margin = float(out.get("margin", 0.0))
    denom = max(abs(float(cand_i.get("estimated_value_if_allocate_next", 0.0))), abs(float(cand_j.get("estimated_value_if_allocate_next", 0.0))), 1e-6)
    std_i = float(cand_i.get("allocation_value_std", 0.0))
    std_j = float(cand_j.get("allocation_value_std", 0.0))
    out["margin_abs"] = abs(margin)
    out["relative_margin"] = abs(margin) / denom
    out["near_tie_flag"] = bool(abs(margin) <= float(near_tie_margin))
    out["pair_uncertainty_std_mean"] = 0.5 * (std_i + std_j)
    out["pair_uncertainty_std_max"] = max(std_i, std_j)
    mode_i = str(cand_i.get("mode", "unknown"))
    mode_j = str(cand_j.get("mode", "unknown"))
    out["pair_mode_provenance"] = mode_i if mode_i == mode_j else "mixed"
    out["outside_gap_i"] = float(cand_i.get("branch_vs_outside_gap", 0.0))
    out["outside_gap_j"] = float(cand_j.get("branch_vs_outside_gap", 0.0))
    out["outside_gap_abs_diff"] = abs(out["outside_gap_i"] - out["outside_gap_j"])
    out["pair_type"] = pair_type
    out["pair_quality_version"] = "branch_pair_quality_v1"
    return out


def _annotate_ambiguous_pair(
    row: dict[str, Any],
    *,
    tie_abs_margin_threshold: float,
    tie_relative_margin_threshold: float,
    tie_std_threshold: float,
    tie_use_near_tie_flag: bool,
    tie_include_approx: bool,
    tie_require_exact_or_mixed: bool,
) -> dict[str, Any]:
    out = dict(row)
    pair_mode = str(out.get("pair_mode_provenance", "unknown"))
    eligible_mode = True
    if (not tie_include_approx) and pair_mode == "approx":
        eligible_mode = False
    if tie_require_exact_or_mixed and pair_mode not in {"exact", "mixed"}:
        eligible_mode = False
    triggers: list[str] = []
    if float(out.get("margin_abs", 0.0)) <= float(tie_abs_margin_threshold):
        triggers.append("abs_margin")
    if float(out.get("relative_margin", 1e9)) <= float(tie_relative_margin_threshold):
        triggers.append("relative_margin")
    if float(out.get("pair_uncertainty_std_mean", 0.0)) >= float(tie_std_threshold):
        triggers.append("uncertainty_std")
    if tie_use_near_tie_flag and bool(out.get("near_tie_flag", False)):
        triggers.append("near_tie_flag")
    out["ambiguous_tie_target"] = bool(eligible_mode and len(triggers) > 0)
    out["ambiguous_tie_reasons"] = triggers
    out["ternary_label_name"] = (
        "tie_ambiguous"
        if out["ambiguous_tie_target"]
        else ("prefer_branch_i" if int(out.get("label", out.get("preference", 0))) == 1 else "prefer_branch_j")
    )
    return out


def _assign_supervision_reliability(
    row: dict[str, Any],
    *,
    low_trust_near_tie_approx_weight: float,
    medium_trust_approx_weight: float,
    exact_trust_weight: float,
    low_trust_std_threshold: float,
) -> dict[str, Any]:
    out = dict(row)
    pair_mode = str(out.get("pair_mode_provenance", "unknown"))
    pair_type = str(out.get("pair_type", "generic"))
    near_tie = bool(out.get("near_tie_flag", False))
    pair_std = float(out.get("pair_uncertainty_std_mean", 0.0))
    label_source = str(out.get("label_source", ""))
    is_exact = pair_mode in {"exact", "mixed"} or label_source.startswith("exact")

    trust_tier = "medium"
    weight = float(medium_trust_approx_weight)
    keep_in_quality_mixed_trust = True

    if is_exact:
        trust_tier = "high_exact"
        weight = float(exact_trust_weight)
    elif (pair_type == "adjacent_rank") and near_tie and pair_std >= float(low_trust_std_threshold):
        trust_tier = "low_approx_near_tie_adjacent_high_std"
        weight = float(low_trust_near_tie_approx_weight)
        keep_in_quality_mixed_trust = False
    elif near_tie:
        trust_tier = "medium_approx_near_tie"
        weight = float(low_trust_near_tie_approx_weight)
    elif pair_std <= float(low_trust_std_threshold):
        trust_tier = "high_approx_easy"
        weight = 1.0

    out["supervision_trust_tier"] = trust_tier
    out["supervision_reliability_weight"] = max(weight, 1e-8)
    out["keep_in_quality_mixed_trust"] = bool(keep_in_quality_mixed_trust)
    return out


def main() -> None:
    args = parse_args()
    labels_dir = Path(args.labels_dir)
    out_root = Path(args.output_dir) / args.run_id
    out_root.mkdir(parents=True, exist_ok=True)

    candidates = _read_jsonl(labels_dir / "candidate_labels.jsonl")
    pairwise = _read_jsonl(labels_dir / "pairwise_labels.jsonl")
    states = _read_jsonl(labels_dir / "state_summaries.jsonl")

    cand_map: dict[tuple[str, str], dict[str, Any]] = {}
    state_to_cands: dict[str, list[dict[str, Any]]] = {}
    for c in candidates:
        sid = str(c["state_id"])
        bid = str(c["branch_id"])
        cand_map[(sid, bid)] = c
        state_to_cands.setdefault(sid, []).append(c)

    base_pair_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for p in pairwise:
        k = _pair_key(str(p["state_id"]), str(p["branch_i"]), str(p["branch_j"]))
        base_pair_map[k] = p

    exact_pair_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    if args.exact_labels_dir:
        exact_dir = Path(args.exact_labels_dir)
        if (exact_dir / "pairwise_labels.jsonl").exists():
            for p in _read_jsonl(exact_dir / "pairwise_labels.jsonl"):
                exact_pair_map[_pair_key(str(p["state_id"]), str(p["branch_i"]), str(p["branch_j"]))] = p

    strategies = [s.strip() for s in args.pair_strategies.split(",") if s.strip()]
    run_manifest: dict[str, Any] = {
        "run_id": args.run_id,
        "labels_dir": str(labels_dir),
        "strategies": strategies,
        "config": {
            "near_tie_margin": args.near_tie_margin,
            "high_margin_threshold": args.high_margin_threshold,
            "max_pair_std": args.max_pair_std,
            "promote_exact_over_approx": bool(args.promote_exact_over_approx),
            "min_relative_margin": args.min_relative_margin,
            "exact_labels_dir": args.exact_labels_dir,
            "tie_abs_margin_threshold": args.tie_abs_margin_threshold,
            "tie_relative_margin_threshold": args.tie_relative_margin_threshold,
            "tie_std_threshold": args.tie_std_threshold,
            "tie_use_near_tie_flag": bool(args.tie_use_near_tie_flag),
            "tie_include_approx": bool(args.tie_include_approx),
            "tie_require_exact_or_mixed": bool(args.tie_require_exact_or_mixed),
            "low_trust_near_tie_approx_weight": args.low_trust_near_tie_approx_weight,
            "medium_trust_approx_weight": args.medium_trust_approx_weight,
            "exact_trust_weight": args.exact_trust_weight,
            "low_trust_std_threshold": args.low_trust_std_threshold,
        },
        "regimes": {},
    }

    for strat in strategies:
        kept: list[dict[str, Any]] = []
        for sid, cand_rows in state_to_cands.items():
            ranked = sorted(cand_rows, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0)), reverse=True)
            top_branch = str(ranked[0]["branch_id"]) if ranked else ""
            neighbor_pairs = set()
            for i in range(max(0, len(ranked) - 1)):
                neighbor_pairs.add(_pair_key(sid, str(ranked[i]["branch_id"]), str(ranked[i + 1]["branch_id"])))

            for i in range(len(ranked)):
                for j in range(i + 1, len(ranked)):
                    bi = str(ranked[i]["branch_id"])
                    bj = str(ranked[j]["branch_id"])
                    k = _pair_key(sid, bi, bj)
                    base = dict(base_pair_map.get(k, {
                        "state_id": sid,
                        "example_id": ranked[i].get("example_id", ""),
                        "dataset_name": ranked[i].get("dataset_name", "unknown"),
                        "remaining_budget": ranked[i].get("remaining_budget", 0),
                        "branch_i": bi,
                        "branch_j": bj,
                    }))

                    vi = float(cand_map[(sid, bi)].get("estimated_value_if_allocate_next", 0.0))
                    vj = float(cand_map[(sid, bj)].get("estimated_value_if_allocate_next", 0.0))
                    winner = bi if vi >= vj else bj
                    if "preference" not in base and "label" not in base:
                        base["preference"] = _canonical_label_for_pair(str(base.get("branch_i", bi)), str(base.get("branch_j", bj)), winner)
                    else:
                        base["preference"] = int(base.get("preference", base.get("label", 0)))
                    base["label"] = int(base["preference"])
                    if "margin" not in base:
                        base["margin"] = vi - vj if str(base.get("branch_i", bi)) == bi else vj - vi

                    if args.promote_exact_over_approx and k in exact_pair_map:
                        ex = exact_pair_map[k]
                        ex_bi = str(ex.get("branch_i", bi))
                        ex_bj = str(ex.get("branch_j", bj))
                        base["branch_i"] = ex_bi
                        base["branch_j"] = ex_bj
                        base["preference"] = int(ex.get("preference", ex.get("label", 0)))
                        base["label"] = int(base["preference"])
                        base["margin"] = float(ex.get("margin", base["margin"]))
                        base["label_source"] = "exact_promoted"
                        base["replaced_approx_label"] = True
                        base["pair_mode_provenance"] = "exact"
                    else:
                        src_mode = str(cand_map[(sid, bi)].get("mode", "unknown"))
                        base["label_source"] = "exact_original" if src_mode == "exact" else "approx_original"
                        base["replaced_approx_label"] = False

                    pair_type = "generic"
                    if bi == top_branch or bj == top_branch:
                        pair_type = "top_vs_rest"
                    if k in neighbor_pairs:
                        pair_type = "adjacent_rank"

                    prow = _augment_pair_row(
                        base,
                        cand_i=cand_map[(sid, str(base["branch_i"]))],
                        cand_j=cand_map[(sid, str(base["branch_j"]))],
                        near_tie_margin=float(args.near_tie_margin),
                        pair_type=pair_type,
                    )

                    if float(prow.get("relative_margin", 0.0)) < float(args.min_relative_margin):
                        continue

                    keep = False
                    if strat == "all_pairs":
                        keep = True
                    elif strat == "top_vs_rest":
                        keep = prow["pair_type"] == "top_vs_rest"
                    elif strat == "adjacent_rank":
                        keep = prow["pair_type"] == "adjacent_rank"
                    elif strat == "high_margin_only":
                        keep = float(prow["margin_abs"]) >= float(args.high_margin_threshold)
                    elif strat == "uncertainty_filtered":
                        keep = (
                            float(prow["pair_uncertainty_std_mean"]) <= float(args.max_pair_std)
                            and not bool(prow["near_tie_flag"])
                        )
                    elif strat == "quality_mixed_trust":
                        keep = True
                    else:
                        raise ValueError(f"Unknown strategy: {strat}")

                    if keep:
                        annotated = _annotate_ambiguous_pair(
                            prow,
                            tie_abs_margin_threshold=float(args.tie_abs_margin_threshold),
                            tie_relative_margin_threshold=float(args.tie_relative_margin_threshold),
                            tie_std_threshold=float(args.tie_std_threshold),
                            tie_use_near_tie_flag=bool(args.tie_use_near_tie_flag),
                            tie_include_approx=bool(args.tie_include_approx),
                            tie_require_exact_or_mixed=bool(args.tie_require_exact_or_mixed),
                        )
                        annotated = _assign_supervision_reliability(
                            annotated,
                            low_trust_near_tie_approx_weight=float(args.low_trust_near_tie_approx_weight),
                            medium_trust_approx_weight=float(args.medium_trust_approx_weight),
                            exact_trust_weight=float(args.exact_trust_weight),
                            low_trust_std_threshold=float(args.low_trust_std_threshold),
                        )
                        if strat == "quality_mixed_trust" and (not bool(annotated.get("keep_in_quality_mixed_trust", True))):
                            continue
                        kept.append(annotated)

        out_dir = out_root / f"regime_{strat}"
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(out_dir / "candidate_labels.jsonl", candidates)
        _write_jsonl(out_dir / "pairwise_labels.jsonl", kept)
        _write_jsonl(out_dir / "state_summaries.jsonl", states)

        summary = {
            "strategy": strat,
            "pairs": len(kept),
            "near_tie_rate": (sum(1 for r in kept if bool(r.get("near_tie_flag", False))) / max(1, len(kept))),
            "exact_or_promoted_rate": (
                sum(1 for r in kept if str(r.get("label_source", "")).startswith("exact")) / max(1, len(kept))
            ),
            "pair_type_counts": {
                "top_vs_rest": sum(1 for r in kept if r.get("pair_type") == "top_vs_rest"),
                "adjacent_rank": sum(1 for r in kept if r.get("pair_type") == "adjacent_rank"),
                "generic": sum(1 for r in kept if r.get("pair_type") == "generic"),
            },
        }
        (out_dir / "target_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        run_manifest["regimes"][strat] = {
            "output_dir": str(out_dir),
            "summary": summary,
        }

    (out_root / "manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    md = ["# Branch-comparison target regimes", "", f"- run_id: `{args.run_id}`", "", "## Regimes", ""]
    for name, info in run_manifest["regimes"].items():
        s = info["summary"]
        md.append(f"- {name}: pairs={s['pairs']}, near_tie_rate={s['near_tie_rate']:.3f}, exact_or_promoted_rate={s['exact_or_promoted_rate']:.3f}")
    (out_root / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_root), "regimes": list(run_manifest["regimes"].keys())}, indent=2))


if __name__ == "__main__":
    main()
