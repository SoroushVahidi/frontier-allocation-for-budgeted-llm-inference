"""Apply frozen slice-aware reranking rules to scored candidates (no retuning).

This script transfers pre-selected slice-aware rules (typically from Task K outputs)
onto a disjoint scored artifact. It never learns/retunes thresholds on the target.

Primary baseline: verifier_top1 (highest score in each group).
Frozen policy: for slices with matching (method, budget), apply the frozen rule.
Fallback: verifier_top1 for unmatched/unsupported slices.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

SUPPORTED_MODES = {"epsilon", "spread"}
SUPPORTED_TIE_POLICIES = {"lowest_seed", "highest_seed", "median_seed", "verifier_top1"}


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _seed_as_float(v: Any) -> float:
    return _safe_float(v, 0.0)


def load_scored(path: pathlib.Path, score_field: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            meta = raw.get("metadata", {}) or {}
            row: dict[str, Any] = {
                score_field: _safe_float(raw.get(score_field), 0.0),
                "predicted_label": _safe_int(raw.get("predicted_label"), 0),
                "feature_text": raw.get("feature_text", ""),
            }
            for k, v in meta.items():
                row[k] = v
            rows.append(row)
    return rows


def build_groups(rows: list[dict[str, Any]], group_fields: list[str]) -> dict[tuple, list[dict[str, Any]]]:
    out: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        out[tuple(r.get(f) for f in group_fields)].append(r)
    return dict(out)


def _canonical_budget(v: Any) -> str:
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float) and float(v).is_integer():
        return str(int(v))
    s = str(v).strip()
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except (TypeError, ValueError):
        pass
    return s


def _canonical_method(v: Any) -> str:
    return str(v).strip()


def _canonical_slice(method: Any, budget: Any) -> tuple[str, str]:
    return (_canonical_method(method), _canonical_budget(budget))


def _normalize_mode(v: Any) -> str:
    return str(v).strip().lower()


def _normalize_tie_policy(v: Any) -> str:
    return str(v).strip().lower()


def load_rules_csv(path: pathlib.Path, policy_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            if (raw.get("policy_name") or "").strip() != policy_name:
                continue
            rows.append(dict(raw))
    return rows


def load_rules_json(path: pathlib.Path, policy_name: str) -> list[dict[str, Any]]:
    obj = json.load(open(path))
    if isinstance(obj, dict):
        if "rules" in obj and isinstance(obj["rules"], list):
            rows = obj["rules"]
        elif policy_name in obj and isinstance(obj[policy_name], list):
            rows = obj[policy_name]
        else:
            rows = []
    elif isinstance(obj, list):
        rows = obj
    else:
        rows = []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        pn = str(r.get("policy_name", policy_name)).strip()
        if pn != policy_name:
            continue
        out.append(dict(r))
    return out


def validate_and_index_rules(raw_rules: list[dict[str, Any]]) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (indexed_rules, supported_rows, unsupported_rows, duplicate_rows)."""
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    supported_rows: list[dict[str, Any]] = []
    unsupported_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []

    for r in raw_rules:
        method = _canonical_method(r.get("method"))
        budget = _canonical_budget(r.get("budget"))
        mode = _normalize_mode(r.get("mode"))
        tie_policy = _normalize_tie_policy(r.get("tie_policy"))
        threshold = _safe_float(r.get("threshold"), 0.0)

        normalized = dict(r)
        normalized["method"] = method
        normalized["budget"] = budget
        normalized["mode"] = mode
        normalized["tie_policy"] = tie_policy
        normalized["threshold"] = threshold

        unsupported_reasons = []
        if mode not in SUPPORTED_MODES:
            unsupported_reasons.append(f"unsupported_mode:{mode}")
        if tie_policy not in SUPPORTED_TIE_POLICIES:
            unsupported_reasons.append(f"unsupported_tie_policy:{tie_policy}")

        if unsupported_reasons:
            normalized["unsupported_reason"] = ";".join(unsupported_reasons)
            unsupported_rows.append(normalized)
            continue

        key = (method, budget)
        if key in indexed:
            normalized["unsupported_reason"] = "duplicate_slice_rule_ignored"
            duplicate_rows.append(normalized)
            continue

        indexed[key] = normalized
        supported_rows.append(normalized)

    return indexed, supported_rows, unsupported_rows, duplicate_rows


