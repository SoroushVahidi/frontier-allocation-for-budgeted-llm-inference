#!/usr/bin/env python3
"""Build a curated ambiguous branch-comparison dataset (new-paper, bounded/cheap)."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build curated ambiguous branch-comparison dataset")
    p.add_argument("--output-root", default="outputs/new_paper/ambiguous_branch_dataset")
    p.add_argument("--run-id", default=None)
    p.add_argument("--seed", type=int, default=91)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=140)
    p.add_argument("--oracle-episodes", type=int, default=30)
    p.add_argument("--max-pairs", type=int, default=520)
    p.add_argument("--abs-proxy-margin-threshold", type=float, default=0.08)
    p.add_argument("--abs-bt-margin-threshold", type=float, default=0.12)
    p.add_argument("--low-confidence-threshold", type=float, default=0.35)
    p.add_argument("--oracle-strong-margin", type=float, default=0.08)
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _linear_score(model: dict[str, Any], feats: dict[str, float]) -> float:
    s = float(model.get("intercept", 0.0))
    for name, weight in model.get("weights", {}).items():
        s += float(weight) * float(feats.get(name, 0.0))
    return s


def _pref_from_delta(delta: float, tie_margin: float = 1e-12) -> int:
    if abs(delta) <= tie_margin:
        return 0
    return 1 if delta > 0 else -1


def _pair_key(episode_id: int, decision_id: int, a: str, b: str) -> str:
    x, y = sorted([str(a), str(b)])
    return f"{int(episode_id)}|{int(decision_id)}|{x}|{y}"


def _canonical_pref(a_id: str, b_id: str, pref_oriented_to_a: int) -> int:
    x, _ = sorted([str(a_id), str(b_id)])
    return int(pref_oriented_to_a) if str(a_id) == x else int(-pref_oriented_to_a)


def _build_reason_codes(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if bool(row["flag_near_tie"]):
        reasons.append("near_tie")
    if bool(row["flag_low_confidence"]):
        reasons.append("low_confidence")
    if bool(row["flag_proxy_oracle_disagree"]):
        reasons.append("proxy_oracle_disagree")
    if bool(row["flag_bt_vs_oracle_disagree"]):
        reasons.append("bt_oracle_disagree")
    if bool(row["flag_raokupper_vs_oracle_disagree"]):
        reasons.append("raokupper_oracle_disagree")
    if bool(row["flag_bt_raokupper_disagree"]):
        reasons.append("bt_raokupper_disagree")
    if bool(row["flag_oracle_margin_strong"]):
        reasons.append("strong_oracle_margin")
    if bool(row["flag_proxy_weak_separation"]):
        reasons.append("weak_proxy_separation")
    return reasons


def _tier(row: dict[str, Any]) -> str:
    if bool(row["has_oracle_reference"]):
        if bool(row["flag_bt_vs_oracle_disagree"]) and bool(row["flag_oracle_margin_strong"]):
            return "A"
        disagree_count = int(row["flag_proxy_oracle_disagree"]) + int(row["flag_bt_vs_oracle_disagree"]) + int(row["flag_raokupper_vs_oracle_disagree"])
        if disagree_count >= 2 or (bool(row["flag_bt_raokupper_disagree"]) and bool(row["flag_near_tie"])):
            return "A"
        if bool(row["flag_near_tie"]) or bool(row["flag_low_confidence"]) or bool(row["flag_proxy_weak_separation"]):
            return "B"
        return "C"
    if bool(row["flag_bt_raokupper_disagree"]) and bool(row["flag_near_tie"]):
        return "B"
    if bool(row["flag_near_tie"]) or bool(row["flag_low_confidence"]):
        return "C"
    return "C"


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    stage_dir = run_dir / "staging"
    stage_dir.mkdir(parents=True, exist_ok=True)

    ranking_path = stage_dir / "branch_scorer_v3_dataset.jsonl"
    pairwise_path = stage_dir / "pairwise_dataset.jsonl"
    bt_model_path = stage_dir / "model_bt_baseline.json"
    rk_model_path = stage_dir / "model_bt_raokupper_tie_or_uncertain.json"
    oracle_dir = stage_dir / "oracle_labels"

    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"),
        "--output-dir",
        str(stage_dir),
        "--episodes",
        str(args.ranking_episodes),
        "--budget",
        str(args.budget),
        "--seed",
        str(args.seed),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/build_bt_pairwise_branch_dataset.py"),
        "--ranking-dataset",
        str(ranking_path),
        "--output",
        str(pairwise_path),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(pairwise_path),
        "--output",
        str(bt_model_path),
        "--seed",
        str(args.seed),
        "--objective",
        "bt",
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(pairwise_path),
        "--output",
        str(rk_model_path),
        "--seed",
        str(args.seed),
        "--objective",
        "raokupper",
        "--tie-supervision",
        "tie_or_uncertain",
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/run_new_paper_oracle_branch_label_generation.py"),
        "--output-root",
        str(oracle_dir),
        "--run-id",
        "oracle_source",
        "--episodes",
        str(args.oracle_episodes),
        "--seed",
        str(args.seed),
        "--decision-budget",
        str(args.budget),
        "--max-decisions-per-episode-to-label",
        "3",
        "--max-branches-per-decision",
        "3",
        "--rollouts-per-policy",
        "3",
        "--value-aggregation",
        "robust_blend",
        "--value-std-penalty",
        "0.1",
    ])

    bt_model = _load_json(bt_model_path)
    rk_model = _load_json(rk_model_path)
    pair_rows = _load_jsonl(pairwise_path)

    oracle_branch_rows = _load_jsonl(oracle_dir / "oracle_source" / "branch_oracle_labels.jsonl")
    oracle_pair_rows = _load_jsonl(oracle_dir / "oracle_source" / "pairwise_oracle_preferences.jsonl")

    oracle_branch_map: dict[str, dict[str, Any]] = {}
    for row in oracle_branch_rows:
        oracle_branch_map[f"{int(row['episode_id'])}|{int(row['decision_id'])}|{row['branch_id']}"] = row

    curated: list[dict[str, Any]] = []

    # Source 1: Pairwise BT dataset (no oracle reference).
    for r in pair_rows:
        ua = float(r.get("utility_a", 0.0))
        ub = float(r.get("utility_b", 0.0))
        proxy_margin = abs(ua - ub)
        conf = float(r.get("pair_confidence", 0.0))
        bt_a = _linear_score(bt_model, r["features_a"])
        bt_b = _linear_score(bt_model, r["features_b"])
        rk_a = _linear_score(rk_model, r["features_a"])
        rk_b = _linear_score(rk_model, r["features_b"])
        bt_margin = abs(bt_a - bt_b)

        near_tie = proxy_margin <= float(args.abs_proxy_margin_threshold) or bt_margin <= float(args.abs_bt_margin_threshold) or int(r.get("tie_or_uncertain", 0)) == 1
        low_conf = conf <= float(args.low_confidence_threshold)
        bt_pref = _pref_from_delta(bt_a - bt_b)
        rk_pref = _pref_from_delta(rk_a - rk_b)
        bt_rk_disagree = bt_pref != rk_pref
        weak_proxy_sep = proxy_margin <= 0.05

        if not (near_tie or low_conf or bt_rk_disagree):
            continue

        a_id = str(r["branch_a_id"])
        b_id = str(r["branch_b_id"])
        proxy_pref = _canonical_pref(a_id, b_id, 1 if ua >= ub else -1)
        bt_pref_can = _canonical_pref(a_id, b_id, bt_pref)
        rk_pref_can = _canonical_pref(a_id, b_id, rk_pref)

        rec = {
            "pair_key": _pair_key(int(r["episode_id"]), int(r["decision_id"]), a_id, b_id),
            "source_group": "pairwise_bt_dataset",
            "episode_id": int(r["episode_id"]),
            "decision_id": int(r["decision_id"]),
            "remaining_budget": int(r.get("remaining_budget", 0)),
            "branch_a_id": a_id,
            "branch_b_id": b_id,
            "proxy_utility_a": ua,
            "proxy_utility_b": ub,
            "proxy_margin": proxy_margin,
            "proxy_preference_canonical": proxy_pref,
            "proxy_bt_score_a": bt_a,
            "proxy_bt_score_b": bt_b,
            "proxy_bt_margin": bt_margin,
            "proxy_bt_preference_canonical": bt_pref_can,
            "raokupper_score_a": rk_a,
            "raokupper_score_b": rk_b,
            "raokupper_preference_canonical": rk_pref_can,
            "pair_confidence": conf,
            "tie_flag": int(r.get("tie", 0)),
            "tie_or_uncertain_flag": int(r.get("tie_or_uncertain", 0)),
            "has_oracle_reference": 0,
            "oracle_preference_canonical": None,
            "oracle_margin": None,
            "oracle_tie_flag": None,
            "flag_near_tie": int(near_tie),
            "flag_low_confidence": int(low_conf),
            "flag_proxy_oracle_disagree": 0,
            "flag_bt_vs_oracle_disagree": 0,
            "flag_raokupper_vs_oracle_disagree": 0,
            "flag_bt_raokupper_disagree": int(bt_rk_disagree),
            "flag_oracle_margin_strong": 0,
            "flag_proxy_weak_separation": int(weak_proxy_sep),
            "feature_summary": {
                "node_3_score_a": float(r["features_a"].get("node_3_score", 0.0)),
                "node_3_score_b": float(r["features_b"].get("node_3_score", 0.0)),
                "verify_count_a": float(r["features_a"].get("verify_count", 0.0)),
                "verify_count_b": float(r["features_b"].get("verify_count", 0.0)),
                "stalled_steps_a": float(r["features_a"].get("stalled_steps", 0.0)),
                "stalled_steps_b": float(r["features_b"].get("stalled_steps", 0.0)),
            },
        }
        rec["reason_codes"] = _build_reason_codes(rec)
        rec["quality_tier"] = _tier(rec)
        curated.append(rec)

    # Source 2: Oracle-ish pairwise preferences + branch features.
    for r in oracle_pair_rows:
        a_id = str(r["branch_a_id"])
        b_id = str(r["branch_b_id"])
        a_branch = oracle_branch_map.get(f"{int(r['episode_id'])}|{int(r['decision_id'])}|{a_id}")
        b_branch = oracle_branch_map.get(f"{int(r['episode_id'])}|{int(r['decision_id'])}|{b_id}")
        if (a_branch is None) or (b_branch is None):
            continue

        feats_a = a_branch.get("features_v7", {})
        feats_b = b_branch.get("features_v7", {})
        bt_a = _linear_score(bt_model, feats_a)
        bt_b = _linear_score(bt_model, feats_b)
        rk_a = _linear_score(rk_model, feats_a)
        rk_b = _linear_score(rk_model, feats_b)
        bt_pref = _pref_from_delta(bt_a - bt_b, tie_margin=0.02)
        rk_pref = _pref_from_delta(rk_a - rk_b, tie_margin=0.02)

        oracle_pref = int(r.get("oracle_preference", 0))
        proxy_pref = int(r.get("proxy_preference", 0))
        oracle_margin = float(r.get("oracle_margin", 0.0))
        proxy_margin = float(r.get("proxy_margin", 0.0))
        near_tie = bool(int(r.get("oracle_tie", 0))) or bool(int(r.get("proxy_tie", 0))) or (oracle_margin <= 0.03)
        weak_proxy_sep = proxy_margin <= 0.05

        bt_vs_oracle = (oracle_pref != 0) and (bt_pref != oracle_pref)
        rk_vs_oracle = (oracle_pref != 0) and (rk_pref != oracle_pref)
        proxy_oracle = oracle_pref != proxy_pref
        bt_rk_disagree = bt_pref != rk_pref
        include = near_tie or proxy_oracle or bt_vs_oracle or rk_vs_oracle or bt_rk_disagree or (oracle_margin >= float(args.oracle_strong_margin) and proxy_oracle)
        if not include:
            continue

        rec = {
            "pair_key": _pair_key(int(r["episode_id"]), int(r["decision_id"]), a_id, b_id),
            "source_group": "oracle_pairwise_labels",
            "episode_id": int(r["episode_id"]),
            "decision_id": int(r["decision_id"]),
            "remaining_budget": int(r.get("remaining_budget", 0)),
            "branch_a_id": a_id,
            "branch_b_id": b_id,
            "proxy_utility_a": float(r.get("proxy_a", 0.0)),
            "proxy_utility_b": float(r.get("proxy_b", 0.0)),
            "proxy_margin": proxy_margin,
            "proxy_preference_canonical": proxy_pref,
            "proxy_bt_score_a": bt_a,
            "proxy_bt_score_b": bt_b,
            "proxy_bt_margin": abs(bt_a - bt_b),
            "proxy_bt_preference_canonical": bt_pref,
            "raokupper_score_a": rk_a,
            "raokupper_score_b": rk_b,
            "raokupper_preference_canonical": rk_pref,
            "pair_confidence": None,
            "tie_flag": int(r.get("proxy_tie", 0)),
            "tie_or_uncertain_flag": int(r.get("oracle_tie", 0)),
            "has_oracle_reference": 1,
            "oracle_preference_canonical": oracle_pref,
            "oracle_margin": oracle_margin,
            "oracle_tie_flag": int(r.get("oracle_tie", 0)),
            "flag_near_tie": int(near_tie),
            "flag_low_confidence": 0,
            "flag_proxy_oracle_disagree": int(proxy_oracle),
            "flag_bt_vs_oracle_disagree": int(bt_vs_oracle),
            "flag_raokupper_vs_oracle_disagree": int(rk_vs_oracle),
            "flag_bt_raokupper_disagree": int(bt_rk_disagree),
            "flag_oracle_margin_strong": int(oracle_margin >= float(args.oracle_strong_margin)),
            "flag_proxy_weak_separation": int(weak_proxy_sep),
            "feature_summary": {
                "depth_a": int(a_branch.get("depth", 0)),
                "depth_b": int(b_branch.get("depth", 0)),
                "verify_count_a": int(a_branch.get("verify_count", 0)),
                "verify_count_b": int(b_branch.get("verify_count", 0)),
                "stalled_steps_a": int(a_branch.get("stalled_steps", 0)),
                "stalled_steps_b": int(b_branch.get("stalled_steps", 0)),
                "label_kind_a": a_branch.get("label_kind", ""),
                "label_kind_b": b_branch.get("label_kind", ""),
            },
        }
        rec["reason_codes"] = _build_reason_codes(rec)
        rec["quality_tier"] = _tier(rec)
        curated.append(rec)

    curated_sorted = sorted(
        curated,
        key=lambda x: (
            0 if x["quality_tier"] == "A" else (1 if x["quality_tier"] == "B" else 2),
            -int(x["has_oracle_reference"]),
            -len(x["reason_codes"]),
            -float(x["oracle_margin"] or 0.0),
            -float(x["proxy_bt_margin"]),
        ),
    )[: int(args.max_pairs)]

    out_jsonl = run_dir / "ambiguous_branch_pairs.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as f:
        for row in curated_sorted:
            f.write(json.dumps(row) + "\n")

    reason_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for row in curated_sorted:
        source_counts[str(row["source_group"])] = source_counts.get(str(row["source_group"]), 0) + 1
        tier_counts[str(row["quality_tier"])] = tier_counts.get(str(row["quality_tier"]), 0) + 1
        for reason in row["reason_codes"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    summary_rows: list[dict[str, Any]] = []
    summary_rows.append({"group": "dataset", "name": "n_pairs", "count": len(curated_sorted)})
    summary_rows.extend({"group": "source_group", "name": k, "count": v} for k, v in sorted(source_counts.items()))
    summary_rows.extend({"group": "quality_tier", "name": k, "count": v} for k, v in sorted(tier_counts.items()))
    summary_rows.extend({"group": "reason_code", "name": k, "count": v} for k, v in sorted(reason_counts.items(), key=lambda x: (-x[1], x[0])))
    _write_csv(run_dir / "ambiguous_branch_pairs_summary.csv", summary_rows)

    oracle_subset = [r for r in curated_sorted if bool(r["has_oracle_reference"]) and int(r["oracle_preference_canonical"] or 0) != 0]

    def _acc(rows: list[dict[str, Any]], field: str) -> float:
        if not rows:
            return 0.0
        ok = 0
        for row in rows:
            ok += int(int(row[field]) == int(row["oracle_preference_canonical"]))
        return ok / len(rows)

    method_rows = [
        {"method": "proxy_preference", "n_oracle_pairs": len(oracle_subset), "agreement_with_oracle_reference": _acc(oracle_subset, "proxy_preference_canonical")},
        {"method": "proxy_bt", "n_oracle_pairs": len(oracle_subset), "agreement_with_oracle_reference": _acc(oracle_subset, "proxy_bt_preference_canonical")},
        {"method": "raokupper", "n_oracle_pairs": len(oracle_subset), "agreement_with_oracle_reference": _acc(oracle_subset, "raokupper_preference_canonical")},
    ]
    _write_csv(run_dir / "method_agreement_on_ambiguous_pairs.csv", method_rows)

    proxy_bt_acc = next((float(r["agreement_with_oracle_reference"]) for r in method_rows if r["method"] == "proxy_bt"), 0.0)
    rk_acc = next((float(r["agreement_with_oracle_reference"]) for r in method_rows if r["method"] == "raokupper"), 0.0)

    slice_md = [
        f"# Ambiguous-slice method comparison ({run_id})",
        "",
        f"- Oracle-referenced ambiguous pairs used: **{len(oracle_subset)}**.",
        f"- Proxy BT agreement vs oracle-ish reference: **{proxy_bt_acc:.3f}**.",
        f"- Rao-Kupper agreement vs oracle-ish reference: **{rk_acc:.3f}**.",
        f"- Delta (Rao-Kupper - Proxy BT): **{(rk_acc - proxy_bt_acc):+.3f}**.",
        "",
        "## Where proxy BT fails most",
        f"- `bt_oracle_disagree` count: {reason_counts.get('bt_oracle_disagree', 0)}.",
        f"- `strong_oracle_margin` count: {reason_counts.get('strong_oracle_margin', 0)}.",
        "",
        "## Where Rao-Kupper helps/hurts",
        f"- `bt_raokupper_disagree` count: {reason_counts.get('bt_raokupper_disagree', 0)}.",
        "- Improvement is counted only against oracle-referenced rows and remains approximate (bounded oracle-ish labels).",
    ]
    (run_dir / "ambiguous_slice_comparison.md").write_text("\n".join(slice_md) + "\n", encoding="utf-8")

    schema = {
        "dataset_name": "ambiguous_branch_pairs",
        "version": "v1",
        "description": "Curated hard/ambiguous branch comparisons from pairwise BT data + bounded oracle-ish pair labels.",
        "quality_tiers": {
            "A": "Strong/high-value disagreement (especially oracle-referenced disagreements with strong margin or multi-signal conflict).",
            "B": "Useful ambiguous cases with meaningful conflict/near-tie signals.",
            "C": "Weaker but still informative ambiguity cases.",
        },
        "fields": {
            "pair_key": "Canonical pair identifier episode|decision|branch_low|branch_high.",
            "source_group": "Origin: pairwise_bt_dataset or oracle_pairwise_labels.",
            "proxy_preference_canonical": "Proxy preference in canonical branch ordering (-1/0/1).",
            "proxy_bt_preference_canonical": "Plain proxy BT model preference in canonical ordering (-1/0/1).",
            "raokupper_preference_canonical": "Rao-Kupper model preference in canonical ordering (-1/0/1).",
            "oracle_preference_canonical": "Oracle-ish preference when available (-1/0/1, null if unavailable).",
            "reason_codes": "Inclusion reason codes used for curation.",
            "quality_tier": "A/B/C usefulness tier.",
        },
    }
    (run_dir / "ambiguous_branch_dataset_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")

    interpretation = [
        f"# Ambiguous branch dataset interpretation ({run_id})",
        "",
        "## What this resource is",
        "- A bounded, text-only curation of hard branch-comparison cases intended for targeted evaluation/inspection and later supervision experiments.",
        "- It is not a gold label set; oracle-ish references are bounded approximations.",
        "",
        "## Coverage",
        f"- Total curated pairs: **{len(curated_sorted)}**.",
        f"- Oracle-referenced pairs: **{sum(1 for r in curated_sorted if bool(r['has_oracle_reference']))}**.",
        f"- Tier counts: A={tier_counts.get('A', 0)}, B={tier_counts.get('B', 0)}, C={tier_counts.get('C', 0)}.",
        "",
        "## Conservative findings",
        f"- Proxy BT agreement on oracle-referenced ambiguous slice: {proxy_bt_acc:.3f}.",
        f"- Rao-Kupper agreement on oracle-referenced ambiguous slice: {rk_acc:.3f}.",
        f"- Rao-Kupper minus Proxy BT on this slice: {(rk_acc - proxy_bt_acc):+.3f}.",
        "- If this delta is small/mixed, the main value of the dataset is targeted evaluation + manual inspection, not immediate default-switch decisions.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interpretation) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "seed": args.seed,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "oracle_episodes": args.oracle_episodes,
        "max_pairs": args.max_pairs,
        "input_artifacts": {
            "pairwise_dataset": str(pairwise_path),
            "bt_model": str(bt_model_path),
            "raokupper_model": str(rk_model_path),
            "oracle_branch_labels": str(oracle_dir / "oracle_source" / "branch_oracle_labels.jsonl"),
            "oracle_pairwise_preferences": str(oracle_dir / "oracle_source" / "pairwise_oracle_preferences.jsonl"),
        },
        "outputs": {
            "ambiguous_branch_pairs": str(run_dir / "ambiguous_branch_pairs.jsonl"),
            "summary": str(run_dir / "ambiguous_branch_pairs_summary.csv"),
            "schema": str(run_dir / "ambiguous_branch_dataset_schema.json"),
            "method_agreement": str(run_dir / "method_agreement_on_ambiguous_pairs.csv"),
            "slice_comparison": str(run_dir / "ambiguous_slice_comparison.md"),
            "interpretation": str(run_dir / "interpretation.md"),
        },
        "counts": {
            "n_pairs": len(curated_sorted),
            "n_oracle_reference_pairs": len(oracle_subset),
            "tier_counts": tier_counts,
            "reason_counts": reason_counts,
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "n_pairs": len(curated_sorted), "n_oracle_reference_pairs": len(oracle_subset)}, indent=2))


if __name__ == "__main__":
    main()
