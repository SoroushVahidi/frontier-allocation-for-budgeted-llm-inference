#!/usr/bin/env python3
"""Build and evaluate an offline learned fixed-pool reliability router.

Offline-only: consumes existing per-example artifacts and emits diagnostics.
No API calls are performed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier

from experiments.support_aware_selector import agreement_only_2of3_against_frontier


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT_DEFAULT = REPO_ROOT / "outputs" / "learned_fixed_pool_router_20260524"
DOC_PATH_DEFAULT = REPO_ROOT / "docs" / "LEARNED_FIXED_POOL_ROUTER_20260524.md"

METHOD_FRONTIER = "direct_reserve_semantic_frontier_v2"
METHOD_L1 = "external_l1_max"
METHOD_S1 = "external_s1_budget_forcing"
METHOD_TALE = "external_tale_prompt_budgeting"
ALL_METHODS = [METHOD_FRONTIER, METHOD_L1, METHOD_S1, METHOD_TALE]
METHOD_TO_SHORT = {
    METHOD_FRONTIER: "frontier",
    METHOD_L1: "L1",
    METHOD_S1: "S1",
    METHOD_TALE: "TALE",
}
SHORT_TO_METHOD = {v: k for k, v in METHOD_TO_SHORT.items()}
SOURCE_ORDER = ["frontier", "L1", "S1", "TALE"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help=(
            "Source spec: scenario_id|provider|dataset|/abs/or/rel/path/to/per_example_records.jsonl . "
            "Can be provided multiple times."
        ),
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=OUT_ROOT_DEFAULT,
        help=f"Output directory (default: {OUT_ROOT_DEFAULT})",
    )
    parser.add_argument(
        "--doc-path",
        type=Path,
        default=DOC_PATH_DEFAULT,
        help=f"Human report path (default: {DOC_PATH_DEFAULT})",
    )
    parser.add_argument("--random-seed", type=int, default=7)
    parser.add_argument("--n-folds", type=int, default=5)
    parser.add_argument(
        "--allow-auxiliary-sources",
        action="store_true",
        default=False,
        help="Allow sources that do not meet the canonical 300-example/1200-row shape requirement (e.g. auxiliary seed-11 runs). Shape check is logged as a warning rather than an error.",
    )
    return parser.parse_args()


def default_sources() -> list[str]:
    return [
        (
            "cohere_gsm8k|cohere|openai/gsm8k|"
            "outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z/"
            "cohere_real_model_cost_normalized_validation_20260523T181948Z/per_example_records.jsonl"
        ),
        (
            "mistral_gsm8k|mistral|openai/gsm8k|"
            "outputs/merged_repaired_cohere_mistral_selector_replay_20260524/"
            "mistral_full300_merged_per_example_records.jsonl"
        ),
    ]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, obj: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    ensure_dir(path.parent)
    if fieldnames is None:
        keys: set[str] = set()
        for row in rows:
            keys.update(row.keys())
        fieldnames = sorted(keys)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def norm_answer(x: Any) -> str | None:
    s = str(x or "").strip()
    if not s or s.lower() in {"none", "null", "__unknown__"}:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    if s.startswith("\\boxed{") and s.endswith("}"):
        s = s[len("\\boxed{") : -1].strip()
    s = re.sub(r"\s+", " ", s)
    try:
        if "/" in s and s.count("/") == 1 and not any(ch.isalpha() for ch in s):
            num_s, den_s = s.split("/")
            num = float(num_s)
            den = float(den_s)
            if den != 0:
                v = num / den
            else:
                v = None
        else:
            v = float(s)
        if v is not None and math.isfinite(v):
            if abs(v - int(v)) < 1e-12:
                return str(int(v))
            return f"{v:.10f}".rstrip("0").rstrip(".")
    except Exception:
        pass
    return s.lower()


def is_clean_numeric(ans: str | None) -> int:
    if ans is None:
        return 0
    return int(bool(re.fullmatch(r"[+-]?(\d+(\.\d+)?|\.\d+)", ans)))


def answer_len(ans: str | None) -> int:
    return len(str(ans or ""))


def pooled4_with_fallback(frontier: str | None, l1: str | None, s1: str | None, tale: str | None) -> tuple[str | None, str]:
    votes = [("frontier", frontier), ("L1", l1), ("S1", s1), ("TALE", tale)]
    valid = [a for _, a in votes if a is not None]
    if not valid:
        return frontier, "fallback_frontier_no_votes"
    counts = pd.Series(valid).value_counts()
    top_ans = str(counts.index[0])
    top_count = int(counts.iloc[0])
    second = int(counts.iloc[1]) if len(counts) > 1 else 0
    if top_count >= 3:
        return (frontier, "frontier_pooled_match") if top_ans == frontier else (top_ans, "pooled_majority")
    if top_count == 2 and second < 2:
        return (frontier, "frontier_pooled_match") if top_ans == frontier else (top_ans, "pooled_plurality_unique_2of4")
    return frontier, "fallback_frontier_no_majority"


def deterministic_fold(example_id: str, n_folds: int) -> int:
    h = hashlib.md5(example_id.encode("utf-8")).hexdigest()
    return int(h, 16) % n_folds


def parse_source_spec(spec: str) -> tuple[str, str, str, Path]:
    parts = spec.split("|")
    if len(parts) != 4:
        raise ValueError(f"invalid --source spec: {spec}")
    scenario_id, provider, dataset, path_s = parts
    path = Path(path_s)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return scenario_id, provider, dataset, path


@dataclass
class SourceLoadResult:
    scenario_id: str
    provider: str
    dataset: str
    path: Path
    rows: list[dict[str, Any]]
    integrity: dict[str, Any]


def validate_source_rows(rows: list[dict[str, Any]], expected_provider: str, expected_dataset: str) -> dict[str, Any]:
    method_counts: dict[str, int] = {}
    example_ids: set[str] = set()
    dup = 0
    seen: set[tuple[str, str]] = set()
    provider_vals: set[str] = set()
    dataset_vals: set[str] = set()
    has_question = 0
    has_correct = 0
    has_norm = 0
    for row in rows:
        method = str(row.get("method"))
        exid = str(row.get("example_id"))
        method_counts[method] = method_counts.get(method, 0) + 1
        example_ids.add(exid)
        key = (exid, method)
        if key in seen:
            dup += 1
        seen.add(key)
        provider_vals.add(str(row.get("provider")))
        dataset_vals.add(str(row.get("dataset")))
        if str(row.get("question") or "").strip():
            has_question += 1
        if row.get("exact_match") not in (None, ""):
            has_correct += 1
        if str(row.get("final_answer_canonical") or row.get("selected_answer_canonical") or "").strip():
            has_norm += 1
    integrity = {
        "rows": len(rows),
        "unique_examples": len(example_ids),
        "method_counts": method_counts,
        "duplicate_example_method_rows": dup,
        "provider_values": sorted(provider_vals),
        "dataset_values": sorted(dataset_vals),
        "has_question_rows": has_question,
        "has_exact_match_rows": has_correct,
        "has_normalized_answer_rows": has_norm,
    }
    integrity["pass_expected_shape"] = (
        len(rows) == 1200
        and len(example_ids) == 300
        and dup == 0
        and all(method_counts.get(m, 0) == 300 for m in ALL_METHODS)
        and provider_vals == {expected_provider}
        and dataset_vals == {expected_dataset}
    )
    return integrity


def load_source(spec: str) -> SourceLoadResult:
    scenario_id, provider, dataset, path = parse_source_spec(spec)
    rows = read_jsonl(path)
    integrity = validate_source_rows(rows, expected_provider=provider, expected_dataset=dataset)
    return SourceLoadResult(
        scenario_id=scenario_id,
        provider=provider,
        dataset=dataset,
        path=path,
        rows=rows,
        integrity=integrity,
    )


def _get_answer_from_row(row: dict[str, Any]) -> str | None:
    return norm_answer(row.get("final_answer_canonical") or row.get("selected_answer_canonical") or row.get("final_answer_raw"))


def _get_correct_from_row(row: dict[str, Any]) -> int:
    try:
        return int(row.get("exact_match") or 0)
    except Exception:
        return 0


def _make_pattern_features(frontier: str | None, l1: str | None, s1: str | None, tale: str | None) -> dict[str, int]:
    vals = {"frontier": frontier, "L1": l1, "S1": s1, "TALE": tale}
    nonnull = {k: v for k, v in vals.items() if v is not None}
    counts = pd.Series(list(nonnull.values())).value_counts() if nonnull else pd.Series(dtype=int)
    unique_count = int(len(counts))
    top_count = int(counts.iloc[0]) if len(counts) else 0
    n_top = int((counts == top_count).sum()) if len(counts) else 0

    majority_answer = str(counts.index[0]) if top_count >= 2 and n_top == 1 else None
    external = [l1, s1, tale]
    ext_nonnull = [x for x in external if x is not None]
    ext_counts = pd.Series(ext_nonnull).value_counts() if ext_nonnull else pd.Series(dtype=int)
    ext_top = int(ext_counts.iloc[0]) if len(ext_counts) else 0
    ext_n_top = int((ext_counts == ext_top).sum()) if len(ext_counts) else 0
    ext_majority_answer = str(ext_counts.index[0]) if ext_top >= 2 and ext_n_top == 1 else None

    return {
        "unique_answer_count": unique_count,
        "all_four_agree": int(unique_count == 1 and len(nonnull) == 4),
        "three_one_split": int(top_count == 3 and n_top == 1),
        "two_two_split": int(top_count == 2 and n_top == 2),
        "all_different": int(unique_count == len(nonnull) and len(nonnull) == 4),
        "frontier_in_majority": int(frontier is not None and majority_answer is not None and frontier == majority_answer),
        "S1_in_majority": int(s1 is not None and majority_answer is not None and s1 == majority_answer),
        "S1_isolated": int(s1 is not None and sum(int(s1 == x) for x in [frontier, l1, tale]) == 0),
        "frontier_isolated": int(frontier is not None and sum(int(frontier == x) for x in [l1, s1, tale]) == 0),
        "L1_TALE_agree": int(l1 is not None and tale is not None and l1 == tale),
        "L1_S1_agree": int(l1 is not None and s1 is not None and l1 == s1),
        "frontier_S1_agree": int(frontier is not None and s1 is not None and frontier == s1),
        "external_majority_exists": int(ext_majority_answer is not None),
        "external_majority_answer_excludes_frontier": int(ext_majority_answer is not None and frontier is not None and ext_majority_answer != frontier),
        "external_majority_answer_excludes_S1": int(ext_majority_answer is not None and s1 is not None and ext_majority_answer != s1),
    }


def _question_features(question: str) -> dict[str, int]:
    q = question or ""
    toks = re.findall(r"\S+", q)
    num_toks = re.findall(r"[+-]?\d+(?:\.\d+)?(?:/\d+)?", q)
    return {
        "question_len_chars": len(q),
        "question_len_tokens": len(toks),
        "question_numeric_tokens": len(num_toks),
        "has_fraction": int(bool(re.search(r"\b\d+/\d+\b", q))),
        "has_percentage": int("%" in q or "percent" in q.lower()),
        "has_equation_symbol": int(bool(re.search(r"[=<>]", q))),
        "operator_symbol_count": len(re.findall(r"[+\-*/^=<>]", q)),
    }


def build_example_rows(source: SourceLoadResult) -> list[dict[str, Any]]:
    by_ex: dict[str, dict[str, dict[str, Any]]] = {}
    for row in source.rows:
        exid = str(row.get("example_id"))
        by_ex.setdefault(exid, {})[str(row.get("method"))] = row

    rows: list[dict[str, Any]] = []
    for exid in sorted(by_ex.keys()):
        group = by_ex[exid]
        if any(m not in group for m in ALL_METHODS):
            continue
        r_frontier = group[METHOD_FRONTIER]
        r_l1 = group[METHOD_L1]
        r_s1 = group[METHOD_S1]
        r_tale = group[METHOD_TALE]
        frontier = _get_answer_from_row(r_frontier)
        l1 = _get_answer_from_row(r_l1)
        s1 = _get_answer_from_row(r_s1)
        tale = _get_answer_from_row(r_tale)
        pooled_ans, pooled_action = pooled4_with_fallback(frontier, l1, s1, tale)
        agreement_ans, agreement_meta = agreement_only_2of3_against_frontier(
            frontier_answer=frontier,
            l1_answer=l1,
            s1_answer=s1,
            tale_answer=tale,
        )
        agreement_ans = norm_answer(agreement_ans)
        gold = norm_answer(r_frontier.get("gold_answer_canonical") or r_frontier.get("gold_answer"))

        question = str(r_frontier.get("question") or r_l1.get("question") or r_s1.get("question") or r_tale.get("question") or "")

        out = {
            "scenario_id": source.scenario_id,
            "provider": source.provider,
            "dataset": source.dataset,
            "example_id": exid,
            "seed": int(r_frontier.get("seed") or 0),
            "budget": int(r_frontier.get("budget") or 0),
            "question": question,
            "gold_answer": gold,
            "frontier_answer": frontier,
            "L1_answer": l1,
            "S1_answer": s1,
            "TALE_answer": tale,
            "frontier_correct": _get_correct_from_row(r_frontier),
            "L1_correct": _get_correct_from_row(r_l1),
            "S1_correct": _get_correct_from_row(r_s1),
            "TALE_correct": _get_correct_from_row(r_tale),
            "pooled4_answer": pooled_ans,
            "pooled4_action_detail": pooled_action,
            "agreement_only_answer": agreement_ans,
            "agreement_only_action_detail": str(agreement_meta.get("reason", "")),
            "pooled4_correct": int(pooled_ans is not None and gold is not None and pooled_ans == gold),
            "agreement_only_correct": int(agreement_ans is not None and gold is not None and agreement_ans == gold),
            "always_s1_correct": _get_correct_from_row(r_s1),
            "frontier_answer_len": answer_len(frontier),
            "L1_answer_len": answer_len(l1),
            "S1_answer_len": answer_len(s1),
            "TALE_answer_len": answer_len(tale),
            "frontier_clean_numeric": is_clean_numeric(frontier),
            "L1_clean_numeric": is_clean_numeric(l1),
            "S1_clean_numeric": is_clean_numeric(s1),
            "TALE_clean_numeric": is_clean_numeric(tale),
            "frontier_parse_success": int(frontier is not None),
            "L1_parse_success": int(l1 is not None),
            "S1_parse_success": int(s1 is not None),
            "TALE_parse_success": int(tale is not None),
            "frontier_missing_answer": int(frontier is None),
            "L1_missing_answer": int(l1 is None),
            "S1_missing_answer": int(s1 is None),
            "TALE_missing_answer": int(tale is None),
            "frontier_raw_len": len(str(r_frontier.get("final_answer_raw") or "")),
            "L1_raw_len": len(str(r_l1.get("final_answer_raw") or "")),
            "S1_raw_len": len(str(r_s1.get("final_answer_raw") or "")),
            "TALE_raw_len": len(str(r_tale.get("final_answer_raw") or "")),
        }
        out.update(_question_features(question))
        out.update(_make_pattern_features(frontier, l1, s1, tale))
        out["oracle_best_source_correct"] = int(max(out[f"{s}_correct"] for s in SOURCE_ORDER))
        out["oracle_best_action_correct"] = int(
            max(
                out["frontier_correct"],
                out["L1_correct"],
                out["S1_correct"],
                out["TALE_correct"],
                out["pooled4_correct"],
                out["agreement_only_correct"],
            )
        )
        rows.append(out)
    return rows


def compute_calibration_stats(train_df: pd.DataFrame) -> dict[str, Any]:
    n = max(1, len(train_df))
    raw_acc = {s: float(train_df[f"{s}_correct"].mean()) for s in SOURCE_ORDER}
    shrunk_acc = {s: float((train_df[f"{s}_correct"].sum() + 1.0) / (n + 2.0)) for s in SOURCE_ORDER}
    sorted_raw = sorted(raw_acc.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    sorted_shrunk = sorted(shrunk_acc.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    best_raw_source, best_raw_acc = sorted_raw[0]
    second_raw_acc = sorted_raw[1][1]
    best_shrunk_source, best_shrunk_acc = sorted_shrunk[0]
    second_shrunk_acc = sorted_shrunk[1][1]

    same_answer_rates: dict[str, float] = {}
    same_wrong_rates: dict[str, float] = {}
    pairs = [("frontier", "L1"), ("frontier", "S1"), ("frontier", "TALE"), ("L1", "S1"), ("L1", "TALE"), ("S1", "TALE")]
    for a, b in pairs:
        sa = train_df[f"{a}_answer"] == train_df[f"{b}_answer"]
        same_answer_rates[f"{a}_{b}_same_answer_rate"] = float(sa.mean())
        same_wrong = sa & (train_df[f"{a}_correct"] == 0) & (train_df[f"{b}_correct"] == 0)
        same_wrong_rates[f"{a}_{b}_same_wrong_rate"] = float(same_wrong.mean())

    return {
        "n_train": int(n),
        "raw_acc": raw_acc,
        "shrunk_acc": shrunk_acc,
        "best_raw_source": best_raw_source,
        "best_shrunk_source": best_shrunk_source,
        "best_raw_minus_second": float(best_raw_acc - second_raw_acc),
        "best_shrunk_minus_second": float(best_shrunk_acc - second_shrunk_acc),
        "dominance_raw_0p05": int((best_raw_acc - second_raw_acc) > 0.05),
        "dominance_raw_0p10": int((best_raw_acc - second_raw_acc) > 0.10),
        "dominance_shrunk_0p05": int((best_shrunk_acc - second_shrunk_acc) > 0.05),
        "dominance_shrunk_0p10": int((best_shrunk_acc - second_shrunk_acc) > 0.10),
        "same_answer_rates": same_answer_rates,
        "same_wrong_rates": same_wrong_rates,
    }


def apply_dynamic_actions(df: pd.DataFrame, cal: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    raw_best = str(cal["best_raw_source"])
    beta_best = str(cal["best_shrunk_source"])
    raw_dom = bool(cal["dominance_raw_0p05"])
    beta_dom = bool(cal["dominance_shrunk_0p05"])

    def _row_apply(row: pd.Series, mode: str) -> tuple[str | None, str]:
        if mode == "raw":
            if raw_dom:
                src = raw_best
                return row[f"{src}_answer"], f"best_source_raw_{src}"
            return row["pooled4_answer"], "pooled4_raw_fallback"
        if beta_dom:
            src = beta_best
            return row[f"{src}_answer"], f"best_source_beta_{src}"
        return row["pooled4_answer"], "pooled4_beta_fallback"

    raw_ans: list[str | None] = []
    raw_action: list[str] = []
    beta_ans: list[str | None] = []
    beta_action: list[str] = []
    raw_ok: list[int] = []
    beta_ok: list[int] = []
    dom_ok: list[int] = []
    for _, row in out.iterrows():
        r_ans, r_action = _row_apply(row, "raw")
        b_ans, b_action = _row_apply(row, "beta")
        raw_ans.append(r_ans)
        raw_action.append(r_action)
        beta_ans.append(b_ans)
        beta_action.append(b_action)
        gold = row["gold_answer"]
        raw_ok.append(int(r_ans is not None and gold is not None and r_ans == gold))
        beta_ok.append(int(b_ans is not None and gold is not None and b_ans == gold))
        dom_ok.append(int(b_ans is not None and gold is not None and b_ans == gold))
    out["raw_spread_regime_selector_answer"] = raw_ans
    out["raw_spread_regime_selector_action_detail"] = raw_action
    out["raw_spread_regime_selector_correct"] = raw_ok
    out["beta_shrinkage_regime_selector_answer"] = beta_ans
    out["beta_shrinkage_regime_selector_action_detail"] = beta_action
    out["beta_shrinkage_regime_selector_correct"] = beta_ok
    out["dominant_source_action_correct"] = dom_ok
    return out


def add_calibration_feature_columns(df: pd.DataFrame, cal: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    for s in SOURCE_ORDER:
        out[f"train_raw_acc_{s}"] = float(cal["raw_acc"][s])
        out[f"train_shrunk_acc_{s}"] = float(cal["shrunk_acc"][s])
    out["train_best_source_raw"] = str(cal["best_raw_source"])
    out["train_best_source_shrunk"] = str(cal["best_shrunk_source"])
    out["train_best_minus_second_raw"] = float(cal["best_raw_minus_second"])
    out["train_best_minus_second_shrunk"] = float(cal["best_shrunk_minus_second"])
    out["train_dominance_raw_0p05"] = int(cal["dominance_raw_0p05"])
    out["train_dominance_raw_0p10"] = int(cal["dominance_raw_0p10"])
    out["train_dominance_shrunk_0p05"] = int(cal["dominance_shrunk_0p05"])
    out["train_dominance_shrunk_0p10"] = int(cal["dominance_shrunk_0p10"])
    for k, v in cal["same_answer_rates"].items():
        out[f"train_{k}"] = float(v)
    for k, v in cal["same_wrong_rates"].items():
        out[f"train_{k}"] = float(v)
    return out


def feature_columns() -> tuple[list[str], list[str], list[str]]:
    runtime_numeric = [
        "question_len_chars",
        "question_len_tokens",
        "question_numeric_tokens",
        "has_fraction",
        "has_percentage",
        "has_equation_symbol",
        "operator_symbol_count",
        "unique_answer_count",
        "all_four_agree",
        "three_one_split",
        "two_two_split",
        "all_different",
        "frontier_in_majority",
        "S1_in_majority",
        "S1_isolated",
        "frontier_isolated",
        "L1_TALE_agree",
        "L1_S1_agree",
        "frontier_S1_agree",
        "external_majority_exists",
        "external_majority_answer_excludes_frontier",
        "external_majority_answer_excludes_S1",
        "frontier_clean_numeric",
        "L1_clean_numeric",
        "S1_clean_numeric",
        "TALE_clean_numeric",
        "frontier_answer_len",
        "L1_answer_len",
        "S1_answer_len",
        "TALE_answer_len",
        "frontier_raw_len",
        "L1_raw_len",
        "S1_raw_len",
        "TALE_raw_len",
        "frontier_parse_success",
        "L1_parse_success",
        "S1_parse_success",
        "TALE_parse_success",
        "frontier_missing_answer",
        "L1_missing_answer",
        "S1_missing_answer",
        "TALE_missing_answer",
    ]
    calibration_numeric = [
        "train_best_minus_second_raw",
        "train_best_minus_second_shrunk",
        "train_dominance_raw_0p05",
        "train_dominance_raw_0p10",
        "train_dominance_shrunk_0p05",
        "train_dominance_shrunk_0p10",
    ]
    for s in SOURCE_ORDER:
        calibration_numeric.append(f"train_raw_acc_{s}")
        calibration_numeric.append(f"train_shrunk_acc_{s}")
    for pair in [
        "frontier_L1",
        "frontier_S1",
        "frontier_TALE",
        "L1_S1",
        "L1_TALE",
        "S1_TALE",
    ]:
        calibration_numeric.append(f"train_{pair}_same_answer_rate")
        calibration_numeric.append(f"train_{pair}_same_wrong_rate")
    categorical = ["provider", "dataset", "scenario_id", "train_best_source_raw", "train_best_source_shrunk"]
    return runtime_numeric, calibration_numeric, categorical


def _build_preprocessor(cat_cols: list[str], num_cols: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
            ("num", "passthrough", num_cols),
        ],
        remainder="drop",
        sparse_threshold=0.0,
    )


def _fit_binary_classifier(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    model_type: str,
    seed: int,
    cat_cols: list[str],
    num_cols: list[str],
    max_depth: int | None = None,
) -> BaseEstimator:
    if len(np.unique(y_train)) < 2:
        model = DummyClassifier(strategy="constant", constant=int(y_train[0]))
        model.fit(np.zeros((len(y_train), 1)), y_train)
        return model
    pre = _build_preprocessor(cat_cols=cat_cols, num_cols=num_cols)
    if model_type == "logreg":
        clf: BaseEstimator = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed)
    elif model_type == "tree":
        clf = DecisionTreeClassifier(max_depth=max_depth or 3, min_samples_leaf=8, random_state=seed)
    elif model_type == "hgb":
        clf = HistGradientBoostingClassifier(
            max_depth=max_depth or 3,
            max_iter=120,
            learning_rate=0.05,
            min_samples_leaf=20,
            random_state=seed,
        )
    else:
        raise ValueError(f"unknown model_type={model_type}")
    pipe = Pipeline([("pre", pre), ("clf", clf)])
    pipe.fit(X_train, y_train)
    return pipe


def _predict_prob_positive(model: BaseEstimator, X: pd.DataFrame) -> np.ndarray:
    if isinstance(model, DummyClassifier):
        if hasattr(model, "predict_proba"):
            return model.predict_proba(np.zeros((len(X), 1)))[:, 1]
        return model.predict(np.zeros((len(X), 1))).astype(float)
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)
        if probs.shape[1] == 1:
            return probs[:, 0]
        return probs[:, 1]
    if hasattr(model, "decision_function"):
        raw = model.decision_function(X)
        return 1.0 / (1.0 + np.exp(-np.asarray(raw)))
    pred = model.predict(X)
    return np.asarray(pred).astype(float)


def _action_to_answer_and_correct(row: pd.Series, action_name: str) -> tuple[str | None, int]:
    if action_name == "choose_frontier":
        return row["frontier_answer"], int(row["frontier_correct"])
    if action_name == "choose_L1":
        return row["L1_answer"], int(row["L1_correct"])
    if action_name == "choose_S1":
        return row["S1_answer"], int(row["S1_correct"])
    if action_name == "choose_TALE":
        return row["TALE_answer"], int(row["TALE_correct"])
    if action_name == "pooled4_with_fallback":
        return row["pooled4_answer"], int(row["pooled4_correct"])
    if action_name == "agreement_only_2of3_against_frontier":
        return row["agreement_only_answer"], int(row["agreement_only_correct"])
    if action_name == "raw_spread_regime_selector":
        return row["raw_spread_regime_selector_answer"], int(row["raw_spread_regime_selector_correct"])
    if action_name == "beta_shrinkage_regime_selector":
        return row["beta_shrinkage_regime_selector_answer"], int(row["beta_shrinkage_regime_selector_correct"])
    raise ValueError(action_name)


def _compute_ece(y_true: np.ndarray, y_prob: np.ndarray, bins: int = 5) -> float:
    if len(y_true) == 0:
        return 0.0
    y_true = np.asarray(y_true).astype(float)
    y_prob = np.asarray(y_prob).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(bins):
        left, right = edges[i], edges[i + 1]
        if i == bins - 1:
            mask = (y_prob >= left) & (y_prob <= right)
        else:
            mask = (y_prob >= left) & (y_prob < right)
        if not mask.any():
            continue
        acc = y_true[mask].mean()
        conf = y_prob[mask].mean()
        ece += (mask.sum() / n) * abs(acc - conf)
    return float(ece)


def _metric_row(
    protocol: str,
    scenario_id: str,
    model_name: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray | None,
    pooled4_true: np.ndarray,
    s1_true: np.ndarray,
    best_static_true: np.ndarray,
    oracle_source_true: np.ndarray,
    oracle_action_true: np.ndarray,
) -> dict[str, Any]:
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    pooled4_true = np.asarray(pooled4_true).astype(int)
    s1_true = np.asarray(s1_true).astype(int)
    best_static_true = np.asarray(best_static_true).astype(int)
    oracle_source_true = np.asarray(oracle_source_true).astype(int)
    oracle_action_true = np.asarray(oracle_action_true).astype(int)
    n = int(len(y_true))
    acc = float(y_pred.mean()) if n else 0.0
    pooled_acc = float(pooled4_true.mean()) if n else 0.0
    s1_acc = float(s1_true.mean()) if n else 0.0
    best_static_acc = float(best_static_true.mean()) if n else 0.0
    oracle_source_acc = float(oracle_source_true.mean()) if n else 0.0
    oracle_action_acc = float(oracle_action_true.mean()) if n else 0.0
    wins_pooled = int(((y_pred == 1) & (pooled4_true == 0)).sum())
    losses_pooled = int(((y_pred == 0) & (pooled4_true == 1)).sum())
    ties_pooled = int((y_pred == pooled4_true).sum())
    wins_s1 = int(((y_pred == 1) & (s1_true == 0)).sum())
    losses_s1 = int(((y_pred == 0) & (s1_true == 1)).sum())
    ties_s1 = int((y_pred == s1_true).sum())
    rec_vs_pooled = wins_pooled
    reg_vs_pooled = losses_pooled
    rec_vs_best_static = int(((y_pred == 1) & (best_static_true == 0)).sum())
    reg_vs_best_static = int(((y_pred == 0) & (best_static_true == 1)).sum())
    out = {
        "protocol": protocol,
        "scenario_id": scenario_id,
        "model_name": model_name,
        "n_examples": n,
        "accuracy": acc,
        "pooled4_accuracy": pooled_acc,
        "always_s1_accuracy": s1_acc,
        "best_static_source_accuracy": best_static_acc,
        "oracle_best_source_accuracy": oracle_source_acc,
        "oracle_best_action_accuracy": oracle_action_acc,
        "regret_to_best_static_source": float(best_static_acc - acc),
        "regret_to_oracle_best_source": float(oracle_source_acc - acc),
        "regret_to_oracle_best_action": float(oracle_action_acc - acc),
        "win_vs_pooled4": wins_pooled,
        "loss_vs_pooled4": losses_pooled,
        "tie_vs_pooled4": ties_pooled,
        "win_vs_always_s1": wins_s1,
        "loss_vs_always_s1": losses_s1,
        "tie_vs_always_s1": ties_s1,
        "recovery_vs_pooled4": rec_vs_pooled,
        "regression_vs_pooled4": reg_vs_pooled,
        "recovery_vs_best_static_source": rec_vs_best_static,
        "regression_vs_best_static_source": reg_vs_best_static,
    }
    if y_prob is not None and n:
        prob_arr = np.asarray(y_prob).astype(float)
        finite_mask = np.isfinite(prob_arr)
        if finite_mask.any():
            prob_use = prob_arr[finite_mask]
            y_use = y_true[finite_mask]
            out["brier_score"] = float(brier_score_loss(y_use, prob_use))
            out["ece_5bin"] = _compute_ece(y_use, prob_use, bins=5)
        else:
            out["brier_score"] = np.nan
            out["ece_5bin"] = np.nan
    else:
        out["brier_score"] = np.nan
        out["ece_5bin"] = np.nan
    return out


def _best_static_source_from_train(train_df: pd.DataFrame) -> str:
    accs = {s: float(train_df[f"{s}_correct"].mean()) for s in SOURCE_ORDER}
    return max(SOURCE_ORDER, key=lambda s: (accs[s], s))


def _build_feature_frame(df: pd.DataFrame, include_scenario_features: bool) -> tuple[pd.DataFrame, list[str], list[str]]:
    runtime_num, calibration_num, categorical = feature_columns()
    cats = [c for c in categorical if c in df.columns]
    if not include_scenario_features:
        cats = [c for c in cats if c not in {"provider", "scenario_id"}]
    num_cols = runtime_num + calibration_num
    return df[num_cols + cats].copy(), num_cols, cats


def _fit_predict_source_router(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    seed: int,
    include_scenario_features: bool,
) -> tuple[pd.DataFrame, dict[str, BaseEstimator]]:
    X_train, num_cols, cat_cols = _build_feature_frame(train_df, include_scenario_features=include_scenario_features)
    X_test, _, _ = _build_feature_frame(test_df, include_scenario_features=include_scenario_features)
    models: dict[str, BaseEstimator] = {}
    prob_cols: dict[str, np.ndarray] = {}
    for s in SOURCE_ORDER:
        y_train = train_df[f"{s}_correct"].to_numpy(dtype=int)
        model = _fit_binary_classifier(X_train, y_train, model_type="logreg", seed=seed, cat_cols=cat_cols, num_cols=num_cols)
        models[s] = model
        prob_cols[s] = _predict_prob_positive(model, X_test)
    probs_mat = np.column_stack([prob_cols[s] for s in SOURCE_ORDER])
    best_idx = np.argmax(probs_mat, axis=1)
    chosen_sources = [SOURCE_ORDER[i] for i in best_idx]
    chosen_prob = probs_mat[np.arange(len(test_df)), best_idx]
    pred_rows = test_df[["scenario_id", "provider", "dataset", "example_id", "seed", "budget"]].copy()
    pred_rows["selected_action"] = [f"choose_{s}" for s in chosen_sources]
    pred_rows["selected_source"] = chosen_sources
    pred_rows["selected_answer"] = [test_df.iloc[i][f"{s}_answer"] for i, s in enumerate(chosen_sources)]
    pred_rows["selected_correct"] = [int(test_df.iloc[i][f"{s}_correct"]) for i, s in enumerate(chosen_sources)]
    pred_rows["predicted_probability"] = chosen_prob
    for s in SOURCE_ORDER:
        pred_rows[f"p_{s}"] = prob_cols[s]
    return pred_rows, models


def _fit_predict_action_router(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    seed: int,
    include_scenario_features: bool,
    model_kind: str,
    max_depth: int | None = None,
) -> tuple[pd.DataFrame, dict[str, BaseEstimator]]:
    X_train, num_cols, cat_cols = _build_feature_frame(train_df, include_scenario_features=include_scenario_features)
    X_test, _, _ = _build_feature_frame(test_df, include_scenario_features=include_scenario_features)
    actions = [
        "choose_frontier",
        "choose_L1",
        "choose_S1",
        "choose_TALE",
        "pooled4_with_fallback",
        "agreement_only_2of3_against_frontier",
        "raw_spread_regime_selector",
        "beta_shrinkage_regime_selector",
    ]
    label_map = {
        "choose_frontier": "frontier_correct",
        "choose_L1": "L1_correct",
        "choose_S1": "S1_correct",
        "choose_TALE": "TALE_correct",
        "pooled4_with_fallback": "pooled4_correct",
        "agreement_only_2of3_against_frontier": "agreement_only_correct",
        "raw_spread_regime_selector": "raw_spread_regime_selector_correct",
        "beta_shrinkage_regime_selector": "beta_shrinkage_regime_selector_correct",
    }
    models: dict[str, BaseEstimator] = {}
    prob_cols: dict[str, np.ndarray] = {}
    for action in actions:
        y_train = train_df[label_map[action]].to_numpy(dtype=int)
        model = _fit_binary_classifier(
            X_train,
            y_train,
            model_type=model_kind,
            seed=seed,
            cat_cols=cat_cols,
            num_cols=num_cols,
            max_depth=max_depth,
        )
        models[action] = model
        prob_cols[action] = _predict_prob_positive(model, X_test)
    probs_mat = np.column_stack([prob_cols[a] for a in actions])
    best_idx = np.argmax(probs_mat, axis=1)
    chosen_actions = [actions[i] for i in best_idx]
    chosen_prob = probs_mat[np.arange(len(test_df)), best_idx]

    pred_rows = test_df[["scenario_id", "provider", "dataset", "example_id", "seed", "budget"]].copy()
    pred_rows["selected_action"] = chosen_actions
    selected_sources: list[str] = []
    selected_answers: list[str | None] = []
    selected_correct: list[int] = []
    for i, action in enumerate(chosen_actions):
        row = test_df.iloc[i]
        ans, ok = _action_to_answer_and_correct(row, action)
        selected_answers.append(ans)
        selected_correct.append(ok)
        if action.startswith("choose_"):
            selected_sources.append(action.replace("choose_", ""))
        else:
            selected_sources.append(action)
    pred_rows["selected_source"] = selected_sources
    pred_rows["selected_answer"] = selected_answers
    pred_rows["selected_correct"] = selected_correct
    pred_rows["predicted_probability"] = chosen_prob
    for action in actions:
        pred_rows[f"p_{action}"] = prob_cols[action]
    return pred_rows, models


def _baseline_predictions(test_df: pd.DataFrame, train_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    best_train_source = _best_static_source_from_train(train_df)
    defs: dict[str, Callable[[pd.Series], tuple[str | None, int, str]]] = {
        "frontier": lambda r: (r["frontier_answer"], int(r["frontier_correct"]), "frontier"),
        "L1": lambda r: (r["L1_answer"], int(r["L1_correct"]), "L1"),
        "S1": lambda r: (r["S1_answer"], int(r["S1_correct"]), "S1"),
        "TALE": lambda r: (r["TALE_answer"], int(r["TALE_correct"]), "TALE"),
        "best_static_source_train_fold": lambda r: (r[f"{best_train_source}_answer"], int(r[f"{best_train_source}_correct"]), best_train_source),
        "pooled4_with_fallback": lambda r: (r["pooled4_answer"], int(r["pooled4_correct"]), "pooled4"),
        "agreement_only_2of3_against_frontier": lambda r: (r["agreement_only_answer"], int(r["agreement_only_correct"]), "agreement"),
        "raw_spread_regime_selector": lambda r: (
            r["raw_spread_regime_selector_answer"],
            int(r["raw_spread_regime_selector_correct"]),
            "raw_spread",
        ),
        "beta_shrinkage_regime_selector": lambda r: (
            r["beta_shrinkage_regime_selector_answer"],
            int(r["beta_shrinkage_regime_selector_correct"]),
            "beta_shrinkage",
        ),
        "always_S1": lambda r: (r["S1_answer"], int(r["S1_correct"]), "S1"),
        "oracle_best_source": lambda r: (
            next((r[f"{s}_answer"] for s in SOURCE_ORDER if int(r[f"{s}_correct"]) == 1), r["frontier_answer"]),
            int(r["oracle_best_source_correct"]),
            "oracle_source",
        ),
        "oracle_best_action": lambda r: (
            next(
                (
                    r[f"{s}_answer"]
                    for s in SOURCE_ORDER
                    if int(r[f"{s}_correct"]) == 1
                ),
                r["pooled4_answer"],
            ),
            int(r["oracle_best_action_correct"]),
            "oracle_action",
        ),
    }
    out: dict[str, pd.DataFrame] = {}
    for name, fn in defs.items():
        base = test_df[["scenario_id", "provider", "dataset", "example_id", "seed", "budget"]].copy()
        actions = [fn(test_df.iloc[i]) for i in range(len(test_df))]
        base["selected_answer"] = [a[0] for a in actions]
        base["selected_correct"] = [a[1] for a in actions]
        base["selected_source"] = [a[2] for a in actions]
        base["selected_action"] = name
        base["predicted_probability"] = np.nan
        out[name] = base
    return out


def _evaluate_prediction_df(
    protocol: str,
    model_name: str,
    pred_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario_id, grp in pred_df.groupby("scenario_id"):
        test_grp = test_df[test_df["scenario_id"] == scenario_id].set_index("example_id")
        pred_grp = grp.set_index("example_id")
        common = [eid for eid in pred_grp.index if eid in test_grp.index]
        y_pred = pred_grp.loc[common, "selected_correct"].to_numpy(dtype=int)
        pooled4 = test_grp.loc[common, "pooled4_correct"].to_numpy(dtype=int)
        s1 = test_grp.loc[common, "S1_correct"].to_numpy(dtype=int)
        best_static = []
        for eid in common:
            row = test_grp.loc[eid]
            best_static.append(max(int(row["frontier_correct"]), int(row["L1_correct"]), int(row["S1_correct"]), int(row["TALE_correct"])))
        best_static_arr = np.asarray(best_static, dtype=int)
        oracle_source = test_grp.loc[common, "oracle_best_source_correct"].to_numpy(dtype=int)
        oracle_action = test_grp.loc[common, "oracle_best_action_correct"].to_numpy(dtype=int)
        probs = pred_grp.loc[common, "predicted_probability"].to_numpy(dtype=float) if "predicted_probability" in pred_grp.columns else None
        row = _metric_row(
            protocol=protocol,
            scenario_id=str(scenario_id),
            model_name=model_name,
            y_true=y_pred,
            y_pred=y_pred,
            y_prob=probs,
            pooled4_true=pooled4,
            s1_true=s1,
            best_static_true=best_static_arr,
            oracle_source_true=oracle_source,
            oracle_action_true=oracle_action,
        )
        rows.append(row)
    # macro + worst scenario
    if rows:
        macro_acc = float(np.mean([r["accuracy"] for r in rows]))
        worst = float(np.min([r["accuracy"] for r in rows]))
        rows.append(
            {
                "protocol": protocol,
                "scenario_id": "ALL_MACRO",
                "model_name": model_name,
                "n_examples": int(sum(r["n_examples"] for r in rows)),
                "accuracy": macro_acc,
                "worst_scenario_accuracy": worst,
            }
        )
    return rows


def _collect_feature_importance(
    model_name: str,
    models: dict[str, BaseEstimator],
    feature_names_fn: Callable[[BaseEstimator], list[str] | None],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target, model in models.items():
        features = feature_names_fn(model)
        if features is None:
            continue
        clf = model.named_steps["clf"] if isinstance(model, Pipeline) and "clf" in model.named_steps else None
        if clf is None:
            continue
        if hasattr(clf, "coef_"):
            coef = np.asarray(clf.coef_).reshape(-1)
            top_idx = np.argsort(np.abs(coef))[::-1][:20]
            for idx in top_idx:
                rows.append(
                    {
                        "router_model": model_name,
                        "target": target,
                        "feature": features[idx],
                        "importance_type": "abs_coef",
                        "importance_value": float(abs(coef[idx])),
                        "signed_value": float(coef[idx]),
                    }
                )
        elif hasattr(clf, "feature_importances_"):
            imp = np.asarray(clf.feature_importances_).reshape(-1)
            top_idx = np.argsort(imp)[::-1][:20]
            for idx in top_idx:
                rows.append(
                    {
                        "router_model": model_name,
                        "target": target,
                        "feature": features[idx],
                        "importance_type": "tree_importance",
                        "importance_value": float(imp[idx]),
                        "signed_value": np.nan,
                    }
                )
    return rows


def _extract_feature_names(model: BaseEstimator) -> list[str] | None:
    if not isinstance(model, Pipeline):
        return None
    if "pre" not in model.named_steps:
        return None
    pre = model.named_steps["pre"]
    try:
        names = pre.get_feature_names_out()
        return [str(n) for n in names]
    except Exception:
        return None


def run_protocol(
    *,
    protocol: str,
    full_df: pd.DataFrame,
    split_iter: list[tuple[np.ndarray, np.ndarray]],
    include_scenario_features: bool,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    metrics_rows: list[dict[str, Any]] = []
    pred_rows: list[dict[str, Any]] = []
    calib_rows: list[dict[str, Any]] = []
    fold_models: dict[str, Any] = {}

    for fold_idx, (train_idx, test_idx) in enumerate(split_iter):
        train_df = full_df.iloc[train_idx].reset_index(drop=True)
        test_df = full_df.iloc[test_idx].reset_index(drop=True)
        cal = compute_calibration_stats(train_df)
        train_df = apply_dynamic_actions(train_df, cal)
        test_df = apply_dynamic_actions(test_df, cal)
        train_df = add_calibration_feature_columns(train_df, cal)
        test_df = add_calibration_feature_columns(test_df, cal)

        baseline_preds = _baseline_predictions(test_df, train_df)
        for bname, bdf in baseline_preds.items():
            bdf = bdf.copy()
            bdf["protocol"] = protocol
            bdf["fold"] = fold_idx
            bdf["model_name"] = bname
            pred_rows.extend(bdf.to_dict(orient="records"))
            metrics_rows.extend(_evaluate_prediction_df(protocol, bname, bdf, test_df))

        src_pred, src_models = _fit_predict_source_router(
            train_df=train_df,
            test_df=test_df,
            seed=seed + fold_idx,
            include_scenario_features=include_scenario_features,
        )
        src_name = "source_logistic_router_with_ids" if include_scenario_features else "source_logistic_router_no_ids"
        src_pred["protocol"] = protocol
        src_pred["fold"] = fold_idx
        src_pred["model_name"] = src_name
        pred_rows.extend(src_pred.to_dict(orient="records"))
        metrics_rows.extend(_evaluate_prediction_df(protocol, src_name, src_pred, test_df))

        act_pred, act_models = _fit_predict_action_router(
            train_df=train_df,
            test_df=test_df,
            seed=seed + fold_idx,
            include_scenario_features=include_scenario_features,
            model_kind="logreg",
        )
        act_name = "action_logistic_router_with_ids" if include_scenario_features else "action_logistic_router_no_ids"
        act_pred["protocol"] = protocol
        act_pred["fold"] = fold_idx
        act_pred["model_name"] = act_name
        pred_rows.extend(act_pred.to_dict(orient="records"))
        metrics_rows.extend(_evaluate_prediction_df(protocol, act_name, act_pred, test_df))

        best_tree_pred: pd.DataFrame | None = None
        best_tree_acc = -1.0
        best_tree_depth = None
        best_tree_models: dict[str, BaseEstimator] | None = None
        for d in [2, 3, 4]:
            tree_pred, tree_models = _fit_predict_action_router(
                train_df=train_df,
                test_df=test_df,
                seed=seed + fold_idx,
                include_scenario_features=include_scenario_features,
                model_kind="tree",
                max_depth=d,
            )
            acc = float(tree_pred["selected_correct"].mean()) if len(tree_pred) else 0.0
            if acc > best_tree_acc:
                best_tree_acc = acc
                best_tree_pred = tree_pred
                best_tree_depth = d
                best_tree_models = tree_models
        assert best_tree_pred is not None
        tree_name = (
            f"action_tree_router_depth{best_tree_depth}_with_ids"
            if include_scenario_features
            else f"action_tree_router_depth{best_tree_depth}_no_ids"
        )
        best_tree_pred = best_tree_pred.copy()
        best_tree_pred["protocol"] = protocol
        best_tree_pred["fold"] = fold_idx
        best_tree_pred["model_name"] = tree_name
        pred_rows.extend(best_tree_pred.to_dict(orient="records"))
        metrics_rows.extend(_evaluate_prediction_df(protocol, tree_name, best_tree_pred, test_df))

        gb_pred, gb_models = _fit_predict_action_router(
            train_df=train_df,
            test_df=test_df,
            seed=seed + fold_idx,
            include_scenario_features=include_scenario_features,
            model_kind="hgb",
            max_depth=3,
        )
        gb_name = "action_hgb_router_with_ids" if include_scenario_features else "action_hgb_router_no_ids"
        gb_pred["protocol"] = protocol
        gb_pred["fold"] = fold_idx
        gb_pred["model_name"] = gb_name
        pred_rows.extend(gb_pred.to_dict(orient="records"))
        metrics_rows.extend(_evaluate_prediction_df(protocol, gb_name, gb_pred, test_df))

        calib_rows.append(
            {
                "protocol": protocol,
                "fold": fold_idx,
                "train_n": cal["n_train"],
                "best_raw_source": cal["best_raw_source"],
                "best_shrunk_source": cal["best_shrunk_source"],
                "best_raw_minus_second": cal["best_raw_minus_second"],
                "best_shrunk_minus_second": cal["best_shrunk_minus_second"],
                "dominance_raw_0p05": cal["dominance_raw_0p05"],
                "dominance_shrunk_0p05": cal["dominance_shrunk_0p05"],
            }
        )
        fold_models[f"{protocol}_fold{fold_idx}"] = {
            "source_models": src_models,
            "action_logreg_models": act_models,
            "action_tree_models": best_tree_models,
            "action_hgb_models": gb_models,
        }

    return metrics_rows, pred_rows, calib_rows, fold_models


def build_split_iter_within(df: pd.DataFrame, scenario_id: str, n_folds: int) -> list[tuple[np.ndarray, np.ndarray]]:
    sdf = df[df["scenario_id"] == scenario_id].reset_index(drop=False)
    fold_map = {i: deterministic_fold(str(sdf.iloc[i]["example_id"]), n_folds) for i in range(len(sdf))}
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    global_idx = sdf["index"].to_numpy()
    for fold in range(n_folds):
        test_global = global_idx[[i for i in range(len(sdf)) if fold_map[i] == fold]]
        train_global = np.array([idx for idx in global_idx if idx not in set(test_global)], dtype=int)
        splits.append((train_global, test_global.astype(int)))
    return splits


def build_split_iter_pooled(df: pd.DataFrame, n_folds: int, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    splitter = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    y = df["scenario_id"].to_numpy()
    X = np.arange(len(df))
    return [(train_idx, test_idx) for train_idx, test_idx in splitter.split(X, y)]


def build_split_iter_transfer(df: pd.DataFrame, train_scenario: str, test_scenario: str) -> list[tuple[np.ndarray, np.ndarray]]:
    train_idx = df.index[df["scenario_id"] == train_scenario].to_numpy(dtype=int)
    test_idx = df.index[df["scenario_id"] == test_scenario].to_numpy(dtype=int)
    return [(train_idx, test_idx)]


def main() -> int:
    args = parse_args()
    out_root: Path = args.out_root.resolve()
    ensure_dir(out_root)
    ensure_dir(out_root / "models")

    source_specs = args.source[:] if args.source else default_sources()
    sources = [load_source(spec) for spec in source_specs]
    if len(sources) < 1:
        raise RuntimeError("no valid sources")
    for src in sources:
        if not src.integrity["pass_expected_shape"]:
            if args.allow_auxiliary_sources:
                print(f"[warn] non-canonical shape for {src.path}: {src.integrity['rows']} rows, {src.integrity['unique_examples']} examples (allowed via --allow-auxiliary-sources)")
            else:
                raise RuntimeError(f"source failed expected shape checks: {src.path} -> {src.integrity}")

    inventory = {
        "created_by": str(Path(__file__).resolve()),
        "sources": [
            {
                "scenario_id": s.scenario_id,
                "provider": s.provider,
                "dataset": s.dataset,
                "path": str(s.path),
                "integrity": s.integrity,
            }
            for s in sources
        ],
    }
    write_json(out_root / "source_artifact_inventory.json", inventory)

    rows: list[dict[str, Any]] = []
    for src in sources:
        rows.extend(build_example_rows(src))
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("no example rows built")
    # deterministic column ordering for exported tables
    df = df.sort_values(["scenario_id", "example_id"]).reset_index(drop=True)

    # Write base dataset artifacts
    write_csv(out_root / "router_feature_table.csv", df.to_dict(orient="records"))
    label_cols = [
        "scenario_id",
        "provider",
        "dataset",
        "example_id",
        "seed",
        "budget",
        "frontier_correct",
        "L1_correct",
        "S1_correct",
        "TALE_correct",
        "pooled4_correct",
        "agreement_only_correct",
        "always_s1_correct",
        "dominant_source_action_correct",
        "oracle_best_source_correct",
        "oracle_best_action_correct",
    ]
    # dominant_source_action_correct is fold-defined; fill with NaN in base label table.
    label_df = df.copy()
    label_df["dominant_source_action_correct"] = np.nan
    write_csv(out_root / "router_label_table.csv", label_df[label_cols].to_dict(orient="records"), fieldnames=label_cols)
    write_jsonl(out_root / "router_combined_dataset.jsonl", df.to_dict(orient="records"))

    all_metrics: list[dict[str, Any]] = []
    all_preds: list[dict[str, Any]] = []
    all_calib: list[dict[str, Any]] = []
    all_fold_models: dict[str, Any] = {}

    scenario_ids = sorted(df["scenario_id"].unique().tolist())
    within_rows: list[dict[str, Any]] = []
    for scenario_id in scenario_ids:
        splits = build_split_iter_within(df, scenario_id, args.n_folds)
        metrics, preds, calib, fold_models = run_protocol(
            protocol=f"within_{scenario_id}",
            full_df=df,
            split_iter=splits,
            include_scenario_features=True,
            seed=args.random_seed,
        )
        within_rows.extend(metrics)
        all_metrics.extend(metrics)
        all_preds.extend(preds)
        all_calib.extend(calib)
        all_fold_models.update(fold_models)
    write_csv(out_root / "within_scenario_cv_summary.csv", within_rows)

    # Pooled stratified (with IDs and without IDs)
    pooled_splits = build_split_iter_pooled(df, args.n_folds, args.random_seed)
    pooled_rows_with, pooled_preds_with, pooled_calib_with, pooled_models_with = run_protocol(
        protocol="pooled_stratified_with_ids",
        full_df=df,
        split_iter=pooled_splits,
        include_scenario_features=True,
        seed=args.random_seed + 101,
    )
    pooled_rows_no, pooled_preds_no, pooled_calib_no, pooled_models_no = run_protocol(
        protocol="pooled_stratified_no_ids",
        full_df=df,
        split_iter=pooled_splits,
        include_scenario_features=False,
        seed=args.random_seed + 151,
    )
    pooled_rows = pooled_rows_with + pooled_rows_no
    write_csv(out_root / "pooled_stratified_cv_summary.csv", pooled_rows)
    all_metrics.extend(pooled_rows)
    all_preds.extend(pooled_preds_with + pooled_preds_no)
    all_calib.extend(pooled_calib_with + pooled_calib_no)
    all_fold_models.update(pooled_models_with)
    all_fold_models.update(pooled_models_no)

    # Cross-scenario transfer
    transfer_rows: list[dict[str, Any]] = []
    transfer_preds: list[dict[str, Any]] = []
    transfer_calib: list[dict[str, Any]] = []
    for train_s in scenario_ids:
        for test_s in scenario_ids:
            if train_s == test_s:
                continue
            metrics, preds, calib, fold_models = run_protocol(
                protocol=f"transfer_{train_s}_to_{test_s}",
                full_df=df,
                split_iter=build_split_iter_transfer(df, train_s, test_s),
                include_scenario_features=False,
                seed=args.random_seed + 301,
            )
            transfer_rows.extend(metrics)
            transfer_preds.extend(preds)
            transfer_calib.extend(calib)
            all_fold_models.update(fold_models)
    write_csv(out_root / "cross_scenario_transfer_summary.csv", transfer_rows)
    all_metrics.extend(transfer_rows)
    all_preds.extend(transfer_preds)
    all_calib.extend(transfer_calib)

    metrics_df = pd.DataFrame(all_metrics)
    preds_df = pd.DataFrame(all_preds)
    calib_df = pd.DataFrame(all_calib)
    write_csv(out_root / "all_router_eval_metrics.csv", metrics_df.to_dict(orient="records"))
    write_csv(out_root / "calibration_fold_stats.csv", calib_df.to_dict(orient="records"))
    write_csv(out_root / "case_level_router_predictions.csv", preds_df.to_dict(orient="records"))

    # Required model-summary slices
    if not metrics_df.empty:
        write_csv(
            out_root / "source_logistic_router_summary.csv",
            metrics_df[metrics_df["model_name"].astype(str).str.contains("source_logistic_router", na=False)].to_dict(orient="records"),
        )
        write_csv(
            out_root / "action_logistic_router_summary.csv",
            metrics_df[metrics_df["model_name"].astype(str).str.contains("action_logistic_router", na=False)].to_dict(orient="records"),
        )
        write_csv(
            out_root / "decision_tree_router_summary.csv",
            metrics_df[metrics_df["model_name"].astype(str).str.contains("action_tree_router", na=False)].to_dict(orient="records"),
        )
        write_csv(
            out_root / "gradient_boosting_router_summary.csv",
            metrics_df[metrics_df["model_name"].astype(str).str.contains("action_hgb_router", na=False)].to_dict(orient="records"),
        )
        baseline_mask = metrics_df["model_name"].isin(
            [
                "frontier",
                "L1",
                "S1",
                "TALE",
                "best_static_source_train_fold",
                "pooled4_with_fallback",
                "agreement_only_2of3_against_frontier",
                "raw_spread_regime_selector",
                "beta_shrinkage_regime_selector",
                "always_S1",
                "oracle_best_source",
                "oracle_best_action",
            ]
        )
        write_csv(out_root / "baseline_selector_summary.csv", metrics_df[baseline_mask].to_dict(orient="records"))

        # oracle regret summary
        keep_cols = [
            "protocol",
            "scenario_id",
            "model_name",
            "accuracy",
            "regret_to_best_static_source",
            "regret_to_oracle_best_source",
            "regret_to_oracle_best_action",
        ]
        write_csv(out_root / "oracle_regret_summary.csv", metrics_df[keep_cols].to_dict(orient="records"), fieldnames=keep_cols)

        # recovery/regression summary
        rr_cols = [
            "protocol",
            "scenario_id",
            "model_name",
            "recovery_vs_pooled4",
            "regression_vs_pooled4",
            "recovery_vs_best_static_source",
            "regression_vs_best_static_source",
            "win_vs_pooled4",
            "loss_vs_pooled4",
            "tie_vs_pooled4",
            "win_vs_always_s1",
            "loss_vs_always_s1",
            "tie_vs_always_s1",
        ]
        write_csv(out_root / "recovery_regression_summary.csv", metrics_df[rr_cols].to_dict(orient="records"), fieldnames=rr_cols)

        # calibration metrics summary
        cal_metrics = metrics_df[
            metrics_df["model_name"].astype(str).str.contains("router", na=False)
            & metrics_df["brier_score"].notna()
        ][["protocol", "scenario_id", "model_name", "accuracy", "brier_score", "ece_5bin"]]
        write_csv(out_root / "calibration_metrics_summary.csv", cal_metrics.to_dict(orient="records"))

    # Feature importance: fit final diagnostic models on all data using pooled calibration.
    cal_all = compute_calibration_stats(df)
    full_dyn = apply_dynamic_actions(df.copy(), cal_all)
    full_dyn = add_calibration_feature_columns(full_dyn, cal_all)
    X_all_with, num_cols, cat_cols = _build_feature_frame(full_dyn, include_scenario_features=True)
    feature_rows: list[dict[str, Any]] = []

    # final source logistic models
    final_source_models: dict[str, BaseEstimator] = {}
    for s in SOURCE_ORDER:
        y = full_dyn[f"{s}_correct"].to_numpy(dtype=int)
        final_source_models[s] = _fit_binary_classifier(
            X_all_with,
            y,
            model_type="logreg",
            seed=args.random_seed + 701,
            cat_cols=cat_cols,
            num_cols=num_cols,
        )
    feature_rows.extend(_collect_feature_importance("source_logistic_router_final", final_source_models, _extract_feature_names))

    # final action logistic/tree/hgb models
    action_label_map = {
        "choose_frontier": "frontier_correct",
        "choose_L1": "L1_correct",
        "choose_S1": "S1_correct",
        "choose_TALE": "TALE_correct",
        "pooled4_with_fallback": "pooled4_correct",
        "agreement_only_2of3_against_frontier": "agreement_only_correct",
        "raw_spread_regime_selector": "raw_spread_regime_selector_correct",
        "beta_shrinkage_regime_selector": "beta_shrinkage_regime_selector_correct",
    }
    final_action_log_models: dict[str, BaseEstimator] = {}
    final_action_tree_models: dict[str, BaseEstimator] = {}
    final_action_hgb_models: dict[str, BaseEstimator] = {}
    for action, label_col in action_label_map.items():
        y = full_dyn[label_col].to_numpy(dtype=int)
        final_action_log_models[action] = _fit_binary_classifier(
            X_all_with,
            y,
            model_type="logreg",
            seed=args.random_seed + 801,
            cat_cols=cat_cols,
            num_cols=num_cols,
        )
        final_action_tree_models[action] = _fit_binary_classifier(
            X_all_with,
            y,
            model_type="tree",
            seed=args.random_seed + 811,
            cat_cols=cat_cols,
            num_cols=num_cols,
            max_depth=3,
        )
        final_action_hgb_models[action] = _fit_binary_classifier(
            X_all_with,
            y,
            model_type="hgb",
            seed=args.random_seed + 821,
            cat_cols=cat_cols,
            num_cols=num_cols,
            max_depth=3,
        )
    feature_rows.extend(_collect_feature_importance("action_logistic_router_final", final_action_log_models, _extract_feature_names))
    feature_rows.extend(_collect_feature_importance("action_tree_router_final", final_action_tree_models, _extract_feature_names))
    feature_rows.extend(_collect_feature_importance("action_hgb_router_final", final_action_hgb_models, _extract_feature_names))
    write_csv(out_root / "feature_importance_summary.csv", feature_rows)

    # Save final diagnostic model bundle
    model_bundle = {
        "source_logistic_router_final": final_source_models,
        "action_logistic_router_final": final_action_log_models,
        "action_tree_router_final": final_action_tree_models,
        "action_hgb_router_final": final_action_hgb_models,
    }
    joblib.dump(model_bundle, out_root / "models" / "learned_fixed_pool_router_final_models.joblib")
    write_json(
        out_root / "models" / "learned_fixed_pool_router_model_metadata.json",
        {
            "note": "Diagnostic-only models trained on full combined dataset; not promotion evidence.",
            "actions": list(action_label_map.keys()),
            "sources": SOURCE_ORDER,
            "feature_columns_numeric": num_cols,
            "feature_columns_categorical": cat_cols,
            "calibration_stats_full_dataset": cal_all,
        },
    )

    # Failure analysis using pooled_stratified_with_ids action logistic predictions
    pooled_action = preds_df[
        (preds_df["protocol"] == "pooled_stratified_with_ids")
        & (preds_df["model_name"] == "action_logistic_router_with_ids")
    ].copy()
    pooled_baseline = preds_df[
        (preds_df["protocol"] == "pooled_stratified_with_ids")
        & (preds_df["model_name"] == "pooled4_with_fallback")
    ][["example_id", "selected_answer", "selected_correct"]].rename(
        columns={"selected_answer": "pooled4_answer_pred", "selected_correct": "pooled4_correct_pred"}
    )
    pooled_s1 = preds_df[
        (preds_df["protocol"] == "pooled_stratified_with_ids")
        & (preds_df["model_name"] == "S1")
    ][["example_id", "selected_answer", "selected_correct"]].rename(
        columns={"selected_answer": "s1_answer_pred", "selected_correct": "s1_correct_pred"}
    )
    merged_fail = pooled_action.merge(pooled_baseline, on="example_id", how="left").merge(pooled_s1, on="example_id", how="left")
    merged_fail = merged_fail.merge(
        df[
            [
                "example_id",
                "scenario_id",
                "question",
                "gold_answer",
                "frontier_answer",
                "L1_answer",
                "S1_answer",
                "TALE_answer",
                "pooled4_answer",
                "agreement_only_answer",
            ]
        ],
        on=["example_id", "scenario_id"],
        how="left",
    )
    failures = merged_fail[merged_fail["selected_correct"] == 0].copy()
    write_csv(out_root / "learned_router_failure_cases.csv", failures.to_dict(orient="records"))
    disag_pool = merged_fail[merged_fail["selected_answer"] != merged_fail["pooled4_answer_pred"]].copy()
    disag_s1 = merged_fail[merged_fail["selected_answer"] != merged_fail["s1_answer_pred"]].copy()
    write_csv(out_root / "router_vs_pooled4_disagreements.csv", disag_pool.to_dict(orient="records"))
    write_csv(out_root / "router_vs_s1_disagreements.csv", disag_s1.to_dict(orient="records"))

    casebook_lines = [
        "# Learned Router Failure Casebook",
        "",
        "Protocol: `pooled_stratified_with_ids`, model: `action_logistic_router_with_ids`.",
        "",
    ]
    for _, row in failures.head(40).iterrows():
        casebook_lines.extend(
            [
                f"## example_id={row['example_id']} scenario={row['scenario_id']}",
                f"- question: {row.get('question', '')}",
                f"- gold: {row.get('gold_answer', '')}",
                f"- router_action: {row.get('selected_action', '')}",
                f"- router_answer: {row.get('selected_answer', '')}",
                f"- pooled4_answer: {row.get('pooled4_answer_pred', '')}",
                f"- s1_answer: {row.get('s1_answer_pred', '')}",
                f"- frontier/L1/S1/TALE: {row.get('frontier_answer', '')} | {row.get('L1_answer', '')} | {row.get('S1_answer', '')} | {row.get('TALE_answer', '')}",
                "",
            ]
        )
    (out_root / "learned_router_failure_casebook.md").write_text("\n".join(casebook_lines), encoding="utf-8")

    # Write human-readable docs report
    top_tbl = metrics_df[
        metrics_df["scenario_id"].isin(["cohere_gsm8k", "mistral_gsm8k", "ALL_MACRO"])
        & metrics_df["model_name"].isin(
            [
                "action_logistic_router_with_ids",
                "action_logistic_router_no_ids",
                "source_logistic_router_with_ids",
                "source_logistic_router_no_ids",
                "pooled4_with_fallback",
                "S1",
                "beta_shrinkage_regime_selector",
                "raw_spread_regime_selector",
            ]
        )
    ].copy()
    top_tbl = top_tbl.sort_values(["protocol", "model_name", "scenario_id"])
    report_lines = [
        "# Learned Fixed-Pool Router Prototype (2026-05-24)",
        "",
        "This report documents an offline-only prototype learned router over `{frontier, L1, S1, TALE}`.",
        "",
        "## Sources Used",
        "",
    ]
    for s in sources:
        report_lines.append(f"- `{s.scenario_id}` | provider={s.provider} | dataset={s.dataset} | path=`{s.path}`")
        report_lines.append(
            f"  - integrity: rows={s.integrity['rows']}, unique_examples={s.integrity['unique_examples']}, "
            f"method_counts={s.integrity['method_counts']}, duplicates={s.integrity['duplicate_example_method_rows']}"
        )
    report_lines.extend(
        [
            "",
            "## Evaluation Scope",
            "",
            "- Within-scenario 5-fold CV for Cohere and Mistral GSM8K.",
            "- Pooled stratified 5-fold CV with and without scenario/provider IDs.",
            "- Cross-scenario transfer (`cohere -> mistral`, `mistral -> cohere`).",
            "- Results are prototype diagnostics only (2 scenarios total).",
            "",
            "## Selected Summary Rows",
            "",
        ]
    )
    if top_tbl.empty:
        report_lines.append("No summary rows available.")
    else:
        report_lines.append("| protocol | model_name | scenario_id | accuracy | regret_to_oracle_best_source |")
        report_lines.append("|---|---|---:|---:|---:|")
        for _, r in top_tbl.iterrows():
            report_lines.append(
                f"| {r.get('protocol','')} | {r.get('model_name','')} | {r.get('scenario_id','')} | "
                f"{float(r.get('accuracy',0.0)):.4f} | {float(r.get('regret_to_oracle_best_source', np.nan)):.4f} |"
            )
    report_lines.extend(
        [
            "",
            "## Important Limitations",
            "",
            "- Only two scenarios are available, so this can overfit provider/scenario patterns.",
            "- Cross-scenario transfer should be treated as stress-test only.",
            "- No promotion claim is made; this is diagnostic analysis.",
            "",
            "## Files",
            "",
            f"- Output root: `{out_root}`",
            f"- Source inventory: `{out_root / 'source_artifact_inventory.json'}`",
            f"- Metrics table: `{out_root / 'all_router_eval_metrics.csv'}`",
            f"- Case predictions: `{out_root / 'case_level_router_predictions.csv'}`",
            "",
        ]
    )
    ensure_dir(args.doc_path.parent)
    args.doc_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    # Manifest
    produced_files = sorted(str(p.relative_to(out_root)) for p in out_root.rglob("*") if p.is_file())
    manifest = {
        "timestamp_utc": pd.Timestamp.now("UTC").isoformat(),
        "script_path": str(Path(__file__).resolve()),
        "out_root": str(out_root),
        "source_artifacts": [
            {
                "scenario_id": s.scenario_id,
                "provider": s.provider,
                "dataset": s.dataset,
                "path": str(s.path),
                "integrity": s.integrity,
            }
            for s in sources
        ],
        "model_variants_trained": [
            "source_logistic_router",
            "action_logistic_router",
            "action_tree_router(depth in {2,3,4} by CV)",
            "action_hgb_router",
        ],
        "evaluation_protocols": [
            "within-scenario 5-fold CV",
            "pooled stratified 5-fold CV (with IDs)",
            "pooled stratified 5-fold CV (without IDs)",
            "cross-scenario transfer",
        ],
        "no_api_calls": True,
        "active_jobs_touched": False,
        "limitations": [
            "Two scenarios only (cohere_gsm8k, mistral_gsm8k).",
            "Prototype diagnostics; no policy promotion evidence.",
            "Potential provider/scenario lookup risk assessed via no-ID ablation.",
        ],
        "produced_files": produced_files,
    }
    write_json(out_root / "manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
