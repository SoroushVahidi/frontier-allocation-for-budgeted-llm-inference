#!/usr/bin/env python3
"""Diagnostic-only Cobbe-style outcome-verifier selector over existing traced candidates.

This script only reranks already-generated candidates; it never calls real model APIs.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.output_layer_repair import canonicalize_answer
from scripts.learned_branch_scorer_utils import as_float, as_int, read_csv, write_csv


@dataclass(frozen=True)
class CaseKey:
    dataset: str
    example_id: str
    seed: int
    budget: int


DEFAULT_CASEBOOK = "outputs/l1_better_than_frontier_casebook_20260426T232030Z"
DEFAULT_TRACE = "outputs/direct_reserve_frontier_gate_failure_slice_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN_DIAGNOSTIC_ACTUAL"
DEFAULT_COST = "outputs/cohere_real_model_cost_normalized_validation_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN"

FALLBACK_TRACE_DIRS = [
    "outputs/cohere_direct_reserve_failure_replay_seed_latest",
    "outputs/cohere_direct_reserve_validation_DIRECT_RESERVE_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN_DIAGNOSTIC_ACTUAL",
]
FALLBACK_COST_DIRS = [
    "outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--casebook-dir", default=DEFAULT_CASEBOOK)
    p.add_argument("--trace-dir", default=DEFAULT_TRACE)
    p.add_argument("--cost-dir", default=DEFAULT_COST)
    p.add_argument("--alpha-grid", default="0.0,0.1,0.25")
    p.add_argument("--beta-grid", default="0.0,0.1,0.25")
    p.add_argument("--gamma-grid", default="0.0,0.1,0.25")
    return p.parse_args()


def _parse_grid(text: str) -> list[float]:
    vals: list[float] = []
    for tok in str(text).split(","):
        tok = tok.strip()
        if not tok:
            continue
        vals.append(float(tok))
    return vals or [0.0]


def _norm(raw: Any, dataset: str) -> str:
    t = str(raw or "").strip()
    if not t:
        return "NA"
    try:
        c = canonicalize_answer(t, dataset=dataset)
        if c is None:
            return "NA"
        return str(c)
    except Exception:
        return t


def _resolve_dir(primary: str, fallbacks: list[str], required_files: list[str]) -> Path:
    candidates = [primary] + fallbacks
    for c in candidates:
        p = (REPO_ROOT / c).resolve()
        if p.exists() and all((p / f).exists() for f in required_files):
            return p
    raise SystemExit(f"Unable to find usable directory from: {candidates}")


def _load_method_predictions(trace_dir: Path, cost_dir: Path) -> dict[CaseKey, dict[str, str]]:
    out: dict[CaseKey, dict[str, str]] = defaultdict(dict)
    per_case = read_csv(trace_dir / "per_case_method_results.csv")
    for r in per_case:
        ck = CaseKey(
            dataset=str(r.get("dataset", "openai/gsm8k")),
            example_id=str(r.get("example_id", "")),
            seed=as_int(r.get("seed", -1), -1),
            budget=as_int(r.get("budget", -1), -1),
        )
        out[ck][str(r.get("method", ""))] = _norm(r.get("normalized_selected_answer", r.get("final_selected_answer", "")), ck.dataset)
        out[ck]["gold_answer"] = _norm(r.get("gold_answer", ""), ck.dataset)

    if out:
        return out

    # fallback to cost-normalized per-example records if needed
    records_path = cost_dir / "per_example_records.jsonl"
    if records_path.exists():
        with records_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                ck = CaseKey(
                    dataset=str(d.get("dataset", "openai/gsm8k")),
                    example_id=str(d.get("example_id", "")),
                    seed=as_int(d.get("seed", -1), -1),
                    budget=as_int(d.get("budget", -1), -1),
                )
                out[ck][str(d.get("method", ""))] = _norm(d.get("prediction", d.get("final_answer", "")), ck.dataset)
                out[ck]["gold_answer"] = _norm(d.get("gold_answer", ""), ck.dataset)
    return out


def build_answer_buckets(trace_dir: Path, method_preds: dict[CaseKey, dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    branch_rows = read_csv(trace_dir / "candidate_branch_table.csv")
    ag_rows = read_csv(trace_dir / "answer_group_summary.csv")
    support_map: dict[tuple[CaseKey, str, str], int] = {}
    selected_group_map: dict[tuple[CaseKey, str], str] = {}
    for r in ag_rows:
        ck = CaseKey(str(r.get("dataset", "openai/gsm8k")), str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1))
        method = str(r.get("method", ""))
        grp = _norm(r.get("answer_group", ""), ck.dataset)
        support_map[(ck, method, grp)] = max(as_int(r.get("support", 0), 0), support_map.get((ck, method, grp), 0))
        if str(r.get("is_selected_group", "")).strip().lower() in {"1", "true", "yes"}:
            selected_group_map[(ck, method)] = grp

    bucket_acc: dict[tuple[CaseKey, str], dict[str, Any]] = {}
    branch_feature_rows: list[dict[str, Any]] = []

    for b in branch_rows:
        ck = CaseKey(str(b.get("dataset", "openai/gsm8k")), str(b.get("example_id", "")), as_int(b.get("seed", -1), -1), as_int(b.get("budget", -1), -1))
        method = str(b.get("method", ""))
        norm_ans = _norm(b.get("normalized_candidate_answer", b.get("predicted_answer", "")), ck.dataset)
        key = (ck, norm_ans)
        fam = str(b.get("branch_prompt_style", "na")) or "na"
        depth = as_int(b.get("branch_depth", 0), 0)
        pred_text = str(b.get("predicted_answer", ""))
        parse_success = int(norm_ans not in {"NA", ""})
        output_repair_flag = int(_norm(pred_text, ck.dataset) != pred_text.strip()) if pred_text.strip() else 0
        l1_ans = method_preds.get(ck, {}).get("external_l1_max", "NA")
        f3_ans = method_preds.get(ck, {}).get("strict_f3", "NA")
        gold = method_preds.get(ck, {}).get("gold_answer", "NA")

        row = {
            "dataset": ck.dataset,
            "example_id": ck.example_id,
            "seed": ck.seed,
            "budget": ck.budget,
            "method": method,
            "branch_id": str(b.get("branch_id", "")),
            "normalized_answer": norm_ans,
            "branch_depth": depth,
            "branch_prompt_style": fam,
            "reasoning_length": len(str(b.get("reasoning_text", "") or "")),
            "raw_length": len(str(b.get("raw_branch_text", "") or "")),
            "parse_success": parse_success,
            "output_repair_flag": output_repair_flag,
            "equals_external_l1_max": int(norm_ans == l1_ans and l1_ans not in {"NA", ""}),
            "equals_strict_f3": int(norm_ans == f3_ans and f3_ans not in {"NA", ""}),
            "is_gold_candidate": int(norm_ans == gold and gold not in {"NA", ""}),
            "numeric_parse_success": int(_is_number_like(norm_ans)),
            "numeric_abs_value": abs(_to_float(norm_ans)) if _is_number_like(norm_ans) else -1.0,
        }
        branch_feature_rows.append(row)

        if key not in bucket_acc:
            bucket_acc[key] = {
                "dataset": ck.dataset,
                "example_id": ck.example_id,
                "seed": ck.seed,
                "budget": ck.budget,
                "normalized_answer": norm_ans,
                "candidate_branch_ids": [],
                "methods": set(),
                "families": set(),
                "max_maturity": 0,
                "mean_maturity_sum": 0.0,
                "mean_maturity_n": 0,
                "support_count": 0,
                "equals_external_l1_max": int(norm_ans == l1_ans and l1_ans not in {"NA", ""}),
                "equals_strict_f3": int(norm_ans == f3_ans and f3_ans not in {"NA", ""}),
                "equals_gold_offline": int(norm_ans == gold and gold not in {"NA", ""}),
                "gold_answer": gold,
                "selected_by_strict_f3": 0,
                "selected_by_external_l1_max": 0,
            }
        acc = bucket_acc[key]
        acc["candidate_branch_ids"].append(str(b.get("branch_id", "")))
        acc["methods"].add(method)
        acc["families"].add(fam)
        acc["max_maturity"] = max(acc["max_maturity"], depth)
        acc["mean_maturity_sum"] += float(depth)
        acc["mean_maturity_n"] += 1
        acc["support_count"] = max(acc["support_count"], support_map.get((ck, method, norm_ans), 0))
        if selected_group_map.get((ck, "strict_f3"), "") == norm_ans:
            acc["selected_by_strict_f3"] = 1
        if selected_group_map.get((ck, "external_l1_max"), "") == norm_ans:
            acc["selected_by_external_l1_max"] = 1

    buckets: list[dict[str, Any]] = []
    for acc in bucket_acc.values():
        n = max(1, int(acc.pop("mean_maturity_n")))
        acc["mean_maturity"] = float(acc.pop("mean_maturity_sum")) / n
        acc["family_count"] = len(acc.pop("families"))
        acc["method_count"] = len(acc.pop("methods"))
        acc["candidate_branch_count"] = len(acc["candidate_branch_ids"])
        acc["candidate_branch_ids"] = "|".join(sorted(x for x in acc["candidate_branch_ids"] if x))
        buckets.append(acc)

    return buckets, branch_feature_rows


def _to_float(v: str) -> float:
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return 0.0


def _is_number_like(v: str) -> bool:
    try:
        float(str(v).replace(",", ""))
        return True
    except Exception:
        return False


def build_training_rows(buckets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for b in buckets:
        rows.append(
            {
                "dataset": b["dataset"],
                "example_id": b["example_id"],
                "seed": b["seed"],
                "budget": b["budget"],
                "normalized_answer": b["normalized_answer"],
                # features
                "support_count": as_float(b.get("support_count", 0), 0.0),
                "max_maturity": as_float(b.get("max_maturity", 0), 0.0),
                "mean_maturity": as_float(b.get("mean_maturity", 0), 0.0),
                "family_count": as_float(b.get("family_count", 0), 0.0),
                "candidate_branch_count": as_float(b.get("candidate_branch_count", 0), 0.0),
                "equals_external_l1_max": as_float(b.get("equals_external_l1_max", 0), 0.0),
                "equals_strict_f3": as_float(b.get("equals_strict_f3", 0), 0.0),
                "parse_success": 1.0 if str(b.get("normalized_answer", "")) not in {"NA", ""} else 0.0,
                "numeric_parse_success": 1.0 if _is_number_like(str(b.get("normalized_answer", ""))) else 0.0,
                "numeric_abs_value": abs(_to_float(str(b.get("normalized_answer", "")))) if _is_number_like(str(b.get("normalized_answer", ""))) else -1.0,
                # labels / diagnostics
                "label_is_correct": as_int(b.get("equals_gold_offline", 0), 0),
                "gold_answer": str(b.get("gold_answer", "NA")),
            }
        )
    return rows


def _feature_matrix(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    feature_names = [
        "support_count",
        "max_maturity",
        "mean_maturity",
        "family_count",
        "candidate_branch_count",
        "equals_external_l1_max",
        "equals_strict_f3",
        "parse_success",
        "numeric_parse_success",
        "numeric_abs_value",
    ]
    X = np.array([[float(r.get(f, 0.0)) for f in feature_names] for r in rows], dtype=float)
    y = np.array([int(r.get("label_is_correct", 0)) for r in rows], dtype=int)
    return X, y, feature_names


def _group_by_case(rows: list[dict[str, Any]]) -> dict[tuple[str, int, int, str], list[dict[str, Any]]]:
    g: dict[tuple[str, int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        k = (str(r.get("dataset", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1), str(r.get("example_id", "")))
        g[k].append(r)
    return g


def _loeo_train_predict(train_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_case = _group_by_case(train_rows)
    case_keys = sorted(by_case.keys())
    pred_rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []

    for holdout in case_keys:
        tr = [r for ck, rr in by_case.items() if ck != holdout for r in rr]
        te = list(by_case[holdout])
        if not tr or not te:
            continue
        Xtr, ytr, _ = _feature_matrix(tr)
        Xte, yte, _ = _feature_matrix(te)

        # handle degenerate label folds
        if len(set(ytr.tolist())) < 2:
            probs = np.full(shape=(len(te),), fill_value=float(np.mean(ytr)))
        else:
            clf = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=7)
            clf.fit(Xtr, ytr)
            probs = clf.predict_proba(Xte)[:, 1]

        yp = (probs >= 0.5).astype(int)
        auc = None
        if len(set(yte.tolist())) > 1:
            try:
                auc = float(roc_auc_score(yte, probs))
            except Exception:
                auc = None
        report_rows.append(
            {
                "dataset": holdout[0],
                "seed": holdout[1],
                "budget": holdout[2],
                "example_id": holdout[3],
                "n_train_rows": len(tr),
                "n_test_rows": len(te),
                "fold_accuracy": float(accuracy_score(yte, yp)),
                "fold_auc": "" if auc is None else auc,
            }
        )
        for row, p in zip(te, probs):
            pred_rows.append({**row, "verifier_score": float(p)})

    return pred_rows, report_rows


def select_by_rule(buckets: list[dict[str, Any]], method_preds: dict[CaseKey, dict[str, str]], scored_rows: list[dict[str, Any]], alpha: float, beta: float, gamma: float) -> tuple[list[dict[str, Any]], dict[str, float]]:
    by_case = _group_by_case(buckets)
    by_case_scored = _group_by_case(scored_rows)
    decisions: list[dict[str, Any]] = []

    for ck_tuple, case_buckets in by_case.items():
        ck = CaseKey(ck_tuple[0], ck_tuple[3], ck_tuple[1], ck_tuple[2])
        strict_ans = method_preds.get(ck, {}).get("strict_f3", "NA")
        l1_ans = method_preds.get(ck, {}).get("external_l1_max", "NA")
        gold = method_preds.get(ck, {}).get("gold_answer", "NA")

        def pick_max(key_name: str) -> str:
            best = sorted(case_buckets, key=lambda b: (as_float(b.get(key_name, 0), 0.0), as_float(b.get("support_count", 0), 0.0), b.get("normalized_answer", "")), reverse=True)[0]
            return str(best.get("normalized_answer", "NA"))

        scored_lookup = {str(r["normalized_answer"]): float(r.get("verifier_score", 0.0)) for r in by_case_scored.get(ck_tuple, [])}

        def verifier_group_score(b: dict[str, Any]) -> float:
            cand = scored_lookup.get(str(b.get("normalized_answer", "NA")), 0.0)
            return cand + alpha * cand + beta * math.log1p(max(0.0, as_float(b.get("support_count", 0), 0.0))) + gamma * as_float(b.get("family_count", 0), 0.0)

        verifier_pick = sorted(case_buckets, key=lambda b: (verifier_group_score(b), as_float(b.get("support_count", 0), 0.0), b.get("normalized_answer", "")), reverse=True)[0]

        l1_present = any(str(b.get("normalized_answer", "")) == l1_ans for b in case_buckets)
        oracle_pick = next((b for b in case_buckets if as_int(b.get("equals_gold_offline", 0), 0) == 1), None)

        choices = {
            "strict_f3_selection": strict_ans,
            "external_l1_max": l1_ans,
            "highest_support": pick_max("support_count"),
            "highest_maturity": pick_max("max_maturity"),
            "highest_family_count": pick_max("family_count"),
            "support_plus_maturity": sorted(
                case_buckets,
                key=lambda b: (
                    as_float(b.get("support_count", 0), 0.0) + as_float(b.get("max_maturity", 0), 0.0),
                    as_float(b.get("family_count", 0), 0.0),
                    b.get("normalized_answer", ""),
                ),
                reverse=True,
            )[0]["normalized_answer"],
            "l1_preserve_if_present": l1_ans if l1_present else strict_ans,
            "oracle_if_gold_present": str(oracle_pick["normalized_answer"]) if oracle_pick is not None else strict_ans,
            "diagnostic_outcome_verifier_selector": str(verifier_pick["normalized_answer"]),
        }

        row: dict[str, Any] = {
            "dataset": ck.dataset,
            "example_id": ck.example_id,
            "seed": ck.seed,
            "budget": ck.budget,
            "gold_answer": gold,
            "l1_better_case": int(l1_ans == gold and strict_ans != gold and gold not in {"NA", ""}),
            "frontier_better_case": int(strict_ans == gold and l1_ans != gold and gold not in {"NA", ""}),
            "both_wrong_case": int(strict_ans != gold and l1_ans != gold and gold not in {"NA", ""}),
            "gold_present_in_candidate_pool": int(any(as_int(b.get("equals_gold_offline", 0), 0) == 1 for b in case_buckets)),
        }
        for k, pred in choices.items():
            row[f"selected__{k}"] = pred
            row[f"correct__{k}"] = int(pred == gold and gold not in {"NA", ""})
        decisions.append(row)

    summary: dict[str, float] = {}
    if decisions:
        n = len(decisions)
        for sel in [
            "external_l1_max",
            "strict_f3_selection",
            "highest_support",
            "highest_maturity",
            "highest_family_count",
            "support_plus_maturity",
            "l1_preserve_if_present",
            "oracle_if_gold_present",
            "diagnostic_outcome_verifier_selector",
        ]:
            summary[f"{sel}_accuracy"] = sum(as_int(r.get(f"correct__{sel}", 0), 0) for r in decisions) / n
        summary["matched_examples"] = float(n)

    return decisions, summary


def build_selector_summary(decisions: list[dict[str, Any]], verifier_summary: dict[str, float]) -> list[dict[str, Any]]:
    if not decisions:
        return []
    n = len(decisions)
    rows: list[dict[str, Any]] = []
    selectors = [
        "external_l1_max",
        "strict_f3_selection",
        "highest_support",
        "highest_maturity",
        "highest_family_count",
        "support_plus_maturity",
        "l1_preserve_if_present",
        "oracle_if_gold_present",
        "diagnostic_outcome_verifier_selector",
    ]
    for s in selectors:
        acc = sum(as_int(r.get(f"correct__{s}", 0), 0) for r in decisions) / n
        rows.append({"selector": s, "n_cases": n, "accuracy": acc})

    best_non_oracle = max((r for r in rows if r["selector"] not in {"oracle_if_gold_present", "diagnostic_outcome_verifier_selector"}), key=lambda x: x["accuracy"])
    diag = next(r for r in rows if r["selector"] == "diagnostic_outcome_verifier_selector")
    rows.append(
        {
            "selector": "diagnostic_notes",
            "n_cases": n,
            "accuracy": diag["accuracy"],
            "best_non_neural_selector": best_non_oracle["selector"],
            "best_non_neural_accuracy": best_non_oracle["accuracy"],
            "verifier_candidate_level_accuracy": verifier_summary.get("candidate_level_accuracy", ""),
            "verifier_candidate_level_auc": verifier_summary.get("candidate_level_auc", ""),
        }
    )
    for subset_key, label in [
        ("l1_better_case", "l1_better_subset"),
        ("frontier_better_case", "frontier_better_subset"),
        ("both_wrong_case", "both_wrong_subset"),
    ]:
        sub = [r for r in decisions if as_int(r.get(subset_key, 0), 0) == 1]
        if not sub:
            continue
        rows.append(
            {
                "selector": f"subset__{label}",
                "n_cases": len(sub),
                "accuracy": sum(as_int(r.get("correct__diagnostic_outcome_verifier_selector", 0), 0) for r in sub) / len(sub),
                "external_l1_max_accuracy": sum(as_int(r.get("correct__external_l1_max", 0), 0) for r in sub) / len(sub),
                "strict_f3_accuracy": sum(as_int(r.get("correct__strict_f3_selection", 0), 0) for r in sub) / len(sub),
            }
        )
    return rows


def evaluate_subset(decisions: list[dict[str, Any]], subset_key: str, selector: str) -> float:
    sub = [r for r in decisions if as_int(r.get(subset_key, 0), 0) == 1]
    if not sub:
        return float("nan")
    return sum(as_int(r.get(f"correct__{selector}", 0), 0) for r in sub) / len(sub)


def main() -> None:
    args = parse_args()
    trace_dir = _resolve_dir(args.trace_dir, FALLBACK_TRACE_DIRS, ["candidate_branch_table.csv", "answer_group_summary.csv", "per_case_method_results.csv"])
    cost_dir = _resolve_dir(args.cost_dir, FALLBACK_COST_DIRS, ["per_example_records.jsonl"])
    casebook_dir = (REPO_ROOT / args.casebook_dir).resolve()

    alpha_grid = _parse_grid(args.alpha_grid)
    beta_grid = _parse_grid(args.beta_grid)
    gamma_grid = _parse_grid(args.gamma_grid)

    out_dir = REPO_ROOT / "outputs" / f"outcome_verifier_selector_diagnostic_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    method_preds = _load_method_predictions(trace_dir, cost_dir)
    buckets, branch_features = build_answer_buckets(trace_dir, method_preds)
    train_rows = build_training_rows(buckets)
    scored_rows, fold_report = _loeo_train_predict(train_rows)

    y_true = np.array([as_int(r.get("label_is_correct", 0), 0) for r in scored_rows], dtype=int) if scored_rows else np.array([], dtype=int)
    y_prob = np.array([as_float(r.get("verifier_score", 0.0), 0.0) for r in scored_rows], dtype=float) if scored_rows else np.array([], dtype=float)
    verifier_summary: dict[str, float] = {}
    if len(y_true) > 0:
        verifier_summary["candidate_level_accuracy"] = float(accuracy_score(y_true, (y_prob >= 0.5).astype(int)))
        if len(set(y_true.tolist())) > 1:
            verifier_summary["candidate_level_auc"] = float(roc_auc_score(y_true, y_prob))

    best = None
    best_decisions: list[dict[str, Any]] = []
    best_summary: dict[str, float] = {}
    for a in alpha_grid:
        for b in beta_grid:
            for g in gamma_grid:
                drows, s = select_by_rule(buckets, method_preds, scored_rows, a, b, g)
                key_acc = s.get("diagnostic_outcome_verifier_selector_accuracy", -1.0)
                if best is None or key_acc > best[0]:
                    best = (key_acc, a, b, g)
                    best_decisions = drows
                    best_summary = s

    selector_summary = build_selector_summary(best_decisions, verifier_summary)

    gold_present_not_selected = sum(
        1
        for r in best_decisions
        if as_int(r.get("gold_present_in_candidate_pool", 0), 0) == 1 and as_int(r.get("correct__diagnostic_outcome_verifier_selector", 0), 0) == 0
    )
    fixed_cases = sum(
        1
        for r in best_decisions
        if as_int(r.get("correct__diagnostic_outcome_verifier_selector", 0), 0) == 1 and as_int(r.get("correct__strict_f3_selection", 0), 0) == 0
    )
    harmed_cases = sum(
        1
        for r in best_decisions
        if as_int(r.get("correct__diagnostic_outcome_verifier_selector", 0), 0) == 0 and as_int(r.get("correct__strict_f3_selection", 0), 0) == 1
    )

    oracle_rows = [
        {"metric": "gold_present_but_not_selected_count", "value": gold_present_not_selected},
        {"metric": "cases_fixed_by_verifier_selector", "value": fixed_cases},
        {"metric": "cases_harmed_by_verifier_selector", "value": harmed_cases},
        {"metric": "improvement_over_l1_clean_or_artifact_sensitive", "value": "artifact-sensitive" if harmed_cases > 0 else "clean-on-this-slice"},
    ]

    l1_subset_rows = []
    for s in ["external_l1_max", "strict_f3_selection", "l1_preserve_if_present", "diagnostic_outcome_verifier_selector"]:
        l1_subset_rows.append({"selector": s, "l1_better_subset_accuracy": evaluate_subset(best_decisions, "l1_better_case", s)})

    write_csv(out_dir / "candidate_answer_groups.csv", buckets)
    write_csv(out_dir / "candidate_branch_features.csv", branch_features)
    write_csv(out_dir / "selector_summary.csv", selector_summary)
    write_csv(out_dir / "per_case_selector_decisions.csv", best_decisions)
    write_csv(out_dir / "verifier_training_report.csv", fold_report)
    write_csv(out_dir / "oracle_gap_report.csv", oracle_rows)
    write_csv(out_dir / "l1_better_subset_selector_report.csv", l1_subset_rows)

    summary_lines = [
        "# Outcome verifier selector diagnostic",
        "",
        "## Inputs",
        f"- casebook_dir: `{casebook_dir}` (optional reference)",
        f"- trace_dir: `{trace_dir}`",
        f"- cost_dir: `{cost_dir}`",
        "",
        "## Selected hyperparameters",
        f"- alpha={best[1] if best else 'n/a'}",
        f"- beta={best[2] if best else 'n/a'}",
        f"- gamma={best[3] if best else 'n/a'}",
        "",
        "## Headline",
        f"- matched examples: {int(best_summary.get('matched_examples', 0))}",
        f"- external_l1_max accuracy: {best_summary.get('external_l1_max_accuracy', float('nan'))}",
        f"- strict_f3 accuracy: {best_summary.get('strict_f3_selection_accuracy', float('nan'))}",
        f"- oracle_if_gold_present accuracy: {best_summary.get('oracle_if_gold_present_accuracy', float('nan'))}",
        f"- diagnostic_outcome_verifier_selector accuracy: {best_summary.get('diagnostic_outcome_verifier_selector_accuracy', float('nan'))}",
        f"- candidate-level verifier accuracy (LOEO): {verifier_summary.get('candidate_level_accuracy', float('nan'))}",
        f"- candidate-level verifier AUC (LOEO): {verifier_summary.get('candidate_level_auc', float('nan'))}",
        "",
        "## Notes",
        "- Diagnostic-only: reranking over existing candidates; no branch generation and no API calls.",
        "- Gold equality used only as offline label, never as model input feature.",
    ]
    (out_dir / "README.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    doc = REPO_ROOT / "docs" / "OUTCOME_VERIFIER_SELECTOR_DIAGNOSTIC.md"
    doc.write_text(
        "\n".join(
            [
                "# Outcome Verifier Selector Diagnostic",
                "",
                "This diagnostic implements a Cobbe-style *outcome verifier selector* over existing frontier candidates only.",
                "",
                "## Guardrails",
                "- No real API calls.",
                "- No manuscript/canonical artifact updates.",
                "- Gold answer equality is used only as an offline training label for leakage-safe evaluation.",
                "",
                "## Run",
                "```bash",
                ".venv-test/bin/python scripts/run_outcome_verifier_selector_diagnostic.py",
                "```",
                "",
                "## Outputs",
                f"- `outputs/{out_dir.name}/candidate_answer_groups.csv`",
                f"- `outputs/{out_dir.name}/candidate_branch_features.csv`",
                f"- `outputs/{out_dir.name}/selector_summary.csv`",
                f"- `outputs/{out_dir.name}/per_case_selector_decisions.csv`",
                f"- `outputs/{out_dir.name}/verifier_training_report.csv`",
                f"- `outputs/{out_dir.name}/oracle_gap_report.csv`",
                f"- `outputs/{out_dir.name}/l1_better_subset_selector_report.csv`",
                f"- `outputs/{out_dir.name}/README.md`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote diagnostic bundle: {out_dir}")


if __name__ == "__main__":
    main()
