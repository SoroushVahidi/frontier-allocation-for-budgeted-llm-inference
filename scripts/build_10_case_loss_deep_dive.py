#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import extract_final_answer
from experiments.hf_datasets import _import_hf_load_dataset
from experiments.output_layer_repair import canonicalize_answer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build focused 10-case deep-dive where strict_f3 lost to external_l1_max.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--max-cases", type=int, default=10)
    p.add_argument(
        "--input-package",
        default="outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/",
    )
    p.add_argument(
        "--source-run",
        default="outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG/cohere/per_example_rows.csv",
    )
    p.add_argument("--recover-gsm8k", action="store_true", default=True)
    p.add_argument("--rerun-traces", action="store_true")
    p.add_argument("--provider", default="cohere")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--skip-real-api-if-no-key", action="store_true", default=True)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--split", default="test")
    p.add_argument("--config", default="main")
    return p.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            if fieldnames:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            return
        if fieldnames is None:
            keys: list[str] = []
            seen = set()
            for r in rows:
                for k in r.keys():
                    if k not in seen:
                        seen.add(k)
                        keys.append(k)
            fieldnames = keys
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def as_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def pick(row: dict[str, Any], *keys: str, default: Any = "NA") -> Any:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return default


def parse_openai_gsm8k_index(example_id: str) -> int | None:
    m = re.fullmatch(r"openai_gsm8k_(\d+)", str(example_id).strip())
    return int(m.group(1)) if m else None


def classify_problem_type(question: str) -> str:
    q = (question or "").lower()
    if any(x in q for x in ["ways", "choose", "arrange", "permutation", "combination", "how many"]):
        return "counting_combinatorics"
    if any(x in q for x in ["percent", "%", "ratio", "fraction", "rate"]):
        return "ratio_percent"
    if any(x in q for x in ["more than", "less than", "greater than", "fewer", "difference", "compared"]):
        return "comparison"
    if any(
        x in q
        for x in [
            "km",
            "kilometer",
            "meter",
            "cm",
            "inch",
            "mile",
            "kg",
            "gram",
            "liter",
            "hour",
            "minute",
            "second",
        ]
    ):
        return "unit_conversion"
    if any(x in q for x in ["equation", "solve for", "variable", "x =", "x=", "y ="]):
        return "algebra_like"
    num_count = len(re.findall(r"[-+]?\d*\.?\d+", q))
    sentence_count = len([s for s in re.split(r"[.!?]+", q) if s.strip()])
    if num_count >= 3 or sentence_count >= 3:
        return "multi_step_arithmetic"
    if num_count >= 1:
        return "single_arithmetic"
    return "unknown"


def keyword_tags(question: str) -> dict[str, int]:
    q = (question or "").lower()
    return {
        "contains_how_many": int("how many" in q),
        "contains_ways_choose_arrange": int(any(x in q for x in ["ways", "choose", "arrange", "combination", "permutation"])),
        "contains_percent": int("percent" in q or "%" in q),
        "contains_rate": int("rate" in q),
        "contains_money": int(any(x in q for x in ["$", "dollar", "dollars", "cents"])),
        "contains_time": int(any(x in q for x in ["hour", "minute", "second", "day", "week", "month", "year"])),
        "contains_units": int(any(x in q for x in ["km", "kilometer", "meter", "cm", "inch", "mile", "kg", "gram", "liter"])),
        "contains_comparison_words": int(any(x in q for x in ["more than", "less than", "greater", "fewer", "difference", "compared"])),
    }


def load_gsm8k_index_map(dataset: str, config: str | None, split: str) -> tuple[dict[int, dict[str, str]], str]:
    try:
        load_dataset = _import_hf_load_dataset()
        if config:
            ds = load_dataset(dataset, config, split=split)
        else:
            ds = load_dataset(dataset, split=split)
        out: dict[int, dict[str, str]] = {}
        for idx, row in enumerate(ds):
            q = str(row.get("question", ""))
            ans_raw = str(row.get("answer", ""))
            out[idx] = {
                "question": q,
                "gold_answer_raw": ans_raw,
                "gold_answer": extract_final_answer(ans_raw),
            }
        return out, "index_direct_from_hf_split_order"
    except Exception as exc:  # noqa: BLE001
        return {}, f"unavailable:{type(exc).__name__}"


