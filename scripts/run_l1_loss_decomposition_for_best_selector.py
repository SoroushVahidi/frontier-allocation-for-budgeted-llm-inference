#!/usr/bin/env python3
"""Orchestrate real Cohere validation + L1 vs DR-v2(+best selector) loss decomposition artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


METHOD_L1 = "external_l1_max"
METHOD_DRV2 = "direct_reserve_semantic_frontier_v2"
METHOD_OV = "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1"
METHOD_PRM = "direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1"
METHOD_SFIX = "direct_reserve_semantic_frontier_v2_selection_fix_v1"

FALLBACK_ORDER = [METHOD_OV, METHOD_PRM, METHOD_SFIX]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="L1 loss decomposition for best DR-v2 selector lane (real Cohere path)")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--provider", default="cohere")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--split", default="test", help="Documentary; GSM8K loader uses dataset default split (typically test).")
    p.add_argument("--seed", type=int, default=20260501)
    p.add_argument("--budget", type=int, default=4)
    p.add_argument("--target-scored", type=int, default=100)
    p.add_argument("--cohere-model", default="command-a-03-2025")
    p.add_argument("--allow-api", action="store_true")
    p.add_argument("--max-calls", type=int, default=600, dest="max_calls", help="Hard cap on cumulative API calls (generator-level).")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--output-dir", default="", help="Artifact root (default outputs/l1_loss_decomposition_best_selector_<timestamp>)")
    return p.parse_args()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def estimate_calls_per_paired_case_three_lane(*, budget: int) -> int:
    """Conservative estimate of generator api_calls for one paired instance (all three methods)."""
    base = max(10, min(96, 8 + budget * 7))
    selector_overhead = max(8, budget * 4)
    return base + base + (base + selector_overhead)


def slice_scored_count(rows: list[dict[str, Any]], *, method: str) -> int:
    return sum(1 for r in rows if r.get("method") == method and int(r.get("scored", 0)) == 1)


def mock_ov_signals(rows: list[dict[str, Any]]) -> bool:
    """True if OV lane rows indicate mock verifier while env asks for cohere."""
    backend_env = (os.getenv("DR_V2_OV_RERANK_VERIFIER_BACKEND") or "").strip().lower()
    if backend_env != "cohere":
        return False
    for r in rows:
        if r.get("method") != METHOD_OV or int(r.get("scored", 0)) != 1:
            continue
        md = r.get("result_metadata") or {}
        if str(md.get("verifier_backend") or "").strip().lower() == "mock":
            return True
        vr = md.get("ov_rerank_verifier_results") or {}
        if isinstance(vr, dict):
            for payload in vr.values():
                if isinstance(payload, dict) and "deterministic_mock" in str(payload.get("short_reason", "")).lower():
                    return True
    return False


def group_by_case(rows: list[dict[str, Any]]) -> dict[tuple[str, str, int, int, str], dict[str, dict[str, Any]]]:
    out: dict[tuple[str, str, int, int, str], dict[str, dict[str, Any]]] = {}
    for r in rows:
        if int(r.get("scored", 0)) != 1:
            continue
        k = (
            str(r.get("provider", "cohere")),
            str(r.get("dataset", "")),
            int(r.get("seed", 0)),
            int(r.get("budget", 0)),
            str(r.get("example_id", "")),
        )
        out.setdefault(k, {})[str(r.get("method"))] = r
    return out


def classify_loss_bucket(*, l1_row: dict[str, Any], sel_row: dict[str, Any]) -> str:
    """Loss taxonomy among L1-correct / selected-wrong."""
    md = sel_row.get("result_metadata") or {}
    final_nodes = sel_row.get("final_nodes") or []
    pool = md.get("selector_candidate_pool")
    method_id = str(sel_row.get("method") or "")

    if int(sel_row.get("parse_extraction_failure", 0)) == 1:
        return "parse_or_canonicalization_failure"

    trace_missing = (not final_nodes) and (not pool)
    if sel_row.get("status") != "scored":
        return "trace_or_candidate_artifact_missing"
    if trace_missing:
        fr = str(md.get("fallback_reason") or "")
        if "no_candidates" in fr.lower() or "candidate" in fr.lower() and "extract" in fr.lower():
            return "candidate_generation_failed_or_empty"
        return "trace_or_candidate_artifact_missing"

    cache_hint = str(md.get("fallback_reason") or "")
    verifier_calls = int(md.get("verifier_calls") or 0)
    configured_cap = int(md.get("selector_configured_candidate_cap") or 0)
    if (
        "cache" in cache_hint.lower()
        or "cap" in cache_hint.lower()
        or (method_id == METHOD_OV and verifier_calls == 0 and int(md.get("candidate_count") or 0) > 1)
        or (configured_cap > 0 and int(md.get("candidate_count") or 0) >= configured_cap > 0)
    ):
        return "selector_missing_score_or_cache_limited"

    gold_in_tree = int(sel_row.get("gold_in_tree", 0))
    if gold_in_tree == 0:
        return "gold_absent_from_candidate_tree"
    if gold_in_tree == 1:
        return "gold_present_but_not_selected"
    return "unknown"


def paired_stats_from_groups(
    groups: dict[tuple[str, str, int, int, str], dict[str, dict[str, Any]]],
    *,
    selected_method: str,
) -> dict[str, Any]:
    l1_ok_sel_bad: list[tuple[Any, Any]] = []
    sel_ok_l1_bad: list[tuple[Any, Any]] = []
    both_ok: list[tuple[Any, Any]] = []
    both_bad: list[tuple[Any, Any]] = []
    triple_items: list[tuple[Any, Any]] = []
    for _k, m in groups.items():
        l1 = m.get(METHOD_L1)
        dr = m.get(METHOD_DRV2)
        sel = m.get(selected_method)
        if not l1 or not dr or not sel:
            continue
        triple_items.append((_k, m))
        l1c = int(l1.get("exact_match", 0))
        sc = int(sel.get("exact_match", 0))
        if l1c and sc:
            both_ok.append((_k, m))
        elif not l1c and not sc:
            both_bad.append((_k, m))
        elif l1c and not sc:
            l1_ok_sel_bad.append((_k, m))
        elif not l1c and sc:
            sel_ok_l1_bad.append((_k, m))

    def acc(items: list[tuple[Any, Any]], method: str) -> float:
        if not items:
            return 0.0
        return sum(int(x[1][method].get("exact_match", 0)) for x in items) / len(items)

    return {
        "paired_keys": len(triple_items),
        "l1_correct_ours_wrong_count": len(l1_ok_sel_bad),
        "ours_correct_l1_wrong_count": len(sel_ok_l1_bad),
        "both_correct_count": len(both_ok),
        "both_wrong_count": len(both_bad),
        "l1_accuracy": acc(triple_items, METHOD_L1),
        "drv2_accuracy": acc(triple_items, METHOD_DRV2),
        "selected_method_accuracy": acc(triple_items, selected_method),
        "l1_ok_sel_bad_cases": l1_ok_sel_bad,
    }


def main() -> None:
    args = parse_args()
    stamp = args.timestamp.strip()
    if args.output_dir:
        out_root = Path(args.output_dir).expanduser().resolve()
    else:
        out_root = (REPO_ROOT / "outputs" / f"l1_loss_decomposition_best_selector_{stamp}").resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    planned_per_case = estimate_calls_per_paired_case_three_lane(budget=args.budget)
    planned_total = planned_per_case * args.target_scored
    allowed_max = int(args.max_calls)

    call_budget_summary: dict[str, Any] = {
        "planned_calls_per_paired_case_estimate": planned_per_case,
        "planned_calls_for_100": planned_per_case * 100,
        "allowed_max_calls": allowed_max,
        "maximum_feasible_paired_cases": (allowed_max // planned_per_case) if planned_per_case else 0,
        "recommended_max_calls_for_full_100": planned_total,
        "budget_note": "Estimates are conservative; measured api_calls live in validation manifest.",
    }

    target_scored = args.target_scored
    cap_limited = False
    if allowed_max > 0 and planned_total > allowed_max:
        mf = allowed_max // planned_per_case if planned_per_case else 0
        if mf < target_scored:
            target_scored = max(0, mf)
            cap_limited = True
            call_budget_summary["target_scored_adjusted_to"] = target_scored
            call_budget_summary["reason"] = "planned_total exceeds allowed_max_calls"

    write_json(out_root / "call_budget_summary.json", call_budget_summary)

    ready_ok = False
    ready_reason = "skipped_readiness"
    if args.allow_api:
        from scripts.run_cohere_real_model_cost_normalized_validation import ensure_cohere_readiness as _coh_ready

        ready_ok, ready_reason = _coh_ready(model=args.cohere_model, timestamp=stamp)
    write_json(
        out_root / "cohere_readiness_summary.json",
        {
            "cohere_model": args.cohere_model,
            "allow_api": bool(args.allow_api),
            "ready_ok": bool(ready_ok),
            "reason": ready_reason,
            "cohere_api_key_present": bool(os.getenv("COHERE_API_KEY")),
            "hf_token_present": bool(os.getenv("HF_TOKEN")),
        },
    )

    progress = {
        "stage": "init",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_scored_effective": target_scored,
        "cap_limited": cap_limited,
    }
    write_json(out_root / "run_progress_summary.json", progress)

    if not args.allow_api:
        write_json(
            out_root / "selected_method_decision.json",
            {"selected_method": None, "reason": "--allow-api not set", "attempts": []},
        )
        write_json(
            out_root / "l1_loss_decomposition_summary.json",
            {"claim_safety_status": "blocked_no_cohere", "note": "Set --allow-api after exporting credentials."},
        )
        raise SystemExit(0)

    if not ready_ok:
        write_json(
            out_root / "selected_method_decision.json",
            {"selected_method": None, "reason": ready_reason, "attempts": []},
        )
        write_json(out_root / "l1_loss_decomposition_summary.json", {"claim_safety_status": "blocked_no_cohere"})
        raise SystemExit(1)

    if target_scored <= 0:
        write_json(
            out_root / "selected_method_decision.json",
            {"selected_method": None, "reason": "zero feasible paired cases under api call cap", "attempts": []},
        )
        raise SystemExit(1)

    cumulative_calls_used = 0
    chosen_dir: Path | None = None
    chosen_method: str | None = None
    attempts_log: list[dict[str, Any]] = []

    for cand in FALLBACK_ORDER:
        short = {METHOD_OV: "ov", METHOD_PRM: "prm", METHOD_SFIX: "sfix"}[cand]
        val_ts = f"{stamp}_{short}"
        val_dir = REPO_ROOT / "outputs" / f"cohere_real_model_cost_normalized_validation_{val_ts}"
        remaining = max(0, allowed_max - cumulative_calls_used) if allowed_max > 0 else 0
        if allowed_max > 0 and remaining <= 0:
            attempts_log.append({"method": cand, "status": "skipped", "reason": "max-calls already exhausted"})
            break

        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts/run_cohere_real_model_cost_normalized_validation.py"),
            "--timestamp",
            val_ts,
            "--providers",
            args.provider,
            "--datasets",
            args.dataset,
            "--budgets",
            str(args.budget),
            "--seeds",
            str(args.seed),
            "--methods",
            ",".join([METHOD_L1, METHOD_DRV2, cand]),
            "--target-scored-per-slice",
            str(target_scored),
            "--cohere-model",
            args.cohere_model,
            "--resume",
        ]
        if allowed_max > 0:
            cmd.extend(["--max-total-api-calls", str(remaining if remaining > 0 else allowed_max)])

        subprocess.run(cmd, cwd=REPO_ROOT, check=True)

        rows = read_jsonl(val_dir / "per_example_records.jsonl")
        manifest_calls = 0
        mp = val_dir / "manifest.json"
        if mp.exists():
            try:
                manifest_calls = int(json.loads(mp.read_text(encoding="utf-8")).get("total_api_calls_recorded", 0))
            except Exception:
                manifest_calls = sum(int(r.get("api_calls", 0) or 0) for r in rows)
        else:
            manifest_calls = sum(int(r.get("api_calls", 0) or 0) for r in rows)
        cumulative_calls_used += manifest_calls

        complete_l1 = slice_scored_count(rows, method=METHOD_L1) >= target_scored
        complete_drv2 = slice_scored_count(rows, method=METHOD_DRV2) >= target_scored
        complete_sel = slice_scored_count(rows, method=cand) >= target_scored
        mock_ov = cand == METHOD_OV and mock_ov_signals(rows)

        ok = complete_l1 and complete_drv2 and complete_sel and not mock_ov
        attempts_log.append(
            {
                "candidate": cand,
                "validation_dir": str(val_dir.resolve().relative_to(REPO_ROOT.resolve())),
                "complete_l1": complete_l1,
                "complete_drv2": complete_drv2,
                "complete_selector": complete_sel,
                "mock_ov_signals": mock_ov,
                "accepted": ok,
                "manifest_api_calls": manifest_calls,
            }
        )

        if ok:
            chosen_dir = val_dir
            chosen_method = cand
            break

    write_json(
        out_root / "selected_method_decision.json",
        {
            "selected_method": chosen_method,
            "fallback_order": FALLBACK_ORDER,
            "attempts": attempts_log,
            "validation_output_dir": str(chosen_dir.resolve().relative_to(REPO_ROOT.resolve())) if chosen_dir else None,
        },
    )

    if chosen_dir is None or chosen_method is None:
        write_json(
            out_root / "l1_loss_decomposition_summary.json",
            {
                "claim_safety_status": "incomplete_artifacts",
                "bottleneck_conclusion": "inconclusive_due_to_missing_traces",
                "note": "No selector lane completed under fallback rules.",
            },
        )
        raise SystemExit(2)

    rows = read_jsonl(chosen_dir / "per_example_records.jsonl")
    groups = group_by_case(rows)
    groups = {k: v for k, v in groups.items() if METHOD_L1 in v and METHOD_DRV2 in v and chosen_method in v}
    stats = paired_stats_from_groups(groups, selected_method=chosen_method)
    l1_ok_bad = stats.pop("l1_ok_sel_bad_cases")

    buckets: Counter[str] = Counter()
    per_case_rows: list[dict[str, Any]] = []
    for key, m in l1_ok_bad:
        l1r = m[METHOD_L1]
        selr = m[chosen_method]
        bucket = classify_loss_bucket(l1_row=l1r, sel_row=selr)
        buckets[bucket] += 1
        per_case_rows.append(
            {
                "dataset": key[1],
                "example_id": key[4],
                "seed": key[2],
                "budget": key[3],
                "loss_bucket": bucket,
                "l1_exact_match": int(l1r.get("exact_match", 0)),
                "selected_exact_match": int(selr.get("exact_match", 0)),
                "selected_method": chosen_method,
                "failure_tag": selr.get("failure_tag"),
                "gold_in_tree": int(selr.get("gold_in_tree", 0)),
            }
        )

    total_pairs = int(stats["paired_keys"])
    l1_acc = float(stats["l1_accuracy"])
    sel_acc = float(stats["selected_method_accuracy"])
    drv2_acc = float(stats["drv2_accuracy"])
    delta = sel_acc - l1_acc

    wins = losses = ties = 0
    for _k, m in groups.items():
        l1 = m.get(METHOD_L1)
        sel = m.get(chosen_method)
        if not l1 or not sel:
            continue
        a = int(l1.get("exact_match", 0))
        b = int(sel.get("exact_match", 0))
        if b > a:
            wins += 1
        elif b < a:
            losses += 1
        else:
            ties += 1

    cov_status = "full" if total_pairs >= target_scored and not cap_limited else "partial"

    evidence_100 = total_pairs >= 100 and target_scored >= 100 and not cap_limited
    claim_status = "evidence_complete_100case" if evidence_100 else "diagnostic_only"
    if cap_limited:
        claim_status = "cap_limited_partial_run"

    absent_c = int(buckets.get("gold_absent_from_candidate_tree", 0))
    present_c = int(buckets.get("gold_present_but_not_selected", 0))
    parse_c = int(buckets.get("parse_or_canonicalization_failure", 0))
    sel_miss_c = int(buckets.get("selector_missing_score_or_cache_limited", 0))
    cand_empty_c = int(buckets.get("candidate_generation_failed_or_empty", 0))
    trace_c = int(buckets.get("trace_or_candidate_artifact_missing", 0))
    unknown_c = int(buckets.get("unknown", 0))

    denom = max(1, stats["l1_correct_ours_wrong_count"])
    mixed_abs_present = absent_c > 0 and present_c > 0
    if stats["l1_correct_ours_wrong_count"] == 0:
        bottleneck = "inconclusive_due_to_small_n"
    elif absent_c >= present_c and absent_c > 0:
        bottleneck = "discovery_coverage_dominant"
    elif present_c > absent_c:
        bottleneck = "selection_dominant"
    elif mixed_abs_present:
        bottleneck = "mixed"
    elif trace_c + cand_empty_c > 0 and (absent_c + present_c) == 0:
        bottleneck = "inconclusive_due_to_missing_traces"
    else:
        bottleneck = "mixed"

    recoveries = breaks = 0
    for _k, m in groups.items():
        dr = m.get(METHOD_DRV2)
        sel = m.get(chosen_method)
        if not dr or not sel:
            continue
        d = int(dr.get("exact_match", 0))
        s = int(sel.get("exact_match", 0))
        if d == 0 and s == 1:
            recoveries += 1
        if d == 1 and s == 0:
            breaks += 1

    drv2_correct = sum(1 for _k, m in groups.items() if int(m.get(METHOD_DRV2, {}).get("exact_match", 0)) == 1)
    breaks_on_dr2_correct = sum(
        1
        for _k, m in groups.items()
        if int(m.get(METHOD_DRV2, {}).get("exact_match", 0)) == 1 and int(m.get(chosen_method, {}).get("exact_match", 0)) == 0
    )
    break_rate_drv2 = (breaks_on_dr2_correct / drv2_correct) if drv2_correct else 0.0

    avg_cand = 0.0
    avg_unique = 0.0
    n_md = 0
    for _k, m in groups.items():
        sel = m.get(chosen_method)
        if not sel:
            continue
        md = (sel.get("result_metadata") or {}) if isinstance(sel.get("result_metadata"), dict) else {}
        fn = sel.get("final_nodes") or []
        pool = md.get("selector_candidate_pool")
        if isinstance(pool, list):
            avg_cand += len(pool)
            n_md += 1
            norms = {str((x or {}).get("predicted_answer") or "") for x in pool}
            avg_unique += len([x for x in norms if x])
        elif fn:
            avg_cand += len(fn)
            n_md += 1
            norms = {str(x.get("predicted_answer_normalized") or "") for x in fn}
            avg_unique += len([x for x in norms if x])
    if n_md:
        avg_cand /= n_md
        avg_unique /= n_md

    summary = {
        "total_paired_cases": total_pairs,
        "target_paired_cases": args.target_scored,
        "l1_accuracy": l1_acc,
        "drv2_accuracy": drv2_acc,
        "selected_method_accuracy": sel_acc,
        "selected_method": chosen_method,
        "l1_correct_ours_wrong_count": stats["l1_correct_ours_wrong_count"],
        "ours_correct_l1_wrong_count": stats["ours_correct_l1_wrong_count"],
        "both_correct_count": stats["both_correct_count"],
        "both_wrong_count": stats["both_wrong_count"],
        "selected_method_vs_l1_delta_accuracy": delta,
        "selected_method_vs_l1_wins": wins,
        "selected_method_vs_l1_ties": ties,
        "selected_method_vs_l1_losses": losses,
        "gold_absent_from_candidate_tree_count": absent_c,
        "gold_present_but_not_selected_count": present_c,
        "parse_or_canonicalization_failure_count": parse_c,
        "selector_missing_score_or_cache_limited_count": sel_miss_c,
        "candidate_generation_failed_or_empty_count": cand_empty_c,
        "trace_or_candidate_artifact_missing_count": trace_c,
        "unknown_count": unknown_c,
        "percent_gold_absent_from_candidate_tree": absent_c / denom,
        "percent_gold_present_but_not_selected": present_c / denom,
        "selector_recovery_count_vs_base_drv2": recoveries,
        "selector_break_count_vs_base_drv2": breaks,
        "selector_net_fixes_minus_breaks_vs_base_drv2": recoveries - breaks,
        "selector_break_rate_on_drv2_correct_cases": break_rate_drv2,
        "average_candidate_count": avg_cand,
        "average_unique_answer_count": avg_unique,
        "score_coverage_status": cov_status,
        "claim_safety_status": claim_status,
        "bottleneck_conclusion": bottleneck,
        "canonical_seed": args.seed,
        "canonical_budget": args.budget,
        "dataset_split_documentation": {"dataset": args.dataset, "split_requested": args.split},
    }

    write_json(out_root / "l1_loss_decomposition_summary.json", summary)
    write_csv(out_root / "per_case_l1_loss_decomposition.csv", per_case_rows)
    with (out_root / "per_case_l1_loss_decomposition.jsonl").open("w", encoding="utf-8") as f:
        for row in per_case_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    sum_csv_row = {**summary}
    write_csv(out_root / "l1_loss_decomposition_summary.csv", [sum_csv_row])

    report_lines = [
        "# L1 loss decomposition (best DR-v2 selector lane)",
        "",
        f"- Timestamp: `{stamp}`",
        f"- Selected method: `{chosen_method}`",
        f"- Paired cases (usable): **{total_pairs}**",
        f"- Target: **{args.target_scored}**",
        f"- L1 accuracy: **{l1_acc:.4f}**",
        f"- Selected accuracy: **{sel_acc:.4f}**",
        f"- Δ (selected − L1): **{delta:+.4f}**",
        "",
        "## Loss buckets among L1-correct / selected-wrong",
        "",
        "| Bucket | Count |",
        "|---|---:|",
        f"| gold_absent_from_candidate_tree | {absent_c} |",
        f"| gold_present_but_not_selected | {present_c} |",
        f"| parse_or_canonicalization_failure | {parse_c} |",
        f"| selector_missing_score_or_cache_limited | {sel_miss_c} |",
        f"| trace_or_candidate_artifact_missing | {trace_c} |",
        f"| unknown | {unknown_c} |",
        "",
        f"- Bottleneck conclusion: **{bottleneck}**",
        f"- Claim safety status: **{claim_status}**",
        "",
    ]
    (out_root / "l1_loss_decomposition_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    def write_casebook(name: str, pred: Callable[[dict[str, Any]], bool]) -> None:
        rs = [r for r in per_case_rows if pred(r)]
        p = out_root / name
        with p.open("w", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    write_casebook("casebook_l1_correct_ours_wrong.jsonl", lambda r: True)
    write_casebook(
        "casebook_gold_absent_from_tree.jsonl",
        lambda r: r["loss_bucket"] == "gold_absent_from_candidate_tree",
    )
    write_casebook(
        "casebook_gold_present_but_not_selected.jsonl",
        lambda r: r["loss_bucket"] == "gold_present_but_not_selected",
    )
    write_casebook(
        "casebook_selector_missing_score_or_cache_limited.jsonl",
        lambda r: r["loss_bucket"] == "selector_missing_score_or_cache_limited",
    )
    write_casebook(
        "casebook_trace_missing_or_unknown.jsonl",
        lambda r: r["loss_bucket"] in {"trace_or_candidate_artifact_missing", "unknown"},
    )

    progress["stage"] = "completed"
    progress["final_output_dir"] = str(out_root.resolve().relative_to(REPO_ROOT.resolve()))
    write_json(out_root / "run_progress_summary.json", progress)


if __name__ == "__main__":
    main()
