#!/usr/bin/env python3
"""Train lightweight candidate scorers: grouped holdout by (example_id, seed, budget)."""
from __future__ import annotations

import argparse
import pickle
import random
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
import sys
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.learned_branch_scorer_utils import as_int, read_csv, write_csv, write_json

DIVERSE = "direct_reserve_strong_plus_diverse_v1"
MARGIN = "direct_reserve_strong_plus_diverse_margin_gated_v1"


def _gid(r: dict) -> str:
    return f"{r.get('example_id','')}|{r.get('seed','')}|{r.get('budget','')}"


def _feat(d: dict) -> dict[str, float]:
    out: dict[str, float] = {"m__" + str(d.get("method", "x")): 1.0}
    for k in (
        "branch_depth",
        "answer_group_support",
        "answer_group_rank",
        "action_count",
        "top2_support_gap",
        "answer_entropy",
        "n_methods_sharing_norm_answer",
        "selected_by_method",
        "match_strict_f3_final",
        "match_external_l1_max_final",
        "match_direct_reserve_strong_v1_final",
        "match_direct_reserve_strong_plus_diverse_v1_final",
        "extraction_ok",
        "problem_gold_present",
        "problem_present_not_selected",
        "diverse_gold_in_pool",
    ):
        try:
            v = d.get(k, 0) or 0
            s = str(v).replace("NA", "0")
            out["f_" + k] = float(s) if s else 0.0
        except Exception:
            out["f_" + k] = 0.0
    st = str(d.get("stratum", "u") or "u")
    out["f_strat__" + st[:32]] = 1.0
    p = str(d.get("prompt_style", "NA") or "NA")
    out["f_prompt__" + p[:32]] = 1.0
    stype = str(d.get("source_type", "b"))[:20]
    out["f_src__" + stype] = 1.0
    return out


def _build_pairs(
    tr_idx: list[int],
    rows: list[dict],
    y: list[int],
    gids: list[str],
) -> tuple[Any, Any]:
    by: dict[str, list[int]] = defaultdict(list)
    for k in tr_idx:
        by[gids[k]].append(k)
    rng = random.Random(0)
    feats: list[dict] = []
    lab: list[int] = []
    for g, ids in by.items():
        posi = [i for i in ids if y[i] == 1]
        negi = [i for i in ids if y[i] == 0]
        if not posi or not negi:
            continue
        n_pair = min(200, 10 * len(posi) * max(1, len(negi)))
        for t in range(n_pair):
            if t % 2 == 0:
                a, b = rng.choice(posi), rng.choice(negi)
                lab.append(1)
            else:
                a, b = rng.choice(negi), rng.choice(posi)
                lab.append(0)
            fa, fb = _feat(rows[a]), _feat(rows[b])
            ddiff: dict[str, float] = {}
            for k in set(fa) | set(fb):
                ddiff[k] = fa.get(k, 0.0) - fb.get(k, 0.0)
            feats.append(ddiff)
    if not feats or len(set(lab)) < 2:
        return None, None
    pv = DictVectorizer(sparse=False)
    Xp = pv.fit_transform(feats)
    plr = LogisticRegression(max_iter=1500, class_weight="balanced", solver="lbfgs", C=0.5)
    plr.fit(Xp, np.array(lab, dtype=int))
    return pv, plr


def _diverse_top1(
    te_idx: list[int],
    rows: list[dict],
    y: list[int],
    gids: list[str],
    te_s: set[str],
    s: np.ndarray,
) -> tuple[float, list[dict]]:
    by: dict[str, list[tuple[float, int, str, dict]]] = defaultdict(list)
    for p, k in enumerate(te_idx):
        if gids[k] not in te_s and te_s:
            continue
        if rows[k].get("method", "") != DIVERSE:
            continue
        g = gids[k]
        if p >= len(s):
            break
        by[g].append((float(s[p]), y[k], str(rows[k].get("stratum", "")), dict(rows[k])))
    rows_ = []
    for g, cands in by.items():
        if not cands:
            continue
        ch = max(cands, key=lambda t: t[0])
        rows_.append(
            {
                "group_id": g,
                "stratum": ch[2],
                "top1_hit": int(ch[1] == 1),
            }
        )
    rate = sum(1 for r in rows_ if r["top1_hit"]) / max(1, len(rows_))
    return rate, rows_


