#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_METHODS = [
    "external_l1_max",
    "direct_reserve_semantic_frontier_v2",
    "direct_reserve_semantic_frontier_v2_selection_fix_v1",
    "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build outcome-verifier rerank diagnostics from validation artifacts.")
    p.add_argument("--artifact-dir", required=True, help="outputs/cohere_real_model_cost_normalized_validation_<timestamp>")
    p.add_argument("--report-path", default="", help="Optional docs markdown output path.")
    p.add_argument("--timestamp", default="", help="Run timestamp label; inferred from artifact directory if omitted.")
    return p.parse_args()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _mean(vals: list[float]) -> float | None:
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def _infer_timestamp(artifact_dir: Path, explicit: str) -> str:
    if explicit:
        return explicit
    prefix = "cohere_real_model_cost_normalized_validation_"
    if artifact_dir.name.startswith(prefix):
        return artifact_dir.name[len(prefix) :]
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _build_rows_by_key(records: list[dict[str, Any]]) -> dict[tuple[str, str, int, int, str], dict[str, dict[str, Any]]]:
    rows_by_key: dict[tuple[str, str, int, int, str], dict[str, dict[str, Any]]] = {}
    for r in records:
        if _safe_int(r.get("scored", 0)) != 1:
            continue
        key = (
            str(r.get("provider", "")),
            str(r.get("dataset", "")),
            _safe_int(r.get("seed", 0)),
            _safe_int(r.get("budget", 0)),
            str(r.get("example_id", "")),
        )
        rows_by_key.setdefault(key, {})[str(r.get("method", ""))] = r
    return rows_by_key


