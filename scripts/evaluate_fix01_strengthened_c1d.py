#!/usr/bin/env python3
"""
Evaluate FIX-01: strengthened C1d with conservative dominance activation.

Offline-only evaluation over completed scenarios.
No API calls, no active job interaction.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "outputs" / "fix01_strengthened_c1d_20260524"
OUT_DIR.mkdir(parents=True, exist_ok=True)

C1_UNIFIED = REPO_ROOT / "outputs" / "reliability_gated_pooled_voting_c1_20260524" / "c1_unified_case_table.csv"
C1_ROUTER = REPO_ROOT / "outputs" / "reliability_gated_pooled_voting_c1_20260524" / "c1_router_augmented_feature_table.csv"
WB_UNIFIED = REPO_ROOT / "outputs" / "failure_pattern_mining_workbench_20260524" / "failure_workbench_unified_cases.csv"

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
    entropy_norm: float


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


def _seed_from_key(*parts) -> int:
    s = "||".join(map(str, parts))
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)


def load_unified() -> Tuple[pd.DataFrame, Dict[str, str]]:
    if not C1_UNIFIED.exists():
        raise FileNotFoundError(f"Missing input: {C1_UNIFIED}")
    if not C1_ROUTER.exists():
        raise FileNotFoundError(f"Missing input: {C1_ROUTER}")

    c1 = pd.read_csv(C1_UNIFIED)
    router = pd.read_csv(C1_ROUTER)

    # Cross-check with workbench table if available.
    cross = {}
    if WB_UNIFIED.exists():
        wb = pd.read_csv(WB_UNIFIED)
        cross = {
            "workbench_rows": int(len(wb)),
            "workbench_scenarios": wb["scenario_id"].value_counts().to_dict(),
            "same_case_pairs": bool(
                c1[["scenario_id", "example_id"]].drop_duplicates().shape[0]
                == wb[["scenario_id", "example_id"]].drop_duplicates().shape[0]
            ),
        }

    # Merge C1d/C1a_t005/c1 decisions into c1 base table.
    use_cols = [
        "scenario_id",
        "example_id",
        "c1_decision_c1a_t005",
        "c1_ok_c1a_t005",
        "c1_decision_c1d",
        "c1_ok_c1d",
    ]
    available = [c for c in use_cols if c in router.columns]
    merged = c1.merge(router[available], on=["scenario_id", "example_id"], how="left")

    # Add official/auxiliary label.
    merged["official_or_auxiliary"] = np.where(
        merged["scenario_id"].isin(OFFICIAL_SCENARIOS), "official", "auxiliary"
    )

    # Ensure bool/int columns.
    bool_cols = [
        "frontier_ok",
        "L1_ok",
        "S1_ok",
        "TALE_ok",
        "pooled4_ok",
        "beta_shrinkage_ok",
        "agreement_only_ok",
        "always_S1_ok",
        "oracle_ok",
        "c1_ok_c1a_t005",
        "c1_ok_c1d",
    ]
    for col in bool_cols:
        if col in merged.columns:
            merged[col] = merged[col].map(_bool).astype(int)
        else:
            merged[col] = 0

    # Basic derived fields.
    merged["n_sources_correct"] = (
        merged["frontier_ok"] + merged["L1_ok"] + merged["S1_ok"] + merged["TALE_ok"]
    )
    merged["all_sources_wrong"] = (merged["n_sources_correct"] == 0).astype(int)

    if "question" not in merged.columns:
        merged["question"] = ""

    for c in ["has_majority", "all_four_agree", "three_one_split", "two_two_split", "all_different", "S1_isolated", "frontier_isolated", "no_majority_flag"]:
        if c in merged.columns:
            merged[c] = merged[c].map(_bool).astype(int)
        else:
            merged[c] = 0

    if "majority_size" not in merged.columns:
        merged["majority_size"] = 0
    merged["majority_size"] = pd.to_numeric(merged["majority_size"], errors="coerce").fillna(0).astype(int)

    for src in SOURCES:
        ans_col = f"{src}_ans"
        if ans_col not in merged.columns:
            merged[ans_col] = ""
        merged[ans_col] = merged[ans_col].apply(_safe_str)

    merged["majority_answer"] = merged.get("majority_answer", "").apply(_safe_str)
    merged["gold"] = merged.get("gold", "").apply(_safe_str)

    # Reconstruct baseline correctness where a scenario has missing precomputed selector cols.
    def _ok_from_answer_local(r: pd.Series, ans: str) -> int:
        ans = _safe_str(ans)
        if ans:
            matched = []
            for s in SOURCES:
                if _safe_str(r.get(f"{s}_ans")) == ans:
                    matched.append(int(r.get(f"{s}_ok", 0)))
            if matched:
                return int(max(matched))
        gold = _safe_str(r.get("gold"))
        if gold:
            return int(ans == gold)
        return 0

    def _pooled4_ans_local(r: pd.Series) -> str:
        if _bool(r.get("has_majority")) and _safe_str(r.get("majority_answer")):
            return _safe_str(r.get("majority_answer"))
        return _safe_str(r.get("frontier_ans"))

    def _agreement_ans_local(r: pd.Series) -> str:
        frontier = _safe_str(r.get("frontier_ans"))
        ext = [_safe_str(r.get("L1_ans")), _safe_str(r.get("S1_ans")), _safe_str(r.get("TALE_ans"))]
        cnt = {}
        for a in ext:
            if a:
                cnt[a] = cnt.get(a, 0) + 1
        if cnt:
            top_ans = max(cnt.items(), key=lambda x: x[1])[0]
            if cnt[top_ans] >= 2 and top_ans != frontier:
                return top_ans
        return frontier

    # Scenario-level dominant source for beta reconstruction (near-peer -> pooled4).
    scen_stats = merged.groupby("scenario_id")[["frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]].mean()
    scen_best = {}
    for sid, row in scen_stats.iterrows():
        ranked = sorted(SOURCES, key=lambda s: float(row[f"{s}_ok"]), reverse=True)
        spread = float(row[f"{ranked[0]}_ok"] - row[f"{ranked[1]}_ok"])
        scen_best[sid] = {"best": ranked[0], "spread": spread}

    for sid in merged["scenario_id"].unique():
        sidx = merged["scenario_id"] == sid
        sub = merged.loc[sidx]
        # pooled4
        if int(sub["pooled4_ok"].sum()) == 0:
            pooled_ok = sub.apply(lambda r: _ok_from_answer_local(r, _pooled4_ans_local(r)), axis=1).astype(int)
            merged.loc[sidx, "pooled4_ok"] = pooled_ok.values
        # agreement
        if int(sub["agreement_only_ok"].sum()) == 0:
            agr_ok = sub.apply(lambda r: _ok_from_answer_local(r, _agreement_ans_local(r)), axis=1).astype(int)
            merged.loc[sidx, "agreement_only_ok"] = agr_ok.values
        # always S1
        if int(sub["always_S1_ok"].sum()) == 0:
            merged.loc[sidx, "always_S1_ok"] = sub["S1_ok"].astype(int).values
        # beta shrinkage (if absent): dominant-source if spread>=0.05 else pooled4
        if int(sub["beta_shrinkage_ok"].sum()) == 0:
            best = scen_best[sid]["best"]
            spread = scen_best[sid]["spread"]
            if spread >= 0.05:
                merged.loc[sidx, "beta_shrinkage_ok"] = sub[f"{best}_ok"].astype(int).values
            else:
                merged.loc[sidx, "beta_shrinkage_ok"] = merged.loc[sidx, "pooled4_ok"].astype(int).values

    # Inventory
    inventory = {
        "preferred_input": str(C1_UNIFIED),
        "secondary_crosscheck_input": str(WB_UNIFIED),
        "router_augmented_input": str(C1_ROUTER),
        "c1_rows": int(len(c1)),
        "c1_scenarios": c1["scenario_id"].value_counts().to_dict(),
        "merged_rows": int(len(merged)),
        "merged_scenarios": merged["scenario_id"].value_counts().to_dict(),
        "crosscheck": cross,
        "expected_counts": {
            "cohere_gsm8k": 300,
            "mistral_gsm8k": 300,
            "mistral_math500": 300,
            "cohere_math500_aux": 488,
        },
    }

    inv_json = OUT_DIR / "source_artifact_inventory.json"
    inv_csv = OUT_DIR / "source_artifact_inventory.csv"
    with open(inv_json, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2)

    rows = []
    for sid, n in merged["scenario_id"].value_counts().to_dict().items():
        rows.append(
            {
                "scenario_id": sid,
                "n_rows": int(n),
                "provider": merged.loc[merged["scenario_id"] == sid, "provider"].iloc[0],
                "dataset": merged.loc[merged["scenario_id"] == sid, "dataset"].iloc[0],
                "official_or_auxiliary": merged.loc[merged["scenario_id"] == sid, "official_or_auxiliary"].iloc[0],
            }
        )
    pd.DataFrame(rows).to_csv(inv_csv, index=False)

    merged.to_csv(OUT_DIR / "fix01_unified_case_table.csv", index=False)
    return merged, inventory


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
    probs = np.array([posteriors[s].mean for s in SOURCES], dtype=float)
    probs = probs / probs.sum() if probs.sum() > 0 else np.ones(len(SOURCES)) / len(SOURCES)
    ent = -float(np.sum(probs * np.log(probs + 1e-12))) / math.log(len(SOURCES))

    return Calibration(
        n_train=n,
        posteriors=posteriors,
        ranked=ranked,
        spread_best_second=spread,
        entropy_norm=ent,
    )


def choose_pooled4(row: pd.Series, calib: Calibration) -> Tuple[str, str, str]:
    maj = _safe_str(row.get("majority_answer"))
    has_maj = _bool(row.get("has_majority"))
    if has_maj and maj:
        return maj, "majority", "pooled4_majority"

    frontier = _safe_str(row.get("frontier_ans"))
    if frontier:
        return frontier, "frontier_fallback", "frontier"

    # fallback by calibration-ranked source availability
    for src in calib.ranked:
        ans = _safe_str(row.get(f"{src}_ans"))
        if ans:
            return ans, f"{src.lower()}_fallback", src
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

    gold = _safe_str(row.get("gold"))
    if gold:
        return int(ans == gold)
    return 0


def dominant_by_lcb_gap(calib: Calibration, delta_lcb: float) -> Optional[str]:
    best = None
    best_gap = -1e9
    for src in SOURCES:
        lcb = calib.posteriors[src].lcb95
        max_other_ucb = max(calib.posteriors[o].ucb95 for o in SOURCES if o != src)
        gap = lcb - max_other_ucb
        if gap > best_gap:
            best_gap = gap
            best = src
    if best is not None and best_gap >= delta_lcb:
        return best
    return None


def probability_of_dominance(calib: Calibration, src: str, delta: float, n_samples: int = 2000, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    samples = {}
    for s in SOURCES:
        p = calib.posteriors[s]
        samples[s] = rng.beta(p.alpha, p.beta, size=n_samples)

    cond = np.ones(n_samples, dtype=bool)
    for o in SOURCES:
        if o == src:
            continue
        cond &= samples[src] > (samples[o] + delta)
    return float(cond.mean())


def dominant_by_probability(calib: Calibration, tau: float, delta: float, seed: int) -> Optional[str]:
    best_src = None
    best_prob = -1.0
    for src in SOURCES:
        p = probability_of_dominance(calib, src, delta=delta, n_samples=2000, seed=seed + _seed_from_key(src))
        if p > best_prob:
            best_prob = p
            best_src = src
    if best_src is not None and best_prob >= tau:
        return best_src
    return None


def near_peer_safety_gate(calib: Calibration, spread_min: float, entropy_max: Optional[float] = None) -> bool:
    if calib.spread_best_second < spread_min:
        return False
    if entropy_max is not None and calib.entropy_norm > entropy_max:
        return False
    return True


def _weighted_vote_margin(row: pd.Series, calib: Calibration, majority_answer: str, dominant_answer: str) -> float:
    maj_w = 0.0
    dom_w = 0.0
    for src in SOURCES:
        w = calib.posteriors[src].mean
        ans = _safe_str(row.get(f"{src}_ans"))
        if ans == majority_answer:
            maj_w += w
        if ans == dominant_answer:
            dom_w += w
    return maj_w - dom_w


def strong_override_condition(row: pd.Series, calib: Calibration, dominant_src: str, override_margin: float) -> bool:
    has_maj = _bool(row.get("has_majority"))
    if not has_maj:
        return False

    majority_answer = _safe_str(row.get("majority_answer"))
    majority_size = int(row.get("majority_size", 0))

    if majority_size >= 3:
        return True

    if majority_size == 2:
        second_best = calib.ranked[1]
        second_ans = _safe_str(row.get(f"{second_best}_ans"))
        includes_second = second_ans == majority_answer
        dominant_ans = _safe_str(row.get(f"{dominant_src}_ans"))
        margin = _weighted_vote_margin(row, calib, majority_answer, dominant_ans)
        return bool(includes_second and margin >= override_margin)

    return False


def is_dominant_answer_isolated(row: pd.Series, dominant_src: str) -> bool:
    dom_ans = _safe_str(row.get(f"{dominant_src}_ans"))
    if not dom_ans:
        return False
    for s in SOURCES:
        if s == dominant_src:
            continue
        if _safe_str(row.get(f"{s}_ans")) == dom_ans:
            return False
    return True


def pattern_allows_override(row: pd.Series, dominant_src: str, lcb_gap_strength: float) -> bool:
    # Allowed:
    # - dominant isolated + strong
    # - all-different + strong
    # - 2-2 split with dominant included in a cluster
    # - weak majority-exclusion (majority_size==2 in no-majority framing)
    all_agree = _bool(row.get("all_four_agree"))
    if all_agree:
        return False

    has_maj = _bool(row.get("has_majority"))
    majority_size = int(row.get("majority_size", 0))

    if has_maj and majority_size >= 3 and lcb_gap_strength < 0.08:
        return False

    if is_dominant_answer_isolated(row, dominant_src) and lcb_gap_strength >= 0.02:
        return True

    if _bool(row.get("all_different")) and lcb_gap_strength >= 0.02:
        return True

    if _bool(row.get("two_two_split")):
        return True

    if (not has_maj) and majority_size == 2:
        return True

    return lcb_gap_strength >= 0.08


def infer_strengthened_c1d(
    row: pd.Series,
    calib: Calibration,
    variant: str,
    params: Dict,
    rng_seed: int,
) -> Dict:
    """
    Inference function for FIX-01 variants.
    Uses only runtime answer pattern + fold-safe calibration. No gold access.
    """
    pooled_ans, pooled_action, pooled_src = choose_pooled4(row, calib)

    dominant_src = None
    near_peer_blocked = False
    reason = ""

    if variant == "fix01a":
        dominant_src = params.get("_dominant_src", None)
        if "_dominant_src" not in params:
            dominant_src = dominant_by_lcb_gap(calib, params["delta_lcb"])
    elif variant == "fix01b":
        dominant_src = params.get("_dominant_src", None)
        if "_dominant_src" not in params:
            dominant_src = dominant_by_probability(calib, params["tau"], params["delta"], seed=rng_seed)
    elif variant == "fix01c":
        near_peer_blocked = bool(params.get("_near_peer_blocked", False))
        if near_peer_blocked:
            reason = "near_peer_safety_block"
        dominant_src = params.get("_dominant_src", None)
        if "_dominant_src" not in params:
            if near_peer_safety_gate(calib, params["spread_min"], entropy_max=params.get("entropy_max")):
                dominant_src = dominant_by_lcb_gap(calib, params.get("delta_lcb", 0.02))
            else:
                near_peer_blocked = True
                reason = "near_peer_safety_block"
    elif variant == "fix01d":
        near_peer_blocked = bool(params.get("_near_peer_blocked", False))
        if near_peer_blocked:
            reason = "near_peer_safety_block"
        dominant_src = params.get("_dominant_src", None)
        if "_dominant_src" not in params:
            if near_peer_safety_gate(calib, params.get("spread_min", 0.05), entropy_max=params.get("entropy_max")):
                dominant_src = dominant_by_lcb_gap(calib, params.get("delta_lcb", 0.02))
            else:
                near_peer_blocked = True
                reason = "near_peer_safety_block"
    elif variant == "fix01e":
        best = calib.ranked[0]
        second = calib.ranked[1]
        spread = calib.posteriors[best].mean - calib.posteriors[second].mean
        majority_ans = _safe_str(row.get("majority_answer"))
        best_ans = _safe_str(row.get(f"{best}_ans"))
        if spread >= params.get("spread_threshold", 0.08):
            if _bool(row.get("has_majority")) and majority_ans and best_ans and majority_ans != best_ans:
                return {
                    "selected_answer": best_ans,
                    "selected_source": best,
                    "selected_action": "fix01e_best_source_override",
                    "dominant_source": best,
                    "dominance_active": 1,
                    "override_passed": 0,
                    "override_rejected": 1,
                    "near_peer_blocked": 0,
                    "confidence": spread,
                    "reason": "best_minus_second_ge_8pp_and_majority_excludes_best",
                }
        return {
            "selected_answer": pooled_ans,
            "selected_source": pooled_src,
            "selected_action": "fix01e_pooled4",
            "dominant_source": best,
            "dominance_active": 0,
            "override_passed": 0,
            "override_rejected": 0,
            "near_peer_blocked": 0,
            "confidence": spread,
            "reason": "spread_below_threshold_or_majority_not_excluding_best",
        }
    else:
        raise ValueError(f"Unknown variant family: {variant}")

    if dominant_src is None:
        return {
            "selected_answer": pooled_ans,
            "selected_source": pooled_src,
            "selected_action": "pooled4_no_dominance",
            "dominant_source": "none",
            "dominance_active": 0,
            "override_passed": 0,
            "override_rejected": 0,
            "near_peer_blocked": int(near_peer_blocked),
            "confidence": calib.spread_best_second,
            "reason": reason or "no_confident_dominance",
        }

    dom_ans = _safe_str(row.get(f"{dominant_src}_ans"))
    majority_ans = _safe_str(row.get("majority_answer"))
    has_maj = _bool(row.get("has_majority"))

    if not dom_ans:
        return {
            "selected_answer": pooled_ans,
            "selected_source": pooled_src,
            "selected_action": "pooled4_missing_dominant_answer",
            "dominant_source": dominant_src,
            "dominance_active": 0,
            "override_passed": 0,
            "override_rejected": 0,
            "near_peer_blocked": int(near_peer_blocked),
            "confidence": calib.spread_best_second,
            "reason": "dominant_source_missing_answer",
        }

    if has_maj and majority_ans and dom_ans == majority_ans:
        return {
            "selected_answer": majority_ans,
            "selected_source": "majority",
            "selected_action": "majority_includes_dominant",
            "dominant_source": dominant_src,
            "dominance_active": 1,
            "override_passed": 0,
            "override_rejected": 0,
            "near_peer_blocked": int(near_peer_blocked),
            "confidence": calib.spread_best_second,
            "reason": "dominant_aligned_with_majority",
        }

    # majority excludes dominant (or no majority)
    override_passed = strong_override_condition(row, calib, dominant_src, params.get("override_margin", 0.05))

    if variant == "fix01d":
        gap_strength = calib.posteriors[dominant_src].lcb95 - max(
            calib.posteriors[s].ucb95 for s in SOURCES if s != dominant_src
        )
        if not pattern_allows_override(row, dominant_src, gap_strength):
            return {
                "selected_answer": pooled_ans,
                "selected_source": pooled_src,
                "selected_action": "pattern_blocks_dominance",
                "dominant_source": dominant_src,
                "dominance_active": 0,
                "override_passed": 0,
                "override_rejected": 1,
                "near_peer_blocked": int(near_peer_blocked),
                "confidence": gap_strength,
                "reason": "pattern_gate_block",
            }

    if override_passed and majority_ans:
        return {
            "selected_answer": majority_ans,
            "selected_source": "majority",
            "selected_action": "majority_override",
            "dominant_source": dominant_src,
            "dominance_active": 1,
            "override_passed": 1,
            "override_rejected": 0,
            "near_peer_blocked": int(near_peer_blocked),
            "confidence": calib.spread_best_second,
            "reason": "strong_override_condition_passed",
        }

    return {
        "selected_answer": dom_ans,
        "selected_source": dominant_src,
        "selected_action": "dominant_protect",
        "dominant_source": dominant_src,
        "dominance_active": 1,
        "override_passed": 0,
        "override_rejected": 1,
        "near_peer_blocked": int(near_peer_blocked),
        "confidence": calib.spread_best_second,
        "reason": "majority_excludes_dominant_or_no_majority",
    }


def build_variant_grid() -> List[Dict]:
    variants = []

    for delta_lcb in [0.00, 0.02, 0.03, 0.05]:
        for ov in [0.00, 0.03, 0.05, 0.08]:
            variants.append(
                {
                    "variant_name": f"fix01a_lcb{int(delta_lcb*100):02d}_ov{int(ov*100):02d}",
                    "family": "fix01a",
                    "params": {"delta_lcb": delta_lcb, "override_margin": ov},
                }
            )

    for tau in [0.75, 0.85, 0.90, 0.95]:
        for delta in [0.00, 0.02, 0.05]:
            variants.append(
                {
                    "variant_name": f"fix01b_tau{int(tau*100):02d}_d{int(delta*100):02d}",
                    "family": "fix01b",
                    "params": {"tau": tau, "delta": delta, "override_margin": 0.05},
                }
            )

    for spread_min in [0.03, 0.05, 0.08, 0.10]:
        variants.append(
            {
                "variant_name": f"fix01c_spread{int(spread_min*100):02d}",
                "family": "fix01c",
                "params": {"spread_min": spread_min, "delta_lcb": 0.02, "override_margin": 0.05, "entropy_max": 0.97},
            }
        )

    variants.append(
        {
            "variant_name": "fix01d_pattern_aware",
            "family": "fix01d",
            "params": {"spread_min": 0.05, "delta_lcb": 0.02, "override_margin": 0.05, "entropy_max": 0.97},
        }
    )

    variants.append(
        {
            "variant_name": "fix01e_minimal_safe",
            "family": "fix01e",
            "params": {"spread_threshold": 0.08},
        }
    )

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
    for sid, ids in by_scenario.items():
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


def row_best_train_source(row: pd.Series, best_src: str) -> int:
    return int(row.get(f"{best_src}_ok", 0))


def evaluate_fold(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    protocol: str,
    fold_id: str,
    variant_grid: List[Dict],
) -> Tuple[List[Dict], List[Dict]]:
    calib = build_calibration(train_df)

    # baseline best individual source from training fold
    best_train_source = calib.ranked[0]

    eval_rows: List[Dict] = []
    pred_rows: List[Dict] = []

    # Baseline selector columns as correctness vectors
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

    # Precompute fold-level dominance decisions per variant (training-only).
    variant_runtime = {}
    for v in variant_grid:
        params = dict(v["params"])
        family = v["family"]
        if family == "fix01a":
            params["_dominant_src"] = dominant_by_lcb_gap(calib, params["delta_lcb"])
        elif family == "fix01b":
            seed = _seed_from_key(protocol, fold_id, v["variant_name"], "fold_dominance")
            params["_dominant_src"] = dominant_by_probability(calib, params["tau"], params["delta"], seed=seed)
        elif family == "fix01c":
            gate = near_peer_safety_gate(calib, params["spread_min"], entropy_max=params.get("entropy_max"))
            params["_near_peer_blocked"] = not gate
            params["_dominant_src"] = dominant_by_lcb_gap(calib, params.get("delta_lcb", 0.02)) if gate else None
        elif family == "fix01d":
            gate = near_peer_safety_gate(calib, params.get("spread_min", 0.05), entropy_max=params.get("entropy_max"))
            params["_near_peer_blocked"] = not gate
            params["_dominant_src"] = dominant_by_lcb_gap(calib, params.get("delta_lcb", 0.02)) if gate else None
        variant_runtime[v["variant_name"]] = {"family": family, "params": params}

    # per-row inference for FIX-01 variants
    for _, row in test_df.iterrows():
        scenario_id = row["scenario_id"]
        for v in variant_grid:
            vname = v["variant_name"]
            family = variant_runtime[vname]["family"]
            runtime_params = variant_runtime[vname]["params"]
            seed = _seed_from_key(protocol, fold_id, scenario_id, row["example_id"], vname)
            pred = infer_strengthened_c1d(row, calib, family, runtime_params, rng_seed=seed)
            ok = answer_to_correctness(row, pred["selected_answer"])

            pred_rows.append(
                {
                    "protocol": protocol,
                    "fold": fold_id,
                    "scenario_id": scenario_id,
                    "provider": row["provider"],
                    "dataset": row["dataset"],
                    "official_or_auxiliary": row["official_or_auxiliary"],
                    "example_id": row["example_id"],
                    "variant": vname,
                    "selected_answer": pred["selected_answer"],
                    "selected_source": pred["selected_source"],
                    "selected_action": pred["selected_action"],
                    "variant_ok": int(ok),
                    "dominant_source": pred["dominant_source"],
                    "dominance_active": int(pred["dominance_active"]),
                    "override_passed": int(pred["override_passed"]),
                    "override_rejected": int(pred["override_rejected"]),
                    "near_peer_blocked": int(pred["near_peer_blocked"]),
                    "confidence": float(pred["confidence"]),
                    "reason": pred["reason"],
                    "spread_best_second": float(calib.spread_best_second),
                    "entropy_norm": float(calib.entropy_norm),
                    "best_train_source": best_train_source,
                    "pooled4_ok": int(row.get("pooled4_ok", 0)),
                    "beta_shrinkage_ok": int(row.get("beta_shrinkage_ok", 0)),
                    "c1d_ok": int(row.get("c1_ok_c1d", 0)),
                    "all_sources_wrong": int(row.get("all_sources_wrong", 0)),
                    "no_majority_flag": int(row.get("no_majority_flag", 0)),
                    "S1_ok": int(row.get("S1_ok", 0)),
                    "frontier_ok": int(row.get("frontier_ok", 0)),
                    "L1_ok": int(row.get("L1_ok", 0)),
                    "TALE_ok": int(row.get("TALE_ok", 0)),
                    "majority_size": int(row.get("majority_size", 0)),
                    "has_majority": int(row.get("has_majority", 0)),
                    "question": _safe_str(row.get("question", "")),
                    "gold": _safe_str(row.get("gold", "")),
                    "frontier_ans": _safe_str(row.get("frontier_ans", "")),
                    "L1_ans": _safe_str(row.get("L1_ans", "")),
                    "S1_ans": _safe_str(row.get("S1_ans", "")),
                    "TALE_ans": _safe_str(row.get("TALE_ans", "")),
                    "majority_answer": _safe_str(row.get("majority_answer", "")),
                }
            )

    pred_df = pd.DataFrame(pred_rows)

    # Variant accuracies
    for vname, g in pred_df.groupby("variant"):
        eval_rows.append(
            {
                "protocol": protocol,
                "fold": fold_id,
                "selector": vname,
                "n": int(len(g)),
                "correct": int(g["variant_ok"].sum()),
                "accuracy": float(g["variant_ok"].mean()),
                "best_train_source": best_train_source,
                "spread_best_second": float(calib.spread_best_second),
                "entropy_norm": float(calib.entropy_norm),
            }
        )

    # Baselines and source-level
    for src in SOURCES:
        col = f"{src}_ok"
        ok = test_df[col].astype(int)
        eval_rows.append(
            {
                "protocol": protocol,
                "fold": fold_id,
                "selector": src,
                "n": int(len(ok)),
                "correct": int(ok.sum()),
                "accuracy": float(ok.mean()),
                "best_train_source": best_train_source,
                "spread_best_second": float(calib.spread_best_second),
                "entropy_norm": float(calib.entropy_norm),
            }
        )

    best_train_ok = test_df.apply(lambda r: row_best_train_source(r, best_train_source), axis=1).astype(int)
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
            "entropy_norm": float(calib.entropy_norm),
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
                "entropy_norm": float(calib.entropy_norm),
            }
        )

    return eval_rows, pred_rows


def run_within_scenario_cv(df: pd.DataFrame, variant_grid: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    eval_all = []
    pred_all = []

    for sid in SCENARIO_ORDER:
        sdf = df[df["scenario_id"] == sid].reset_index(drop=True)
        folds = kfold_indices(len(sdf), k=5, seed=42)
        for i, (tr, te) in enumerate(folds):
            eval_rows, pred_rows = evaluate_fold(sdf.iloc[tr], sdf.iloc[te], protocol="within_scenario_cv", fold_id=f"{sid}_fold{i}", variant_grid=variant_grid)
            eval_all.extend(eval_rows)
            pred_all.extend(pred_rows)

    return pd.DataFrame(eval_all), pd.DataFrame(pred_all)


def run_pooled_cv(df: pd.DataFrame, variant_grid: List[Dict], include_aux: bool) -> Tuple[pd.DataFrame, pd.DataFrame]:
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
        eval_rows, pred_rows = evaluate_fold(pdf.iloc[tr], pdf.iloc[te], protocol=protocol, fold_id=f"fold{i}", variant_grid=variant_grid)
        eval_all.extend(eval_rows)
        pred_all.extend(pred_rows)

    return pd.DataFrame(eval_all), pd.DataFrame(pred_all)


def run_loso(df: pd.DataFrame, variant_grid: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    eval_all = []
    pred_all = []
    for held in SCENARIO_ORDER:
        train = df[df["scenario_id"] != held].copy().reset_index(drop=True)
        test = df[df["scenario_id"] == held].copy().reset_index(drop=True)
        eval_rows, pred_rows = evaluate_fold(train, test, protocol="leave_one_scenario_out", fold_id=f"heldout_{held}", variant_grid=variant_grid)
        eval_all.extend(eval_rows)
        pred_all.extend(pred_rows)
    return pd.DataFrame(eval_all), pd.DataFrame(pred_all)


def run_full_diagnostic(df: pd.DataFrame, variant_grid: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    eval_all = []
    pred_all = []
    for sid in SCENARIO_ORDER:
        sdf = df[df["scenario_id"] == sid].copy().reset_index(drop=True)
        eval_rows, pred_rows = evaluate_fold(sdf, sdf, protocol="full_artifact_diagnostic", fold_id=f"diag_{sid}", variant_grid=variant_grid)
        eval_all.extend(eval_rows)
        pred_all.extend(pred_rows)
    return pd.DataFrame(eval_all), pd.DataFrame(pred_all)


def summarize_selector_accuracy(eval_df: pd.DataFrame, protocol: str) -> pd.DataFrame:
    sdf = eval_df[eval_df["protocol"] == protocol].copy()
    grp = sdf.groupby(["selector"], as_index=False).agg(
        n=("n", "sum"),
        correct=("correct", "sum"),
        accuracy=("correct", lambda s: float(s.sum()) / max(int(sdf[sdf["selector"] == sdf.loc[s.index[0], "selector"]]["n"].sum()), 1)),
    )
    # recompute robustly
    tmp = sdf.groupby("selector", as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
    tmp["accuracy"] = tmp["correct"] / tmp["n"]
    tmp["protocol"] = protocol
    return tmp[["protocol", "selector", "n", "correct", "accuracy"]]


def summarize_macro_by_scenario(eval_df: pd.DataFrame, protocol: str) -> pd.DataFrame:
    # Build from per-case predictions where available for variants; for baselines from fold eval rows.
    sdf = eval_df[eval_df["protocol"] == protocol].copy()
    out = sdf.groupby("selector", as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
    out["accuracy"] = out["correct"] / out["n"]
    out["protocol"] = protocol
    return out[["protocol", "selector", "n", "correct", "accuracy"]]


def pairwise_from_preds(pred_df: pd.DataFrame, variant: str, baseline_col: str) -> Dict:
    v = pred_df[pred_df["variant"] == variant].copy()
    if len(v) == 0:
        return {}

    a = v["variant_ok"].astype(int)
    b = v[baseline_col].astype(int)
    wins = int(((a == 1) & (b == 0)).sum())
    losses = int(((a == 0) & (b == 1)).sum())
    ties = int((a == b).sum())
    n = int(len(v))
    b_cnt = wins
    c_cnt = losses
    mcnemar = ((abs(b_cnt - c_cnt) - 1) ** 2 / (b_cnt + c_cnt)) if (b_cnt + c_cnt) > 0 else 0.0
    return {
        "variant": variant,
        "baseline": baseline_col,
        "n": n,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "net": wins - losses,
        "variant_acc": float(a.mean()),
        "baseline_acc": float(b.mean()),
        "delta": float(a.mean() - b.mean()),
        "mcnemar_stat_cc": float(mcnemar),
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
    deltas = np.array(deltas)
    return float(np.mean(deltas)), float(np.quantile(deltas, 0.025)), float(np.quantile(deltas, 0.975))


def build_candidate_table(
    eval_official: pd.DataFrame,
    eval_official_aux: pd.DataFrame,
    loso_eval: pd.DataFrame,
    pred_official: pd.DataFrame,
    variant_grid: List[Dict],
) -> Tuple[pd.DataFrame, str]:
    var_names = [v["variant_name"] for v in variant_grid]

    # Helper map accuracy
    def _acc_map(df):
        m = {}
        tmp = df.groupby("selector", as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
        tmp["acc"] = tmp["correct"] / tmp["n"]
        for _, r in tmp.iterrows():
            m[r["selector"]] = float(r["acc"])
        return m

    off_map = _acc_map(eval_official)
    all_map = _acc_map(eval_official_aux)

    # LOSO stability: min across held-out folds
    loso_tmp = loso_eval.groupby(["fold", "selector"], as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
    loso_tmp["acc"] = loso_tmp["correct"] / loso_tmp["n"]

    rows = []

    for vname in var_names:
        vpred = pred_official[pred_official["variant"] == vname].copy()
        if len(vpred) == 0:
            continue

        official_macro = off_map.get(vname, np.nan)
        all_macro = all_map.get(vname, np.nan)
        beta = off_map.get("beta_shrinkage", np.nan)
        c1d = off_map.get("C1d", np.nan)

        # worst official scenario from row-level preds
        scen = vpred.groupby("scenario_id", as_index=False)["variant_ok"].mean()
        scen_off = scen[scen["scenario_id"].isin(OFFICIAL_SCENARIOS)]
        worst_off = float(scen_off["variant_ok"].min()) if len(scen_off) else np.nan

        # loso stability
        v_loso = loso_tmp[loso_tmp["selector"] == vname]
        loso_min = float(v_loso["acc"].min()) if len(v_loso) else np.nan

        false_dom = int(((vpred["dominance_active"] == 1) & (vpred["spread_best_second"] < 0.05) & (vpred["variant_ok"] == 0)).sum())

        missed_dom = int(((vpred["S1_ok"] == 1) & (vpred["pooled4_ok"] == 0) & (vpred["variant_ok"] == 0)).sum())

        # complexity/overfit heuristic
        family = vname.split("_")[0]
        if family in {"fix01d", "fix01e"}:
            complexity = "low"
            overfit_risk = "low"
        elif family == "fix01c":
            complexity = "medium"
            overfit_risk = "low-medium"
        elif family == "fix01a":
            complexity = "medium"
            overfit_risk = "medium"
        else:
            complexity = "medium-high"
            overfit_risk = "medium-high"

        # Recommendation
        if (official_macro >= beta) and (official_macro >= c1d) and false_dom <= 5:
            rec = "promote candidate"
        elif (official_macro >= c1d - 0.002):
            rec = "keep diagnostic"
        else:
            rec = "reject"

        rows.append(
            {
                "variant": vname,
                "official_macro_cv": official_macro,
                "official_plus_auxiliary_macro_cv": all_macro,
                "worst_official_scenario_acc": worst_off,
                "loso_min_acc": loso_min,
                "delta_vs_beta_shrinkage": official_macro - beta,
                "delta_vs_C1d": official_macro - c1d,
                "false_dominance_activations": false_dom,
                "missed_dominance_recoveries": missed_dom,
                "complexity": complexity,
                "overfitting_risk": overfit_risk,
                "recommendation": rec,
            }
        )

    out = pd.DataFrame(rows).sort_values(
        ["official_macro_cv", "delta_vs_C1d", "false_dominance_activations"],
        ascending=[False, False, True],
    )

    best_variant = out.iloc[0]["variant"] if len(out) else "none"
    return out, best_variant


def write_candidate_decision_md(df: pd.DataFrame, best_variant: str):
    out_md = OUT_DIR / "fix01_candidate_decision.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# FIX-01 Candidate Decision\n\n")
        f.write(f"Best variant by official pooled CV: **{best_variant}**\n\n")
        f.write("## Ranked Variants\n\n")
        f.write(df.to_string(index=False))
        f.write("\n")


def write_next_iteration(best_variant: str, best_row: pd.Series):
    md = OUT_DIR / "fix01_next_iteration_recommendations.md"
    qcsv = OUT_DIR / "fix01_updated_failure_driven_queue.csv"

    should_keep_fix01 = "yes" if best_row["delta_vs_C1d"] >= -0.001 else "no"
    implement_fix03_next = "yes" if best_row["false_dominance_activations"] > 0 else "conditional"
    implement_rgeb_next = "wait_for_cerebras"
    wait_cohere_s4 = "yes"

    with open(md, "w", encoding="utf-8") as f:
        f.write("# FIX-01 Next Iteration Recommendations\n\n")
        f.write(f"- keep FIX-01: **{should_keep_fix01}**\n")
        f.write(f"- implement FIX-03 (S1 near-peer gate) next: **{implement_fix03_next}**\n")
        f.write(f"- implement RG-EB-Action next: **{implement_rgeb_next}**\n")
        f.write(f"- wait for Cohere official Scenario 4 before final decision: **{wait_cohere_s4}**\n")

    queue_rows = [
        {
            "priority": 1,
            "item": f"Deepen {best_variant} threshold tuning",
            "why": "Best official macro and direct comparison vs beta/C1d",
            "depends_on": "none",
            "status": "next",
        },
        {
            "priority": 2,
            "item": "Implement FIX-03 near-peer S1 gate",
            "why": "Reduce false dominance / S1 overtrust in near-peer slices",
            "depends_on": "FIX-01 regression audit",
            "status": "next",
        },
        {
            "priority": 3,
            "item": "Re-evaluate after Cohere official Scenario 4 completion",
            "why": "Current Cohere MATH is auxiliary only",
            "depends_on": "active job completion",
            "status": "pending",
        },
        {
            "priority": 4,
            "item": "Re-evaluate after Cerebras completion",
            "why": "Cross-provider robustness for promotion decision",
            "depends_on": "active job completion",
            "status": "pending",
        },
        {
            "priority": 5,
            "item": "RG-EB-Action table",
            "why": "Needs richer cross-scenario support",
            "depends_on": "Cerebras + Cohere official MATH",
            "status": "pending",
        },
    ]
    pd.DataFrame(queue_rows).to_csv(qcsv, index=False)


def build_report(
    unified: pd.DataFrame,
    within_eval: pd.DataFrame,
    off_eval: pd.DataFrame,
    all_eval: pd.DataFrame,
    loso_eval: pd.DataFrame,
    pairwise_df: pd.DataFrame,
    cand_df: pd.DataFrame,
    best_variant: str,
):
    doc = REPO_ROOT / "docs" / "FIX01_STRENGTHENED_C1D_20260524.md"

    def _agg(df: pd.DataFrame) -> pd.DataFrame:
        t = df.groupby("selector", as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
        t["accuracy"] = t["correct"] / t["n"]
        return t.sort_values("accuracy", ascending=False)

    within_agg = _agg(within_eval)
    off_agg = _agg(off_eval)
    all_agg = _agg(all_eval)
    loso_agg = _agg(loso_eval)

    best_row = cand_df.iloc[0] if len(cand_df) else None

    with open(doc, "w", encoding="utf-8") as f:
        f.write("# FIX01_STRENGTHENED_C1D_20260524\n\n")
        f.write("## 1. Executive summary\n")
        if best_row is not None:
            f.write(
                f"Best FIX-01 variant: `{best_variant}` with official pooled CV {best_row['official_macro_cv']:.4f}, "
                f"delta vs beta-shrinkage {best_row['delta_vs_beta_shrinkage']:+.4f}, "
                f"delta vs C1d {best_row['delta_vs_C1d']:+.4f}.\n\n"
            )
        else:
            f.write("No candidate rows produced.\n\n")

        f.write("## 2. Data sources and caveats\n")
        f.write("Used completed scenarios only: Cohere×GSM8K (official), Mistral×GSM8K (official), Mistral×MATH-500 (official), Cohere×MATH-500 auxiliary (noncanonical). Active official Cohere MATH/Cerebras/train1000 runs excluded.\n\n")

        f.write("## 3. FIX-01 variants\n")
        f.write("Implemented families: FIX01a (LCB-gap), FIX01b (prob-of-dominance), FIX01c (near-peer safety), FIX01d (pattern-aware), FIX01e (minimal safe).\n\n")

        f.write("## 4. Evaluation protocol\n")
        f.write("Within-scenario 5-fold CV, official pooled stratified CV, official+aux pooled CV, LOSO, and full-artifact diagnostic (labeled non-test-valid).\n\n")

        f.write("## 5. Results by scenario\n")
        f.write(within_agg.head(20).to_string(index=False))
        f.write("\n\n")

        f.write("## 6. Official macro results\n")
        f.write(off_agg.head(20).to_string(index=False))
        f.write("\n\n")

        f.write("## 7. LOSO transfer results\n")
        f.write(loso_agg.head(20).to_string(index=False))
        f.write("\n\n")

        f.write("## 8. Pairwise recovery/regression\n")
        f.write(pairwise_df.sort_values(["baseline", "delta"], ascending=[True, False]).head(60).to_string(index=False))
        f.write("\n\n")

        f.write("## 9. Failure/regression analysis\n")
        f.write("See `outputs/fix01_strengthened_c1d_20260524/fix01_best_variant_casebook.md` and companion CSVs.\n\n")

        f.write("## 10. Best variant decision\n")
        f.write(cand_df.head(20).to_string(index=False))
        f.write("\n\n")

        f.write("## 11. Manuscript implication\n")
        f.write("Treat FIX-01 as selector-improvement evidence; avoid final promotion claim until official Cohere MATH and Cerebras scenarios complete.\n\n")

        f.write("## 12. Next iteration recommendation\n")
        f.write("Prioritize top FIX-01 variant refinement and FIX-03 near-peer S1 gate, then re-evaluate after active scenario completions.\n\n")

        f.write("## 13. Safety confirmation\n")
        f.write("Offline only; no API calls launched; no active-job interaction; no commit/push.\n")


def write_manifest(input_paths: Dict[str, str], scripts_created: List[str], output_files: List[str]):
    manifest = {
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_artifacts": input_paths,
        "scripts_created": scripts_created,
        "output_files": output_files,
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "limitations": [
            "Cohere official MATH-500 Scenario 4 excluded while active.",
            "Cerebras and Mistral train1000 active runs excluded.",
            "Auxiliary Cohere MATH-500 is noncanonical and reported separately.",
            "Full-artifact diagnostic is descriptive only (train=test).",
        ],
    }
    with open(OUT_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def main():
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[FIX01] start {ts}")

    unified, inventory = load_unified()
    print(f"[FIX01] unified rows: {len(unified)}")

    # Prepare variant grid
    variant_grid = build_variant_grid()
    print(f"[FIX01] variants: {len(variant_grid)}")

    # Run protocols
    within_eval, within_preds = run_within_scenario_cv(unified, variant_grid)
    off_eval, off_preds = run_pooled_cv(unified, variant_grid, include_aux=False)
    all_eval, all_preds = run_pooled_cv(unified, variant_grid, include_aux=True)
    loso_eval, loso_preds = run_loso(unified, variant_grid)
    diag_eval, diag_preds = run_full_diagnostic(unified, variant_grid)

    # Write summary outputs
    within_eval.to_csv(OUT_DIR / "fix01_within_scenario_cv_summary.csv", index=False)
    off_eval.to_csv(OUT_DIR / "fix01_official_pooled_cv_summary.csv", index=False)
    all_eval.to_csv(OUT_DIR / "fix01_official_plus_auxiliary_cv_summary.csv", index=False)
    loso_eval.to_csv(OUT_DIR / "fix01_leave_one_scenario_out_summary.csv", index=False)
    diag_eval.to_csv(OUT_DIR / "fix01_full_artifact_diagnostic_summary.csv", index=False)

    # Pairwise vs pooled4/beta/C1d from official pooled predictions
    pairwise_rows = []
    for v in [x["variant_name"] for x in variant_grid]:
        for bcol in ["pooled4_ok", "beta_shrinkage_ok", "c1d_ok"]:
            row = pairwise_from_preds(off_preds, v, bcol)
            if row:
                pairwise_rows.append(row)
    pairwise_df = pd.DataFrame(pairwise_rows)
    pairwise_df.to_csv(OUT_DIR / "fix01_pairwise_win_loss_summary.csv", index=False)

    # Oracle regret summary (official pooled)
    regret_rows = []
    off_agg = off_eval.groupby("selector", as_index=False).agg(n=("n", "sum"), correct=("correct", "sum"))
    off_agg["accuracy"] = off_agg["correct"] / off_agg["n"]
    oracle_acc = float(off_agg.loc[off_agg["selector"] == "oracle_best_source", "accuracy"].iloc[0])
    for _, r in off_agg.iterrows():
        regret_rows.append(
            {
                "selector": r["selector"],
                "official_pooled_acc": float(r["accuracy"]),
                "oracle_acc": oracle_acc,
                "regret_vs_oracle": float(oracle_acc - r["accuracy"]),
            }
        )
    pd.DataFrame(regret_rows).to_csv(OUT_DIR / "fix01_oracle_regret_summary.csv", index=False)

    # Recovery/regression summary vs beta and c1d
    rr_rows = []
    for v in [x["variant_name"] for x in variant_grid]:
        vpred = off_preds[off_preds["variant"] == v]
        if len(vpred) == 0:
            continue
        for bcol, bname in [("beta_shrinkage_ok", "beta_shrinkage"), ("c1d_ok", "C1d")]:
            rec = int(((vpred["variant_ok"] == 1) & (vpred[bcol] == 0)).sum())
            reg = int(((vpred["variant_ok"] == 0) & (vpred[bcol] == 1)).sum())
            rr_rows.append(
                {
                    "variant": v,
                    "baseline": bname,
                    "recoveries": rec,
                    "regressions": reg,
                    "net": rec - reg,
                    "variant_acc": float(vpred["variant_ok"].mean()),
                    "baseline_acc": float(vpred[bcol].mean()),
                }
            )
    rr_df = pd.DataFrame(rr_rows)
    rr_df.to_csv(OUT_DIR / "fix01_recovery_regression_summary.csv", index=False)

    # Candidate decision table
    cand_df, best_variant = build_candidate_table(off_eval, all_eval, loso_eval, off_preds, variant_grid)
    cand_df.to_csv(OUT_DIR / "fix01_candidate_decision_table.csv", index=False)
    write_candidate_decision_md(cand_df, best_variant)

    # Best-variant case analysis
    best_pred = off_preds[off_preds["variant"] == best_variant].copy()
    best_pred["recovery_vs_beta"] = ((best_pred["variant_ok"] == 1) & (best_pred["beta_shrinkage_ok"] == 0)).astype(int)
    best_pred["regression_vs_beta"] = ((best_pred["variant_ok"] == 0) & (best_pred["beta_shrinkage_ok"] == 1)).astype(int)
    best_pred["recovery_vs_c1d"] = ((best_pred["variant_ok"] == 1) & (best_pred["c1d_ok"] == 0)).astype(int)
    best_pred["regression_vs_c1d"] = ((best_pred["variant_ok"] == 0) & (best_pred["c1d_ok"] == 1)).astype(int)

    best_pred.to_csv(OUT_DIR / "fix01_best_variant_failure_cases.csv", index=False)
    best_pred[best_pred["regression_vs_beta"] == 1].to_csv(OUT_DIR / "fix01_regressions_vs_beta_shrinkage.csv", index=False)
    best_pred[best_pred["recovery_vs_beta"] == 1].to_csv(OUT_DIR / "fix01_recoveries_vs_beta_shrinkage.csv", index=False)
    best_pred[best_pred["regression_vs_c1d"] == 1].to_csv(OUT_DIR / "fix01_regressions_vs_c1d.csv", index=False)
    best_pred[best_pred["recovery_vs_c1d"] == 1].to_csv(OUT_DIR / "fix01_recoveries_vs_c1d.csv", index=False)

    false_dom = best_pred[
        (best_pred["dominance_active"] == 1)
        & (best_pred["spread_best_second"] < 0.05)
        & (best_pred["variant_ok"] == 0)
    ].copy()
    false_dom.to_csv(OUT_DIR / "fix01_false_dominance_cases.csv", index=False)

    missed_dom = best_pred[
        (best_pred["S1_ok"] == 1)
        & (best_pred["pooled4_ok"] == 0)
        & (best_pred["variant_ok"] == 0)
    ].copy()
    missed_dom.to_csv(OUT_DIR / "fix01_missed_dominance_cases.csv", index=False)

    # Casebook
    with open(OUT_DIR / "fix01_best_variant_casebook.md", "w", encoding="utf-8") as f:
        f.write(f"# FIX-01 Best Variant Casebook\n\n")
        f.write(f"Best variant: **{best_variant}**\n\n")

        f.write("## Top Recoveries vs Beta-shrinkage\n\n")
        rec = best_pred[best_pred["recovery_vs_beta"] == 1].head(25)
        for _, r in rec.iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} action={r['selected_action']} source={r['selected_source']} reason={r['reason']}\n")

        f.write("\n## Top Regressions vs Beta-shrinkage\n\n")
        reg = best_pred[best_pred["regression_vs_beta"] == 1].head(25)
        for _, r in reg.iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} action={r['selected_action']} source={r['selected_source']} reason={r['reason']}\n")

        f.write("\n## Override Accepted and Wrong\n\n")
        oa = best_pred[(best_pred["override_passed"] == 1) & (best_pred["variant_ok"] == 0)].head(25)
        for _, r in oa.iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} maj={r['majority_answer']} dominant={r['dominant_source']}\n")

        f.write("\n## Override Rejected and Wrong\n\n")
        orw = best_pred[(best_pred["override_rejected"] == 1) & (best_pred["variant_ok"] == 0)].head(25)
        for _, r in orw.iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} action={r['selected_action']} dominant={r['dominant_source']}\n")

        f.write("\n## No-majority wrong\n\n")
        nm = best_pred[(best_pred["no_majority_flag"] == 1) & (best_pred["variant_ok"] == 0)].head(25)
        for _, r in nm.iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']} action={r['selected_action']}\n")

        f.write("\n## All-sources-wrong cases (selector-nonfixable)\n\n")
        aw = best_pred[(best_pred["all_sources_wrong"] == 1)].head(25)
        for _, r in aw.iterrows():
            f.write(f"- {r['scenario_id']}::{r['example_id']}\n")

    # Next iteration recommendation files
    best_row = cand_df.iloc[0] if len(cand_df) else pd.Series(dtype=object)
    write_next_iteration(best_variant, best_row)

    # Report doc
    build_report(unified, within_eval, off_eval, all_eval, loso_eval, pairwise_df, cand_df, best_variant)

    # Write raw prediction dumps for reproducibility
    within_preds.to_csv(OUT_DIR / "fix01_within_scenario_case_predictions.csv", index=False)
    off_preds.to_csv(OUT_DIR / "fix01_official_pooled_case_predictions.csv", index=False)
    all_preds.to_csv(OUT_DIR / "fix01_official_plus_aux_case_predictions.csv", index=False)
    loso_preds.to_csv(OUT_DIR / "fix01_loso_case_predictions.csv", index=False)
    diag_preds.to_csv(OUT_DIR / "fix01_full_diagnostic_case_predictions.csv", index=False)

    # Optional bootstrap CI for best variant vs beta/c1d on official pooled
    bpred = off_preds[off_preds["variant"] == best_variant]
    ci_rows = []
    if len(bpred):
        a = bpred["variant_ok"].astype(int).to_numpy()
        for bcol, name in [("beta_shrinkage_ok", "beta_shrinkage"), ("c1d_ok", "C1d")]:
            b = bpred[bcol].astype(int).to_numpy()
            mean, lo, hi = bootstrap_ci_delta(a, b, n_boot=2000, seed=42)
            ci_rows.append({"variant": best_variant, "baseline": name, "delta_mean": mean, "ci95_lo": lo, "ci95_hi": hi})
    pd.DataFrame(ci_rows).to_csv(OUT_DIR / "fix01_bootstrap_ci_summary.csv", index=False)

    output_files = sorted([p.name for p in OUT_DIR.glob("*")])
    write_manifest(
        input_paths={
            "c1_unified": str(C1_UNIFIED),
            "c1_router": str(C1_ROUTER),
            "workbench_unified": str(WB_UNIFIED),
        },
        scripts_created=["scripts/evaluate_fix01_strengthened_c1d.py"],
        output_files=output_files,
    )

    print(f"[FIX01] done; best_variant={best_variant}")


if __name__ == "__main__":
    main()
