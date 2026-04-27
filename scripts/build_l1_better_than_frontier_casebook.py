#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

DIAG_DIR = REPO_ROOT / "outputs" / "direct_reserve_frontier_gate_failure_slice_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN_DIAGNOSTIC_ACTUAL"
REPLAY_DIR = REPO_ROOT / "outputs" / "cohere_real_model_cost_normalized_validation_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN"
NEAR_DIRECT_DIR = REPO_ROOT / "outputs" / "near_direct_reserve_frontier_gate_failure_slice_20260426T223900Z"
CALIBRATED_DIR = REPO_ROOT / "outputs" / "calibrated_near_direct_gate_sweep_20260426T230600Z"


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            out = {}
            for key in fields:
                val = row.get(key, "")
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, sort_keys=True)
                out[key] = val
            w.writerow(out)


def _norm(value: Any) -> str:
    text = str(value or "").strip().replace(",", "")
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", text)
    if nums:
        out = nums[-1]
        return out[:-2] if out.endswith(".0") else out
    return text.lower()


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


def _get(row: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return default


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("example_id", "")), str(row.get("seed", "")), str(row.get("budget", "")))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _top_groups(group_rows: list[dict[str, str]], limit: int = 4) -> str:
    ranked = sorted(
        group_rows,
        key=lambda r: (_as_int(r.get("support_count")), _as_float(r.get("best_branch_score"))),
        reverse=True,
    )
    parts = []
    for row in ranked[:limit]:
        parts.append(
            f"{row.get('answer_group')} (support={row.get('support_count')}, maturity={row.get('maturity')}, families={row.get('family_count')})"
        )
    return "; ".join(parts)


def _branch_summary(branch_rows: list[dict[str, str]], limit: int = 6) -> str:
    parts = []
    for row in branch_rows[:limit]:
        parts.append(
            f"{row.get('branch_id')}:{row.get('answer_group')} depth={row.get('depth')} family={row.get('family_id') or 'NA'} selected={row.get('is_selected')}"
        )
    return "; ".join(parts)


def _label_case(
    *,
    row: dict[str, Any],
    strict_groups: list[dict[str, str]],
    v1_groups: list[dict[str, str]],
    v1_meta: dict[str, Any],
    output_repair: bool,
) -> tuple[str, str]:
    gold = _norm(row["gold_answer"])
    l1 = _norm(row["external_l1_max_prediction"])
    strict = _norm(row["strict_f3_prediction"])
    v1 = _norm(_get(row, "direct_reserve_frontier_gate_v1_prediction", "direct_reserve_frontier_gate_prediction"))
    strict_group_keys = {_norm(g.get("answer_group")) for g in strict_groups}
    v1_group_keys = {_norm(g.get("answer_group")) for g in v1_groups}
    groups_for_final = v1_groups or strict_groups
    gold_present = gold in (v1_group_keys | strict_group_keys)
    l1_present = l1 in (v1_group_keys | strict_group_keys)
    final_groups = [g for g in groups_for_final if _norm(g.get("answer_group")) == v1]
    gold_groups = [g for g in groups_for_final if _norm(g.get("answer_group")) == gold]
    final_support = max((_as_int(g.get("support_count")) for g in final_groups), default=0)
    gold_support = max((_as_int(g.get("support_count")) for g in gold_groups), default=0)
    if output_repair:
        return "artifact_sensitive_repair_case", "fix answer surfacing/repair accounting before using override gains"
    if _as_int(row.get("frontier_override_triggered")) and _as_int(row.get("harmful_override")):
        return "unsafe_override", "tighten override guard and preserve L1 incumbent"
    if _as_int(row.get("external_l1_max_correct")) and _as_int(
        _get(row, "direct_reserve_frontier_gate_v1_correct", "direct_reserve_frontier_gate_correct")
    ) == 0:
        return "direct_answer_should_have_been_preserved", "prefer protected near-direct incumbent when traced support includes it"
    if not gold_present:
        return "gold_absent_from_frontier", "improve frontier generation/coverage rather than selection"
    if gold_present and strict != gold and v1 != gold:
        return "gold_present_but_misselected", "improve verifier/answer-group selection"
    if l1_present and strict != l1 and v1 != l1:
        return "l1_answer_present_but_not_selected", "preserve near-direct answer when present in frontier support"
    if final_support > gold_support:
        return "frontier_wrong_answer_over_supported", "add support calibration and verifier checks"
    if groups_for_final and max((_as_int(g.get("family_count")) for g in groups_for_final), default=0) <= 1:
        return "insufficient_branch_diversity", "require independent families before trusting frontier support"
    if "__unknown__" in (v1_group_keys | strict_group_keys):
        return "frontier_no_parse_or_unresolved", "improve parsing and unresolved branch handling"
    return "unknown_needs_manual_review", "manual trace inspection"


