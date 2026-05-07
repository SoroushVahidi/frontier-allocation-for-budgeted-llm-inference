#!/usr/bin/env python3
"""Offline PAL path-coverage counterfactual analysis (no API)."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from experiments.output_layer_repair import canonicalize_answer
from experiments.pal_executor import extract_pal_stdout_numeric_candidate
from experiments.frontier_max_support_tiebreak import normalize_answer_group_key


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _to_int(v: Any) -> int:
    try:
        return int(float(str(v)))
    except Exception:
        return 0


def _norm(v: Any) -> str:
    return str(v if v is not None else "").strip()


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _extract_candidate_texts_from_obj(v: Any) -> list[str]:
    out: list[str] = []
    if isinstance(v, dict):
        for k in ("predicted_answer", "trace_extracted_answer", "extracted_answer", "answer", "final_answer"):
            s = _norm(v.get(k))
            if s:
                out.append(s)
    return out


def _candidate_match_gold(ans: str, gcan: str) -> bool:
    if not ans or not gcan:
        return False
    return canonicalize_answer(ans, dataset="openai/gsm8k") == gcan


def _regret_bucket(cb: dict[str, str]) -> str:
    ext = _to_int(cb.get("external_exact") or cb.get("external_l1_max_exact"))
    pal = _to_int(cb.get("pal_exact"))
    if ext and pal:
        return "both_correct"
    if ext and not pal:
        return "external_only"
    if pal and not ext:
        return "pal_only"
    return "both_wrong"


def _index_pal(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in _iter_jsonl(path):
        eid = _norm(row.get("example_id") or row.get("case_id"))
        if eid:
            out[eid] = row
    return out


def _extract_provenance_candidates(md: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {
        "selector_pool": [],
        "direct_attempts": [],
        "final_branch_states": [],
        "branch_states": [],
        "action_trace": [],
        "frontier_action_trace": [],
        "pal_execution": [],
    }
    # Selector pool
    for row in _as_list(md.get("selector_candidate_pool")):
        out["selector_pool"].extend(_extract_candidate_texts_from_obj(row))
    # Direct reserve attempts
    for row in _as_list(md.get("direct_reserve_attempts")):
        out["direct_attempts"].extend(_extract_candidate_texts_from_obj(row))
    # Branch states
    for row in _as_list(md.get("final_branch_states")):
        out["final_branch_states"].extend(_extract_candidate_texts_from_obj(row))
    for row in _as_list(md.get("branch_states")):
        out["branch_states"].extend(_extract_candidate_texts_from_obj(row))
    # Action traces
    for row in _as_list(md.get("action_trace")):
        out["action_trace"].extend(_extract_candidate_texts_from_obj(row))
    fm = md.get("frontier_metadata")
    if isinstance(fm, dict):
        for row in _as_list(fm.get("action_trace")):
            out["frontier_action_trace"].extend(_extract_candidate_texts_from_obj(row))
    # PAL execution
    px = md.get("pal_execution")
    if isinstance(px, dict):
        per = px.get("pal_execution_result")
        if not isinstance(per, dict):
            per = {}
        for k in ("pal_candidate_answer",):
            s = _norm(px.get(k))
            if s:
                out["pal_execution"].append(s)
        for k in ("pal_answer_normalized", "pal_answer_raw"):
            s = _norm(per.get(k))
            if s:
                out["pal_execution"].append(s)
        stdout_num = extract_pal_stdout_numeric_candidate(_norm(per.get("pal_stdout")))
        if stdout_num:
            out["pal_execution"].append(stdout_num)
    return out


def run_counterfactual(casebook_path: Path, pal_results_path: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cb_rows = _read_csv_rows(casebook_path)
    pal_by_id = _index_pal(pal_results_path)

    coverage_rows: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()
    cf_counts: Counter[str] = Counter()
    gate_counts: Counter[str] = Counter()

    for cb in cb_rows:
        bucket = _regret_bucket(cb)
        if bucket not in {"external_only", "both_wrong"}:
            continue
        bucket_counts[bucket] += 1
        eid = _norm(cb.get("example_id") or cb.get("case_id"))
        gold = _norm(cb.get("gold_answer"))
        gcan = canonicalize_answer(gold, dataset="openai/gsm8k") if gold else ""
        pal_row = pal_by_id.get(eid, {})
        md = pal_row.get("result_metadata")
        if not isinstance(md, dict):
            md = {}
        prov = _extract_provenance_candidates(md)

        pool_vals = prov["selector_pool"]
        trace_vals = (
            prov["direct_attempts"]
            + prov["final_branch_states"]
            + prov["branch_states"]
            + prov["action_trace"]
            + prov["frontier_action_trace"]
        )
        exec_vals = prov["pal_execution"]
        all_vals = pool_vals + trace_vals + exec_vals

        gold_pool = int(any(_candidate_match_gold(a, gcan) for a in pool_vals))
        gold_trace = int(any(_candidate_match_gold(a, gcan) for a in trace_vals))
        gold_exec = int(any(_candidate_match_gold(a, gcan) for a in exec_vals))
        gold_any = int(any(_candidate_match_gold(a, gcan) for a in all_vals))
        gold_absent_everywhere = int(gold_any == 0)

        available_not_pool = int(gold_any == 1 and gold_pool == 0)
        likely_selection_overlay_loss = int(gold_pool == 1 and _to_int(cb.get("pal_exact")) == 0)
        likely_upstream_generation_loss = int(gold_absent_everywhere == 1)

        pool_groups = {
            normalize_answer_group_key(_norm(a)) or "__unknown__"
            for a in pool_vals
            if _norm(a)
        }
        low_div = int(len(pool_groups) <= 1)
        would_trigger = int(gold_pool == 0 and low_div == 1)
        trace_nonpool_groups = {
            normalize_answer_group_key(_norm(a)) or "__unknown__"
            for a in trace_vals
            if _norm(a)
        } - pool_groups
        recoverable_if_trigger = int(would_trigger == 1 and gold_trace == 1 and bool(trace_nonpool_groups))

        if available_not_pool:
            cf_counts["gold_available_somewhere_not_selector_pool"] += 1
        if gold_absent_everywhere:
            cf_counts["gold_absent_everywhere_detectable"] += 1
        if likely_selection_overlay_loss:
            cf_counts["selection_or_overlay_likely_loss"] += 1
        if likely_upstream_generation_loss:
            cf_counts["upstream_generation_likely_loss"] += 1
        gate_counts["would_trigger"] += would_trigger
        gate_counts["recoverable_if_trigger"] += recoverable_if_trigger

        row = {
            "example_id": eid,
            "bucket": bucket,
            "pal_exact": _to_int(cb.get("pal_exact")),
            "external_exact": _to_int(cb.get("external_exact") or cb.get("external_l1_max_exact")),
            "pal_overlay_triggered": _to_int(cb.get("pal_overlay_triggered")),
            "gold_in_selector_pool": gold_pool,
            "gold_in_trace_candidates": gold_trace,
            "gold_in_execution_output": gold_exec,
            "gold_absent_everywhere_detectable": gold_absent_everywhere,
            "gold_available_somewhere_not_selector_pool": available_not_pool,
            "selection_or_overlay_likely_loss": likely_selection_overlay_loss,
            "upstream_generation_likely_loss": likely_upstream_generation_loss,
            "discovery_first_gate_would_trigger": would_trigger,
            "discovery_first_gate_recoverable_if_trigger": recoverable_if_trigger,
            "selector_pool_unique_groups": len(pool_groups),
            "trace_nonpool_unique_groups": len(trace_nonpool_groups),
        }
        coverage_rows.append(row)
        if available_not_pool or gold_absent_everywhere or recoverable_if_trigger:
            if len(anchors) < 80:
                anchors.append(row)

    summary = {
        "meta": {
            "casebook_path": str(casebook_path.resolve()),
            "pal_results_path": str(pal_results_path.resolve()),
            "output_dir": str(output_dir.resolve()),
            "api_calls": "none",
        },
        "focus_rows": len(coverage_rows),
        "bucket_counts_focus": dict(bucket_counts),
        "counterfactual_counts": dict(cf_counts),
        "discovery_first_gate": {
            "would_trigger": int(gate_counts["would_trigger"]),
            "recoverable_if_trigger": int(gate_counts["recoverable_if_trigger"]),
        },
        "dominant_root_cause": (
            max(cf_counts.items(), key=lambda kv: kv[1])[0] if cf_counts else "insufficient_data"
        ),
    }

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (output_dir / "coverage_table.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = list(coverage_rows[0].keys()) if coverage_rows else ["example_id"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        if coverage_rows:
            w.writerows(coverage_rows)
    with (output_dir / "anchor_cases.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = list(anchors[0].keys()) if anchors else ["example_id"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        if anchors:
            w.writerows(anchors)

    lines = [
        "# Offline PAL path coverage counterfactual",
        "",
        f"- Focus rows (external_only + both_wrong): **{summary['focus_rows']}**",
        f"- Bucket counts: `{summary['bucket_counts_focus']}`",
        f"- Counterfactual counts: `{summary['counterfactual_counts']}`",
        f"- Discovery-first gate would trigger: **{summary['discovery_first_gate']['would_trigger']}**",
        f"- Discovery-first gate recoverable-if-trigger: **{summary['discovery_first_gate']['recoverable_if_trigger']}**",
        f"- Dominant root cause: **{summary['dominant_root_cause']}**",
        "- API calls: none",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> None:
    repo = Path.cwd()
    default_dir = repo / "outputs" / "cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z"
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--casebook", type=Path, default=default_dir / "paired_casebook.csv")
    p.add_argument("--pal-results", type=Path, dest="pal_results", default=default_dir / "pal_results.jsonl")
    p.add_argument(
        "--output-dir",
        type=Path,
        default=repo / "outputs" / "offline_pal_path_coverage_counterfactual_20260506",
    )
    args = p.parse_args()
    out = run_counterfactual(args.casebook, args.pal_results, args.output_dir)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
