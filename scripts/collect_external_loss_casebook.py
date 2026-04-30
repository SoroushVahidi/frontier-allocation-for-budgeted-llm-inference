#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_VERSION = "external_loss_casebook_diag_v2"

INTERNAL_METHOD_ALIASES = {
    "direct_reserve_semantic_frontier_v2": "direct_reserve_semantic_frontier_v2",
    "dr_v2": "direct_reserve_semantic_frontier_v2",
    "direct_reserve_semantic_frontier_v2_selection_fix_v1": "direct_reserve_semantic_frontier_v2_selection_fix_v1",
    "strict_f3": "strict_f3",
    "strict_gate1_cap_k6": "strict_gate1_cap_k6",
    "strict_f3_anti_collapse_weak_v1": "strict_f3_anti_collapse_weak_v1",
}
EXTERNAL_METHOD_ALIASES = {
    "external_l1_max": "external_l1_max",
    "l1_max": "external_l1_max",
    "l1-max": "external_l1_max",
    "external_l1_exact": "external_l1_exact",
    "l1_exact": "external_l1_exact",
    "external_tale_prompt_budgeting": "external_tale_prompt_budgeting",
    "tale": "external_tale_prompt_budgeting",
    "external_s1_budget_forcing": "external_s1_budget_forcing",
    "s1": "external_s1_budget_forcing",
    "tot_beam_matched_budget": "tot_beam_matched_budget",
    "tot_bfs_matched_budget": "tot_bfs_matched_budget",
    "tot_dfs_matched_budget": "tot_dfs_matched_budget",
}
INTERNAL_PRIORITY = [
    "direct_reserve_semantic_frontier_v2",
    "direct_reserve_semantic_frontier_v2_selection_fix_v1",
    "strict_f3",
    "strict_gate1_cap_k6",
    "strict_f3_anti_collapse_weak_v1",
]
EXTERNAL_PRIORITY = [
    "external_l1_max",
    "external_l1_exact",
    "external_tale_prompt_budgeting",
    "external_s1_budget_forcing",
    "tot_beam_matched_budget",
    "tot_bfs_matched_budget",
    "tot_dfs_matched_budget",
]


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


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _canon_method(method: str) -> tuple[str, str]:
    m = _norm(method).lower()
    if m in INTERNAL_METHOD_ALIASES:
        return "internal", INTERNAL_METHOD_ALIASES[m]
    if m in EXTERNAL_METHOD_ALIASES:
        return "external", EXTERNAL_METHOD_ALIASES[m]
    return "other", _norm(method)


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except csv.Error:
        # Some archived files are nominally CSV but contain NUL bytes.
        # Fall back to a sanitized decode so one corrupt file does not kill broad scan.
        raw = path.read_bytes().replace(b"\x00", b"")
        text = raw.decode("utf-8", errors="ignore")
        return list(csv.DictReader(text.splitlines()))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _discover_artifacts(roots: list[Path]) -> list[Path]:
    found: dict[Path, set[Path]] = defaultdict(set)
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".jsonl", ".json", ".csv", ".tsv", ".parquet", ".md", ".txt"}:
                continue
            found[p.parent].add(p)
    return sorted(found.keys())


def _pick_internal(methods: set[str]) -> str:
    for m in INTERNAL_PRIORITY:
        if m in methods:
            return m
    return ""


def _pick_best_external(method_rows: dict[str, dict[str, Any]]) -> tuple[str, int, dict[str, Any]] | None:
    cand = []
    for m, row in method_rows.items():
        if m in EXTERNAL_PRIORITY:
            ok = _safe_int(row.get("is_correct", row.get("exact_match", 0)))
            cand.append((m, ok, row))
    if not cand:
        return None
    cand.sort(key=lambda x: (x[1], x[0] == "external_l1_max", -EXTERNAL_PRIORITY.index(x[0]) if x[0] in EXTERNAL_PRIORITY else -999), reverse=True)
    return cand[0]


def _load_table_like(path: Path) -> tuple[list[dict[str, Any]], str]:
    ext = path.suffix.lower()
    if ext == ".csv":
        return _read_csv(path), "csv"
    if ext == ".tsv":
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f, delimiter="\t")), "tsv"
    if ext == ".jsonl":
        return _read_jsonl(path), "jsonl"
    if ext == ".json":
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(obj, list):
                return [x for x in obj if isinstance(x, dict)], "json_array"
            if isinstance(obj, dict):
                for k in ("rows", "data", "records"):
                    if isinstance(obj.get(k), list):
                        return [x for x in obj[k] if isinstance(x, dict)], "json_wrapped"
        except Exception:
            pass
        return [], "json"
    if ext == ".parquet":
        try:
            import pandas as pd

            return pd.read_parquet(path).to_dict(orient="records"), "parquet"
        except Exception:
            return [], "parquet_unreadable"
    return [], "unknown"


