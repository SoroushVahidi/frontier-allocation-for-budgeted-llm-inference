#!/usr/bin/env python3
"""Audit current branch-allocation data utilization and write reusable summaries."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _field_presence(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, float]:
    n = max(1, len(rows))
    return {f: sum(1 for r in rows if f in r) / n for f in fields}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit data utilization from existing branch-allocation artifacts")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--regime-root", default="")
    p.add_argument("--output-dir", default="outputs/data_utilization_audit")
    p.add_argument("--run-id", required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    labels_dir = Path(args.labels_dir)
    regime_root = Path(args.regime_root) if args.regime_root else None
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = _read_jsonl(labels_dir / "candidate_labels.jsonl")
    pairs = _read_jsonl(labels_dir / "pairwise_labels.jsonl")
    states = _read_jsonl(labels_dir / "state_summaries.jsonl")

    candidate_fields = [
        "estimated_value_if_allocate_next",
        "allocation_value_std",
        "branch_vs_outside_gap",
        "features_branch_v1",
        "mode",
    ]
    pair_fields = [
        "margin",
        "near_tie_flag",
        "pair_uncertainty_std_mean",
        "ambiguous_tie_target",
        "partial_order_label",
        "soft_target_prob_tie",
        "ternary_defer_label",
        "penalized_marginal_gap",
        "exact_vs_approx_disagreement_risk",
        "supervision_reliability_weight",
    ]

    regime_stats: dict[str, Any] = {}
    if regime_root and regime_root.exists():
        for d in sorted(regime_root.glob("regime_*")):
            rp = d / "pairwise_labels.jsonl"
            if not rp.exists():
                continue
            rr = _read_jsonl(rp)
            if not rr:
                continue
            regime_name = d.name.replace("regime_", "", 1)
            regime_stats[regime_name] = {
                "rows": len(rr),
                "field_presence": _field_presence(rr, pair_fields),
                "defer_rate_if_penalized": sum(
                    1 for r in rr if str(r.get("penalized_ternary_label_name", "")) == "defer"
                )
                / max(1, len(rr)),
                "ambiguous_tie_rate": sum(1 for r in rr if bool(r.get("ambiguous_tie_target", False))) / max(1, len(rr)),
            }

    by_budget = Counter(str(int(r.get("remaining_budget", 0))) for r in pairs)
    by_dataset = Counter(str(r.get("dataset_name", "unknown")) for r in pairs)
    by_mode = Counter(str(r.get("mode", "unknown")) for r in candidates)

    underutilized_signals = {
        "exact_vs_approx_disagreement_signal_sparse": (
            sum(1 for r in pairs if bool(r.get("exact_vs_approx_disagreement_risk", False))) / max(1, len(pairs))
        ),
        "partial_order_label_sparse": sum(1 for r in pairs if "partial_order_label" in r) / max(1, len(pairs)),
        "soft_prob_target_sparse": sum(1 for r in pairs if "soft_target_prob_tie" in r) / max(1, len(pairs)),
        "supervision_reliability_weight_sparse": sum(1 for r in pairs if "supervision_reliability_weight" in r) / max(1, len(pairs)),
    }

    summary = {
        "inputs": {
            "labels_dir": str(labels_dir),
            "regime_root": str(regime_root) if regime_root else None,
        },
        "counts": {
            "states": len(states),
            "candidates": len(candidates),
            "pairwise": len(pairs),
        },
        "base_field_presence": {
            "candidate": _field_presence(candidates, candidate_fields),
            "pairwise": _field_presence(pairs, pair_fields),
        },
        "distribution": {
            "pairwise_by_budget": dict(by_budget),
            "pairwise_by_dataset": dict(by_dataset),
            "candidate_by_mode": dict(by_mode),
        },
        "regime_stats": regime_stats,
        "underutilized_signals": underutilized_signals,
        "recommended_priorities": {
            "reprocess_now": [
                "preserve advanced pairwise supervision fields into canonical corpus rows",
                "surface disagreement and hard-case rates by dataset/budget in summaries",
            ],
            "relabel_now": [
                "prioritize exact relabeling candidates where disagreement + near-tie + adjacent-rank overlap",
            ],
            "slice_analyze_now": [
                "track defer/coverage/accepted-accuracy by budget + ambiguity + provenance jointly",
            ],
            "collect_labels_later": [
                "expand exact relabel budget only for decision-critical hard slices",
            ],
            "new_datasets_later": [
                "add second reasoning dataset once hard-slice semantics stabilize on current corpus",
            ],
        },
        "implemented_changes": [
            "canonical corpus passthrough for advanced pairwise fields",
            "disagreement-aware ambiguity flag support during learning-table prep",
        ],
        "caveats": [
            "audit uses currently available labels/regimes only",
            "field-presence rates do not by themselves prove causal utility",
        ],
    }

    (out_dir / "data_utilization_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# Current data utilization audit",
        "",
        f"- labels_dir: `{labels_dir}`",
        f"- candidates: `{len(candidates)}`",
        f"- pairwise: `{len(pairs)}`",
        f"- states: `{len(states)}`",
        "",
        "## Underutilized signal rates (base pair rows)",
    ]
    for k, v in underutilized_signals.items():
        md.append(f"- {k}: `{v:.4f}`")
    md.append("")
    md.append("## Implemented now")
    for item in summary["implemented_changes"]:
        md.append(f"- {item}")
    md.append("")
    md.append("## Recommended next")
    for item in summary["recommended_priorities"]["relabel_now"]:
        md.append(f"- {item}")
    (out_dir / "data_utilization_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "pairwise": len(pairs), "regime_count": len(regime_stats)}, indent=2))


if __name__ == "__main__":
    main()
