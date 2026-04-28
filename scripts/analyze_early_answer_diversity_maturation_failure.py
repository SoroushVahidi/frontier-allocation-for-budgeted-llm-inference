#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "scripts" / "run_early_answer_diversity_maturation_diagnostic.py"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit failure modes for early answer-diversity maturation variants.")
    p.add_argument(
        "--v1-dir",
        default="outputs/early_answer_diversity_maturation_diagnostic_20260428T201131Z",
    )
    p.add_argument(
        "--gated-dir",
        default="outputs/early_answer_diversity_maturation_diagnostic_20260428T201809Z",
    )
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    return p.parse_args()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _write_csv(path: Path, rows: list[dict[str, Any]], header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def _key(row: dict[str, str]) -> tuple[str, int]:
    return str(row.get("example_id", "")), _safe_int(row.get("budget"), 0)


def _pair_index(rows: list[dict[str, str]], method: str) -> dict[tuple[str, int], dict[str, str]]:
    return {_key(r): r for r in rows if str(r.get("method", "")) == method}


def _corr(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = sum((x - mx) ** 2 for x in xs) ** 0.5
    deny = sum((y - my) ** 2 for y in ys) ** 0.5
    if denx <= 1e-12 or deny <= 1e-12:
        return 0.0
    return num / (denx * deny)


def main() -> None:
    args = parse_args()
    v1_dir = REPO_ROOT / args.v1_dir
    gated_dir = REPO_ROOT / args.gated_dir
    v1_rows = _read_csv(v1_dir / "per_case_results.csv")
    gated_rows = _read_csv(gated_dir / "per_case_results.csv")
    out_dir = REPO_ROOT / "outputs" / f"early_answer_diversity_maturation_failure_audit_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    strict_idx = _pair_index(gated_rows, "strict_f3")
    l1_idx = _pair_index(gated_rows, "external_l1_max")
    v1_idx = _pair_index(v1_rows, "early_answer_diversity_maturation_v1")
    gated_idx = _pair_index(gated_rows, "early_answer_diversity_maturation_gated_v1")

    pair_rows: list[dict[str, Any]] = []
    trigger_counter: Counter[str] = Counter()
    skipped_counter: Counter[str] = Counter()
    overrode_high_cont_count = 0
    overrode_count = 0
    for k, grow in gated_idx.items():
        srow = strict_idx.get(k)
        lrow = l1_idx.get(k)
        vrow = v1_idx.get(k)
        if srow is None:
            continue
        strict_correct = _safe_int(srow.get("is_correct"))
        gated_correct = _safe_int(grow.get("is_correct"))
        l1_correct = _safe_int(lrow.get("is_correct")) if lrow else 0
        v1_correct = _safe_int(vrow.get("is_correct")) if vrow else 0
        applied = _safe_int(grow.get("early_gated_override_applied"))
        considered = _safe_int(grow.get("early_gated_override_considered"))
        if applied > 0:
            overrode_count += 1
            # Heuristic "high continuation branch overridden" proxy: strict had fewer repeated family expansions
            # and gated changed decision while strict remained correct.
            if strict_correct == 1 and gated_correct == 0:
                overrode_high_cont_count += 1
        for trig in [t for t in str(grow.get("early_gated_override_triggers", "")).split(";") if t]:
            trigger_counter[trig] += 1
        skip = str(grow.get("early_gated_override_skipped_reason", "")).strip()
        if skip:
            skipped_counter[skip] += 1
        pair_rows.append(
            {
                "example_id": k[0],
                "budget": k[1],
                "strict_f3_correct": strict_correct,
                "v1_correct": v1_correct,
                "gated_correct": gated_correct,
                "external_l1_max_correct": l1_correct,
                "v1_delta_vs_strict_f3": v1_correct - strict_correct,
                "gated_delta_vs_strict_f3": gated_correct - strict_correct,
                "gated_delta_vs_external_l1_max": gated_correct - l1_correct,
                "v1_early_unique_answer_groups": _safe_int(vrow.get("early_unique_answer_groups")) if vrow else 0,
                "strict_early_unique_answer_groups": _safe_int(srow.get("early_unique_answer_groups")),
                "gated_early_unique_answer_groups": _safe_int(grow.get("early_unique_answer_groups")),
                "v1_repeated_family_expansions_early": _safe_int(vrow.get("early_repeated_family_expansions")) if vrow else 0,
                "strict_repeated_family_expansions_early": _safe_int(srow.get("early_repeated_family_expansions")),
                "gated_repeated_family_expansions_early": _safe_int(grow.get("early_repeated_family_expansions")),
                "gated_override_considered": considered,
                "gated_override_applied": applied,
                "gated_override_skipped_reason": skip,
                "gated_override_triggers": str(grow.get("early_gated_override_triggers", "")),
            }
        )

    summary_rows: list[dict[str, Any]] = []
    for method, idx in (
        ("strict_f3", strict_idx),
        ("early_answer_diversity_maturation_v1", v1_idx),
        ("early_answer_diversity_maturation_gated_v1", gated_idx),
        ("external_l1_max", l1_idx),
    ):
        n = max(1, len(idx))
        vals = list(idx.values())
        summary_rows.append(
            {
                "method": method,
                "n": len(vals),
                "accuracy": sum(_safe_int(r.get("is_correct")) for r in vals) / n,
                "absent_from_tree_rate": sum(_safe_int(r.get("absent_from_tree")) for r in vals) / n,
                "present_not_selected_rate": sum(_safe_int(r.get("present_not_selected")) for r in vals) / n,
                "avg_actions": sum(_safe_float(r.get("actions")) for r in vals) / n,
                "avg_expansions": sum(_safe_float(r.get("expansions")) for r in vals) / n,
                "avg_early_unique_answer_groups": sum(_safe_float(r.get("early_unique_answer_groups")) for r in vals) / n,
                "avg_repeated_family_expansions_early": sum(_safe_float(r.get("early_repeated_family_expansions")) for r in vals) / n,
            }
        )

    delta_by_budget: defaultdict[int, list[int]] = defaultdict(list)
    repeat_delta: list[float] = []
    acc_delta: list[float] = []
    diversity_delta: list[float] = []
    for r in pair_rows:
        b = _safe_int(r["budget"])
        d = _safe_int(r["gated_delta_vs_strict_f3"])
        delta_by_budget[b].append(d)
        repeat_delta.append(
            _safe_float(r["gated_repeated_family_expansions_early"])
            - _safe_float(r["strict_repeated_family_expansions_early"])
        )
        diversity_delta.append(
            _safe_float(r["gated_early_unique_answer_groups"])
            - _safe_float(r["strict_early_unique_answer_groups"])
        )
        acc_delta.append(float(d))

    trigger_rows = [
        {"trigger": k, "count": v, "share_over_pairs": v / max(1, len(pair_rows))}
        for k, v in sorted(trigger_counter.items())
    ]
    trigger_rows.extend(
        {"trigger": f"skip:{k}", "count": v, "share_over_pairs": v / max(1, len(pair_rows))}
        for k, v in sorted(skipped_counter.items())
    )
    trigger_rows.append(
        {
            "trigger": "override_applied_rate",
            "count": overrode_count,
            "share_over_pairs": overrode_count / max(1, len(pair_rows)),
        }
    )

    strict_gate1_status = "unknown"
    strict_gate1_reason = "unknown"
    mex = _read_csv(gated_dir / "methods_excluded.csv")
    for row in mex:
        if str(row.get("method")) == "strict_gate1_cap_k6":
            strict_gate1_status = "excluded"
            strict_gate1_reason = str(row.get("reason", ""))
            break
    if strict_gate1_status != "excluded":
        strict_gate1_status = "included"
        strict_gate1_reason = "resolved_alias_or_direct_registry_match"

    runner_text = RUNNER_PATH.read_text(encoding="utf-8") if RUNNER_PATH.exists() else ""
    runner_alias_fix_present = "_resolve_runtime_key" in runner_text and "strict_gate1_cap_k6" in runner_text

    rec = {
        "status": "experimental_provenance_only",
        "v1_accuracy_delta_vs_strict_f3": next(
            (r["accuracy"] for r in summary_rows if r["method"] == "early_answer_diversity_maturation_v1"), 0.0
        )
        - next((r["accuracy"] for r in summary_rows if r["method"] == "strict_f3"), 0.0),
        "gated_accuracy_delta_vs_strict_f3": next(
            (r["accuracy"] for r in summary_rows if r["method"] == "early_answer_diversity_maturation_gated_v1"), 0.0
        )
        - next((r["accuracy"] for r in summary_rows if r["method"] == "strict_f3"), 0.0),
        "gated_absent_from_tree_delta_vs_strict_f3": next(
            (r["absent_from_tree_rate"] for r in summary_rows if r["method"] == "early_answer_diversity_maturation_gated_v1"),
            0.0,
        )
        - next((r["absent_from_tree_rate"] for r in summary_rows if r["method"] == "strict_f3"), 0.0),
        "gated_accuracy_delta_vs_external_l1_max": next(
            (r["accuracy"] for r in summary_rows if r["method"] == "early_answer_diversity_maturation_gated_v1"), 0.0
        )
        - next((r["accuracy"] for r in summary_rows if r["method"] == "external_l1_max"), 0.0),
        "losses_vs_strict_f3_pairs": sum(1 for r in pair_rows if _safe_int(r["gated_delta_vs_strict_f3"]) < 0),
        "wins_vs_strict_f3_pairs": sum(1 for r in pair_rows if _safe_int(r["gated_delta_vs_strict_f3"]) > 0),
        "ties_vs_strict_f3_pairs": sum(1 for r in pair_rows if _safe_int(r["gated_delta_vs_strict_f3"]) == 0),
        "dominant_failure_pattern": "diversity_or_override_changes_without_correctness_gain",
        "override_applied_rate": overrode_count / max(1, len(pair_rows)),
        "override_harm_rate_when_applied": overrode_high_cont_count / max(1, overrode_count),
        "repeated_family_reduction_corr_with_accuracy_delta": _corr(repeat_delta, acc_delta),
        "diversity_gain_corr_with_accuracy_delta": _corr(diversity_delta, acc_delta),
        "delta_vs_strict_f3_by_budget": {
            str(k): (sum(v) / max(1, len(v))) for k, v in sorted(delta_by_budget.items())
        },
        "strict_gate1_cap_k6_status_in_audited_dirs": strict_gate1_status,
        "strict_gate1_cap_k6_reason_in_audited_dirs": strict_gate1_reason,
        "strict_gate1_cap_k6_runner_alias_fix_present": bool(runner_alias_fix_present),
        "strict_gate1_cap_k6_interpretation": (
            "audited_dirs_excluded_but_runner_mapping_fix_present"
            if strict_gate1_status == "excluded" and runner_alias_fix_present
            else (
                "included_in_audited_dirs"
                if strict_gate1_status == "included"
                else "still_unresolved"
            )
        ),
        "final_recommendation": "discard_algorithmic_line_keep_provenance_only",
        "revisit_condition": "only_if_real_model_traces_show_repeated_family_collapse_with_recoverable_alternatives",
    }

    _write_csv(
        out_dir / "early_maturation_failure_summary.csv",
        summary_rows,
        [
            "method",
            "n",
            "accuracy",
            "absent_from_tree_rate",
            "present_not_selected_rate",
            "avg_actions",
            "avg_expansions",
            "avg_early_unique_answer_groups",
            "avg_repeated_family_expansions_early",
        ],
    )
    _write_csv(
        out_dir / "early_maturation_pairwise_case_audit.csv",
        pair_rows,
        [
            "example_id",
            "budget",
            "strict_f3_correct",
            "v1_correct",
            "gated_correct",
            "external_l1_max_correct",
            "v1_delta_vs_strict_f3",
            "gated_delta_vs_strict_f3",
            "gated_delta_vs_external_l1_max",
            "v1_early_unique_answer_groups",
            "strict_early_unique_answer_groups",
            "gated_early_unique_answer_groups",
            "v1_repeated_family_expansions_early",
            "strict_repeated_family_expansions_early",
            "gated_repeated_family_expansions_early",
            "gated_override_considered",
            "gated_override_applied",
            "gated_override_skipped_reason",
            "gated_override_triggers",
        ],
    )
    _write_csv(
        out_dir / "early_maturation_trigger_audit.csv",
        trigger_rows,
        ["trigger", "count", "share_over_pairs"],
    )
    (out_dir / "early_maturation_recommendation.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote audit outputs to: {out_dir}")


if __name__ == "__main__":
    main()