def pair_from_per_example(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    order: dict[tuple[str, str, str, str, str], int] = {}
    for i, r in enumerate(rows):
        key = (
            str(r.get("dataset", "")),
            str(r.get("seed", "")),
            str(r.get("budget", "")),
            str(r.get("example_id", "")),
            str(r.get("provider", "")),
        )
        if key not in order:
            order[key] = i
        buckets[key][str(r.get("method", ""))] = r

    paired: list[dict[str, Any]] = []
    for key in sorted(order.keys(), key=lambda k: order[k]):
        cell = buckets[key]
        if "strict_f3" not in cell or "external_l1_max" not in cell:
            continue
        strict = cell["strict_f3"]
        ext = cell["external_l1_max"]
        s_ok = as_int(strict.get("is_correct"), -1)
        e_ok = as_int(ext.get("is_correct"), -1)
        if s_ok == 0 and e_ok == 1:
            paired.append(
                {
                    "source": "reconstructed_from_per_example_rows",
                    "dataset": strict.get("dataset", ""),
                    "provider": strict.get("provider", ""),
                    "model": strict.get("model", ""),
                    "seed": strict.get("seed", ""),
                    "budget": strict.get("budget", ""),
                    "example_id": strict.get("example_id", ""),
                    "strict_row": strict,
                    "external_row": ext,
                    "pair_row": {},
                    "row_index_in_150_loss_slice": len(paired) + 1,
                }
            )
    return paired


def select_cases(args: argparse.Namespace) -> tuple[list[dict[str, Any]], str, Path | None]:
    pkg = REPO_ROOT / args.input_package
    candidates = [
        pkg / "all_paired_cases.csv",
        REPO_ROOT
        / "outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/loss_cases_strict_f3_wrong_external_correct.csv",
    ]

    for path in candidates:
        rows = read_csv(path)
        if not rows:
            continue
        if path.name == "all_paired_cases.csv":
            rows = [r for r in rows if str(r.get("pair_type", "")) == "strict_f3_wrong_external_correct"]
        selected = rows[: args.max_cases]
        out: list[dict[str, Any]] = []
        for i, row in enumerate(selected, start=1):
            strict_row = {k.replace("strict_f3_", ""): v for k, v in row.items() if k.startswith("strict_f3_")}
            external_row = {k.replace("external_", ""): v for k, v in row.items() if k.startswith("external_")}
            out.append(
                {
                    "source": f"from_{path.name}",
                    "dataset": pick(row, "dataset"),
                    "provider": pick(row, "provider"),
                    "model": pick(row, "model"),
                    "seed": pick(row, "seed"),
                    "budget": pick(row, "budget"),
                    "example_id": pick(row, "example_id"),
                    "strict_row": strict_row,
                    "external_row": external_row,
                    "pair_row": row,
                    "row_index_in_150_loss_slice": as_int(pick(row, "row_index_in_150_loss_slice", "row_index", default=i), i),
                }
            )
        return out, f"{path}", path

    source_rows = read_csv(REPO_ROOT / args.source_run)
    rec = pair_from_per_example(source_rows)[: args.max_cases]
    return rec, f"{REPO_ROOT / args.source_run}", REPO_ROOT / args.source_run


def normalize_answer(raw: Any, dataset: str) -> str:
    if raw in (None, "", "NA"):
        return "NA"
    try:
        return str(canonicalize_answer(str(raw), dataset=dataset))
    except Exception:
        return "NA"


def maybe_rerun_trace_stub(case: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    strict_trace = {
        "trace_status": "unavailable",
        "trace_source": "existing_artifacts_only",
        "action_trace": [],
        "branches": [],
        "message": "Full branch/step traces were not emitted by the original run and cannot be recovered without rerunning the model.",
    }
    ext_trace = {
        "trace_status": "unavailable",
        "trace_source": "existing_artifacts_only",
        "prompt": "NA",
        "response_text": "NA",
        "message": "External baseline reasoning text was not emitted by the original run and cannot be recovered without rerunning the model.",
    }

    if args.dry_run:
        strict_actions = {
            "expand": as_int(pick(case["strict_row"], "expansions", default=0), 0),
            "verify": as_int(pick(case["strict_row"], "verifications", default=0), 0),
            "total_actions": as_int(pick(case["strict_row"], "actions_used", default=0), 0),
        }
        ext_actions = {
            "expand": as_int(pick(case["external_row"], "expansions", default=0), 0),
            "verify": as_int(pick(case["external_row"], "verifications", default=0), 0),
            "total_actions": as_int(pick(case["external_row"], "actions_used", default=0), 0),
        }
        strict_trace = {
            "trace_status": "dry_run_reconstruction",
            "trace_source": "aggregate_action_counts_only",
            "action_trace": [strict_actions],
            "branches": [],
            "message": "Full branch/step traces were not emitted by the original run and cannot be recovered without rerunning the model.",
        }
        ext_trace = {
            "trace_status": "dry_run_reconstruction",
            "trace_source": "aggregate_action_counts_only",
            "prompt": "NA",
            "response_text": "NA",
            "action_counts": [ext_actions],
            "message": "External baseline reasoning text was not emitted by the original run and cannot be recovered without rerunning the model.",
        }

    if args.rerun_traces:
        has_key = bool(os.environ.get("COHERE_API_KEY"))
        if not has_key and args.skip_real_api_if_no_key:
            strict_trace["trace_status"] = "skipped_no_api_key"
            ext_trace["trace_status"] = "skipped_no_api_key"
        else:
            strict_trace["trace_status"] = "not_implemented_in_diagnostic_script"
            ext_trace["trace_status"] = "not_implemented_in_diagnostic_script"
    return strict_trace, ext_trace


def build_case_records(cases: list[dict[str, Any]], gsm_map: dict[int, dict[str, str]], mapping_rule: str, args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    summary_rows: list[dict[str, Any]] = []
    strict_rows: list[dict[str, Any]] = []
    ext_rows: list[dict[str, Any]] = []
    strict_branch_rows: list[dict[str, Any]] = []
    ext_trace_rows: list[dict[str, Any]] = []
    strict_action_rows: list[dict[str, Any]] = []
    answer_diag_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []

    required_fields = [
        "strict_final_answer_raw",
        "strict_final_answer_normalized",
        "external_final_answer_raw",
        "external_final_answer_normalized",
        "strict_branch_prompt",
        "strict_branch_response_reasoning",
        "strict_branch_scores",
        "strict_answer_group_support_counts",
        "strict_selected_answer_group",
        "strict_top_answer_group",
        "strict_top2_support_gap",
        "strict_answer_entropy",
        "strict_commit_margin",
        "strict_commit_guard_state",
        "external_prompt",
        "external_response_reasoning",
        "external_selection_reason",
    ]

    for idx, case in enumerate(cases, start=1):
        ds = str(case["dataset"])
        ex_id = str(case["example_id"])
        ex_idx = parse_openai_gsm8k_index(ex_id) if ds == "openai/gsm8k" else None
        q = "NA"
        gold_raw = "NA"
        gold_final_raw = "NA"
        mapping_status = "not_attempted"
        if ex_idx is not None and ex_idx in gsm_map:
            item = gsm_map[ex_idx]
            q = item["question"]
            gold_raw = item["gold_answer_raw"]
            gold_final_raw = item["gold_answer"]
            mapping_status = "recovered_by_index"
        elif ex_idx is not None:
            mapping_status = "index_missing_in_loader"

        gold_norm = normalize_answer(gold_final_raw, ds)

        strict_raw = pick(
            case["pair_row"],
            "our_final_answer",
            "strict_f3_final_answer",
            "strict_f3_final_answer_raw",
            default="NA",
        )
        if strict_raw == "NA":
            strict_raw = pick(case["strict_row"], "final_answer", "final_answer_raw", default="NA")

        ext_raw = pick(
            case["pair_row"],
            "external_final_answer",
            "external_l1_max_final_answer",
            "external_l1_max_final_answer_raw",
            default="NA",
        )
        if ext_raw == "NA":
            ext_raw = pick(case["external_row"], "final_answer", "final_answer_raw", default="NA")

        strict_norm = normalize_answer(strict_raw, ds)
        ext_norm = normalize_answer(ext_raw, ds)

        strict_correct = as_int(pick(case["strict_row"], "is_correct", "correct", default=0), 0)
        ext_correct = as_int(pick(case["external_row"], "is_correct", "correct", default=1), 1)

        strict_trace, ext_trace = maybe_rerun_trace_stub(case, args)

        problem_type = classify_problem_type(q if q != "NA" else "")
        tags = keyword_tags(q if q != "NA" else "")

        case_id = f"{case['dataset']}|{case['seed']}|{case['budget']}|{case['example_id']}"

        summary = {
            "case_number": idx,
            "row_index_in_150_loss_slice": case["row_index_in_150_loss_slice"],
            "case_id": case_id,
            "source": case["source"],
            "source_timestamp_or_run": args.source_run,
            "dataset": ds,
            "provider": case["provider"],
            "model": case["model"],
            "seed": case["seed"],
            "budget": case["budget"],
            "example_id": ex_id,
            "runtime_method_strict_f3": pick(case["strict_row"], "runtime_method", default="NA"),
            "runtime_method_external_l1_max": pick(case["external_row"], "runtime_method", default="NA"),
            "problem_statement": q,
            "raw_gold_answer": gold_raw,
            "gold_answer_extracted": gold_final_raw,
            "gold_answer_normalized": gold_norm,
            "problem_type": problem_type,
            **tags,
            "strict_f3_final_answer_raw": strict_raw,
            "strict_f3_final_answer_normalized": strict_norm,
            "strict_f3_exact_match": strict_correct,
            "strict_f3_failure_type": pick(case["strict_row"], "failure_type", default="NA"),
            "strict_f3_absent_from_tree": as_int(pick(case["strict_row"], "absent_from_tree", default=0), 0),
            "strict_f3_present_not_selected": as_int(pick(case["strict_row"], "present_not_selected", default=0), 0),
            "strict_f3_output_layer_mismatch": as_int(pick(case["strict_row"], "output_layer_mismatch", default=0), 0),
            "strict_f3_actions_used": as_int(pick(case["strict_row"], "actions_used", default=0), 0),
            "strict_f3_expansions": as_int(pick(case["strict_row"], "expansions", default=0), 0),
            "strict_f3_verifications": as_int(pick(case["strict_row"], "verifications", default=0), 0),
            "strict_f3_oracle_gap": pick(case["strict_row"], "oracle_gap", default="NA"),
            "strict_f3_oracle_regret": pick(case["strict_row"], "oracle_regret", default="NA"),
            "strict_f3_repeated_same_family_expansion_rate": pick(case["strict_row"], "repeated_same_family_expansion_rate", default="NA"),
            "strict_f3_max_family_expansion_share": pick(case["strict_row"], "max_family_expansion_share", default="NA"),
            "external_l1_max_final_answer_raw": ext_raw,
            "external_l1_max_final_answer_normalized": ext_norm,
            "external_l1_max_exact_match": ext_correct,
            "external_l1_max_failure_type": pick(case["external_row"], "failure_type", default="NA"),
            "external_l1_max_actions_used": as_int(pick(case["external_row"], "actions_used", default=0), 0),
            "external_l1_max_expansions": as_int(pick(case["external_row"], "expansions", default=0), 0),
            "external_l1_max_verifications": as_int(pick(case["external_row"], "verifications", default=0), 0),
            "external_l1_max_oracle_gap": pick(case["external_row"], "oracle_gap", default="NA"),
            "external_l1_max_oracle_regret": pick(case["external_row"], "oracle_regret", default="NA"),
            "mapping_rule": mapping_rule,
            "mapping_status": mapping_status,
            "strict_trace_status": strict_trace["trace_status"],
            "external_trace_status": ext_trace["trace_status"],
        }
        summary_rows.append(summary)

        strict_detail = {
            "case_id": case_id,
            "case_number": idx,
            "method": "strict_f3",
            "runtime_method": pick(case["strict_row"], "runtime_method", default="NA"),
            "final_answer_raw": strict_raw,
            "final_answer_normalized": strict_norm,
            "exact_match": strict_correct,
            "failure_type": pick(case["strict_row"], "failure_type", default="NA"),
            "absent_from_tree": as_int(pick(case["strict_row"], "absent_from_tree", default=0), 0),
            "present_not_selected": as_int(pick(case["strict_row"], "present_not_selected", default=0), 0),
            "output_layer_mismatch": as_int(pick(case["strict_row"], "output_layer_mismatch", default=0), 0),
            "actions_used": as_int(pick(case["strict_row"], "actions_used", default=0), 0),
            "expansions": as_int(pick(case["strict_row"], "expansions", default=0), 0),
            "verifications": as_int(pick(case["strict_row"], "verifications", default=0), 0),
            "oracle_gap": pick(case["strict_row"], "oracle_gap", default="NA"),
            "oracle_regret": pick(case["strict_row"], "oracle_regret", default="NA"),
            "repeated_same_family_expansion_rate": pick(case["strict_row"], "repeated_same_family_expansion_rate", default="NA"),
            "max_family_expansion_share": pick(case["strict_row"], "max_family_expansion_share", default="NA"),
        }
        strict_rows.append(strict_detail)

        ext_rows.append(
            {
                "case_id": case_id,
                "case_number": idx,
                "method": "external_l1_max",
                "runtime_method": pick(case["external_row"], "runtime_method", default="NA"),
                "final_answer_raw": ext_raw,
                "final_answer_normalized": ext_norm,
                "exact_match": ext_correct,
                "failure_type": pick(case["external_row"], "failure_type", default="NA"),
                "actions_used": as_int(pick(case["external_row"], "actions_used", default=0), 0),
                "expansions": as_int(pick(case["external_row"], "expansions", default=0), 0),
                "verifications": as_int(pick(case["external_row"], "verifications", default=0), 0),
                "oracle_gap": pick(case["external_row"], "oracle_gap", default="NA"),
                "oracle_regret": pick(case["external_row"], "oracle_regret", default="NA"),
            }
        )

        strict_branch_rows.append(
            {
                "case_id": case_id,
                "case_number": idx,
                "trace_status": strict_trace["trace_status"],
                "trace_source": strict_trace["trace_source"],
                "action_trace": strict_trace["action_trace"],
                "branches": strict_trace["branches"],
                "note": strict_trace["message"],
            }
        )
        ext_trace_rows.append(
            {
                "case_id": case_id,
                "case_number": idx,
                "trace_status": ext_trace["trace_status"],
                "trace_source": ext_trace["trace_source"],
                "prompt": ext_trace.get("prompt", "NA"),
                "response_text": ext_trace.get("response_text", "NA"),
                "action_counts": ext_trace.get("action_counts", []),
                "note": ext_trace["message"],
            }
        )
        strict_action_rows.append(
            {
                "case_id": case_id,
                "case_number": idx,
                "trace_status": strict_trace["trace_status"],
                "actions_used": strict_detail["actions_used"],
                "expansions": strict_detail["expansions"],
                "verifications": strict_detail["verifications"],
                "action_trace": strict_trace["action_trace"],
            }
        )

        answer_diag_rows.append(
            {
                "case_id": case_id,
                "case_number": idx,
                "selected_answer_group": "NA",
                "gold_answer_group": "NA",
                "top_answer_group": "NA",
                "answer_group_support_counts": "NA",
                "top2_support_gap": "NA",
                "answer_entropy": "NA",
                "commit_margin": "NA",
                "commit_guard_state": "NA",
                "recoverability_note": "Branch-level answer group diagnostics are not present in the available committed artifacts for this run.",
            }
        )

        for field in required_fields:
            missing_rows.append(
                {
                    "case_id": case_id,
                    "case_number": idx,
                    "field": field,
                    "status": "missing",
                    "reason": "Not emitted in available artifacts; requires rerun with full trace logging.",
                }
            )

    return {
        "summary_rows": summary_rows,
        "strict_rows": strict_rows,
        "ext_rows": ext_rows,
        "strict_branch_rows": strict_branch_rows,
        "ext_trace_rows": ext_trace_rows,
        "strict_action_rows": strict_action_rows,
        "answer_diag_rows": answer_diag_rows,
        "missing_rows": missing_rows,
    }


def build_casebook(summary_rows: list[dict[str, Any]]) -> str:
    lines = ["# Ten-Case strict_f3 Loss Deep Dive", ""]
    strict_unavailable = "Full branch/step traces were not emitted by the original run and cannot be recovered without rerunning the model."
    ext_unavailable = "External baseline reasoning text was not emitted by the original run and cannot be recovered without rerunning the model."

    for r in summary_rows:
        diag = "strict_f3 failed while baseline succeeded; likely selection/coverage issue based on aggregate counters only."
        if as_int(r.get("strict_f3_absent_from_tree"), 0) == 1:
            diag = "strict_f3 marked absent_from_tree, so the gold answer likely never appeared in explored branches."
        elif as_int(r.get("strict_f3_present_not_selected"), 0) == 1:
            diag = "strict_f3 marked present_not_selected, so a correct branch likely existed but lost selection."

        lines.extend(
            [
                f"## Case {r['case_number']}: {r['example_id']}, seed={r['seed']}, budget={r['budget']}",
                "",
                "### Problem",
                str(r.get("problem_statement", "NA")),
                "",
                "### Gold answer",
                f"Raw: {r.get('raw_gold_answer', 'NA')}",
                f"Normalized: {r.get('gold_answer_normalized', 'NA')}",
                "",
                "### strict_f3 result",
                f"- final answer: {r.get('strict_f3_final_answer_raw', 'NA')}",
                f"- normalized answer: {r.get('strict_f3_final_answer_normalized', 'NA')}",
                f"- correct?: {'yes' if as_int(r.get('strict_f3_exact_match'), 0) == 1 else 'no'}",
                f"- failure type: {r.get('strict_f3_failure_type', 'NA')}",
                f"- absent_from_tree: {r.get('strict_f3_absent_from_tree', 'NA')}",
                f"- present_not_selected: {r.get('strict_f3_present_not_selected', 'NA')}",
                f"- actions / expansions / verifications: {r.get('strict_f3_actions_used', 'NA')} / {r.get('strict_f3_expansions', 'NA')} / {r.get('strict_f3_verifications', 'NA')}",
                f"- runtime method: {r.get('runtime_method_strict_f3', 'NA')}",
                f"- short diagnosis: {diag}",
                "",
                "### external_l1_max result",
                f"- final answer: {r.get('external_l1_max_final_answer_raw', 'NA')}",
                f"- normalized answer: {r.get('external_l1_max_final_answer_normalized', 'NA')}",
                f"- correct?: {'yes' if as_int(r.get('external_l1_max_exact_match'), 0) == 1 else 'no'}",
                f"- actions / expansions / verifications: {r.get('external_l1_max_actions_used', 'NA')} / {r.get('external_l1_max_expansions', 'NA')} / {r.get('external_l1_max_verifications', 'NA')}",
                f"- runtime method: {r.get('runtime_method_external_l1_max', 'NA')}",
                "- short diagnosis: External baseline produced the accepted answer in this paired comparison.",
                "",
                "### strict_f3 reasoning/tree details",
                strict_unavailable,
                "",
                "### external_l1_max reasoning details",
                ext_unavailable,
                "",
                "### What is recoverable vs not recoverable",
                "Recoverable: case identity, method config, correctness, failure flags, aggregate actions/expansions/verifications, oracle gap/regret, GSM8K question/gold mapping.",
                "Not recoverable from current artifacts: full prompt/response traces, branch tables, per-branch scores, answer-group support diagnostics, commit guard internals.",
                "",
                "### Hypothesis for why strict_f3 lost",
                "Based on available aggregate evidence only, strict_f3 appears to lose due to either missing the gold answer in explored tree states or ranking/selection failures when a candidate answer was present, while the external baseline returns the correct normalized answer for the same case slice.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    cases, source_note, _ = select_cases(args)
    if not cases:
        raise RuntimeError("No loss cases found from available artifacts.")

    gsm_map: dict[int, dict[str, str]] = {}
    mapping_rule = "not_attempted"
    if args.recover_gsm8k:
        gsm_map, mapping_rule = load_gsm8k_index_map(args.dataset, args.config, args.split)

    built = build_case_records(cases, gsm_map, mapping_rule, args)

    ts = args.timestamp
    out_dir = REPO_ROOT / "outputs" / f"ten_case_loss_deep_dive_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = built["summary_rows"]
    write_csv(out_dir / "ten_case_summary.csv", summary_rows)
    write_jsonl(out_dir / "ten_case_summary.jsonl", summary_rows)
    write_jsonl(out_dir / "strict_f3_case_details.jsonl", built["strict_rows"])
    write_jsonl(out_dir / "external_l1_max_case_details.jsonl", built["ext_rows"])
    write_jsonl(out_dir / "strict_f3_branch_traces.jsonl", built["strict_branch_rows"])
    write_jsonl(out_dir / "external_l1_max_traces.jsonl", built["ext_trace_rows"])
    write_jsonl(out_dir / "strict_f3_action_traces.jsonl", built["strict_action_rows"])
    write_jsonl(out_dir / "answer_group_diagnostics.jsonl", built["answer_diag_rows"])
    write_csv(
        out_dir / "missing_fields_report.csv",
        built["missing_rows"],
        fieldnames=["case_id", "case_number", "field", "status", "reason"],
    )

    readme = "\n".join(
        [
            f"# ten_case_loss_deep_dive_{ts}",
            "",
            f"- Source selection rule: first `max_cases={args.max_cases}` where strict_f3 lost to external_l1_max.",
            f"- Source artifact used: `{source_note}`",
            f"- per-example source run: `{args.source_run}`",
            f"- recover_gsm8k: {args.recover_gsm8k}",
            f"- rerun_traces: {args.rerun_traces}",
            f"- dry_run: {args.dry_run}",
            "- If traces are unavailable, files include explicit unrecoverable notes and missing-field report entries.",
            "",
            "## Optional rerun command for 10-case trace capture",
            "```bash",
            f"python scripts/build_10_case_loss_deep_dive.py --timestamp {ts} --max-cases 10 --input-package {args.input_package} --source-run {args.source_run} --recover-gsm8k --rerun-traces --provider {args.provider} --cohere-model {args.cohere_model} --resume --skip-real-api-if-no-key",
            "```",
        ]
    ) + "\n"
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    casebook = build_casebook(summary_rows)
    (out_dir / "casebook.md").write_text(casebook, encoding="utf-8")

    docs_path = REPO_ROOT / "docs" / f"TEN_CASE_LOSS_DEEP_DIVE_{ts}.md"
    docs_path.write_text(
        "\n".join(
            [
                f"# TEN_CASE_LOSS_DEEP_DIVE_{ts}",
                "",
                "This report mirrors the package casebook for the first 10 strict_f3 loss cases versus external_l1_max.",
                "",
                f"- Package directory: `outputs/ten_case_loss_deep_dive_{ts}/`",
                f"- Source: `{source_note}`",
                f"- Mapping rule: `{mapping_rule}`",
                "",
                casebook,
            ]
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "cases": len(summary_rows),
                "output_dir": str(out_dir.relative_to(REPO_ROOT)),
                "docs_report": str(docs_path.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
