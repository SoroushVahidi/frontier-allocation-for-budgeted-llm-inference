#!/usr/bin/env python3
"""Diagnostic-only Cobbe-style outcome verifier over traced candidates.

No real API calls. Uses local artifacts only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.output_layer_repair import canonicalize_answer
from scripts.learned_branch_scorer_utils import as_float, as_int, read_csv, write_csv, write_json

TRACE_DIR_DEFAULT = "outputs/direct_reserve_frontier_gate_failure_slice_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN_DIAGNOSTIC_ACTUAL"
COST_DIR_DEFAULT = "outputs/cohere_real_model_cost_normalized_validation_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN"
CASEBOOK_DIR_DEFAULT = "outputs/l1_better_than_frontier_casebook_20260426T232030Z"

STRUCTURAL_FEATURES = [
    "support_count",
    "family_count",
    "group_max_depth",
    "group_mean_depth",
    "candidate_branch_count",
    "branch_depth",
    "equals_external_l1_max",
    "equals_strict_f3",
    "parse_success",
    "output_repair_flag",
    "numeric_parse_success",
    "numeric_abs_value",
]

TEXT_FIELDS = [
    "question_text",
    "candidate_solution_text",
    "reasoning_text",
    "raw_branch_text",
    "candidate_final_answer_raw",
]

BETA_GRID = (0.0, 0.1, 0.25)
GAMMA_GRID = (0.0, 0.1, 0.25)


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


def _is_num(v: str) -> bool:
    try:
        float(str(v).replace(",", ""))
        return True
    except Exception:
        return False


def _to_float(v: str) -> float:
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return 0.0


def _first_existing_file(base_dirs: list[Path], names: list[str]) -> Path | None:
    for d in base_dirs:
        for n in names:
            p = d / n
            if p.exists():
                return p
    return None


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
    req_trace = ["manifest.json"]
    req_cost = ["per_example_records.jsonl"]
    for f in req_trace:
        if not (trace_dir / f).exists():
            raise SystemExit(f"Missing required trace file: {trace_dir / f}")
    for f in req_cost:
        if not (cost_dir / f).exists():
            raise SystemExit(f"Missing required cost file: {cost_dir / f}")

    case_path = _first_existing_file([trace_dir], ["per_case_results.csv", "per_case_method_results.csv"])
    if case_path is None:
        raise SystemExit("Strict source failed: expected per_case_results.csv or per_case_method_results.csv in trace_dir")

    ag_path = _first_existing_file([trace_dir, cost_dir], ["answer_group_table.csv", "answer_group_summary.csv"])
    if ag_path is None:
        raise SystemExit("Strict source failed: missing answer_group_table.csv/answer_group_summary.csv")

    branch_path = _first_existing_file([trace_dir, cost_dir], ["candidate_branch_table.csv"])
    if branch_path is None:
        raise SystemExit("Strict source failed: missing candidate_branch_table.csv")

    manifest = json.loads((trace_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_n = as_int(manifest.get("matched_examples", -1), -1)
    if manifest_n != required_matched_examples:
        raise SystemExit(f"Strict manifest check failed: expected {required_matched_examples}, got {manifest_n}")


def _load_case_table(trace_dir: Path, cost_dir: Path) -> dict[CaseKey, dict[str, str]]:
    out: dict[CaseKey, dict[str, str]] = defaultdict(dict)

    per_case_results = trace_dir / "per_case_results.csv"
    per_case_method = trace_dir / "per_case_method_results.csv"

    if per_case_results.exists():
        for r in read_csv(per_case_results):
            ck = CaseKey(str(r.get("dataset", "openai/gsm8k")), str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1))
            out[ck]["external_l1_max"] = _norm(r.get("external_l1_max_prediction", ""), ck.dataset)
            out[ck]["strict_f3"] = _norm(r.get("strict_f3_prediction", ""), ck.dataset)
            out[ck]["gold_answer"] = _norm(r.get("gold_answer", ""), ck.dataset)

    if per_case_method.exists():
        for r in read_csv(per_case_method):
            ck = CaseKey(str(r.get("dataset", "openai/gsm8k")), str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1))
            method = str(r.get("method", ""))
            pred = _norm(r.get("normalized_selected_answer", r.get("final_selected_answer", "")), ck.dataset)
            if method:
                out[ck][method] = pred
            out[ck]["gold_answer"] = _norm(r.get("gold_answer", ""), ck.dataset)

    if not out:
        # last-resort local fallback for method predictions; still local/offline
        rec_path = cost_dir / "per_example_records.jsonl"
        if rec_path.exists():
            with rec_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    d = json.loads(line)
                    ck = CaseKey(str(d.get("dataset", "openai/gsm8k")), str(d.get("example_id", "")), as_int(d.get("seed", -1), -1), as_int(d.get("budget", -1), -1))
                    out[ck][str(d.get("method", ""))] = _norm(d.get("selected_answer_raw", d.get("final_answer_raw", "")), ck.dataset)
                    out[ck]["gold_answer"] = _norm(d.get("gold_answer", ""), ck.dataset)

    return dict(out)


def _load_question_and_reasoning(cost_dir: Path) -> tuple[dict[CaseKey, str], dict[CaseKey, str], dict[tuple[CaseKey, str, str], dict[str, str]]]:
    question_map: dict[CaseKey, str] = {}
    question_hash_map: dict[CaseKey, str] = {}
    branch_text_map: dict[tuple[CaseKey, str, str], dict[str, str]] = {}

    rec_path = cost_dir / "per_example_records.jsonl"
    if not rec_path.exists():
        return question_map, question_hash_map, branch_text_map

    with rec_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            ck = CaseKey(str(d.get("dataset", "openai/gsm8k")), str(d.get("example_id", "")), as_int(d.get("seed", -1), -1), as_int(d.get("budget", -1), -1))
            q = str(d.get("question", ""))
            question_map.setdefault(ck, q)
            question_hash_map.setdefault(ck, hashlib.sha1(q.encode("utf-8")).hexdigest()[:16] if q else "")
            method = str(d.get("method", ""))
            for n in d.get("final_nodes", []) or []:
                bid = str(n.get("branch_id", ""))
                if not bid:
                    continue
                branch_text_map[(ck, method, bid)] = {
                    "reasoning_text": str(n.get("reasoning_text", "")),
                    "candidate_solution_text": str(n.get("reasoning_text", "")),
                    "raw_branch_text": str(n.get("raw_branch_text", "")),
                    "candidate_final_answer_raw": str(n.get("predicted_answer", "")),
                }

    return question_map, question_hash_map, branch_text_map


def build_candidate_solution_rows(trace_dir: Path, cost_dir: Path, case_table: dict[CaseKey, dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_keys = set(case_table.keys())
    if not case_keys:
        raise SystemExit("No case records loaded")

    ag_path = _first_existing_file([trace_dir, cost_dir], ["answer_group_table.csv", "answer_group_summary.csv"])
    if ag_path is None:
        raise SystemExit("Missing answer-group table/summary")
    ag_rows = read_csv(ag_path)
    if not ag_rows:
        raise SystemExit("answer-group rows are empty")

    branch_path = _first_existing_file([trace_dir, cost_dir], ["candidate_branch_table.csv"])
    if branch_path is None:
        raise SystemExit("Missing candidate_branch_table.csv")
    branch_rows = read_csv(branch_path)
    if not branch_rows:
        raise SystemExit("candidate branch rows are empty")

    question_map, question_hash_map, branch_text_map = _load_question_and_reasoning(cost_dir)

    support_map: dict[tuple[CaseKey, str, str], int] = {}
    family_map: dict[tuple[CaseKey, str, str], int] = {}
    depth_max_map: dict[tuple[CaseKey, str, str], int] = {}
    depth_mean_sum: dict[tuple[CaseKey, str, str], float] = defaultdict(float)
    depth_mean_n: dict[tuple[CaseKey, str, str], int] = defaultdict(int)

    for r in ag_rows:
        ck = CaseKey(str(r.get("dataset", "openai/gsm8k")), str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1))
        if ck not in case_keys:
            continue
        method = str(r.get("method", ""))
        ans = _norm(r.get("answer_group", ""), ck.dataset)
        k = (ck, method, ans)
        support_map[k] = max(support_map.get(k, 0), as_int(r.get("support_count", r.get("support", 0)), 0))
        family_map[k] = max(family_map.get(k, 0), as_int(r.get("family_count", 1), 1))
        depth_max = as_int(r.get("depth_max", r.get("maturity", 0)), 0)
        depth_mean = as_float(r.get("depth_mean", depth_max), float(depth_max))
        depth_max_map[k] = max(depth_max_map.get(k, 0), depth_max)
        depth_mean_sum[k] += depth_mean
        depth_mean_n[k] += 1

    rows: list[dict[str, Any]] = []
    for b in branch_rows:
        ck = CaseKey(str(b.get("dataset", "openai/gsm8k")), str(b.get("example_id", "")), as_int(b.get("seed", -1), -1), as_int(b.get("budget", -1), -1))
        if ck not in case_keys:
            continue
        method = str(b.get("method", ""))
        branch_id = str(b.get("branch_id", ""))
        norm_ans = _norm(b.get("parsed_answer", b.get("predicted_answer", b.get("answer_group", ""))), ck.dataset)
        group_key = (ck, method, norm_ans)

        pred_raw = str(b.get("parsed_answer", b.get("predicted_answer", b.get("answer_group", ""))))
        branch_text = branch_text_map.get((ck, method, branch_id), {})
        reasoning_text = str(branch_text.get("reasoning_text", ""))
        raw_branch_text = str(branch_text.get("raw_branch_text", ""))
        candidate_solution_text = str(branch_text.get("candidate_solution_text", ""))
        if not candidate_solution_text:
            candidate_solution_text = str(b.get("metadata", ""))

        rows.append(
            {
                "dataset": ck.dataset,
                "example_id": ck.example_id,
                "seed": ck.seed,
                "budget": ck.budget,
                "question_text": question_map.get(ck, ""),
                "question_hash": question_hash_map.get(ck, ""),
                "method": method,
                "source_method": method,
                "branch_id": branch_id,
                "parent_id": str(b.get("parent_id", "")),
                "family_id": str(b.get("family_id", b.get("branch_prompt_style", "na"))),
                "branch_depth": as_int(b.get("depth", b.get("branch_depth", 0)), 0),
                "maturity": as_int(b.get("depth", b.get("branch_depth", 0)), 0),
                "candidate_final_answer_raw": pred_raw,
                "candidate_final_answer_normalized": norm_ans,
                "normalized_answer": norm_ans,
                "answer_group": norm_ans,
                "candidate_solution_text": candidate_solution_text,
                "reasoning_text": reasoning_text,
                "raw_branch_text": raw_branch_text,
                "support_count": as_int(support_map.get(group_key, 0), 0),
                "family_count": as_int(family_map.get(group_key, 1), 1),
                "group_max_depth": as_int(depth_max_map.get(group_key, 0), 0),
                "group_mean_depth": depth_mean_sum.get(group_key, 0.0) / max(1, depth_mean_n.get(group_key, 1)),
                "candidate_branch_count": 1,
                "equals_external_l1_max": int(norm_ans == case_table.get(ck, {}).get("external_l1_max", "NA") and norm_ans not in {"NA", ""}),
                "equals_strict_f3": int(norm_ans == case_table.get(ck, {}).get("strict_f3", "NA") and norm_ans not in {"NA", ""}),
                "parse_success": int(norm_ans not in {"NA", ""}),
                "output_repair_flag": int(_norm(pred_raw, ck.dataset) != pred_raw.strip()) if pred_raw.strip() else 0,
                "numeric_parse_success": int(_is_num(norm_ans)),
                "numeric_abs_value": abs(_to_float(norm_ans)) if _is_num(norm_ans) else -1.0,
                "equals_gold_answer": int(norm_ans == case_table.get(ck, {}).get("gold_answer", "NA") and case_table.get(ck, {}).get("gold_answer", "NA") not in {"NA", ""}),
                "label_is_correct": int(norm_ans == case_table.get(ck, {}).get("gold_answer", "NA") and case_table.get(ck, {}).get("gold_answer", "NA") not in {"NA", ""}),
            }
        )

    if not rows:
        raise SystemExit("No candidate solution rows matched requested cases")

    aux = {
        "ag_path": str(ag_path),
        "branch_path": str(branch_path),
        "n_answer_group_rows": len(ag_rows),
    }
    return rows, aux


def verifier_feature_audit_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for f in STRUCTURAL_FEATURES:
        rows.append({"column": f, "role": "feature", "feature_group": "structural", "gold_derived": 0})
    for f in TEXT_FIELDS:
        rows.append({"column": f, "role": "feature", "feature_group": "text", "gold_derived": 0})
    for c in ["label_is_correct", "equals_gold_answer"]:
        rows.append({"column": c, "role": "label_only", "feature_group": "none", "gold_derived": 1})
    for c in ["dataset", "example_id", "seed", "budget", "method", "branch_id", "parent_id", "family_id", "answer_group", "question_hash"]:
        rows.append({"column": c, "role": "metadata", "feature_group": "none", "gold_derived": 0})
    return rows


def no_gold_leak_feature_audit() -> list[dict[str, Any]]:
    # compatibility helper used by tests
    return [{"feature": r["column"], "used_as_input": int(r["role"] == "feature"), "contains_gold_term": int("gold" in str(r["column"]).lower())} for r in verifier_feature_audit_rows()]


def _text_blob(r: dict[str, Any]) -> str:
    parts = [str(r.get("question_text", "")), str(r.get("candidate_solution_text", "")), str(r.get("reasoning_text", "")), str(r.get("raw_branch_text", "")), str(r.get("candidate_final_answer_raw", ""))]
    return "\n".join(x for x in parts if x).strip()


def split_groups(rows: list[dict[str, Any]], mode: str = "example_id") -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = str(r.get("example_id", "")) if mode == "example_id" else (str(r.get("question_hash", "")) or str(r.get("example_id", "")))
        out[key].append(r)
    return out


def _build_mats(train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], variant: str) -> tuple[csr_matrix, np.ndarray, csr_matrix, np.ndarray]:
    y_train = np.array([as_int(r.get("label_is_correct", 0), 0) for r in train_rows], dtype=int)
    y_test = np.array([as_int(r.get("label_is_correct", 0), 0) for r in test_rows], dtype=int)

    use_struct = variant in {"structural_logistic", "hybrid_tfidf_structural_logistic"}
    use_text = variant in {"tfidf_solution_logistic", "hybrid_tfidf_structural_logistic", "char_tfidf_solution_logistic"}

    mats_train = []
    mats_test = []

    if use_struct:
        dv = DictVectorizer(sparse=True)
        tr = [{f: float(r.get(f, 0.0)) for f in STRUCTURAL_FEATURES} for r in train_rows]
        te = [{f: float(r.get(f, 0.0)) for f in STRUCTURAL_FEATURES} for r in test_rows]
        mats_train.append(dv.fit_transform(tr))
        mats_test.append(dv.transform(te))

    if use_text:
        analyzer = "char_wb" if variant == "char_tfidf_solution_logistic" else "word"
        ngrams = (3, 5) if variant == "char_tfidf_solution_logistic" else (1, 2)
        tv = TfidfVectorizer(min_df=1, analyzer=analyzer, ngram_range=ngrams)
        mats_train.append(tv.fit_transform([_text_blob(r) for r in train_rows]))
        mats_test.append(tv.transform([_text_blob(r) for r in test_rows]))

    X_train = mats_train[0] if len(mats_train) == 1 else hstack(mats_train)
    X_test = mats_test[0] if len(mats_test) == 1 else hstack(mats_test)
    return csr_matrix(X_train), y_train, csr_matrix(X_test), y_test


def score_branches_loeo(rows: list[dict[str, Any]], variant: str, split_mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    groups = split_groups(rows, mode=split_mode)
    scored_rows: list[dict[str, Any]] = []
    folds: list[dict[str, Any]] = []
    for holdout, test_rows in sorted(groups.items(), key=lambda x: x[0]):
        train_rows = [r for g, rr in groups.items() if g != holdout for r in rr]
        if not train_rows or not test_rows:
            continue
        Xtr, ytr, Xte, yte = _build_mats(train_rows, test_rows, variant)
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
        folds.append({"verifier_type": variant, "split_mode": split_mode, "holdout_group": holdout, "n_train": len(train_rows), "n_test": len(test_rows), "fold_accuracy": float(accuracy_score(yte, yp)), "fold_auc": fold_auc})
        for r, p in zip(test_rows, probs):
            scored_rows.append({**r, "verifier_type": variant, "split_mode": split_mode, "verifier_score": float(p)})

    y_true = np.array([as_int(r.get("label_is_correct", 0), 0) for r in scored_rows], dtype=int) if scored_rows else np.array([], dtype=int)
    y_prob = np.array([as_float(r.get("verifier_score", 0.0), 0.0) for r in scored_rows], dtype=float) if scored_rows else np.array([], dtype=float)
    summary: dict[str, float] = {}
    if len(y_true) > 0:
        summary["candidate_level_accuracy"] = float(accuracy_score(y_true, (y_prob >= 0.5).astype(int)))
        if len(set(y_true.tolist())) > 1:
            summary["candidate_level_auc"] = float(roc_auc_score(y_true, y_prob))
    return scored_rows, folds, summary


def aggregate_bucket_scores(case_rows: list[dict[str, Any]], scored_rows: list[dict[str, Any]], agg: str, beta: float, gamma: float) -> tuple[str, list[dict[str, Any]]]:
    score_map = {
        (
            str(r.get("dataset", "")),
            str(r.get("example_id", "")),
            as_int(r.get("seed", -1), -1),
            as_int(r.get("budget", -1), -1),
            str(r.get("method", "")),
            str(r.get("branch_id", "")),
        ): as_float(r.get("verifier_score", 0.0), 0.0)
        for r in scored_rows
    }
    bucket_scores: dict[str, list[float]] = defaultdict(list)
    bucket_support: dict[str, float] = defaultdict(float)
    bucket_family: dict[str, float] = defaultdict(float)

    for r in case_rows:
        ans = str(r.get("normalized_answer", "NA"))
        key = (
            str(r.get("dataset", "")),
            str(r.get("example_id", "")),
            as_int(r.get("seed", -1), -1),
            as_int(r.get("budget", -1), -1),
            str(r.get("method", "")),
            str(r.get("branch_id", "")),
        )
        bucket_scores[ans].append(score_map.get(key, 0.0))
        bucket_support[ans] = max(bucket_support[ans], as_float(r.get("support_count", 0), 0.0))
        bucket_family[ans] = max(bucket_family[ans], as_float(r.get("family_count", 0), 0.0))

    rows = []
    for ans, vals in sorted(bucket_scores.items(), key=lambda x: x[0]):
        max_s = max(vals)
        mean_s = float(np.mean(vals))
        lse_s = float(np.log(np.sum(np.exp(vals))))
        if agg == "max":
            final = max_s
        elif agg == "mean":
            final = mean_s
        elif agg == "logsumexp":
            final = lse_s
        elif agg == "max_plus_support":
            final = max_s + beta * math.log1p(max(0.0, bucket_support[ans]))
        elif agg == "max_plus_support_plus_family":
            final = max_s + beta * math.log1p(max(0.0, bucket_support[ans])) + gamma * bucket_family[ans]
        else:
            raise ValueError(agg)
        rows.append({"normalized_answer": ans, "bucket_score": final, "max_branch_score": max_s, "mean_branch_score": mean_s, "logsumexp_score": lse_s, "support_count": bucket_support[ans], "family_count": bucket_family[ans], "agg": agg, "beta": beta, "gamma": gamma})

    pick = sorted(rows, key=lambda x: (x["bucket_score"], x["support_count"], x["normalized_answer"]), reverse=True)[0]["normalized_answer"]
    return pick, rows


def summarize_selectors(decisions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    n = len(decisions)
    sels = sorted({k[len("correct__") :] for r in decisions for k in r.keys() if k.startswith("correct__")})
    rows = [{"selector": s, "n_cases": n, "accuracy": sum(as_int(r.get(f"correct__{s}", 0), 0) for r in decisions) / max(1, n)} for s in sels]
    rows = sorted(rows, key=lambda r: (r["accuracy"], r["selector"]), reverse=True)
    return rows, (rows[0]["selector"] if rows else "")


def _best_prefix(summary: list[dict[str, Any]], prefix: str) -> tuple[str, float]:
    cand = [r for r in summary if str(r["selector"]).startswith(prefix)]
    if not cand:
        return "", float("nan")
    best = sorted(cand, key=lambda r: (r["accuracy"], r["selector"]), reverse=True)[0]
    return str(best["selector"]), as_float(best["accuracy"], float("nan"))


def _load_current_selector_baseline() -> dict[tuple[str, str, int, int], str]:
    out: dict[tuple[str, str, int, int], str] = {}
    dirs = sorted((REPO_ROOT / "outputs").glob("outcome_verifier_selector_diagnostic_*STRICT30"), key=lambda p: p.name, reverse=True)
    for d in dirs:
        p = d / "per_case_selector_decisions.csv"
        if not p.exists():
            continue
        for r in read_csv(p):
            out[(str(r.get("dataset", "")), str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1))] = str(r.get("selected__diagnostic_outcome_verifier_selector", "NA"))
        if out:
            return out
    return out


def _baseline_choices(case_rows: list[dict[str, Any]], meta: dict[str, str]) -> dict[str, str]:
    def pick_max(field: str) -> str:
        best = sorted(case_rows, key=lambda r: (as_float(r.get(field, 0), 0.0), as_float(r.get("support_count", 0), 0.0), str(r.get("normalized_answer", ""))), reverse=True)[0]
        return str(best.get("normalized_answer", "NA"))

    l1 = meta.get("external_l1_max", "NA")
    strict = meta.get("strict_f3", "NA")
    l1_present = any(str(r.get("normalized_answer", "")) == l1 for r in case_rows)
    oracle = next((r for r in case_rows if as_int(r.get("label_is_correct", 0), 0) == 1), None)

    return {
        "external_l1_max": l1,
        "strict_f3": strict,
        "highest_support": pick_max("support_count"),
        "highest_maturity": pick_max("group_max_depth"),
        "highest_family_count": pick_max("family_count"),
        "support_plus_maturity": sorted(case_rows, key=lambda r: (as_float(r.get("support_count", 0), 0.0) + as_float(r.get("group_max_depth", 0), 0.0), str(r.get("normalized_answer", ""))), reverse=True)[0]["normalized_answer"],
        "l1_preserve_if_present": l1 if l1_present else strict,
        "oracle_if_gold_present": str(oracle["normalized_answer"]) if oracle is not None else strict,
    }


def run_all_selectors(rows: list[dict[str, Any]], case_table: dict[CaseKey, dict[str, str]], scored_by_variant: dict[str, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[CaseKey, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[CaseKey(str(r["dataset"]), str(r["example_id"]), as_int(r["seed"], -1), as_int(r["budget"], -1))].append(r)

    current_baseline = _load_current_selector_baseline()

    decisions: list[dict[str, Any]] = []
    bucket_rows: list[dict[str, Any]] = []
    aggs = [("max", 0.0, 0.0), ("mean", 0.0, 0.0), ("logsumexp", 0.0, 0.0)] + [("max_plus_support", b, 0.0) for b in BETA_GRID] + [("max_plus_support_plus_family", b, g) for b in BETA_GRID for g in GAMMA_GRID]

    for ck, case_rows in grouped.items():
        meta = case_table[ck]
        gold = meta.get("gold_answer", "NA")
        row: dict[str, Any] = {
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

        for s, p in _baseline_choices(case_rows, meta).items():
            row[f"selected__{s}"] = p
            row[f"correct__{s}"] = int(p == gold and gold not in {"NA", ""})

        key = (ck.dataset, ck.example_id, ck.seed, ck.budget)
        if key in current_baseline:
            pred = current_baseline[key]
            row["selected__current_diagnostic_outcome_verifier_selector"] = pred
            row["correct__current_diagnostic_outcome_verifier_selector"] = int(pred == gold and gold not in {"NA", ""})

        for variant, srows in scored_by_variant.items():
            case_scored = [r for r in srows if r["dataset"] == ck.dataset and r["example_id"] == ck.example_id and as_int(r["seed"], -1) == ck.seed and as_int(r["budget"], -1) == ck.budget and str(r.get("split_mode", "")) == "example_id"]
            for agg, beta, gamma in aggs:
                pred, buckets = aggregate_bucket_scores(case_rows, case_scored, agg=agg, beta=beta, gamma=gamma)
                name = f"{variant}__{agg}__b{beta}__g{gamma}"
                row[f"selected__{name}"] = pred
                row[f"correct__{name}"] = int(pred == gold and gold not in {"NA", ""})
                for b in buckets:
                    bucket_rows.append({"dataset": ck.dataset, "example_id": ck.example_id, "seed": ck.seed, "budget": ck.budget, "verifier_type": variant, **b, "is_selected": int(b["normalized_answer"] == pred), "is_gold": int(b["normalized_answer"] == gold and gold not in {"NA", ""})})

        decisions.append(row)

    return decisions, bucket_rows


def _subset_report(decisions: list[dict[str, Any]], subset_key: str, selectors: list[str]) -> list[dict[str, Any]]:
    sub = [r for r in decisions if as_int(r.get(subset_key, 0), 0) == 1]
    out = []
    for s in selectors:
        out.append({"subset": subset_key, "selector": s, "n_cases": len(sub), "accuracy": (sum(as_int(r.get(f"correct__{s}", 0), 0) for r in sub) / len(sub)) if sub else float("nan")})
    return out


def main() -> None:
    args = parse_args()
    trace_dir = (REPO_ROOT / args.trace_dir).resolve()
    cost_dir = (REPO_ROOT / args.cost_dir).resolve()
    casebook_dir = (REPO_ROOT / args.casebook_dir).resolve()

    if args.strict_source:
        ensure_strict_sources(trace_dir, cost_dir, args.required_matched_examples)

    case_table = _load_case_table(trace_dir, cost_dir)
    if len(case_table) != args.required_matched_examples:
        raise SystemExit(f"Expected matched_examples={args.required_matched_examples}, got {len(case_table)}")

    candidate_rows, aux = build_candidate_solution_rows(trace_dir, cost_dir, case_table)

    variants = ["structural_logistic", "tfidf_solution_logistic", "hybrid_tfidf_structural_logistic", "char_tfidf_solution_logistic"]
    scored_by_variant: dict[str, list[dict[str, Any]]] = {}
    training_report: list[dict[str, Any]] = []
    candidate_metrics: dict[str, dict[str, float]] = {}

    for v in variants:
        scored_ex, folds_ex, m_ex = score_branches_loeo(candidate_rows, variant=v, split_mode="example_id")
        scored_q, folds_q, m_q = score_branches_loeo(candidate_rows, variant=v, split_mode="question_hash")
        scored_by_variant[v] = scored_ex
        training_report.extend(folds_ex)
        training_report.extend(folds_q)
        candidate_metrics[v] = {
            "candidate_level_accuracy": m_ex.get("candidate_level_accuracy", float("nan")),
            "candidate_level_auc": m_ex.get("candidate_level_auc", float("nan")),
            "question_holdout_candidate_level_accuracy": m_q.get("candidate_level_accuracy", float("nan")),
            "question_holdout_candidate_level_auc": m_q.get("candidate_level_auc", float("nan")),
        }

    decisions, bucket_score_rows = run_all_selectors(candidate_rows, case_table, scored_by_variant)
    selector_summary, _ = summarize_selectors(decisions)

    structural_sel, structural_acc = _best_prefix(selector_summary, "structural_logistic__")
    tfidf_sel, tfidf_acc = _best_prefix(selector_summary, "tfidf_solution_logistic__")
    hybrid_sel, hybrid_acc = _best_prefix(selector_summary, "hybrid_tfidf_structural_logistic__")

    cobbe_rows = [r for r in selector_summary if str(r["selector"]).startswith(("structural_logistic__", "tfidf_solution_logistic__", "hybrid_tfidf_structural_logistic__", "char_tfidf_solution_logistic__"))]
    best_cobbe = sorted(cobbe_rows, key=lambda r: (r["accuracy"], r["selector"]), reverse=True)[0]
    best_sel = str(best_cobbe["selector"])
    best_key = f"correct__{best_sel}"

    n = len(decisions)
    l1_key = "correct__external_l1_max"
    strict_key = "correct__strict_f3"
    l1_acc = sum(as_int(r.get(l1_key, 0), 0) for r in decisions) / max(1, n)
    strict_acc = sum(as_int(r.get(strict_key, 0), 0) for r in decisions) / max(1, n)
    high_sup_acc = sum(as_int(r.get("correct__highest_support", 0), 0) for r in decisions) / max(1, n)
    high_mat_acc = sum(as_int(r.get("correct__highest_maturity", 0), 0) for r in decisions) / max(1, n)
    l1_preserve_acc = sum(as_int(r.get("correct__l1_preserve_if_present", 0), 0) for r in decisions) / max(1, n)
    oracle_acc = sum(as_int(r.get("correct__oracle_if_gold_present", 0), 0) for r in decisions) / max(1, n)

    best_acc = sum(as_int(r.get(best_key, 0), 0) for r in decisions) / max(1, n)
    fixed_vs_strict = sum(as_int(r.get(best_key, 0), 0) == 1 and as_int(r.get(strict_key, 0), 0) == 0 for r in decisions)
    harmed_vs_strict = sum(as_int(r.get(best_key, 0), 0) == 0 and as_int(r.get(strict_key, 0), 0) == 1 for r in decisions)
    fixed_vs_l1 = sum(as_int(r.get(best_key, 0), 0) == 1 and as_int(r.get(l1_key, 0), 0) == 0 for r in decisions)
    harmed_vs_l1 = sum(as_int(r.get(best_key, 0), 0) == 0 and as_int(r.get(l1_key, 0), 0) == 1 for r in decisions)

    improve_cases = sum(as_int(r.get(best_key, 0), 0) for r in decisions) - sum(as_int(r.get(l1_key, 0), 0) for r in decisions)
    larger_than_prev_plus_one = improve_cases > 1
    gold_present_not_selected = sum(as_int(r.get("gold_present_in_candidate_pool", 0), 0) == 1 and as_int(r.get(best_key, 0), 0) == 0 for r in decisions)

    if improve_cases <= 1:
        readiness = "promising_but_not_manuscript_ready"
    else:
        readiness = "promising_requires_larger_pilot"
    safety = "unsafe" if harmed_vs_l1 > 1 else "provisionally_safe"

    text_aware_best = max(tfidf_acc, hybrid_acc)
    text_not_better = text_aware_best <= max(structural_acc, high_mat_acc)

    out_dir = REPO_ROOT / "outputs" / f"cobbe_style_outcome_verifier_diagnostic_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    branch_level_rows = []
    for v, srows in scored_by_variant.items():
        for r in srows:
            branch_level_rows.append({"dataset": r["dataset"], "example_id": r["example_id"], "seed": r["seed"], "budget": r["budget"], "method": r["method"], "branch_id": r["branch_id"], "normalized_answer": r["normalized_answer"], "verifier_type": v, "split_mode": r.get("split_mode", "example_id"), "verifier_score": r.get("verifier_score", 0.0), "label_is_correct": r.get("label_is_correct", 0)})

    subset_selectors = ["external_l1_max", "strict_f3", "highest_support", "highest_maturity", "l1_preserve_if_present", best_sel]

    oracle_gap_rows = [
        {"metric": "gold_present_but_not_selected_count", "value": gold_present_not_selected},
        {"metric": "cases_fixed_vs_strict_f3", "value": fixed_vs_strict},
        {"metric": "cases_harmed_vs_strict_f3", "value": harmed_vs_strict},
        {"metric": "cases_fixed_vs_external_l1_max", "value": fixed_vs_l1},
        {"metric": "cases_harmed_vs_external_l1_max", "value": harmed_vs_l1},
        {"metric": "improves_over_external_l1_max", "value": int(improve_cases > 0)},
        {"metric": "improvement_cases_over_external_l1_max", "value": improve_cases},
        {"metric": "larger_than_previous_plus_one_case", "value": int(larger_than_prev_plus_one)},
        {"metric": "classification", "value": readiness},
        {"metric": "safety", "value": safety},
    ]

    recommended = {
        "best_selector": best_sel,
        "matched_examples": n,
        "number_candidate_branches": len(candidate_rows),
        "number_answer_buckets": len({(r['dataset'], r['example_id'], r['seed'], r['budget'], r['normalized_answer']) for r in candidate_rows}),
        "improves_over_external_l1_max": bool(improve_cases > 0),
        "improvement_cases_over_external_l1_max": int(improve_cases),
        "larger_than_previous_plus_one_case": bool(larger_than_prev_plus_one),
        "harms_more_than_one_l1_solved_case": bool(harmed_vs_l1 > 1),
        "classification": readiness,
        "safety": safety,
        "oracle_headroom_accuracy_gap": oracle_acc - best_acc,
        "text_aware_beats_structural": bool(text_aware_best > structural_acc),
        "text_aware_beats_highest_maturity": bool(text_aware_best > high_mat_acc),
        "text_aware_did_not_improve_over_structural_or_highest_maturity": bool(text_not_better),
        "larger_real_model_pilot_justified": bool(improve_cases > 0 and harmed_vs_l1 <= 1),
        "source_answer_group_file": aux["ag_path"],
        "source_candidate_branch_file": aux["branch_path"],
    }

    write_csv(out_dir / "candidate_solution_rows.csv", candidate_rows)
    write_csv(out_dir / "verifier_feature_audit.csv", verifier_feature_audit_rows())
    write_csv(out_dir / "branch_level_verifier_scores.csv", branch_level_rows)
    write_csv(out_dir / "answer_bucket_scores.csv", bucket_score_rows)
    write_csv(out_dir / "selector_summary.csv", selector_summary)
    write_csv(out_dir / "per_case_selector_decisions.csv", decisions)
    write_csv(out_dir / "l1_better_subset_report.csv", _subset_report(decisions, "l1_better_case", subset_selectors))
    write_csv(out_dir / "frontier_better_subset_report.csv", _subset_report(decisions, "frontier_better_case", subset_selectors))
    write_csv(out_dir / "both_wrong_subset_report.csv", _subset_report(decisions, "both_wrong_case", subset_selectors))
    write_csv(out_dir / "verifier_training_report.csv", training_report)
    write_csv(out_dir / "oracle_gap_report.csv", oracle_gap_rows)
    write_json(out_dir / "recommended_next_steps.json", recommended)

    summary_lines = [
        "# Cobbe-style outcome verifier diagnostic",
        "",
        "## Inputs",
        f"- trace_dir: `{trace_dir}`",
        f"- cost_dir: `{cost_dir}`",
        f"- casebook_dir: `{casebook_dir}`",
        "",
        "## Required metrics",
        f"- matched_examples: {n}",
        f"- number_of_candidate_branches: {len(candidate_rows)}",
        f"- number_of_answer_buckets: {recommended['number_answer_buckets']}",
        f"- external_l1_max accuracy: {l1_acc}",
        f"- strict_f3 accuracy: {strict_acc}",
        f"- highest_support accuracy: {high_sup_acc}",
        f"- highest_maturity accuracy: {high_mat_acc}",
        f"- l1_preserve_if_present accuracy: {l1_preserve_acc}",
        f"- oracle_if_gold_present accuracy: {oracle_acc}",
        f"- structural logistic verifier selector accuracy: {structural_acc}",
        f"- TF-IDF text verifier selector accuracy: {tfidf_acc}",
        f"- hybrid verifier selector accuracy: {hybrid_acc}",
        f"- best Cobbe-style selector: {best_sel}",
        f"- best Cobbe-style selector accuracy: {best_acc}",
        f"- candidate-level structural accuracy/AUC: {candidate_metrics['structural_logistic'].get('candidate_level_accuracy')} / {candidate_metrics['structural_logistic'].get('candidate_level_auc')}",
        f"- candidate-level tfidf accuracy/AUC: {candidate_metrics['tfidf_solution_logistic'].get('candidate_level_accuracy')} / {candidate_metrics['tfidf_solution_logistic'].get('candidate_level_auc')}",
        f"- candidate-level hybrid accuracy/AUC: {candidate_metrics['hybrid_tfidf_structural_logistic'].get('candidate_level_accuracy')} / {candidate_metrics['hybrid_tfidf_structural_logistic'].get('candidate_level_auc')}",
        f"- cases_fixed_vs_strict_f3: {fixed_vs_strict}",
        f"- cases_harmed_vs_strict_f3: {harmed_vs_strict}",
        f"- cases_fixed_vs_external_l1_max: {fixed_vs_l1}",
        f"- cases_harmed_vs_external_l1_max: {harmed_vs_l1}",
        f"- gold_present_but_not_selected_count: {gold_present_not_selected}",
        f"- improves_over_external_l1_max: {improve_cases > 0}",
        f"- larger_than_previous_plus_one_case: {larger_than_prev_plus_one}",
        f"- larger_real_model_pilot_justified: {recommended['larger_real_model_pilot_justified']}",
        "",
        "## Interpretation",
        f"- readiness_classification: {readiness}",
        f"- safety_classification: {safety}",
        f"- oracle_headroom_accuracy_gap: {oracle_acc - best_acc}",
        f"- text_aware_did_not_improve_over_structural_or_highest_maturity: {text_not_better}",
        "- Diagnostic-only: no API calls, no manuscript updates, no canonical artifact changes.",
    ]
    (out_dir / "README.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

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
