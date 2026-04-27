#!/usr/bin/env python3
"""Diagnostic-only Cobbe-style outcome verifier over traced Cohere GSM8K candidates.

No real API calls are made. This script consumes existing local artifacts only.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from scipy.sparse import csr_matrix, hstack

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.output_layer_repair import canonicalize_answer
from scripts.learned_branch_scorer_utils import as_float, as_int, read_csv, write_csv, write_json

TRACE_DIR_DEFAULT = "outputs/direct_reserve_frontier_gate_failure_slice_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN_DIAGNOSTIC_ACTUAL"
COST_DIR_DEFAULT = "outputs/cohere_real_model_cost_normalized_validation_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN"
CASEBOOK_DIR_DEFAULT = "outputs/l1_better_than_frontier_casebook_20260426T232030Z"

BETA_GRID = (0.0, 0.1, 0.25)
GAMMA_GRID = (0.0, 0.1, 0.25)

STRUCTURAL_FEATURES = [
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
    "branch_depth",
]


@dataclass(frozen=True)
class CaseKey:
    dataset: str
    example_id: str
    seed: int
    budget: int


def _norm(raw: Any, dataset: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return "NA"
    try:
        c = canonicalize_answer(text, dataset=dataset)
        return "NA" if c is None else str(c)
    except Exception:
        return text


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--trace-dir", default=TRACE_DIR_DEFAULT)
    p.add_argument("--cost-dir", default=COST_DIR_DEFAULT)
    p.add_argument("--casebook-dir", default=CASEBOOK_DIR_DEFAULT)
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--strict-source", action="store_true")
    p.add_argument("--required-matched-examples", type=int, default=30)
    return p.parse_args()


def ensure_strict_sources(trace_dir: Path, cost_dir: Path, required_matched_examples: int) -> None:
    req_trace = ["manifest.json", "per_case_results.csv"]
    req_cost = ["per_example_records.jsonl", "candidate_branch_table.csv", "answer_group_table.csv"]
    for f in req_trace:
        if not (trace_dir / f).exists():
            raise SystemExit(f"Missing required trace file: {trace_dir / f}")
    for f in req_cost:
        if not (cost_dir / f).exists():
            raise SystemExit(f"Missing required cost file: {cost_dir / f}")
    manifest = json.loads((trace_dir / "manifest.json").read_text(encoding="utf-8"))
    if as_int(manifest.get("matched_examples", -1), -1) != required_matched_examples:
        raise SystemExit(
            f"Strict manifest check failed: expected matched_examples={required_matched_examples}, "
            f"got {manifest.get('matched_examples')}"
        )


def _load_case_table(trace_dir: Path) -> tuple[dict[CaseKey, dict[str, str]], list[CaseKey]]:
    rows = read_csv(trace_dir / "per_case_results.csv")
    out: dict[CaseKey, dict[str, str]] = {}
    keys: list[CaseKey] = []
    for r in rows:
        ck = CaseKey(str(r.get("dataset", "openai/gsm8k")), str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1))
        out[ck] = {
            "external_l1_max": _norm(r.get("external_l1_max_prediction", ""), ck.dataset),
            "strict_f3": _norm(r.get("strict_f3_prediction", ""), ck.dataset),
            "gold_answer": _norm(r.get("gold_answer", ""), ck.dataset),
        }
        keys.append(ck)
    return out, keys


def _load_question_and_reasoning(cost_dir: Path) -> tuple[dict[CaseKey, str], dict[tuple[CaseKey, str, str], str]]:
    qmap: dict[CaseKey, str] = {}
    reasoning: dict[tuple[CaseKey, str, str], str] = {}
    with (cost_dir / "per_example_records.jsonl").open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            ck = CaseKey(str(d.get("dataset", "openai/gsm8k")), str(d.get("example_id", "")), as_int(d.get("seed", -1), -1), as_int(d.get("budget", -1), -1))
            qmap.setdefault(ck, str(d.get("question", "")))
            method = str(d.get("method", ""))
            for n in d.get("final_nodes", []) or []:
                bid = str(n.get("branch_id", ""))
                if bid:
                    reasoning[(ck, method, bid)] = str(n.get("reasoning_text", ""))
    return qmap, reasoning


def build_candidate_rows(cost_dir: Path, case_table: dict[CaseKey, dict[str, str]], case_keys: list[CaseKey]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed = set(case_keys)
    qmap, reasoning_map = _load_question_and_reasoning(cost_dir)

    ag_rows = read_csv(cost_dir / "answer_group_table.csv")
    if not ag_rows:
        raise SystemExit("answer-group rows are empty")

    support: dict[tuple[CaseKey, str, str], int] = {}
    family_count: dict[tuple[CaseKey, str, str], int] = {}
    max_depth: dict[tuple[CaseKey, str, str], int] = {}
    mean_depth_sum: dict[tuple[CaseKey, str, str], float] = defaultdict(float)
    mean_depth_n: dict[tuple[CaseKey, str, str], int] = defaultdict(int)

    for r in ag_rows:
        ck = CaseKey(str(r.get("dataset", "openai/gsm8k")), str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1))
        if ck not in allowed:
            continue
        method = str(r.get("method", ""))
        ans = _norm(r.get("answer_group", ""), ck.dataset)
        k = (ck, method, ans)
        support[k] = max(support.get(k, 0), as_int(r.get("support_count", 0), 0))
        family_count[k] = max(family_count.get(k, 0), as_int(r.get("family_count", 0), 0))
        depth = as_int(r.get("depth_max", r.get("maturity", 0)), 0)
        max_depth[k] = max(max_depth.get(k, 0), depth)
        mean_depth_sum[k] += as_float(r.get("depth_mean", depth), float(depth))
        mean_depth_n[k] += 1

    branches = read_csv(cost_dir / "candidate_branch_table.csv")
    if not branches:
        raise SystemExit("candidate branch rows are empty")

    rows: list[dict[str, Any]] = []
    for b in branches:
        ck = CaseKey(str(b.get("dataset", "openai/gsm8k")), str(b.get("example_id", "")), as_int(b.get("seed", -1), -1), as_int(b.get("budget", -1), -1))
        if ck not in allowed:
            continue
        method = str(b.get("method", ""))
        branch_id = str(b.get("branch_id", ""))
        raw_ans = b.get("parsed_answer", b.get("answer_group", ""))
        norm_ans = _norm(raw_ans, ck.dataset)
        group_key = (ck, method, norm_ans)
        gold = case_table.get(ck, {}).get("gold_answer", "NA")
        question = qmap.get(ck, "")
        reasoning = reasoning_map.get((ck, method, branch_id), "")
        text_blob = "\n".join([question, reasoning, str(raw_ans or "")]).strip()
        depth = as_int(b.get("depth", 0), 0)

        rows.append(
            {
                "dataset": ck.dataset,
                "example_id": ck.example_id,
                "seed": ck.seed,
                "budget": ck.budget,
                "method": method,
                "branch_id": branch_id,
                "family_id": str(b.get("family_id", "na")),
                "branch_depth": depth,
                "question_text": question,
                "candidate_solution_text": reasoning,
                "candidate_final_answer": str(raw_ans or ""),
                "normalized_answer": norm_ans,
                "answer_group": norm_ans,
                "support_count": as_int(support.get(group_key, 0), 0),
                "family_count": as_int(family_count.get(group_key, 1), 1),
                "max_maturity": as_int(max_depth.get(group_key, depth), depth),
                "mean_maturity": mean_depth_sum.get(group_key, float(depth)) / max(1, mean_depth_n.get(group_key, 1)),
                "candidate_branch_count": 1,
                "equals_external_l1_max": int(norm_ans == case_table.get(ck, {}).get("external_l1_max", "NA") and norm_ans not in {"NA", ""}),
                "equals_strict_f3": int(norm_ans == case_table.get(ck, {}).get("strict_f3", "NA") and norm_ans not in {"NA", ""}),
                "parse_success": int(norm_ans not in {"NA", ""}),
                "numeric_parse_success": int(_is_number_like(norm_ans)),
                "numeric_abs_value": abs(_to_float(norm_ans)) if _is_number_like(norm_ans) else -1.0,
                "branch_text_for_verifier": text_blob,
                "label_is_correct": int(norm_ans == gold and gold not in {"NA", ""}),
            }
        )

    if not rows:
        raise SystemExit("No candidate rows matched the requested case slice")
    return rows, ag_rows


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


def split_groups(rows: list[dict[str, Any]], mode: str = "example_id") -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if mode == "question_text":
            key = str(r.get("question_text", "")).strip() or f"noq::{r['example_id']}"
        else:
            key = str(r.get("example_id", ""))
        out[key].append(r)
    return out


def build_X_y(train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], variant: str):
    y_train = np.array([as_int(r.get("label_is_correct", 0), 0) for r in train_rows], dtype=int)
    y_test = np.array([as_int(r.get("label_is_correct", 0), 0) for r in test_rows], dtype=int)

    use_struct = variant in {"structural", "hybrid"}
    use_text = variant in {"text_tfidf", "hybrid", "text_char_tfidf"}

    mats_train = []
    mats_test = []

    if use_struct:
        dv = DictVectorizer(sparse=True)
        tr_dict = [{f: float(r.get(f, 0.0)) for f in STRUCTURAL_FEATURES} for r in train_rows]
        te_dict = [{f: float(r.get(f, 0.0)) for f in STRUCTURAL_FEATURES} for r in test_rows]
        mats_train.append(dv.fit_transform(tr_dict))
        mats_test.append(dv.transform(te_dict))

    if use_text:
        analyzer = "char_wb" if variant == "text_char_tfidf" else "word"
        ngram_range = (3, 5) if variant == "text_char_tfidf" else (1, 2)
        tv = TfidfVectorizer(min_df=1, analyzer=analyzer, ngram_range=ngram_range)
        tr_text = [str(r.get("branch_text_for_verifier", "")) for r in train_rows]
        te_text = [str(r.get("branch_text_for_verifier", "")) for r in test_rows]
        mats_train.append(tv.fit_transform(tr_text))
        mats_test.append(tv.transform(te_text))

    if not mats_train:
        raise ValueError(f"Unsupported variant: {variant}")
    X_train = mats_train[0] if len(mats_train) == 1 else hstack(mats_train)
    X_test = mats_test[0] if len(mats_test) == 1 else hstack(mats_test)
    return csr_matrix(X_train), y_train, csr_matrix(X_test), y_test


def loeo_scores(rows: list[dict[str, Any]], variant: str, split_mode: str = "example_id") -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    groups = split_groups(rows, mode=split_mode)
    scored: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []

    for holdout_key, hold_rows in sorted(groups.items(), key=lambda x: x[0]):
        train_rows = [r for g, rr in groups.items() if g != holdout_key for r in rr]
        test_rows = list(hold_rows)
        if not train_rows or not test_rows:
            continue

        Xtr, ytr, Xte, yte = build_X_y(train_rows, test_rows, variant)
        if len(set(ytr.tolist())) < 2:
            probs = np.full(shape=(len(test_rows),), fill_value=float(np.mean(ytr)))
        else:
            clf = LogisticRegression(max_iter=1200, class_weight="balanced", random_state=7)
            clf.fit(Xtr, ytr)
            probs = clf.predict_proba(Xte)[:, 1]

        yp = (probs >= 0.5).astype(int)
        fold_auc = ""
        if len(set(yte.tolist())) > 1:
            try:
                fold_auc = float(roc_auc_score(yte, probs))
            except Exception:
                fold_auc = ""

        fold_rows.append(
            {
                "verifier_type": variant,
                "split_mode": split_mode,
                "holdout_group": holdout_key,
                "n_train": len(train_rows),
                "n_test": len(test_rows),
                "fold_accuracy": float(accuracy_score(yte, yp)),
                "fold_auc": fold_auc,
            }
        )
        for r, p in zip(test_rows, probs):
            scored.append({**r, "verifier_type": variant, "split_mode": split_mode, "verifier_score": float(p)})

    y_true = np.array([as_int(r.get("label_is_correct", 0), 0) for r in scored], dtype=int) if scored else np.array([], dtype=int)
    y_prob = np.array([as_float(r.get("verifier_score", 0.0), 0.0) for r in scored], dtype=float) if scored else np.array([], dtype=float)
    metrics: dict[str, float] = {}
    if len(y_true) > 0:
        metrics["candidate_level_accuracy"] = float(accuracy_score(y_true, (y_prob >= 0.5).astype(int)))
        if len(set(y_true.tolist())) > 1:
            metrics["candidate_level_auc"] = float(roc_auc_score(y_true, y_prob))
    return scored, fold_rows, metrics


def aggregate_bucket_scores(case_rows: list[dict[str, Any]], scored_rows: list[dict[str, Any]], agg: str, beta: float, gamma: float) -> tuple[str, list[dict[str, Any]]]:
    score_map = {(r["example_id"], r["seed"], r["budget"], r["method"], r["branch_id"]): as_float(r.get("verifier_score", 0.0), 0.0) for r in scored_rows}
    by_bucket: dict[str, list[float]] = defaultdict(list)
    bucket_struct: dict[str, tuple[float, float]] = {}

    for r in case_rows:
        bk = str(r.get("normalized_answer", "NA"))
        key = (r["example_id"], r["seed"], r["budget"], r["method"], r["branch_id"])
        by_bucket[bk].append(score_map.get(key, 0.0))
        prev = bucket_struct.get(bk, (0.0, 0.0))
        bucket_struct[bk] = (
            max(prev[0], as_float(r.get("support_count", 0), 0.0)),
            max(prev[1], as_float(r.get("family_count", 0), 0.0)),
        )

    scored_buckets = []
    for ans, vals in sorted(by_bucket.items(), key=lambda x: x[0]):
        max_s = max(vals) if vals else 0.0
        mean_s = float(np.mean(vals)) if vals else 0.0
        lse_s = float(np.log(np.sum(np.exp(vals)))) if vals else -1e9
        support_count, fam_count = bucket_struct.get(ans, (0.0, 0.0))

        if agg == "max":
            base = max_s
        elif agg == "mean":
            base = mean_s
        elif agg == "logsumexp":
            base = lse_s
        elif agg == "max_support":
            base = max_s + beta * math.log1p(max(0.0, support_count))
        elif agg == "max_support_family":
            base = max_s + beta * math.log1p(max(0.0, support_count)) + gamma * fam_count
        else:
            raise ValueError(agg)

        scored_buckets.append(
            {
                "normalized_answer": ans,
                "bucket_score": base,
                "max_branch_score": max_s,
                "mean_branch_score": mean_s,
                "logsumexp_score": lse_s,
                "support_count": support_count,
                "family_count": fam_count,
                "agg": agg,
                "beta": beta,
                "gamma": gamma,
            }
        )

    best = sorted(scored_buckets, key=lambda x: (x["bucket_score"], x["support_count"], x["normalized_answer"]), reverse=True)[0]["normalized_answer"]
    return best, scored_buckets


def compute_baseline_choices(case_rows: list[dict[str, Any]], case_meta: dict[str, str]) -> dict[str, str]:
    def pick_max(field: str) -> str:
        best = sorted(case_rows, key=lambda r: (as_float(r.get(field, 0), 0.0), as_float(r.get("support_count", 0), 0.0), str(r.get("normalized_answer", ""))), reverse=True)[0]
        return str(best.get("normalized_answer", "NA"))

    l1 = case_meta.get("external_l1_max", "NA")
    strict = case_meta.get("strict_f3", "NA")
    l1_present = any(str(r.get("normalized_answer", "")) == l1 for r in case_rows)
    oracle = next((r for r in case_rows if as_int(r.get("label_is_correct", 0), 0) == 1), None)

    return {
        "external_l1_max": l1,
        "strict_f3": strict,
        "highest_support": pick_max("support_count"),
        "highest_maturity": pick_max("max_maturity"),
        "highest_family_count": pick_max("family_count"),
        "support_plus_maturity": sorted(case_rows, key=lambda r: (as_float(r.get("support_count", 0), 0.0) + as_float(r.get("max_maturity", 0), 0.0), str(r.get("normalized_answer", ""))), reverse=True)[0]["normalized_answer"],
        "l1_preserve_if_present": l1 if l1_present else strict,
        "oracle_if_gold_present": str(oracle["normalized_answer"]) if oracle is not None else strict,
    }


def run_selectors(candidate_rows: list[dict[str, Any]], case_table: dict[CaseKey, dict[str, str]], scored_by_variant: dict[str, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[CaseKey, list[dict[str, Any]]] = defaultdict(list)
    for r in candidate_rows:
        grouped[CaseKey(str(r["dataset"]), str(r["example_id"]), as_int(r["seed"], -1), as_int(r["budget"], -1))].append(r)

    decisions: list[dict[str, Any]] = []
    bucket_score_rows: list[dict[str, Any]] = []

    agg_configs = [("max", 0.0, 0.0), ("mean", 0.0, 0.0), ("logsumexp", 0.0, 0.0)] + [("max_support", b, 0.0) for b in BETA_GRID] + [
        ("max_support_family", b, g) for b in BETA_GRID for g in GAMMA_GRID
    ]

    for ck, case_rows in grouped.items():
        meta = case_table[ck]
        gold = meta.get("gold_answer", "NA")
        row = {
            "dataset": ck.dataset,
            "example_id": ck.example_id,
            "seed": ck.seed,
            "budget": ck.budget,
            "gold_answer": gold,
            "l1_better_case": int(meta.get("external_l1_max") == gold and meta.get("strict_f3") != gold and gold not in {"NA", ""}),
            "frontier_better_case": int(meta.get("strict_f3") == gold and meta.get("external_l1_max") != gold and gold not in {"NA", ""}),
            "both_wrong_case": int(meta.get("strict_f3") != gold and meta.get("external_l1_max") != gold and gold not in {"NA", ""}),
            "gold_present_in_candidate_pool": int(any(as_int(r.get("label_is_correct", 0), 0) == 1 for r in case_rows)),
        }

        for sel, pred in compute_baseline_choices(case_rows, meta).items():
            row[f"selected__{sel}"] = pred
            row[f"correct__{sel}"] = int(pred == gold and gold not in {"NA", ""})

        for variant, scored in scored_by_variant.items():
            case_scored = [r for r in scored if r["dataset"] == ck.dataset and r["example_id"] == ck.example_id and as_int(r["seed"], -1) == ck.seed and as_int(r["budget"], -1) == ck.budget and r.get("split_mode") == "example_id"]
            for agg, beta, gamma in agg_configs:
                pred, bucket_rows = aggregate_bucket_scores(case_rows, case_scored, agg=agg, beta=beta, gamma=gamma)
                name = f"{variant}__{agg}__b{beta}__g{gamma}"
                row[f"selected__{name}"] = pred
                row[f"correct__{name}"] = int(pred == gold and gold not in {"NA", ""})
                for b in bucket_rows:
                    bucket_score_rows.append(
                        {
                            "dataset": ck.dataset,
                            "example_id": ck.example_id,
                            "seed": ck.seed,
                            "budget": ck.budget,
                            "verifier_type": variant,
                            **b,
                            "is_selected": int(b["normalized_answer"] == pred),
                            "is_gold": int(b["normalized_answer"] == gold and gold not in {"NA", ""}),
                        }
                    )

        decisions.append(row)
    return decisions, bucket_score_rows


def summarize_selectors(decisions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    n = len(decisions)
    selector_names = sorted({k[len("correct__") :] for r in decisions for k in r.keys() if k.startswith("correct__")})
    rows = []
    for s in selector_names:
        rows.append({"selector": s, "n_cases": n, "accuracy": sum(as_int(r.get(f"correct__{s}", 0), 0) for r in decisions) / max(1, n)})
    rows = sorted(rows, key=lambda r: (r["accuracy"], r["selector"]), reverse=True)
    best = rows[0]["selector"] if rows else ""
    return rows, best


def best_selector_for_prefix(selector_summary: list[dict[str, Any]], prefix: str) -> tuple[str, float]:
    cand = [r for r in selector_summary if str(r.get("selector", "")).startswith(prefix)]
    if not cand:
        return "", float("nan")
    best = sorted(cand, key=lambda r: (as_float(r.get("accuracy", 0.0), 0.0), str(r.get("selector", ""))), reverse=True)[0]
    return str(best["selector"]), as_float(best["accuracy"], float("nan"))


def subset_report(decisions: list[dict[str, Any]], subset_key: str, selectors: list[str]) -> list[dict[str, Any]]:
    sub = [r for r in decisions if as_int(r.get(subset_key, 0), 0) == 1]
    out = []
    for s in selectors:
        denom = len(sub)
        acc = (sum(as_int(r.get(f"correct__{s}", 0), 0) for r in sub) / denom) if denom else float("nan")
        out.append({"subset": subset_key, "selector": s, "n_cases": denom, "accuracy": acc})
    return out


def find_current_selector_baseline(decisions: list[dict[str, Any]]) -> dict[tuple[str, int, int, str], str]:
    # optional baseline from prior lightweight diagnostic output
    out: dict[tuple[str, int, int, str], str] = {}
    cand_dirs = sorted((REPO_ROOT / "outputs").glob("outcome_verifier_selector_diagnostic_*STRICT30"), key=lambda p: p.name, reverse=True)
    for d in cand_dirs:
        p = d / "per_case_selector_decisions.csv"
        if not p.exists():
            continue
        for r in read_csv(p):
            key = (str(r.get("dataset", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1), str(r.get("example_id", "")))
            out[key] = str(r.get("selected__diagnostic_outcome_verifier_selector", "NA"))
        if out:
            return out
    return out


def apply_current_selector_baseline(decisions: list[dict[str, Any]]) -> None:
    baseline = find_current_selector_baseline(decisions)
    for r in decisions:
        key = (str(r.get("dataset", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1), str(r.get("example_id", "")))
        pred = baseline.get(key)
        if pred is None:
            continue
        gold = str(r.get("gold_answer", "NA"))
        r["selected__current_diagnostic_outcome_verifier_selector"] = pred
        r["correct__current_diagnostic_outcome_verifier_selector"] = int(pred == gold and gold not in {"NA", ""})


def no_gold_leak_feature_audit() -> list[dict[str, Any]]:
    feature_rows = []
    for f in STRUCTURAL_FEATURES + ["branch_text_for_verifier"]:
        feature_rows.append({"feature": f, "used_as_input": 1, "contains_gold_term": int("gold" in f.lower())})
    feature_rows.append({"feature": "label_is_correct", "used_as_input": 0, "contains_gold_term": 0})
    return feature_rows


def main() -> None:
    args = parse_args()
    trace_dir = (REPO_ROOT / args.trace_dir).resolve()
    cost_dir = (REPO_ROOT / args.cost_dir).resolve()
    casebook_dir = (REPO_ROOT / args.casebook_dir).resolve()

    if args.strict_source:
        ensure_strict_sources(trace_dir, cost_dir, args.required_matched_examples)

    case_table, case_keys = _load_case_table(trace_dir)
    if len(case_keys) != args.required_matched_examples:
        raise SystemExit(f"Expected {args.required_matched_examples} matched examples, got {len(case_keys)}")

    candidate_rows, answer_group_rows = build_candidate_rows(cost_dir, case_table, case_keys)

    # additional fail-fast guarantees
    if len(candidate_rows) == 0:
        raise SystemExit("candidate branch rows are empty")
    if len(answer_group_rows) == 0:
        raise SystemExit("answer-group rows are empty")

    variants = ["structural", "text_tfidf", "hybrid", "text_char_tfidf"]
    scored_by_variant: dict[str, list[dict[str, Any]]] = {}
    training_report: list[dict[str, Any]] = []
    candidate_metrics: dict[str, dict[str, float]] = {}

    for v in variants:
        scored_ex, fold_ex, m_ex = loeo_scores(candidate_rows, variant=v, split_mode="example_id")
        scored_q, fold_q, m_q = loeo_scores(candidate_rows, variant=v, split_mode="question_text")
        scored_by_variant[v] = scored_ex
        training_report.extend(fold_ex)
        training_report.extend(fold_q)
        candidate_metrics[v] = {
            "candidate_level_accuracy": m_ex.get("candidate_level_accuracy", float("nan")),
            "candidate_level_auc": m_ex.get("candidate_level_auc", float("nan")),
            "question_holdout_candidate_level_accuracy": m_q.get("candidate_level_accuracy", float("nan")),
            "question_holdout_candidate_level_auc": m_q.get("candidate_level_auc", float("nan")),
        }

    decisions, bucket_score_rows = run_selectors(candidate_rows, case_table, scored_by_variant)
    apply_current_selector_baseline(decisions)

    selector_summary, _best_selector_any = summarize_selectors(decisions)
    structural_sel, structural_acc = best_selector_for_prefix(selector_summary, "structural__")
    text_sel, text_acc = best_selector_for_prefix(selector_summary, "text_tfidf__")
    hybrid_sel, hybrid_acc = best_selector_for_prefix(selector_summary, "hybrid__")
    text_char_sel, text_char_acc = best_selector_for_prefix(selector_summary, "text_char_tfidf__")
    cobbe_candidates = [r for r in selector_summary if str(r.get("selector", "")).startswith(("structural__", "text_tfidf__", "hybrid__", "text_char_tfidf__"))]
    best_cobbe_row = sorted(cobbe_candidates, key=lambda r: (as_float(r.get("accuracy", 0.0), 0.0), str(r.get("selector", ""))), reverse=True)[0]
    best_cobbe_selector = str(best_cobbe_row["selector"])
    best_cobbe_accuracy = as_float(best_cobbe_row["accuracy"], 0.0)

    # subset reports
    subset_selectors = ["external_l1_max", "strict_f3", "highest_support", "highest_maturity", "l1_preserve_if_present"]
    subset_selectors += [s["selector"] for s in selector_summary[:5] if s["selector"] not in subset_selectors]

    l1_report = subset_report(decisions, "l1_better_case", subset_selectors)
    frontier_report = subset_report(decisions, "frontier_better_case", subset_selectors)
    both_wrong_report = subset_report(decisions, "both_wrong_case", subset_selectors)

    # oracle / safety gaps
    best_correct_key = f"correct__{best_cobbe_selector}"
    strict_key = "correct__strict_f3"
    l1_key = "correct__external_l1_max"
    fixed_vs_strict = sum(as_int(r.get(best_correct_key, 0), 0) == 1 and as_int(r.get(strict_key, 0), 0) == 0 for r in decisions)
    harmed_vs_strict = sum(as_int(r.get(best_correct_key, 0), 0) == 0 and as_int(r.get(strict_key, 0), 0) == 1 for r in decisions)
    fixed_vs_l1 = sum(as_int(r.get(best_correct_key, 0), 0) == 1 and as_int(r.get(l1_key, 0), 0) == 0 for r in decisions)
    harmed_vs_l1 = sum(as_int(r.get(best_correct_key, 0), 0) == 0 and as_int(r.get(l1_key, 0), 0) == 1 for r in decisions)
    gold_present_not_selected = sum(as_int(r.get("gold_present_in_candidate_pool", 0), 0) == 1 and as_int(r.get(best_correct_key, 0), 0) == 0 for r in decisions)

    n_cases = len(decisions)
    l1_acc = sum(as_int(r.get(l1_key, 0), 0) for r in decisions) / max(1, n_cases)
    best_acc = sum(as_int(r.get(best_correct_key, 0), 0) for r in decisions) / max(1, n_cases)

    improvement_cases = sum(as_int(r.get(best_correct_key, 0), 0) for r in decisions) - sum(as_int(r.get(l1_key, 0), 0) for r in decisions)
    larger_than_prev_plus_one = improvement_cases > 1
    harms_l1_solved = harmed_vs_l1

    if improvement_cases <= 1:
        readiness = "promising_but_not_manuscript_ready"
    else:
        readiness = "promising_requires_larger_pilot"
    if harms_l1_solved > 1:
        safety = "unsafe"
    else:
        safety = "provisionally_safe"

    oracle_acc = sum(as_int(r.get("correct__oracle_if_gold_present", 0), 0) for r in decisions) / max(1, n_cases)
    headroom = oracle_acc - best_acc

    highest_maturity_acc = sum(as_int(r.get("correct__highest_maturity", 0), 0) for r in decisions) / max(1, n_cases)

    recommended = {
        "best_selector": best_cobbe_selector,
        "matched_examples": n_cases,
        "number_candidate_branches": len(candidate_rows),
        "number_answer_buckets": len({(r['dataset'], r['example_id'], r['seed'], r['budget'], r['normalized_answer']) for r in candidate_rows}),
        "improves_over_external_l1_max": bool(improvement_cases > 0),
        "improvement_cases_over_external_l1_max": int(improvement_cases),
        "larger_than_previous_plus_one_case": bool(larger_than_prev_plus_one),
        "harms_more_than_one_l1_solved_case": bool(harms_l1_solved > 1),
        "classification": readiness,
        "safety": safety,
        "oracle_headroom_accuracy_gap": headroom,
        "text_aware_beats_structural": max(text_acc, hybrid_acc, text_char_acc) > structural_acc,
        "text_aware_beats_highest_maturity": max(text_acc, hybrid_acc, text_char_acc) > highest_maturity_acc,
        "larger_real_model_pilot_justified": bool(improvement_cases > 0 and harms_l1_solved <= 1),
    }

    oracle_rows = [
        {"metric": "gold_present_but_not_selected_count", "value": gold_present_not_selected},
        {"metric": "cases_fixed_vs_strict_f3", "value": fixed_vs_strict},
        {"metric": "cases_harmed_vs_strict_f3", "value": harmed_vs_strict},
        {"metric": "cases_fixed_vs_external_l1_max", "value": fixed_vs_l1},
        {"metric": "cases_harmed_vs_external_l1_max", "value": harmed_vs_l1},
        {"metric": "improves_over_external_l1_max", "value": int(improvement_cases > 0)},
        {"metric": "improvement_cases_over_external_l1_max", "value": improvement_cases},
        {"metric": "larger_than_previous_plus_one_case", "value": int(larger_than_prev_plus_one)},
        {"metric": "classification", "value": readiness},
        {"metric": "safety", "value": safety},
    ]

    out_dir = REPO_ROOT / "outputs" / f"cobbe_style_outcome_verifier_diagnostic_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    branch_score_rows = []
    for v, rows in scored_by_variant.items():
        for r in rows:
            branch_score_rows.append(
                {
                    "dataset": r["dataset"],
                    "example_id": r["example_id"],
                    "seed": r["seed"],
                    "budget": r["budget"],
                    "method": r["method"],
                    "branch_id": r["branch_id"],
                    "normalized_answer": r["normalized_answer"],
                    "verifier_type": v,
                    "split_mode": r.get("split_mode", "example_id"),
                    "verifier_score": r.get("verifier_score", 0.0),
                    "label_is_correct": r.get("label_is_correct", 0),
                }
            )

    write_csv(out_dir / "candidate_solution_rows.csv", candidate_rows)
    write_csv(out_dir / "verifier_feature_audit.csv", no_gold_leak_feature_audit())
    write_csv(out_dir / "branch_level_verifier_scores.csv", branch_score_rows)
    write_csv(out_dir / "answer_bucket_scores.csv", bucket_score_rows)
    write_csv(out_dir / "selector_summary.csv", selector_summary)
    write_csv(out_dir / "per_case_selector_decisions.csv", decisions)
    write_csv(out_dir / "l1_better_subset_report.csv", l1_report)
    write_csv(out_dir / "frontier_better_subset_report.csv", frontier_report)
    write_csv(out_dir / "both_wrong_subset_report.csv", both_wrong_report)
    write_csv(out_dir / "verifier_training_report.csv", training_report)
    write_csv(out_dir / "oracle_gap_report.csv", oracle_rows)
    write_json(out_dir / "recommended_next_steps.json", recommended)

    summary = [
        "# Cobbe-style outcome verifier diagnostic",
        "",
        "## Inputs",
        f"- trace_dir: `{trace_dir}`",
        f"- cost_dir: `{cost_dir}`",
        f"- casebook_dir: `{casebook_dir}`",
        "",
        "## Required metrics",
        f"- matched_examples: {n_cases}",
        f"- number_of_candidate_branches: {len(candidate_rows)}",
        f"- number_of_answer_buckets: {recommended['number_answer_buckets']}",
        f"- external_l1_max accuracy: {l1_acc}",
        f"- strict_f3 accuracy: {sum(as_int(r.get(strict_key, 0), 0) for r in decisions) / max(1, n_cases)}",
        f"- highest_support accuracy: {sum(as_int(r.get('correct__highest_support', 0), 0) for r in decisions) / max(1, n_cases)}",
        f"- highest_maturity accuracy: {sum(as_int(r.get('correct__highest_maturity', 0), 0) for r in decisions) / max(1, n_cases)}",
        f"- l1_preserve_if_present accuracy: {sum(as_int(r.get('correct__l1_preserve_if_present', 0), 0) for r in decisions) / max(1, n_cases)}",
        f"- oracle_if_gold_present accuracy: {oracle_acc}",
        f"- structural logistic verifier selector: {structural_sel}",
        f"- structural logistic verifier selector accuracy: {structural_acc}",
        f"- TF-IDF text verifier selector: {text_sel}",
        f"- TF-IDF text verifier selector accuracy: {text_acc}",
        f"- hybrid verifier selector: {hybrid_sel}",
        f"- hybrid verifier selector accuracy: {hybrid_acc}",
        f"- best Cobbe-style selector: {best_cobbe_selector}",
        f"- best Cobbe-style selector accuracy: {best_cobbe_accuracy}",
        f"- candidate-level structural acc/auc: {candidate_metrics['structural'].get('candidate_level_accuracy')} / {candidate_metrics['structural'].get('candidate_level_auc')}",
        f"- candidate-level text_tfidf acc/auc: {candidate_metrics['text_tfidf'].get('candidate_level_accuracy')} / {candidate_metrics['text_tfidf'].get('candidate_level_auc')}",
        f"- candidate-level hybrid acc/auc: {candidate_metrics['hybrid'].get('candidate_level_accuracy')} / {candidate_metrics['hybrid'].get('candidate_level_auc')}",
        f"- cases_fixed_vs_strict_f3: {fixed_vs_strict}",
        f"- cases_harmed_vs_strict_f3: {harmed_vs_strict}",
        f"- cases_fixed_vs_external_l1_max: {fixed_vs_l1}",
        f"- cases_harmed_vs_external_l1_max: {harmed_vs_l1}",
        f"- gold_present_but_not_selected_count: {gold_present_not_selected}",
        f"- improves_over_external_l1_max: {improvement_cases > 0}",
        f"- larger_than_previous_plus_one_case: {larger_than_prev_plus_one}",
        f"- larger_real_model_pilot_justified: {recommended['larger_real_model_pilot_justified']}",
        "",
        "## Interpretation",
        f"- readiness_classification: {readiness}",
        f"- safety_classification: {safety}",
        f"- oracle_headroom_accuracy_gap: {headroom}",
        f"- text_aware_beats_structural: {recommended['text_aware_beats_structural']}",
        f"- text_aware_beats_highest_maturity: {recommended['text_aware_beats_highest_maturity']}",
        "- Diagnostic-only: no API calls, no manuscript updates, no canonical artifact changes.",
    ]
    (out_dir / "README.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    doc = REPO_ROOT / "docs" / "COBBE_STYLE_OUTCOME_VERIFIER_DIAGNOSTIC.md"
    doc.write_text(
        "\n".join(
            [
                "# Cobbe-Style Outcome Verifier Diagnostic",
                "",
                "Diagnostic-only local adaptation inspired by Cobbe et al. verifier selection.",
                "",
                "## Run",
                "```bash",
                "python scripts/run_cobbe_style_outcome_verifier_diagnostic.py --strict-source --required-matched-examples 30",
                "```",
                "",
                "## Outputs",
                f"- `outputs/{out_dir.name}/candidate_solution_rows.csv`",
                f"- `outputs/{out_dir.name}/verifier_feature_audit.csv`",
                f"- `outputs/{out_dir.name}/branch_level_verifier_scores.csv`",
                f"- `outputs/{out_dir.name}/answer_bucket_scores.csv`",
                f"- `outputs/{out_dir.name}/selector_summary.csv`",
                f"- `outputs/{out_dir.name}/per_case_selector_decisions.csv`",
                f"- `outputs/{out_dir.name}/l1_better_subset_report.csv`",
                f"- `outputs/{out_dir.name}/frontier_better_subset_report.csv`",
                f"- `outputs/{out_dir.name}/both_wrong_subset_report.csv`",
                f"- `outputs/{out_dir.name}/verifier_training_report.csv`",
                f"- `outputs/{out_dir.name}/oracle_gap_report.csv`",
                f"- `outputs/{out_dir.name}/recommended_next_steps.json`",
                f"- `outputs/{out_dir.name}/README.md`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote Cobbe-style diagnostic bundle: {out_dir}")


if __name__ == "__main__":
    main()
