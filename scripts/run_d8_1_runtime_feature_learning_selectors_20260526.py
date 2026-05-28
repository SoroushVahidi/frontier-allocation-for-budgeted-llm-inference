#!/usr/bin/env python3
"""Run D8.1 runtime-visible learned selectors (offline only, no API calls)."""

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
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, precision_recall_fscore_support, roc_auc_score

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
        rows.append(
            {
                "scenario_id": scen,
                "baseline_policy": best,
                "baseline_policy_acc_ref": max(vals.values()),
                "baseline_policy_source_split": split_used,
            }
        )
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


def scenario_eval(selected: pd.DataFrame, base: pd.DataFrame, method_name: str) -> pd.DataFrame:
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
                "is_oracle": 0,
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


def pick_feature_columns(cand: pd.DataFrame, include_dataset: bool) -> tuple[list[str], list[str]]:
    cat = [
        c
        for c in [
            "provider",
            "provider_api_id",
            "provider_backend_type",
            "model_deployment_name",
            "method",
            "action_family",
            "prompt_method_family",
            "budget_prompting_type",
            "predicted_instance_type",
            "predicted_answer_type",
            "answer_type_rt",
            "dataset",
            "scenario_id",
        ]
        if c in cand.columns
    ]
    if not include_dataset:
        cat = [c for c in cat if c not in {"dataset", "scenario_id"}]

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
        "example_uid",
        "original_example_id",
        "question_hash",
        "raw_output_text",
        "question_text",
        "extracted_answer",
        "normalized_answer",
        "row_id",
        "action_correct",
    }

    num = []
    for c in cand.columns:
        if c in forbidden or c in cat:
            continue
        if c.endswith("_flag") or c.endswith("_rt") or c.endswith("_foldsafe"):
            num.append(c)
    allow_extra = [
        "answer_length_chars",
        "output_length_chars",
        "output_length_tokens_approx",
        "problem_length_chars",
        "problem_length_tokens_approx",
        "problem_numeric_token_count",
        "cluster_size",
        "max_cluster_size",
        "distinct_answer_count",
        "agreement_entropy",
        "openai_compatible_flag",
        "reasoning_output_fallback_flag",
        "ours_vs_external_flag",
        "parse_success",
        "numeric_answer_flag",
        "expression_answer_flag",
        "malformed_output_flag",
    ]
    for c in allow_extra:
        if c in cand.columns and c not in num and c not in forbidden:
            num.append(c)

    return cat, sorted(set(num))


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


def _candidate_models() -> list[tuple[str, Any]]:
    models: list[tuple[str, Any]] = []
    try:
        from xgboost import XGBClassifier  # type: ignore

        models.append(
            (
                "xgboost",
                XGBClassifier(
                    n_estimators=250,
                    max_depth=7,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    objective="binary:logistic",
                    eval_metric="logloss",
                    random_state=42,
                    n_jobs=4,
                ),
            )
        )
    except Exception:
        pass

    try:
        from lightgbm import LGBMClassifier  # type: ignore

        models.append(("lightgbm", LGBMClassifier(n_estimators=300, learning_rate=0.05, max_depth=-1, random_state=42)))
    except Exception:
        pass

    try:
        from catboost import CatBoostClassifier  # type: ignore

        models.append(("catboost", CatBoostClassifier(verbose=0, depth=8, learning_rate=0.05, iterations=300, random_state=42)))
    except Exception:
        pass

    models.append(("hist_gradient_boosting", HistGradientBoostingClassifier(max_depth=8, learning_rate=0.05, max_iter=350, random_state=42)))
    models.append(("random_forest", RandomForestClassifier(n_estimators=500, max_depth=16, random_state=42, n_jobs=4)))
    models.append(("logistic_regression", LogisticRegression(max_iter=2000, n_jobs=4)))
    return models


