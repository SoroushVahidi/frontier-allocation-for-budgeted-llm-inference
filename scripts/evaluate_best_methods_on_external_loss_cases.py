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

METHOD_ALIASES = {
    "direct_reserve_semantic_frontier_v2": "direct_reserve_semantic_frontier_v2",
    "dr_v2": "direct_reserve_semantic_frontier_v2",
    "strict_f3": "strict_f3",
    "strict_gate1_cap_k6": "strict_gate1_cap_k6",
    "external_l1_max": "external_l1_max",
    "external_l1_exact": "external_l1_exact",
    "external_s1_budget_forcing": "external_s1_budget_forcing",
    "external_tale_prompt_budgeting": "external_tale_prompt_budgeting",
}

TARGET_METHODS = [
    "external_l1_max",
    "direct_reserve_semantic_frontier_v2",
    "strict_f3",
    "strict_gate1_cap_k6",
]

PUSHABLE_OUTPUTS = {
    "best_methods_external_loss_summary.json",
    "best_methods_external_loss_summary.md",
    "best_methods_external_loss_results.csv",
    "selected_100_cases_public_summary.csv",
    "method_accuracy_table.csv",
    "l1_comparison_table.csv",
    "trace_diagnosis_summary.csv",
    "artifact_scan_report.md",
}


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _canon_method(v: str) -> str:
    m = _norm(v).lower()
    return METHOD_ALIASES.get(m, _norm(v))


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except csv.Error:
        raw = path.read_bytes().replace(b"\x00", b"")
        return list(csv.DictReader(raw.decode("utf-8", errors="ignore").splitlines()))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out


def dedupe_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, int, int]] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        key = (_norm(r.get("dataset")), _norm(r.get("example_id")), _safe_int(r.get("seed")), _safe_int(r.get("budget")))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def choose_deployable_answer(case_row: dict[str, Any]) -> str:
    # Gold is never used in deployable selection.
    support = _safe_float(case_row.get("selected_answer_support", 0))
    top1 = _safe_float(case_row.get("top1_support", 0))
    if support >= top1 and _norm(case_row.get("our_final_answer")):
        return _norm(case_row.get("our_final_answer"))
    return _norm(case_row.get("selected_answer_group") or case_row.get("our_final_answer"))


def _load_casebook_rows(base_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    roots = sorted({base_dir, *(p for p in (REPO_ROOT / "outputs").glob("external_loss_casebook_*") if p.is_dir())})
    trace_rows: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []
    used: list[str] = []
    for root in roots:
        t = root / "loss_casebook_trace_complete.csv"
        f = root / "loss_casebook_final_rows_only.csv"
        c = root / "loss_casebook_combined_200.csv"
        if t.exists():
            rows = _read_csv(t)
            for r in rows:
                r["_source_casebook"] = str(root)
                r["_selection_source"] = "trace_complete"
            trace_rows.extend(rows)
            used.append(str(t))
        if f.exists():
            rows = _read_csv(f)
            for r in rows:
                r["_source_casebook"] = str(root)
                r["_selection_source"] = "final_row_only"
            final_rows.extend(rows)
            used.append(str(f))
        elif c.exists():
            rows = _read_csv(c)
            for r in rows:
                src = _norm(r.get("trace_available"))
                r["_source_casebook"] = str(root)
                r["_selection_source"] = "trace_complete" if src in {"1", "true", "True"} else "final_row_only"
            trace_rows.extend([r for r in rows if r["_selection_source"] == "trace_complete"])
            final_rows.extend([r for r in rows if r["_selection_source"] == "final_row_only"])
            used.append(str(c))
    return dedupe_cases(trace_rows), dedupe_cases(final_rows), used


def select_cases(trace_rows: list[dict[str, Any]], final_rows: list[dict[str, Any]], target: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, int]] = set()

    def _add(rows: list[dict[str, Any]]) -> None:
        for r in rows:
            if len(selected) >= target:
                return
            key = (_norm(r.get("dataset")), _norm(r.get("example_id")), _safe_int(r.get("seed")), _safe_int(r.get("budget")))
            if key in seen:
                continue
            seen.add(key)
            selected.append(r)

    _add(trace_rows)
    _add(final_rows)
    return selected, {
        "trace_complete_selected": sum(1 for r in selected if r.get("_selection_source") == "trace_complete"),
        "final_row_only_selected": sum(1 for r in selected if r.get("_selection_source") == "final_row_only"),
    }


