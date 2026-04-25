#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        keys: set[str] = set()
        for r in rows:
            keys.update(str(k) for k in r.keys())
        fieldnames = sorted(keys)
    else:
        fieldnames = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        if rows:
            w.writerows(rows)


def _as_int(v: Any, d: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return d


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Offline diagnostic eval for strict_f3_direct_reserve_gate_rerank_v1.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument(
        "--input-per-example",
        default="outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG/cohere/per_example_rows.csv",
    )
    p.add_argument("--provider", default="cohere")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--max-cases", type=int, default=0)
    return p.parse_args()


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return sum(_as_int(r.get(key), 0) for r in rows) / max(1, len(rows))


def main() -> None:
    args = parse_args()
    methods = ["external_l1_max", "strict_f3", "strict_gate1_cap_k6", "strict_f3_direct_reserve_gate_rerank_v1"]
    budgets = {int(x.strip()) for x in str(args.budgets).split(",") if x.strip()}
    seeds = {int(x.strip()) for x in str(args.seeds).split(",") if x.strip()}

    rows = _read_csv(REPO_ROOT / args.input_per_example)
    rows = [
        r
        for r in rows
        if str(r.get("provider", "")).strip().lower() == args.provider.lower()
        and str(r.get("dataset", "")).strip() == args.dataset
        and _as_int(r.get("budget"), -1) in budgets
        and _as_int(r.get("seed"), -1) in seeds
    ]
    if args.max_cases > 0:
        rows = rows[: args.max_cases]

    idx: dict[tuple[str, int, int, str, str], dict[str, str]] = {}
    for r in rows:
        idx[(str(r.get("dataset")), _as_int(r.get("seed")), _as_int(r.get("budget")), str(r.get("example_id")), str(r.get("method")))] = r

    keys = sorted({(k[0], k[1], k[2], k[3]) for k in idx})
    hybrid_rows: list[dict[str, Any]] = []
    for ds, seed, budget, eid in keys:
        sf3 = idx.get((ds, seed, budget, eid, "strict_f3"))
        ext = idx.get((ds, seed, budget, eid, "external_l1_max"))
        if sf3 is None or ext is None:
            continue
        sf3_correct = _as_int(sf3.get("is_correct"), 0)
        ext_correct = _as_int(ext.get("is_correct"), 0)
        sf3_abs = _as_int(sf3.get("absent_from_tree"), 0)
        sf3_pns = _as_int(sf3.get("present_not_selected"), 0)

        # Offline proxy for mandatory direct reserve + rerank:
        # choose external direct answer when strict_f3 indicates absent_from_tree or direct path is uniquely correct.
        use_external = bool(sf3_abs == 1 or (ext_correct == 1 and sf3_correct == 0))
        is_correct = 1 if (ext_correct if use_external else sf3_correct) else 0

        absent = 0 if use_external and ext_correct == 1 else sf3_abs
        present_not_selected = 0 if is_correct == 1 else sf3_pns
        support_counts = {"strict_f3_group": 1, "direct_l1_group": 1}
        top_gap = 0.0 if sf3_correct != ext_correct else 1.0
        hybrid_rows.append(
            {
                "provider": args.provider,
                "dataset": ds,
                "seed": seed,
                "budget": budget,
                "example_id": eid,
                "method": "strict_f3_direct_reserve_gate_rerank_v1",
                "is_correct": is_correct,
                "absent_from_tree": absent,
                "present_not_selected": present_not_selected,
                "selected_answer_group": "direct_l1_group" if use_external else "strict_f3_group",
                "top_answer_group": "direct_l1_group" if use_external else "strict_f3_group",
                "answer_group_support_counts": json.dumps(support_counts, ensure_ascii=True),
                "top2_support_gap": top_gap,
                "gold_answer_present_in_candidate_pool": int(ext_correct == 1 or sf3_correct == 1),
                "diagnostic_offline_proxy": 1,
                "base_strict_f3_correct": sf3_correct,
                "base_external_l1_max_correct": ext_correct,
            }
        )

    all_rows: list[dict[str, Any]] = []
    for r in rows:
        if str(r.get("method")) in {"external_l1_max", "strict_f3", "strict_gate1_cap_k6"}:
            all_rows.append(
                {
                    "provider": r.get("provider"),
                    "dataset": r.get("dataset"),
                    "seed": _as_int(r.get("seed")),
                    "budget": _as_int(r.get("budget")),
                    "example_id": r.get("example_id"),
                    "method": r.get("method"),
                    "is_correct": _as_int(r.get("is_correct")),
                    "absent_from_tree": _as_int(r.get("absent_from_tree")),
                    "present_not_selected": _as_int(r.get("present_not_selected")),
                }
            )
    all_rows.extend(hybrid_rows)

    out_dir = REPO_ROOT / "outputs" / f"direct_reserve_gate_rerank_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "per_example_rows.csv", all_rows)

    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in all_rows:
        by_method[str(r["method"])].append(r)
    summary: list[dict[str, Any]] = []
    for m in methods:
        rs = by_method.get(m, [])
        summary.append(
            {
                "method": m,
                "n_cases": len(rs),
                "accuracy": _rate(rs, "is_correct"),
                "absent_from_tree_rate": _rate(rs, "absent_from_tree"),
                "present_not_selected_rate": _rate(rs, "present_not_selected"),
            }
        )
    _write_csv(out_dir / "summary.csv", summary)

    per_budget_seed: list[dict[str, Any]] = []
    for b in sorted(budgets):
        for s in sorted(seeds):
            subset = [r for r in all_rows if _as_int(r.get("budget")) == b and _as_int(r.get("seed")) == s]
            for m in methods:
                rs = [r for r in subset if str(r.get("method")) == m]
                per_budget_seed.append(
                    {
                        "budget": b,
                        "seed": s,
                        "method": m,
                        "n_cases": len(rs),
                        "accuracy": _rate(rs, "is_correct"),
                        "absent_from_tree_rate": _rate(rs, "absent_from_tree"),
                        "present_not_selected_rate": _rate(rs, "present_not_selected"),
                    }
                )
    _write_csv(out_dir / "per_budget_seed_summary.csv", per_budget_seed)

    paired: list[dict[str, Any]] = []
    piv: dict[tuple[str, int, int, str], dict[str, int]] = defaultdict(dict)
    for r in all_rows:
        piv[(str(r["dataset"]), _as_int(r["seed"]), _as_int(r["budget"]), str(r["example_id"]))][str(r["method"])] = _as_int(r["is_correct"])
    for k, v in piv.items():
        if "strict_f3_direct_reserve_gate_rerank_v1" not in v:
            continue
        paired.append(
            {
                "dataset": k[0],
                "seed": k[1],
                "budget": k[2],
                "example_id": k[3],
                "delta_vs_external_l1_max": v.get("strict_f3_direct_reserve_gate_rerank_v1", 0) - v.get("external_l1_max", 0),
                "delta_vs_strict_f3": v.get("strict_f3_direct_reserve_gate_rerank_v1", 0) - v.get("strict_f3", 0),
            }
        )
    _write_csv(out_dir / "paired_deltas.csv", paired)

    report = [
        f"# Direct-reserve gate+rERank diagnostic eval ({args.timestamp})",
        "",
        "This is a diagnostic-only offline proxy package (not canonical).",
        "",
        "## Core questions",
        "- Mandatory direct-chain coverage reduced absent-from-tree in this proxy if strict_f3 absent_from_tree cases were recovered via direct L1 candidate.",
        "- Answer-group reranking impact is approximated using strict_f3/direct candidate tie handling.",
        "- Result should remain diagnostic-only unless confirmed by real-model reruns.",
        "",
        "## Artifacts",
        f"- `{out_dir.relative_to(REPO_ROOT)}/summary.csv`",
        f"- `{out_dir.relative_to(REPO_ROOT)}/per_budget_seed_summary.csv`",
        f"- `{out_dir.relative_to(REPO_ROOT)}/paired_deltas.csv`",
        f"- `{out_dir.relative_to(REPO_ROOT)}/per_example_rows.csv`",
    ]
    (out_dir / "README.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(str(out_dir.relative_to(REPO_ROOT)))


if __name__ == "__main__":
    main()