def baseline_top1_index(cands: list[dict[str, Any]], score_field: str) -> int:
    return max(
        range(len(cands)),
        key=lambda i: (_safe_float(cands[i].get(score_field), 0.0), -_seed_as_float(cands[i].get("seed"))),
    )


def anti_verifier_index(cands: list[dict[str, Any]], score_field: str) -> int:
    return min(
        range(len(cands)),
        key=lambda i: (_safe_float(cands[i].get(score_field), 0.0), _seed_as_float(cands[i].get("seed"))),
    )


def _epsilon_tie_idxs(cands: list[dict[str, Any]], score_field: str, threshold: float) -> list[int]:
    scores = [_safe_float(c.get(score_field), 0.0) for c in cands]
    max_score = max(scores) if scores else 0.0
    tie = [i for i, s in enumerate(scores) if (max_score - s) <= (threshold + 1e-12)]
    return tie or [0]


def _spread_tie_idxs(cands: list[dict[str, Any]], score_field: str, threshold: float, baseline_idx: int) -> list[int]:
    scores = [_safe_float(c.get(score_field), 0.0) for c in cands]
    spread = (max(scores) - min(scores)) if scores else 0.0
    if spread < (threshold + 1e-12):
        return list(range(len(cands)))
    return [baseline_idx]


def tie_indices(cands: list[dict[str, Any]], score_field: str, mode: str, threshold: float, baseline_idx: int) -> list[int]:
    if mode == "epsilon":
        return _epsilon_tie_idxs(cands, score_field, threshold)
    if mode == "spread":
        return _spread_tie_idxs(cands, score_field, threshold, baseline_idx)
    return [baseline_idx]


