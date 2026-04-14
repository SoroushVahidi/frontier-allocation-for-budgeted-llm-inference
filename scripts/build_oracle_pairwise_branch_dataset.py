#!/usr/bin/env python3
"""Build pairwise branch-preference data from approximate bounded oracle-ish continuation labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build pairwise dataset from oracle-ish branch labels")
    p.add_argument("--branch-labels", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--tie-margin", type=float, default=0.02)
    return p.parse_args()


def _load(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def main() -> None:
    args = parse_args()
    rows = _load(Path(args.branch_labels))

    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((int(row["episode_id"]), int(row["decision_id"])), []).append(row)

    out_rows: list[dict[str, Any]] = []
    ties = 0
    uncertain = 0

    for (episode_id, decision_id), group in grouped.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a = group[i]
                b = group[j]
                ua = float(a["approx_oracle_continuation_value"])
                ub = float(b["approx_oracle_continuation_value"])
                diff = ua - ub
                tie = abs(diff) <= float(args.tie_margin)
                if tie:
                    ties += 1
                a_preferred = diff > 0.0 if not tie else (str(a["branch_id"]) <= str(b["branch_id"]))
                pair_conf = min(1.0, abs(diff) / max(1e-9, 0.2))
                tie_or_uncertain = int(abs(diff) <= 2.0 * float(args.tie_margin))
                uncertain += tie_or_uncertain

                out_rows.append(
                    {
                        "episode_id": episode_id,
                        "decision_id": decision_id,
                        "split": a.get("split", "train"),
                        "remaining_budget": int(a.get("remaining_budget", 0)),
                        "branch_a_id": a["branch_id"],
                        "branch_b_id": b["branch_id"],
                        "a_preferred": int(a_preferred),
                        "preference_label": int(a_preferred),
                        "tie": int(tie),
                        "label_source": "approx_oracle_continuation_value",
                        "utility_a": ua,
                        "utility_b": ub,
                        "features_a": a["features_v7"],
                        "features_b": b["features_v7"],
                        "preference_margin": abs(diff),
                        "pair_confidence": pair_conf,
                        "tie_or_uncertain": tie_or_uncertain,
                    }
                )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row) + "\n")

    meta = {
        "source": str(Path(args.branch_labels)),
        "pair_rows": len(out_rows),
        "tie_rows": ties,
        "tie_or_uncertain_rows": uncertain,
        "label_name": "approx_oracle_continuation_value",
        "label_caveat": "Approximate bounded oracle-ish continuation labels, not exact global oracle truth.",
    }
    out_path.with_name(out_path.stem + "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
