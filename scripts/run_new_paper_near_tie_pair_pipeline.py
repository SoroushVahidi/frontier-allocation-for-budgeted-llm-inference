#!/usr/bin/env python3
"""Extract and summarize hard near-tie branch pairs (new-paper track, text-only outputs)."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build near-tie/hard-pair dataset from proxy BT pairwise data")
    p.add_argument("--pairwise-dataset", required=True)
    p.add_argument("--bt-model", required=True)
    p.add_argument("--oracle-pairwise", default=None)
    p.add_argument("--output-root", default="outputs/new_paper/near_tie_pairs")
    p.add_argument("--run-id", default=None)
    p.add_argument("--abs-proxy-margin-threshold", type=float, default=0.08)
    p.add_argument("--abs-bt-margin-threshold", type=float, default=0.12)
    p.add_argument("--low-confidence-threshold", type=float, default=0.35)
    p.add_argument("--dominant-signal-threshold", type=float, default=0.06)
    p.add_argument("--min-signals", type=int, default=1)
    return p.parse_args()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _score(model: dict[str, Any], features: dict[str, float]) -> float:
    s = float(model.get("intercept", 0.0))
    for name, weight in model.get("weights", {}).items():
        s += float(weight) * float(features.get(name, 0.0))
    return s


def _pair_key(episode_id: int, decision_id: int, a: str, b: str) -> tuple[int, int, str, str]:
    x, y = sorted([str(a), str(b)])
    return (int(episode_id), int(decision_id), x, y)


def _oracle_map(rows: list[dict[str, Any]]) -> dict[tuple[int, int, str, str], int]:
    out: dict[tuple[int, int, str, str], int] = {}
    for r in rows:
        key = _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"])
        pref = int(r.get("oracle_preference", 0))
        # Map to canonical sorted ordering preference.
        a = str(r["branch_a_id"])
        b = str(r["branch_b_id"])
        canonical_pref = pref
        if sorted([a, b])[0] != a:
            canonical_pref = -pref
        out[key] = canonical_pref
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    pair_rows = _load_jsonl(Path(args.pairwise_dataset))
    model = json.loads(Path(args.bt_model).read_text(encoding="utf-8"))
    oracle_lookup: dict[tuple[int, int, str, str], int] = {}
    if args.oracle_pairwise:
        oracle_lookup = _oracle_map(_load_jsonl(Path(args.oracle_pairwise)))

    near_rows: list[dict[str, Any]] = []
    signal_counts: dict[str, int] = {}
    budget_bins: dict[str, int] = {}
    joined_oracle = 0
    oracle_disagree = 0

    for r in pair_rows:
        ua = float(r.get("utility_a", 0.0))
        ub = float(r.get("utility_b", 0.0))
        proxy_margin = abs(ua - ub)
        bta = _score(model, r["features_a"])
        btb = _score(model, r["features_b"])
        bt_margin = abs(bta - btb)
        conf = float(r.get("pair_confidence", 0.0))

        signals = {
            "small_proxy_margin": int(proxy_margin <= float(args.abs_proxy_margin_threshold)),
            "small_bt_margin": int(bt_margin <= float(args.abs_bt_margin_threshold)),
            "low_confidence": int(conf <= float(args.low_confidence_threshold)),
            "tie_or_uncertain": int(r.get("tie_or_uncertain", 0)),
            "dominant_signal_collapse": int(abs(float(r["features_a"].get("node_3_score", 0.0)) - float(r["features_b"].get("node_3_score", 0.0)) <= float(args.dominant_signal_threshold))),
        }

        key = _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"])
        oracle_pref = None
        proxy_pref_canonical = 1 if ua >= ub else -1
        if key in oracle_lookup:
            joined_oracle += 1
            oracle_pref = oracle_lookup[key]
            if int(oracle_pref) != int(proxy_pref_canonical):
                oracle_disagree += 1
                signals["proxy_oracle_disagree"] = 1
            else:
                signals["proxy_oracle_disagree"] = 0
        else:
            signals["proxy_oracle_disagree"] = 0

        n_signals = sum(int(v) for v in signals.values())
        if n_signals < int(args.min_signals):
            continue

        for k, v in signals.items():
            if v:
                signal_counts[k] = signal_counts.get(k, 0) + 1

        rem = int(r.get("remaining_budget", 0))
        bkey = "0-2" if rem <= 2 else ("3-5" if rem <= 5 else "6+")
        budget_bins[bkey] = budget_bins.get(bkey, 0) + 1

        near_rows.append(
            {
                "pair_key": "|".join(map(str, key)),
                "episode_id": int(r["episode_id"]),
                "decision_id": int(r["decision_id"]),
                "split": r.get("split", "train"),
                "remaining_budget": rem,
                "branch_a_id": r["branch_a_id"],
                "branch_b_id": r["branch_b_id"],
                "features_a": r["features_a"],
                "features_b": r["features_b"],
                "proxy_utility_a": ua,
                "proxy_utility_b": ub,
                "proxy_margin": proxy_margin,
                "bt_score_a": bta,
                "bt_score_b": btb,
                "bt_margin": bt_margin,
                "pair_confidence": conf,
                "tie": int(r.get("tie", 0)),
                "tie_or_uncertain": int(r.get("tie_or_uncertain", 0)),
                "proxy_preference": int(r.get("a_preferred", 0)),
                "oracle_preference_canonical": oracle_pref,
                "proxy_oracle_disagree": int(signals["proxy_oracle_disagree"]),
                **signals,
                "signal_count": n_signals,
            }
        )

    near_path = out_dir / "near_tie_pairs.jsonl"
    with near_path.open("w", encoding="utf-8") as f:
        for r in near_rows:
            f.write(json.dumps(r) + "\n")

    summary_json = {
        "run_id": run_id,
        "n_total_pairs": len(pair_rows),
        "n_near_tie_pairs": len(near_rows),
        "near_tie_rate": len(near_rows) / max(1, len(pair_rows)),
        "signal_counts": signal_counts,
        "remaining_budget_distribution": budget_bins,
        "oracle_joined_pairs": joined_oracle,
        "oracle_disagreement_rate_on_joined": oracle_disagree / max(1, joined_oracle),
    }
    (out_dir / "hard_pair_summary.json").write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

    summary_rows = [
        {"metric": "n_total_pairs", "value": len(pair_rows)},
        {"metric": "n_near_tie_pairs", "value": len(near_rows)},
        {"metric": "near_tie_rate", "value": len(near_rows) / max(1, len(pair_rows))},
        {"metric": "oracle_joined_pairs", "value": joined_oracle},
        {"metric": "oracle_disagreement_rate_on_joined", "value": oracle_disagree / max(1, joined_oracle)},
    ]
    summary_rows.extend({"metric": f"signal_{k}", "value": v} for k, v in sorted(signal_counts.items()))
    summary_rows.extend({"metric": f"budget_bin_{k}", "value": v} for k, v in sorted(budget_bins.items()))
    _write_csv(out_dir / "hard_pair_summary.csv", summary_rows)

    md = [
        f"# Hard near-tie pair summary ({run_id})",
        "",
        "This report is generated from proxy BT pairwise data with optional oracle-ish join.",
        f"- Total pairs: {len(pair_rows)}",
        f"- Near-tie/hard pairs: {len(near_rows)} ({len(near_rows) / max(1, len(pair_rows)):.3f})",
        f"- Oracle-joined pairs: {joined_oracle}",
        f"- Proxy-vs-oracle disagreement rate on joined hard pairs: {oracle_disagree / max(1, joined_oracle):.3f}",
        "",
        "## Dominant hard-pair signals",
    ]
    for k, v in sorted(signal_counts.items(), key=lambda x: x[1], reverse=True):
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Remaining-budget distribution (hard pairs)")
    for k, v in sorted(budget_bins.items()):
        md.append(f"- {k}: {v}")
    (out_dir / "hard_pair_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"run_id": run_id, "out_dir": str(out_dir), "summary": summary_json}, indent=2))


if __name__ == "__main__":
    main()