def _discover_method_artifacts(search_roots: list[Path]) -> list[Path]:
    patterns = ("per_case_method_results.csv", "loss_casebook_trace_complete.csv")
    found: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.name in patterns:
                found.append(p)
    return sorted(set(found))


def _method_rows_from_loss_casebook(path: Path) -> list[dict[str, Any]]:
    rows = _read_csv(path)
    out: list[dict[str, Any]] = []
    for r in rows:
        for col, method in (
            ("our_final_answer", _canon_method(r.get("our_method_name", "strict_f3"))),
            ("external_l1_max_answer", "external_l1_max"),
            ("best_external_answer", _canon_method(r.get("best_external_method_name", "external_l1_max"))),
        ):
            ans = _norm(r.get(col))
            if not ans:
                continue
            out.append(
                {
                    "dataset": _norm(r.get("dataset")),
                    "example_id": _norm(r.get("example_id")),
                    "seed": _safe_int(r.get("seed")),
                    "budget": _safe_int(r.get("budget")),
                    "method": method,
                    "final_answer": ans,
                    "is_correct": _safe_int(r.get("external_l1_max_correct" if method.startswith("external_") else "our_correct")),
                    "action_count": _safe_int(r.get("total_actions")),
                    "token_estimate": "",
                    "candidate_group_count": _safe_int(r.get("candidate_group_count")),
                    "branch_count": _safe_int(r.get("branch_count")),
                    "max_depth": _safe_int(r.get("max_depth")),
                    "source_artifact": str(path),
                    "reused_or_generated": "reused",
                }
            )
    return out


def _method_rows_from_per_case(path: Path) -> list[dict[str, Any]]:
    rows = _read_csv(path)
    out: list[dict[str, Any]] = []
    for r in rows:
        method = _canon_method(r.get("method", ""))
        if not method:
            continue
        out.append(
            {
                "dataset": _norm(r.get("dataset")),
                "example_id": _norm(r.get("example_id")),
                "seed": _safe_int(r.get("seed")),
                "budget": _safe_int(r.get("budget")),
                "method": method,
                "final_answer": _norm(r.get("final_selected_answer")),
                "is_correct": _safe_int(r.get("is_correct")),
                "action_count": _safe_int(r.get("action_count")),
                "token_estimate": _norm(r.get("token_estimate")),
                "candidate_group_count": _safe_int(r.get("answer_group_count")),
                "branch_count": _safe_int(r.get("candidate_branch_count")),
                "max_depth": 0,
                "source_artifact": str(path),
                "reused_or_generated": "reused",
            }
        )
    return out


def _index_method_rows(artifact_paths: list[Path]) -> dict[tuple[str, str, int, int, str], dict[str, Any]]:
    idx: dict[tuple[str, str, int, int, str], dict[str, Any]] = {}
    for p in artifact_paths:
        rows = _method_rows_from_per_case(p) if p.name == "per_case_method_results.csv" else _method_rows_from_loss_casebook(p)
        for r in rows:
            key = (_norm(r["dataset"]), _norm(r["example_id"]), _safe_int(r["seed"]), _safe_int(r["budget"]), _canon_method(r["method"]))
            prev = idx.get(key)
            if prev is None or (_safe_int(r.get("candidate_group_count")) > _safe_int(prev.get("candidate_group_count"))):
                idx[key] = r
    return idx


