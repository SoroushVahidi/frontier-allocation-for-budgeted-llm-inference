#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
NEAR_DIRECT_DIR = REPO_ROOT / "outputs" / "near_direct_reserve_frontier_gate_failure_slice_20260426T223900Z"
V1_DIAG_DIR = REPO_ROOT / "outputs" / "direct_reserve_frontier_gate_failure_slice_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN_DIAGNOSTIC_ACTUAL"
OVERRIDE_AUDIT_DIR = REPO_ROOT / "outputs" / "direct_reserve_frontier_gate_override_audit_20260426T220757Z"


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _load_features() -> list[dict[str, Any]]:
    near_rows = _read_csv(NEAR_DIRECT_DIR / "per_case_results.csv")
    audit_rows = _read_csv(OVERRIDE_AUDIT_DIR / "override_case_report.csv")
    audit_by_key = {(r["example_id"], r["seed"], r["budget"]): r for r in audit_rows}
    v1_rows = _read_csv(V1_DIAG_DIR / "per_case_results.csv")
    v1_by_key = {(r["example_id"], r["seed"], r["budget"]): r for r in v1_rows}
    features: list[dict[str, Any]] = []
    for row in near_rows:
        key = (row["example_id"], row["seed"], row["budget"])
        audit = audit_by_key.get(key, {})
        v1 = v1_by_key.get(key, {})
        features.append(
            {
                **row,
                "v1_override": _as_int(v1.get("frontier_override_triggered", 0)),
                "frontier_support": _as_int(audit.get("frontier_support", 0)),
                "frontier_candidate_family_count": _as_int(audit.get("frontier_candidate_family_count", 0)),
                "support_margin": _as_float(audit.get("support_margin", 0.0)),
                "maturity_margin": _as_float(audit.get("maturity_margin", 0.0)),
                "incumbent_seen_in_frontier_support": _as_int(audit.get("external_prediction_support_in_pool", 0)) > 0,
                "frontier_disagrees_with_incumbent": str(row.get("frontier_candidate_answer", "")) != str(row.get("protected_incumbent_answer", "")),
                "artifact_sensitive": _as_int(row.get("artifact_sensitive_helpful_case", 0)),
            }
        )
    return features


