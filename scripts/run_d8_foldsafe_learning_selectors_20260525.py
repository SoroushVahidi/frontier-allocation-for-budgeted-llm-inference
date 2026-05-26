#!/usr/bin/env python3
"""Run D8 fold-safe learned-selector iteration (offline, no API)."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

METHODS = [
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
]
METHOD_ALIAS = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "l1",
    "external_s1_budget_forcing": "s1",
    "external_tale_prompt_budgeting": "tale",
}
ALIAS_TO_METHOD = {v: k for k, v in METHOD_ALIAS.items()}

FIXED_BASELINES = [
    "select_frontier_correct",
    "select_l1_correct",
    "select_s1_correct",
    "select_tale_correct",
    "pooled4_plurality_correct",
    "agreement_largest_cluster_correct",
    "agreement_strict_2plus_correct",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_now() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")


def bool_int(x: Any) -> int:
    if isinstance(x, bool):
        return int(x)
    if x is None:
        return 0
    s = str(x).strip().lower()
    if s in {"1", "true", "yes"}:
        return 1
    if s in {"0", "false", "no", "", "nan", "none"}:
        return 0
    try:
        return int(float(s) != 0.0)
    except Exception:
        return 0


def safe_float(x: Any, d: float = 0.0) -> float:
    try:
        if pd.isna(x):
            return d
        return float(x)
    except Exception:
        return d


def ece(y_true: np.ndarray, y_prob: np.ndarray, bins: int = 10) -> float:
    if len(y_true) == 0:
        return float("nan")
    y_prob = np.clip(y_prob, 1e-6, 1 - 1e-6)
    edges = np.linspace(0, 1, bins + 1)
    out = 0.0
    n = len(y_true)
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        m = (y_prob >= lo) & (y_prob < hi if i < bins - 1 else y_prob <= hi)
        k = int(m.sum())
        if k == 0:
            continue
        out += (k / n) * abs(float(y_true[m].mean() - y_prob[m].mean()))
    return float(out)


def run_cmd(cmd: list[str], cwd: Path) -> None:
    p = subprocess.run(cmd, cwd=cwd)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def pick_baseline_policy_by_scenario(base: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scen, g in base.groupby("scenario_id"):
        src = g[g["split"] == "validation"]
        split_used = "validation"
        if src.empty:
            src = g[g["split"] == "train"]
            split_used = "train"
        if src.empty:
            src = g
            split_used = "all"
        vals = {}
        for c in FIXED_BASELINES:
            if c in src.columns:
                vals[c] = float(pd.to_numeric(src[c], errors="coerce").fillna(0).mean())
        if not vals:
            continue
        best = sorted([k for k, v in vals.items() if np.isclose(v, max(vals.values()))])[0]
        rows.append({
            "scenario_id": scen,
            "baseline_policy": best,
            "baseline_policy_acc_ref": max(vals.values()),
            "baseline_policy_source_split": split_used,
        })
    return pd.DataFrame(rows)


def baseline_policy_to_method(pool_row: pd.Series, policy: str) -> tuple[str, int]:
    if policy == "select_frontier_correct":
        return ALIAS_TO_METHOD["frontier"], int(pool_row.get("select_frontier_correct", 0))
    if policy == "select_l1_correct":
        return ALIAS_TO_METHOD["l1"], int(pool_row.get("select_l1_correct", 0))
    if policy == "select_s1_correct":
        return ALIAS_TO_METHOD["s1"], int(pool_row.get("select_s1_correct", 0))
    if policy == "select_tale_correct":
        return ALIAS_TO_METHOD["tale"], int(pool_row.get("select_tale_correct", 0))

    if policy == "pooled4_plurality_correct":
        alias = str(pool_row.get("pooled4_plurality_selected_method", "frontier")).strip().lower()
        return ALIAS_TO_METHOD.get(alias, ALIAS_TO_METHOD["frontier"]), int(pool_row.get("pooled4_plurality_correct", 0))
    if policy == "agreement_largest_cluster_correct":
        alias = str(pool_row.get("agreement_largest_cluster_selected_method", "frontier")).strip().lower()
        return ALIAS_TO_METHOD.get(alias, ALIAS_TO_METHOD["frontier"]), int(pool_row.get("agreement_largest_cluster_correct", 0))
    if policy == "agreement_strict_2plus_correct":
        alias = str(pool_row.get("agreement_strict_2plus_selected_method", "frontier")).strip().lower()
        return ALIAS_TO_METHOD.get(alias, ALIAS_TO_METHOD["frontier"]), int(pool_row.get("agreement_strict_2plus_correct", 0))

    return ALIAS_TO_METHOD["frontier"], int(pool_row.get("select_frontier_correct", 0))


def choose_feature_columns(cand: pd.DataFrame) -> tuple[list[str], list[str]]:
    # Keep runtime-visible + fold-safe columns only.
    cat = [
        c
        for c in ["provider", "dataset", "scenario_id", "method", "math_subject", "math_level", "model_family", "dataset_family", "provider_family"]
        if c in cand.columns
    ]
    num_candidates = [
        "parse_success",
        "answer_length_chars",
        "output_length_chars",
        "output_length_tokens_approx",
        "problem_length_chars",
        "problem_length_tokens_approx",
        "problem_numeric_token_count",
        "numeric_answer_flag",
        "integer_answer_flag",
        "fraction_answer_flag",
        "expression_answer_flag",
        "answer_contains_variable",
        "answer_contains_units",
        "answer_magnitude_abs",
        "cluster_size",
        "max_cluster_size",
        "distinct_answer_count",
        "agreement_entropy",
        "candidate_is_isolated_flag",
        "candidate_in_largest_cluster_flag",
        "agrees_with_frontier",
        "agrees_with_l1",
        "agrees_with_s1",
        "agrees_with_tale",
    ]
    num_foldsafe = [c for c in cand.columns if c.endswith("_foldsafe")]
    num = [c for c in (num_candidates + num_foldsafe) if c in cand.columns]

    forbidden = {
        "candidate_correct",
        "candidate_correct_exact",
        "candidate_correct_combined",
        "gold_answer_for_labeling_only",
        "source_correct_vector_json",
        "oracle_available",
        "all_sources_wrong",
        "candidate_in_correct_cluster",
        "candidate_is_unique_correct",
        "row_id",
        "example_uid",
        "original_example_id",
        "question_hash",
        "question_text",
        "raw_output_text",
        "extracted_answer",
        "normalized_answer",
    }
    cat = [c for c in cat if c not in forbidden]
    num = [c for c in num if c not in forbidden]
    return cat, num


def make_matrix(df: pd.DataFrame, cat_cols: list[str], num_cols: list[str], fit_cols: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    X = df[cat_cols + num_cols].copy()
    for c in num_cols:
        X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0.0)
    for c in cat_cols:
        X[c] = X[c].fillna("unknown").astype(str)
    X = pd.get_dummies(X, columns=cat_cols, dummy_na=False)
    if fit_cols is not None:
        for c in fit_cols:
            if c not in X.columns:
                X[c] = 0
        X = X[fit_cols]
    return X, X.columns.tolist()


def pool_top1(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    s = df.sort_values(["pool_id", score_col], ascending=[True, False]).copy()
    return s.groupby("pool_id", as_index=False).head(1).copy()


def scenario_eval(selected: pd.DataFrame, base: pd.DataFrame, method_name: str) -> pd.DataFrame:
    # selected has one row per pool
    pool_acc = selected[["pool_id", "scenario_id", "provider", "dataset", "split", "candidate_correct"]].copy()
    pool_acc.rename(columns={"candidate_correct": "accuracy"}, inplace=True)

    rows = []
    for (spl, scen, prov, ds), g in pool_acc.groupby(["split", "scenario_id", "provider", "dataset"]):
        b = base[(base["split"] == spl) & (base["scenario_id"] == scen)]
        baseline_vals = {c: float(b[c].mean()) for c in FIXED_BASELINES if c in b.columns}
        if not baseline_vals:
            continue
        best_val = max(baseline_vals.values())
        best_names = sorted([k for k, v in baseline_vals.items() if np.isclose(v, best_val)])
        oracle = float(b["oracle_correct"].mean()) if "oracle_correct" in b.columns else float("nan")
        acc = float(g["accuracy"].mean())
        rows.append(
            {
                "split": spl,
                "scenario_id": scen,
                "provider": prov,
                "dataset": ds,
                "method": method_name,
                "n_pools": int(len(g)),
                "accuracy": acc,
                "best_corrected_fixed_baseline": ";".join(best_names),
                "best_corrected_fixed_baseline_acc": best_val,
                "delta_vs_best_corrected_fixed_baseline": acc - best_val,
                "win_tie_loss_vs_best_baseline": "win" if acc > best_val + 1e-12 else "tie" if np.isclose(acc, best_val) else "loss",
                "oracle_upper_bound": oracle,
                "oracle_gap_recovered": (acc / oracle) if oracle > 0 else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def summarize_wtl(df: pd.DataFrame, method: str, split_filter: str) -> str:
    x = df[(df["method"] == method) & (df["split"] == split_filter)]
    if x.empty:
        return "0/0/0"
    w = int((x["win_tie_loss_vs_best_baseline"] == "win").sum())
    t = int((x["win_tie_loss_vs_best_baseline"] == "tie").sum())
    l = int((x["win_tie_loss_vs_best_baseline"] == "loss").sum())
    return f"{w}/{t}/{l}"


def train_d8a(cand: pd.DataFrame, base: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, str, pd.DataFrame, dict[str, Any]]:
    cat_cols, num_cols = choose_feature_columns(cand)

    train = cand[cand["split"] == "train"].copy()
    val = cand[cand["split"] == "validation"].copy()
    test = cand[cand["split"] == "test"].copy()
    seen = cand[cand["split"] == "seen_dev"].copy()

    y_train = train["candidate_correct"].astype(int).values
    y_val = val["candidate_correct"].astype(int).values if not val.empty else np.array([])

    X_train, feat_cols = make_matrix(train, cat_cols, num_cols)
    X_val, _ = make_matrix(val, cat_cols, num_cols, fit_cols=feat_cols)
    X_test, _ = make_matrix(test, cat_cols, num_cols, fit_cols=feat_cols)
    X_seen, _ = make_matrix(seen, cat_cols, num_cols, fit_cols=feat_cols)

    # pool-balanced sample weights
    pool_counts = train.groupby("pool_id")["pool_id"].transform("count").astype(float)
    w_train = (1.0 / pool_counts).values

    models: dict[str, Any] = {
        "logreg": LogisticRegression(max_iter=2000),
        "hgb": HistGradientBoostingClassifier(max_depth=8, learning_rate=0.06, max_iter=300, random_state=42),
        "rf": RandomForestClassifier(n_estimators=500, random_state=42, n_jobs=-1),
    }
    if subprocess.run(["python3", "-c", "import xgboost"], capture_output=True).returncode == 0:
        from xgboost import XGBClassifier

        models["xgboost"] = XGBClassifier(
            n_estimators=500,
            max_depth=8,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
    if subprocess.run(["python3", "-c", "import lightgbm"], capture_output=True).returncode == 0:
        from lightgbm import LGBMClassifier

        models["lightgbm"] = LGBMClassifier(
            n_estimators=500,
            learning_rate=0.05,
            num_leaves=63,
            random_state=42,
            n_jobs=-1,
        )

    model_scores = []
    pred_cache: dict[str, dict[str, np.ndarray]] = {}

    for name, m in models.items():
        m.fit(X_train, y_train, sample_weight=w_train)
        p_train = m.predict_proba(X_train)[:, 1]
        p_val = m.predict_proba(X_val)[:, 1] if len(val) else np.array([])
        p_test = m.predict_proba(X_test)[:, 1] if len(test) else np.array([])
        p_seen = m.predict_proba(X_seen)[:, 1] if len(seen) else np.array([])

        val_sc = float("nan")
        if len(val):
            vdf = val.copy()
            vdf["score"] = p_val
            top = pool_top1(vdf, "score")
            val_sc = float(top["candidate_correct"].mean())
        model_scores.append({"model": name, "validation_pool_top1_accuracy": val_sc})
        pred_cache[name] = {"train": p_train, "val": p_val, "test": p_test, "seen": p_seen, "model": m}

    ms = pd.DataFrame(model_scores).sort_values("validation_pool_top1_accuracy", ascending=False)
    best_model = str(ms.iloc[0]["model"]) if not ms.empty else "logreg"
    p = pred_cache[best_model]

    # Optional Platt calibration on validation
    calib_used = False
    if len(val) > 200 and len(np.unique(y_val)) == 2:
        z = p["val"].reshape(-1, 1)
        cal = LogisticRegression(max_iter=1000)
        cal.fit(z, y_val)
        p["train"] = cal.predict_proba(p["train"].reshape(-1, 1))[:, 1]
        p["val"] = cal.predict_proba(p["val"].reshape(-1, 1))[:, 1]
        p["test"] = cal.predict_proba(p["test"].reshape(-1, 1))[:, 1] if len(test) else p["test"]
        p["seen"] = cal.predict_proba(p["seen"].reshape(-1, 1))[:, 1] if len(seen) else p["seen"]
        calib_used = True

    # predictions table
    parts = []
    for spl, arr in [("train", p["train"]), ("validation", p["val"]), ("test", p["test"]), ("seen_dev", p["seen"])]:
        sub = cand[cand["split"] == spl].copy()
        if len(sub) != len(arr):
            continue
        sub["d8a_prob"] = arr
        parts.append(sub)
    pred = pd.concat(parts, ignore_index=True)
    pred.to_csv(out_dir / "d8a_selector_case_predictions.csv", index=False)

    # selected top1
    selected = pool_top1(pred, "d8a_prob")
    selected.to_csv(out_dir / "d8a_selected_top1.csv", index=False)

    eval_df = scenario_eval(selected, base, "D8A")
    eval_df.to_csv(out_dir / "d8a_results_by_scenario.csv", index=False)

    # calibration summary
    cal_rows = []
    for spl in ["validation", "test", "seen_dev"]:
        sub = pred[pred["split"] == spl]
        if sub.empty:
            continue
        y = sub["candidate_correct"].astype(int).values
        pp = sub["d8a_prob"].astype(float).values
        auc = float(roc_auc_score(y, pp)) if len(np.unique(y)) > 1 else float("nan")
        cal_rows.append(
            {
                "split": spl,
                "auc": auc,
                "brier": float(brier_score_loss(y, pp)),
                "ece": ece(y, pp),
            }
        )
    cal_df = pd.DataFrame(cal_rows)
    cal_df.to_csv(out_dir / "calibration_summary.csv", index=False)

    # feature importance
    m_obj = p["model"]
    fi = pd.DataFrame({"feature": feat_cols, "importance": 0.0})
    if hasattr(m_obj, "feature_importances_"):
        imp = np.asarray(m_obj.feature_importances_)
        if len(imp) == len(feat_cols):
            fi["importance"] = imp
    elif hasattr(m_obj, "coef_"):
        c = np.abs(np.asarray(m_obj.coef_).reshape(-1))
        if len(c) == len(feat_cols):
            fi["importance"] = c
    fi.sort_values("importance", ascending=False).to_csv(out_dir / "feature_importance.csv", index=False)

    meta = {
        "best_model": best_model,
        "calibration_used": calib_used,
        "feature_count": len(feat_cols),
        "categorical_features": cat_cols,
        "numeric_features": num_cols,
    }
    return pred, eval_df, best_model, ms, meta


def train_d8b(cand: pd.DataFrame, base: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    policies = pick_baseline_policy_by_scenario(base)
    pool = base.merge(policies, on="scenario_id", how="left")

    # map baseline method + correctness per pool
    bm = []
    for _, r in pool.iterrows():
        pol = r.get("baseline_policy", "select_frontier_correct")
        m, c = baseline_policy_to_method(r, pol)
        bm.append((m, c))
    pool["baseline_method"] = [x[0] for x in bm]
    pool["baseline_correct"] = [x[1] for x in bm]

    c = cand.merge(pool[["pool_id", "baseline_policy", "baseline_method", "baseline_correct"]], on="pool_id", how="left")
    c["is_baseline_candidate"] = (c["method"] == c["baseline_method"]).astype(int)

    # baseline candidate answer/feature reference
    bfeat = c[c["is_baseline_candidate"] == 1][["pool_id", "answer_cluster_id", "parse_success", "rel_scenario_method_acc_foldsafe"]].copy()
    bfeat.rename(
        columns={
            "answer_cluster_id": "baseline_answer_cluster_id",
            "parse_success": "baseline_parse_success",
            "rel_scenario_method_acc_foldsafe": "baseline_rel_acc",
        },
        inplace=True,
    )
    c = c.merge(bfeat, on="pool_id", how="left")

    # override labels on non-baseline candidates
    cand_nb = c[c["is_baseline_candidate"] == 0].copy()
    cand_nb["override_good"] = ((cand_nb["candidate_correct"] == 1) & (cand_nb["baseline_correct"] == 0)).astype(int)
    cand_nb["override_bad"] = ((cand_nb["candidate_correct"] == 0) & (cand_nb["baseline_correct"] == 1)).astype(int)

    # features
    base_cols = [
        "provider",
        "dataset",
        "scenario_id",
        "method",
        "math_subject",
        "math_level",
        "parse_success",
        "output_length_chars",
        "problem_length_chars",
        "agreement_entropy",
        "cluster_size",
        "max_cluster_size",
        "agrees_with_frontier",
        "agrees_with_l1",
        "agrees_with_s1",
        "agrees_with_tale",
        "rel_scenario_method_acc_foldsafe",
        "rel_scenario_method_logodds_foldsafe",
        "rel_dataset_method_acc_foldsafe",
        "rel_provider_method_acc_foldsafe",
        "rel_unique_correct_rate_scenario_method_foldsafe",
        "comp_disagree_rate_frontier_foldsafe",
        "comp_rescue_rate_frontier_foldsafe",
        "comp_disagree_rate_l1_foldsafe",
        "comp_rescue_rate_l1_foldsafe",
        "comp_disagree_rate_s1_foldsafe",
        "comp_rescue_rate_s1_foldsafe",
        "comp_disagree_rate_tale_foldsafe",
        "comp_rescue_rate_tale_foldsafe",
        "baseline_parse_success",
        "baseline_rel_acc",
    ]
    feat_cols = [x for x in base_cols if x in cand_nb.columns]
    cat_cols = [c for c in feat_cols if cand_nb[c].dtype == object]
    num_cols = [c for c in feat_cols if c not in cat_cols]

    tr = cand_nb[cand_nb["split"] == "train"].copy()
    va = cand_nb[cand_nb["split"] == "validation"].copy()
    te = cand_nb[cand_nb["split"] == "test"].copy()
    sd = cand_nb[cand_nb["split"] == "seen_dev"].copy()

    if tr.empty:
        raise RuntimeError("No train rows for D8B")

    Xtr, fit_cols = make_matrix(tr, cat_cols, num_cols)
    Xva, _ = make_matrix(va, cat_cols, num_cols, fit_cols=fit_cols)
    Xte, _ = make_matrix(te, cat_cols, num_cols, fit_cols=fit_cols)
    Xsd, _ = make_matrix(sd, cat_cols, num_cols, fit_cols=fit_cols)

    ytr = tr["override_good"].astype(int).values
    yva = va["override_good"].astype(int).values if not va.empty else np.array([])

    model = HistGradientBoostingClassifier(max_depth=6, learning_rate=0.07, max_iter=250, random_state=42)
    model.fit(Xtr, ytr)

    tr["override_prob"] = model.predict_proba(Xtr)[:, 1]
    va["override_prob"] = model.predict_proba(Xva)[:, 1] if len(va) else np.array([])
    te["override_prob"] = model.predict_proba(Xte)[:, 1] if len(te) else np.array([])
    sd["override_prob"] = model.predict_proba(Xsd)[:, 1] if len(sd) else np.array([])

    all_nb = pd.concat([tr, va, te, sd], ignore_index=True)

    # threshold tuning on validation pools
    default_pool = pool[["pool_id", "baseline_method", "baseline_correct", "scenario_id", "provider", "dataset", "split"]].drop_duplicates("pool_id")

    # baseline accuracy on validation
    val_pool = default_pool[default_pool["split"] == "validation"]
    baseline_val_acc = float(val_pool["baseline_correct"].mean()) if not val_pool.empty else float("nan")

    best_tau = 0.8
    best_acc = -1.0
    threshold_rows = []
    for tau in np.linspace(0.5, 0.95, 19):
        sel = []
        for pid, g in all_nb[all_nb["split"] == "validation"].groupby("pool_id"):
            top = g.sort_values("override_prob", ascending=False).iloc[0]
            p = default_pool[default_pool["pool_id"] == pid].iloc[0]
            if float(top["override_prob"]) >= tau:
                pred_correct = int(top["candidate_correct"])
                over = 1
            else:
                pred_correct = int(p["baseline_correct"])
                over = 0
            sel.append({"pool_id": pid, "pred_correct": pred_correct, "override": over})
        if not sel:
            continue
        s = pd.DataFrame(sel)
        acc = float(s["pred_correct"].mean())
        cov = float(s["override"].mean())
        threshold_rows.append({"tau": float(tau), "validation_accuracy": acc, "override_rate": cov, "delta_vs_baseline": acc - baseline_val_acc})
        if acc >= baseline_val_acc - 0.002 and (acc > best_acc + 1e-12 or (np.isclose(acc, best_acc) and cov > 0.01)):
            best_acc = acc
            best_tau = float(tau)

    th_df = pd.DataFrame(threshold_rows)
    th_df.to_csv(out_dir / "d8b_threshold_sweep.csv", index=False)

    # apply policy at pool level for all splits
    selected_rows = []
    for _, p in default_pool.iterrows():
        pid = p["pool_id"]
        g = all_nb[all_nb["pool_id"] == pid]
        if g.empty:
            # no non-baseline candidate available
            selected_rows.append(
                {
                    "pool_id": pid,
                    "scenario_id": p["scenario_id"],
                    "provider": p["provider"],
                    "dataset": p["dataset"],
                    "split": p["split"],
                    "candidate_correct": int(p["baseline_correct"]),
                    "selected_method": p["baseline_method"],
                    "override_applied": 0,
                    "override_prob": 0.0,
                }
            )
            continue
        top = g.sort_values("override_prob", ascending=False).iloc[0]
        if float(top["override_prob"]) >= best_tau:
            selected_rows.append(
                {
                    "pool_id": pid,
                    "scenario_id": p["scenario_id"],
                    "provider": p["provider"],
                    "dataset": p["dataset"],
                    "split": p["split"],
                    "candidate_correct": int(top["candidate_correct"]),
                    "selected_method": top["method"],
                    "override_applied": 1,
                    "override_prob": float(top["override_prob"]),
                }
            )
        else:
            selected_rows.append(
                {
                    "pool_id": pid,
                    "scenario_id": p["scenario_id"],
                    "provider": p["provider"],
                    "dataset": p["dataset"],
                    "split": p["split"],
                    "candidate_correct": int(p["baseline_correct"]),
                    "selected_method": p["baseline_method"],
                    "override_applied": 0,
                    "override_prob": float(top["override_prob"]),
                }
            )

    selected = pd.DataFrame(selected_rows)
    selected.to_csv(out_dir / "d8b_selected_top1.csv", index=False)
    all_nb.to_csv(out_dir / "d8b_override_decisions.csv", index=False)

    eval_df = scenario_eval(selected, base, "D8B")
    eval_df.to_csv(out_dir / "d8b_results_by_scenario.csv", index=False)

    # false override diagnostics
    fo = selected[(selected["override_applied"] == 1) & (selected["candidate_correct"] == 0)].copy()
    fo.to_csv(out_dir / "false_override_cases.csv", index=False)

    meta = {
        "best_threshold": best_tau,
        "validation_baseline_accuracy": baseline_val_acc,
        "validation_selected_accuracy": best_acc,
    }
    return all_nb, eval_df, meta


def train_d8c(cand: pd.DataFrame, base: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    # numeric-only ranking features for robustness
    num_cols = [
        c
        for c in [
            "parse_success",
            "output_length_chars",
            "problem_length_chars",
            "cluster_size",
            "max_cluster_size",
            "distinct_answer_count",
            "agreement_entropy",
            "agrees_with_frontier",
            "agrees_with_l1",
            "agrees_with_s1",
            "agrees_with_tale",
            "rel_scenario_method_acc_foldsafe",
            "rel_scenario_method_logodds_foldsafe",
            "rel_dataset_method_acc_foldsafe",
            "rel_provider_method_acc_foldsafe",
            "rel_unique_correct_rate_scenario_method_foldsafe",
            "comp_disagree_rate_frontier_foldsafe",
            "comp_rescue_rate_frontier_foldsafe",
            "comp_disagree_rate_l1_foldsafe",
            "comp_rescue_rate_l1_foldsafe",
            "comp_disagree_rate_s1_foldsafe",
            "comp_rescue_rate_s1_foldsafe",
            "comp_disagree_rate_tale_foldsafe",
            "comp_rescue_rate_tale_foldsafe",
        ]
        if c in cand.columns
    ]

    use_cols = ["pool_id", "scenario_id", "provider", "dataset", "split", "method", "candidate_correct"] + num_cols
    d = cand[use_cols].copy()
    for c in num_cols:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)
    d["candidate_correct"] = d["candidate_correct"].astype(int)

    tr = d[d["split"] == "train"].copy()
    va = d[d["split"] == "validation"].copy()
    te = d[d["split"] == "test"].copy()
    sd = d[d["split"] == "seen_dev"].copy()

    if tr.empty:
        return pd.DataFrame(), pd.DataFrame(), {"skipped": True, "reason": "no_train"}

    model_name = "fallback_hgb_regressor"
    ranker = None

    if subprocess.run(["python3", "-c", "import lightgbm"], capture_output=True).returncode == 0:
        from lightgbm import LGBMRanker

        model_name = "lightgbm_lambdarank"
        ranker = LGBMRanker(
            objective="lambdarank",
            n_estimators=300,
            learning_rate=0.05,
            num_leaves=63,
            random_state=42,
        )
    elif subprocess.run(["python3", "-c", "import xgboost"], capture_output=True).returncode == 0:
        from xgboost import XGBRanker

        model_name = "xgboost_ranker"
        ranker = XGBRanker(
            objective="rank:pairwise",
            n_estimators=350,
            learning_rate=0.05,
            max_depth=8,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
        )

    Xtr = tr[num_cols]
    ytr = tr["candidate_correct"].astype(float)
    grp_tr = tr.groupby("pool_id").size().values

    if ranker is not None:
        if model_name == "lightgbm_lambdarank":
            ranker.fit(Xtr, ytr, group=grp_tr)
        else:
            ranker.fit(Xtr, ytr, group=grp_tr)
    else:
        from sklearn.ensemble import HistGradientBoostingRegressor

        ranker = HistGradientBoostingRegressor(max_depth=8, learning_rate=0.06, max_iter=250, random_state=42)
        ranker.fit(Xtr, ytr)

    parts = []
    for spl_df in [tr, va, te, sd]:
        if spl_df.empty:
            continue
        sub = spl_df.copy()
        sub["ranking_score"] = ranker.predict(sub[num_cols])
        parts.append(sub)
    pred = pd.concat(parts, ignore_index=True)
    pred.to_csv(out_dir / "d8c_ranking_scores.csv", index=False)

    selected = pool_top1(pred, "ranking_score")
    selected.to_csv(out_dir / "d8c_selected_top1.csv", index=False)

    eval_df = scenario_eval(selected, base, "D8C")
    eval_df.to_csv(out_dir / "d8c_results_by_scenario.csv", index=False)

    # all-zero pools diagnostics
    all_zero = (
        d.groupby("pool_id")["candidate_correct"].sum().reset_index().rename(columns={"candidate_correct": "n_correct"})
    )
    all_zero["all_zero_group_flag"] = (all_zero["n_correct"] == 0).astype(int)
    all_zero.to_csv(out_dir / "d8c_all_zero_group_analysis.csv", index=False)

    return pred, eval_df, {"model": model_name, "feature_count": len(num_cols)}


def train_d8d(pool_feat_path: Path, out_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    p = pd.read_csv(pool_feat_path)
    if "oracle_available" not in p.columns:
        return pd.DataFrame(), {"skipped": True, "reason": "missing_oracle_label"}

    tr = p[p["split"] == "train"].copy()
    va = p[p["split"] == "validation"].copy()
    te = p[p["split"] == "test"].copy()
    sd = p[p["split"] == "seen_dev"].copy()
    if tr.empty:
        return pd.DataFrame(), {"skipped": True, "reason": "no_train"}

    use_num = [c for c in p.columns if c not in {"pool_id", "scenario_id", "provider", "dataset", "split", "oracle_available", "all_sources_wrong"}]
    # add one-hot for provider/dataset/scenario
    def make(sub: pd.DataFrame, cols_fit: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
        x = sub[["provider", "dataset", "scenario_id"] + use_num].copy()
        for c in use_num:
            x[c] = pd.to_numeric(x[c], errors="coerce").fillna(0.0)
        x = pd.get_dummies(x, columns=["provider", "dataset", "scenario_id"], dummy_na=False)
        if cols_fit is not None:
            for c in cols_fit:
                if c not in x.columns:
                    x[c] = 0
            x = x[cols_fit]
        return x, x.columns.tolist()

    Xtr, fit_cols = make(tr)
    Xva, _ = make(va, fit_cols)
    Xte, _ = make(te, fit_cols)
    Xsd, _ = make(sd, fit_cols)

    ytr = tr["oracle_available"].astype(int).values
    mdl = HistGradientBoostingClassifier(max_depth=6, learning_rate=0.06, max_iter=250, random_state=42)
    mdl.fit(Xtr, ytr)

    rows = []
    for name, sub, X in [("validation", va, Xva), ("test", te, Xte), ("seen_dev", sd, Xsd)]:
        if sub.empty:
            continue
        y = sub["oracle_available"].astype(int).values
        pp = mdl.predict_proba(X)[:, 1]
        auc = float(roc_auc_score(y, pp)) if len(np.unique(y)) > 1 else float("nan")
        pred = (pp >= 0.5).astype(int)
        acc = float((pred == y).mean())
        rows.append(
            {
                "split": name,
                "auc": auc,
                "brier": float(brier_score_loss(y, pp)),
                "ece": ece(y, pp),
                "accuracy": acc,
                "all_sources_wrong_recall": float(((pred == 0) & (sub["all_sources_wrong"].astype(int) == 1)).sum() / max(1, int((sub["all_sources_wrong"].astype(int) == 1).sum()))),
            }
        )

    rep = pd.DataFrame(rows)
    rep.to_csv(out_dir / "d8d_oracle_classifier_summary.csv", index=False)

    # save pool predictions
    all_parts = []
    for sub, X in [(tr, Xtr), (va, Xva), (te, Xte), (sd, Xsd)]:
        if sub.empty:
            continue
        ss = sub.copy()
        ss["d8d_oracle_prob"] = mdl.predict_proba(X)[:, 1]
        all_parts.append(ss)
    if all_parts:
        pd.concat(all_parts, ignore_index=True).to_csv(out_dir / "d8d_pool_predictions.csv", index=False)

    return rep, {"trained": True, "feature_count": len(fit_cols)}


def merge_rankings_with_existing(existing_rank_csv: Path, d8_eval_frames: list[pd.DataFrame], base: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    old = pd.read_csv(existing_rank_csv)

    # adapt old schema fields
    old = old.copy()
    if "is_oracle" not in old.columns:
        old["is_oracle"] = (old["method"] == "oracle_upper_bound").astype(int)

    add = pd.concat([x for x in d8_eval_frames if x is not None and not x.empty], ignore_index=True)
    if not add.empty:
        add2 = add.copy()
        add2["split_status"] = add2["split"].map(lambda s: "clean_test" if s == "test" else "seen_dev_provisional" if s == "seen_dev" else s)
        add2["scenario_id"] = add2["scenario_id"]
        add2["is_oracle"] = 0
        add2 = add2[
            [
                "split",
                "split_status",
                "scenario_id",
                "provider",
                "dataset",
                "method",
                "accuracy",
                "best_corrected_fixed_baseline",
                "best_corrected_fixed_baseline_acc",
                "delta_vs_best_corrected_fixed_baseline",
                "win_tie_loss_vs_best_baseline",
                "oracle_upper_bound",
                "is_oracle",
            ]
        ]
    else:
        add2 = pd.DataFrame(columns=[
            "split",
            "split_status",
            "scenario_id",
            "provider",
            "dataset",
            "method",
            "accuracy",
            "best_corrected_fixed_baseline",
            "best_corrected_fixed_baseline_acc",
            "delta_vs_best_corrected_fixed_baseline",
            "win_tie_loss_vs_best_baseline",
            "oracle_upper_bound",
            "is_oracle",
        ])

    # keep old comparable columns
    old2 = old[
        [
            "split",
            "split_status",
            "scenario_id",
            "provider",
            "dataset",
            "method",
            "accuracy",
            "best_corrected_fixed_baseline",
            "best_corrected_fixed_baseline_acc",
            "delta_vs_best_corrected_fixed_baseline",
            "win_tie_loss_vs_best_baseline",
            "oracle_upper_bound",
            "is_oracle",
        ]
    ].copy()

    combo = pd.concat([old2, add2], ignore_index=True)
    combo.to_csv(out_dir / "d8_scenario_method_rankings.csv", index=False)

    # scenario json summary
    scen = {}
    for sid, g in combo.groupby("scenario_id"):
        scen[sid] = {
            "split_status": sorted(g["split_status"].dropna().astype(str).unique().tolist()),
            "methods": g.sort_values("accuracy", ascending=False).to_dict(orient="records"),
        }
    (out_dir / "d8_scenario_method_rankings.json").write_text(json.dumps(scen, indent=2))

    # wins/ties/losses for D8 methods on clean test and seen_dev
    summary = {}
    for m in ["D8A", "D8B", "D8C"]:
        summary[m] = {
            "clean_test_wtl": summarize_wtl(combo, m, "test"),
            "seen_dev_wtl": summarize_wtl(combo, m, "seen_dev"),
        }

    # best non-oracle among D8 variants by mean clean-test accuracy
    best_var = None
    best_val = -1.0
    for m in ["D8A", "D8B", "D8C"]:
        x = combo[(combo["method"] == m) & (combo["split"] == "test")]
        if x.empty:
            continue
        v = float(x["accuracy"].mean())
        if v > best_val:
            best_val = v
            best_var = m

    gsum = {
        "generated_at": now_utc(),
        "best_d8_variant_clean_test": best_var,
        "best_d8_variant_clean_test_mean_accuracy": best_val if best_var else None,
        "scenario_wtl": summary,
    }
    (out_dir / "d8_global_summary.json").write_text(json.dumps(gsum, indent=2))

    return combo, gsum


def write_markdown_summary(out_dir: Path, preflight: dict[str, Any], d8a_meta: dict[str, Any], d8b_meta: dict[str, Any], d8c_meta: dict[str, Any], d8d_meta: dict[str, Any], global_summary: dict[str, Any]) -> None:
    lines = [
        "# D8 Results Summary",
        "",
        "## Preflight",
        f"- Data source: `{preflight['unified_dir']}`",
        f"- Corrected baseline source: `{preflight['baseline_dir']}`",
        f"- Candidate rows: {preflight['candidate_rows']}",
        f"- Pool rows: {preflight['pool_rows']}",
        f"- Scenarios: {preflight['scenarios']}",
        f"- Splits: {preflight['splits']}",
        f"- Known warnings: {preflight['warnings']}",
        "",
        "## D8 Variants",
        f"- D8A best model: {d8a_meta.get('best_model')} (calibration_used={d8a_meta.get('calibration_used')})",
        f"- D8B best threshold: {d8b_meta.get('best_threshold')}",
        f"- D8C model: {d8c_meta.get('model', 'skipped')}",
        f"- D8D oracle classifier: {'trained' if d8d_meta.get('trained') else 'skipped'}",
        "",
        "## Headline",
        f"- Best D8 variant on clean test mean accuracy: {global_summary.get('best_d8_variant_clean_test')} ({global_summary.get('best_d8_variant_clean_test_mean_accuracy')})",
        f"- D8A clean-test W/T/L: {global_summary['scenario_wtl'].get('D8A', {}).get('clean_test_wtl')}",
        f"- D8B clean-test W/T/L: {global_summary['scenario_wtl'].get('D8B', {}).get('clean_test_wtl')}",
        f"- D8C clean-test W/T/L: {global_summary['scenario_wtl'].get('D8C', {}).get('clean_test_wtl')}",
        "",
        "Oracle is reported as upper bound only. No row-wise max baseline used.",
    ]
    (out_dir / "D8_RESULTS_SUMMARY.md").write_text("\n".join(lines) + "\n")


def update_ledger_and_backlog(repo: Path, run_id: str, out_dir: Path, preflight: dict[str, Any], gsum: dict[str, Any]) -> None:
    ldir = repo / "outputs/training_experiment_ledger_20260525"
    csv_path = ldir / "training_experiment_ledger.csv"
    md_path = ldir / "training_experiment_ledger.md"
    backlog_path = ldir / "training_backlog.md"

    df = pd.read_csv(csv_path)
    new_row = {
        "run_id": run_id,
        "date_time_utc": now_utc(),
        "input_table_path": preflight["unified_dir"],
        "output_path": str(out_dir.relative_to(repo)),
        "model_families_tried": "d8a_gbdt+d8b_override+d8c_ranker+d8d_oracle_optional",
        "feature_groups_used": "runtime_safe+foldsafe_reliability+foldsafe_complementarity",
        "reliability_features_used": "yes",
        "complementarity_features_used": "yes",
        "calibration_used": "yes_if_validation_supported",
        "gpu_used": "unknown",
        "clean_test_wins_ties_losses": gsum.get("scenario_wtl", {}).get("D8A", {}).get("clean_test_wtl", ""),
        "seen_dev_wins_ties_losses": gsum.get("scenario_wtl", {}).get("D8A", {}).get("seen_dev_wtl", ""),
        "macro_accuracy": np.nan,
        "worst_scenario_accuracy": np.nan,
        "biggest_losses": "see d8_scenario_method_rankings.csv",
        "promotion_decision": "not_promotable_yet_or_pending_manual_review",
        "next_recommended_training": "Fix D6 scripts and build regime/policy label table in parallel",
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(csv_path, index=False)

    # regenerate markdown table
    cols = list(df.columns)
    lines = ["# Training Experiment Ledger", "", "| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            if pd.isna(v):
                vals.append("")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    md_path.write_text("\n".join(lines) + "\n")

    # append backlog status
    old = backlog_path.read_text() if backlog_path.exists() else "# Training Backlog\n\n"
    add = f"\n- D8 fold-safe learned-selector iteration completed: `{out_dir.relative_to(repo)}`\n"
    if add not in old:
        backlog_path.write_text(old.rstrip() + "\n" + add)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--session-name", required=False, default="")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    out_dir = Path(args.run_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    unified_dir = repo / "outputs/unified_learning_tables_20260525/run_20260525T184354Z"
    baseline_dir = repo / "outputs/baseline_selector_definition_audit_20260525/run_20260525T194246Z"
    corrected_eval_dir = repo / "outputs/corrected_d1_d2_evaluation_20260525/run_20260525T201240Z"
    existing_rank = repo / "outputs/project_state_and_branch_audit_20260525/run_20260525T214516Z/scenario_method_rankings.csv"

    # Preflight
    cand = pd.read_csv(unified_dir / "unified_candidate_action_table.csv", usecols=["scenario_id", "provider", "dataset", "split", "pool_id"]) 
    pool = pd.read_csv(unified_dir / "unified_pool_level_table.csv", usecols=["scenario_id", "split", "pool_id"]) 
    base = pd.read_csv(baseline_dir / "corrected_baseline_pool_decisions.csv")

    preflight = {
        "generated_at": now_utc(),
        "unified_dir": str(unified_dir.relative_to(repo)),
        "baseline_dir": str(baseline_dir.relative_to(repo)),
        "corrected_eval_dir": str(corrected_eval_dir.relative_to(repo)),
        "candidate_rows": int(len(cand)),
        "pool_rows": int(pool["pool_id"].nunique()),
        "scenarios": sorted(cand["scenario_id"].dropna().astype(str).unique().tolist()),
        "splits": sorted(cand["split"].dropna().astype(str).unique().tolist()),
        "label_availability": {
            "candidate_correct": True,
            "oracle_available": True,
            "all_sources_wrong": True,
            "override_good_derivable": True,
            "ranking_relevance_derivable": True,
        },
        "feature_availability": {
            "foldsafe_reliability": True,
            "foldsafe_complementarity": True,
            "cluster_agreement": True,
        },
        "warnings": [
            "MATH-500 splits are seen_dev/provisional",
            "Cohere MATH-500 known 10-ID inconsistency warning applies to some downstream labels",
            "No row-wise max baseline used",
        ],
    }
    (out_dir / "d8_preflight_summary.json").write_text(json.dumps(preflight, indent=2))
    (out_dir / "d8_preflight_summary.md").write_text(
        "\n".join(
            [
                "# D8 Preflight Summary",
                "",
                f"- Data source paths: `{preflight['unified_dir']}`, `{preflight['baseline_dir']}`, `{preflight['corrected_eval_dir']}`",
                f"- Candidate rows: {preflight['candidate_rows']}",
                f"- Pool rows: {preflight['pool_rows']}",
                f"- Scenarios: {preflight['scenarios']}",
                f"- Splits: {preflight['splits']}",
                f"- Label availability: {preflight['label_availability']}",
                f"- Feature availability: {preflight['feature_availability']}",
                f"- Known warnings: {preflight['warnings']}",
            ]
        )
        + "\n"
    )

    # Part B: build fold-safe features
    run_cmd(
        [
            "python3",
            "scripts/d8_build_foldsafe_learning_features.py",
            "--unified-dir",
            str(unified_dir),
            "--baseline-dir",
            str(baseline_dir),
            "--output-dir",
            str(out_dir),
        ],
        cwd=repo,
    )

    cand_feat = pd.read_csv(out_dir / "d8_candidate_features.csv")
    pool_feat = pd.read_csv(out_dir / "d8_pool_features.csv")
    base_df = pd.read_csv(baseline_dir / "corrected_baseline_pool_decisions.csv")

    # Part C: label schema/report
    label_schema = {
        "candidate_labels": ["candidate_correct"],
        "pool_labels": ["oracle_available", "all_sources_wrong"],
        "override_labels": ["baseline_policy", "baseline_method", "baseline_correct", "override_good", "override_bad"],
        "ranking_labels": ["candidate_correct as relevance", "all_zero_group_flag"],
        "cluster_labels_offline_only": ["candidate_in_correct_cluster", "candidate_is_unique_correct"],
    }
    (out_dir / "d8_label_schema.json").write_text(json.dumps(label_schema, indent=2))
    (out_dir / "d8_label_report.md").write_text(
        "\n".join(
            [
                "# D8 Label Report",
                "",
                "- Candidate/action label: `candidate_correct`.",
                "- Pool labels: `oracle_available`, `all_sources_wrong`.",
                "- Override labels are built against scenario-best corrected fixed baseline policy.",
                "- Ranking relevance: binary correctness (`candidate_correct`).",
                "- Cluster correctness labels are offline-only diagnostics and not used as runtime-visible features.",
            ]
        )
        + "\n"
    )

    # D8A
    d8a_pred, d8a_eval, d8a_best_model, d8a_models, d8a_meta = train_d8a(cand_feat, base_df, out_dir)
    d8a_models.to_csv(out_dir / "d8a_model_selection.csv", index=False)
    (out_dir / "d8a_meta.json").write_text(json.dumps({**d8a_meta, "best_model": d8a_best_model}, indent=2))

    # D8B
    d8b_pred, d8b_eval, d8b_meta = train_d8b(cand_feat, base_df, out_dir)
    (out_dir / "d8b_meta.json").write_text(json.dumps(d8b_meta, indent=2))

    # D8C
    d8c_pred, d8c_eval, d8c_meta = train_d8c(cand_feat, base_df, out_dir)
    (out_dir / "d8c_meta.json").write_text(json.dumps(d8c_meta, indent=2))

    # D8D
    d8d_eval, d8d_meta = train_d8d(out_dir / "d8_pool_features.csv", out_dir)
    (out_dir / "d8d_meta.json").write_text(json.dumps(d8d_meta, indent=2))

    # Common diagnostics
    # oracle-available missed cases from D8A
    top_a = pd.read_csv(out_dir / "d8a_selected_top1.csv")
    b = base_df[["pool_id", "oracle_correct", "select_frontier_correct"]].copy()
    z = top_a.merge(b, on="pool_id", how="left")
    miss = z[(z["oracle_correct"].fillna(0).astype(int) == 1) & (z["candidate_correct"].astype(int) == 0)]
    miss.to_csv(out_dir / "oracle_available_missed_cases.csv", index=False)

    # frontier contribution summary by scenario (D8A and D8B/D8C if present)
    fc_rows = []
    for mname, fp in [("D8A", out_dir / "d8a_selected_top1.csv"), ("D8B", out_dir / "d8b_selected_top1.csv"), ("D8C", out_dir / "d8c_selected_top1.csv")]:
        if not fp.exists():
            continue
        s = pd.read_csv(fp)
        for scen, g in s.groupby("scenario_id"):
            fc_rows.append({
                "method": mname,
                "scenario_id": scen,
                "split_values": ";".join(sorted(g["split"].dropna().astype(str).unique().tolist())),
                "accuracy": float(g["candidate_correct"].mean()),
                "frontier_selected_rate": float((g.get("selected_method", pd.Series([""])) == "direct_reserve_semantic_frontier_v2").mean()) if "selected_method" in g.columns else float("nan"),
            })
    pd.DataFrame(fc_rows).to_csv(out_dir / "frontier_contribution_summary.csv", index=False)

    # failure diagnostics markdown
    fd_lines = [
        "# D8 Failure Diagnostics",
        "",
        "Focus scenarios:",
        "- cohere_math500",
        "- cloudrift_math500",
        "- cohere_gsm8k",
        "- cloudrift_gsm8k",
        "",
        "See files:",
        "- false_override_cases.csv",
        "- oracle_available_missed_cases.csv",
        "- frontier_contribution_summary.csv",
        "- d8_scenario_method_rankings.csv",
    ]
    (out_dir / "d8_failure_diagnostics.md").write_text("\n".join(fd_lines) + "\n")

    # Merge rankings with existing D1-D4 baselines
    combo, gsum = merge_rankings_with_existing(existing_rank, [d8a_eval, d8b_eval, d8c_eval], base_df, out_dir)

    write_markdown_summary(out_dir, preflight, {**d8a_meta, "best_model": d8a_best_model}, d8b_meta, d8c_meta, d8d_meta, gsum)

    # Update training ledger/backlog
    run_id = out_dir.name
    update_ledger_and_backlog(repo, run_id, out_dir, preflight, gsum)

    # completion marker
    done = {
        "completed_at": now_utc(),
        "run_dir": str(out_dir),
        "best_d8_variant": gsum.get("best_d8_variant_clean_test"),
        "best_d8_variant_clean_test_mean_accuracy": gsum.get("best_d8_variant_clean_test_mean_accuracy"),
        "scenario_wtl": gsum.get("scenario_wtl", {}),
        "d8_promotable": "pending_manual_review",
        "next_recommendation": "continue learning with existing data in parallel; fix D6 generation/eval scripts before any API D6 run",
    }
    (out_dir / "d8_completion.json").write_text(json.dumps(done, indent=2))
    print(json.dumps(done, indent=2))


if __name__ == "__main__":
    main()