def _extract_method_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        m = _norm(r.get("method"))
        if not m:
            continue
        kind, canon = _canon_method(m)
        if kind == "other":
            continue
        out.append({**r, "_method_kind": kind, "_method_canon": canon})
    return out


def _is_trace_complete(row: dict[str, Any], groups: list[dict[str, Any]], branches: list[dict[str, Any]]) -> bool:
    if groups:
        return True
    md = row.get("result_metadata", {}) if isinstance(row.get("result_metadata"), dict) else {}
    if isinstance(md.get("selector_candidate_pool"), list) and md.get("selector_candidate_pool"):
        return True
    if branches:
        return True
    return False


def _summary_scan_row(
    artifact_path: Path,
    file_type: str,
    schema: str,
    rows: list[dict[str, Any]],
    methods: set[str],
    paired_exists: bool,
    candidate_losses: int,
    trace_losses: int,
    rejection_reason: str,
) -> dict[str, Any]:
    datasets = sorted({_norm(r.get("dataset")) for r in rows if _norm(r.get("dataset"))})
    return {
        "artifact_path": str(artifact_path),
        "file_type": file_type,
        "schema_detected": schema,
        "row_count": len(rows),
        "datasets_found": "|".join(datasets),
        "methods_found": "|".join(sorted(methods)),
        "paired_internal_external_exists": int(paired_exists),
        "candidate_loss_cases": candidate_losses,
        "trace_complete_loss_cases": trace_losses,
        "rejection_reason": rejection_reason,
    }


def _collect_groups_from_rows(rows: list[dict[str, Any]], case_key: tuple[str, str, int, int]) -> list[dict[str, Any]]:
    dataset, example_id, seed, budget = case_key
    out = []
    for r in rows:
        rk = (_norm(r.get("dataset")), _norm(r.get("example_id")), _safe_int(r.get("seed")), _safe_int(r.get("budget")))
        if rk != case_key:
            continue
        if _norm(r.get("answer_group")) or _norm(r.get("normalized_answer")):
            out.append(
                {
                    "answer": _norm(r.get("answer_group", r.get("normalized_answer"))),
                    "support": _safe_int(r.get("support", r.get("support_count", 0))),
                    "method": _norm(r.get("method")),
                }
            )
    return out