def compute_accuracy_table(scored_by_method: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for method, rows in scored_by_method.items():
        n = len(rows)
        correct = sum(_safe_int(r.get("exact_match", 0)) for r in rows)
        actions: list[float] = []
        toks: list[float] = []
        costs: list[float] = []
        lats: list[float] = []
        for r in rows:
            md = r.get("result_metadata", {}) or {}
            if md.get("actions_used", None) is not None:
                actions.append(_safe_float(md.get("actions_used")))
            if r.get("total_tokens", None) is not None:
                toks.append(_safe_float(r.get("total_tokens")))
            if r.get("estimated_cost_usd", None) is not None:
                costs.append(_safe_float(r.get("estimated_cost_usd")))
            if r.get("latency_seconds", None) is not None:
                lats.append(_safe_float(r.get("latency_seconds")))
        out.append(
            {
                "method": method,
                "scored_count": n,
                "correct_count": correct,
                "incorrect_count": max(0, n - correct),
                "accuracy": (correct / n) if n else 0.0,
                "mean_actions_used": _mean(actions),
                "mean_total_tokens": _mean(toks),
                "mean_estimated_cost_usd": _mean(costs),
                "mean_latency_seconds": _mean(lats),
            }
        )
    return out


def compute_paired_wtl(
    rows_by_key: dict[tuple[str, str, int, int, str], dict[str, dict[str, Any]]],
    method_a: str,
    method_b: str,
) -> dict[str, Any]:
    wins = ties = losses = 0
    deltas: list[float] = []
    for method_map in rows_by_key.values():
        ra = method_map.get(method_a)
        rb = method_map.get(method_b)
        if not ra or not rb:
            continue
        da = _safe_int(ra.get("exact_match", 0))
        db = _safe_int(rb.get("exact_match", 0))
        d = da - db
        deltas.append(float(d))
        if d > 0:
            wins += 1
        elif d < 0:
            losses += 1
        else:
            ties += 1
    matched = len(deltas)
    return {
        "method_a": method_a,
        "method_b": method_b,
        "matched_examples": matched,
        "wins_a": wins,
        "ties": ties,
        "losses_a": losses,
        "win_rate_a": (wins / matched) if matched else 0.0,
        "mean_accuracy_delta_a_minus_b": (sum(deltas) / matched) if matched else 0.0,
    }


def compute_main_question_summary(rows_by_key: dict[tuple[str, str, int, int, str], dict[str, dict[str, Any]]]) -> dict[str, Any]:
    l1_correct_dr_wrong = 0
    had_gold_present = 0
    recovered = 0
    still_missed = 0
    dr_correct_total = 0
    kept_correct = 0
    regressions = 0
    for mm in rows_by_key.values():
        l1 = mm.get("external_l1_max")
        dr = mm.get("direct_reserve_semantic_frontier_v2")
        ov = mm.get("direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1")
        if dr and _safe_int(dr.get("exact_match", 0)) == 1:
            dr_correct_total += 1
            if ov and _safe_int(ov.get("exact_match", 0)) == 1:
                kept_correct += 1
            elif ov and _safe_int(ov.get("exact_match", 0)) == 0:
                regressions += 1
        if not (l1 and dr and ov):
            continue
        if _safe_int(l1.get("exact_match", 0)) == 1 and _safe_int(dr.get("exact_match", 0)) == 0:
            l1_correct_dr_wrong += 1
            md_ov = ov.get("result_metadata", {}) or {}
            present_flag = md_ov.get("ov_rerank_gold_present_in_candidates", None)
            if present_flag is None:
                present_flag = dr.get("gold_in_tree", None)
            if present_flag is not None and _safe_int(present_flag, -1) == 1:
                had_gold_present += 1
            if _safe_int(ov.get("exact_match", 0)) == 1:
                recovered += 1
            else:
                still_missed += 1
    return {
        "l1_correct_dr_v2_wrong_total": l1_correct_dr_wrong,
        "gold_present_in_dr_v2_pool_if_available": had_gold_present,
        "recovered_by_ov_reranker": recovered,
        "still_missed_by_ov_reranker": still_missed,
        "recovery_rate_over_l1_correct_dr_wrong": (recovered / l1_correct_dr_wrong) if l1_correct_dr_wrong else 0.0,
        "dr_v2_correct_total": dr_correct_total,
        "dr_v2_correct_kept_by_ov": kept_correct,
        "dr_v2_correct_regressed_by_ov": regressions,
        "regression_rate_from_dr_v2_correct": (regressions / dr_correct_total) if dr_correct_total else 0.0,
    }


def _failure_category(ov: dict[str, Any], dr: dict[str, Any] | None) -> str:
    if _safe_int(ov.get("exact_match", 0)) == 1:
        return "correct"
    if _safe_int(ov.get("parse_extraction_failure", 0)) == 1:
        return "extraction/canonicalization failure"
    if dr and _safe_int(dr.get("exact_match", 0)) == 1 and _safe_int(ov.get("exact_match", 0)) == 0:
        return "verifier regression"
    if "gold_in_tree" in ov:
        if _safe_int(ov.get("gold_in_tree", 0)) == 0:
            return "correct answer absent from explored tree"
        if _safe_int(ov.get("gold_in_tree", 0)) == 1:
            return "correct answer present but not selected"
    nodes = ov.get("final_nodes", [])
    if not isinstance(nodes, list) or not nodes:
        return "trace missing/unclassifiable"
    return "unknown"


def compute_failure_taxonomy(rows_by_key: dict[tuple[str, str, int, int, str], dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    ctr: Counter[str] = Counter()
    for mm in rows_by_key.values():
        ov = mm.get("direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1")
        dr = mm.get("direct_reserve_semantic_frontier_v2")
        if not ov:
            continue
        ctr[_failure_category(ov, dr)] += 1
    ordered = [
        "correct",
        "correct answer absent from explored tree",
        "correct answer present but not selected",
        "extraction/canonicalization failure",
        "verifier regression",
        "trace missing/unclassifiable",
        "unknown",
    ]
    return [{"category": c, "count": int(ctr.get(c, 0))} for c in ordered]


def compute_selector_diagnostics(rows_by_key: dict[tuple[str, str, int, int, str], dict[str, dict[str, Any]]]) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    parse_failures = 0
    disagreement = 0
    verifier_calls_total = 0
    for key, mm in rows_by_key.items():
        ov = mm.get("direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1")
        if not ov:
            continue
        md = ov.get("result_metadata", {}) or {}
        group_scores = md.get("ov_rerank_group_scores", [])
        top = second = None
        margin = None
        if isinstance(group_scores, list):
            arr = [x for x in group_scores if isinstance(x, dict)]
            arr.sort(key=lambda x: _safe_float(x.get("group_score", -1e9)), reverse=True)
            if arr:
                top = arr[0]
            if len(arr) > 1:
                second = arr[1]
                margin = _safe_float(top.get("group_score", 0.0)) - _safe_float(second.get("group_score", 0.0))
            by_support = sorted(arr, key=lambda x: _safe_int(x.get("original_group_size", 0)), reverse=True)
            if by_support and top and str(top.get("normalized_answer", "")) != str(by_support[0].get("normalized_answer", "")):
                disagreement += 1
        vr = md.get("ov_rerank_verifier_results", {})
        if isinstance(vr, dict):
            for value in vr.values():
                if isinstance(value, dict) and "parse" in str(value.get("short_reason", "")).lower():
                    parse_failures += 1
        verifier_calls_total += _safe_int(md.get("verifier_calls", 0))
        cases.append(
            {
                "provider": key[0],
                "dataset": key[1],
                "seed": key[2],
                "budget": key[3],
                "example_id": key[4],
                "selected_answer_before_rerank": md.get("ov_rerank_original_dr_v2_selected_answer"),
                "selected_answer_after_rerank": md.get("ov_rerank_selected_answer", md.get("selected_normalized_answer")),
                "gold_answer_canonical": ov.get("gold_answer_canonical"),
                "gold_present_in_candidate_pool": md.get("ov_rerank_gold_present_in_candidates"),
                "answer_group_count": md.get("answer_group_count"),
                "selected_group_score": md.get("selected_group_score"),
                "top_group_score": None if not top else top.get("group_score"),
                "second_group_score": None if not second else second.get("group_score"),
                "top2_group_margin": margin,
                "verifier_calls": md.get("verifier_calls"),
                "verifier_backend": md.get("verifier_backend"),
            }
        )
    return {
        "case_rows": cases,
        "summary": {
            "case_count_with_ov_rows": len(cases),
            "verifier_parse_failures": parse_failures,
            "verifier_calls_total": verifier_calls_total,
            "support_count_vs_verifier_disagreement_cases": disagreement,
        },
    }


def available_selector_fields(ov_rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    wanted = [
        "ov_rerank_original_dr_v2_selected_answer",
        "ov_rerank_selected_answer",
        "selected_normalized_answer",
        "gold_answer_canonical",
        "ov_rerank_gold_present_in_candidates",
        "answer_group_count",
        "selected_group_score",
        "ov_rerank_group_scores",
        "ov_rerank_verifier_results",
        "verifier_calls",
        "verifier_backend",
    ]
    present: set[str] = set()
    for r in ov_rows:
        md = r.get("result_metadata", {}) or {}
        for k in wanted:
            if k in md or k in r:
                present.add(k)
    missing = [k for k in wanted if k not in present]
    return sorted(list(present)), missing


def compute_claim_safety(accuracy_table: list[dict[str, Any]], target_scored_per_method: int) -> dict[str, str]:
    if any(_safe_int(r.get("scored_count", 0)) < target_scored_per_method for r in accuracy_table):
        return {"classification": "incomplete_not_claim_safe", "policy_note": "At least one method is below target scored rows."}
    acc = {r["method"]: _safe_float(r["accuracy"], 0.0) for r in accuracy_table}
    ov = acc.get("direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1", 0.0)
    dr = acc.get("direct_reserve_semantic_frontier_v2", 0.0)
    l1 = acc.get("external_l1_max", 0.0)
    if ov <= dr:
        return {"classification": "diagnostic_negative", "policy_note": "Reranker did not improve over original DR-v2."}
    if ov > l1:
        return {"classification": "diagnostic_strong_positive", "policy_note": "Reranker beats external_l1_max on completed run; still diagnostic unless promoted."}
    return {"classification": "diagnostic_positive", "policy_note": "Reranker improves over DR-v2 but does not beat external_l1_max."}


def build_report(artifact_dir: Path, run_timestamp: str, report_path: Path | None = None) -> Path:
    manifest_path = artifact_dir / "manifest.json"
    per_example_path = artifact_dir / "per_example_records.jsonl"
    progress_path = artifact_dir / "progress_heartbeat.jsonl"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = _read_jsonl(per_example_path)
    if not records:
        raise SystemExit(f"No records found at {per_example_path}")

    methods = list(manifest.get("methods", DEFAULT_METHODS))
    target_scored = _safe_int(manifest.get("target_scored_per_slice", 100), 100)
    scored_rows = [r for r in records if _safe_int(r.get("scored", 0)) == 1]
    scored_by_method: dict[str, list[dict[str, Any]]] = {m: [] for m in methods}
    for r in scored_rows:
        scored_by_method.setdefault(str(r.get("method", "")), []).append(r)
    scored_counts = {m: len(scored_by_method.get(m, [])) for m in methods}
    rows_by_key = _build_rows_by_key(scored_rows)

    run_metadata = {
        "timestamp": run_timestamp,
        "provider": ",".join([str(x) for x in manifest.get("providers", sorted({r.get("provider", "") for r in scored_rows}))]),
        "model": json.dumps(manifest.get("models", {}), ensure_ascii=False),
        "dataset": ",".join([str(x) for x in manifest.get("datasets", sorted({r.get("dataset", "") for r in scored_rows}))]),
        "budget": ",".join([str(x) for x in manifest.get("budgets", sorted({_safe_int(r.get("budget", 0)) for r in scored_rows}))]),
        "seed": ",".join([str(x) for x in manifest.get("seeds", sorted({_safe_int(r.get("seed", 0)) for r in scored_rows}))]),
        "methods": ",".join(methods),
        "target_scored_rows_per_method": target_scored,
        "all_methods_reached_target": all(v >= target_scored for v in scored_counts.values()),
    }

    accuracy_table = compute_accuracy_table(scored_by_method)
    paired_table = [
        compute_paired_wtl(rows_by_key, "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1", "direct_reserve_semantic_frontier_v2"),
        compute_paired_wtl(rows_by_key, "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1", "direct_reserve_semantic_frontier_v2_selection_fix_v1"),
        compute_paired_wtl(rows_by_key, "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1", "external_l1_max"),
        compute_paired_wtl(rows_by_key, "direct_reserve_semantic_frontier_v2", "external_l1_max"),
        compute_paired_wtl(rows_by_key, "direct_reserve_semantic_frontier_v2_selection_fix_v1", "external_l1_max"),
    ]
    main_q = compute_main_question_summary(rows_by_key)
    selector_diag = compute_selector_diagnostics(rows_by_key)
    failure_tax = compute_failure_taxonomy(rows_by_key)
    fields_present, fields_missing = available_selector_fields(scored_by_method.get("direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1", []))
    claim = compute_claim_safety(accuracy_table, target_scored)

    cost_table = []
    for method in [
        "direct_reserve_semantic_frontier_v2",
        "direct_reserve_semantic_frontier_v2_selection_fix_v1",
        "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
        "external_l1_max",
    ]:
        rows = scored_by_method.get(method, [])
        n = len(rows)
        tok = sum(_safe_int(r.get("total_tokens", 0)) for r in rows)
        usd = sum(_safe_float(r.get("estimated_cost_usd", 0.0)) for r in rows)
        lat = _mean([_safe_float(r.get("latency_seconds", 0.0)) for r in rows])
        cost_table.append(
            {
                "method": method,
                "scored_count": n,
                "total_tokens": tok,
                "mean_tokens_per_example": (tok / n) if n else 0.0,
                "total_estimated_cost_usd": usd,
                "mean_cost_per_example_usd": (usd / n) if n else 0.0,
                "mean_latency_seconds": lat,
            }
        )
    ov_rows = scored_by_method.get("direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1", [])
    ov_overhead = {
        "ov_verifier_calls_total": sum(_safe_int((r.get("result_metadata", {}) or {}).get("verifier_calls", 0)) for r in ov_rows),
        "ov_total_tokens": sum(_safe_int(r.get("total_tokens", 0)) for r in ov_rows),
        "ov_total_estimated_cost_usd": sum(_safe_float(r.get("estimated_cost_usd", 0.0)) for r in ov_rows),
        "ov_mean_latency_seconds": _mean([_safe_float(r.get("latency_seconds", 0.0)) for r in ov_rows]),
    }

    summary_json = {
        "run_metadata": run_metadata,
        "scored_counts_per_method": scored_counts,
        "accuracy_table": accuracy_table,
        "paired_comparisons": paired_table,
        "main_question_summary": main_q,
        "selector_diagnostics_summary": selector_diag["summary"],
        "selector_fields_present": fields_present,
        "selector_fields_missing": fields_missing,
        "failure_taxonomy": failure_tax,
        "cost_latency_table": cost_table,
        "ov_verifier_overhead": ov_overhead,
        "claim_safety": claim,
        "artifact_files_read": {
            "manifest": str(manifest_path),
            "per_example_records": str(per_example_path),
            "progress_heartbeat": str(progress_path),
        },
    }

    _write_csv(artifact_dir / "ov_rerank_accuracy_table.csv", accuracy_table)
    _write_csv(artifact_dir / "ov_rerank_paired_comparisons.csv", paired_table)
    _write_csv(artifact_dir / "ov_rerank_main_question_table.csv", [main_q])
    _write_csv(artifact_dir / "ov_rerank_failure_taxonomy.csv", failure_tax)
    _write_csv(artifact_dir / "ov_rerank_cost_latency_table.csv", cost_table)
    _write_csv(artifact_dir / "ov_rerank_selector_case_diagnostics.csv", selector_diag["case_rows"])
    (artifact_dir / "ov_rerank_summary.json").write_text(json.dumps(summary_json, indent=2) + "\n", encoding="utf-8")

    if report_path is None:
        report_path = Path("docs") / f"OUTCOME_VERIFIER_RERANK_V1_COHERE_100CASE_RESULTS_{run_timestamp}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def _fmt(v: float | None) -> str:
        if v is None:
            return "NA"
        return f"{v:.4f}"

    lines = [
        "# OUTCOME_VERIFIER_RERANK_V1_COHERE_100CASE_RESULTS",
        "",
        "## Run metadata",
        f"- timestamp: `{run_metadata['timestamp']}`",
        f"- provider: `{run_metadata['provider']}`",
        f"- model(s): `{run_metadata['model']}`",
        f"- dataset(s): `{run_metadata['dataset']}`",
        f"- budget(s): `{run_metadata['budget']}`",
        f"- seed(s): `{run_metadata['seed']}`",
        f"- methods: `{run_metadata['methods']}`",
        f"- target scored rows per method: `{target_scored}`",
        "- actual scored rows per method:",
        *[f"  - {m}: {scored_counts.get(m, 0)}" for m in methods],
        f"- every method reached 100 scored rows: `{bool(run_metadata['all_methods_reached_target'])}`",
        "",
        "## Accuracy table",
        "| method | scored | accuracy | correct | incorrect | mean_actions | mean_tokens | mean_cost | mean_latency |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in accuracy_table:
        lines.append(
            f"| {r['method']} | {r['scored_count']} | {_fmt(_safe_float(r['accuracy']))} | {r['correct_count']} | "
            f"{r['incorrect_count']} | {_fmt(r['mean_actions_used'])} | {_fmt(r['mean_total_tokens'])} | "
            f"{_fmt(r['mean_estimated_cost_usd'])} | {_fmt(r['mean_latency_seconds'])} |"
        )
    lines.extend(
        [
            "",
            "## Paired comparison tables",
            "| method_a | method_b | matched | W | T | L | win_rate_a | delta(a-b) |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for r in paired_table:
        lines.append(
            f"| {r['method_a']} | {r['method_b']} | {r['matched_examples']} | {r['wins_a']} | {r['ties']} | {r['losses_a']} | "
            f"{_fmt(_safe_float(r['win_rate_a']))} | {_fmt(_safe_float(r['mean_accuracy_delta_a_minus_b']))} |"
        )
    lines.extend(
        [
            "",
            "## Main question table",
            f"- total L1-correct / DR-v2-wrong: `{main_q['l1_correct_dr_v2_wrong_total']}`",
            f"- had gold present in DR-v2 pool (if available): `{main_q['gold_present_in_dr_v2_pool_if_available']}`",
            f"- recovered by OV reranker: `{main_q['recovered_by_ov_reranker']}`",
            f"- still missed: `{main_q['still_missed_by_ov_reranker']}`",
            f"- recovery percentage: `{_fmt(_safe_float(main_q['recovery_rate_over_l1_correct_dr_wrong']) * 100.0)}%`",
            "",
            f"- DR-v2 correct cases: `{main_q['dr_v2_correct_total']}`",
            f"- kept correct by OV: `{main_q['dr_v2_correct_kept_by_ov']}`",
            f"- regressed by OV: `{main_q['dr_v2_correct_regressed_by_ov']}`",
            f"- regression percentage: `{_fmt(_safe_float(main_q['regression_rate_from_dr_v2_correct']) * 100.0)}%`",
            "",
            "## Selector-specific diagnostics",
            f"- available fields: `{fields_present}`",
            f"- missing fields: `{fields_missing}`",
            f"- verifier parse failures: `{selector_diag['summary']['verifier_parse_failures']}`",
            f"- verifier calls: `{selector_diag['summary']['verifier_calls_total']}`",
            f"- support/verifier disagreement cases: `{selector_diag['summary']['support_count_vs_verifier_disagreement_cases']}`",
            "",
            "## Failure taxonomy",
        ]
    )
    for r in failure_tax:
        lines.append(f"- {r['category']}: {r['count']}")
    lines.extend(
        [
            "",
            "## Cost and latency table",
            "| method | scored | total_tokens | mean_tokens | total_cost | mean_cost | mean_latency |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for r in cost_table:
        lines.append(
            f"| {r['method']} | {r['scored_count']} | {r['total_tokens']} | {_fmt(_safe_float(r['mean_tokens_per_example']))} | "
            f"{_fmt(_safe_float(r['total_estimated_cost_usd']))} | {_fmt(_safe_float(r['mean_cost_per_example_usd']))} | {_fmt(r['mean_latency_seconds'])} |"
        )
    lines.extend(
        [
            "",
            "## Claim-safety conclusion",
            f"- classification: `{claim['classification']}`",
            f"- note: {claim['policy_note']}",
            "- status posture: diagnostic by default; only canonical if explicitly promoted by repo policy.",
            "",
            "## Machine-readable outputs",
            "- `ov_rerank_summary.json`",
            "- `ov_rerank_accuracy_table.csv`",
            "- `ov_rerank_paired_comparisons.csv`",
            "- `ov_rerank_main_question_table.csv`",
            "- `ov_rerank_failure_taxonomy.csv`",
            "- `ov_rerank_cost_latency_table.csv`",
            "- `ov_rerank_selector_case_diagnostics.csv`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    args = parse_args()
    artifact_dir = Path(args.artifact_dir).resolve()
    ts = _infer_timestamp(artifact_dir, args.timestamp)
    report_path = Path(args.report_path) if args.report_path else None
    written = build_report(artifact_dir=artifact_dir, run_timestamp=ts, report_path=report_path)
    print(f"Wrote {written}")
    print(f"Wrote {artifact_dir / 'ov_rerank_summary.json'}")


if __name__ == "__main__":
    main()