def _model_predict_proba(model: Any, X: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    pred = model.predict(X)
    return np.asarray(pred, dtype=float)


def train_d8_1a(cand: pd.DataFrame, base: pd.DataFrame, out_dir: Path, include_dataset: bool, method_name: str) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    cat_cols, num_cols = pick_feature_columns(cand, include_dataset=include_dataset)

    tr = cand[cand["split"] == "train"].copy()
    va = cand[cand["split"] == "validation"].copy()
    te = cand[cand["split"] == "test"].copy()
    sd = cand[cand["split"] == "seen_dev"].copy()

    if tr.empty:
        raise RuntimeError(f"No train rows for {method_name}")

    Xtr, fit_cols = make_matrix(tr, cat_cols, num_cols)
    ytr = tr["action_correct"].astype(int).values
    Xva, _ = make_matrix(va, cat_cols, num_cols, fit_cols)
    yva = va["action_correct"].astype(int).values if len(va) else np.array([])

    best = None
    best_name = ""
    best_val = -1.0
    model_rows = []

    for name, mdl in _candidate_models():
        try:
            mdl.fit(Xtr, ytr)
            if len(va):
                va2 = va.copy()
                va2["score"] = _model_predict_proba(mdl, Xva)
                sel = pool_top1(va2, "score")
                v = float(sel["action_correct"].mean())
            else:
                tr2 = tr.copy()
                tr2["score"] = _model_predict_proba(mdl, Xtr)
                v = float(pool_top1(tr2, "score")["action_correct"].mean())
            model_rows.append({"model": name, "validation_pool_top1_acc": v})
            if v > best_val:
                best_val = v
                best = mdl
                best_name = name
        except Exception as e:
            model_rows.append({"model": name, "validation_pool_top1_acc": float("nan"), "error": str(e)})

    if best is None:
        raise RuntimeError(f"No model trained for {method_name}")

    # optional calibration on validation
    calib_used = False
    iso: IsotonicRegression | None = None
    if len(va) >= 20 and len(np.unique(yva)) >= 2:
        pva_raw = _model_predict_proba(best, Xva)
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(pva_raw, yva)
        calib_used = True

    frames = []
    for sub in [tr, va, te, sd]:
        if sub.empty:
            continue
        X, _ = make_matrix(sub, cat_cols, num_cols, fit_cols)
        p = _model_predict_proba(best, X)
        if iso is not None:
            p = iso.predict(p)
        ss = sub.copy()
        ss["pred_prob"] = p
        frames.append(ss)

    pred = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    selected = pool_top1(pred, "pred_prob").copy()
    selected["candidate_correct"] = selected["action_correct"].astype(int)

    eval_df = scenario_eval(selected, base, method_name)
    pred.to_csv(out_dir / f"{method_name.lower()}_candidate_predictions.csv", index=False)
    selected.to_csv(out_dir / f"{method_name.lower()}_selected_top1.csv", index=False)
    eval_df.to_csv(out_dir / f"{method_name.lower()}_results_by_scenario.csv", index=False)
    pd.DataFrame(model_rows).to_csv(out_dir / f"{method_name.lower()}_model_selection.csv", index=False)

    # calibration summary by split
    crows = []
    for split in ["train", "validation", "test", "seen_dev"]:
        ss = pred[pred["split"] == split]
        if ss.empty:
            continue
        y = ss["action_correct"].astype(int).values
        p = ss["pred_prob"].astype(float).values
        crows.append(
            {
                "method": method_name,
                "split": split,
                "n": int(len(ss)),
                "ece": ece(y, p),
                "brier": float(brier_score_loss(y, np.clip(p, 1e-6, 1 - 1e-6))),
                "mean_prob": float(np.mean(p)),
                "base_rate": float(np.mean(y)),
            }
        )
    cal_df = pd.DataFrame(crows)

    fi = pd.DataFrame({"feature": fit_cols, "importance": 0.0})
    if hasattr(best, "feature_importances_"):
        imp = np.asarray(best.feature_importances_)
        if len(imp) == len(fit_cols):
            fi["importance"] = imp
    fi = fi.sort_values("importance", ascending=False)
    fi.to_csv(out_dir / f"{method_name.lower()}_feature_importance.csv", index=False)

    meta = {
        "method_name": method_name,
        "best_model": best_name,
        "calibration_used": calib_used,
        "feature_count": len(fit_cols),
        "include_dataset": include_dataset,
        "cat_cols": cat_cols,
        "num_cols": num_cols,
    }
    (out_dir / f"{method_name.lower()}_meta.json").write_text(json.dumps(meta, indent=2))

    return eval_df, meta, cal_df


def train_d8_1b(pool: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    p = pool.copy()
    if "oracle_available" not in p.columns:
        return pd.DataFrame(), {"trained": False, "reason": "missing_oracle_available"}, pd.DataFrame()

    use_num = [c for c in p.columns if c not in {"pool_id", "scenario_id", "provider", "dataset", "split", "oracle_available", "all_sources_wrong", "predicted_instance_type_mode"}]

    def mat(sub: pd.DataFrame, fit_cols: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
        x = sub[["provider", "dataset", "scenario_id", "predicted_instance_type_mode"] + use_num].copy()
        for c in use_num:
            x[c] = pd.to_numeric(x[c], errors="coerce").fillna(0.0)
        for c in ["provider", "dataset", "scenario_id", "predicted_instance_type_mode"]:
            x[c] = x[c].fillna("unknown").astype(str)
        x = pd.get_dummies(x, columns=["provider", "dataset", "scenario_id", "predicted_instance_type_mode"], dummy_na=False)
        if fit_cols is not None:
            for c in fit_cols:
                if c not in x.columns:
                    x[c] = 0
            x = x[fit_cols]
        return x, x.columns.tolist()

    tr = p[p["split"] == "train"].copy()
    va = p[p["split"] == "validation"].copy()
    te = p[p["split"] == "test"].copy()
    sd = p[p["split"] == "seen_dev"].copy()
    if tr.empty:
        return pd.DataFrame(), {"trained": False, "reason": "missing_train"}, pd.DataFrame()

    Xtr, fit_cols = mat(tr)
    ytr = tr["oracle_available"].astype(int).values

    mdl = HistGradientBoostingClassifier(max_depth=6, learning_rate=0.06, max_iter=250, random_state=42)
    mdl.fit(Xtr, ytr)

    rows = []
    pred_rows = []
    for split, sub in [("train", tr), ("validation", va), ("test", te), ("seen_dev", sd)]:
        if sub.empty:
            continue
        X, _ = mat(sub, fit_cols)
        p_or = mdl.predict_proba(X)[:, 1]
        y = sub["oracle_available"].astype(int).values
        y_wrong = sub["all_sources_wrong"].astype(int).values if "all_sources_wrong" in sub.columns else 1 - y
        yhat = (p_or >= 0.5).astype(int)
        auc = float(roc_auc_score(y, p_or)) if len(np.unique(y)) >= 2 else float("nan")
        brier = float(brier_score_loss(y, np.clip(p_or, 1e-6, 1 - 1e-6)))
        prec, rec, _, _ = precision_recall_fscore_support(y_wrong, (1 - yhat), average="binary", zero_division=0)
        rows.append(
            {
                "split": split,
                "n": int(len(sub)),
                "auc_oracle_available": auc,
                "brier_oracle_available": brier,
                "ece_oracle_available": ece(y, p_or),
                "accuracy_oracle_available": float((yhat == y).mean()),
                "precision_all_sources_wrong": float(prec),
                "recall_all_sources_wrong": float(rec),
            }
        )
        ss = sub.copy()
        ss["d8_1b_oracle_prob"] = p_or
        pred_rows.append(ss)

    rep = pd.DataFrame(rows)
    pred = pd.concat(pred_rows, ignore_index=True) if pred_rows else pd.DataFrame()
    rep.to_csv(out_dir / "d8_1b_oracle_classifier_summary.csv", index=False)
    pred.to_csv(out_dir / "d8_1b_pool_predictions.csv", index=False)
    meta = {"trained": True, "feature_count": len(fit_cols)}
    return rep, meta, pred


def train_d8_1c(cand: pd.DataFrame, base: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    policies = pick_baseline_policy_by_scenario(base)
    pool = base.merge(policies, on="scenario_id", how="left")

    default_pool = pool[["pool_id", "scenario_id", "provider", "dataset", "split", "baseline_policy", "baseline_policy_acc_ref"] + [c for c in FIXED_BASELINES if c in pool.columns]].drop_duplicates("pool_id")

    def baseline_method_for_row(r: pd.Series) -> str:
        pol = str(r.get("baseline_policy", "select_frontier_correct"))
        if pol.startswith("select_"):
            return pol.replace("select_", "external_").replace("frontier", "direct_reserve_semantic_frontier_v2").replace("l1", "l1_max").replace("s1", "s1_budget_forcing").replace("tale", "tale_prompt_budgeting")
        if pol == "pooled4_plurality_correct":
            alias = str(r.get("pooled4_plurality_selected_method", "frontier")).strip().lower()
            return ALIAS_TO_METHOD.get(alias, ALIAS_TO_METHOD["frontier"])
        if pol == "agreement_largest_cluster_correct":
            alias = str(r.get("agreement_largest_cluster_selected_method", "frontier")).strip().lower()
            return ALIAS_TO_METHOD.get(alias, ALIAS_TO_METHOD["frontier"])
        if pol == "agreement_strict_2plus_correct":
            alias = str(r.get("agreement_strict_2plus_selected_method", "frontier")).strip().lower()
            return ALIAS_TO_METHOD.get(alias, ALIAS_TO_METHOD["frontier"])
        return ALIAS_TO_METHOD["frontier"]

    # baseline correctness and method per pool
    pool_map = {}
    for _, r in pool.iterrows():
        pol = str(r.get("baseline_policy", "select_frontier_correct"))
        m, c = baseline_policy_to_method(r, pol)
        pool_map[r["pool_id"]] = (m, int(c))

    c = cand.copy()
    c["baseline_method"] = c["pool_id"].map(lambda p: pool_map.get(p, (ALIAS_TO_METHOD["frontier"], 0))[0])
    c["baseline_correct"] = c["pool_id"].map(lambda p: pool_map.get(p, (ALIAS_TO_METHOD["frontier"], 0))[1])
    c["is_baseline_candidate"] = (c["method"] == c["baseline_method"]).astype(int)

    nb = c[c["is_baseline_candidate"] == 0].copy()
    nb["override_good"] = ((nb["action_correct"] == 1) & (nb["baseline_correct"] == 0)).astype(int)
    nb["override_bad"] = ((nb["action_correct"] == 0) & (nb["baseline_correct"] == 1)).astype(int)

    feat_cat = [
        c for c in ["provider", "scenario_id", "method", "predicted_instance_type", "predicted_answer_type", "action_family"] if c in nb.columns
    ]
    feat_num = [
        c
        for c in [
            "pred_prob",
            "candidate_cluster_size_rt",
            "candidate_in_largest_cluster_rt",
            "agreement_entropy_rt",
            "rel_provider_method_acc_foldsafe",
            "rel_instype_method_acc_foldsafe",
            "rel_provider_instype_method_acc_foldsafe",
            "rel_unique_correct_rate_provider_method_foldsafe",
            "pair_rescue_l1_provider_foldsafe",
            "pair_rescue_s1_provider_foldsafe",
            "pair_rescue_tale_provider_foldsafe",
            "pair_disagree_l1_provider_foldsafe",
            "pair_disagree_s1_provider_foldsafe",
            "pair_disagree_tale_provider_foldsafe",
            "problem_token_count_simple",
            "multi_step_cue_count",
        ]
        if c in nb.columns
    ]

    tr = nb[nb["split"] == "train"].copy()
    va = nb[nb["split"] == "validation"].copy()
    te = nb[nb["split"] == "test"].copy()
    sd = nb[nb["split"] == "seen_dev"].copy()

    if tr.empty:
        return pd.DataFrame(), {"trained": False, "reason": "missing_train"}, pd.DataFrame()

    Xtr, fit_cols = make_matrix(tr, feat_cat, feat_num)
    ytr = tr["override_good"].astype(int).values
    model = HistGradientBoostingClassifier(max_depth=6, learning_rate=0.06, max_iter=250, random_state=42)
    model.fit(Xtr, ytr)

    all_nb = pd.concat([tr, va, te, sd], ignore_index=True)
    Xall, _ = make_matrix(all_nb, feat_cat, feat_num, fit_cols)
    all_nb["override_prob"] = model.predict_proba(Xall)[:, 1]

    # threshold sweep on validation with guard
    val_pools = base[base["split"] == "validation"]["pool_id"].drop_duplicates().tolist()
    baseline_val_acc = float(base[base["split"] == "validation"]["select_l1_correct"].mean()) if not base[base["split"] == "validation"].empty else 0.0

    def apply_threshold(tau: float, pool_ids: list[Any]) -> tuple[float, float]:
        sel = []
        for pid in pool_ids:
            pbase = pool_map.get(pid, (ALIAS_TO_METHOD["frontier"], 0))
            pred_correct = pbase[1]
            over = 0
            g = all_nb[all_nb["pool_id"] == pid]
            if not g.empty:
                top = g.sort_values("override_prob", ascending=False).iloc[0]
                if float(top["override_prob"]) >= tau:
                    pred_correct = int(top["action_correct"])
                    over = 1
            sel.append({"pool_id": pid, "pred_correct": pred_correct, "override": over})
        s = pd.DataFrame(sel)
        if s.empty:
            return 0.0, 0.0
        return float(s["pred_correct"].mean()), float(s["override"].mean())

    trs = np.linspace(0.5, 0.9, 17)
    trows = []
    best_tau = 0.75
    best_acc = -1.0
    for tau in trs:
        vacc, cov = apply_threshold(float(tau), val_pools)
        delta = vacc - baseline_val_acc
        trows.append({"tau": float(tau), "validation_accuracy": vacc, "override_rate": cov, "delta_vs_baseline": delta})
        if delta >= -0.002 and vacc > best_acc:
            best_acc = vacc
            best_tau = float(tau)

    pd.DataFrame(trows).to_csv(out_dir / "d8_1c_threshold_sweep.csv", index=False)

    # Build selected top1 per pool
    sel_rows = []
    for pid, psub in cand.groupby("pool_id"):
        pbase = pool_map.get(pid, (ALIAS_TO_METHOD["frontier"], 0))
        base_m, base_c = pbase
        top_g = all_nb[all_nb["pool_id"] == pid]
        if top_g.empty:
            rr = psub[psub["method"] == base_m]
            chosen = rr.iloc[0] if not rr.empty else psub.iloc[0]
            sel_rows.append({**chosen.to_dict(), "override_applied": 0, "override_prob": 0.0, "candidate_correct": int(base_c)})
            continue
        top = top_g.sort_values("override_prob", ascending=False).iloc[0]
        if float(top["override_prob"]) >= best_tau:
            chosen = psub[(psub["method"] == top["method"]) & (psub["normalized_answer"] == top["normalized_answer"]) ]
            if chosen.empty:
                chosen = psub[psub["method"] == top["method"]]
            chosen = chosen.iloc[0] if not chosen.empty else psub.iloc[0]
            sel_rows.append({**chosen.to_dict(), "override_applied": 1, "override_prob": float(top["override_prob"])})
        else:
            rr = psub[psub["method"] == base_m]
            chosen = rr.iloc[0] if not rr.empty else psub.iloc[0]
            sel_rows.append({**chosen.to_dict(), "override_applied": 0, "override_prob": float(top["override_prob"])})

    selected = pd.DataFrame(sel_rows)
    selected["candidate_correct"] = selected["action_correct"].astype(int)
    selected.to_csv(out_dir / "d8_1c_selected_top1.csv", index=False)
    all_nb.to_csv(out_dir / "d8_1c_override_decisions.csv", index=False)

    fo = selected[(selected["override_applied"] == 1) & (selected["candidate_correct"] == 0)].copy()
    fo.to_csv(out_dir / "d8_1_false_override_cases.csv", index=False)

    eval_df = scenario_eval(selected, base, "D8_1C")
    eval_df.to_csv(out_dir / "d8_1c_results_by_scenario.csv", index=False)

    meta = {"trained": True, "best_threshold": best_tau, "guard_floor_delta_pp": -0.2, "feature_count": len(fit_cols)}
    return eval_df, meta, selected


def train_d8_1d_ranker(cand: pd.DataFrame, base: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    num_cols = [
        c
        for c in [
            "candidate_output_length_rt",
            "candidate_answer_length_rt",
            "candidate_reasoning_length_rt",
            "numeric_candidate_flag_rt",
            "expression_candidate_flag_rt",
            "malformed_answer_flag_rt",
            "pool_size_rt",
            "distinct_clusters_rt",
            "largest_cluster_size_rt",
            "candidate_cluster_size_rt",
            "candidate_in_largest_cluster_rt",
            "agreement_entropy_rt",
            "answer_fragmentation_ratio_rt",
            "rel_provider_method_acc_foldsafe",
            "rel_instype_method_acc_foldsafe",
            "rel_provider_instype_method_acc_foldsafe",
            "rel_unique_correct_rate_provider_method_foldsafe",
            "multi_step_cue_count",
            "problem_token_count_simple",
            "problem_numeric_token_count_rt",
            "problem_max_abs_numeric_magnitude_rt",
        ]
        if c in cand.columns
    ]

    tr = cand[cand["split"] == "train"].copy()
    te = cand[cand["split"].isin(["validation", "test", "seen_dev"])].copy()
    if tr.empty:
        return pd.DataFrame(), {"trained": False, "reason": "missing_train"}, pd.DataFrame()

    model_name = "fallback_hgb_regressor"
    ranker: Any = None

    try:
        from lightgbm import LGBMRanker  # type: ignore

        ranker = LGBMRanker(objective="lambdarank", n_estimators=250, learning_rate=0.05, random_state=42)
        model_name = "lightgbm_lambdarank"
    except Exception:
        try:
            from xgboost import XGBRanker  # type: ignore

            ranker = XGBRanker(objective="rank:pairwise", n_estimators=300, max_depth=7, learning_rate=0.05, random_state=42)
            model_name = "xgboost_ranker"
        except Exception:
            ranker = HistGradientBoostingRegressor(max_depth=8, learning_rate=0.05, max_iter=300, random_state=42)
            model_name = "fallback_hgb_regressor"

    Xtr = tr[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    ytr = tr["action_correct"].astype(int).values
    if model_name in {"lightgbm_lambdarank", "xgboost_ranker"}:
        grp = tr.groupby("pool_id").size().astype(int).tolist()
        ranker.fit(Xtr, ytr, group=grp)
    else:
        ranker.fit(Xtr, ytr)

    pred = pd.concat([tr, te], ignore_index=True).copy()
    Xp = pred[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    pred["ranking_score"] = ranker.predict(Xp)
    pred.to_csv(out_dir / "d8_1d_ranking_scores.csv", index=False)

    selected = pool_top1(pred, "ranking_score")
    selected["candidate_correct"] = selected["action_correct"].astype(int)
    selected.to_csv(out_dir / "d8_1d_selected_top1.csv", index=False)

    eval_df = scenario_eval(selected, base, "D8_1D")
    eval_df.to_csv(out_dir / "d8_1d_results_by_scenario.csv", index=False)

    zero_grp = pred.groupby("pool_id")["action_correct"].sum().reset_index()
    zero_grp = zero_grp[zero_grp["action_correct"] == 0]
    zero_grp.to_csv(out_dir / "d8_1d_all_zero_group_analysis.csv", index=False)

    meta = {"trained": True, "model": model_name, "feature_count": len(num_cols)}
    return eval_df, meta, selected


def run_d8_1e_cluster_selector(cand: pd.DataFrame, base: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    # Deterministic reliability-weighted cluster voting (no paid APIs)
    rows = []
    for pid, g in cand.groupby("pool_id"):
        gg = g.copy()
        if "answer_cluster_id" not in gg.columns:
            top = gg.sort_values("candidate_cluster_size_rt", ascending=False).iloc[0]
            rows.append(top)
            continue

        # cluster score: mean reliability * cluster size
        cl_rows = []
        for cid, sub in gg.groupby("answer_cluster_id", dropna=False):
            rel = float(pd.to_numeric(sub.get("rel_provider_instype_method_acc_foldsafe", 0.5), errors="coerce").fillna(0.5).mean())
            size = float(pd.to_numeric(sub.get("candidate_cluster_size_rt", 1.0), errors="coerce").fillna(1.0).mean())
            score = rel * max(size, 1.0)
            cl_rows.append((cid, score))
        best_cid = sorted(cl_rows, key=lambda t: t[1], reverse=True)[0][0] if cl_rows else None
        cand_in = gg[gg["answer_cluster_id"] == best_cid] if best_cid is not None else gg
        if cand_in.empty:
            cand_in = gg
        cand_in = cand_in.sort_values("rel_provider_instype_method_acc_foldsafe", ascending=False)
        rows.append(cand_in.iloc[0])

    selected = pd.DataFrame(rows)
    selected["candidate_correct"] = selected["action_correct"].astype(int)
    selected.to_csv(out_dir / "d8_1e_selected_top1.csv", index=False)

    eval_df = scenario_eval(selected, base, "D8_1E")
    eval_df.to_csv(out_dir / "d8_1e_results_by_scenario.csv", index=False)
    return eval_df, {"trained": True, "mode": "deterministic_reliability_weighted_cluster"}, selected


def merge_rankings(existing_rank_paths: list[Path], new_eval_frames: list[pd.DataFrame], out_dir: Path) -> pd.DataFrame:
    frames = []
    for p in existing_rank_paths:
        if p.exists():
            try:
                old = pd.read_csv(p)
                need = [
                    "split",
                    "scenario_id",
                    "provider",
                    "dataset",
                    "method",
                    "n_pools",
                    "accuracy",
                    "best_corrected_fixed_baseline",
                    "best_corrected_fixed_baseline_acc",
                    "delta_vs_best_corrected_fixed_baseline",
                    "win_tie_loss_vs_best_baseline",
                    "oracle_upper_bound",
                    "oracle_gap_recovered",
                    "is_oracle",
                ]
                for c in need:
                    if c not in old.columns:
                        old[c] = np.nan
                old = old[need].copy()
                frames.append(old)
            except Exception:
                pass

    for df in new_eval_frames:
        if df is None or df.empty:
            continue
        frames.append(df.copy())

    if not frames:
        return pd.DataFrame()

    combo = pd.concat(frames, ignore_index=True)
    combo = combo.drop_duplicates(subset=["split", "scenario_id", "provider", "dataset", "method"], keep="last")
    combo.to_csv(out_dir / "d8_1_scenario_method_rankings.csv", index=False)

    scen = {}
    for sid, g in combo.groupby("scenario_id"):
        scen[sid] = g.sort_values("accuracy", ascending=False).to_dict(orient="records")
    (out_dir / "d8_1_scenario_method_rankings.json").write_text(json.dumps(scen, indent=2))
    return combo


def build_scenario_defeat_matrix(combo: pd.DataFrame, bsum: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    rows = []
    methods_ours = [m for m in combo["method"].dropna().astype(str).unique().tolist() if m.startswith("D") or m.startswith("d")]
    for (spl, sid, prov, ds), g in combo.groupby(["split", "scenario_id", "provider", "dataset"]):
        base_acc = float(g["best_corrected_fixed_baseline_acc"].max()) if "best_corrected_fixed_baseline_acc" in g.columns else float("nan")
        base_name = sorted(g["best_corrected_fixed_baseline"].dropna().astype(str).unique().tolist())
        base_name_str = ";".join(base_name) if base_name else "unknown"

        best_our = g[g["method"].isin(methods_ours)]
        if best_our.empty:
            best_our_m = "none"
            best_our_acc = float("nan")
        else:
            best_row = best_our.sort_values("accuracy", ascending=False).iloc[0]
            best_our_m = str(best_row["method"])
            best_our_acc = float(best_row["accuracy"])

        d8_1a = g[g["method"] == "D8_1A"]["accuracy"]
        d8_1a_nd = g[g["method"] == "D8_1A_NO_DATASET"]["accuracy"]
        d8_1c = g[g["method"] == "D8_1C"]["accuracy"]
        d8_1d = g[g["method"] == "D8_1D"]["accuracy"]
        d8_1e = g[g["method"] == "D8_1E"]["accuracy"]

        bsub = bsum[(bsum["split"] == spl)] if not bsum.empty and "split" in bsum.columns else pd.DataFrame()

        defeated = bool(best_our_acc > base_acc + 1e-12) if not np.isnan(best_our_acc) and not np.isnan(base_acc) else False
        margin = best_our_acc - base_acc if not np.isnan(best_our_acc) and not np.isnan(base_acc) else float("nan")
        oracle = float(g["oracle_upper_bound"].max()) if "oracle_upper_bound" in g.columns else float("nan")
        gap = oracle - best_our_acc if not np.isnan(oracle) and not np.isnan(best_our_acc) else float("nan")

        if defeated:
            ftype = "already_defeated"
            fix = "keep_D8_1_module"
        elif not np.isnan(gap) and gap > 0.2:
            ftype = "pool_quality_failure"
            fix = "D6_frontier_improvement"
        elif spl == "seen_dev":
            ftype = "provisional_data_issue"
            fix = "more_data_needed"
        else:
            ftype = "feature_weakness"
            fix = "more_problem_features"

        rows.append(
            {
                "split": spl,
                "scenario_id": sid,
                "provider": prov,
                "dataset": ds,
                "best_corrected_external_fixed_baseline": base_name_str,
                "best_baseline_accuracy": base_acc,
                "D8_1A_accuracy": float(d8_1a.iloc[0]) if len(d8_1a) else np.nan,
                "D8_1A_no_dataset_accuracy": float(d8_1a_nd.iloc[0]) if len(d8_1a_nd) else np.nan,
                "D8_1C_accuracy": float(d8_1c.iloc[0]) if len(d8_1c) else np.nan,
                "D8_1D_accuracy": float(d8_1d.iloc[0]) if len(d8_1d) else np.nan,
                "D8_1E_accuracy": float(d8_1e.iloc[0]) if len(d8_1e) else np.nan,
                "D8_1B_auc_oracle_available": float(bsub["auc_oracle_available"].iloc[0]) if not bsub.empty and "auc_oracle_available" in bsub.columns else np.nan,
                "best_our_method": best_our_m,
                "best_our_accuracy": best_our_acc,
                "defeated_baseline": int(defeated),
                "margin_vs_baseline": margin,
                "oracle_upper_bound": oracle,
                "remaining_gap_to_oracle": gap,
                "current_failure_type": ftype,
                "recommended_next_fix": fix,
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "d8_1_scenario_defeat_matrix.csv", index=False)
    return out


def build_frontier_contribution(cand: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    rows = []
    for sid, g in cand.groupby("scenario_id"):
        p = g.pivot_table(index="pool_id", columns="method", values="action_correct", aggfunc="max").fillna(0)
        for m in METHODS:
            if m not in p.columns:
                p[m] = 0
        frontier = p[ALIAS_TO_METHOD["frontier"]] if ALIAS_TO_METHOD["frontier"] in p.columns else p["direct_reserve_semantic_frontier_v2"]
        l1 = p["external_l1_max"]
        s1 = p["external_s1_budget_forcing"]
        tale = p["external_tale_prompt_budgeting"]
        ext = np.maximum(np.maximum(l1, s1), tale)
        rows.append(
            {
                "scenario_id": sid,
                "frontier_rate": float(frontier.mean()),
                "best_external_rate": float(ext.mean()),
                "frontier_unique_correct_rate": float(((frontier == 1) & (ext == 0)).mean()),
                "external_unique_correct_rate": float(((frontier == 0) & (ext == 1)).mean()),
                "all_sources_wrong_rate": float(((frontier == 0) & (ext == 0)).mean()),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "d8_1_frontier_contribution_summary.csv", index=False)
    return out


def update_ledger_and_backlog(repo: Path, run_id: str, out_dir: Path, gsum: dict[str, Any], decision: str) -> None:
    led_csv = repo / "outputs/training_experiment_ledger_20260525/training_experiment_ledger.csv"
    led_md = repo / "outputs/training_experiment_ledger_20260525/training_experiment_ledger.md"
    back_md = repo / "outputs/training_experiment_ledger_20260525/training_backlog.md"

    row = {
        "run_id": run_id,
        "date_time_utc": now_utc(),
        "input_table_path": "outputs/unified_learning_tables_20260525/run_20260525T184354Z",
        "output_path": str(out_dir.relative_to(repo)),
        "model_families_tried": "d8_1a+d8_1a_no_dataset+d8_1b+d8_1c+d8_1d+d8_1e",
        "feature_groups_used": "runtime_visible_problem_provider_candidate_pool+foldsafe_rel_comp",
        "reliability_features_used": "yes",
        "complementarity_features_used": "yes",
        "calibration_used": "yes_if_validation_supported",
        "gpu_used": "unknown",
        "clean_test_wins_ties_losses": gsum.get("d8_1a_clean_wtl", ""),
        "seen_dev_wins_ties_losses": gsum.get("d8_1a_seen_wtl", ""),
        "macro_accuracy": np.nan,
        "worst_scenario_accuracy": np.nan,
        "biggest_losses": "see d8_1_scenario_defeat_matrix.csv",
        "promotion_decision": decision,
        "next_recommended_training": "D8.1 feature refinement vs D6 blocker fixes",
    }

    if led_csv.exists():
        old = pd.read_csv(led_csv)
        old = pd.concat([old, pd.DataFrame([row])], ignore_index=True)
    else:
        old = pd.DataFrame([row])
    old.to_csv(led_csv, index=False)

    if led_md.exists():
        md = led_md.read_text()
    else:
        md = "# Training Experiment Ledger\n"
    md += f"\n- D8.1 runtime-feature selector run completed: `{out_dir.relative_to(repo)}`\n"
    led_md.write_text(md)

    if back_md.exists():
        b = back_md.read_text()
    else:
        b = "# Training Backlog\n"
    b += (
        "\n- D8.1 run logged. If scenario defeats remain on MATH-500, prioritize either additional runtime-visible"
        " feature refinement or D6 frontier-improvement blockers before API generation approval.\n"
    )
    back_md.write_text(b)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--session-name", default="job_d8_1_runtime_feature_learning_selectors_20260526")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    out_dir = Path(args.run_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    unified_dir = repo / "outputs/unified_learning_tables_20260525/run_20260525T184354Z"
    baseline_dir = repo / "outputs/baseline_selector_definition_audit_20260525/run_20260525T194246Z"
    existing_rank_1 = repo / "outputs/project_state_and_branch_audit_20260525/run_20260525T214516Z/scenario_method_rankings.csv"
    existing_rank_2 = repo / "outputs/job_d8_foldsafe_learning_selectors_20260525/run_20260525T221353Z/d8_scenario_method_rankings.csv"

    # Build features
    run_cmd(
        [
            "python3",
            "scripts/d8_1_build_runtime_feature_tables.py",
            "--unified-dir",
            str(unified_dir),
            "--baseline-dir",
            str(baseline_dir),
            "--output-dir",
            str(out_dir),
        ],
        repo,
    )

    cand = pd.read_csv(out_dir / "d8_1_candidate_features.csv")
    pool = pd.read_csv(out_dir / "d8_1_pool_features.csv")
    base = pd.read_csv(baseline_dir / "corrected_baseline_pool_decisions.csv")

    # D8.1A and no-dataset ablation
    eval_a, meta_a, cal_a = train_d8_1a(cand, base, out_dir, include_dataset=True, method_name="D8_1A")
    eval_a_nd, meta_a_nd, cal_a_nd = train_d8_1a(cand, base, out_dir, include_dataset=False, method_name="D8_1A_NO_DATASET")

    # D8.1B
    rep_b, meta_b, pred_b = train_d8_1b(pool, out_dir)

    # D8.1C conservative override uses D8.1A probs
    pred_a = pd.read_csv(out_dir / "d8_1a_candidate_predictions.csv")
    cand_c = cand.merge(pred_a[["pool_id", "method", "normalized_answer", "split", "pred_prob"]], on=["pool_id", "method", "normalized_answer", "split"], how="left")
    eval_c, meta_c, selected_c = train_d8_1c(cand_c, base, out_dir)

    # D8.1D
    eval_d, meta_d, selected_d = train_d8_1d_ranker(cand, base, out_dir)

    # D8.1E
    eval_e, meta_e, selected_e = run_d8_1e_cluster_selector(cand, base, out_dir)

    # Combine eval/rankings
    combo = merge_rankings([existing_rank_1, existing_rank_2], [eval_a, eval_a_nd, eval_c, eval_d, eval_e], out_dir)

    # Diagnostics
    # oracle-available missed cases using D8.1A selected
    sel_a = pd.read_csv(out_dir / "d8_1a_selected_top1.csv")
    pool_or = base[["pool_id", "oracle_correct"]].drop_duplicates("pool_id")
    mm = sel_a.merge(pool_or, on="pool_id", how="left")
    mm["oracle_available"] = mm["oracle_correct"].map(bool_int)
    missed = mm[(mm["oracle_available"] == 1) & (mm["candidate_correct"] == 0)].copy()
    missed.to_csv(out_dir / "d8_1_oracle_available_missed_cases.csv", index=False)

    fsum = build_frontier_contribution(cand, out_dir)

    cal = pd.concat([cal_a, cal_a_nd], ignore_index=True) if not cal_a.empty or not cal_a_nd.empty else pd.DataFrame()
    if not rep_b.empty:
        rep_b2 = rep_b.copy()
        rep_b2["method"] = "D8_1B"
        cal = pd.concat([cal, rep_b2], ignore_index=True)
    cal.to_csv(out_dir / "d8_1_calibration_summary.csv", index=False)

    fi_frames = []
    for nm in ["d8_1a_feature_importance.csv", "d8_1a_no_dataset_feature_importance.csv"]:
        p = out_dir / nm
        if p.exists():
            f = pd.read_csv(p)
            f["source"] = nm.replace("_feature_importance.csv", "")
            fi_frames.append(f)
    if fi_frames:
        pd.concat(fi_frames, ignore_index=True).to_csv(out_dir / "d8_1_feature_importance.csv", index=False)

    # scenario defeat matrix
    dm = build_scenario_defeat_matrix(combo, rep_b, out_dir)

    # Failure diagnostics markdown
    lines = [
        "# D8.1 Failure Diagnostics",
        "",
        f"- Oracle-available missed pools (D8.1A): {len(missed)}",
        f"- False overrides (D8.1C): {len(pd.read_csv(out_dir / 'd8_1_false_override_cases.csv')) if (out_dir / 'd8_1_false_override_cases.csv').exists() else 0}",
        "- Priority scenarios: cohere_math500, cloudrift_math500, cohere_gsm8k, cloudrift_gsm8k, mistral_gsm8k.",
        "",
        "## Dominant unresolved slices",
    ]
    if not dm.empty:
        worst = dm.sort_values("margin_vs_baseline", ascending=True).head(10)
        for _, r in worst.iterrows():
            lines.append(f"- {r['scenario_id']} ({r['split']}): margin {r['margin_vs_baseline']:.4f}, failure={r['current_failure_type']}, fix={r['recommended_next_fix']}")
    (out_dir / "D8_1_FAILURE_DIAGNOSTICS.md").write_text("\n".join(lines) + "\n")

    # Global summary and promotion decision
    gsum = {
        "run_time_utc": now_utc(),
        "best_d8_1_variant_clean_test": None,
        "best_d8_1_variant_clean_test_mean_accuracy": None,
        "d8_1a_clean_wtl": summarize_wtl(combo, "D8_1A", "test") if not combo.empty else "0/0/0",
        "d8_1a_seen_wtl": summarize_wtl(combo, "D8_1A", "seen_dev") if not combo.empty else "0/0/0",
        "d8_1a_no_dataset_clean_wtl": summarize_wtl(combo, "D8_1A_NO_DATASET", "test") if not combo.empty else "0/0/0",
        "d8_1a_no_dataset_seen_wtl": summarize_wtl(combo, "D8_1A_NO_DATASET", "seen_dev") if not combo.empty else "0/0/0",
        "models": {
            "D8_1A": meta_a,
            "D8_1A_NO_DATASET": meta_a_nd,
            "D8_1B": meta_b,
            "D8_1C": meta_c,
            "D8_1D": meta_d,
            "D8_1E": meta_e,
        },
    }

    ctest = combo[(combo["split"] == "test") & (combo["method"].isin(["D8_1A", "D8_1A_NO_DATASET", "D8_1C", "D8_1D", "D8_1E"]))] if not combo.empty else pd.DataFrame()
    if not ctest.empty:
        means = ctest.groupby("method")["accuracy"].mean().sort_values(ascending=False)
        gsum["best_d8_1_variant_clean_test"] = str(means.index[0])
        gsum["best_d8_1_variant_clean_test_mean_accuracy"] = float(means.iloc[0])

    # promotability
    decision = "D8_1_NEEDS_MORE_FEATURES"
    if not dm.empty:
        clean_losses = int(((dm["split"] == "test") & (dm["defeated_baseline"] == 0)).sum())
        seen_losses = int(((dm["split"] == "seen_dev") & (dm["defeated_baseline"] == 0)).sum())
        if clean_losses == 0 and seen_losses == 0:
            decision = "D8_1_PROMOTE_GLOBAL"
        elif clean_losses == 0 and seen_losses > 0:
            decision = "D8_1_PROMOTE_AS_MODULE"
        elif seen_losses > 0:
            decision = "D8_1_FIX_D6_NEXT"

    (out_dir / "d8_1_global_summary.json").write_text(json.dumps(gsum, indent=2))
    (out_dir / "d8_1_promotability_decision.json").write_text(json.dumps({"decision": decision}, indent=2))

    # Scenario method rankings JSON already written by merge; ensure file exists for completeness
    if not (out_dir / "d8_1_scenario_method_rankings.json").exists():
        (out_dir / "d8_1_scenario_method_rankings.json").write_text("{}\n")

    # Results summary docs
    res = [
        "# D8.1 Results Summary",
        "",
        f"- Run directory: `{out_dir}`",
        f"- No API calls: yes",
        f"- Best D8.1 variant on clean test mean accuracy: {gsum.get('best_d8_1_variant_clean_test')} ({gsum.get('best_d8_1_variant_clean_test_mean_accuracy')})",
        f"- D8.1A clean-test W/T/L vs best corrected fixed baseline: {gsum['d8_1a_clean_wtl']}",
        f"- D8.1A seen-dev/provisional W/T/L: {gsum['d8_1a_seen_wtl']}",
        f"- D8.1A-no-dataset clean-test W/T/L: {gsum['d8_1a_no_dataset_clean_wtl']}",
        f"- D8.1A-no-dataset seen-dev/provisional W/T/L: {gsum['d8_1a_no_dataset_seen_wtl']}",
        "- Baselines used: corrected fixed-policy baselines only.",
        "- Oracle is upper bound only; row-wise max baseline not used.",
        "",
        decision,
    ]
    (out_dir / "D8_1_RESULTS_SUMMARY.md").write_text("\n".join(res) + "\n")

    next_actions = [
        "# D8.1 Next Actions",
        "",
        f"- Promotion decision: `{decision}`",
        "- If MATH-500 slices remain undefeated, prioritize D6 blocker fixes and frontier pool improvement before API generation approval.",
        "- Continue runtime-visible feature refinement where false overrides remain concentrated.",
        "- Keep no-dataset ablation in future runs to verify instance-level generalization.",
    ]
    (out_dir / "D8_1_NEXT_ACTIONS.md").write_text("\n".join(next_actions) + "\n")

    # Legacy-named files expected by prompt
    (out_dir / "d8_1_scenario_method_rankings.json").write_text((out_dir / "d8_1_scenario_method_rankings.json").read_text())

    # Update ledger/backlog
    update_ledger_and_backlog(repo, out_dir.name, out_dir, gsum, decision)


if __name__ == "__main__":
    main()
