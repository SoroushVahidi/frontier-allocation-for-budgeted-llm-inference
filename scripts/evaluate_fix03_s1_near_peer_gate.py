#!/usr/bin/env python3
"""
Evaluate FIX-03: S1 near-peer gate (offline only).

Implements fold-safe calibration and FIX03a-f variants over completed
Cohere/Mistral artifacts only. No API calls.
"""

from __future__ import annotations

import datetime
import hashlib
import inspect
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "outputs" / "fix03_s1_near_peer_gate_20260524"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOC_PATH = REPO_ROOT / "docs" / "FIX03_S1_NEAR_PEER_GATE_20260524.md"

C1_UNIFIED = REPO_ROOT / "outputs" / "reliability_gated_pooled_voting_c1_20260524" / "c1_unified_case_table.csv"
WB_UNIFIED = REPO_ROOT / "outputs" / "failure_pattern_mining_workbench_20260524" / "failure_workbench_unified_cases.csv"
FIX01_OUT = REPO_ROOT / "outputs" / "fix01_strengthened_c1d_20260524"

SCENARIO_ORDER = ["cohere_gsm8k", "mistral_gsm8k", "mistral_math500", "cohere_math500_aux"]
OFFICIAL_SCENARIOS = ["cohere_gsm8k", "mistral_gsm8k", "mistral_math500"]
AUX_SCENARIOS = ["cohere_math500_aux"]
SOURCES = ["frontier", "L1", "S1", "TALE"]


@dataclass
class SourcePosterior:
    source: str
    n_total: int
    n_correct: int
    alpha: float
    beta: float
    mean: float
    var: float
    std: float
    lcb95: float
    ucb95: float


@dataclass
class Calibration:
    n_train: int
    posteriors: Dict[str, SourcePosterior]
    ranked: List[str]
    spread_best_second: float
    s1_minus_second: float
    best_source: str


def _seed_from_key(*parts) -> int:
    s = "||".join(map(str, parts))
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)


def _bool(v) -> bool:
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if pd.isna(v):
        return False
    if isinstance(v, (int, np.integer, float, np.floating)):
        return bool(int(v))
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


def _safe_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    s = str(v).strip()
    if s.lower() in {"nan", "none"}:
        return ""
    return s


def _answer_supported(row: pd.Series, ans: str, src: str = "S1") -> bool:
    if not ans:
        return False
    if _bool(row.get("all_four_agree")):
        return True
    if src == "S1" and _bool(row.get("S1_in_majority")):
        return True
    for s in SOURCES:
        if s == src:
            continue
        if _safe_str(row.get(f"{s}_ans")) == ans:
            return True
    return False


def choose_pooled4_answer(row: pd.Series) -> Tuple[str, str, str]:
    maj = _safe_str(row.get("majority_answer"))
    if _bool(row.get("has_majority")) and maj:
        return maj, "pooled4_majority", "majority"
    frontier = _safe_str(row.get("frontier_ans"))
    if frontier:
        return frontier, "frontier_fallback", "frontier"
    for s in SOURCES:
        a = _safe_str(row.get(f"{s}_ans"))
        if a:
            return a, f"{s.lower()}_fallback", s
    return "", "empty", "none"


def answer_to_correctness(row: pd.Series, answer: str) -> int:
    ans = _safe_str(answer)
    if ans:
        matched = []
        for src in SOURCES:
            if _safe_str(row.get(f"{src}_ans")) == ans:
                matched.append(int(row.get(f"{src}_ok", 0)))
        if matched:
            return int(max(matched))
    # gold usage only for offline evaluation fallback
    gold = _safe_str(row.get("gold"))
    if gold:
        return int(ans == gold)
    return 0


def beta_posterior_bounds(n_correct: int, n_total: int, alpha0: float = 1.0, beta0: float = 1.0, z: float = 1.96) -> SourcePosterior:
    alpha = alpha0 + n_correct
    beta = beta0 + (n_total - n_correct)
    mean = alpha / (alpha + beta)
    var = (alpha * beta) / (((alpha + beta) ** 2) * (alpha + beta + 1.0))
    std = math.sqrt(max(var, 0.0))
    lcb = max(0.0, mean - z * std)
    ucb = min(1.0, mean + z * std)
    return SourcePosterior(
        source="",
        n_total=n_total,
        n_correct=n_correct,
        alpha=alpha,
        beta=beta,
        mean=mean,
        var=var,
        std=std,
        lcb95=lcb,
        ucb95=ucb,
    )


def build_calibration(train_df: pd.DataFrame) -> Calibration:
    n = int(len(train_df))
    posteriors: Dict[str, SourcePosterior] = {}
    for src in SOURCES:
        n_ok = int(train_df[f"{src}_ok"].sum())
        p = beta_posterior_bounds(n_ok, n)
        p.source = src
        posteriors[src] = p

    ranked = sorted(SOURCES, key=lambda s: posteriors[s].mean, reverse=True)
    spread = posteriors[ranked[0]].mean - posteriors[ranked[1]].mean
    s1m = posteriors["S1"].mean - max(posteriors[s].mean for s in SOURCES if s != "S1")

    return Calibration(
        n_train=n,
        posteriors=posteriors,
        ranked=ranked,
        spread_best_second=spread,
        s1_minus_second=s1m,
        best_source=ranked[0],
    )


def near_peer(calib: Calibration, spread_thr: Optional[float] = None, s1_margin_thr: Optional[float] = None) -> bool:
    cond = False
    if spread_thr is not None:
        cond = cond or (calib.spread_best_second <= spread_thr)
    if s1_margin_thr is not None:
        cond = cond or (calib.s1_minus_second <= s1_margin_thr)
    return cond