def choose_index(cands: list[dict[str, Any]], tie_idxs: list[int], tie_policy: str, baseline_idx: int) -> int:
    if tie_policy == "verifier_top1":
        return baseline_idx

    ordered = sorted(tie_idxs, key=lambda i: _seed_as_float(cands[i].get("seed")))
    if tie_policy == "lowest_seed":
        return ordered[0]
    if tie_policy == "highest_seed":
        return ordered[-1]
    if tie_policy == "median_seed":
        return ordered[len(ordered) // 2]
    return baseline_idx


def aggregate_group_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    n = len(rows)
    baseline_correct = sum(_safe_int(r.get("baseline_em"), 0) for r in rows)
    frozen_correct = sum(_safe_int(r.get("frozen_em"), 0) for r in rows)
    anti_correct = sum(_safe_int(r.get("anti_em"), 0) for r in rows)
    oracle_correct = sum(_safe_int(r.get("oracle_any_correct"), 0) for r in rows)
    random_expected_sum = sum(_safe_float(r.get("random_expected"), 0.0) for r in rows)
    affected = sum(_safe_int(r.get("changed_choice"), 0) for r in rows)
    recoveries = sum(_safe_int(r.get("recovery"), 0) for r in rows)
    regressions = sum(_safe_int(r.get("regression"), 0) for r in rows)
    matched = sum(_safe_int(r.get("slice_has_rule"), 0) for r in rows)

    return {
        "n_groups": n,
        "baseline_verifier_top1_accuracy": baseline_correct / n,
        "frozen_policy_accuracy": frozen_correct / n,
        "random_expected_accuracy": random_expected_sum / n,
        "anti_verifier_accuracy": anti_correct / n,
        "oracle_ceiling": oracle_correct / n,
        "frozen_minus_verifier": (frozen_correct - baseline_correct) / n,
        "frozen_minus_random": (frozen_correct / n) - (random_expected_sum / n),
        "recoveries": recoveries,
        "regressions": regressions,
        "net_gain": recoveries - regressions,
        "affected_groups": affected,
        "affected_rate": affected / n,
        "matched_rule_groups": matched,
        "matched_rule_group_rate": matched / n,
    }


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for row in rows:
            w.writerow({k: _fmt(row.get(k)) for k in columns})


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scored-jsonl", required=True)
    p.add_argument("--rule-csv", default="")
    p.add_argument("--rule-json", default="")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--policy-name", default="all_positive_net_slices")
    p.add_argument("--score-field", default="proba_ready")
    p.add_argument("--correct-field", default="exact_match_metadata")
    p.add_argument("--group-fields", default="example_id,budget,method")
    p.add_argument("--method-field", default="method")
    p.add_argument("--budget-field", default="budget")
    p.add_argument("--seed-field", default="seed")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    scored_path = pathlib.Path(args.scored_jsonl)
    if not scored_path.exists():
        print(f"ERROR: scored-jsonl not found: {scored_path}", file=sys.stderr)
        return 1

    if not args.rule_csv and not args.rule_json:
        print("ERROR: provide --rule-csv or --rule-json", file=sys.stderr)
        return 1

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_scored(scored_path, args.score_field)
    group_fields = [x.strip() for x in args.group_fields.split(",") if x.strip()]
    groups = build_groups(rows, group_fields)

    if args.rule_csv:
        raw_rules = load_rules_csv(pathlib.Path(args.rule_csv), args.policy_name)
        rule_source = args.rule_csv
    else:
        raw_rules = load_rules_json(pathlib.Path(args.rule_json), args.policy_name)
        rule_source = args.rule_json

    indexed_rules, supported_rules, unsupported_rules, duplicate_rules = validate_and_index_rules(raw_rules)

    try:
        method_idx = group_fields.index(args.method_field)
    except ValueError:
        print(f"ERROR: method field '{args.method_field}' not in group fields {group_fields}", file=sys.stderr)
        return 1
    try:
        budget_idx = group_fields.index(args.budget_field)
    except ValueError:
        print(f"ERROR: budget field '{args.budget_field}' not in group fields {group_fields}", file=sys.stderr)
        return 1

    group_rows: list[dict[str, Any]] = []
    target_slices: set[tuple[str, str]] = set()
    matched_slices: set[tuple[str, str]] = set()

    for key, cands in groups.items():
        method = _canonical_method(key[method_idx])
        budget = _canonical_budget(key[budget_idx])
        slice_key = (method, budget)
        target_slices.add(slice_key)

        b_idx = baseline_top1_index(cands, args.score_field)
        anti_idx = anti_verifier_index(cands, args.score_field)

        ems = [_safe_int(c.get(args.correct_field), 0) for c in cands]
        random_expected = statistics.mean(ems) if ems else 0.0
        oracle_any_correct = int(any(e == 1 for e in ems))

        rule = indexed_rules.get(slice_key)
        slice_has_rule = int(rule is not None)
        if rule is not None:
            matched_slices.add(slice_key)
            tie_idxs = tie_indices(cands, args.score_field, rule["mode"], _safe_float(rule["threshold"]), b_idx)
            frozen_idx = choose_index(cands, tie_idxs, rule["tie_policy"], b_idx)
            applied_mode = rule["mode"]
            applied_threshold = _safe_float(rule["threshold"])
            applied_tie_policy = rule["tie_policy"]
        else:
            tie_idxs = [b_idx]
            frozen_idx = b_idx
            applied_mode = "fallback"
            applied_threshold = 0.0
            applied_tie_policy = "verifier_top1"

        baseline_em = _safe_int(cands[b_idx].get(args.correct_field), 0)
        frozen_em = _safe_int(cands[frozen_idx].get(args.correct_field), 0)
        anti_em = _safe_int(cands[anti_idx].get(args.correct_field), 0)

        row = {f: v for f, v in zip(group_fields, key)}
        row.update(
            {
                "n_candidates": len(cands),
                "slice_has_rule": slice_has_rule,
                "rule_mode": applied_mode,
                "rule_threshold": applied_threshold,
                "rule_tie_policy": applied_tie_policy,
                "tie_set_size": len(tie_idxs),
                "baseline_seed": cands[b_idx].get(args.seed_field),
                "frozen_seed": cands[frozen_idx].get(args.seed_field),
                "baseline_score": _safe_float(cands[b_idx].get(args.score_field), 0.0),
                "frozen_score": _safe_float(cands[frozen_idx].get(args.score_field), 0.0),
                "baseline_em": baseline_em,
                "frozen_em": frozen_em,
                "random_expected": random_expected,
                "anti_em": anti_em,
                "oracle_any_correct": oracle_any_correct,
                "changed_choice": int(frozen_idx != b_idx),
                "recovery": int(baseline_em == 0 and frozen_em == 1),
                "regression": int(baseline_em == 1 and frozen_em == 0),
                "net_gain_delta": frozen_em - baseline_em,
            }
        )
        group_rows.append(row)

    overall = aggregate_group_rows(group_rows)

    by_method_rows: list[dict[str, Any]] = []
    grouped_m: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_mb: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in group_rows:
        m = _canonical_method(r.get(args.method_field))
        b = _canonical_budget(r.get(args.budget_field))
        grouped_m[m].append(r)
        grouped_mb[(m, b)].append(r)

    for method, m_rows in sorted(grouped_m.items()):
        agg = aggregate_group_rows(m_rows)
        agg["method"] = method
        by_method_rows.append(agg)

    by_mb_rows: list[dict[str, Any]] = []
    for (method, budget), mb_rows in sorted(grouped_mb.items(), key=lambda x: (x[0][0], x[0][1])):
        agg = aggregate_group_rows(mb_rows)
        agg["method"] = method
        agg["budget"] = budget
        by_mb_rows.append(agg)

    affected_rows = [r for r in group_rows if _safe_int(r.get("changed_choice"), 0) == 1]

    rule_slices = set(indexed_rules.keys())
    unmatched_rule_slices = sorted(rule_slices - target_slices)
    unmatched_target_slices = sorted(target_slices - rule_slices)

    policy_overall = dict(overall)
    policy_overall.update(
        {
            "policy_name": args.policy_name,
            "rule_source": rule_source,
            "n_supported_rules": len(supported_rules),
            "n_unsupported_rules": len(unsupported_rules),
            "n_duplicate_rules_ignored": len(duplicate_rules),
            "unmatched_rule_slice_count": len(unmatched_rule_slices),
            "unmatched_target_slice_count": len(unmatched_target_slices),
        }
    )

    write_csv(
        out_dir / "policy_overall.csv",
        [policy_overall],
        [
            "policy_name",
            "rule_source",
            "n_groups",
            "baseline_verifier_top1_accuracy",
            "frozen_policy_accuracy",
            "random_expected_accuracy",
            "anti_verifier_accuracy",
            "oracle_ceiling",
            "frozen_minus_verifier",
            "frozen_minus_random",
            "recoveries",
            "regressions",
            "net_gain",
            "affected_groups",
            "affected_rate",
            "matched_rule_groups",
            "matched_rule_group_rate",
            "n_supported_rules",
            "n_unsupported_rules",
            "n_duplicate_rules_ignored",
            "unmatched_rule_slice_count",
            "unmatched_target_slice_count",
        ],
    )

    write_csv(
        out_dir / "policy_by_method.csv",
        by_method_rows,
        [
            "method",
            "n_groups",
            "baseline_verifier_top1_accuracy",
            "frozen_policy_accuracy",
            "random_expected_accuracy",
            "anti_verifier_accuracy",
            "oracle_ceiling",
            "frozen_minus_verifier",
            "frozen_minus_random",
            "recoveries",
            "regressions",
            "net_gain",
            "affected_groups",
            "affected_rate",
            "matched_rule_groups",
            "matched_rule_group_rate",
        ],
    )

    write_csv(
        out_dir / "policy_by_method_budget.csv",
        by_mb_rows,
        [
            "method",
            "budget",
            "n_groups",
            "baseline_verifier_top1_accuracy",
            "frozen_policy_accuracy",
            "random_expected_accuracy",
            "anti_verifier_accuracy",
            "oracle_ceiling",
            "frozen_minus_verifier",
            "frozen_minus_random",
            "recoveries",
            "regressions",
            "net_gain",
            "affected_groups",
            "affected_rate",
            "matched_rule_groups",
            "matched_rule_group_rate",
        ],
    )

    write_csv(
        out_dir / "affected_groups.csv",
        affected_rows,
        group_fields
        + [
            "n_candidates",
            "slice_has_rule",
            "rule_mode",
            "rule_threshold",
            "rule_tie_policy",
            "tie_set_size",
            "baseline_seed",
            "frozen_seed",
            "baseline_score",
            "frozen_score",
            "baseline_em",
            "frozen_em",
            "random_expected",
            "anti_em",
            "oracle_any_correct",
            "changed_choice",
            "recovery",
            "regression",
            "net_gain_delta",
        ],
    )

    report_lines = [
        f"# Frozen Slice-Aware Rule Transfer Report ({args.policy_name})",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Input scored JSONL: `{args.scored_jsonl}`",
        f"- Rule source: `{rule_source}`",
        f"- Policy name: `{args.policy_name}`",
        f"- Groups: {policy_overall['n_groups']}",
        "",
        "## Overall",
        "",
        f"- Baseline verifier_top1 accuracy: {policy_overall['baseline_verifier_top1_accuracy']:.4f}",
        f"- Frozen policy accuracy: {policy_overall['frozen_policy_accuracy']:.4f}",
        f"- frozen_minus_verifier: {policy_overall['frozen_minus_verifier']:+.4f}",
        f"- random_expected accuracy: {policy_overall['random_expected_accuracy']:.4f}",
        f"- frozen_minus_random: {policy_overall['frozen_minus_random']:+.4f}",
        f"- anti_verifier accuracy: {policy_overall['anti_verifier_accuracy']:.4f}",
        f"- oracle ceiling: {policy_overall['oracle_ceiling']:.4f}",
        f"- recoveries / regressions / net_gain: {policy_overall['recoveries']} / {policy_overall['regressions']} / {policy_overall['net_gain']}",
        f"- affected groups: {policy_overall['affected_groups']}/{policy_overall['n_groups']} ({policy_overall['affected_rate']*100:.1f}%)",
        "",
        "## Rule Match Audit",
        "",
        f"- Supported rule rows used for matching: {policy_overall['n_supported_rules']}",
        f"- Unsupported rule rows (ignored): {policy_overall['n_unsupported_rules']}",
        f"- Duplicate slice rows ignored: {policy_overall['n_duplicate_rules_ignored']}",
        f"- Unmatched rule slices (present in rules, absent in target): {policy_overall['unmatched_rule_slice_count']}",
        f"- Unmatched target slices (present in target, absent in rules): {policy_overall['unmatched_target_slice_count']}",
        "",
        "## Frozen-Transfer Discipline",
        "",
        "- No thresholds or tie policies were learned on target data.",
        "- Target slices without a matching frozen rule fallback to verifier_top1.",
        "- Gold/exact-match fields are used only for offline evaluation metrics.",
    ]

    if unmatched_rule_slices:
        report_lines += ["", "### Unmatched Rule Slices", ""]
        for m, b in unmatched_rule_slices:
            report_lines.append(f"- `{m}` @ budget `{b}`")

    if unmatched_target_slices:
        report_lines += ["", "### Unmatched Target Slices", ""]
        for m, b in unmatched_target_slices:
            report_lines.append(f"- `{m}` @ budget `{b}`")

    (out_dir / "frozen_rule_application_report.md").write_text("\n".join(report_lines) + "\n")

    metrics = {
        "stamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "input": {
            "scored_jsonl": args.scored_jsonl,
            "rule_source": rule_source,
            "policy_name": args.policy_name,
            "group_fields": group_fields,
            "score_field": args.score_field,
            "correct_field": args.correct_field,
            "method_field": args.method_field,
            "budget_field": args.budget_field,
            "seed_field": args.seed_field,
        },
        "overall": policy_overall,
        "by_method": by_method_rows,
        "by_method_budget": by_mb_rows,
        "rule_audit": {
            "supported_rules": supported_rules,
            "unsupported_rules": unsupported_rules,
            "duplicate_rules_ignored": duplicate_rules,
            "unmatched_rule_slices": [{"method": m, "budget": b} for m, b in unmatched_rule_slices],
            "unmatched_target_slices": [{"method": m, "budget": b} for m, b in unmatched_target_slices],
            "matched_slices": [{"method": m, "budget": b} for m, b in sorted(matched_slices)],
        },
        "n_rows": len(rows),
        "n_groups": len(groups),
        "n_affected_groups": len(affected_rows),
    }
    with open(out_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"[done] wrote frozen transfer outputs to: {out_dir}")
    print(
        "[summary] "
        f"groups={policy_overall['n_groups']} "
        f"baseline={policy_overall['baseline_verifier_top1_accuracy']:.4f} "
        f"frozen={policy_overall['frozen_policy_accuracy']:.4f} "
        f"delta={policy_overall['frozen_minus_verifier']:+.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