def _evaluate_rule(features: list[dict[str, Any]], cfg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    correct = clean_correct = overrides = helpful = harmful = clean_helpful = clean_harmful = 0
    preserved = harmed = artifact_helpful = escalations = 0
    for row in features:
        external_ok = _as_int(row["external_l1_max_correct"])
        v1_override = _as_int(row["v1_override"])
        artifact = _as_int(row["artifact_sensitive"])
        allow = bool(v1_override)
        reasons: list[str] = []
        if cfg["block_incumbent_seen"] and row["incumbent_seen_in_frontier_support"]:
            allow = False
            reasons.append("incumbent_seen")
        if row["frontier_support"] < cfg["frontier_support_min"]:
            allow = False
            reasons.append("frontier_support")
        if row["frontier_candidate_family_count"] < cfg["frontier_family_count_min"]:
            allow = False
            reasons.append("family_count")
        if row["support_margin"] < cfg["support_margin_min"]:
            allow = False
            reasons.append("support_margin")
        if row["maturity_margin"] < cfg["maturity_margin_min"]:
            allow = False
            reasons.append("maturity_margin")
        if cfg["require_frontier_disagreement"] and not row["frontier_disagrees_with_incumbent"]:
            allow = False
            reasons.append("frontier_agrees")
        if cfg["exclude_artifact_sensitive"] and artifact:
            allow = False
            reasons.append("artifact_sensitive")
        if cfg["require_verifier_margin"]:
            allow = False
            reasons.append("verifier_margin_missing")

        pred_ok = _as_int(row["near_direct_reserve_frontier_gate_v1_correct"]) if allow else external_ok
        clean_pred_ok = external_ok if (allow and artifact) else pred_ok
        correct += pred_ok
        clean_correct += clean_pred_ok
        overrides += int(allow)
        helpful += int(allow and not external_ok and pred_ok)
        harmful += int(allow and external_ok and not pred_ok)
        clean_helpful += int(allow and not external_ok and clean_pred_ok and not artifact)
        clean_harmful += int(allow and external_ok and not clean_pred_ok)
        preserved += int(external_ok and pred_ok)
        harmed += int(external_ok and not pred_ok)
        artifact_helpful += int(allow and artifact and not external_ok and pred_ok)
        escalations += int(v1_override)
        decisions.append(
            {
                "example_id": row["example_id"],
                "seed": row["seed"],
                "budget": row["budget"],
                "rule_name": cfg["rule_name"],
                "v1_override": v1_override,
                "calibrated_override": int(allow),
                "decision_reason": "allow" if allow else (";".join(reasons) or "no_v1_override"),
                "external_l1_max_correct": external_ok,
                "calibrated_correct_reported": pred_ok,
                "calibrated_correct_clean": clean_pred_ok,
                "artifact_sensitive": artifact,
            }
        )
    n = len(features)
    metrics = {
        **cfg,
        "external_l1_max_accuracy": sum(_as_int(r["external_l1_max_correct"]) for r in features) / n,
        "strict_f3_accuracy": sum(_as_int(r["strict_f3_correct"]) for r in features) / n,
        "near_direct_reserve_frontier_gate_v1_accuracy": sum(_as_int(r["near_direct_reserve_frontier_gate_v1_correct"]) for r in features) / n,
        "calibrated_near_direct_frontier_gate_v1_reported_accuracy": correct / n,
        "calibrated_near_direct_frontier_gate_v1_clean_accuracy_excluding_artifact": clean_correct / n,
        "escalation_rate": escalations / n,
        "override_rate": overrides / n,
        "helpful_overrides": helpful,
        "harmful_overrides": harmful,
        "clean_helpful_overrides": clean_helpful,
        "clean_harmful_overrides": clean_harmful,
        "direct_solved_preserved": preserved,
        "direct_solved_harmed": harmed,
        "artifact_sensitive_helpful_count": artifact_helpful,
        "improves_over_external_l1_max_reported": int((correct / n) > (sum(_as_int(r["external_l1_max_correct"]) for r in features) / n)),
        "improves_over_external_l1_max_clean": int((clean_correct / n) > (sum(_as_int(r["external_l1_max_correct"]) for r in features) / n)),
        "larger_real_model_pilot_justified": "no",
    }
    return metrics, decisions


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline calibrated near-direct gate threshold sweep.")
    ap.add_argument("--timestamp", default=_now_ts())
    args = ap.parse_args()
    out_dir = REPO_ROOT / "outputs" / f"calibrated_near_direct_gate_sweep_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    sweep: list[dict[str, Any]] = []
    decisions_all: list[dict[str, Any]] = []
    for fs, ff, sm, mm, block, exclude_artifact, disagree, verifier in product(
        [2, 3], [1, 2], [1, 2], [1, 2], [False, True], [False, True], [False, True], [False]
    ):
        cfg = {
            "rule_name": f"fs{fs}_ff{ff}_sm{sm}_mm{mm}_block{int(block)}_artifact{int(exclude_artifact)}_disagree{int(disagree)}",
            "frontier_support_min": fs,
            "frontier_family_count_min": ff,
            "support_margin_min": sm,
            "maturity_margin_min": mm,
            "block_incumbent_seen": block,
            "exclude_artifact_sensitive": exclude_artifact,
            "require_frontier_disagreement": disagree,
            "require_verifier_margin": verifier,
        }
        metrics, decisions = _evaluate_rule(features, cfg)
        sweep.append(metrics)
        decisions_all.extend(decisions)
    # Prefer clean, non-artifact improvement; otherwise pick the safest no-harm rule.
    ranked = sorted(
        sweep,
        key=lambda r: (
            int(r["improves_over_external_l1_max_clean"]),
            float(r["calibrated_near_direct_frontier_gate_v1_clean_accuracy_excluding_artifact"]),
            -int(r["harmful_overrides"]),
            -int(r["artifact_sensitive_helpful_count"]),
            -float(r["override_rate"]),
            int(r["block_incumbent_seen"]),
            int(r["exclude_artifact_sensitive"]),
            float(r["calibrated_near_direct_frontier_gate_v1_reported_accuracy"]),
        ),
        reverse=True,
    )
    recommended = ranked[0]
    recommended["larger_real_model_pilot_justified"] = "no"
    _write_csv(out_dir / "threshold_sweep.csv", sweep)
    _write_csv(out_dir / "per_case_decisions.csv", decisions_all)
    artifact_rows = [
        {
            "metric": "artifact_sensitive_helpful_cases",
            "count": sum(_as_int(r["artifact_sensitive"]) for r in features),
            "impact": "reported gains depend on output repair if this count is the only helpful override",
        },
        {
            "metric": "recommended_clean_improves_over_external_l1_max",
            "count": recommended["improves_over_external_l1_max_clean"],
            "impact": "pilot remains unjustified unless this is 1",
        },
    ]
    _write_csv(out_dir / "artifact_sensitivity_report.csv", artifact_rows)
    (out_dir / "recommended_rule.json").write_text(json.dumps(recommended, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(
        "# Calibrated Near-Direct Frontier Gate Sweep\n\n"
        "- Diagnostic-only; not canonical; not manuscript-ready.\n"
        "- No real API calls were made.\n"
        f"- Recommended rule: `{recommended['rule_name']}`\n"
        f"- Reported accuracy: {recommended['calibrated_near_direct_frontier_gate_v1_reported_accuracy']:.4f}\n"
        f"- Clean accuracy excluding artifact-sensitive benefit: {recommended['calibrated_near_direct_frontier_gate_v1_clean_accuracy_excluding_artifact']:.4f}\n"
        f"- Clean improvement over `external_l1_max`: {recommended['improves_over_external_l1_max_clean']}\n"
        "- A fresh real-model pilot is not justified because clean non-artifact improvement was not established.\n",
        encoding="utf-8",
    )
    (REPO_ROOT / "docs" / "CALIBRATED_NEAR_DIRECT_FRONTIER_GATE_STATUS.md").write_text(
        "# CALIBRATED_NEAR_DIRECT_FRONTIER_GATE_STATUS\n\n"
        f"- Output directory: `{out_dir.relative_to(REPO_ROOT)}`\n"
        "- Variant: `calibrated_near_direct_frontier_gate_v1`\n"
        "- Status: diagnostic-only; not canonical; not manuscript-ready unless clean non-artifact improvement is found.\n"
        "- Real API calls made: no.\n"
        f"- Recommended rule: `{recommended['rule_name']}`\n"
        f"- `external_l1_max` accuracy: {recommended['external_l1_max_accuracy']:.4f}\n"
        f"- `strict_f3` accuracy: {recommended['strict_f3_accuracy']:.4f}\n"
        f"- near-direct reported accuracy: {recommended['near_direct_reserve_frontier_gate_v1_accuracy']:.4f}\n"
        f"- calibrated reported accuracy: {recommended['calibrated_near_direct_frontier_gate_v1_reported_accuracy']:.4f}\n"
        f"- calibrated clean accuracy excluding artifact: {recommended['calibrated_near_direct_frontier_gate_v1_clean_accuracy_excluding_artifact']:.4f}\n"
        f"- Improves over `external_l1_max` reported: {recommended['improves_over_external_l1_max_reported']}\n"
        f"- Improves over `external_l1_max` clean: {recommended['improves_over_external_l1_max_clean']}\n"
        "- Fresh real-model pilot justified: no.\n\n"
        "Interpretation: do not edit the manuscript or promote this controller. The saved-trace sweep does not establish clean non-artifact improvement.\n",
        encoding="utf-8",
    )
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