def _pair_diverse_top1(
    all_rows: list[dict],
    y: list[int],
    gids: list[str],
    te_s: set[str],
    pvec: Any,
    plr: Any,
) -> float:
    if len(all_rows) < 2 or pvec is None or plr is None:
        return float("nan")
    by: dict[str, list[int]] = defaultdict(list)
    for i, g in enumerate(gids):
        if g not in te_s and te_s:
            continue
        if all_rows[i].get("method", "") != DIVERSE:
            continue
        by[g].append(i)
    hit = 0
    n = 0
    for g, cands in by.items():
        if len(cands) < 2:
            continue
        scores: dict[int, float] = {j0: 0.0 for j0 in cands}
        for a, b in combinations(cands, 2):
            fa, fb = _feat(all_rows[a]), _feat(all_rows[b])
            d_ab: dict[str, float] = {k: fa.get(k, 0) - fb.get(k, 0) for k in set(fa) | set(fb)}
            s = float(plr.decision_function(pvec.transform([d_ab]))[0])
            scores[a] = scores.get(a, 0.0) + s
            scores[b] = scores.get(b, 0.0) - s
        best = max(cands, key=lambda j0: scores.get(j0, 0.0))
        n += 1
        if y[best] == 1:
            hit += 1
    return hit / max(1, n)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--dataset-dir", required=True)
    p.add_argument("--test-fraction", type=float, default=0.3)
    p.add_argument("--split-seed", type=int, default=7)
    p.add_argument(
        "--diverse-only",
        action="store_true",
        help="Use only direct_reserve_strong_plus_diverse_v1 rows (re-ranker).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    dpath = (REPO_ROOT / args.dataset_dir) if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    ex = dpath / "examples.csv"
    if not ex.exists():
        raise SystemExit(f"Missing {ex}")
    all_rows: list[dict] = [dict(r) for r in read_csv(ex) if as_int(r.get("excluded_from_training", 0), 0) == 0]
    if args.diverse_only:
        all_rows = [r for r in all_rows if r.get("method", "") == DIVERSE]
    if not all_rows:
        raise SystemExit("No rows to train on.")
    y = [as_int(r.get("is_gold_candidate", 0), 0) for r in all_rows]
    gids = [_gid(r) for r in all_rows]
    g_uniq = sorted(set(gids))
    rng = random.Random(args.split_seed)
    sh = list(g_uniq)
    rng.shuffle(sh)
    n_te = max(1, int(round(len(g_uniq) * float(args.test_fraction)))) if g_uniq else 0
    n_te = min(n_te, max(0, len(sh) - 1)) if len(sh) > 1 else 1
    if len(sh) <= 1:
        te_s, tr_s = {sh[0] if sh else ""}, {sh[0] if sh else ""}
    else:
        te_s, tr_s = set(sh[:n_te]), set(sh[n_te:])
    tr_idx = [i for i, g in enumerate(gids) if g in tr_s]
    te_idx = [i for i, g in enumerate(gids) if g in te_s]
    if not tr_idx or tr_idx == te_idx:
        tr_idx, te_idx = list(range(len(all_rows))), list(range(len(all_rows)))
        te_s = tr_s = set(g_uniq)

    vec = DictVectorizer(sparse=False)
    Xtr = vec.fit_transform([_feat(all_rows[i]) for i in tr_idx])
    ytr = np.array([y[i] for i in tr_idx], dtype=int)
    Xte = vec.transform([_feat(all_rows[i]) for i in te_idx])
    yte = np.array([y[i] for i in te_idx], dtype=int)

    lr = LogisticRegression(max_iter=3000, class_weight="balanced", solver="lbfgs", C=0.4)
    lr.fit(Xtr, ytr)
    rf = RandomForestClassifier(
        n_estimators=120, max_depth=5, class_weight="balanced", random_state=args.split_seed, n_jobs=-1
    )
    rf.fit(Xtr, ytr)
    hgb = HistGradientBoostingClassifier(
        max_iter=180, max_depth=4, class_weight="balanced", learning_rate=0.08, random_state=args.split_seed
    )
    hgb.fit(Xtr, ytr)

    def _auc(yt, sc) -> float:
        try:
            if len(yt) == 0 or len(np.unique(yt)) < 2:
                return float("nan")
            return float(roc_auc_score(yt, sc))
        except Exception:
            return float("nan")

    s_lr = lr.decision_function(Xte) if Xte.shape[0] else np.array([])
    s_rf = rf.predict_proba(Xte)[:, 1] if Xte.shape[0] else np.array([])
    s_hg = hgb.predict_proba(Xte)[:, 1] if Xte.shape[0] else np.array([])

    t1_lr, _ = _diverse_top1(te_idx, all_rows, y, gids, te_s, s_lr)
    t1_rf, _ = _diverse_top1(te_idx, all_rows, y, gids, te_s, s_rf)
    t1_hg, _ = _diverse_top1(te_idx, all_rows, y, gids, te_s, s_hg)
    pair_vec, pair_lr = _build_pairs(tr_idx, all_rows, y, gids)
    t1_pair: float
    t1_pair = _pair_diverse_top1(all_rows, y, gids, te_s, pair_vec, pair_lr) if (pair_vec and pair_lr) else float("nan")
    out = REPO_ROOT / "outputs" / f"direct_reserve_candidate_scorer_train_{args.timestamp}"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "selected_model.joblib").open("wb") as f:
        payload: dict = {"vectorizer": vec, "logistic": lr, "rf": rf, "hgb": hgb, "diverse": DIVERSE}
        if pair_vec is not None and pair_lr is not None:
            payload["pair_vectorizer"] = pair_vec
            payload["pair_logit"] = pair_lr
        pickle.dump(payload, f)
    mrows = [
        {
            "model": "logistic",
            "candidate_auc": _auc(yte, s_lr),
            "candidate_accuracy": float(accuracy_score(yte, s_lr > 0)) if len(yte) else float("nan"),
            "diverse_top1": t1_lr,
        },
        {
            "model": "random_forest",
            "candidate_auc": _auc(yte, s_rf),
            "candidate_accuracy": float(accuracy_score(yte, (s_rf >= 0.5).astype(int))) if len(yte) else float("nan"),
            "diverse_top1": t1_rf,
        },
        {
            "model": "hist_gboost",
            "candidate_auc": _auc(yte, s_hg),
            "candidate_accuracy": float(accuracy_score(yte, (s_hg >= 0.5).astype(int))) if len(yte) else float("nan"),
            "diverse_top1": t1_hg,
        },
    ]
    if pair_vec is not None and pair_lr is not None:
        mrows.append(
            {
                "model": "pairwise_logit",
                "candidate_auc": float("nan"),
                "candidate_accuracy": float("nan"),
                "diverse_top1": t1_pair,
            }
        )
    write_csv(out / "metrics.csv", mrows)
    write_csv(out / "model_comparison.csv", mrows)
    write_csv(
        out / "predictions.csv",
        [
            {
                "row_id": all_rows[k].get("row_id", ""),
                "example_id": all_rows[k].get("example_id", ""),
                "y_true": y[k],
                "p_logit": float(s_lr[j] if j < len(s_lr) else 0),
                "p_rf": float(s_rf[j] if j < len(s_rf) else 0),
                "p_hgb": float(s_hg[j] if j < len(s_hg) else 0),
            }
            for j, k in enumerate(te_idx)
        ],
    )
    write_csv(
        out / "split_assignments.csv",
        [{"group_id": g, "partition": "test" if g in te_s else "train"} for g in g_uniq],
    )
    write_json(
        out / "model_manifest.json",
        {
            "diverse_only": args.diverse_only,
            "n_rows": len(all_rows),
            "n_problems": len(g_uniq),
            "n_positive": int(sum(y)),
            "test_group_ids": sorted(te_s),
        },
    )
    write_csv(out / "case_level_selection_metrics.csv", mrows)
    write_csv(
        out / "split_metrics.csv",
        [
            {
                "split": "test",
                "diverse_top1_logit": t1_lr,
                "diverse_top1_rf": t1_rf,
            }
        ],
    )
    write_csv(out / "improvement_cases.csv", [])
    write_csv(out / "degradation_cases.csv", [])
    (out / "README.md").write_text(
        "Trained logit / random forest / HGB on candidate `is_gold_candidate`. "
        "Grouped test split: test groups in model_manifest. "
        "`diverse_top1` = fraction of test cases where the highest-scoring *diverse* row is gold.\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {out} diverse_top1: logit={t1_lr:.3f} rf={t1_rf:.3f} hgb={t1_hg:.3f} pair={t1_pair!s}"
    )


if __name__ == "__main__":
    main()