def load_unified() -> Tuple[pd.DataFrame, Dict[str, object]]:
    if not C1_UNIFIED.exists():
        raise FileNotFoundError(f"Missing preferred input: {C1_UNIFIED}")
    if not WB_UNIFIED.exists():
        raise FileNotFoundError(f"Missing cross-check input: {WB_UNIFIED}")

    c1 = pd.read_csv(C1_UNIFIED)
    wb = pd.read_csv(WB_UNIFIED)

    expected = {
        "cohere_gsm8k": 300,
        "mistral_gsm8k": 300,
        "mistral_math500": 300,
        "cohere_math500_aux": 488,
    }

    merge_cols = [
        "scenario_id",
        "example_id",
        "c1_decision_c1a_t005",
        "c1_ok_c1a_t005",
        "c1_decision_c1d",
        "c1_ok_c1d",
        "beta_shrinkage_decision",
        "beta_shrinkage_decision_answer",
        "pooled4_decision",
        "pooled4_decision_answer",
        "agreement_only_decision",
        "agreement_only_decision_answer",
        "always_S1_decision",
        "always_S1_decision_answer",
        "C1d_decision",
    ]
    have_merge = [c for c in merge_cols if c in wb.columns]

    merged = c1.merge(wb[have_merge], on=["scenario_id", "example_id"], how="left")

    # Normalize bool/int flags (temporary; selector baseline flags are rebuilt below).
    for col in [
        "frontier_ok",
        "L1_ok",
        "S1_ok",
        "TALE_ok",
        "c1_ok_c1a_t005",
        "c1_ok_c1d",
        "all_four_agree",
        "three_one_split",
        "two_two_split",
        "all_different",
        "has_majority",
        "S1_in_majority",
        "S1_isolated",
        "frontier_isolated",
        "no_majority_flag",
    ]:
        if col in merged.columns:
            merged[col] = merged[col].map(_bool).astype(int)
        else:
            merged[col] = 0

    for col in ["pooled4_ok", "beta_shrinkage_ok", "agreement_only_ok", "always_S1_ok", "oracle_ok"]:
        if col not in merged.columns:
            merged[col] = np.nan

    for src in SOURCES:
        col = f"{src}_ans"
        if col not in merged.columns:
            merged[col] = ""
        merged[col] = merged[col].apply(_safe_str)

    for col in [
        "majority_answer",
        "gold",
        "question",
        "beta_shrinkage_decision_answer",
        "pooled4_decision_answer",
        "agreement_only_decision_answer",
        "always_S1_decision_answer",
        "c1_decision_c1d",
        "C1d_decision",
    ]:
        if col not in merged.columns:
            merged[col] = ""
        merged[col] = merged[col].apply(_safe_str)

    if "majority_size" not in merged.columns:
        merged["majority_size"] = 0
    merged["majority_size"] = pd.to_numeric(merged["majority_size"], errors="coerce").fillna(0).astype(int)

    # Reconstruct missing selector decision answers.
    def _recon_pooled(r: pd.Series) -> str:
        a, _, _ = choose_pooled4_answer(r)
        return a

    merged["pooled4_decision_answer"] = merged.apply(
        lambda r: _safe_str(r["pooled4_decision_answer"]) or _recon_pooled(r), axis=1
    )
    merged["agreement_only_decision_answer"] = merged.apply(
        lambda r: _safe_str(r["agreement_only_decision_answer"]) or _safe_str(r.get("pooled4_decision_answer")),
        axis=1,
    )
    merged["always_S1_decision_answer"] = merged.apply(
        lambda r: _safe_str(r["always_S1_decision_answer"]) or _safe_str(r.get("S1_ans")), axis=1
    )

    # Reconstruct beta answer if missing using scenario-level dominant-source style fallback.
    scen_stats = merged.groupby("scenario_id")[["frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]].mean()
    scen_best = {}
    for sid, row in scen_stats.iterrows():
        ranked = sorted(SOURCES, key=lambda s: float(row[f"{s}_ok"]), reverse=True)
        spread = float(row[f"{ranked[0]}_ok"] - row[f"{ranked[1]}_ok"])
        scen_best[sid] = (ranked[0], spread)

    def _recon_beta(r: pd.Series) -> str:
        sid = _safe_str(r.get("scenario_id"))
        best_src, spread = scen_best.get(sid, ("S1", 0.0))
        if spread >= 0.05:
            return _safe_str(r.get(f"{best_src}_ans"))
        return _safe_str(r.get("pooled4_decision_answer"))

    merged["beta_shrinkage_decision_answer"] = merged.apply(
        lambda r: _safe_str(r["beta_shrinkage_decision_answer"]) or _recon_beta(r), axis=1
    )

    merged["c1d_decision_answer"] = merged.apply(
        lambda r: _safe_str(r.get("c1_decision_c1d")) or _safe_str(r.get("C1d_decision")) or _safe_str(r.get("pooled4_decision_answer")),
        axis=1,
    )

    # Rebuild selector correctness flags from decision answers so missing source artifacts
    # do not get interpreted as incorrect.
    def _ok_from_answer(r: pd.Series, ans_col: str) -> int:
        ans = _safe_str(r.get(ans_col))
        if ans:
            matched = []
            for src in SOURCES:
                if _safe_str(r.get(f"{src}_ans")) == ans:
                    matched.append(int(r.get(f"{src}_ok", 0)))
            if matched:
                return int(max(matched))
        gold = _safe_str(r.get("gold"))
        if gold:
            return int(ans == gold)
        return 0

    merged["pooled4_ok"] = merged.apply(lambda r: _ok_from_answer(r, "pooled4_decision_answer"), axis=1).astype(int)
    merged["beta_shrinkage_ok"] = merged.apply(lambda r: _ok_from_answer(r, "beta_shrinkage_decision_answer"), axis=1).astype(int)
    merged["agreement_only_ok"] = merged.apply(lambda r: _ok_from_answer(r, "agreement_only_decision_answer"), axis=1).astype(int)
    merged["always_S1_ok"] = merged.apply(lambda r: _ok_from_answer(r, "always_S1_decision_answer"), axis=1).astype(int)
    merged["c1_ok_c1d"] = merged.apply(lambda r: _ok_from_answer(r, "c1d_decision_answer"), axis=1).astype(int)
    if "c1_decision_c1a_t005" in merged.columns:
        merged["c1_ok_c1a_t005"] = merged.apply(lambda r: _ok_from_answer(r, "c1_decision_c1a_t005"), axis=1).astype(int)
    else:
        merged["c1_ok_c1a_t005"] = merged["c1_ok_c1d"].astype(int)
    merged["oracle_ok"] = merged[[f"{s}_ok" for s in SOURCES]].max(axis=1).astype(int)

    merged["official_or_auxiliary"] = np.where(
        merged["scenario_id"].isin(OFFICIAL_SCENARIOS), "official", "auxiliary"
    )

    merged["n_sources_correct"] = (
        merged["frontier_ok"] + merged["L1_ok"] + merged["S1_ok"] + merged["TALE_ok"]
    )
    merged["all_sources_wrong"] = (merged["n_sources_correct"] == 0).astype(int)

    # Provide source chosen by base decisions.
    def _answer_source(r: pd.Series, ans_col: str) -> str:
        ans = _safe_str(r.get(ans_col))
        if not ans:
            return "none"
        # prefer exact source match order
        for s in SOURCES:
            if _safe_str(r.get(f"{s}_ans")) == ans:
                return s
        if _bool(r.get("has_majority")) and _safe_str(r.get("majority_answer")) == ans:
            return "majority"
        return "derived"

    merged["beta_source"] = merged.apply(lambda r: _answer_source(r, "beta_shrinkage_decision_answer"), axis=1)
    merged["c1d_source"] = merged.apply(lambda r: _answer_source(r, "c1d_decision_answer"), axis=1)

    # expected-count validation
    c1_counts = c1["scenario_id"].value_counts().to_dict()
    wb_counts = wb["scenario_id"].value_counts().to_dict()
    merged_counts = merged["scenario_id"].value_counts().to_dict()
    same_cases = (
        c1[["scenario_id", "example_id"]].drop_duplicates().shape[0]
        == wb[["scenario_id", "example_id"]].drop_duplicates().shape[0]
    )

    inventory = {
        "preferred_input": str(C1_UNIFIED),
        "crosscheck_input": str(WB_UNIFIED),
        "c1_rows": int(len(c1)),
        "wb_rows": int(len(wb)),
        "merged_rows": int(len(merged)),
        "c1_scenario_counts": c1_counts,
        "wb_scenario_counts": wb_counts,
        "merged_scenario_counts": merged_counts,
        "same_unique_case_pairs": bool(same_cases),
        "expected_counts": expected,
        "expected_count_match_c1": c1_counts == expected,
        "expected_count_match_wb": wb_counts == expected,
        "expected_count_match_merged": merged_counts == expected,
        "excluded_active_artifacts": [
            "outputs/cohere_math500_official_scenario4_20260524/ (active)",
            "outputs/mistral_large_router_training_gsm8k_20260524/ (active)",
            "outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/ (active)",
            "outputs/overnight_cerebras_supervisor_20260524/ (active)",
        ],
        "available_required_fields": {
            "source_answers": all(c in merged.columns for c in ["frontier_ans", "L1_ans", "S1_ans", "TALE_ans"]),
            "source_correctness": all(c in merged.columns for c in ["frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]),
            "pooled4_beta_c1d_flags": all(c in merged.columns for c in ["pooled4_ok", "beta_shrinkage_ok", "c1_ok_c1d"]),
            "answer_pattern_features": all(c in merged.columns for c in ["has_majority", "majority_size", "S1_isolated", "S1_in_majority", "all_four_agree", "no_majority_flag"]),
        },
    }

    with open(OUT_DIR / "source_artifact_inventory.json", "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2)

    rows = []
    for sid, n in merged["scenario_id"].value_counts().to_dict().items():
        rows.append({
            "scenario_id": sid,
            "n_rows": int(n),
            "official_or_auxiliary": merged.loc[merged["scenario_id"] == sid, "official_or_auxiliary"].iloc[0],
            "provider": merged.loc[merged["scenario_id"] == sid, "provider"].iloc[0],
            "dataset": merged.loc[merged["scenario_id"] == sid, "dataset"].iloc[0],
        })
    pd.DataFrame(rows).to_csv(OUT_DIR / "source_artifact_inventory.csv", index=False)

    merged.to_csv(OUT_DIR / "fix03_unified_case_table.csv", index=False)
    return merged, inventory


def infer_fix03(
    row: pd.Series,
    calib: Calibration,
    family: str,
    params: Dict,
) -> Dict[str, object]:
    pooled_ans, pooled_action, pooled_src = choose_pooled4_answer(row)
    majority_ans = _safe_str(row.get("majority_answer"))
    has_majority = _bool(row.get("has_majority"))
    s1_ans = _safe_str(row.get("S1_ans"))

    beta_ans = _safe_str(row.get("beta_shrinkage_decision_answer"))
    c1d_ans = _safe_str(row.get("c1d_decision_answer"))
    beta_selects_s1 = bool(beta_ans and s1_ans and beta_ans == s1_ans)
    c1d_selects_s1 = bool(c1d_ans and s1_ans and c1d_ans == s1_ans)
    s1_supported = _answer_supported(row, s1_ans, src="S1")
    s1_isolated = not s1_supported if s1_ans else False

    spread_thr = params.get("spread_thr")
    s1_margin_thr = params.get("s1_margin_thr")
    np_flag = near_peer(calib, spread_thr=spread_thr, s1_margin_thr=s1_margin_thr)
    dom_conf_low = calib.s1_minus_second <= params.get("dominance_conf_thr", 0.03)

    base = params.get("base", "beta")
    base_ans = beta_ans if base == "beta" else c1d_ans
    base_source = row.get("beta_source") if base == "beta" else row.get("c1d_source")

    selected_answer = base_ans
    selected_source = _safe_str(base_source)
    selected_action = f"{base}_keep"
    blocked_s1 = 0
    used_majority = 0

    if family == "fix03a":
        if beta_selects_s1 and (np_flag or dom_conf_low):
            selected_answer = pooled_ans
            selected_source = pooled_src
            selected_action = "blocked_s1_to_pooled4"
            blocked_s1 = 1
    elif family == "fix03b":
        base_selects_s1 = beta_selects_s1 if base == "beta" else c1d_selects_s1
        if base_selects_s1 and s1_isolated and np_flag and not _bool(row.get("S1_in_majority")) and not _bool(row.get("all_four_agree")):
            if has_majority and majority_ans:
                selected_answer = majority_ans
                selected_source = "majority"
                selected_action = "blocked_isolated_s1_to_majority"
                used_majority = 1
            else:
                selected_answer = pooled_ans
                selected_source = pooled_src
                selected_action = "blocked_isolated_s1_to_pooled4"
            blocked_s1 = 1
    elif family == "fix03c":
        if beta_selects_s1 and np_flag:
            allow = False
            if _bool(row.get("S1_in_majority")):
                allow = True
            elif _answer_supported(row, s1_ans, src="S1"):
                allow = True
            elif (not has_majority) and (calib.best_source == "S1") and (calib.s1_minus_second > params.get("allow_margin", 0.02)):
                allow = True
            if not allow:
                selected_answer = pooled_ans
                selected_source = pooled_src
                selected_action = "s1_support_required_block_to_pooled4"
                blocked_s1 = 1
    elif family == "fix03d":
        # Explicitly provider-free: same runtime logic, no provider/dataset condition.
        if beta_selects_s1 and s1_isolated and np_flag:
            selected_answer = pooled_ans
            selected_source = pooled_src
            selected_action = "provider_free_s1_block"
            blocked_s1 = 1
    elif family == "fix03e":
        # overtrust repair only: narrow activation
        if beta_selects_s1 and np_flag and (s1_isolated or not s1_supported):
            if has_majority and majority_ans:
                selected_answer = majority_ans
                selected_source = "majority"
                selected_action = "overtrust_repair_to_majority"
                used_majority = 1
            elif pooled_ans:
                selected_answer = pooled_ans
                selected_source = pooled_src
                selected_action = "overtrust_repair_to_pooled4"
            blocked_s1 = 1
    elif family == "fix03f":
        if c1d_selects_s1 and (not _bool(row.get("S1_in_majority"))) and (np_flag or dom_conf_low):
            selected_answer = pooled_ans
            selected_source = pooled_src
            selected_action = "c1d_hybrid_block_s1_to_pooled4"
            blocked_s1 = 1
    else:
        raise ValueError(f"Unknown family: {family}")

    return {
        "selected_answer": _safe_str(selected_answer),
        "selected_source": _safe_str(selected_source),
        "selected_action": selected_action,
        "blocked_s1": int(blocked_s1),
        "used_majority": int(used_majority),
        "near_peer": int(np_flag),
        "dominance_conf_low": int(dom_conf_low),
        "beta_selects_s1": int(beta_selects_s1),
        "c1d_selects_s1": int(c1d_selects_s1),
        "s1_supported": int(s1_supported),
        "s1_isolated": int(s1_isolated),
    }


def build_variant_grid() -> List[Dict[str, object]]:
    variants: List[Dict[str, object]] = []

    for t in [0.03, 0.05, 0.08, 0.10]:
        variants.append({
            "variant_name": f"fix03a_spread{int(t*100):02d}",
            "family": "fix03a",
            "params": {"spread_thr": t, "base": "beta", "dominance_conf_thr": 0.03},
        })
    for t in [0.03, 0.05, 0.08]:
        variants.append({
            "variant_name": f"fix03a_s1margin{int(t*100):02d}",
            "family": "fix03a",
            "params": {"s1_margin_thr": t, "base": "beta", "dominance_conf_thr": t},
        })

    for base in ["beta", "c1d"]:
        for t in [0.05, 0.08, 0.10]:
            variants.append({
                "variant_name": f"fix03b_{base}_np{int(t*100):02d}",
                "family": "fix03b",
                "params": {"base": base, "spread_thr": t},
            })

    for t in [0.05, 0.08, 0.10]:
        variants.append({
            "variant_name": f"fix03c_np{int(t*100):02d}",
            "family": "fix03c",
            "params": {"base": "beta", "spread_thr": t, "allow_margin": 0.02},
        })

    for t in [0.05, 0.08, 0.10]:
        variants.append({
            "variant_name": f"fix03d_providerfree_np{int(t*100):02d}",
            "family": "fix03d",
            "params": {"base": "beta", "spread_thr": t},
        })

    for t in [0.05, 0.08, 0.10]:
        variants.append({
            "variant_name": f"fix03e_overtrust_repair_np{int(t*100):02d}",
            "family": "fix03e",
            "params": {"base": "beta", "spread_thr": t},
        })

    for t in [0.05, 0.08, 0.10]:
        for c in [0.03, 0.05]:
            variants.append({
                "variant_name": f"fix03f_c1d_hybrid_np{int(t*100):02d}_conf{int(c*100):02d}",
                "family": "fix03f",
                "params": {"base": "c1d", "spread_thr": t, "dominance_conf_thr": c},
            })

    return variants


def kfold_indices(n: int, k: int = 5, seed: int = 42) -> List[Tuple[np.ndarray, np.ndarray]]:
    idx = list(range(n))
    rnd = random.Random(seed)
    rnd.shuffle(idx)
    folds = []
    base = n // k
    for i in range(k):
        s = i * base
        e = s + base if i < k - 1 else n
        test = np.array(idx[s:e], dtype=int)
        train = np.array(idx[:s] + idx[e:], dtype=int)
        folds.append((train, test))
    return folds


def stratified_kfold_indices(df: pd.DataFrame, k: int = 5, seed: int = 42) -> List[Tuple[np.ndarray, np.ndarray]]:
    by_scenario = {}
    rnd = random.Random(seed)
    for sid in sorted(df["scenario_id"].unique()):
        ids = df.index[df["scenario_id"] == sid].tolist()
        rnd.shuffle(ids)
        by_scenario[sid] = ids

    fold_tests: List[List[int]] = [[] for _ in range(k)]
    for _, ids in by_scenario.items():
        base = len(ids) // k
        for i in range(k):
            s = i * base
            e = s + base if i < k - 1 else len(ids)
            fold_tests[i].extend(ids[s:e])

    all_idx = set(df.index.tolist())
    folds = []
    for i in range(k):
        test = np.array(sorted(fold_tests[i]), dtype=int)
        train = np.array(sorted(all_idx - set(test.tolist())), dtype=int)
        folds.append((train, test))
    return folds


def evaluate_fold(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    protocol: str,
    fold_id: str,
    variant_grid: List[Dict[str, object]],
) -> Tuple[List[Dict], List[Dict]]:
    calib = build_calibration(train_df)

    eval_rows: List[Dict] = []
    pred_rows: List[Dict] = []

    baseline_ok_cols = {
        "pooled4": "pooled4_ok",
        "agreement_only": "agreement_only_ok",
        "always_S1": "always_S1_ok",
        "beta_shrinkage": "beta_shrinkage_ok",
        "C1d": "c1_ok_c1d",
        "C1a_t005": "c1_ok_c1a_t005",
        "oracle_best_source": "oracle_ok",
        "oracle_best_action": "oracle_ok",
    }

    for _, row in test_df.iterrows():
        sid = _safe_str(row.get("scenario_id"))
        for v in variant_grid:
            vname = v["variant_name"]
            family = v["family"]
            params = dict(v["params"])
            pred = infer_fix03(row, calib, family=family, params=params)
            ok = answer_to_correctness(row, pred["selected_answer"])

            pred_rows.append(
                {
                    "protocol": protocol,
                    "fold": fold_id,
                    "scenario_id": sid,
                    "provider": _safe_str(row.get("provider")),
                    "dataset": _safe_str(row.get("dataset")),
                    "official_or_auxiliary": _safe_str(row.get("official_or_auxiliary")),
                    "example_id": _safe_str(row.get("example_id")),
                    "variant": vname,
                    "family": family,
                    "selected_answer": pred["selected_answer"],
                    "selected_source": pred["selected_source"],
                    "selected_action": pred["selected_action"],
                    "variant_ok": int(ok),
                    "spread_best_second": float(calib.spread_best_second),
                    "s1_minus_second": float(calib.s1_minus_second),
                    "best_train_source": calib.best_source,
                    "near_peer": int(pred["near_peer"]),
                    "dominance_conf_low": int(pred["dominance_conf_low"]),
                    "blocked_s1": int(pred["blocked_s1"]),
                    "used_majority": int(pred["used_majority"]),
                    "beta_selects_s1": int(pred["beta_selects_s1"]),
                    "c1d_selects_s1": int(pred["c1d_selects_s1"]),
                    "s1_supported": int(pred["s1_supported"]),
                    "s1_isolated": int(pred["s1_isolated"]),
                    "pooled4_ok": int(row.get("pooled4_ok", 0)),
                    "beta_shrinkage_ok": int(row.get("beta_shrinkage_ok", 0)),
                    "c1d_ok": int(row.get("c1_ok_c1d", 0)),
                    "c1a_t005_ok": int(row.get("c1_ok_c1a_t005", 0)),
                    "always_S1_ok": int(row.get("always_S1_ok", 0)),
                    "agreement_only_ok": int(row.get("agreement_only_ok", 0)),
                    "oracle_ok": int(row.get("oracle_ok", 0)),
                    "frontier_ok": int(row.get("frontier_ok", 0)),
                    "L1_ok": int(row.get("L1_ok", 0)),
                    "S1_ok": int(row.get("S1_ok", 0)),
                    "TALE_ok": int(row.get("TALE_ok", 0)),
                    "all_sources_wrong": int(row.get("all_sources_wrong", 0)),
                    "has_majority": int(row.get("has_majority", 0)),
                    "majority_size": int(row.get("majority_size", 0)),
                    "S1_in_majority": int(row.get("S1_in_majority", 0)),
                    "S1_isolated_feature": int(row.get("S1_isolated", 0)),
                    "no_majority_flag": int(row.get("no_majority_flag", 0)),
                    "beta_shrinkage_decision_answer": _safe_str(row.get("beta_shrinkage_decision_answer")),
                    "c1d_decision_answer": _safe_str(row.get("c1d_decision_answer")),
                    "pooled4_decision_answer": _safe_str(row.get("pooled4_decision_answer")),
                    "frontier_ans": _safe_str(row.get("frontier_ans")),
                    "L1_ans": _safe_str(row.get("L1_ans")),
                    "S1_ans": _safe_str(row.get("S1_ans")),
                    "TALE_ans": _safe_str(row.get("TALE_ans")),
                    "majority_answer": _safe_str(row.get("majority_answer")),
                    "question": _safe_str(row.get("question")),
                    "gold": _safe_str(row.get("gold")),
                }
            )

    pred_df = pd.DataFrame(pred_rows)

    for vname, g in pred_df.groupby("variant"):
        eval_rows.append(
            {
                "protocol": protocol,
                "fold": fold_id,
                "selector": vname,
                "n": int(len(g)),
                "correct": int(g["variant_ok"].sum()),
                "accuracy": float(g["variant_ok"].mean()),
                "best_train_source": calib.best_source,
                "spread_best_second": float(calib.spread_best_second),
                "s1_minus_second": float(calib.s1_minus_second),
            }
        )

    for src in SOURCES:
        ok = test_df[f"{src}_ok"].astype(int)
        eval_rows.append(
            {
                "protocol": protocol,
                "fold": fold_id,
                "selector": src,
                "n": int(len(ok)),
                "correct": int(ok.sum()),
                "accuracy": float(ok.mean()),
                "best_train_source": calib.best_source,
                "spread_best_second": float(calib.spread_best_second),
                "s1_minus_second": float(calib.s1_minus_second),
            }
        )

    best_train_source = calib.best_source
    best_train_ok = test_df[f"{best_train_source}_ok"].astype(int)
    eval_rows.append(
        {
            "protocol": protocol,
            "fold": fold_id,
            "selector": "best_individual_source_trainfold",
            "n": int(len(best_train_ok)),
            "correct": int(best_train_ok.sum()),
            "accuracy": float(best_train_ok.mean()),
            "best_train_source": best_train_source,
            "spread_best_second": float(calib.spread_best_second),
            "s1_minus_second": float(calib.s1_minus_second),
        }
    )

    for sel, col in baseline_ok_cols.items():
        ok = test_df[col].astype(int)
        eval_rows.append(
            {
                "protocol": protocol,
                "fold": fold_id,
                "selector": sel,
                "n": int(len(ok)),
                "correct": int(ok.sum()),
                "accuracy": float(ok.mean()),
                "best_train_source": best_train_source,
                "spread_best_second": float(calib.spread_best_second),
                "s1_minus_second": float(calib.s1_minus_second),
            }
        )

    # Include best FIX01 as a baseline if available in this fold/protocol.
    if FIX01_OUT.exists():
        fix01_decision = FIX01_OUT / "fix01_candidate_decision_table.csv"
        if fix01_decision.exists():
            f1 = pd.read_csv(fix01_decision)
            if len(f1):
                best_fix01 = str(f1.iloc[0]["variant"])
                proto_map = {
                    "within_scenario_cv": "fix01_within_scenario_case_predictions.csv",
                    "official_pooled_cv": "fix01_official_pooled_case_predictions.csv",
                    "official_plus_aux_pooled_cv": "fix01_official_plus_aux_case_predictions.csv",
                    "leave_one_scenario_out": "fix01_loso_case_predictions.csv",
                    "full_artifact_diagnostic": "fix01_full_diagnostic_case_predictions.csv",
                }
                fp = FIX01_OUT / proto_map.get(protocol, "")
                if fp.exists():
                    fpred = pd.read_csv(fp)
                    sub = fpred[(fpred.get("variant", "") == best_fix01) & (fpred.get("fold", "") == fold_id)]
                    if len(sub):
                        ok = sub["variant_ok"].astype(int)
                        eval_rows.append(
                            {
                                "protocol": protocol,
                                "fold": fold_id,
                                "selector": "best_FIX01_variant",
                                "n": int(len(ok)),
                                "correct": int(ok.sum()),
                                "accuracy": float(ok.mean()),
                                "best_train_source": best_train_source,
                                "spread_best_second": float(calib.spread_best_second),
                                "s1_minus_second": float(calib.s1_minus_second),
                            }
                        )

    return eval_rows, pred_rows


def run_within_scenario_cv(df: pd.DataFrame, variant_grid: List[Dict[str, object]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    eval_all = []
    pred_all = []
    for sid in SCENARIO_ORDER:
        sdf = df[df["scenario_id"] == sid].reset_index(drop=True)
        folds = kfold_indices(len(sdf), k=5, seed=42)
        for i, (tr, te) in enumerate(folds):
            er, pr = evaluate_fold(sdf.iloc[tr], sdf.iloc[te], "within_scenario_cv", f"{sid}_fold{i}", variant_grid)
            eval_all.extend(er)
            pred_all.extend(pr)
    return pd.DataFrame(eval_all), pd.DataFrame(pred_all)


def run_pooled_cv(df: pd.DataFrame, variant_grid: List[Dict[str, object]], include_aux: bool) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if include_aux:
        pdf = df.copy().reset_index(drop=True)
        protocol = "official_plus_aux_pooled_cv"
    else:
        pdf = df[df["scenario_id"].isin(OFFICIAL_SCENARIOS)].copy().reset_index(drop=True)
        protocol = "official_pooled_cv"

    eval_all = []
    pred_all = []
    folds = stratified_kfold_indices(pdf, k=5, seed=42)
    for i, (tr, te) in enumerate(folds):
        er, pr = evaluate_fold(pdf.iloc[tr], pdf.iloc[te], protocol, f"fold{i}", variant_grid)
        eval_all.extend(er)
        pred_all.extend(pr)
    return pd.DataFrame(eval_all), pd.DataFrame(pred_all)


def run_loso(df: pd.DataFrame, variant_grid: List[Dict[str, object]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    eval_all = []
    pred_all = []
    for held in SCENARIO_ORDER:
        tr = df[df["scenario_id"] != held].reset_index(drop=True)
        te = df[df["scenario_id"] == held].reset_index(drop=True)
        er, pr = evaluate_fold(tr, te, "leave_one_scenario_out", f"heldout_{held}", variant_grid)
        eval_all.extend(er)
        pred_all.extend(pr)
    return pd.DataFrame(eval_all), pd.DataFrame(pred_all)


def run_full_diag(df: pd.DataFrame, variant_grid: List[Dict[str, object]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    eval_all = []
    pred_all = []
    for sid in SCENARIO_ORDER:
        sdf = df[df["scenario_id"] == sid].reset_index(drop=True)
        er, pr = evaluate_fold(sdf, sdf, "full_artifact_diagnostic", f"diag_{sid}", variant_grid)
        eval_all.extend(er)
        pred_all.extend(pr)
    return pd.DataFrame(eval_all), pd.DataFrame(pred_all)


def aggregate_eval(eval_df: pd.DataFrame) -> pd.DataFrame:
    out = eval_df.groupby(["protocol", "selector"], as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
    out["accuracy"] = out["correct"] / out["n"]
    return out


def pairwise_from_preds(pred_df: pd.DataFrame, variant: str, baseline_col: str) -> Dict[str, object]:
    v = pred_df[pred_df["variant"] == variant]
    if len(v) == 0:
        return {}
    a = v["variant_ok"].astype(int)
    b = v[baseline_col].astype(int)
    wins = int(((a == 1) & (b == 0)).sum())
    losses = int(((a == 0) & (b == 1)).sum())
    ties = int((a == b).sum())
    b_cnt = wins
    c_cnt = losses
    mcnemar_cc = ((abs(b_cnt - c_cnt) - 1) ** 2 / (b_cnt + c_cnt)) if (b_cnt + c_cnt) > 0 else 0.0
    return {
        "variant": variant,
        "baseline": baseline_col,
        "n": int(len(v)),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "net": wins - losses,
        "variant_acc": float(a.mean()),
        "baseline_acc": float(b.mean()),
        "delta": float(a.mean() - b.mean()),
        "mcnemar_stat_cc": float(mcnemar_cc),
    }


def bootstrap_ci_delta(a: np.ndarray, b: np.ndarray, n_boot: int = 2000, seed: int = 42) -> Tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    n = len(a)
    if n == 0:
        return 0.0, 0.0, 0.0
    deltas = []
    idx = np.arange(n)
    for _ in range(n_boot):
        s = rng.choice(idx, size=n, replace=True)
        deltas.append(float(a[s].mean() - b[s].mean()))
    arr = np.array(deltas)
    return float(arr.mean()), float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def build_candidate_decision(
    off_eval: pd.DataFrame,
    all_eval: pd.DataFrame,
    loso_eval: pd.DataFrame,
    off_preds: pd.DataFrame,
    variant_grid: List[Dict[str, object]],
) -> Tuple[pd.DataFrame, str]:
    var_names = [v["variant_name"] for v in variant_grid]

    def _map_acc(df: pd.DataFrame) -> Dict[str, float]:
        t = df.groupby("selector", as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
        t["acc"] = t["correct"] / t["n"]
        return {str(r["selector"]): float(r["acc"]) for _, r in t.iterrows()}

    off_map = _map_acc(off_eval)
    all_map = _map_acc(all_eval)

    loso_tmp = loso_eval.groupby(["fold", "selector"], as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
    loso_tmp["acc"] = loso_tmp["correct"] / loso_tmp["n"]

    rows = []
    for vname in var_names:
        vpred = off_preds[off_preds["variant"] == vname]
        if len(vpred) == 0:
            continue

        official_macro = off_map.get(vname, np.nan)
        all_macro = all_map.get(vname, np.nan)
        beta = off_map.get("beta_shrinkage", np.nan)
        c1d = off_map.get("C1d", np.nan)

        scen = vpred.groupby("scenario_id", as_index=False)["variant_ok"].mean()
        scen_off = scen[scen["scenario_id"].isin(OFFICIAL_SCENARIOS)]
        worst_off = float(scen_off["variant_ok"].min()) if len(scen_off) else np.nan

        v_loso = loso_tmp[loso_tmp["selector"] == vname]
        loso_min = float(v_loso["acc"].min()) if len(v_loso) else np.nan

        recover_overtrust = int(((vpred["variant_ok"] == 1) & (vpred["beta_shrinkage_ok"] == 0) & (vpred["beta_selects_s1"] == 1) & (vpred["near_peer"] == 1)).sum())
        regress_undertrust = int(((vpred["variant_ok"] == 0) & (vpred["beta_shrinkage_ok"] == 1) & (vpred["S1_ok"] == 1) & (vpred["beta_selects_s1"] == 1)).sum())
        near_peer_reg = int(((vpred["variant_ok"] == 0) & (vpred["beta_shrinkage_ok"] == 1) & (vpred["near_peer"] == 1)).sum())
        mistral_reg = int(((vpred["scenario_id"].str.startswith("mistral")) & (vpred["variant_ok"] == 0) & (vpred["beta_shrinkage_ok"] == 1) & (vpred["blocked_s1"] == 1)).sum())

        fam = vname.split("_")[0]
        if fam in {"fix03d", "fix03e"}:
            complexity = "low"
            overfit = "low"
        elif fam in {"fix03a", "fix03b", "fix03c"}:
            complexity = "medium"
            overfit = "low-medium"
        else:
            complexity = "medium"
            overfit = "medium"

        rec = "reject"
        d_beta = official_macro - beta
        d_c1d = official_macro - c1d
        if (d_beta >= 0.002) and (d_c1d >= 0.002) and (recover_overtrust > regress_undertrust):
            rec = "promote candidate"
        elif (d_beta >= -0.001) and (d_c1d >= -0.001):
            rec = "keep diagnostic"
        elif (official_macro >= beta - 0.002):
            rec = "wait for Cohere official Scenario 4"

        rows.append({
            "variant": vname,
            "official_macro_cv": official_macro,
            "official_plus_auxiliary_macro_cv": all_macro,
            "worst_official_scenario_acc": worst_off,
            "loso_min_acc": loso_min,
            "delta_vs_beta_shrinkage": official_macro - beta,
            "delta_vs_C1d": official_macro - c1d,
            "S1_overtrust_recoveries": recover_overtrust,
            "S1_undertrust_regressions": regress_undertrust,
            "near_peer_regressions": near_peer_reg,
            "mistral_dominant_regressions": mistral_reg,
            "near_peer_safety": "good" if near_peer_reg <= recover_overtrust else "risk",
            "mistral_preservation": "good" if mistral_reg <= 1 else "risk",
            "complexity": complexity,
            "overfitting_risk": overfit,
            "recommendation": rec,
        })

    cand = pd.DataFrame(rows).sort_values(
        ["official_macro_cv", "delta_vs_C1d", "S1_undertrust_regressions"],
        ascending=[False, False, True],
    )
    best = str(cand.iloc[0]["variant"]) if len(cand) else "none"
    return cand, best


def write_casebook(best_pred: pd.DataFrame):
    out = OUT_DIR

    overtrust_mask = (
        (best_pred["beta_selects_s1"] == 1)
        & ((best_pred["s1_isolated"] == 1) | (best_pred["s1_supported"] == 0))
        & (best_pred["near_peer"] == 1)
    )

    recoveries = best_pred[overtrust_mask & (best_pred["variant_ok"] == 1) & (best_pred["beta_shrinkage_ok"] == 0)].copy()
    misses = best_pred[overtrust_mask & (best_pred["variant_ok"] == 0) & (best_pred["beta_shrinkage_ok"] == 0)].copy()
    undertrust_reg = best_pred[(best_pred["S1_ok"] == 1) & (best_pred["beta_shrinkage_ok"] == 1) & (best_pred["variant_ok"] == 0)].copy()
    mistral_wrong_block = best_pred[(best_pred["scenario_id"].str.startswith("mistral")) & (best_pred["blocked_s1"] == 1) & (best_pred["S1_ok"] == 1) & (best_pred["variant_ok"] == 0)].copy()
    cohere_correct_block = best_pred[(best_pred["scenario_id"].str.startswith("cohere")) & (best_pred["blocked_s1"] == 1) & (best_pred["variant_ok"] == 1) & (best_pred["beta_shrinkage_ok"] == 0)].copy()
    pooled_wrong = best_pred[(best_pred["blocked_s1"] == 1) & (best_pred["selected_source"].isin(["majority", "frontier", "derived"])) & (best_pred["variant_ok"] == 0)].copy()
    isolated_s1_correct = best_pred[(best_pred["s1_isolated"] == 1) & (best_pred["S1_ok"] == 1)].copy()
    isolated_s1_wrong = best_pred[(best_pred["s1_isolated"] == 1) & (best_pred["S1_ok"] == 0)].copy()

    recoveries.to_csv(out / "fix03_s1_overtrust_recoveries.csv", index=False)
    misses.to_csv(out / "fix03_s1_overtrust_misses.csv", index=False)
    undertrust_reg.to_csv(out / "fix03_s1_undertrust_regressions.csv", index=False)
    mistral_wrong_block.to_csv(out / "fix03_mistral_s1_blocked_wrongly.csv", index=False)
    cohere_correct_block.to_csv(out / "fix03_cohere_s1_blocked_correctly.csv", index=False)
    isolated_s1_correct.to_csv(out / "fix03_isolated_s1_correct_cases.csv", index=False)
    isolated_s1_wrong.to_csv(out / "fix03_isolated_s1_wrong_cases.csv", index=False)

    with open(out / "fix03_best_variant_casebook.md", "w", encoding="utf-8") as f:
        f.write("# FIX-03 Best Variant Casebook\n\n")
        f.write("## S1-overtrusted cases fixed\n\n")
        for _, r in recoveries.head(40).iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} action={r['selected_action']}\n")

        f.write("\n## S1-overtrusted cases missed\n\n")
        for _, r in misses.head(40).iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} action={r['selected_action']}\n")

        f.write("\n## S1-undertrusted regressions introduced\n\n")
        for _, r in undertrust_reg.head(40).iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} action={r['selected_action']}\n")

        f.write("\n## Mistral cases where S1 should be selected but blocked\n\n")
        for _, r in mistral_wrong_block.head(40).iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} action={r['selected_action']}\n")

        f.write("\n## Cohere cases where S1 was correctly blocked\n\n")
        for _, r in cohere_correct_block.head(40).iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} action={r['selected_action']}\n")

        f.write("\n## Cases where pooled4 replacement was wrong\n\n")
        for _, r in pooled_wrong.head(40).iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} action={r['selected_action']}\n")

        f.write("\n## Cases where S1 was isolated and correct\n\n")
        for _, r in isolated_s1_correct.head(40).iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']}\n")

        f.write("\n## Cases where S1 was isolated and wrong\n\n")
        for _, r in isolated_s1_wrong.head(40).iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']}\n")

        f.write("\n## All-sources-wrong cases (non-fixable)\n\n")
        for _, r in best_pred[best_pred["all_sources_wrong"] == 1].head(40).iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']}\n")


def write_next_iteration(best_row: pd.Series):
    keep = "yes" if float(best_row.get("delta_vs_beta_shrinkage", -1.0)) >= 0 and float(best_row.get("delta_vs_C1d", -1.0)) >= 0 else "diagnostic_only"
    replace = "yes" if keep == "yes" and int(best_row.get("S1_undertrust_regressions", 999)) <= int(best_row.get("S1_overtrust_recoveries", 0)) else "no"
    rg_next = "conditional"
    wait = "yes"

    with open(OUT_DIR / "fix03_next_iteration_recommendations.md", "w", encoding="utf-8") as f:
        f.write("# FIX-03 Next Iteration Recommendations\n\n")
        f.write(f"- Should FIX-03 be kept? **{keep}**\n")
        f.write(f"- Should it replace beta-shrinkage/C1d? **{replace}**\n")
        f.write(f"- Should RG-EB-Action be next? **{rg_next}**\n")
        f.write(f"- Should we wait for official Cohere MATH-500 and Mistral train1000 first? **{wait}**\n")
        f.write("- Top remaining failure cluster: **near-peer non-majority disagreement with isolated S1 and mixed external reliability**\n")

    queue_rows = [
        {
            "priority": 1,
            "failure_cluster": "S1_overtrusted_in_near_peer",
            "action": "tighten support gate thresholds and pooled fallback routing",
            "status": "next",
        },
        {
            "priority": 2,
            "failure_cluster": "S1_undertrusted_in_mistral_dominant",
            "action": "preservation constraints in dominant-source regimes",
            "status": "next",
        },
        {
            "priority": 3,
            "failure_cluster": "No-majority mixed errors",
            "action": "RG-EB-Action diagnostic candidate",
            "status": "pending",
        },
        {
            "priority": 4,
            "failure_cluster": "Cross-provider transfer uncertainty",
            "action": "re-evaluate once Cohere official MATH-500 and train1000 complete",
            "status": "pending",
        },
    ]
    pd.DataFrame(queue_rows).to_csv(OUT_DIR / "fix03_updated_failure_driven_queue.csv", index=False)


def write_report(
    unified: pd.DataFrame,
    within_eval: pd.DataFrame,
    off_eval: pd.DataFrame,
    all_eval: pd.DataFrame,
    loso_eval: pd.DataFrame,
    pairwise_df: pd.DataFrame,
    cand_df: pd.DataFrame,
    best_variant: str,
):
    def _agg(df: pd.DataFrame) -> pd.DataFrame:
        t = df.groupby("selector", as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
        t["accuracy"] = t["correct"] / t["n"]
        return t.sort_values("accuracy", ascending=False)

    within_agg = _agg(within_eval)
    off_agg = _agg(off_eval)
    all_agg = _agg(all_eval)
    loso_agg = _agg(loso_eval)

    best_row = cand_df.iloc[0] if len(cand_df) else pd.Series(dtype=object)

    with open(DOC_PATH, "w", encoding="utf-8") as f:
        f.write("# FIX03_S1_NEAR_PEER_GATE_20260524\n\n")
        f.write("## 1. Executive summary\n")
        if len(cand_df):
            f.write(
                f"Best FIX-03 variant: `{best_variant}` with official pooled CV {best_row['official_macro_cv']:.4f}; "
                f"delta vs beta-shrinkage {best_row['delta_vs_beta_shrinkage']:+.4f}; "
                f"delta vs C1d {best_row['delta_vs_C1d']:+.4f}.\n\n"
            )
        else:
            f.write("No candidate variant results produced.\n\n")

        f.write("## 2. Data sources and caveats\n")
        f.write("Used completed offline artifacts only: Cohere GSM8K official, Mistral GSM8K official, Mistral MATH-500 official, Cohere MATH-500 auxiliary. Active Cohere official MATH-500 scenario4, Mistral train1000, Cerebras, and overnight supervisor artifacts were observed only and excluded.\n\n")

        f.write("## 3. FIX-03 variants\n")
        f.write("Implemented FIX03a-f families: near-peer S1 block, isolation gate, support-required gate, provider-free gate, overtrust-repair-only gate, and C1d-hybrid gate.\n\n")

        f.write("## 4. Evaluation protocol\n")
        f.write("Within-scenario 5-fold CV, official pooled stratified CV, official+aux pooled stratified CV, LOSO transfer, and full-artifact diagnostic (descriptive only).\n\n")

        f.write("## 5. Results by scenario\n")
        f.write(within_agg.head(25).to_string(index=False))
        f.write("\n\n")

        f.write("## 6. Official macro results\n")
        f.write(off_agg.head(25).to_string(index=False))
        f.write("\n\n")

        f.write("## 7. LOSO transfer results\n")
        f.write(loso_agg.head(25).to_string(index=False))
        f.write("\n\n")

        f.write("## 8. S1 overtrust/undertrust analysis\n")
        if len(cand_df):
            f.write(cand_df[[
                "variant",
                "S1_overtrust_recoveries",
                "S1_undertrust_regressions",
                "near_peer_regressions",
                "mistral_dominant_regressions",
            ]].head(25).to_string(index=False))
        else:
            f.write("No candidate rows.\n")
        f.write("\n\n")

        f.write("## 9. Failure/regression casebook\n")
        f.write("See `outputs/fix03_s1_near_peer_gate_20260524/fix03_best_variant_casebook.md` and companion CSV files.\n\n")

        f.write("## 10. Best variant decision\n")
        if len(cand_df):
            f.write(cand_df.head(25).to_string(index=False))
        else:
            f.write("No candidate rows.\n")
        f.write("\n\n")

        f.write("## 11. Manuscript implication\n")
        f.write("Treat FIX-03 as selector-level offline evidence; do not promote as final runtime policy unless superiority over beta-shrinkage and C1d is clear and stable on official data.\n\n")

        f.write("## 12. Next iteration recommendation\n")
        f.write("Prioritize residual near-peer disagreement clusters and reassess after official Cohere MATH-500 and train1000 completions.\n\n")

        f.write("## 13. Safety confirmation\n")
        f.write("Offline only. No API calls launched. No active job interference. No commit/push.\n")


def write_manifest(script_path: str):
    output_files = sorted([p.name for p in OUT_DIR.glob("*")])
    manifest = {
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_artifacts": [str(C1_UNIFIED), str(WB_UNIFIED)],
        "scripts_created": [script_path],
        "output_files": output_files,
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "limitations": [
            "Active Cohere official MATH-500 scenario4 excluded while active.",
            "Active Mistral train1000 corpus run excluded while active.",
            "Active Cerebras and overnight supervisor runs excluded while active.",
            "Auxiliary Cohere MATH-500 is noncanonical and reported separately.",
            "Full-artifact diagnostic is descriptive only (train=test).",
        ],
    }
    with open(OUT_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def main():
    print(f"[FIX03] start {datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")

    unified, _inventory = load_unified()
    print(f"[FIX03] unified rows: {len(unified)}")

    variant_grid = build_variant_grid()
    print(f"[FIX03] variants: {len(variant_grid)}")

    within_eval, within_preds = run_within_scenario_cv(unified, variant_grid)
    off_eval, off_preds = run_pooled_cv(unified, variant_grid, include_aux=False)
    all_eval, all_preds = run_pooled_cv(unified, variant_grid, include_aux=True)
    loso_eval, loso_preds = run_loso(unified, variant_grid)
    diag_eval, diag_preds = run_full_diag(unified, variant_grid)

    within_eval.to_csv(OUT_DIR / "fix03_within_scenario_cv_summary.csv", index=False)
    off_eval.to_csv(OUT_DIR / "fix03_official_pooled_cv_summary.csv", index=False)
    all_eval.to_csv(OUT_DIR / "fix03_official_plus_auxiliary_cv_summary.csv", index=False)
    loso_eval.to_csv(OUT_DIR / "fix03_leave_one_scenario_out_summary.csv", index=False)
    diag_eval.to_csv(OUT_DIR / "fix03_full_artifact_diagnostic_summary.csv", index=False)

    within_preds.to_csv(OUT_DIR / "fix03_within_scenario_case_predictions.csv", index=False)
    off_preds.to_csv(OUT_DIR / "fix03_official_pooled_case_predictions.csv", index=False)
    all_preds.to_csv(OUT_DIR / "fix03_official_plus_aux_case_predictions.csv", index=False)
    loso_preds.to_csv(OUT_DIR / "fix03_loso_case_predictions.csv", index=False)
    diag_preds.to_csv(OUT_DIR / "fix03_full_diagnostic_case_predictions.csv", index=False)

    # Pairwise.
    pairwise_rows = []
    for v in [x["variant_name"] for x in variant_grid]:
        for bcol in ["pooled4_ok", "beta_shrinkage_ok", "c1d_ok"]:
            r = pairwise_from_preds(off_preds, v, bcol)
            if r:
                pairwise_rows.append(r)
    pairwise_df = pd.DataFrame(pairwise_rows)
    pairwise_df.to_csv(OUT_DIR / "fix03_pairwise_win_loss_summary.csv", index=False)

    # Oracle regret.
    regret_rows = []
    off_agg = off_eval.groupby("selector", as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
    off_agg["accuracy"] = off_agg["correct"] / off_agg["n"]
    oracle_acc = float(off_agg.loc[off_agg["selector"] == "oracle_best_source", "accuracy"].iloc[0])
    for _, r in off_agg.iterrows():
        regret_rows.append({
            "selector": r["selector"],
            "official_pooled_acc": float(r["accuracy"]),
            "oracle_acc": oracle_acc,
            "regret_vs_oracle": float(oracle_acc - r["accuracy"]),
        })
    pd.DataFrame(regret_rows).to_csv(OUT_DIR / "fix03_oracle_regret_summary.csv", index=False)

    # Recovery/regression summary.
    rr_rows = []
    for v in [x["variant_name"] for x in variant_grid]:
        vpred = off_preds[off_preds["variant"] == v]
        if len(vpred) == 0:
            continue
        rec_beta = int(((vpred["variant_ok"] == 1) & (vpred["beta_shrinkage_ok"] == 0)).sum())
        reg_beta = int(((vpred["variant_ok"] == 0) & (vpred["beta_shrinkage_ok"] == 1)).sum())
        rec_c1d = int(((vpred["variant_ok"] == 1) & (vpred["c1d_ok"] == 0)).sum())
        reg_c1d = int(((vpred["variant_ok"] == 0) & (vpred["c1d_ok"] == 1)).sum())
        s1_over_rec = int(((vpred["variant_ok"] == 1) & (vpred["beta_shrinkage_ok"] == 0) & (vpred["beta_selects_s1"] == 1) & (vpred["near_peer"] == 1)).sum())
        s1_under_reg = int(((vpred["variant_ok"] == 0) & (vpred["beta_shrinkage_ok"] == 1) & (vpred["S1_ok"] == 1) & (vpred["beta_selects_s1"] == 1)).sum())
        np_reg = int(((vpred["variant_ok"] == 0) & (vpred["beta_shrinkage_ok"] == 1) & (vpred["near_peer"] == 1)).sum())
        mistral_dom_reg = int(((vpred["variant_ok"] == 0) & (vpred["beta_shrinkage_ok"] == 1) & (vpred["scenario_id"].str.startswith("mistral")) & (vpred["blocked_s1"] == 1)).sum())
        rr_rows.append({
            "variant": v,
            "recoveries_vs_beta": rec_beta,
            "regressions_vs_beta": reg_beta,
            "recoveries_vs_c1d": rec_c1d,
            "regressions_vs_c1d": reg_c1d,
            "S1_overtrust_recoveries": s1_over_rec,
            "S1_undertrust_regressions": s1_under_reg,
            "near_peer_regressions": np_reg,
            "mistral_dominant_regressions": mistral_dom_reg,
            "variant_acc": float(vpred["variant_ok"].mean()),
            "beta_acc": float(vpred["beta_shrinkage_ok"].mean()),
            "c1d_acc": float(vpred["c1d_ok"].mean()),
        })
    rr_df = pd.DataFrame(rr_rows)
    rr_df.to_csv(OUT_DIR / "fix03_recovery_regression_summary.csv", index=False)

    cand_df, best_variant = build_candidate_decision(off_eval, all_eval, loso_eval, off_preds, variant_grid)
    cand_df.to_csv(OUT_DIR / "fix03_candidate_decision_table.csv", index=False)

    with open(OUT_DIR / "fix03_candidate_decision.md", "w", encoding="utf-8") as f:
        f.write("# FIX-03 Candidate Decision\n\n")
        f.write(f"Best variant by official pooled CV: **{best_variant}**\n\n")
        if len(cand_df):
            f.write(cand_df.to_string(index=False))
        else:
            f.write("No candidate rows produced.\n")

    best_pred = off_preds[off_preds["variant"] == best_variant].copy()
    if len(best_pred):
        write_casebook(best_pred)

        # Bootstrap CIs (if easy) vs beta and c1d for best variant.
        ci_rows = []
        a = best_pred["variant_ok"].astype(int).to_numpy()
        for bcol, name in [("beta_shrinkage_ok", "beta_shrinkage"), ("c1d_ok", "C1d")]:
            b = best_pred[bcol].astype(int).to_numpy()
            mean, lo, hi = bootstrap_ci_delta(a, b, n_boot=2000, seed=42)
            ci_rows.append({"variant": best_variant, "baseline": name, "delta_mean": mean, "ci95_lo": lo, "ci95_hi": hi})
        pd.DataFrame(ci_rows).to_csv(OUT_DIR / "fix03_bootstrap_ci_summary.csv", index=False)

    if len(cand_df):
        write_next_iteration(cand_df.iloc[0])
    else:
        write_next_iteration(pd.Series(dtype=object))

    write_report(unified, within_eval, off_eval, all_eval, loso_eval, pairwise_df, cand_df, best_variant)
    write_manifest("scripts/evaluate_fix03_s1_near_peer_gate.py")

    print(f"[FIX03] done; best_variant={best_variant}")


if __name__ == "__main__":
    main()
