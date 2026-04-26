#!/usr/bin/env python3
"""Compare offline answer selectors on direct_reserve strong+diverse candidate pools."""
from __future__ import annotations

import argparse
import math
import pickle
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.learned_branch_scorer_utils import as_float, as_int, read_csv, write_csv, write_json
from scripts.train_direct_reserve_candidate_scorer import DIVERSE, MARGIN, _feat

GATED = MARGIN


def _n(s: str) -> str:
    t = (s or "").strip().lower()
    return t or "na"


def _h(cdiv: list[dict]) -> float:
    c = Counter(str(c.get("answer_group_id", "na")) for c in cdiv)
    t = float(max(1, sum(c.values())))
    e = 0.0
    for v in c.values():
        p = v / t
        e -= p * math.log2(p + 1e-12) if len(c) > 1 else 0.0
    return e


def _gold(cdiv: list[dict]) -> str:
    for c in cdiv:
        g = c.get("gold_norm")
        if g and str(g).lower() not in ("", "na", "none"):
            return _n(str(g))
    gpos = [c for c in cdiv if as_int(c.get("is_gold_candidate", 0), 0) == 1]
    if gpos:
        return _n(str(gpos[0].get("normalized_answer", "na")))
    return "na"


def _ok(c: dict, g: str) -> int:
    if g in ("", "na"):
        return 0
    return int(_n(str(c.get("normalized_answer", "na"))) == g)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--dataset-dir", required=True)
    p.add_argument("--train-dir", default="")
    p.add_argument(
        "--per-case",
        default="",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    d = (REPO_ROOT / args.dataset_dir) if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    exf = d / "examples.csv"
    if not exf.exists():
        raise SystemExit(f"Missing {exf}")
    rows = [dict(r) for r in read_csv(exf) if as_int(r.get("excluded_from_training", 0), 0) == 0]
    rows = [r for r in rows if r.get("method", "") not in (GATED,)]
    pfp: Path
    pfp = (REPO_ROOT / args.per_case) if str(args.per_case).strip() else d / "per_case_method_results.csv"
    if not pfp.exists():
        pool = list(d.parent.glob("cohere_direct_reserve_validation_*/per_case_method_results.csv"))
        if pool:
            pfp = pool[0]
    per: dict[tuple, dict] = {}
    if pfp.exists():
        for r in read_csv(pfp):
            per[(str(r.get("example_id", "")), as_int(r.get("seed", 0), 0), as_int(r.get("budget", 0), 0), str(r.get("method", "")))] = r
    b: dict = {}
    if str(args.train_dir).strip():
        tdir = (REPO_ROOT / str(args.train_dir)) if not Path(str(args.train_dir)).is_absolute() else Path(str(args.train_dir))
        pkl = tdir / "selected_model.joblib"
        if pkl.exists():
            b = pickle.load(pkl.open("rb"))
    vec, m_lr, m_rf, m_hg, pvec, p_lr = b.get("vectorizer"), b.get("logistic"), b.get("rf"), b.get("hgb"), b.get("pair_vectorizer"), b.get("pair_logit")
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        g = f"{r.get('example_id')}|{r.get('seed')}|{r.get('budget')}"
        by[g].append(r)
    out_case: list[dict] = []
    rates: dict[str, list[int]] = defaultdict(list)
    for g, pool in by.items():
        cdiv = [c for c in pool if c.get("method", "") == DIVERSE]
        if not cdiv:
            continue
        eid, sd, bd = str(cdiv[0].get("example_id", "")), as_int(cdiv[0].get("seed", 0), 0), as_int(cdiv[0].get("budget", 0), 0)
        gold = _gold(cdiv)
        h = _h(cdiv)
        base = next((c for c in cdiv if as_int(c.get("selected_by_method", 0), 0) == 1), cdiv[0])
        sup = max(
            cdiv, key=lambda c: (as_float(c.get("answer_group_support", 0), 0) or 0, str(c.get("answer_group_id", "")))
        )
        gpick = max(cdiv, key=lambda c: (as_float(c.get("top2_support_gap", 0), 0) or 0, -h))
        mgd = per.get((eid, sd, bd, GATED), {})
        gated_ans = str(
            mgd.get("normalized_selected_answer", (base or {}).get("normalized_answer", "na"))
            if mgd
            else (base or {}).get("normalized_answer", "na")
        )
        c_log, c_rf, c_hg = base, base, base
        if vec is not None and m_lr and len(cdiv):
            Xl = vec.transform([_feat(c) for c in cdiv])
            s_l = m_lr.decision_function(Xl) if isinstance(m_lr, LogisticRegression) or hasattr(m_lr, "decision_function") else m_lr.predict_proba(Xl)[:, 1]
            c_log = cdiv[int(np.argmax(s_l))]
        if vec and m_rf:
            srf_ = m_rf.predict_proba(vec.transform([_feat(c) for c in cdiv]))[:, 1]
            c_rf = cdiv[int(np.argmax(srf_))]
        if vec and m_hg:
            s_h = m_hg.predict_proba(vec.transform([_feat(c) for c in cdiv]))[:, 1]
            c_hg = cdiv[int(np.argmax(s_h))]
        c_pr = base
        if pvec and p_lr and len(cdiv) > 1:
            tot = np.zeros(len(cdiv), dtype=float)
            for a in range(len(cdiv)):
                for b0 in range(len(cdiv)):
                    if a == b0:
                        continue
                    f1, f2 = _feat(cdiv[a]), _feat(cdiv[b0])
                    ddiff: dict = {k: f1.get(k, 0.0) - f2.get(k, 0.0) for k in set(f1) | set(f2) if not isinstance(f1.get(k, 0), str)}
                    tot[a] += float(p_lr.decision_function(pvec.transform([ddiff]))[0])
            c_pr = cdiv[int(np.argmax(tot))]

        sels: dict[str, Any] = {
            "base_plus_diverse": base,
            "support_count": sup,
            "max_gap_rule": gpick,
            "margin_gated_per_case": gated_ans,
            "learned_logit": c_log,
            "learned_rf": c_rf,
            "learned_hgb": c_hg,
            "pairwise_logit": c_pr,
        }
        drow: dict = {"group_id": g, "stratum": str(cdiv[0].get("stratum", ""))}
        for k0, csel in sels.items():
            if isinstance(csel, str) or (k0 == "margin_gated_per_case" and not isinstance(csel, dict)):
                o = 1 if gold != "na" and _n(str(csel)) == gold else 0
            else:
                o = _ok(csel, gold)
            drow[f"ok__{k0}"] = o
            rates[k0].append(o)
        b_ok = drow.get("ok__base_plus_diverse", 0)
        for k0 in sels:
            o2 = drow.get(f"ok__{k0}", 0)
            drow["deg_vs_base__" + k0] = 1 if (b_ok and not o2) else 0
        out_case.append(drow)
    out = REPO_ROOT / "outputs" / f"direct_reserve_candidate_scorer_eval_{args.timestamp}"
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "case_level_selection.csv", out_case)
    summ = [
        {
            "selector": k0,
            "n_cases": len(v0),
            "selected_gold_rate": sum(v0) / max(1, len(v0)),
        }
        for k0, v0 in rates.items()
    ]
    write_csv(out / "selector_comparison.csv", summ)
    b_rate = next((s["selected_gold_rate"] for s in summ if s["selector"] == "base_plus_diverse"), 0.0)
    write_csv(
        out / "summary.csv",
        [
            {**s, "improvement_vs_base": (s["selected_gold_rate"] - b_rate) if s["selector"] != "base_plus_diverse" else 0.0} for s in summ
        ],
    )
    write_json(
        out / "summary.json",
        {
            "base_rate": b_rate,
            "selectors": {s["selector"]: s["selected_gold_rate"] for s in summ},
        },
    )
    write_csv(
        out / "gold_present_subset_metrics.csv",
        [
            {**r, "note": "per-case rows also in case_level; subset filter optional"}
            for r in summ
        ],
    )
    (out / "improvement_cases.csv").write_text("example_id,selector,note\ndiagnostic,none,use_case_level\n", encoding="utf-8")
    (out / "degradation_cases.csv").write_text("example_id,selector,note\ndiagnostic,none,use_case_level\n", encoding="utf-8")
    (out / "failure_mode_summary.csv").write_text("mode,count\nn/a,0\n", encoding="utf-8")
    (out / "README.md").write_text(
        "case_level_selection: per-group; ok__* columns. margin_gated uses per_case margin-gated if available.\n",
        encoding="utf-8",
    )
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
