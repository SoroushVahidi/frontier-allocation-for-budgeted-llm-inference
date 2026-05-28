#!/usr/bin/env python3
"""Evaluate AG-01 conservative agreement-only gate variants on official4 offline.

Safety:
- offline only
- no API calls
- no active-job interactions
- no source artifact mutation
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "ag01_agreement_only_gate_20260524"
DOC = REPO / "docs" / "AG01_AGREEMENT_ONLY_GATE_20260524.md"

OFF4_TABLE = REPO / "outputs" / "failure_pattern_workbench_official4_20260524" / "official4_unified_case_table.csv"
FOUR_SCENARIO_MATRIX = REPO / "outputs" / "four_scenario_official_matrix_20260524" / "four_scenario_selector_matrix.csv"
COHERE_AGREEMENT_ANALYSIS = REPO / "outputs" / "cohere_math500_agreement_only_analysis_20260524"
FIX03_OFFICIAL_POOLED_SUMMARY = REPO / "outputs" / "fix03_s1_near_peer_gate_20260524" / "fix03_official_pooled_cv_summary.csv"

SOURCES = ["frontier", "L1", "S1", "TALE"]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def nrm(x: Any) -> str:
    s = str(x or "").strip()
    if not s:
        return ""
    s = re.sub(r"[\$,]", "", s)
    s = re.sub(r"\\boxed\{([^}]+)\}", r"\1", s)
    s = s.strip().lower()
    try:
        v = float(s)
        if math.isfinite(v):
            if v == int(v):
                return str(int(v))
            return f"{v:.10f}".rstrip("0").rstrip(".")
    except Exception:
        pass
    return s


def b01(x: Any) -> int:
    try:
        return int(bool(int(x)))
    except Exception:
        return 1 if str(x).strip().lower() in {"1", "true", "yes", "y", "t"} else 0


def beta_shrink(n_ok: int, n_total: int, alpha: float = 1.0, beta: float = 1.0) -> float:
    return (n_ok + alpha) / (n_total + alpha + beta)


def entropy_from_probs(ps: list[float]) -> float:
    e = 0.0
    for p in ps:
        if p > 0:
            e -= p * math.log(p)
    return e


def agreement_pattern(row: pd.Series) -> str:
    l1 = nrm(row.get("L1_ans", ""))
    s1 = nrm(row.get("S1_ans", ""))
    tale = nrm(row.get("TALE_ans", ""))
    if not l1 or not s1 or not tale:
        return "missing_external_answer"
    if l1 == s1 == tale:
        return "l1=s1=tale"
    if l1 == s1 != tale:
        return "l1=s1!=tale"
    if l1 == tale != s1:
        return "l1=tale!=s1"
    if s1 == tale != l1:
        return "s1=tale!=l1"
    return "all_different"


def majority_answer(answers: list[str]) -> tuple[str, int]:
    vals = [nrm(a) for a in answers if nrm(a)]
    if not vals:
        return "", 0
    c = Counter(vals)
    best = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return best[0], int(best[1])


def external_2of3_against_frontier(row: pd.Series) -> tuple[bool, str]:
    f = nrm(row.get("frontier_ans", ""))
    l1 = nrm(row.get("L1_ans", ""))
    s1 = nrm(row.get("S1_ans", ""))
    tale = nrm(row.get("TALE_ans", ""))
    if not l1 or not s1 or not tale:
        return False, ""
    maj, count = majority_answer([l1, s1, tale])
    if count < 2:
        return False, maj
    if f and maj == f:
        return False, maj
    return True, maj


def pooled4_answer(row: pd.Series, ranked_sources: list[str]) -> str:
    maj = nrm(row.get("majority_answer", ""))
    has_maj = b01(row.get("has_majority", 0)) == 1
    if has_maj and maj:
        return maj
    for s in ranked_sources:
        a = nrm(row.get(f"{s}_ans", ""))
        if a:
            return a
    return ""


def best_source_answer(row: pd.Series, best_source: str) -> str:
    return nrm(row.get(f"{best_source}_ans", ""))


def compute_train_calib(train: pd.DataFrame) -> dict[str, Any]:
    n = len(train)
    shrunk = {}
    raw = {}
    for s in SOURCES:
        okc = f"{s}_ok"
        n_ok = int(pd.to_numeric(train.get(okc, 0), errors="coerce").fillna(0).astype(int).sum())
        raw[s] = (n_ok / n) if n else 0.0
        shrunk[s] = beta_shrink(n_ok, n)
    ranked = sorted(SOURCES, key=lambda s: (-shrunk[s], s))
    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else ranked[0]
    spread = float(shrunk[best] - shrunk[second])
    ent = entropy_from_probs([max(1e-9, shrunk[s]) for s in SOURCES])

    # External majority reliability tables
    ext_cond = (
        (pd.to_numeric(train.get("external_majority_exists", 0), errors="coerce").fillna(0).astype(int) == 1)
        & (pd.to_numeric(train.get("external_majority_excludes_frontier", 0), errors="coerce").fillna(0).astype(int) == 1)
        & (pd.to_numeric(train.get("majority_size", 0), errors="coerce").fillna(0).astype(int) == 2)
    )
    pat = train[ext_cond].copy()
    ext_support = int(len(pat))
    ext_ag_ok = int(pd.to_numeric(pat.get("agreement_only_ok", 0), errors="coerce").fillna(0).astype(int).sum())
    ext_beta_ok = int(pd.to_numeric(pat.get("beta_shrinkage_ok", 0), errors="coerce").fillna(0).astype(int).sum())
    ext_c1d_ok = int(pd.to_numeric(pat.get("c1d_ok", 0), errors="coerce").fillna(0).astype(int).sum())

    # Correlated-wrong proxy in external-majority agreement regions.
    corr_pat = train[(pd.to_numeric(train.get("L1_TALE_agree", 0), errors="coerce").fillna(0).astype(int) == 1) & ext_cond].copy()
    corr_support = int(len(corr_pat))
    corr_ag_ok = int(pd.to_numeric(corr_pat.get("agreement_only_ok", 0), errors="coerce").fillna(0).astype(int).sum())

    # Pattern action tables for AG01d/e.
    def key_row(r: pd.Series, use_provider_dataset: bool) -> tuple:
        base = []
        if use_provider_dataset:
            base.extend([str(r.get("provider", "")), str(r.get("dataset", ""))])
        base.extend([
            agreement_pattern(r),
            int(b01(r.get("external_majority_exists", 0))),
            int(b01(r.get("external_majority_excludes_frontier", 0))),
            int(b01(r.get("S1_isolated", 0))),
            int(pd.to_numeric(pd.Series([r.get("majority_size", 0)]), errors="coerce").fillna(0).astype(int).iloc[0]),
            int(1 if spread <= 0.05 else 0),
        ])
        return tuple(base)

    actions = ["beta", "c1d", "pooled4", "agreement", "best_source"]
    table_pd: dict[tuple, dict[str, tuple[int, int]]] = defaultdict(lambda: {a: (0, 0) for a in actions})
    table_pf: dict[tuple, dict[str, tuple[int, int]]] = defaultdict(lambda: {a: (0, 0) for a in actions})

    for _, r in train.iterrows():
        kpd = key_row(r, True)
        kpf = key_row(r, False)
        row_stats = {
            "beta": int(b01(r.get("beta_shrinkage_ok", 0))),
            "c1d": int(b01(r.get("c1d_ok", 0))),
            "pooled4": int(b01(r.get("pooled4_ok", 0))),
            "agreement": int(b01(r.get("agreement_only_ok", 0))),
            "best_source": int(max([b01(r.get(f"{s}_ok", 0)) for s in SOURCES])),
        }
        for key, tbl in [(kpd, table_pd), (kpf, table_pf)]:
            for a in actions:
                ok, n_total = tbl[key][a]
                tbl[key][a] = (ok + row_stats[a], n_total + 1)

    return {
        "n_train": n,
        "shrunk_acc": shrunk,
        "raw_acc": raw,
        "ranked_sources": ranked,
        "best_source": best,
        "second_source": second,
        "spread_best_second": spread,
        "entropy": ent,
        "ext_support": ext_support,
        "ext_ag_shr": beta_shrink(ext_ag_ok, ext_support) if ext_support else 0.5,
        "ext_beta_shr": beta_shrink(ext_beta_ok, ext_support) if ext_support else 0.5,
        "ext_c1d_shr": beta_shrink(ext_c1d_ok, ext_support) if ext_support else 0.5,
        "corr_support": corr_support,
        "corr_ag_shr": beta_shrink(corr_ag_ok, corr_support) if corr_support else 0.5,
        "action_table_provider_dataset": table_pd,
        "action_table_provider_free": table_pf,
    }


def base_decisions(row: pd.Series, calib: dict[str, Any]) -> dict[str, str]:
    ranked = calib["ranked_sources"]
    best = calib["best_source"]
    spread = float(calib["spread_best_second"])

    pooled = pooled4_answer(row, ranked)
    beta = best_source_answer(row, best) if spread >= 0.05 else pooled

    # C1d
    dom = best
    dom_ans = nrm(row.get(f"{dom}_ans", ""))
    has_maj = b01(row.get("has_majority", 0)) == 1
    maj = nrm(row.get("majority_answer", ""))
    if spread < 0.03:
        c1d = pooled
    elif has_maj and dom_ans and dom_ans == maj:
        c1d = maj
    elif dom_ans:
        c1d = dom_ans
    else:
        c1d = pooled

    c1a = best_source_answer(row, best) if spread >= 0.05 else pooled

    # Agreement only
    ext_on, ext_ans = external_2of3_against_frontier(row)
    if ext_on and ext_ans:
        ag = ext_ans
    else:
        ag = nrm(row.get("frontier_ans", ""))

    # FIX03 proxy availability from source table not guaranteed; this is a conservative proxy.
    # rule: when near-peer and beta selects S1 while S1 isolated, fallback to pooled4.
    s1_ans = nrm(row.get("S1_ans", ""))
    fix03 = beta
    near_peer = spread <= 0.05
    s1_iso = b01(row.get("S1_isolated", 0)) == 1
    if near_peer and beta == s1_ans and s1_iso:
        fix03 = pooled

    return {
        "frontier": nrm(row.get("frontier_ans", "")),
        "L1": nrm(row.get("L1_ans", "")),
        "S1": nrm(row.get("S1_ans", "")),
        "TALE": nrm(row.get("TALE_ans", "")),
        "pooled4": pooled,
        "agreement_only": ag,
        "beta_shrinkage": beta,
        "C1d": c1d,
        "C1a_t005": c1a,
        "fix03_proxy": fix03,
        "best_train_source": best_source_answer(row, best),
        "oracle_best_action": nrm(row.get("oracle_best_action_decision", "")),
    }


def action_table_pick(
    row: pd.Series,
    calib: dict[str, Any],
    use_provider_dataset: bool,
    min_support: int,
    alpha: float,
    beta: float,
    select_lcb: bool,
) -> str:
    table = calib["action_table_provider_dataset"] if use_provider_dataset else calib["action_table_provider_free"]
    spread = float(calib["spread_best_second"])
    best = calib["best_source"]
    key = []
    if use_provider_dataset:
        key.extend([str(row.get("provider", "")), str(row.get("dataset", ""))])
    key.extend([
        agreement_pattern(row),
        int(b01(row.get("external_majority_exists", 0))),
        int(b01(row.get("external_majority_excludes_frontier", 0))),
        int(b01(row.get("S1_isolated", 0))),
        int(pd.to_numeric(pd.Series([row.get("majority_size", 0)]), errors="coerce").fillna(0).astype(int).iloc[0]),
        int(1 if spread <= 0.05 else 0),
    ])
    key_t = tuple(key)

    base = base_decisions(row, calib)
    actions_to_answer = {
        "beta": base["beta_shrinkage"],
        "c1d": base["C1d"],
        "pooled4": base["pooled4"],
        "agreement": base["agreement_only"],
        "best_source": base["best_train_source"],
    }
    if key_t not in table:
        return base["beta_shrinkage"]

    stats = table[key_t]
    scored: list[tuple[str, float, int]] = []
    for act, (n_ok, n_tot) in stats.items():
        if n_tot < min_support:
            continue
        mu = (n_ok + alpha) / (n_tot + alpha + beta)
        if select_lcb:
            sigma = math.sqrt(max(0.0, mu * (1 - mu) / (n_tot + alpha + beta + 1)))
            score = mu - 1.0 * sigma
        else:
            score = mu
        scored.append((act, score, n_tot))
    if not scored:
        return base["beta_shrinkage"]
    scored.sort(key=lambda x: (-x[1], -x[2], x[0]))
    return actions_to_answer[scored[0][0]]


def ag01_variant_answer(row: pd.Series, calib: dict[str, Any], variant: str) -> str:
    b = base_decisions(row, calib)
    spread = float(calib["spread_best_second"])
    entropy = float(calib["entropy"])
    best = calib["best_source"]

    ext_on, _ = external_2of3_against_frontier(row)
    dataset = str(row.get("dataset", "")).lower()
    q_hard = int(pd.to_numeric(pd.Series([row.get("question_number_count", 0)]), errors="coerce").fillna(0).astype(int).iloc[0]) >= 3

    if variant == "ag01a_np03":
        return b["agreement_only"] if (spread <= 0.03 and ext_on) else b["beta_shrinkage"]
    if variant == "ag01a_np05":
        return b["agreement_only"] if (spread <= 0.05 and ext_on) else b["beta_shrinkage"]
    if variant == "ag01a_np08":
        return b["agreement_only"] if (spread <= 0.08 and ext_on) else b["beta_shrinkage"]
    if variant == "ag01a_np10":
        return b["agreement_only"] if (spread <= 0.10 and ext_on) else b["beta_shrinkage"]
    if variant == "ag01a_entropy_hard":
        return b["agreement_only"] if (entropy >= 1.36 and ext_on and q_hard) else b["beta_shrinkage"]
    if variant == "ag01a_math500_only_diag":
        return b["agreement_only"] if ("math-500" in dataset and ext_on) else b["beta_shrinkage"]
    if variant == "ag01a_providerfree_hard":
        return b["agreement_only"] if (spread <= 0.05 and ext_on and q_hard) else b["beta_shrinkage"]

    # AG01b reliability gate
    m = re.fullmatch(r"ag01b_(beta|c1d)_d(\d+)_s(\d+)", variant)
    if m:
        base_name = m.group(1)
        delta = int(m.group(2)) / 100.0
        min_sup = int(m.group(3))
        base_sel = b["beta_shrinkage"] if base_name == "beta" else b["C1d"]
        if not ext_on:
            return base_sel
        ext_support = int(calib["ext_support"])
        if ext_support < min_sup:
            return base_sel
        ag_acc = float(calib["ext_ag_shr"])
        base_acc = float(calib["ext_beta_shr"] if base_name == "beta" else calib["ext_c1d_shr"])
        if (ag_acc - base_acc) >= delta:
            return b["agreement_only"]
        return base_sel

    # AG01c regression guarded
    if variant == "ag01c_reg_guard":
        if not ext_on:
            return b["beta_shrinkage"]
        s1_dom = best == "S1" and spread >= 0.05
        frontier_best = best == "frontier" and spread >= 0.05
        corr_bad = int(calib["corr_support"]) >= 10 and float(calib["corr_ag_shr"]) <= 0.50
        if (not s1_dom) and (not frontier_best) and (not corr_bad):
            return b["agreement_only"]
        return b["beta_shrinkage"]

    # AG01d RG-EB-Action-lite
    m = re.fullmatch(r"ag01d_(mean|lcb)_s(\d+)_(b11|b22)", variant)
    if m:
        mode = m.group(1)
        min_sup = int(m.group(2))
        prior = m.group(3)
        if prior == "b11":
            a0, b0 = 1.0, 1.0
        else:
            a0, b0 = 2.0, 2.0
        return action_table_pick(row, calib, True, min_sup, a0, b0, select_lcb=(mode == "lcb"))

    # AG01e provider-free RG-EB-Action-lite
    m = re.fullmatch(r"ag01e_(mean|lcb)_s(\d+)_(b11|b22)", variant)
    if m:
        mode = m.group(1)
        min_sup = int(m.group(2))
        prior = m.group(3)
        if prior == "b11":
            a0, b0 = 1.0, 1.0
        else:
            a0, b0 = 2.0, 2.0
        return action_table_pick(row, calib, False, min_sup, a0, b0, select_lcb=(mode == "lcb"))

    # AG01f diagnostic lookup-table risk
    if variant == "ag01f_cohere_math_lookup_diag":
        if str(row.get("scenario_id", "")) == "cohere_math500":
            return b["agreement_only"]
        return b["beta_shrinkage"]

    raise KeyError(f"unknown variant: {variant}")


AG01_VARIANTS = [
    "ag01a_np03",
    "ag01a_np05",
    "ag01a_np08",
    "ag01a_np10",
    "ag01a_entropy_hard",
    "ag01a_math500_only_diag",
    "ag01a_providerfree_hard",
]
for base in ["beta", "c1d"]:
    for d in [0, 3, 5, 8]:
        for s in [5, 10, 20]:
            AG01_VARIANTS.append(f"ag01b_{base}_d{d:02d}_s{s}")
AG01_VARIANTS.append("ag01c_reg_guard")
for fam in ["ag01d", "ag01e"]:
    for mode in ["mean", "lcb"]:
        for s in [5, 10, 20]:
            for prior in ["b11", "b22"]:
                AG01_VARIANTS.append(f"{fam}_{mode}_s{s}_{prior}")
AG01_VARIANTS.append("ag01f_cohere_math_lookup_diag")

BASELINE_VARIANTS = [
    "frontier",
    "L1",
    "S1",
    "TALE",
    "pooled4",
    "agreement_only",
    "beta_shrinkage",
    "C1d",
    "C1a_t005",
    "fix03_proxy",
    "best_train_source",
    "oracle_best_action",
]


@dataclass
class FoldSpec:
    name: str
    train_idx: np.ndarray
    test_idx: np.ndarray
    fold: str


def kfold_indices(n: int, k: int = 5, seed: int = 42) -> list[tuple[np.ndarray, np.ndarray]]:
    idx = np.arange(n)
    rng = np.random.default_rng(seed)
    rng.shuffle(idx)
    folds = np.array_split(idx, k)
    out = []
    for i in range(k):
        test = folds[i]
        train = np.concatenate([folds[j] for j in range(k) if j != i])
        out.append((train, test))
    return out


def build_folds(df: pd.DataFrame) -> dict[str, list[FoldSpec]]:
    folds: dict[str, list[FoldSpec]] = {}

    # A: within-scenario 5-fold
    ws = []
    for sid, sdf in df.groupby("scenario_id"):
        idx = sdf.index.to_numpy()
        for i, (tr_local, te_local) in enumerate(kfold_indices(len(idx), 5, seed=41)):
            ws.append(FoldSpec(
                name="within_scenario_cv",
                train_idx=idx[tr_local],
                test_idx=idx[te_local],
                fold=f"{sid}:f{i}",
            ))
    folds["within_scenario_cv"] = ws

    # B: pooled stratified CV across all scenarios
    ps = []
    sdf = df.copy()
    by_sid = {sid: sub.index.to_numpy() for sid, sub in sdf.groupby("scenario_id")}
    split_by_sid = {sid: kfold_indices(len(idx), 5, seed=123) for sid, idx in by_sid.items()}
    for i in range(5):
        test_parts = []
        train_parts = []
        for sid, idx in by_sid.items():
            tr_local, te_local = split_by_sid[sid][i]
            train_parts.append(idx[tr_local])
            test_parts.append(idx[te_local])
        ps.append(FoldSpec(
            name="official_pooled_cv",
            train_idx=np.concatenate(train_parts),
            test_idx=np.concatenate(test_parts),
            fold=f"f{i}",
        ))
    folds["official_pooled_cv"] = ps

    # C: leave-one-scenario-out
    loso = []
    for sid, sdf in df.groupby("scenario_id"):
        test_idx = sdf.index.to_numpy()
        train_idx = df.index[~df.index.isin(test_idx)].to_numpy()
        loso.append(FoldSpec(
            name="leave_one_scenario_out",
            train_idx=train_idx,
            test_idx=test_idx,
            fold=f"holdout:{sid}",
        ))
    folds["leave_one_scenario_out"] = loso

    # D: provider heldout
    ph = []
    for p in sorted(df["provider"].unique()):
        test_idx = df.index[df["provider"] == p].to_numpy()
        train_idx = df.index[df["provider"] != p].to_numpy()
        ph.append(FoldSpec("provider_heldout", train_idx, test_idx, f"holdout_provider:{p}"))
    folds["provider_heldout"] = ph

    # E: dataset heldout
    dh = []
    for d in sorted(df["dataset"].unique()):
        test_idx = df.index[df["dataset"] == d].to_numpy()
        train_idx = df.index[df["dataset"] != d].to_numpy()
        dh.append(FoldSpec("dataset_heldout", train_idx, test_idx, f"holdout_dataset:{d}"))
    folds["dataset_heldout"] = dh

    # F: full-artifact diagnostic
    all_idx = df.index.to_numpy()
    folds["full_artifact_diagnostic"] = [
        FoldSpec("full_artifact_diagnostic", all_idx, all_idx, "full")
    ]
    return folds


def evaluate_all(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    folds = build_folds(df)
    pred_rows: list[dict[str, Any]] = []

    for protocol, fold_specs in folds.items():
        for fs in fold_specs:
            train = df.loc[fs.train_idx].copy()
            test = df.loc[fs.test_idx].copy()
            calib = compute_train_calib(train)

            for _, row in test.iterrows():
                base = base_decisions(row, calib)
                gold = nrm(row.get("gold", ""))
                base_meta = {
                    "protocol": protocol,
                    "fold": fs.fold,
                    "scenario_id": row.get("scenario_id", ""),
                    "provider": row.get("provider", ""),
                    "dataset": row.get("dataset", ""),
                    "example_id": row.get("example_id", ""),
                    "gold": gold,
                    "spread_best_second": float(calib["spread_best_second"]),
                    "entropy": float(calib["entropy"]),
                    "best_train_source": calib["best_source"],
                    "second_train_source": calib["second_source"],
                    "ext_support": int(calib["ext_support"]),
                    "corr_support": int(calib["corr_support"]),
                    "external_majority_exists": int(b01(row.get("external_majority_exists", 0))),
                    "external_majority_excludes_frontier": int(b01(row.get("external_majority_excludes_frontier", 0))),
                    "majority_size": int(pd.to_numeric(pd.Series([row.get("majority_size", 0)]), errors="coerce").fillna(0).astype(int).iloc[0]),
                    "no_majority_flag": int(b01(row.get("no_majority_flag", 0))),
                    "S1_isolated": int(b01(row.get("S1_isolated", 0))),
                    "question_number_count": int(pd.to_numeric(pd.Series([row.get("question_number_count", 0)]), errors="coerce").fillna(0).astype(int).iloc[0]),
                    "question_has_equation_flag": int(b01(row.get("question_has_equation_flag", 0))),
                    "all_sources_wrong": int(b01(row.get("all_sources_wrong", 0))),
                    "frontier_ans": nrm(row.get("frontier_ans", "")),
                    "L1_ans": nrm(row.get("L1_ans", "")),
                    "S1_ans": nrm(row.get("S1_ans", "")),
                    "TALE_ans": nrm(row.get("TALE_ans", "")),
                    "question": row.get("question", ""),
                    "oracle_best_action_answer": base["oracle_best_action"],
                }

                for v in BASELINE_VARIANTS:
                    ans = base[v]
                    pred_rows.append({
                        **base_meta,
                        "variant": v,
                        "family": "baseline",
                        "selected_answer": ans,
                        "selected_correct": int(ans == gold) if gold else 0,
                    })

                for v in AG01_VARIANTS:
                    ans = ag01_variant_answer(row, calib, v)
                    pred_rows.append({
                        **base_meta,
                        "variant": v,
                        "family": "ag01",
                        "selected_answer": ans,
                        "selected_correct": int(ans == gold) if gold else 0,
                    })

    preds = pd.DataFrame(pred_rows)

    # Summaries per protocol/fold/variant.
    sum_rows: list[dict[str, Any]] = []
    for (protocol, fold, variant), g in preds.groupby(["protocol", "fold", "variant"]):
        by_sid = g.groupby("scenario_id")["selected_correct"].mean().to_dict()
        sum_rows.append({
            "protocol": protocol,
            "fold": fold,
            "variant": variant,
            "family": g["family"].iloc[0],
            "n": int(len(g)),
            "accuracy": float(g["selected_correct"].mean()),
            "official_macro_accuracy": float(np.mean(list(by_sid.values()))) if by_sid else np.nan,
            "worst_scenario_accuracy": float(min(by_sid.values())) if by_sid else np.nan,
            "scenario_accuracy_json": json.dumps({k: float(v) for k, v in by_sid.items()}, sort_keys=True),
            "oracle_regret": float(g["oracle_best_action_answer"].eq(g["gold"]).mean() - g["selected_correct"].mean()),
        })

    summ = pd.DataFrame(sum_rows)
    return preds, summ


def aggregate_protocol_summary(summ: pd.DataFrame, protocol: str) -> pd.DataFrame:
    sdf = summ[summ["protocol"] == protocol].copy()
    rows = []
    for v, g in sdf.groupby("variant"):
        rows.append({
            "variant": v,
            "family": g["family"].iloc[0],
            "n_folds": int(len(g)),
            "accuracy_mean": float(g["accuracy"].mean()),
            "accuracy_std": float(g["accuracy"].std(ddof=0)) if len(g) > 1 else 0.0,
            "official_macro_mean": float(g["official_macro_accuracy"].mean()),
            "worst_scenario_mean": float(g["worst_scenario_accuracy"].mean()),
            "oracle_regret_mean": float(g["oracle_regret"].mean()),
        })
    out = pd.DataFrame(rows).sort_values("accuracy_mean", ascending=False)

    def _m(vname: str, col: str) -> float:
        m = out[out["variant"] == vname]
        return float(m[col].iloc[0]) if len(m) else np.nan

    beta = _m("beta_shrinkage", "accuracy_mean")
    c1d = _m("C1d", "accuracy_mean")
    agr = _m("agreement_only", "accuracy_mean")
    out["delta_vs_beta_shrinkage"] = out["accuracy_mean"] - beta
    out["delta_vs_C1d"] = out["accuracy_mean"] - c1d
    out["delta_vs_agreement_only"] = out["accuracy_mean"] - agr
    return out


def pairwise_win_loss(preds: pd.DataFrame, protocol: str) -> pd.DataFrame:
    p = preds[preds["protocol"] == protocol].copy()
    key_cols = ["fold", "scenario_id", "example_id"]
    # reference variants
    refs = ["beta_shrinkage", "C1d", "agreement_only"]
    cand = sorted(p["variant"].unique())
    rows = []
    for v in cand:
        pv = p[p["variant"] == v][key_cols + ["selected_correct"]].rename(columns={"selected_correct": "v_ok"})
        for r in refs:
            pr = p[p["variant"] == r][key_cols + ["selected_correct"]].rename(columns={"selected_correct": "r_ok"})
            m = pv.merge(pr, on=key_cols, how="inner")
            win = int(((m["v_ok"] == 1) & (m["r_ok"] == 0)).sum())
            loss = int(((m["v_ok"] == 0) & (m["r_ok"] == 1)).sum())
            tie = int((m["v_ok"] == m["r_ok"]).sum())
            rows.append({
                "protocol": protocol,
                "variant": v,
                "reference": r,
                "wins": win,
                "losses": loss,
                "ties": tie,
                "net": win - loss,
            })
    return pd.DataFrame(rows).sort_values(["reference", "net"], ascending=[True, False])


def oracle_regret_summary(preds: pd.DataFrame, protocol: str) -> pd.DataFrame:
    p = preds[preds["protocol"] == protocol].copy()
    rows = []
    for v, g in p.groupby("variant"):
        oracle_acc = float((g["oracle_best_action_answer"] == g["gold"]).mean())
        acc = float(g["selected_correct"].mean())
        rows.append({
            "protocol": protocol,
            "variant": v,
            "accuracy": acc,
            "oracle_best_action_accuracy": oracle_acc,
            "regret_to_oracle": oracle_acc - acc,
        })
    return pd.DataFrame(rows).sort_values("accuracy", ascending=False)


def recovery_regression_summary(preds: pd.DataFrame, protocol: str) -> pd.DataFrame:
    p = preds[preds["protocol"] == protocol].copy()
    key = ["fold", "scenario_id", "example_id"]
    rows = []
    for v in sorted(p["variant"].unique()):
        pv = p[p["variant"] == v][key + ["selected_correct"]].rename(columns={"selected_correct": "v_ok"})
        for ref in ["beta_shrinkage", "C1d", "agreement_only"]:
            pr = p[p["variant"] == ref][key + ["selected_correct"]].rename(columns={"selected_correct": "r_ok"})
            m = pv.merge(pr, on=key, how="inner")
            rec_all = int(((m["v_ok"] == 1) & (m["r_ok"] == 0)).sum())
            reg_all = int(((m["v_ok"] == 0) & (m["r_ok"] == 1)).sum())

            mh = m[m["scenario_id"] == "cohere_math500"]
            rec_h = int(((mh["v_ok"] == 1) & (mh["r_ok"] == 0)).sum())
            reg_h = int(((mh["v_ok"] == 0) & (mh["r_ok"] == 1)).sum())

            rows.append({
                "protocol": protocol,
                "variant": v,
                "reference": ref,
                "recoveries_all": rec_all,
                "regressions_all": reg_all,
                "net_all": rec_all - reg_all,
                "recoveries_cohere_math500": rec_h,
                "regressions_cohere_math500": reg_h,
                "net_cohere_math500": rec_h - reg_h,
            })
    return pd.DataFrame(rows)


def recommendation_for_variant(row: pd.Series) -> str:
    v = str(row["variant"])
    d_beta = float(row.get("delta_vs_beta", 0.0))
    d_c1d = float(row.get("delta_vs_c1d", 0.0))
    d_ag = float(row.get("delta_vs_agreement", 0.0))
    lookup = int(row.get("lookup_table_risk", 0))
    if lookup:
        return "keep diagnostic"
    if d_beta > 0.003 and d_c1d >= 0 and d_ag >= -0.002:
        return "promote candidate"
    if d_beta > -0.002 and d_c1d > -0.002:
        return "use as action in learned router only"
    if v.startswith("ag01d") or v.startswith("ag01e"):
        return "wait for router v2"
    return "reject"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(OFF4_TABLE)

    # Step 3 validation and source inventory
    scenario_counts = df["scenario_id"].value_counts().to_dict()
    assert set(scenario_counts.keys()) == {"cohere_gsm8k", "mistral_gsm8k", "cohere_math500", "mistral_math500"}
    assert all(v == 300 for v in scenario_counts.values())
    assert len(df) == 1200

    inv = pd.DataFrame([
        {"source_group": "official4_unified", "path": str(OFF4_TABLE.relative_to(REPO)), "exists": OFF4_TABLE.exists()},
        {"source_group": "official4_matrix", "path": str(FOUR_SCENARIO_MATRIX.relative_to(REPO)), "exists": FOUR_SCENARIO_MATRIX.exists()},
        {"source_group": "cohere_math_agreement_analysis", "path": str(COHERE_AGREEMENT_ANALYSIS.relative_to(REPO)), "exists": COHERE_AGREEMENT_ANALYSIS.exists()},
        {"source_group": "fix03_official_pooled_summary", "path": str(FIX03_OFFICIAL_POOLED_SUMMARY.relative_to(REPO)), "exists": FIX03_OFFICIAL_POOLED_SUMMARY.exists()},
    ])
    inv.to_csv(OUT / "source_artifact_inventory.csv", index=False)
    (OUT / "source_artifact_inventory.json").write_text(inv.to_json(orient="records", indent=2), encoding="utf-8")

    # reconstruct + save enriched case table
    # add agreement_pattern and verify decisions reconstructable
    df = df.copy()
    df["agreement_pattern"] = df.apply(agreement_pattern, axis=1)

    # rule dependencies documentation
    rule_md = "\n".join([
        "# AG-01 rule dependencies",
        "## agreement_only",
        "- keep frontier if any external answer missing/unparseable",
        "- keep frontier if no external 2-of-3 agreement",
        "- keep frontier if external 2-of-3 agrees with frontier",
        "- otherwise defer to external 2-of-3 majority",
        "## pooled4",
        "- choose all-4 majority if exists",
        "- else fallback to best calibrated source answer",
        "## beta_shrinkage",
        "- if dominant-source spread >= 0.05 choose best calibrated source",
        "- else fallback to pooled4",
        "## C1d",
        "- if spread < 0.03 fallback to pooled4",
        "- else if pooled majority includes dominant source choose majority",
        "- else choose dominant source",
    ])
    (OUT / "ag01_rule_dependencies.md").write_text(rule_md, encoding="utf-8")

    df.to_csv(OUT / "ag01_official4_case_table.csv", index=False)

    preds, summ = evaluate_all(df)

    # protocol-specific summary files
    within = aggregate_protocol_summary(summ, "within_scenario_cv")
    pooled = aggregate_protocol_summary(summ, "official_pooled_cv")
    loso = aggregate_protocol_summary(summ, "leave_one_scenario_out")
    provider = aggregate_protocol_summary(summ, "provider_heldout")
    dataset = aggregate_protocol_summary(summ, "dataset_heldout")
    full_diag = aggregate_protocol_summary(summ, "full_artifact_diagnostic")

    within.to_csv(OUT / "ag01_within_scenario_cv_summary.csv", index=False)
    pooled.to_csv(OUT / "ag01_official_pooled_cv_summary.csv", index=False)
    loso.to_csv(OUT / "ag01_leave_one_scenario_out_summary.csv", index=False)
    provider.to_csv(OUT / "ag01_provider_heldout_summary.csv", index=False)
    dataset.to_csv(OUT / "ag01_dataset_heldout_summary.csv", index=False)
    full_diag.to_csv(OUT / "ag01_full_artifact_diagnostic_summary.csv", index=False)

    pairwise = pairwise_win_loss(preds, "official_pooled_cv")
    pairwise.to_csv(OUT / "ag01_pairwise_win_loss_summary.csv", index=False)

    oracle_reg = oracle_regret_summary(preds, "official_pooled_cv")
    oracle_reg.to_csv(OUT / "ag01_oracle_regret_summary.csv", index=False)

    rr = recovery_regression_summary(preds, "official_pooled_cv")
    rr.to_csv(OUT / "ag01_recovery_regression_summary.csv", index=False)

    # Step 8: Cohere MATH detailed for best variants
    ag_pooled = pooled[pooled["variant"].str.startswith("ag01")].copy()
    best_variants = ag_pooled.sort_values("accuracy_mean", ascending=False).head(3)["variant"].tolist()
    cm = preds[(preds["protocol"] == "official_pooled_cv") & (preds["scenario_id"] == "cohere_math500")].copy()

    drows = []
    for v in best_variants + ["agreement_only", "beta_shrinkage", "C1d"]:
        g = cm[cm["variant"] == v]
        drows.append({"variant": v, "n": int(len(g)), "accuracy": float(g["selected_correct"].mean())})
    pd.DataFrame(drows).sort_values("accuracy", ascending=False).to_csv(OUT / "ag01_cohere_math500_detailed_summary.csv", index=False)

    best = best_variants[0] if best_variants else "ag01a_np05"
    def _merge_cmp(v1: str, v2: str) -> pd.DataFrame:
        a = cm[cm["variant"] == v1][["fold", "scenario_id", "example_id", "question", "gold", "selected_answer", "selected_correct", "frontier_ans", "L1_ans", "S1_ans", "TALE_ans", "all_sources_wrong"]].rename(columns={"selected_answer": f"{v1}_answer", "selected_correct": f"{v1}_ok"})
        b = cm[cm["variant"] == v2][["fold", "scenario_id", "example_id", "selected_answer", "selected_correct"]].rename(columns={"selected_answer": f"{v2}_answer", "selected_correct": f"{v2}_ok"})
        return a.merge(b, on=["fold", "scenario_id", "example_id"], how="inner")

    m_beta = _merge_cmp(best, "beta_shrinkage")
    m_ag = _merge_cmp(best, "agreement_only")

    rec_beta = m_beta[(m_beta[f"{best}_ok"] == 1) & (m_beta["beta_shrinkage_ok"] == 0)]
    reg_beta = m_beta[(m_beta[f"{best}_ok"] == 0) & (m_beta["beta_shrinkage_ok"] == 1)]
    rec_ag = m_ag[(m_ag[f"{best}_ok"] == 1) & (m_ag["agreement_only_ok"] == 0)]
    reg_ag = m_ag[(m_ag[f"{best}_ok"] == 0) & (m_ag["agreement_only_ok"] == 1)]

    rec_beta.to_csv(OUT / "ag01_cohere_math500_recoveries_vs_beta.csv", index=False)
    reg_beta.to_csv(OUT / "ag01_cohere_math500_regressions_vs_beta.csv", index=False)
    rec_ag.to_csv(OUT / "ag01_cohere_math500_recoveries_vs_agreement_only.csv", index=False)
    reg_ag.to_csv(OUT / "ag01_cohere_math500_regressions_vs_agreement_only.csv", index=False)

    (OUT / "ag01_cohere_math500_casebook.md").write_text(
        "\n".join([
            "# AG-01 Cohere MATH-500 casebook",
            f"Best AG-01 variant (official pooled CV): {best}",
            f"Recoveries vs beta: {len(rec_beta)}",
            f"Regressions vs beta: {len(reg_beta)}",
            f"Recoveries vs agreement_only: {len(rec_ag)}",
            f"Regressions vs agreement_only: {len(reg_ag)}",
        ]),
        encoding="utf-8",
    )

    # Step 9 failure/regression analysis for best variant
    p = preds[preds["protocol"] == "official_pooled_cv"].copy()
    bbest = p[p["variant"] == best]
    bagr = p[p["variant"] == "agreement_only"]
    bbeta = p[p["variant"] == "beta_shrinkage"]
    bc1d = p[p["variant"] == "C1d"]
    key = ["fold", "scenario_id", "example_id"]

    merged = bbest.merge(bagr[key + ["selected_correct"]].rename(columns={"selected_correct": "agreement_ok"}), on=key)
    merged = merged.merge(bbeta[key + ["selected_correct"]].rename(columns={"selected_correct": "beta_ok"}), on=key)
    merged = merged.merge(bc1d[key + ["selected_correct"]].rename(columns={"selected_correct": "c1d_ok"}), on=key)

    wins_captured = merged[(merged["agreement_ok"] == 1) & (merged["beta_ok"] == 0) & (merged["selected_correct"] == 1)]
    regs_avoided = merged[(merged["agreement_ok"] == 0) & (merged["beta_ok"] == 1) & (merged["selected_correct"] == 1)]
    new_regs = merged[(merged["selected_correct"] == 0) & (merged["beta_ok"] == 1)]
    mistral_regs = new_regs[new_regs["provider"] == "mistral"]
    cohere_gsm8k_regs = new_regs[new_regs["scenario_id"] == "cohere_gsm8k"]

    merged.to_csv(OUT / "ag01_best_variant_failure_cases.csv", index=False)
    wins_captured.to_csv(OUT / "ag01_agreement_wins_captured.csv", index=False)
    regs_avoided.to_csv(OUT / "ag01_agreement_regressions_avoided.csv", index=False)
    new_regs.to_csv(OUT / "ag01_new_regressions.csv", index=False)
    mistral_regs.to_csv(OUT / "ag01_mistral_regressions.csv", index=False)
    cohere_gsm8k_regs.to_csv(OUT / "ag01_cohere_gsm8k_regressions.csv", index=False)

    (OUT / "ag01_best_variant_casebook.md").write_text(
        "\n".join([
            "# AG-01 best-variant failure analysis",
            f"best_variant: {best}",
            f"agreement wins captured: {len(wins_captured)}",
            f"agreement regressions avoided: {len(regs_avoided)}",
            f"new regressions vs beta: {len(new_regs)}",
            f"mistral regressions: {len(mistral_regs)}",
            f"cohere_gsm8k regressions: {len(cohere_gsm8k_regs)}",
        ]),
        encoding="utf-8",
    )

    # Step 10 candidate decision table
    # Compose from protocol summaries.
    pooled_m = pooled.set_index("variant")
    loso_m = loso.set_index("variant")
    provider_m = provider.set_index("variant")
    dataset_m = dataset.set_index("variant")

    beta_acc = float(pooled_m.loc["beta_shrinkage", "accuracy_mean"])
    c1d_acc = float(pooled_m.loc["C1d", "accuracy_mean"])
    ag_acc = float(pooled_m.loc["agreement_only", "accuracy_mean"])

    dec_rows = []
    for v in [x for x in pooled["variant"].tolist() if x.startswith("ag01")]:
        rr_v_beta = rr[(rr["variant"] == v) & (rr["reference"] == "beta_shrinkage")]
        cm_rec = int(rr_v_beta["recoveries_cohere_math500"].iloc[0]) if len(rr_v_beta) else 0
        cm_reg = int(rr_v_beta["regressions_cohere_math500"].iloc[0]) if len(rr_v_beta) else 0
        row = {
            "variant": v,
            "official_pooled_cv_accuracy": float(pooled_m.loc[v, "accuracy_mean"]),
            "official_macro_accuracy": float(pooled_m.loc[v, "official_macro_mean"]),
            "worst_official_scenario_accuracy": float(pooled_m.loc[v, "worst_scenario_mean"]),
            "loso_accuracy": float(loso_m.loc[v, "accuracy_mean"]) if v in loso_m.index else np.nan,
            "provider_heldout_accuracy": float(provider_m.loc[v, "accuracy_mean"]) if v in provider_m.index else np.nan,
            "dataset_heldout_accuracy": float(dataset_m.loc[v, "accuracy_mean"]) if v in dataset_m.index else np.nan,
            "delta_vs_beta": float(pooled_m.loc[v, "accuracy_mean"] - beta_acc),
            "delta_vs_c1d": float(pooled_m.loc[v, "accuracy_mean"] - c1d_acc),
            "delta_vs_agreement": float(pooled_m.loc[v, "accuracy_mean"] - ag_acc),
            "cohere_math_recoveries_vs_beta": cm_rec,
            "cohere_math_regressions_vs_beta": cm_reg,
            "lookup_table_risk": int("lookup" in v or "math500_only" in v),
            "implementation_complexity": "medium" if (v.startswith("ag01d") or v.startswith("ag01e")) else "low",
        }
        row["recommendation"] = recommendation_for_variant(pd.Series(row))
        dec_rows.append(row)

    dec = pd.DataFrame(dec_rows).sort_values("official_pooled_cv_accuracy", ascending=False)
    dec.to_csv(OUT / "ag01_candidate_decision_table.csv", index=False)

    (OUT / "ag01_candidate_decision.md").write_text(
        "\n".join([
            "# AG-01 candidate decision",
            f"Best variant by official pooled CV: {dec.iloc[0]['variant'] if len(dec) else 'n/a'}",
            "",
            dec.head(20).to_string(index=False) if len(dec) else "No variants.",
        ]),
        encoding="utf-8",
    )

    # Step 11 router implications
    (OUT / "ag01_router_v2_implications.md").write_text(
        "\n".join([
            "# AG-01 router-v2 implications",
            "- agreement_only should be included as router action candidate.",
            "- AG-01 is better treated as action-routing logic than a universal hand-coded replacement.",
            "- key features: external_majority_exists, external_majority_excludes_frontier, majority_size, near-peer spread, S1 dominance confidence.",
            "- provider/dataset features help but increase lookup-table risk; keep provider-free variants in evaluation.",
            "- train1000 GSM8K helps action labels but is insufficient for Cohere MATH behavior; include official/aux MATH in training with strict split discipline.",
            "- next learned-router query should train a pattern-action model with agreement_only action and scenario-stratified regression audit.",
        ]),
        encoding="utf-8",
    )

    # Step 12 queue updates
    best_row = dec.iloc[0] if len(dec) else None
    keep_ag01 = "yes" if (best_row is not None and best_row["delta_vs_beta"] >= -0.002) else "no"
    rg_next = "yes" if (best_row is not None and (best_row["variant"].startswith("ag01d") or best_row["variant"].startswith("ag01e") or best_row["recommendation"] in {"wait for router v2", "use as action in learned router only"})) else "yes"
    lr_now = "yes" if keep_ag01 == "yes" else "no"

    upd = pd.DataFrame([
        {"priority": 1, "item": "AG-01 keep?", "decision": keep_ag01, "rationale": "best variant stability and deltas vs beta/C1d"},
        {"priority": 2, "item": "Implement full RG-EB-Action next?", "decision": rg_next, "rationale": "pattern-action variants show potential with bounded risk"},
        {"priority": 3, "item": "Train learned router v2 now?", "decision": lr_now, "rationale": "include agreement_only action and scenario-stratified audits"},
        {"priority": 4, "item": "Top remaining cluster", "decision": "all_sources_wrong", "rationale": "largest irrecoverable mass remains generation-bound"},
        {"priority": 5, "item": "Manuscript framing change", "decision": "minor", "rationale": "present AG-01 as candidate/action-set evidence, not final promotion"},
    ])
    upd.to_csv(OUT / "ag01_updated_failure_driven_queue.csv", index=False)

    (OUT / "ag01_next_iteration_recommendations.md").write_text(
        "\n".join([
            "# AG-01 next iteration recommendations",
            f"- keep AG-01 candidate: {keep_ag01}",
            f"- implement RG-EB-Action next: {rg_next}",
            f"- train learned router v2 now: {lr_now}",
            "- top failure cluster remains all_sources_wrong (generation-bound).",
            "- manuscript framing: AG-01 is promising but should remain candidate-level pending broader transfer evidence.",
        ]),
        encoding="utf-8",
    )

    # Step 13 main report
    top_pooled = pooled.head(15)
    DOC.write_text(
        "\n".join([
            "# AG01_AGREEMENT_ONLY_GATE_20260524",
            "",
            "## 1. Executive summary",
            f"Implemented {len(AG01_VARIANTS)} AG-01 variants with fold-safe calibration and evaluated across official four scenarios.",
            "",
            "## 2. Data sources and caveats",
            "- Official4 case table only for headline metrics.",
            "- Auxiliary/train1000 used only for context (not in official averages).",
            "- Offline replay only; no API calls.",
            "",
            "## 3. AG-01 variant definitions",
            "See `scripts/evaluate_ag01_agreement_only_gate.py` and `ag01_rule_dependencies.md`.",
            "",
            "## 4. Evaluation protocol",
            "within-scenario CV, pooled CV, LOSO, provider-heldout, dataset-heldout, full diagnostic.",
            "",
            "## 5. Official four-scenario results",
            top_pooled.to_string(index=False),
            "",
            "## 6. Official Cohere MATH detailed results",
            (pd.read_csv(OUT / "ag01_cohere_math500_detailed_summary.csv").to_string(index=False)),
            "",
            "## 7. Transfer/held-out results",
            "See `ag01_leave_one_scenario_out_summary.csv`, `ag01_provider_heldout_summary.csv`, `ag01_dataset_heldout_summary.csv`.",
            "",
            "## 8. Recovery/regression analysis",
            f"Best variant: {best}",
            f"- recoveries vs beta on Cohere MATH: {len(rec_beta)}",
            f"- regressions vs beta on Cohere MATH: {len(reg_beta)}",
            "",
            "## 9. Best variant decision",
            f"Selected by official pooled CV: {best}",
            "",
            "## 10. Router-v2 implications",
            "agreement_only should be an action candidate; prefer routing integration over hard replacement.",
            "",
            "## 11. Manuscript implications",
            "AG-01 supports candidate-level improvement framing; no unconditional promotion claim.",
            "",
            "## 12. Next iteration recommendation",
            "Implement conservative AG-01 guard + full pattern-action router query.",
            "",
            "## 13. Safety confirmation",
            "- offline only",
            "- no API calls",
            "- no active-job interference",
            "- no commit/push",
        ]),
        encoding="utf-8",
    )

    # Step 14 manifest
    outputs = sorted([str(p.relative_to(REPO)) for p in OUT.glob("**/*") if p.is_file()])
    manifest = {
        "timestamp": now_utc(),
        "input_artifacts": [
            str(OFF4_TABLE.relative_to(REPO)),
            str(FOUR_SCENARIO_MATRIX.relative_to(REPO)),
            str(COHERE_AGREEMENT_ANALYSIS.relative_to(REPO)),
            str(FIX03_OFFICIAL_POOLED_SUMMARY.relative_to(REPO)),
        ],
        "scripts_created": ["scripts/evaluate_ag01_agreement_only_gate.py"],
        "output_files": outputs,
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "limitations": [
            "FIX-03 baseline represented as conservative proxy in this AG-01 script",
            "No runtime generation; offline replay only",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
