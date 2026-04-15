#!/usr/bin/env python3
"""Build a selective-distillation-ready dataset from oracle ACT-vs-STOP labels.

This is a lightweight preprocessing scaffold:
- consumes contract-compliant oracle label rows,
- assigns accepted / borderline / rejected buckets by configurable policy,
- emits distillation-ready JSONL rows with hard + soft targets and sample weights,
- records summary/provenance without claiming pilot-scale conclusions.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _safe_float(x: Any) -> float | None:
    if x is None:
        return None
    if not _is_number(x):
        return None
    v = float(x)
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _str_or_empty(x: Any) -> str:
    return "" if x is None else str(x)


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _normalize_status(x: Any) -> str:
    return _str_or_empty(x).strip().lower()


def _parse_manifest_markers(manifest: dict[str, Any]) -> tuple[bool, bool]:
    mock_mode = bool(manifest.get("mock_mode", False))
    has_non_oracle_warning = bool(_str_or_empty(manifest.get("non_oracle_warning")))
    return mock_mode, has_non_oracle_warning


def _validate_policy_config(policy_cfg: dict[str, Any]) -> list[str]:
    errs: list[str] = []

    required_sections = ["bucket_policy", "training_treatment", "soft_target", "input_contract"]
    for section in required_sections:
        if section not in policy_cfg:
            errs.append(f"Missing required policy section: {section}")

    training = dict(policy_cfg.get("training_treatment", {}))
    for bucket in ["accepted", "borderline", "rejected"]:
        if bucket not in training:
            errs.append(f"Missing training_treatment.{bucket}")
            continue
        cfg = dict(training.get(bucket, {}))
        for key in ["sample_weight", "hard_loss_weight", "soft_kl_weight", "abstain_target"]:
            val = cfg.get(key)
            if not _is_number(val):
                errs.append(f"training_treatment.{bucket}.{key} must be numeric")

    soft = dict(policy_cfg.get("soft_target", {}))
    temp = soft.get("temperature")
    if not _is_number(temp) or float(temp) <= 0.0:
        errs.append("soft_target.temperature must be > 0")
    clip_min = soft.get("clip_min")
    clip_max = soft.get("clip_max")
    if not _is_number(clip_min) or not _is_number(clip_max):
        errs.append("soft_target.clip_min/clip_max must be numeric")
    elif float(clip_min) >= float(clip_max):
        errs.append("soft_target.clip_min must be < clip_max")

    policy = dict(policy_cfg.get("bucket_policy", {}))
    margin = dict(policy.get("margin_bands", {}))
    accepted_gap = margin.get("accepted_min_abs_gap")
    borderline_gap = margin.get("borderline_min_abs_gap")
    if not _is_number(accepted_gap) or not _is_number(borderline_gap):
        errs.append("bucket_policy.margin_bands accepted/borderline thresholds must be numeric")
    elif float(borderline_gap) > float(accepted_gap):
        errs.append("bucket_policy.margin_bands borderline_min_abs_gap must be <= accepted_min_abs_gap")

    return errs


def _teacher_prob_from_gap(*, gap: float, soft_cfg: dict[str, Any]) -> float:
    method = str(soft_cfg.get("method", "gap_logistic"))
    if method != "gap_logistic":
        raise ValueError(f"Unsupported soft_target.method: {method}")

    temperature = float(soft_cfg.get("temperature", 0.1))
    if temperature <= 0.0:
        raise ValueError("soft_target.temperature must be > 0")

    raw = 1.0 / (1.0 + math.exp(-gap / temperature))
    lo = float(soft_cfg.get("clip_min", 0.001))
    hi = float(soft_cfg.get("clip_max", 0.999))
    return _clip(raw, lo, hi)


def _resolve_margin_thresholds(row: dict[str, Any], policy: dict[str, Any]) -> tuple[float, float, str]:
    margin = dict(policy.get("margin_bands", {}))
    accepted_min = float(margin.get("accepted_min_abs_gap", 0.12))
    borderline_min = float(margin.get("borderline_min_abs_gap", 0.04))
    rule_name = "default"

    remaining_budget = _safe_float(row.get("remaining_budget"))
    if remaining_budget is not None:
        for override in list(policy.get("remaining_budget_region_overrides", [])):
            lo = float(override.get("min_remaining_budget", float("-inf")))
            hi = float(override.get("max_remaining_budget", float("inf")))
            if lo <= remaining_budget <= hi:
                accepted_min = float(override.get("accepted_min_abs_gap", accepted_min))
                borderline_min = float(override.get("borderline_min_abs_gap", borderline_min))
                rule_name = str(override.get("name", "region_override"))
                break

    if borderline_min > accepted_min:
        raise ValueError(
            f"Invalid thresholds: borderline_min_abs_gap ({borderline_min}) > accepted_min_abs_gap ({accepted_min})"
        )

    return accepted_min, borderline_min, rule_name


def _reject_reason_if_any(
    row: dict[str, Any],
    policy: dict[str, Any],
    required_fields: list[str],
    *,
    manifest_mock_mode: bool,
    manifest_non_oracle_warning: bool,
) -> str | None:
    reject_cfg = dict(policy.get("reject_if", {}))
    reject_mock_rows = bool(reject_cfg.get("reject_mock_rows", True))

    missing_required = [f for f in required_fields if f not in row]
    if missing_required:
        return f"missing_required_fields:{','.join(missing_required)}"

    if reject_mock_rows and manifest_mock_mode:
        return "manifest_mock_mode"
    if reject_mock_rows and manifest_non_oracle_warning:
        return "manifest_non_oracle_warning"
    if reject_mock_rows and bool(row.get("mock_interface_only", False)):
        return "mock_interface_only"
    if reject_mock_rows and _str_or_empty(row.get("non_oracle_warning")):
        return "non_oracle_warning_present"

    q_act = _safe_float(row.get("q_act"))
    q_stop = _safe_float(row.get("q_stop"))
    gap = _safe_float(row.get("oracle_action_gap"))
    label = row.get("oracle_label_act")

    if any(x is None for x in [q_act, q_stop, gap]) or label not in {0, 1}:
        return "invalid_core_fields"

    tol = float(policy.get("gap_consistency_tolerance", 1e-6))
    if abs((q_act - q_stop) - gap) > tol:
        return "gap_consistency_fail"

    sign_label = 1 if gap > 0.0 else 0
    if int(label) != sign_label:
        return "label_sign_fail"

    audit_status = _normalize_status(row.get("audit_status"))
    blocked_audit = {str(x).lower() for x in list(reject_cfg.get("blocked_audit_statuses", []))}
    if audit_status and audit_status in blocked_audit:
        return f"blocked_audit_status:{audit_status}"

    quality_status = _normalize_status(row.get("quality_gate_status"))
    blocked_quality = {str(x).lower() for x in list(reject_cfg.get("blocked_quality_statuses", []))}
    if quality_status and quality_status in blocked_quality:
        return f"blocked_quality_status:{quality_status}"

    return None


def _assign_bucket(
    row: dict[str, Any],
    policy: dict[str, Any],
    required_fields: list[str],
    *,
    manifest_mock_mode: bool,
    manifest_non_oracle_warning: bool,
) -> tuple[str, str, dict[str, float | str]]:
    reject_reason = _reject_reason_if_any(
        row,
        policy,
        required_fields,
        manifest_mock_mode=manifest_mock_mode,
        manifest_non_oracle_warning=manifest_non_oracle_warning,
    )
    if reject_reason is not None:
        return "rejected", reject_reason, {}

    gap = float(row["oracle_action_gap"])
    abs_gap = abs(gap)

    accepted_min_gap, borderline_min_gap, threshold_rule = _resolve_margin_thresholds(row, policy)

    agreement_cfg = dict(policy.get("agreement", {}))
    accepted_min_agreement = float(agreement_cfg.get("accepted_min", 0.7))
    borderline_min_agreement = float(agreement_cfg.get("borderline_min", 0.55))
    agreement = _safe_float(row.get("agreement_rate"))

    if abs_gap >= accepted_min_gap:
        if agreement is None or agreement >= accepted_min_agreement:
            return "accepted", f"accepted_margin:{threshold_rule}", {
                "accepted_min_gap": accepted_min_gap,
                "borderline_min_gap": borderline_min_gap,
            }
        if agreement >= borderline_min_agreement:
            return "borderline", f"agreement_downgrade:{threshold_rule}", {
                "accepted_min_gap": accepted_min_gap,
                "borderline_min_gap": borderline_min_gap,
            }
        return "rejected", "agreement_below_borderline", {
            "accepted_min_gap": accepted_min_gap,
            "borderline_min_gap": borderline_min_gap,
        }

    if abs_gap >= borderline_min_gap:
        if agreement is None or agreement >= borderline_min_agreement:
            return "borderline", f"borderline_margin:{threshold_rule}", {
                "accepted_min_gap": accepted_min_gap,
                "borderline_min_gap": borderline_min_gap,
            }
        return "rejected", "agreement_below_borderline", {
            "accepted_min_gap": accepted_min_gap,
            "borderline_min_gap": borderline_min_gap,
        }

    return "rejected", f"gap_below_borderline:{threshold_rule}", {
        "accepted_min_gap": accepted_min_gap,
        "borderline_min_gap": borderline_min_gap,
    }


def _build_output_row(
    *,
    source_row: dict[str, Any],
    idx: int,
    labels_path: Path,
    bucket: str,
    bucket_reason: str,
    bucket_meta: dict[str, float | str],
    policy_cfg: dict[str, Any],
) -> dict[str, Any]:
    gap = _safe_float(source_row.get("oracle_action_gap"))
    q_act = _safe_float(source_row.get("q_act"))
    q_stop = _safe_float(source_row.get("q_stop"))

    gap_f = float(gap) if gap is not None else 0.0
    teacher_prob = _teacher_prob_from_gap(gap=gap_f, soft_cfg=dict(policy_cfg.get("soft_target", {})))

    hard_label = source_row.get("oracle_label_act")
    if hard_label not in {0, 1}:
        hard_label = 1 if gap_f > 0.0 else 0

    treat = dict(dict(policy_cfg.get("training_treatment", {})).get(bucket, {}))
    sample_weight = float(treat.get("sample_weight", 0.0))
    hard_loss_weight = float(treat.get("hard_loss_weight", 0.0))
    soft_kl_weight = float(treat.get("soft_kl_weight", 0.0))
    abstain_target = float(treat.get("abstain_target", 1.0))

    return {
        "state_id": source_row.get("state_id"),
        "example_id": source_row.get("example_id"),
        "budget": source_row.get("budget"),
        "remaining_budget": source_row.get("remaining_budget"),
        "current_branch_id": source_row.get("current_branch_id"),
        "hard_label_act": int(hard_label),
        "teacher_prob_act": teacher_prob,
        "oracle_action_gap": gap_f,
        "abs_oracle_action_gap": abs(gap_f),
        "q_act": q_act,
        "q_stop": q_stop,
        "bucket": bucket,
        "bucket_reason": bucket_reason,
        "sample_weight": sample_weight,
        "hard_loss_weight": hard_loss_weight,
        "soft_kl_weight": soft_kl_weight,
        "abstain_target": abstain_target,
        "agreement_rate": _safe_float(source_row.get("agreement_rate")),
        "audit_status": source_row.get("audit_status"),
        "quality_gate_status": source_row.get("quality_gate_status"),
        "bucket_threshold_meta": bucket_meta,
        "provenance": {
            "source_labels_path": str(labels_path),
            "source_row_index": idx,
            "mock_interface_only": bool(source_row.get("mock_interface_only", False)),
            "has_non_oracle_warning": bool(_str_or_empty(source_row.get("non_oracle_warning"))),
        },
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build selective-distillation-ready oracle ACT-vs-STOP dataset")
    p.add_argument("--labels-jsonl", required=True, help="Input oracle label rows (JSONL)")
    p.add_argument(
        "--policy-config",
        default="configs/stop_vs_act_oracle_selective_distillation_v1.json",
        help="Selective distillation policy config JSON",
    )
    p.add_argument(
        "--manifest-json",
        default="",
        help="Optional oracle manifest JSON for provenance/mock marker checks",
    )
    p.add_argument("--output-jsonl", required=True, help="Output JSONL path for distillation-ready rows")
    p.add_argument("--summary-json", default="", help="Optional summary JSON output path")
    p.add_argument(
        "--fail-on-any-rejected",
        action="store_true",
        help="If set, exit non-zero when any row lands in rejected bucket.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    labels_path = Path(args.labels_jsonl)
    policy_path = Path(args.policy_config)
    output_path = Path(args.output_jsonl)

    rows = _read_jsonl(labels_path)
    policy_cfg = _load_json(policy_path)
    config_errors = _validate_policy_config(policy_cfg)
    if config_errors:
        for e in config_errors:
            print(f"POLICY_CONFIG_ERROR: {e}")
        raise SystemExit(1)

    manifest: dict[str, Any] = {}
    if args.manifest_json:
        manifest = _load_json(Path(args.manifest_json))
    manifest_mock_mode, manifest_non_oracle_warning = _parse_manifest_markers(manifest)

    required_fields = [str(x) for x in list(dict(policy_cfg.get("input_contract", {})).get("required_core_fields", []))]

    out_rows: list[dict[str, Any]] = []
    bucket_counts = {"accepted": 0, "borderline": 0, "rejected": 0}
    reason_counts: dict[str, int] = {}

    for idx, row in enumerate(rows):
        bucket, reason, bucket_meta = _assign_bucket(
            row,
            dict(policy_cfg.get("bucket_policy", {})),
            required_fields,
            manifest_mock_mode=manifest_mock_mode,
            manifest_non_oracle_warning=manifest_non_oracle_warning,
        )
        bucket_counts[bucket] = int(bucket_counts[bucket]) + 1
        reason_counts[reason] = int(reason_counts.get(reason, 0)) + 1
        out_rows.append(
            _build_output_row(
                source_row=row,
                idx=idx,
                labels_path=labels_path,
                bucket=bucket,
                bucket_reason=reason,
                bucket_meta=bucket_meta,
                policy_cfg=policy_cfg,
            )
        )

    _write_jsonl(output_path, out_rows)

    total = len(out_rows)
    summary = {
        "status": "ok",
        "policy_config": str(policy_path),
        "input_labels": str(labels_path),
        "manifest_json": args.manifest_json,
        "output_jsonl": str(output_path),
        "rows_total": total,
        "bucket_counts": bucket_counts,
        "bucket_rates": {k: (float(v) / total if total > 0 else 0.0) for k, v in bucket_counts.items()},
        "bucket_reason_counts": dict(sorted(reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "manifest_markers": {
            "mock_mode": manifest_mock_mode,
            "has_non_oracle_warning": manifest_non_oracle_warning,
        },
        "notes": [
            "This artifact is preprocessing/scaffolding only and does not claim distillation gains.",
            "Rows rejected here are retained in output for auditability but have zero training weights.",
        ],
    }

    summary_path = Path(args.summary_json) if args.summary_json else output_path.with_name("distillation_bucket_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    if args.fail_on_any_rejected and int(bucket_counts["rejected"]) > 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
