#!/usr/bin/env python3
"""Gold-absent path-gap proxy diagnostic (estimated gaps, not observed gold paths)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.gold_absent_path_gap import (  # noqa: E402
    INTERNAL_METHOD_DEFAULT,
    closest_candidate_answer_to_gold,
    compute_path_gap_estimates,
    extract_trace_stats_from_record,
    infer_failure_mode_proxy,
    load_per_example_index,
    parse_case_id,
    row_matches_gold_absent_focus,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _bool_str(v: Any) -> str:
    if v is None or v == "":
        return ""
    return str(v)


def discover_jsonl_under_roots(roots: list[Path], max_depth: int = 4) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        root = root.resolve()
        for dirpath, dirnames, filenames in os.walk(root):
            dp = Path(dirpath)
            rel_depth = len(dp.relative_to(root).parts) if dp != root else 0
            if rel_depth > max_depth:
                dirnames[:] = []
                continue
            if "per_example_records.jsonl" in filenames:
                found.append(dp / "per_example_records.jsonl")
    return sorted(set(found))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-cases", type=Path, required=True)
    ap.add_argument("--previous-run-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument(
        "--discovery-jsonl",
        type=Path,
        default=None,
        help="Primary internal method JSONL (direct_reserve_semantic_frontier_v2).",
    )
    ap.add_argument(
        "--trace-roots",
        type=Path,
        nargs="*",
        default=[],
        help="Directories to scan for per_example_records.jsonl (external + supplemental).",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-cases", type=int, default=0)
    ap.add_argument(
        "--allow-paid-diag",
        action="store_true",
        help="Reserved; disabled unless ALLOW_PAID_DIAG=1 (no LLM calls implemented).",
    )
    ap.add_argument("--provider", default="")
    ap.add_argument("--model", default="")
    args = ap.parse_args()

    paid_calls = 0
    if args.allow_paid_diag and os.environ.get("ALLOW_PAID_DIAG") == "1":
        # Bounded hook for future LLM classifier; default zero.
        paid_calls = 0

    inp = args.input_cases.resolve()
    prev = args.previous_run_dir.resolve()
    out = args.output_dir.resolve()
    if not inp.exists():
        print(f"missing_input_cases:{inp}", file=sys.stderr)
        return 2
    if not prev.exists():
        print(f"missing_previous_run_dir:{prev}", file=sys.stderr)
        return 2

    pc_path = prev / "per_case_results.csv"
    if not pc_path.exists():
        print(f"missing_per_case_results_csv:{pc_path}", file=sys.stderr)
        return 2

    default_discovery = REPO_ROOT / "outputs/cohere_real_model_cost_normalized_validation_20260502T210610Z_DISCOVERY/per_example_records.jsonl"
    discovery_jsonl = args.discovery_jsonl.resolve() if args.discovery_jsonl else default_discovery
    trace_roots = [Path(p).resolve() for p in args.trace_roots]
    if not discovery_jsonl.exists():
        print(f"missing_discovery_jsonl:{discovery_jsonl}", file=sys.stderr)
        return 2

    extra_jsonl_paths = discover_jsonl_under_roots(trace_roots)
    all_paths = [discovery_jsonl] + [p for p in extra_jsonl_paths if p.resolve() != discovery_jsonl.resolve()]

    if args.dry_run:
        per_case_rows = _read_csv(pc_path)
        ga = sum(1 for r in per_case_rows if row_matches_gold_absent_focus(r))
        print("dry_run_ok=1")
        print(f"input_cases={inp}")
        print(f"previous_run_dir={prev}")
        print(f"output_dir={out}")
        print(f"discovery_jsonl={discovery_jsonl}")
        print(f"extra_jsonl_candidates={len(extra_jsonl_paths)}")
        print(f"gold_absent_focus_rows={ga}")
        print(f"paid_api_calls_planned={paid_calls}")
        return 0

    out.mkdir(parents=True, exist_ok=True)

    # Index: merge internal + external methods from all paths (later duplicates override earlier)
    methods_load = {"direct_reserve_semantic_frontier_v2", "external_l1_max", "external_l1_exact"}
    merged: dict[tuple[str, str, int, int, str], dict[str, Any]] = {}
    for p in all_paths:
        part = load_per_example_index([p], methods=methods_load)
        merged.update(part)

    per_case_rows = _read_csv(pc_path)
    casebook_by_id = {r.get("case_id", "").strip(): r for r in _read_csv(inp) if r.get("case_id")}

    gold_rows = [r for r in per_case_rows if row_matches_gold_absent_focus(r)]
    if args.max_cases > 0:
        gold_rows = gold_rows[: args.max_cases]

    list_fields = [
        "case_id",
        "dataset",
        "example_id",
        "seed",
        "budget",
        "problem_statement",
        "gold_answer",
        "new_full_pipeline_selected_answer",
        "best_external_method_name",
        "best_external_answer",
        "source_artifact",
        "gold_present_in_candidate_groups",
        "gold_present_in_tree",
        "discovery_failure_gold_absent",
        "candidate_group_count",
        "candidate_count",
        "branch_count",
        "max_depth",
        "mean_depth",
        "total_actions",
        "total_expansions",
        "commit_step",
        "budget_exhausted_or_early_commit",
        "branch_family_count",
        "source_family_count",
        "repeated_same_family_expansion_count",
        "repeated_same_answer_expansion_count",
        "answer_entropy",
        "top1_support",
        "top2_support",
        "top2_support_gap",
        "all_candidate_answer_groups",
        "selected_answer_group",
        "our_final_answer",
    ]

    gold_list_out: list[dict[str, Any]] = []
    per_gap: list[dict[str, Any]] = []
    missing_trace: list[dict[str, str]] = []

    for row in gold_rows:
        cid = row.get("case_id", "").strip()
        cb = dict(casebook_by_id.get(cid, {}))
        base: dict[str, Any] = {k: cb.get(k, row.get(k, "")) for k in list_fields}
        if not base.get("dataset") or not base.get("example_id"):
            parsed = parse_case_id(cid)
            if parsed:
                base["dataset"], base["example_id"], base["seed"], base["budget"] = parsed
        ofa = row.get("new_full_pipeline_selected_answer", "")
        base["our_final_answer"] = ofa
        gold_list_out.append(base)

        parsed = parse_case_id(cid)
        if not parsed:
            missing_trace.append({"case_id": cid, "reason": "unparseable_case_id"})
            continue
        ds, ex, sd, bd = parsed
        int_m = INTERNAL_METHOD_DEFAULT
        ext_m = str(row.get("best_external_method_name") or "external_l1_max").strip() or "external_l1_max"
        if ext_m not in methods_load:
            ext_m = "external_l1_max"

        irec = merged.get((ds, ex, sd, bd, int_m))
        erec = merged.get((ds, ex, sd, bd, ext_m)) or merged.get((ds, ex, sd, bd, "external_l1_exact"))

        ist = extract_trace_stats_from_record(irec)
        est = extract_trace_stats_from_record(erec)

        int_depth_val = ist.get("max_depth_from_trace")
        int_depth: int | None = None
        if int_depth_val not in ("", None):
            try:
                int_depth = int(int_depth_val)
            except (TypeError, ValueError):
                int_depth = None
        if int_depth is None and cb.get("max_depth") not in (None, ""):
            try:
                int_depth = int(float(cb["max_depth"]))
            except (TypeError, ValueError):
                int_depth = None

        ext_depth = est.get("max_depth_from_trace")
        ext_depth = int(ext_depth) if ext_depth != "" and str(ext_depth).isdigit() else None

        int_act = ist.get("action_count_from_trace")
        int_act = int(int_act) if int_act != "" and str(int_act).isdigit() else None
        if int_act is None:
            tas = cb.get("total_actions")
            try:
                int_act = int(float(tas)) if tas not in (None, "") else None
            except (TypeError, ValueError):
                int_act = None
        pu = ist.get("max_actions_used_in_pool")
        try:
            pu_i = int(pu) if pu != "" and pu is not None else None
        except (TypeError, ValueError):
            pu_i = None
        observed_internal_max_actions = max([x for x in (int_act, pu_i) if isinstance(x, int)], default=None)

        ext_act = est.get("action_count_from_trace")
        ext_act = int(ext_act) if ext_act != "" and str(ext_act).isdigit() else None

        pool = []
        rm = irec.get("result_metadata") if isinstance(irec, dict) else {}
        rm = rm if isinstance(rm, dict) else {}
        sp = rm.get("selector_candidate_pool")
        if isinstance(sp, list):
            pool = [x for x in sp if isinstance(x, dict)]

        gold_a = str(row.get("gold_answer") or cb.get("gold_answer") or "").strip()
        closest_ans, closest_dist, closest_kind, closest_dep = closest_candidate_answer_to_gold(pool, gold_a)

        est_miss_d, est_miss_a, gap_src = compute_path_gap_estimates(
            internal_depth=int_depth,
            internal_actions=observed_internal_max_actions,
            closest_branch_depth=closest_dep,
            external_depth=ext_depth,
            external_actions=ext_act,
        )

        src_split = gap_src.split(";")[0] if gap_src else ""
        lf = infer_failure_mode_proxy(
            internal=ist,
            external=est,
            casebook=cb,
            est_depth_src=src_split or gap_src,
            est_act_src=gap_src,
        )

        caveat = (
            "Proxy diagnostic only: no literal gold path observed in-tree; estimates compare "
            "external vs internal structured traces where available."
        )

        diag_row: dict[str, Any] = {
            "case_id": cid,
            "dataset": ds,
            "example_id": ex,
            "seed": sd,
            "budget": bd,
            "problem_statement": row.get("problem_statement", cb.get("problem_statement", "")),
            "gold_answer": gold_a,
            "our_final_answer": base["our_final_answer"],
            "best_external_method_name": ext_m,
            "best_external_answer": row.get("best_external_answer", ""),
            "all_candidate_answer_groups": row.get("candidate_answer_groups", ""),
            "selected_answer_group": row.get("selected_answer_group", ""),
            "observed_internal_max_depth": int_depth if int_depth is not None else "",
            "observed_internal_max_actions": observed_internal_max_actions
            if observed_internal_max_actions is not None
            else "",
            "external_success_depth": ext_depth if ext_depth is not None else "",
            "external_success_action_count": ext_act if ext_act is not None else "",
            "closest_internal_branch_answer": closest_ans if closest_ans else "",
            "closest_internal_answer_distance": closest_dist if closest_dist != "" else "",
            "closest_internal_answer_distance_kind": closest_kind if closest_kind else "",
            "closest_internal_branch_depth": closest_dep if closest_dep is not None else "",
            "estimated_missing_depth_to_gold": est_miss_d if est_miss_d != "" else "",
            "estimated_missing_actions_to_gold": est_miss_a if est_miss_a != "" else "",
            "missing_edges_estimate_source": gap_src,
            "trace_available_internal": ist.get("trace_available", 0),
            "trace_available_external": est.get("trace_available", 0),
            "gold_present_in_candidate_groups": row.get("gold_present_in_candidate_groups", ""),
            "gold_present_in_tree": row.get("gold_present_in_tree", ""),
            "candidate_group_count": row.get("candidate_group_count", cb.get("candidate_group_count", "")),
            "candidate_count": row.get("candidate_count", cb.get("candidate_count", "")),
            "branch_count": cb.get("branch_count", ""),
            "branch_family_count": cb.get("branch_family_count", ""),
            "source_family_count": cb.get("source_family_count", ""),
            "repeated_same_family_expansion_count": cb.get("repeated_same_family_expansion_count", ""),
            "repeated_same_answer_expansion_count": cb.get("repeated_same_answer_expansion_count", ""),
            "answer_entropy": cb.get("answer_entropy", ""),
            "top1_support": cb.get("top1_support", ""),
            "top2_support": cb.get("top2_support", ""),
            "top2_support_gap": cb.get("top2_support_gap", ""),
            "budget_exhausted_or_early_commit": cb.get("budget_exhausted_or_early_commit", ""),
            "insufficient_root_diversity_casebook": cb.get("insufficient_root_diversity", ""),
            "premature_commitment_casebook": cb.get("premature_commitment", ""),
            "likely_failure_mode": lf[0],
            "failure_mode_reason": lf[1],
            "suggested_intervention": lf[2],
            "confidence": lf[3],
            "caveat": caveat,
            "discovery_failure_gold_absent": row.get("discovery_failure_gold_absent", ""),
            "diagnosis": row.get("diagnosis", ""),
        }

        per_gap.append(diag_row)

        if ist.get("trace_available") != 1:
            missing_trace.append({"case_id": cid, "reason": "no_internal_discovery_record"})
        elif est.get("trace_available") != 1:
            missing_trace.append({"case_id": cid, "reason": "no_external_record_for_matching_key"})

    def _median(xs: list[float]) -> str:
        if not xs:
            return ""
        return str(median(xs))

    depths = []
    for r in per_gap:
        try:
            v = r.get("estimated_missing_depth_to_gold")
            if v != "":
                depths.append(float(v))
        except (TypeError, ValueError):
            pass
    acts = []
    for r in per_gap:
        try:
            v = r.get("estimated_missing_actions_to_gold")
            if v != "":
                acts.append(float(v))
        except (TypeError, ValueError):
            pass

    fm_counts: dict[str, int] = {}
    for r in per_gap:
        fm = str(r.get("likely_failure_mode") or "unknown")
        fm_counts[fm] = fm_counts.get(fm, 0) + 1

    def _intish(v: Any) -> int | None:
        try:
            return int(float(str(v).strip())) if str(v).strip() not in ("", "None") else None
        except (TypeError, ValueError):
            return None

    cr_root = cr_prune = cr_idepth = cr_bdiv = cr_rpt = cr_prem = cr_trace = cr_est = 0
    for r in per_gap:
        if r.get("trace_available_internal") != 1:
            cr_trace += 1
        gsrc = str(r.get("missing_edges_estimate_source") or "")
        if "unavailable" in gsrc:
            cr_est += 1
        bf = _intish(r.get("branch_family_count"))
        bc = _intish(r.get("branch_count"))
        ru = _intish(r.get("insufficient_root_diversity_casebook"))
        if bf is not None and bf <= 1:
            cr_root += 1
        elif ru == 1:
            cr_root += 1

        rst = _intish(r.get("repeated_same_family_expansion_count"))
        if rst is not None and rst >= 10:
            cr_rpt += 1

        be = str(r.get("budget_exhausted_or_early_commit") or "").strip().lower()
        pm = _intish(r.get("premature_commitment_casebook"))
        cc = _intish(r.get("candidate_count"))
        if pm == 1:
            cr_prem += 1
        elif be == "early_commit" and cc is not None and cc > 0:
            cr_prem += 1

        ed = _intish(r.get("external_success_depth"))
        od = _intish(r.get("observed_internal_max_depth"))
        if ed is not None and od is not None and ed > od:
            cr_idepth += 1
            if "budget_exhausted" in be:
                cr_prune += 1

        sf = _intish(r.get("source_family_count"))
        if bc is not None and bf is not None and bc >= 6 and bf <= 2 and (sf or 0) <= 3:
            cr_bdiv += 1

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_88_cases": len(per_case_rows),
        "gold_absent_cases": len(gold_rows),
        "cases_with_internal_trace": sum(1 for r in per_gap if r.get("trace_available_internal") == 1),
        "cases_with_external_success_trace": sum(1 for r in per_gap if r.get("trace_available_external") == 1),
        "cases_with_both_internal_and_external_trace": sum(
            1 for r in per_gap if r.get("trace_available_internal") == 1 and r.get("trace_available_external") == 1
        ),
        "cases_with_estimated_missing_depth": sum(1 for r in per_gap if r.get("estimated_missing_depth_to_gold") not in ("", None)),
        "mean_estimated_missing_depth": str(sum(depths) / len(depths)) if depths else "",
        "median_estimated_missing_depth": _median(depths),
        "max_estimated_missing_depth": str(max(depths)) if depths else "",
        "cases_with_estimated_missing_actions": sum(1 for r in per_gap if r.get("estimated_missing_actions_to_gold") not in ("", None)),
        "mean_estimated_missing_actions": str(sum(acts) / len(acts)) if acts else "",
        "median_estimated_missing_actions": _median(acts),
        "max_estimated_missing_actions": str(max(acts)) if acts else "",
        "count_root_seeding_failure": cr_root,
        "count_early_pruning_failure": cr_prune,
        "count_insufficient_depth": cr_idepth,
        "count_insufficient_branch_diversity": cr_bdiv,
        "count_repeated_same_family_overexpansion": cr_rpt,
        "count_premature_commit": cr_prem,
        "count_trace_missing_or_unclassifiable": cr_trace,
        "count_estimate_unavailable": cr_est,
        "caveat": "All path-gap metrics are proxy diagnostics, not observed gold paths in-tree.",
        "expected_paid_api_calls": paid_calls,
        "actual_paid_api_calls": paid_calls,
        "internal_method": INTERNAL_METHOD_DEFAULT,
        "discovery_jsonl": str(discovery_jsonl),
        "merged_jsonl_paths": [str(p) for p in all_paths],
    }

    run_cfg = {
        "input_cases": str(inp),
        "previous_run_dir": str(prev),
        "discovery_jsonl": str(discovery_jsonl),
        "trace_roots": [str(p) for p in trace_roots],
        "merged_jsonl_paths": [str(p) for p in all_paths],
        "dry_run": False,
        "max_cases": args.max_cases,
        "allow_paid_diag": bool(args.allow_paid_diag),
        "provider": args.provider,
        "model": args.model,
    }

    git_sha = ""
    try:
        git_sha = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    manifest = {
        "timestamp_utc": summary["timestamp_utc"],
        "git_commit_sha": git_sha,
        "repo_root": str(REPO_ROOT),
        "purpose": "Gold-absent path-gap proxy diagnostic for 88-case external-loss follow-up.",
        "claim_boundary": summary["caveat"],
        "artifacts": {
            "gold_absent_case_list_csv": str(out / "gold_absent_case_list.csv"),
            "per_case_path_gap_diagnostic_csv": str(out / "per_case_path_gap_diagnostic.csv"),
            "path_gap_summary_json": str(out / "path_gap_summary.json"),
        },
    }

    _write_json(out / "manifest.json", manifest)
    _write_json(out / "run_config.json", run_cfg)
    _write_json(out / "path_gap_summary.json", summary)
    summary_csv_fields = list(summary.keys())
    _write_csv(out / "path_gap_summary.csv", [summary], summary_csv_fields)

    _write_csv(out / "gold_absent_case_list.csv", gold_list_out, list_fields)
    _write_jsonl(out / "gold_absent_case_list.jsonl", gold_list_out)

    gap_fields = sorted({k for r in per_gap for k in r}) if per_gap else []
    _write_csv(out / "per_case_path_gap_diagnostic.csv", per_gap, gap_fields)
    _write_jsonl(out / "per_case_path_gap_diagnostic.jsonl", per_gap)

    _write_csv(out / "missing_trace_cases.csv", missing_trace, ["case_id", "reason"])

    trace_md = "\n".join(
        [
            "# Trace recovery report",
            "",
            f"- Merged JSONL files: **{len(all_paths)}**",
            "",
        ]
        + [f"  - `{p}`" for p in all_paths]
        + [
            "",
            f"- Gold-absent focus cases: **{len(gold_rows)}**",
            f"- Rows with internal trace: **{summary['cases_with_internal_trace']}**",
            f"- Rows with external trace (matched key): **{summary['cases_with_external_success_trace']}**",
            "",
            "External traces require the same `(dataset, example_id, seed, budget)` as the discovery JSONL.",
            "If external rows are missing, path-gap proxies that depend on external depth/action count stay blank.",
            "",
        ]
    )
    (out / "trace_recovery_report.md").write_text(trace_md + "\n", encoding="utf-8")

    report_md = "\n".join(
        [
            "# Gold-absent path-gap proxy report",
            "",
            "**Caveat:** Estimates are *proxy diagnostics*, not literal missing edges on an observed gold path.",
            "",
            "**External trace alignment:** When merging supplemental `per_example_records.jsonl`, depths/models may "
            "differ from the 20260502 DR-v2 discovery run; comparisons are exploratory only.",
            "",
            "## Summary",
            "",
            f"- Total per-case rows in previous run: **{summary['total_88_cases']}**",
            f"- Gold-absent focus cases: **{summary['gold_absent_cases']}**",
            f"- Internal trace present: **{summary['cases_with_internal_trace']}**",
            f"- External trace present (aligned key): **{summary['cases_with_external_success_trace']}**",
            f"- Both traces: **{summary['cases_with_both_internal_and_external_trace']}**",
            f"- Cases with estimated missing depth: **{summary['cases_with_estimated_missing_depth']}**",
            f"- Cases with estimated missing actions: **{summary['cases_with_estimated_missing_actions']}**",
            f"- Paid API calls: **{summary['actual_paid_api_calls']}** (deterministic mode)",
            "",
            "## Failure-mode counts (heuristic, overlapping categories possible)",
            "",
        ]
        + [f"- `{k}`: **{v}**" for k, v in sorted(fm_counts.items())]
        + ["", f"See `{out / 'path_gap_summary.json'}` for numeric aggregates.", ""]
    )
    (out / "path_gap_report.md").write_text(report_md + "\n", encoding="utf-8")

    # run_env.log (no secrets)
    env_ok = {k: ("set" if os.environ.get(k) else "unset") for k in ("ALLOW_PAID_DIAG",)}
    (out / "run_env.log").write_text(
        "\n".join(
            [
                f"timestamp_utc={summary['timestamp_utc']}",
                f"python={sys.version.split()[0]}",
                f"repo_root={REPO_ROOT}",
                f"output_dir={out}",
                f"env_flags={json.dumps(env_ok)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (out / "batch_submission_info.json").write_text(
        json.dumps({"note": "Populate job_id after sbatch from cluster environment."}, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "monitor_log.jsonl").write_text("", encoding="utf-8")

    print(f"wrote_output_dir={out}")
    print(f"gold_absent_cases={len(gold_rows)}")
    print(f"paid_api_calls={paid_calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