def _collect_branches_from_rows(rows: list[dict[str, Any]], case_key: tuple[str, str, int, int]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        rk = (_norm(r.get("dataset")), _norm(r.get("example_id")), _safe_int(r.get("seed")), _safe_int(r.get("budget")))
        if rk != case_key:
            continue
        if any(k in r for k in ("branch_depth", "depth", "action_index", "action_count", "normalized_candidate_answer")):
            out.append(r)
    return out


def _cohere_request(api_key: str, model: str, prompt: str) -> dict[str, Any]:
    req = urllib.request.Request(
        "https://api.cohere.ai/v1/chat",
        data=json.dumps({"model": model, "message": prompt, "temperature": 0.0}).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        txt = str(body.get("text", "{}"))
        return _parse_diag_json(txt)
    except urllib.error.HTTPError as e:
        return {
            "primary_failure_mode": "unknown",
            "secondary_failure_modes": [],
            "why_external_succeeded": f"http_{e.code}",
            "why_ours_failed": "cohere_http_error",
            "was_ours_close_to_gold": "unknown",
            "suggested_intervention": "retry_or_debug_cohere_client",
            "confidence": 0.0,
        }


def _parse_diag_json(text: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.startswith("json"):
            t = t[4:].strip()
    try:
        d = json.loads(t)
    except Exception:
        i = t.find("{")
        j = t.rfind("}")
        if i >= 0 and j > i:
            d = json.loads(t[i : j + 1])
        else:
            d = {}
    return {
        "primary_failure_mode": str(d.get("primary_failure_mode", "unknown")),
        "selector_vs_discovery_guess": str(d.get("selector_vs_discovery_guess", "unknown")),
        "why_external_succeeded": str(d.get("why_external_succeeded", "")),
        "why_ours_failed": str(d.get("why_ours_failed", "")),
        "suggested_intervention": str(d.get("suggested_intervention", "")),
        "confidence": _safe_float(d.get("confidence", 0.0), 0.0),
    }


def _numeric_error(a: str, b: str) -> float | None:
    try:
        return abs(float(a.replace(",", "")) - float(b.replace(",", "")))
    except Exception:
        return None


def _string_distance(a: str, b: str) -> int:
    # Simple Levenshtein distance for diagnostics
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    dp = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev = dp[0]
        dp[0] = i
        for j, cb in enumerate(b, 1):
            cur = dp[j]
            cost = 0 if ca == cb else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = cur
    return dp[-1]


def _build_loss_row(
    artifact_path: Path,
    case_key: tuple[str, str, int, int],
    our_method: str,
    our_row: dict[str, Any],
    best_external_method: str,
    best_external_row: dict[str, Any],
    all_external_methods: list[str],
    groups: list[dict[str, Any]],
    branches: list[dict[str, Any]],
    trace_available: bool,
) -> dict[str, Any]:
    dataset, example_id, seed, budget = case_key
    gold = _norm(our_row.get("gold_answer", our_row.get("gold_answer_canonical")))
    question = _norm(our_row.get("question", our_row.get("question_raw")))
    our_ans = _norm(our_row.get("normalized_selected_answer", our_row.get("final_selected_answer", our_row.get("final_answer_canonical"))))
    l1_ans = ""
    l1_ok = 0
    if best_external_method == "external_l1_max":
        l1_ans = _norm(best_external_row.get("normalized_selected_answer", best_external_row.get("final_selected_answer")))
        l1_ok = _safe_int(best_external_row.get("is_correct", best_external_row.get("exact_match", 0)))

    if not groups and our_ans:
        groups = [{"answer": our_ans, "support": 1, "method": our_method}]
    unique_answers = sorted({g["answer"] for g in groups if g.get("answer")})
    gold_present = int(gold in unique_answers and gold != "")
    selected_support = max((int(g.get("support", 0)) for g in groups if g.get("answer") == our_ans), default=0)
    gold_support = max((int(g.get("support", 0)) for g in groups if g.get("answer") == gold), default=0)
    support_sorted = sorted(groups, key=lambda x: int(x.get("support", 0)), reverse=True)
    top1 = int(support_sorted[0].get("support", 0)) if support_sorted else 0
    top2 = int(support_sorted[1].get("support", 0)) if len(support_sorted) > 1 else 0

    depths = [_safe_int(b.get("branch_depth", b.get("depth", 0))) for b in branches]
    actions = [_safe_int(b.get("action_index", b.get("action_count", 0))) for b in branches]
    max_depth = max(depths) if depths else 0
    mean_depth = mean(depths) if depths else 0.0
    first_action_by_ans: dict[str, int] = {}
    depth_by_ans: dict[str, int] = {}
    for b in branches:
        ans = _norm(b.get("normalized_candidate_answer", b.get("answer_group", b.get("predicted_answer", b.get("final_answer")))))
        if not ans:
            continue
        act = _safe_int(b.get("action_index", b.get("action_count", 0)))
        dep = _safe_int(b.get("branch_depth", b.get("depth", 0)))
        first_action_by_ans[ans] = min(act, first_action_by_ans.get(ans, act))
        depth_by_ans[ans] = min(dep, depth_by_ans.get(ans, dep))

    oracle_ans = gold if gold_present else our_ans
    oracle_correct = int(oracle_ans == gold and gold != "")
    str_dist = _string_distance(our_ans, gold) if gold else len(our_ans)
    num_err = _numeric_error(our_ans, gold)
    ext_correct = _safe_int(best_external_row.get("is_correct", best_external_row.get("exact_match", 0)))
    our_correct = _safe_int(our_row.get("is_correct", our_row.get("exact_match", 0)))
    row = {
            "case_id": f"{dataset}::{example_id}::{seed}::{budget}",
            "dataset": dataset,
            "example_id": example_id,
            "seed": seed,
            "budget": budget,
            "source_artifact": str(artifact_path),
            "our_method_name": our_method,
            "best_external_method_name": best_external_method,
            "all_available_external_methods": "|".join(sorted(all_external_methods)),
            "problem_statement": question,
            "gold_answer": gold,
            "our_final_answer": our_ans,
            "our_correct": our_correct,
            "external_l1_max_answer": l1_ans,
            "external_l1_max_correct": l1_ok,
            "best_external_answer": _norm(best_external_row.get("normalized_selected_answer", best_external_row.get("final_selected_answer"))),
            "best_external_correct": ext_correct,
            "all_candidate_answer_groups": json.dumps(unique_answers, ensure_ascii=False),
            "selected_answer_group": our_ans,
            "gold_answer_group_if_present": gold if gold_present else "",
            "candidate_group_count": len(unique_answers),
            "candidate_count": len(groups),
            "branch_count": len(branches),
            "max_depth": max_depth,
            "mean_depth": mean_depth,
            "total_expansions": len(branches),
            "total_actions": max(actions) if actions else 0,
            "verifier_calls": _safe_int(our_row.get("verification_count", 0)),
            "commit_step": _safe_int(our_row.get("action_count", 0)),
            "budget_exhausted_or_early_commit": "early_commit" if _safe_int(our_row.get("action_count", 0)) < budget else "budget_exhausted",
            "branch_family_count": len({_norm(b.get("branch_prompt_style", b.get("family_id"))) for b in branches if _norm(b.get("branch_prompt_style", b.get("family_id")))}),
            "source_family_count": len({_norm(g.get("method")) for g in groups if _norm(g.get("method"))}),
            "repeated_same_family_expansion_count": max(0, len(branches) - len({_norm(b.get("branch_prompt_style", b.get("family_id"))) for b in branches})),
            "repeated_same_answer_expansion_count": max(0, len(groups) - len(unique_answers)),
            "answer_entropy": _safe_float(our_row.get("answer_entropy", 0.0)),
            "top1_support": top1,
            "top2_support": top2,
            "top2_support_gap": top1 - top2,
            "support_count_by_answer_group": json.dumps({g["answer"]: g["support"] for g in groups}, ensure_ascii=False),
            "source_family_by_answer_group": json.dumps({g["answer"]: g["method"] for g in groups}, ensure_ascii=False),
            "depth_by_answer_group": json.dumps(depth_by_ans, ensure_ascii=False),
            "first_action_index_by_answer_group": json.dumps(first_action_by_ans, ensure_ascii=False),
            "gold_present_in_candidate_groups": gold_present,
            "gold_present_in_tree": int(gold in depth_by_ans),
            "gold_first_depth_if_present": depth_by_ans.get(gold, ""),
            "gold_first_action_index_if_present": first_action_by_ans.get(gold, ""),
            "selected_vs_gold_answer_distance": str_dist,
            "selected_vs_gold_numeric_error_if_parseable": "" if num_err is None else num_err,
            "selected_answer_support": selected_support,
            "gold_answer_support_if_present": gold_support if gold_present else "",
            "support_gap_selected_minus_gold_if_present": (selected_support - gold_support) if gold_present else "",
            "rank_of_gold_answer_group_if_present": (
                next((i + 1 for i, g in enumerate(sorted(unique_answers, key=lambda a: max([x["support"] for x in groups if x["answer"] == a] or [0]), reverse=True)) if g == gold), "")
                if gold_present
                else ""
            ),
            "oracle_selector_answer": oracle_ans,
            "oracle_selector_correct": oracle_correct,
            "oracle_selector_would_fix": int(oracle_correct == 1 and our_correct == 0),
            "external_found_but_ours_gold_absent": int(ext_correct == 1 and gold_present == 0),
            "l1_correct_but_gold_absent_in_ours": int(l1_ok == 1 and gold_present == 0),
            "estimated_missing_depth_to_gold_if_available": "",
            "estimated_missing_actions_to_gold_if_available": "",
            "trace_available": int(trace_available),
        }
    row["selector_failure_gold_present"] = int(gold_present == 1)
    row["discovery_failure_gold_absent"] = int(gold_present == 0)
    row["premature_commitment"] = int(row["budget_exhausted_or_early_commit"] == "early_commit" and gold_present == 1)
    row["single_answer_collapse"] = int(len(unique_answers) <= 1)
    row["insufficient_root_diversity"] = int(row["branch_family_count"] <= 1)
    row["repeated_same_family_overexpansion"] = int(row["repeated_same_family_expansion_count"] > 0)
    row["arithmetic_or_calculation_error"] = int(num_err is not None and num_err > 0)
    row["wrong_problem_decomposition"] = int(row["selector_failure_gold_present"] == 0 and row["discovery_failure_gold_absent"] == 1 and row["branch_count"] > 0)
    row["external_l1_unique_success"] = int(l1_ok == 1 and best_external_method == "external_l1_max")
    row["artifact_trace_incomplete"] = int(trace_available == 0)
    row["unknown"] = int(
            sum(
                [
                    row["selector_failure_gold_present"],
                    row["discovery_failure_gold_absent"],
                    row["premature_commitment"],
                    row["single_answer_collapse"],
                    row["insufficient_root_diversity"],
                    row["repeated_same_family_overexpansion"],
                    row["arithmetic_or_calculation_error"],
                    row["wrong_problem_decomposition"],
                ]
            )
            == 0
        )
    return row


def _scan_artifact(artifact_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    all_files = [p for p in artifact_dir.iterdir() if p.is_file() and p.suffix.lower() in {".csv", ".jsonl", ".json", ".tsv", ".parquet"}]
    trace_losses: list[dict[str, Any]] = []
    final_only_losses: list[dict[str, Any]] = []
    scan_rows: list[dict[str, Any]] = []

    # Preload likely group/branch tables
    aux_rows: list[dict[str, Any]] = []
    for p in all_files:
        if "answer_group" in p.name or "candidate_branch" in p.name or "final_branch_states" in p.name:
            rows, _ = _load_table_like(p)
            aux_rows.extend(rows)

    for p in all_files:
        rows, schema = _load_table_like(p)
        if not rows:
            scan_rows.append(_summary_scan_row(p, p.suffix.lower().lstrip("."), schema, rows, set(), False, 0, 0, "empty_or_unreadable"))
            continue
        mrows = _extract_method_rows(rows)
        if not mrows:
            scan_rows.append(_summary_scan_row(p, p.suffix.lower().lstrip("."), schema, rows, set(), False, 0, 0, "no_method_rows"))
            continue

        by_case: dict[tuple[str, str, int, int], dict[str, dict[str, Any]]] = defaultdict(dict)
        methods: set[str] = set()
        for r in mrows:
            method = r["_method_canon"]
            methods.add(method)
            key = (_norm(r.get("dataset")), _norm(r.get("example_id")), _safe_int(r.get("seed")), _safe_int(r.get("budget")))
            by_case[key][method] = r

        paired_exists = False
        candidate_losses = 0
        trace_candidate_losses = 0
        for case_key, mm in by_case.items():
            our_method = _pick_internal(set(mm.keys()))
            if not our_method:
                continue
            ext_pick = _pick_best_external(mm)
            if ext_pick is None:
                continue
            paired_exists = True
            ext_method, ext_ok, ext_row = ext_pick
            our_row = mm[our_method]
            our_ok = _safe_int(our_row.get("is_correct", our_row.get("exact_match", 0)))
            if ext_ok != 1 or our_ok == 1:
                continue
            candidate_losses += 1
            all_ext = [m for m in mm.keys() if m in EXTERNAL_PRIORITY]
            groups = _collect_groups_from_rows(aux_rows + rows, case_key)
            branches = _collect_branches_from_rows(aux_rows + rows, case_key)
            trace_complete = _is_trace_complete(our_row, groups, branches)
            lr = _build_loss_row(
                artifact_path=artifact_dir,
                case_key=case_key,
                our_method=our_method,
                our_row=our_row,
                best_external_method=ext_method,
                best_external_row=ext_row,
                all_external_methods=all_ext,
                groups=groups,
                branches=branches,
                trace_available=trace_complete,
            )
            if trace_complete:
                trace_candidate_losses += 1
                trace_losses.append(lr)
            else:
                final_only_losses.append(lr)

        reason = ""
        if not paired_exists:
            reason = "no_paired_internal_external_rows"
        elif candidate_losses == 0:
            reason = "no_external_correct_internal_wrong_losses"
        scan_rows.append(
            _summary_scan_row(
                artifact_path=p,
                file_type=p.suffix.lower().lstrip("."),
                schema=schema,
                rows=rows,
                methods=methods,
                paired_exists=paired_exists,
                candidate_losses=candidate_losses,
                trace_losses=trace_candidate_losses,
                rejection_reason=reason,
            )
        )
    return trace_losses, final_only_losses, scan_rows


def _diag_prompt(case: dict[str, Any]) -> str:
    payload = {
        "task": "diagnostic_failure_labeling_only",
        "instructions": "Diagnose why external baseline succeeded while ours failed. Do not propose method output changes.",
        "problem_statement": case["problem_statement"],
        "gold_answer": case["gold_answer"],
        "our_final_answer": case["our_final_answer"],
        "best_external_answer": case["best_external_answer"],
        "candidate_answer_groups": case["all_candidate_answer_groups"],
        "tree_summary": {
            "branch_count": case["branch_count"],
            "max_depth": case["max_depth"],
            "top2_support_gap": case["top2_support_gap"],
            "gold_present_in_candidate_groups": case["gold_present_in_candidate_groups"],
        },
        "response_schema_strict_json": {
            "primary_failure_mode": "string",
            "selector_vs_discovery_guess": "selector|discovery|mixed|unknown",
            "why_external_succeeded": "string",
            "why_ours_failed": "string",
            "suggested_intervention": "string",
            "confidence": "number_0_to_1",
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def _choose_cases(losses: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    def score(x: dict[str, Any]) -> tuple[int, int, int, int]:
        return (
            int(x["best_external_method_name"] == "external_l1_max"),
            int(x["branch_count"] > 0),
            int(_norm(x["problem_statement"]) != ""),
            int(x["gold_present_in_candidate_groups"]),
        )

    losses_sorted = sorted(
        losses,
        key=lambda x: (score(x), x["dataset"], x["budget"], x["seed"], x["example_id"]),
        reverse=True,
    )
    return losses_sorted[:target]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--target-losses", type=int, default=200)
    p.add_argument("--search-roots", nargs="+", default=["outputs", "archive", "logs"])
    p.add_argument("--output-dir", required=True)
    p.add_argument("--provider", default="cohere")
    p.add_argument("--cohere-model", default="command-r-plus")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--broad-search", action="store_true")
    p.add_argument("--include-final-row-only", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    roots = [(REPO_ROOT / r).resolve() for r in args.search_roots]
    if args.broad_search:
        broad_extra = [
            "paper_tables",
            "paper_plot_data",
            "outputs/paper_tables",
            "outputs/paper_plot_data",
            "neurips2026_anonymous_artifact",
        ]
        for r in broad_extra:
            p = (REPO_ROOT / r).resolve()
            if p.exists():
                roots.append(p)
    roots = sorted(set(roots))
    artifacts = _discover_artifacts(roots)

    scan_rows: list[dict[str, Any]] = []
    trace_losses_all: list[dict[str, Any]] = []
    final_only_losses_all: list[dict[str, Any]] = []
    for art in artifacts:
        trace_losses, final_losses, rows = _scan_artifact(art)
        scan_rows.extend(rows)
        trace_losses_all.extend(trace_losses)
        final_only_losses_all.extend(final_losses)

    with (out_dir / "artifact_scan.csv").open("w", encoding="utf-8", newline="") as f:
        if scan_rows:
            w = csv.DictWriter(f, fieldnames=list(scan_rows[0].keys()))
            w.writeheader()
            w.writerows(scan_rows)
        else:
            f.write("artifact_path,usable,rejection_reason\n")
    (out_dir / "artifact_scan_report.md").write_text(
        "\n".join(
            [
                "# External Loss Artifact Scan",
                "",
                f"- artifacts_scanned: {len(artifacts)}",
                f"- candidate_files_scanned: {len(scan_rows)}",
                f"- trace_complete_losses_found: {len(trace_losses_all)}",
                f"- final_row_only_losses_found: {len(final_only_losses_all)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    selected_trace = _choose_cases(trace_losses_all, args.target_losses)
    remaining = max(0, args.target_losses - len(selected_trace))
    selected_final = _choose_cases(final_only_losses_all, remaining) if args.include_final_row_only else []
    selected = selected_trace + selected_final

    # Build diagnostic plan and optionally annotate
    cache_path = out_dir / "cohere_annotation_cache.jsonl"
    existing_cache = {str(r.get("cache_key")): r for r in _read_jsonl(cache_path)}
    plan_rows: list[dict[str, Any]] = []
    prompt_version = "external_loss_casebook_diag_v1"
    for c in selected:
        key = f"{c['dataset']}::{c['example_id']}::{c['our_method_name']}::{c['best_external_method_name']}::{PROMPT_VERSION}"
        plan_rows.append(
            {
                "case_id": c["case_id"],
                "cache_key": key,
                "provider": args.provider,
                "model": args.cohere_model,
                "would_call": int(key not in existing_cache),
            }
        )
    with (out_dir / "cohere_annotation_plan.jsonl").open("w", encoding="utf-8") as f:
        for r in plan_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    expected_calls = sum(int(r["would_call"]) for r in plan_rows)
    print(
        json.dumps(
            {
                "trace_complete_selected": len(selected_trace),
                "final_row_only_selected": len(selected_final),
                "selected_cases": len(selected),
                "expected_cohere_calls": expected_calls,
                "cache_path": str(cache_path),
                "model": args.cohere_model,
                "output_dir": str(out_dir),
            },
            indent=2,
        )
    )

    api_key = os.environ.get("COHERE_API_KEY", "")
    if args.provider == "cohere" and not args.dry_run and api_key:
        with cache_path.open("a", encoding="utf-8") as cache_f:
            for c in selected:
                key = f"{c['dataset']}::{c['example_id']}::{c['our_method_name']}::{c['best_external_method_name']}::{PROMPT_VERSION}"
                if key in existing_cache:
                    ann = existing_cache[key]
                else:
                    prompt = _diag_prompt(c)
                    ann = {"cache_key": key, "provider": "cohere", "model": args.cohere_model, **_cohere_request(api_key, args.cohere_model, prompt)}
                    cache_f.write(json.dumps(ann, ensure_ascii=False) + "\n")
                    existing_cache[key] = ann
                c.update(
                    {
                        "cohere_primary_failure_mode": ann.get("primary_failure_mode", ""),
                        "cohere_selector_vs_discovery_guess": ann.get("selector_vs_discovery_guess", ""),
                        "cohere_why_external_succeeded": ann.get("why_external_succeeded", ""),
                        "cohere_why_ours_failed": ann.get("why_ours_failed", ""),
                        "cohere_suggested_intervention": ann.get("suggested_intervention", ""),
                        "cohere_confidence": ann.get("confidence", ""),
                    }
                )

    # Ensure schema columns exist even without Cohere
    cohere_cols = [
        "cohere_primary_failure_mode",
        "cohere_selector_vs_discovery_guess",
        "cohere_why_external_succeeded",
        "cohere_why_ours_failed",
        "cohere_suggested_intervention",
        "cohere_confidence",
    ]
    for c in selected:
        for col in cohere_cols:
            c.setdefault(col, "")

    trace_csv = out_dir / "loss_casebook_trace_complete.csv"
    trace_jsonl = out_dir / "loss_casebook_trace_complete.jsonl"
    final_csv = out_dir / "loss_casebook_final_rows_only.csv"
    final_jsonl = out_dir / "loss_casebook_final_rows_only.jsonl"
    combined_csv = out_dir / "loss_casebook_combined_200.csv"
    combined_jsonl = out_dir / "loss_casebook_combined_200.jsonl"

    with trace_jsonl.open("w", encoding="utf-8") as f:
        for r in selected_trace:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with final_jsonl.open("w", encoding="utf-8") as f:
        for r in selected_final:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with combined_jsonl.open("w", encoding="utf-8") as f:
        for r in selected:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def _write_csv_rows(path: Path, rows: list[dict[str, Any]]) -> None:
        fields: list[str] = []
        for r in rows:
            for k in r.keys():
                if k not in fields:
                    fields.append(k)
        if not fields:
            fields = [
                "case_id",
                "dataset",
                "example_id",
                "seed",
                "budget",
                "our_method_name",
                "best_external_method_name",
                "trace_available",
            ]
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    _write_csv_rows(trace_csv, selected_trace)
    _write_csv_rows(final_csv, selected_final)
    _write_csv_rows(combined_csv, selected)

    by_dataset = Counter(r["dataset"] for r in selected)
    by_budget = Counter(str(r["budget"]) for r in selected)
    by_seed = Counter(str(r["seed"]) for r in selected)
    by_internal = Counter(r["our_method_name"] for r in selected)
    by_external = Counter(r["best_external_method_name"] for r in selected)
    gold_present = sum(int(r["gold_present_in_candidate_groups"]) for r in selected_trace)
    oracle_fix = sum(int(r["oracle_selector_would_fix"]) for r in selected_trace)
    l1_found_but_ours_absent = sum(int(r["l1_correct_but_gold_absent_in_ours"]) for r in selected_trace)
    l1_external_correct = sum(int(r["best_external_method_name"] == "external_l1_max") for r in selected)
    other_external_correct = len(selected) - l1_external_correct
    rejected = sum(1 for r in scan_rows if _norm(r.get("rejection_reason")))
    rejected_reasons = Counter(_norm(r.get("rejection_reason")) for r in scan_rows if _norm(r.get("rejection_reason")))
    failure_mode_counts = Counter(
        "selector_failures"
        if int(r["selector_failure_gold_present"]) == 1
        else ("discovery_failures" if int(r["discovery_failure_gold_absent"]) == 1 else "mixed")
        for r in selected
    )

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "loss_cases_found_total": len(trace_losses_all) + len(final_only_losses_all),
        "trace_complete_loss_cases_found": len(trace_losses_all),
        "final_row_only_loss_cases_found": len(final_only_losses_all),
        "loss_cases_included": len(selected),
        "combined_selected_casebook_size": len(selected),
        "target_losses": args.target_losses,
        "breakdown_by_dataset": dict(by_dataset),
        "breakdown_by_budget": dict(by_budget),
        "breakdown_by_seed": dict(by_seed),
        "breakdown_by_internal_method": dict(by_internal),
        "breakdown_by_best_external_method": dict(by_external),
        "gold_present_count": gold_present,
        "gold_present_fraction": (gold_present / len(selected_trace)) if selected_trace else 0.0,
        "gold_absent_count": len(selected_trace) - gold_present,
        "gold_absent_fraction": ((len(selected_trace) - gold_present) / len(selected_trace)) if selected_trace else 0.0,
        "oracle_selector_would_fix_count": oracle_fix,
        "oracle_selector_would_fix_fraction": (oracle_fix / len(selected_trace)) if selected_trace else 0.0,
        "l1_correct_but_gold_absent_in_ours_count": l1_found_but_ours_absent,
        "l1_correct_but_gold_absent_in_ours_fraction": (l1_found_but_ours_absent / len(selected_trace)) if selected_trace else 0.0,
        "external_l1_max_correct_and_ours_wrong_count": l1_external_correct,
        "other_external_correct_and_ours_wrong_count": other_external_correct,
        "most_common_failure_modes": dict(failure_mode_counts),
        "primary_loss_regime": failure_mode_counts.most_common(1)[0][0] if failure_mode_counts else "none",
        "recommended_next_experiment": (
            "focus on selector diagnostics for gold-present losses"
            if failure_mode_counts.get("selector_failures", 0) > failure_mode_counts.get("discovery_failures", 0)
            else "focus on discovery/coverage repair and branch diversity"
        ),
        "expected_cohere_calls": expected_calls,
        "artifacts_rejected_count": rejected,
        "artifact_rejection_reasons": dict(rejected_reasons),
    }
    (out_dir / "loss_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "loss_summary.md").write_text(
        "\n".join(
            [
                "# External Baseline Loss Casebook Summary",
                "",
                f"- total losses found: {summary['loss_cases_found_total']}",
                f"- trace-complete losses found: {summary['trace_complete_loss_cases_found']}",
                f"- final-row-only losses found: {summary['final_row_only_loss_cases_found']}",
                f"- combined selected cases: {summary['combined_selected_casebook_size']}",
                f"- gold-present (trace-complete): {summary['gold_present_count']} ({summary['gold_present_fraction']:.3f})",
                f"- gold-absent (trace-complete): {summary['gold_absent_count']} ({summary['gold_absent_fraction']:.3f})",
                f"- oracle would fix (trace-complete): {summary['oracle_selector_would_fix_count']} ({summary['oracle_selector_would_fix_fraction']:.3f})",
                f"- most common failure modes: {summary['most_common_failure_modes']}",
                f"- artifacts rejected: {summary['artifacts_rejected_count']}",
                f"- recommended next experiment: {summary['recommended_next_experiment']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    doc_path = REPO_ROOT / "docs" / f"EXTERNAL_BASELINE_LOSS_CASEBOOK_BROAD_200_{out_dir.name.split('_')[-1]}.md"
    doc_path.write_text(
        "\n".join(
            [
                f"# EXTERNAL BASELINE LOSS CASEBOOK BROAD 200 {out_dir.name.split('_')[-1]}",
                "",
                f"- output dir: `{out_dir}`",
                f"- selected cases: {len(selected)}",
                f"- expected cohere calls: {expected_calls}",
                "- gold is used for analysis labels only; not for deployable method decisions.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {trace_csv}")
    print(f"Wrote {trace_jsonl}")
    print(f"Wrote {final_csv}")
    print(f"Wrote {final_jsonl}")
    print(f"Wrote {combined_csv}")
    print(f"Wrote {combined_jsonl}")
    print(f"Wrote {out_dir / 'loss_summary.json'}")
    print(f"Wrote {out_dir / 'loss_summary.md'}")
    print(f"Wrote {out_dir / 'cohere_annotation_plan.jsonl'}")
    print(f"Wrote {cache_path}")
    print(f"Wrote {out_dir / 'artifact_scan.csv'}")
    print(f"Wrote {out_dir / 'artifact_scan_report.md'}")
    print(f"Wrote {doc_path}")


if __name__ == "__main__":
    main()
