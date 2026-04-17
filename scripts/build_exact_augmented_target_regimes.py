#!/usr/bin/env python3
"""Build exact-augmented regimes by promoting targeted exact hard-region pairs."""

from __future__ import annotations

import argparse
import json
import math
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
    p.add_argument("--tie-abs-margin-threshold", type=float, default=0.03)
    p.add_argument("--tie-relative-margin-threshold", type=float, default=0.15)
    p.add_argument("--tie-std-threshold", type=float, default=0.08)
    p.add_argument("--tie-use-near-tie-flag", action="store_true")
    p.add_argument("--tie-include-approx", action="store_true")
    p.add_argument("--tie-require-exact-or-mixed", action="store_true")
    p.add_argument(
        "--tie-policy",
        choices=["legacy_or", "davidson_close_call"],
        default="legacy_or",
        help="Tie-assignment policy. davidson_close_call requires closeness + ambiguity risk.",
    )
    return p.parse_args()


def _annotate_ambiguous_pair(
    row: dict[str, Any],
    *,
    tie_policy: str,
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
    margin_close = float(out.get("margin_abs", 0.0)) <= float(tie_abs_margin_threshold)
    relative_close = float(out.get("relative_margin", 1e9)) <= float(tie_relative_margin_threshold)
    near_close = bool(out.get("near_tie_flag", False)) if tie_use_near_tie_flag else False
    std_high = float(out.get("pair_uncertainty_std_mean", 0.0)) >= float(tie_std_threshold)
    adjacent = str(out.get("pair_type", "")) == "adjacent_rank"
    disagreement_risk = bool(out.get("exact_vs_approx_disagreement_risk", False))
    close_call = bool(margin_close or relative_close or near_close)
    ambiguous_risk = bool(std_high or adjacent or disagreement_risk)

    triggers: list[str] = []
    if margin_close:
        triggers.append("abs_margin")
    if relative_close:
        triggers.append("relative_margin")
    if near_close:
        triggers.append("near_tie_flag")
    if std_high:
        triggers.append("uncertainty_std")
    if adjacent:
        triggers.append("adjacent_rank")
    if disagreement_risk:
        triggers.append("exact_vs_approx_disagreement_risk")

    if tie_policy == "davidson_close_call":
        ambiguous = bool(eligible_mode and close_call and ambiguous_risk)
    else:
        ambiguous = bool(eligible_mode and len(triggers) > 0)

    out["ambiguous_tie_target"] = ambiguous
    out["ambiguous_tie_reasons"] = triggers
    out["tie_policy"] = str(tie_policy)
    out["davidson_close_call_flag"] = bool(close_call and ambiguous_risk)
    out["ternary_label_name"] = "tie" if ambiguous else ("i_wins" if int(out.get("label", out.get("preference", 0))) == 1 else "j_wins")
    return out


def _annotate_soft_probabilistic_target(
    row: dict[str, Any],
    *,
    tie_abs_margin_threshold: float,
    tie_relative_margin_threshold: float,
    tie_std_threshold: float,
    tie_use_near_tie_flag: bool,
) -> dict[str, Any]:
    out = dict(row)
    margin_abs = float(out.get("margin_abs", 0.0))
    rel_margin = float(out.get("relative_margin", 1e9))
    pair_std = float(out.get("pair_uncertainty_std_mean", 0.0))
    near_tie = bool(out.get("near_tie_flag", False)) if tie_use_near_tie_flag else False
    adjacent = str(out.get("pair_type", "")) == "adjacent_rank"
    disagreement_risk = bool(out.get("exact_vs_approx_disagreement_risk", False))

    abs_scale = max(float(tie_abs_margin_threshold), 1e-6)
    rel_scale = max(float(tie_relative_margin_threshold), 1e-6)
    std_scale = max(float(tie_std_threshold), 1e-6)

    abs_close = math.exp(-margin_abs / abs_scale)
    rel_close = math.exp(-rel_margin / rel_scale)
    near_close = 0.95 if near_tie else 0.0
    close_strength = max(abs_close, rel_close, near_close)

    std_strength = min(1.0, pair_std / std_scale)
    adjacent_strength = 0.85 if adjacent else 0.0
    disagreement_strength = 1.0 if disagreement_risk else 0.0
    ambiguity_strength = max(std_strength, adjacent_strength, disagreement_strength)

    tie_prob = close_strength * (0.55 + 0.45 * ambiguity_strength)
    easy_pair = (
        margin_abs > (2.0 * abs_scale)
        and rel_margin > (2.0 * rel_scale)
        and pair_std < (0.5 * std_scale)
        and (not adjacent)
    )
    if easy_pair:
        tie_prob = min(tie_prob, 0.02)
    tie_prob = min(max(tie_prob, 0.01), 0.98)

    directional_mass = 1.0 - tie_prob
    directional_softness = max(0.0, 1.0 - min(1.0, margin_abs / max(2.0 * abs_scale, 1e-6)))
    loser_spill = directional_mass * 0.25 * directional_softness
    winner_mass = directional_mass - loser_spill
    label = int(out.get("label", out.get("preference", 0)))
    if label == 1:
        p_i, p_j = winner_mass, loser_spill
    else:
        p_i, p_j = loser_spill, winner_mass

    z = max(1e-8, p_i + tie_prob + p_j)
    p_i /= z
    tie_prob /= z
    p_j /= z
    out["soft_target_prob_i_wins"] = p_i
    out["soft_target_prob_tie"] = tie_prob
    out["soft_target_prob_j_wins"] = p_j
    out["soft_target_entropy"] = -sum(p * math.log(max(p, 1e-12)) for p in [p_i, tie_prob, p_j])
    out["soft_target_source"] = "davidson_soft_prob_v1"
    return out


def _annotate_incomparable_pair(
    row: dict[str, Any],
    *,
    tie_abs_margin_threshold: float,
    tie_relative_margin_threshold: float,
    tie_std_threshold: float,
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

    margin_abs = float(out.get("margin_abs", 0.0))
    rel_margin = float(out.get("relative_margin", 1e9))
    pair_std = float(out.get("pair_uncertainty_std_mean", 0.0))
    near_tie = bool(out.get("near_tie_flag", False))
    adjacent = str(out.get("pair_type", "")) == "adjacent_rank"
    disagreement_risk = bool(out.get("exact_vs_approx_disagreement_risk", False))

    abs_close = margin_abs <= float(tie_abs_margin_threshold)
    rel_close = rel_margin <= float(tie_relative_margin_threshold)
    std_high = pair_std >= float(tie_std_threshold)
    risk_signal = bool(std_high or adjacent or disagreement_risk)

    incomparable = bool(eligible_mode and abs_close and rel_close and near_tie and risk_signal)

    reasons: list[str] = []
    if abs_close:
        reasons.append("abs_margin")
    if rel_close:
        reasons.append("relative_margin")
    if near_tie:
        reasons.append("near_tie_flag")
    if std_high:
        reasons.append("uncertainty_std")
    if adjacent:
        reasons.append("adjacent_rank")
    if disagreement_risk:
        reasons.append("exact_vs_approx_disagreement_risk")

    label = int(out.get("label", out.get("preference", 0)))
    out["partial_order_incomparable_target"] = incomparable
    out["partial_order_incomparable_reasons"] = reasons
    out["partial_order_label"] = 1 if incomparable else (2 if label == 1 else 0)
    out["partial_order_label_name"] = "incomparable" if incomparable else ("i_wins" if label == 1 else "j_wins")
    out["partial_order_policy"] = "conservative_close_call_incomparable_v1"
    return out


def _annotate_allocation_regret_target(
    row: dict[str, Any],
    *,
    cand_i: dict[str, Any],
    cand_j: dict[str, Any],
    state_best_value: float,
    use_outside_option: bool,
    near_tie_margin: float,
) -> dict[str, Any]:
    out = dict(row)
    value_i = float(cand_i.get("estimated_value_if_allocate_next", out.get("pair_value_i", 0.0)))
    value_j = float(cand_j.get("estimated_value_if_allocate_next", out.get("pair_value_j", 0.0)))
    outside = float(out.get("outside_option_value_estimate", cand_i.get("outside_option_value", cand_j.get("outside_option_value", 0.0))))
    best_available = max(float(state_best_value), float(outside)) if use_outside_option else float(state_best_value)

    regret_i = max(0.0, best_available - value_i)
    regret_j = max(0.0, best_available - value_j)
    better_regret = min(regret_i, regret_j)
    worse_regret = max(regret_i, regret_j)
    regret_gap = abs(regret_i - regret_j)
    regret_gap_rel = regret_gap / max(abs(best_available), abs(value_i), abs(value_j), 1e-6)
    prefer_i = regret_i <= regret_j

    out["label"] = 1 if prefer_i else 0
    out["preference"] = int(out["label"])
    out["margin"] = float(regret_j - regret_i)
    out["margin_abs"] = abs(float(out["margin"]))
    out["relative_margin"] = float(regret_gap_rel)
    out["near_tie_flag"] = bool(regret_gap <= float(near_tie_margin))

    out["allocation_regret_target_enabled"] = True
    out["allocation_regret_target_source"] = "best_available_regret_v1"
    out["allocation_regret_use_outside_option"] = bool(use_outside_option)
    out["allocation_regret_best_value_in_state"] = float(state_best_value)
    out["allocation_regret_outside_option_value"] = float(outside)
    out["allocation_regret_best_available_value"] = float(best_available)
    out["allocation_regret_i"] = float(regret_i)
    out["allocation_regret_j"] = float(regret_j)
    out["allocation_regret_best_pair"] = float(better_regret)
    out["allocation_regret_worse_pair"] = float(worse_regret)
    out["allocation_regret_gap"] = float(regret_gap)
    out["allocation_regret_gap_relative"] = float(regret_gap_rel)
    out["allocation_regret_cost_weight"] = float(1.0 + min(2.0, worse_regret / max(abs(best_available), 1e-6)))
    return out


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
    by_state: dict[str, list[dict[str, Any]]] = {}
    for c in candidates:
        by_state.setdefault(str(c["state_id"]), []).append(c)
    state_best_value_map = {
        sid: (max(float(r.get("estimated_value_if_allocate_next", 0.0)) for r in rows) if rows else 0.0)
        for sid, rows in by_state.items()
    }

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
        out["pair_uncertainty_std_max"] = max(std_i, std_j)
        out["relative_margin"] = abs(margin) / max(
            abs(float(ci.get("estimated_value_if_allocate_next", 0.0))),
            abs(float(cj.get("estimated_value_if_allocate_next", 0.0))),
            1e-6,
        )
        mode_i = str(ci.get("mode", "unknown"))
        mode_j = str(cj.get("mode", "unknown"))
        out["pair_mode_provenance"] = mode_i if mode_i == mode_j else "mixed"
        out["pair_type"] = pair_type_map.get(k, "generic")
        promoted.append(
            _annotate_ambiguous_pair(
                out,
                tie_policy=str(args.tie_policy),
                tie_abs_margin_threshold=float(args.tie_abs_margin_threshold),
                tie_relative_margin_threshold=float(args.tie_relative_margin_threshold),
                tie_std_threshold=float(args.tie_std_threshold),
                tie_use_near_tie_flag=bool(args.tie_use_near_tie_flag),
                tie_include_approx=bool(args.tie_include_approx),
                tie_require_exact_or_mixed=bool(args.tie_require_exact_or_mixed),
            )
        )

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
        b["pair_uncertainty_std_max"] = max(float(ci.get("allocation_value_std", 0.0)), float(cj.get("allocation_value_std", 0.0)))
        b["relative_margin"] = abs(margin) / max(
            abs(float(ci.get("estimated_value_if_allocate_next", 0.0))),
            abs(float(cj.get("estimated_value_if_allocate_next", 0.0))),
            1e-6,
        )
        mode_i = str(ci.get("mode", "unknown"))
        mode_j = str(cj.get("mode", "unknown"))
        b["pair_mode_provenance"] = mode_i if mode_i == mode_j else "mixed"
        b["pair_type"] = pair_type_map.get(k, "generic")
        baseline_rows.append(
            _annotate_ambiguous_pair(
                b,
                tie_policy=str(args.tie_policy),
                tie_abs_margin_threshold=float(args.tie_abs_margin_threshold),
                tie_relative_margin_threshold=float(args.tie_relative_margin_threshold),
                tie_std_threshold=float(args.tie_std_threshold),
                tie_use_near_tie_flag=bool(args.tie_use_near_tie_flag),
                tie_include_approx=bool(args.tie_include_approx),
                tie_require_exact_or_mixed=bool(args.tie_require_exact_or_mixed),
            )
        )

    promoted_soft = [
        _annotate_soft_probabilistic_target(
            r,
            tie_abs_margin_threshold=float(args.tie_abs_margin_threshold),
            tie_relative_margin_threshold=float(args.tie_relative_margin_threshold),
            tie_std_threshold=float(args.tie_std_threshold),
            tie_use_near_tie_flag=bool(args.tie_use_near_tie_flag),
        )
        for r in promoted
    ]
    promoted_partial_order = [
        _annotate_incomparable_pair(
            r,
            tie_abs_margin_threshold=float(args.tie_abs_margin_threshold),
            tie_relative_margin_threshold=float(args.tie_relative_margin_threshold),
            tie_std_threshold=float(args.tie_std_threshold),
            tie_include_approx=bool(args.tie_include_approx),
            tie_require_exact_or_mixed=bool(args.tie_require_exact_or_mixed),
        )
        for r in promoted
    ]
    promoted_allocation_regret = [
        _annotate_allocation_regret_target(
            r,
            cand_i=cand_map.get((str(r["state_id"]), str(r["branch_i"])), {}),
            cand_j=cand_map.get((str(r["state_id"]), str(r["branch_j"])), {}),
            state_best_value=float(state_best_value_map.get(str(r["state_id"]), 0.0)),
            use_outside_option=True,
            near_tie_margin=float(args.near_tie_margin),
        )
        for r in promoted
    ]
    promoted_allocation_regret_no_outside = [
        _annotate_allocation_regret_target(
            r,
            cand_i=cand_map.get((str(r["state_id"]), str(r["branch_i"])), {}),
            cand_j=cand_map.get((str(r["state_id"]), str(r["branch_j"])), {}),
            state_best_value=float(state_best_value_map.get(str(r["state_id"]), 0.0)),
            use_outside_option=False,
            near_tie_margin=float(args.near_tie_margin),
        )
        for r in promoted
    ]

    regimes: dict[str, list[dict[str, Any]]] = {
        "all_pairs_approx": baseline_rows,
        "promoted_exact_hard_region": promoted,
        "allocation_regret_target": promoted_allocation_regret,
        "allocation_regret_target_no_outside": promoted_allocation_regret_no_outside,
        "soft_prob_promoted_exact_hard_region": promoted_soft,
        "partial_order_promoted_exact_hard_region": promoted_partial_order,
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
            "tie_abs_margin_threshold": args.tie_abs_margin_threshold,
            "tie_relative_margin_threshold": args.tie_relative_margin_threshold,
            "tie_std_threshold": args.tie_std_threshold,
            "tie_use_near_tie_flag": bool(args.tie_use_near_tie_flag),
            "tie_include_approx": bool(args.tie_include_approx),
            "tie_require_exact_or_mixed": bool(args.tie_require_exact_or_mixed),
            "tie_policy": str(args.tie_policy),
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
            "ambiguous_tie_rate": sum(1 for r in rows if bool(r.get("ambiguous_tie_target", False))) / max(1, len(rows)),
            "mean_soft_tie_prob": sum(float(r.get("soft_target_prob_tie", 0.0)) for r in rows) / max(1, len(rows)),
            "partial_order_incomparable_rate": (
                sum(1 for r in rows if bool(r.get("partial_order_incomparable_target", False))) / max(1, len(rows))
            ),
            "allocation_regret_gap_mean": sum(float(r.get("allocation_regret_gap", 0.0)) for r in rows) / max(1, len(rows)),
            "allocation_regret_worse_pair_mean": sum(float(r.get("allocation_regret_worse_pair", 0.0)) for r in rows) / max(1, len(rows)),
            "allocation_regret_cost_weight_mean": sum(float(r.get("allocation_regret_cost_weight", 1.0)) for r in rows) / max(1, len(rows)),
        }
        (d / "target_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        manifest["regimes"][regime] = {"output_dir": str(d), "summary": summary}

    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"output_dir": str(out_root), "regimes": list(regimes.keys())}, indent=2))


if __name__ == "__main__":
    main()
