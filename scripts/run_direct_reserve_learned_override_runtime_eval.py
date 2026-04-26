#!/usr/bin/env python3
"""Summarize tiny real runtime validation for the direct-reserve learned override."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE_METHOD = "direct_reserve_strong_plus_diverse_v1"
LEARNED_METHOD = "direct_reserve_strong_plus_diverse_learned_override_v1"


def _path(text: str | Path) -> Path:
    p = Path(text)
    return p if p.is_absolute() else REPO_ROOT / p


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({key: row.get(key, "") for key in fields})


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _key(row: dict[str, Any]) -> tuple[str, int, int]:
    return (str(row.get("example_id", "")), _as_int(row.get("seed", 0)), _as_int(row.get("budget", 0)))


def _candidate_json(rows: list[dict[str, str]]) -> str:
    vals = [
        {
            "branch_id": r.get("branch_id", ""),
            "answer": r.get("predicted_answer", ""),
            "normalized_answer": r.get("normalized_candidate_answer", ""),
            "answer_group": r.get("answer_group", ""),
            "selected": _as_int(r.get("is_selected", 0)),
            "source": r.get("branch_prompt_style", ""),
        }
        for r in rows
    ]
    return json.dumps(vals, ensure_ascii=False, sort_keys=True)


def _groups_json(rows: list[dict[str, str]]) -> str:
    vals = [
        {
            "answer_group": r.get("answer_group", ""),
            "support": _as_int(r.get("support", 0)),
            "is_gold_group": _as_int(r.get("is_gold_group", 0)),
            "is_selected_group": _as_int(r.get("is_selected_group", 0)),
        }
        for r in rows
    ]
    return json.dumps(vals, ensure_ascii=False, sort_keys=True)


def _missing_fallback(row: dict[str, str]) -> bool:
    reason = str(row.get("learned_override_reason", "")).strip()
    missing = str(row.get("learned_override_missing_features", "")).strip()
    return bool(missing) or reason in {"model_missing", "missing_required_features"} or reason.startswith("model_load_error:")


def build_eval(validation_dir: Path, out_dir: Path, plan_dir: Path | None) -> dict[str, Any]:
    per_case = _read_csv(validation_dir / "per_case_method_results.csv")
    candidates = _read_csv(validation_dir / "candidate_branch_table.csv")
    groups = _read_csv(validation_dir / "answer_group_summary.csv")
    coverage = _read_csv(validation_dir / "coverage_summary.csv")
    overlap = _read_csv(plan_dir / "overlap_report.csv") if plan_dir else []

    base = {_key(r): r for r in per_case if r.get("method") == BASE_METHOD}
    learned = {_key(r): r for r in per_case if r.get("method") == LEARNED_METHOD}
    cand_by: dict[tuple[str, int, int, str], list[dict[str, str]]] = {}
    for r in candidates:
        cand_by.setdefault((*_key(r), str(r.get("method", ""))), []).append(r)
    group_by: dict[tuple[str, int, int, str], list[dict[str, str]]] = {}
    for r in groups:
        group_by.setdefault((*_key(r), str(r.get("method", ""))), []).append(r)

    comparison: list[dict[str, Any]] = []
    for key in sorted(set(base) | set(learned)):
        b = base.get(key, {})
        l = learned.get(key, {})
        base_ok = _as_int(b.get("gold_selected", b.get("is_correct", 0)))
        learned_ok = _as_int(l.get("gold_selected", l.get("is_correct", 0)))
        triggered = _as_int(l.get("learned_override_triggered", 0))
        available = _as_int(l.get("learned_override_available", 0))
        missing = _missing_fallback(l)
        degradation = int(base_ok == 1 and learned_ok == 0)
        improvement = int(base_ok == 0 and learned_ok == 1)
        selector_degradation = int(triggered == 1 and degradation == 1)
        selector_improvement = int(triggered == 1 and improvement == 1)
        stratum = str(l.get("stratum") or b.get("stratum") or "")
        row = {
            "example_id": key[0],
            "seed": key[1],
            "budget": key[2],
            "question": l.get("question") or b.get("question") or "",
            "stratum": stratum,
            "gold_answer": l.get("gold_answer") or b.get("gold_answer") or "",
            "base_selected_answer": b.get("normalized_selected_answer") or b.get("final_selected_answer") or "",
            "learned_method_selected_answer": l.get("normalized_selected_answer") or l.get("final_selected_answer") or "",
            "runtime_pre_override_answer": l.get("base_selected_answer", ""),
            "learned_selected_answer": l.get("learned_selected_answer", ""),
            "final_selected_answer": l.get("final_selected_answer_after_learned_override") or l.get("normalized_selected_answer") or "",
            "base_selected_gold": base_ok,
            "learned_selected_gold": learned_ok,
            "override_available": available,
            "override_triggered": triggered,
            "override_available_not_triggered": int(available == 1 and triggered == 0),
            "improvement_vs_base": improvement,
            "degradation_vs_base": degradation,
            "selector_triggered_improvement_vs_base": selector_improvement,
            "selector_triggered_degradation_vs_base": selector_degradation,
            "control_degradation": int(degradation and stratum == "control_correct"),
            "selector_triggered_control_degradation": int(selector_degradation and stratum == "control_correct"),
            "missing_feature_or_model_fallback": int(missing),
            "learned_override_margin": _as_float(l.get("learned_override_margin", 0.0)),
            "learned_override_threshold": l.get("learned_override_threshold", ""),
            "learned_override_reason": l.get("learned_override_reason", ""),
            "learned_override_missing_features": l.get("learned_override_missing_features", ""),
            "candidate_answers": _candidate_json(cand_by.get((*key, LEARNED_METHOD), [])),
            "answer_groups": _groups_json(group_by.get((*key, LEARNED_METHOD), [])),
        }
        comparison.append(row)

    n = len(comparison)
    margins = [float(r["learned_override_margin"]) for r in comparison]
    summary = [
        {
            "validation_dir": str(validation_dir),
            "plan_dir": str(plan_dir or ""),
            "n_cases": n,
            "real_api_enabled": coverage[0].get("real_api_enabled", "") if coverage else "",
            "overlap_with_prior_validation_count": max((_as_int(r.get("total_overlap_count", 0)) for r in overlap), default=0),
            "base_selected_gold_count": sum(_as_int(r["base_selected_gold"]) for r in comparison),
            "base_selected_gold_rate": sum(_as_int(r["base_selected_gold"]) for r in comparison) / max(1, n),
            "learned_override_selected_gold_count": sum(_as_int(r["learned_selected_gold"]) for r in comparison),
            "learned_override_selected_gold_rate": sum(_as_int(r["learned_selected_gold"]) for r in comparison) / max(1, n),
            "override_available_count": sum(_as_int(r["override_available"]) for r in comparison),
            "override_count": sum(_as_int(r["override_triggered"]) for r in comparison),
            "improvement_count": sum(_as_int(r["improvement_vs_base"]) for r in comparison),
            "degradation_count": sum(_as_int(r["degradation_vs_base"]) for r in comparison),
            "selector_triggered_improvement_count": sum(_as_int(r["selector_triggered_improvement_vs_base"]) for r in comparison),
            "selector_triggered_degradation_count": sum(_as_int(r["selector_triggered_degradation_vs_base"]) for r in comparison),
            "control_degradation_count": sum(_as_int(r["control_degradation"]) for r in comparison),
            "selector_triggered_control_degradation_count": sum(_as_int(r["selector_triggered_control_degradation"]) for r in comparison),
            "override_available_not_triggered_count": sum(_as_int(r["override_available_not_triggered"]) for r in comparison),
            "missing_feature_or_model_fallback_count": sum(_as_int(r["missing_feature_or_model_fallback"]) for r in comparison),
            "learned_override_margin_min": min(margins) if margins else 0.0,
            "learned_override_margin_mean": sum(margins) / max(1, len(margins)),
            "learned_override_margin_max": max(margins) if margins else 0.0,
            "learned_override_reasons": json.dumps(Counter(str(r["learned_override_reason"]) for r in comparison), sort_keys=True),
        }
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "summary.csv", summary)
    _write_csv(out_dir / "per_case_comparison.csv", comparison)
    _write_csv(out_dir / "override_cases.csv", [r for r in comparison if _as_int(r["override_triggered"]) == 1])
    _write_csv(out_dir / "improvement_cases.csv", [r for r in comparison if _as_int(r["improvement_vs_base"]) == 1])
    _write_csv(out_dir / "degradation_cases.csv", [r for r in comparison if _as_int(r["degradation_vs_base"]) == 1])
    _write_csv(out_dir / "control_degradation_cases.csv", [r for r in comparison if _as_int(r["control_degradation"]) == 1])
    _write_csv(out_dir / "missing_feature_cases.csv", [r for r in comparison if _as_int(r["missing_feature_or_model_fallback"]) == 1])
    _write_csv(out_dir / "available_not_triggered_cases.csv", [r for r in comparison if _as_int(r["override_available_not_triggered"]) == 1])
    (out_dir / "README.md").write_text(
        "# Direct-reserve learned override runtime evaluation\n\n"
        "Diagnostic-only comparison of `direct_reserve_strong_plus_diverse_v1` and "
        "`direct_reserve_strong_plus_diverse_learned_override_v1` on the tiny real Cohere run.\n",
        encoding="utf-8",
    )
    return summary[0]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--validation-dir", required=True)
    p.add_argument("--plan-dir", default="")
    p.add_argument("--output-dir", default="")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    validation_dir = _path(args.validation_dir)
    plan_dir = _path(args.plan_dir) if args.plan_dir else None
    out_dir = _path(args.output_dir) if args.output_dir else REPO_ROOT / "outputs" / f"direct_reserve_learned_override_runtime_eval_{args.timestamp}"
    summary = build_eval(validation_dir=validation_dir, out_dir=out_dir, plan_dir=plan_dir)
    print(
        f"Wrote {out_dir} "
        f"base={summary['base_selected_gold_rate']:.3f} "
        f"learned={summary['learned_override_selected_gold_rate']:.3f} "
        f"overrides={summary['override_count']} "
        f"degradations={summary['degradation_count']}"
    )


if __name__ == "__main__":
    main()