def main() -> int:
    ts = _now_ts()
    out_dir = REPO_ROOT / "outputs" / f"l1_better_than_frontier_casebook_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    v1_rows = _read_csv(DIAG_DIR / "per_case_results.csv")
    near_rows = {_key(r): r for r in _read_csv(NEAR_DIRECT_DIR / "per_case_results.csv")}
    calibrated_rows = {
        (r["example_id"], r["seed"], r["budget"], r["rule_name"]): r
        for r in _read_csv(CALIBRATED_DIR / "per_case_decisions.csv")
    }
    recommended_rule = json.loads((CALIBRATED_DIR / "recommended_rule.json").read_text(encoding="utf-8"))
    recommended_name = str(recommended_rule["rule_name"])
    branches = _read_csv(REPLAY_DIR / "candidate_branch_table.csv")
    groups = _read_csv(REPLAY_DIR / "answer_group_table.csv")
    trace_index = _read_csv(REPLAY_DIR / "per_case_trace_index.csv")
    trace_paths = list((REPLAY_DIR / "traces").glob("*.json"))

    groups_by = defaultdict(list)
    for row in groups:
        groups_by[(row["example_id"], row["seed"], row["budget"], row["method"])].append(row)
    branches_by = defaultdict(list)
    for row in branches:
        branches_by[(row["example_id"], row["seed"], row["budget"], row["method"])].append(row)
    trace_by = {(r["example_id"], r["seed"], r["budget"], r["method"]): r for r in trace_index}

    records_by = {}
    for rec in _load_jsonl(REPLAY_DIR / "per_example_records.jsonl"):
        records_by[(str(rec.get("example_id")), str(rec.get("seed")), str(rec.get("budget")), str(rec.get("method")))] = rec

    case_rows: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    l1_better_cases: list[dict[str, Any]] = []
    frontier_better_rows: list[dict[str, Any]] = []

    for row in v1_rows:
        key = _key(row)
        near = near_rows.get(key, {})
        cal = calibrated_rows.get((key[0], key[1], key[2], recommended_name), {})
        strict_rec = records_by.get((key[0], key[1], key[2], "strict_f3"), {})
        v1_rec = records_by.get((key[0], key[1], key[2], "direct_reserve_frontier_gate_v1"), {})
        question = str(strict_rec.get("question") or v1_rec.get("question") or "")
        qhash = ""
        if not question:
            qhash = str(trace_by.get((key[0], key[1], key[2], "strict_f3"), {}).get("trace_path", ""))
        calibrated_correct = cal.get("calibrated_correct_clean", cal.get("calibrated_correct_reported", ""))
        calibrated_pred = row["external_l1_max_prediction"] if _as_int(cal.get("calibrated_override", 0)) == 0 else near.get("near_direct_reserve_frontier_gate_v1_prediction", "")
        l1_ok = _as_int(row["external_l1_max_correct"])
        strict_ok = _as_int(row["strict_f3_correct"])
        v1_ok = _as_int(_get(row, "direct_reserve_frontier_gate_v1_correct", "direct_reserve_frontier_gate_correct"))
        near_ok = _as_int(near.get("near_direct_reserve_frontier_gate_v1_correct", 0))
        frontier_any = int(any([strict_ok, v1_ok, _as_int(near.get("direct_reserve_frontier_gate_v2_correct", 0)), near_ok, _as_int(calibrated_correct)]))
        case = {
            "example_id": key[0],
            "seed": key[1],
            "budget": key[2],
            "question": question,
            "question_hash": qhash,
            "gold_answer": row["gold_answer"],
            "external_l1_max_prediction": row["external_l1_max_prediction"],
            "external_l1_max_correct": l1_ok,
            "strict_f3_prediction": row["strict_f3_prediction"],
            "strict_f3_correct": strict_ok,
            "direct_reserve_frontier_gate_v1_prediction": _get(
                row, "direct_reserve_frontier_gate_v1_prediction", "direct_reserve_frontier_gate_prediction"
            ),
            "direct_reserve_frontier_gate_v1_correct": v1_ok,
            "direct_reserve_frontier_gate_v2_prediction": near.get("direct_reserve_frontier_gate_v2_prediction", ""),
            "direct_reserve_frontier_gate_v2_correct": near.get("direct_reserve_frontier_gate_v2_correct", ""),
            "near_direct_reserve_frontier_gate_v1_prediction": near.get("near_direct_reserve_frontier_gate_v1_prediction", ""),
            "near_direct_reserve_frontier_gate_v1_correct": near_ok,
            "calibrated_near_direct_frontier_gate_v1_prediction": calibrated_pred,
            "calibrated_near_direct_frontier_gate_v1_correct": calibrated_correct,
            "l1_beats_strict_f3": int(l1_ok and not strict_ok),
            "l1_beats_v1": int(l1_ok and not v1_ok),
            "l1_beats_near_direct": int(l1_ok and not near_ok),
            "frontier_beats_l1": int((not l1_ok) and frontier_any),
            "both_wrong": int((not l1_ok) and (not strict_ok)),
        }
        case_rows.append(case)

        strict_groups = groups_by[(key[0], key[1], key[2], "strict_f3")]
        v1_groups = groups_by[(key[0], key[1], key[2], "direct_reserve_frontier_gate_v1")]
        v1_meta = v1_rec.get("result_metadata", {}) if isinstance(v1_rec.get("result_metadata"), dict) else {}
        surfaced = _norm(v1_rec.get("final_answer_raw") or v1_rec.get("final_answer_canonical"))
        metadata_final = _norm(v1_meta.get("final_answer"))
        output_repair = bool(metadata_final and surfaced and metadata_final != surfaced)
        label, fix = _label_case(row=row, strict_groups=strict_groups, v1_groups=v1_groups, v1_meta=v1_meta, output_repair=output_repair)
        label_rows.append({"example_id": key[0], "seed": key[1], "budget": key[2], "failure_label": label, "suggested_fix_category": fix})

        is_l1_better = bool(l1_ok and (not strict_ok or not v1_ok or not near_ok))
        if is_l1_better:
            l1_better_cases.append({**case, "failure_label": label, "suggested_fix_category": fix})
            gold = _norm(row["gold_answer"])
            l1 = _norm(row["external_l1_max_prediction"])
            frontier_answer = _norm(row["frontier_candidate_answer"])
            final_answer = _norm(_get(row, "direct_reserve_frontier_gate_v1_prediction", "direct_reserve_frontier_gate_prediction"))
            v1_group_keys = {_norm(g.get("answer_group")) for g in v1_groups}
            strict_group_keys = {_norm(g.get("answer_group")) for g in strict_groups}
            all_group_keys = v1_group_keys | strict_group_keys

            def group_rows_for(ans: str, method: str) -> list[dict[str, str]]:
                source = v1_groups if method == "v1" else strict_groups
                return [g for g in source if _norm(g.get("answer_group")) == ans]

            l1_group_rows = group_rows_for(l1, "v1") + group_rows_for(l1, "strict")
            frontier_group_rows = group_rows_for(frontier_answer, "v1") + group_rows_for(frontier_answer, "strict")
            gold_group_rows = group_rows_for(gold, "v1") + group_rows_for(gold, "strict")
            l1_branch_ids = []
            frontier_branch_ids = []
            for branch in branches_by[(key[0], key[1], key[2], "direct_reserve_frontier_gate_v1")] + branches_by[(key[0], key[1], key[2], "strict_f3")]:
                if _norm(branch.get("answer_group")) == l1:
                    l1_branch_ids.append(branch.get("branch_id"))
                if _norm(branch.get("answer_group")) == frontier_answer:
                    frontier_branch_ids.append(branch.get("branch_id"))
            final_support = max((_as_int(g.get("support_count")) for g in group_rows_for(final_answer, "v1")), default=0)
            gold_support = max((_as_int(g.get("support_count")) for g in gold_group_rows), default=0)
            evidence_rows.append(
                {
                    "example_id": key[0],
                    "seed": key[1],
                    "budget": key[2],
                    "answer_group_support_counts": json.dumps(v1_meta.get("answer_group_support_counts", {}), sort_keys=True),
                    "answer_group_maturity": json.dumps({g.get("answer_group"): g.get("maturity") for g in v1_groups}, sort_keys=True),
                    "answer_group_family_counts": json.dumps({g.get("answer_group"): g.get("family_counts") for g in v1_groups}, sort_keys=True),
                    "frontier_candidate_answer": row["frontier_candidate_answer"],
                    "frontier_support": v1_meta.get("frontier_support", row.get("override_margin")),
                    "incumbent_support": v1_meta.get("incumbent_support", ""),
                    "support_margin": v1_meta.get("support_margin", row.get("override_margin")),
                    "maturity_margin": v1_meta.get("maturity_margin", ""),
                    "branch_ids_supporting_l1_answer": sorted(set(x for x in l1_branch_ids if x)),
                    "branch_ids_supporting_frontier_answer": sorted(set(x for x in frontier_branch_ids if x)),
                    "l1_answer_group_depth_max": max((_as_int(g.get("depth_max")) for g in l1_group_rows), default=0),
                    "frontier_answer_group_depth_max": max((_as_int(g.get("depth_max")) for g in frontier_group_rows), default=0),
                    "l1_answer_appeared_in_frontier_support": int(l1 in all_group_keys),
                    "gold_answer_appeared_in_frontier_support": int(gold in all_group_keys),
                    "output_repair_changed_final_answer": int(output_repair),
                    "wrong_frontier_answer_higher_support_than_gold": int(final_answer != gold and final_support > gold_support),
                    "frontier_collapsed_to_one_wrong_answer_family": int(final_answer != gold and max((_as_int(g.get("family_count")) for g in v1_groups), default=0) <= 1),
                    "short_branch_trace_summary": _branch_summary(
                        branches_by[(key[0], key[1], key[2], "direct_reserve_frontier_gate_v1")]
                    ),
                }
            )
        if case["frontier_beats_l1"]:
            frontier_better_rows.append(case)

    _write_csv(out_dir / "case_level_comparison.csv", case_rows)
    _write_csv(out_dir / "l1_beats_strict_f3_cases.csv", [r for r in case_rows if _as_int(r["l1_beats_strict_f3"])])
    _write_csv(out_dir / "l1_beats_v1_cases.csv", [r for r in case_rows if _as_int(r["l1_beats_v1"])])
    _write_csv(out_dir / "frontier_beats_l1_cases.csv", frontier_better_rows)
    _write_csv(out_dir / "qualitative_failure_labels.csv", label_rows)
    _write_csv(out_dir / "branch_evidence_for_l1_better_cases.csv", evidence_rows)

    label_counts = Counter(r["failure_label"] for r in label_rows)
    l1_better_union = [r for r in case_rows if _as_int(r["external_l1_max_correct"]) and (not _as_int(r["strict_f3_correct"]) or not _as_int(r["direct_reserve_frontier_gate_v1_correct"]) or not _as_int(r["near_direct_reserve_frontier_gate_v1_correct"]))]
    evidence_by_key = {_key(r): r for r in evidence_rows}
    gold_absent = sum(_as_int(r.get("gold_answer_appeared_in_frontier_support")) == 0 for r in evidence_rows)
    l1_present_not_selected = sum(_as_int(r.get("l1_answer_appeared_in_frontier_support")) and _norm(next((c["strict_f3_prediction"] for c in case_rows if _key(c) == _key(r)), "")) != _norm(next((c["external_l1_max_prediction"] for c in case_rows if _key(c) == _key(r)), "")) for r in evidence_rows)
    wrong_over = sum(_as_int(r.get("wrong_frontier_answer_higher_support_than_gold")) for r in evidence_rows)
    summary = {
        "matched_examples": len(case_rows),
        "external_l1_max_accuracy": sum(_as_int(r["external_l1_max_correct"]) for r in case_rows) / max(1, len(case_rows)),
        "strict_f3_accuracy": sum(_as_int(r["strict_f3_correct"]) for r in case_rows) / max(1, len(case_rows)),
        "direct_reserve_frontier_gate_v1_accuracy": sum(_as_int(r["direct_reserve_frontier_gate_v1_correct"]) for r in case_rows) / max(1, len(case_rows)),
        "direct_reserve_frontier_gate_v2_accuracy": sum(_as_int(r["direct_reserve_frontier_gate_v2_correct"]) for r in case_rows) / max(1, len(case_rows)),
        "near_direct_reserve_frontier_gate_v1_accuracy": sum(_as_int(r["near_direct_reserve_frontier_gate_v1_correct"]) for r in case_rows) / max(1, len(case_rows)),
        "calibrated_near_direct_frontier_gate_v1_accuracy": sum(_as_int(r["calibrated_near_direct_frontier_gate_v1_correct"]) for r in case_rows) / max(1, len(case_rows)),
        "l1_better_than_strict_f3_cases": sum(_as_int(r["l1_beats_strict_f3"]) for r in case_rows),
        "frontier_better_than_l1_cases": len(frontier_better_rows),
        "both_wrong_cases": sum(_as_int(r["both_wrong"]) for r in case_rows),
        "l1_better_union_cases": len(l1_better_union),
        "gold_absent_from_frontier_in_l1_better_cases": gold_absent,
        "l1_answer_present_but_not_selected_in_l1_better_cases": l1_present_not_selected,
        "wrong_frontier_answer_more_supported_than_gold": wrong_over,
        "top_3_failure_labels": label_counts.most_common(3),
        "trace_json_file_count": len(trace_paths),
        "trace_index_rows": len(trace_index),
        "trace_json_collision_note": "trace JSON filenames are example/method-qualified, not seed/budget-qualified; CSV tables and per_example_records are authoritative.",
        "recommended_next_algorithmic_fix": "better direct preservation plus verifier/answer selection calibration; gold is present in the traced frontier support for these L1-better cases, so selection/preservation is the immediate bottleneck.",
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    md_lines = [
        "# L1 Better Than Frontier Casebook",
        "",
        f"- Matched examples: {summary['matched_examples']}",
        f"- `external_l1_max` accuracy: {summary['external_l1_max_accuracy']:.4f}",
        f"- `strict_f3` accuracy: {summary['strict_f3_accuracy']:.4f}",
        f"- `direct_reserve_frontier_gate_v1` accuracy: {summary['direct_reserve_frontier_gate_v1_accuracy']:.4f}",
        f"- L1-better union cases: {summary['l1_better_union_cases']}",
        "",
    ]
    for case in l1_better_cases:
        e = evidence_by_key.get(_key(case), {})
        top_groups = _top_groups(groups_by[(case["example_id"], case["seed"], case["budget"], "direct_reserve_frontier_gate_v1")])
        md_lines.extend(
            [
                f"## {case['example_id']} seed={case['seed']} budget={case['budget']}",
                "",
                f"Question: {case.get('question') or case.get('question_hash')}",
                f"Gold: `{case['gold_answer']}`",
                f"L1: `{case['external_l1_max_prediction']}` (correct={case['external_l1_max_correct']})",
                f"strict_f3: `{case['strict_f3_prediction']}` (correct={case['strict_f3_correct']})",
                f"guarded frontier v1: `{case['direct_reserve_frontier_gate_v1_prediction']}` (correct={case['direct_reserve_frontier_gate_v1_correct']})",
                f"Gold appeared in frontier: {e.get('gold_answer_appeared_in_frontier_support', '')}",
                f"L1 appeared in frontier: {e.get('l1_answer_appeared_in_frontier_support', '')}",
                f"Top answer groups: {top_groups}",
                f"Branch IDs for L1 answer: {e.get('branch_ids_supporting_l1_answer', [])}",
                f"Branch IDs for frontier answer: {e.get('branch_ids_supporting_frontier_answer', [])}",
                f"Short branch summary: {e.get('short_branch_trace_summary', '')}",
                f"Failure label: `{case['failure_label']}`",
                f"Suggested fix: {case['suggested_fix_category']}",
                "",
            ]
        )
    (out_dir / "manual_review_casebook.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(
        "# L1 Better Than Frontier Casebook\n\n"
        "Offline failure casebook for the traced Cohere GSM8K Stage-1 replay. No API calls were made.\n\n"
        f"- Matched examples: {summary['matched_examples']}\n"
        f"- `external_l1_max` accuracy: {summary['external_l1_max_accuracy']:.4f}\n"
        f"- `strict_f3` accuracy: {summary['strict_f3_accuracy']:.4f}\n"
        f"- `direct_reserve_frontier_gate_v1` accuracy: {summary['direct_reserve_frontier_gate_v1_accuracy']:.4f}\n"
        f"- L1-better-than-strict_f3 cases: {summary['l1_better_than_strict_f3_cases']}\n"
        f"- Frontier-better-than-L1 cases: {summary['frontier_better_than_l1_cases']}\n"
        f"- Both-wrong cases: {summary['both_wrong_cases']}\n"
        f"- Gold absent in L1-better cases: {summary['gold_absent_from_frontier_in_l1_better_cases']}\n"
        f"- L1 answer present but not selected: {summary['l1_answer_present_but_not_selected_in_l1_better_cases']}\n"
        f"- Wrong frontier answer more supported than gold: {summary['wrong_frontier_answer_more_supported_than_gold']}\n"
        f"- Top failure labels: {summary['top_3_failure_labels']}\n\n"
        f"Recommended next algorithmic fix: {summary['recommended_next_algorithmic_fix']}\n",
        encoding="utf-8",
    )
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