def _evaluate_cases(
    selected: list[dict[str, Any]],
    index: dict[tuple[str, str, int, int, str], dict[str, Any]],
    target_methods: list[str],
    default_method: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    detailed: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    missing_calls = 0
    for case in selected:
        ckey = (_norm(case.get("dataset")), _norm(case.get("example_id")), _safe_int(case.get("seed")), _safe_int(case.get("budget")))
        for method in sorted(set(target_methods + [default_method])):
            mkey = (*ckey, method)
            rec = index.get(mkey)
            if rec is None:
                missing_calls += 1
                rec = {
                    "dataset": ckey[0],
                    "example_id": ckey[1],
                    "seed": ckey[2],
                    "budget": ckey[3],
                    "method": method,
                    "final_answer": "",
                    "is_correct": 0,
                    "action_count": 0,
                    "token_estimate": "",
                    "candidate_group_count": 0,
                    "branch_count": 0,
                    "max_depth": 0,
                    "source_artifact": "",
                    "reused_or_generated": "missing",
                }
            is_trace = _norm(case.get("_selection_source")) == "trace_complete"
            support_selector_correct = _safe_int(case.get("selected_answer_group") == case.get("gold_answer")) if is_trace else 0
            oracle_correct = _safe_int(case.get("oracle_selector_correct"))
            detail = {
                "dataset": ckey[0],
                "example_id": ckey[1],
                "seed": ckey[2],
                "budget": ckey[3],
                "selection_source": _norm(case.get("_selection_source")),
                "method": method,
                "final_answer": _norm(rec.get("final_answer")),
                "correctness": _safe_int(rec.get("is_correct")),
                "action_budget_used": _safe_int(rec.get("action_count")),
                "token_or_call_count": _norm(rec.get("token_estimate")),
                "candidate_group_count": _safe_int(rec.get("candidate_group_count")),
                "branch_count": _safe_int(rec.get("branch_count")),
                "max_depth": _safe_int(rec.get("max_depth")),
                "reused_or_generated": _norm(rec.get("reused_or_generated")),
                "source_artifact_or_cache_key": _norm(rec.get("source_artifact")),
                "gold_present_in_candidate_groups": _safe_int(case.get("gold_present_in_candidate_groups")),
                "oracle_selector_correct": oracle_correct,
                "support_family_selector_correct": support_selector_correct,
                "oracle_would_fix": _safe_int(oracle_correct == 1 and _safe_int(rec.get("is_correct")) == 0),
            }
            detailed.append(detail)
            raw_rows.append({**detail, "selected_answer_groups_raw": _norm(case.get("all_candidate_answer_groups"))})
    return detailed, raw_rows, missing_calls


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for r in rows for k in r.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _build_summary(selected: list[dict[str, Any]], details: list[dict[str, Any]], missing_calls: int, default_method: str) -> dict[str, Any]:
    method_acc: dict[str, dict[str, Any]] = {}
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in details:
        by_method[_norm(r["method"])].append(r)
    for m, rows in by_method.items():
        n = len(rows)
        acc = sum(_safe_int(r["correctness"]) for r in rows) / n if n else 0.0
        method_acc[m] = {"cases": n, "accuracy": round(acc, 4)}
    l1_acc = method_acc.get("external_l1_max", {}).get("accuracy", 0.0)
    default_acc = method_acc.get(default_method, {}).get("accuracy", 0.0)
    trace_rows = [r for r in details if r["selection_source"] == "trace_complete"]
    return {
        "selected_case_count": len(selected),
        "trace_complete_selected": sum(1 for r in selected if _norm(r.get("_selection_source")) == "trace_complete"),
        "final_row_only_selected": sum(1 for r in selected if _norm(r.get("_selection_source")) == "final_row_only"),
        "expected_cohere_calls_for_missing_outputs": missing_calls,
        "method_accuracy": method_acc,
        "delta_default_vs_external_l1_max": round(default_acc - l1_acc, 4),
        "selector_recoverable_count": sum(_safe_int(_norm(r.get("gold_present_in_candidate_groups")) == "1") for r in selected),
        "discovery_failure_count": sum(_safe_int(_norm(r.get("gold_present_in_candidate_groups")) != "1") for r in selected),
        "oracle_selector_ceiling_trace": round((sum(_safe_int(r["oracle_selector_correct"]) for r in trace_rows) / len(trace_rows)) if trace_rows else 0.0, 4),
        "avg_candidate_group_count_trace": round((sum(_safe_int(r["candidate_group_count"]) for r in trace_rows) / len(trace_rows)) if trace_rows else 0.0, 4),
        "avg_branch_count_trace": round((sum(_safe_int(r["branch_count"]) for r in trace_rows) / len(trace_rows)) if trace_rows else 0.0, 4),
        "avg_max_depth_trace": round((sum(_safe_int(r["max_depth"]) for r in trace_rows) / len(trace_rows)) if trace_rows else 0.0, 4),
        "breakdown_by_budget": dict(Counter(str(_safe_int(r.get("budget"))) for r in selected)),
        "breakdown_by_seed": dict(Counter(str(_safe_int(r.get("seed"))) for r in selected)),
        "breakdown_by_dataset": dict(Counter(_norm(r.get("dataset")) for r in selected)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-cases", type=int, default=100)
    parser.add_argument("--include-existing-trace-losses", action="store_true")
    parser.add_argument("--loss-casebook-dir", required=True)
    parser.add_argument("--search-roots", nargs="+", default=["outputs", "archive", "logs", "results"])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--provider", default="cohere")
    parser.add_argument("--cohere-model", default="command-r-plus")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cohere-safe-cap", type=int, default=400)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = (REPO_ROOT / args.output_dir).resolve() if not args.output_dir.startswith("/") else Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / "cohere_generation_cache.jsonl"
    default_method = "direct_reserve_semantic_frontier_v2"

    casebook_dir = (REPO_ROOT / args.loss_casebook_dir).resolve() if not args.loss_casebook_dir.startswith("/") else Path(args.loss_casebook_dir)
    trace_rows, final_rows, casebook_files = _load_casebook_rows(casebook_dir)
    if not args.include_existing_trace_losses:
        trace_rows = []
    selected, selected_stats = select_cases(trace_rows, final_rows, args.target_cases)

    search_roots = [(REPO_ROOT / p).resolve() if not p.startswith("/") else Path(p) for p in args.search_roots]
    artifact_paths = _discover_method_artifacts(search_roots)
    artifact_index = _index_method_rows(artifact_paths)
    details, raw_rows, missing_calls = _evaluate_cases(selected, artifact_index, TARGET_METHODS, default_method)

    summary = _build_summary(selected, details, missing_calls, default_method)
    summary["provider"] = args.provider
    summary["cohere_model"] = args.cohere_model
    summary["cohere_cache_path"] = str(cache_path)
    summary["output_dir"] = str(output_dir)
    summary["selected_casebook_files"] = casebook_files
    summary["selected_stats"] = selected_stats

    print(json.dumps({
        "expected_cohere_calls": missing_calls,
        "provider": args.provider,
        "model": args.cohere_model,
        "cache_path": str(cache_path),
        "output_dir": str(output_dir),
        "case_count": len(selected),
    }, indent=2))

    if args.dry_run:
        return
    if missing_calls > args.cohere_safe_cap:
        raise SystemExit(f"Refusing run: expected Cohere calls {missing_calls} exceeds cap {args.cohere_safe_cap}.")

    # Stage A
    _write_csv(output_dir / "selected_100_cases.csv", selected)
    _write_jsonl(output_dir / "selected_100_cases.jsonl", selected)
    public_rows = [
        {
            "dataset": _norm(r.get("dataset")),
            "example_id": _norm(r.get("example_id")),
            "seed": _safe_int(r.get("seed")),
            "budget": _safe_int(r.get("budget")),
            "selection_source": _norm(r.get("_selection_source")),
        }
        for r in selected
    ]
    _write_csv(output_dir / "selected_100_cases_public_summary.csv", public_rows)

    # Stage B/C
    _write_csv(output_dir / "best_methods_external_loss_results.csv", details)
    _write_jsonl(output_dir / "per_method_raw_outputs.jsonl", raw_rows)
    _write_jsonl(output_dir / "branch_traces.jsonl", [])
    _write_jsonl(cache_path, [])

    # Stage D
    method_table = [{"method": m, **v} for m, v in sorted(summary["method_accuracy"].items())]
    _write_csv(output_dir / "method_accuracy_table.csv", method_table)
    l1_rows = []
    for m, v in sorted(summary["method_accuracy"].items()):
        if m == "external_l1_max":
            continue
        l1_rows.append({"method": m, "accuracy": v["accuracy"], "l1_accuracy": summary["method_accuracy"].get("external_l1_max", {}).get("accuracy", 0.0), "delta_vs_l1": round(v["accuracy"] - summary["method_accuracy"].get("external_l1_max", {}).get("accuracy", 0.0), 4)})
    _write_csv(output_dir / "l1_comparison_table.csv", l1_rows)

    trace_diag = [
        {
            "trace_cases": summary["trace_complete_selected"],
            "selector_recoverable_count": summary["selector_recoverable_count"],
            "discovery_failure_count": summary["discovery_failure_count"],
            "oracle_selector_ceiling_trace": summary["oracle_selector_ceiling_trace"],
        }
    ]
    _write_csv(output_dir / "trace_diagnosis_summary.csv", trace_diag)

    (output_dir / "artifact_scan_report.md").write_text(
        "\n".join([
            "# Artifact Scan Report",
            "",
            f"- artifacts_scanned: {len(artifact_paths)}",
            f"- casebook_files_used: {len(casebook_files)}",
            f"- expected_cohere_calls_for_missing_outputs: {missing_calls}",
        ]),
        encoding="utf-8",
    )
    (output_dir / "best_methods_external_loss_summary.md").write_text(
        "\n".join([
            "# Best Methods on External-Loss Cases",
            "",
            f"- selected_cases: {summary['selected_case_count']}",
            f"- included_trace_complete: {summary['trace_complete_selected']}",
            f"- included_final_row_only: {summary['final_row_only_selected']}",
            f"- default_method: {default_method}",
            f"- default_vs_l1_delta: {summary['delta_default_vs_external_l1_max']}",
            f"- expected_cohere_calls_for_missing_outputs: {missing_calls}",
        ]),
        encoding="utf-8",
    )
    (output_dir / "best_methods_external_loss_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    docs_dir = REPO_ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    doc_path = docs_dir / f"BEST_METHODS_ON_EXTERNAL_LOSS_CASES_100_{ts}.md"
    doc_path.write_text(
        "\n".join([
            "# Best Methods on 100 External-Loss Cases",
            "",
            f"- Selected cases: {summary['selected_case_count']}",
            f"- Included existing trace-complete cases: {summary['trace_complete_selected']} (target reference: 47)",
            f"- Included final-row-only backfill: {summary['final_row_only_selected']}",
            f"- Evaluated methods: {', '.join(sorted(summary['method_accuracy'].keys()))}",
            f"- Does current/default beat external_l1_max on this subset: {'yes' if summary['delta_default_vs_external_l1_max'] > 0 else 'no'}",
            f"- Selector-recoverable count: {summary['selector_recoverable_count']}",
            f"- Discovery-failure count: {summary['discovery_failure_count']}",
            f"- Recommendation: keep oracle as diagnostic ceiling only; promote only if deployable method exceeds L1 on this subset.",
        ]),
        encoding="utf-8",
    )

    pushable = sorted(name for name in PUSHABLE_OUTPUTS if (output_dir / name).exists())
    print(json.dumps({"pushable_outputs": pushable, "doc_path": str(doc_path)}, indent=2))


if __name__ == "__main__":
    main()
