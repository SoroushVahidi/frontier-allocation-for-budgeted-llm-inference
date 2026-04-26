#!/usr/bin/env python3
"""Diagnostic audit, cross-slice eval, and degradation analysis for learned candidate scorers."""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.learned_branch_scorer_utils import as_float, as_int, read_csv, write_csv
from scripts.train_direct_reserve_candidate_scorer import DIVERSE, MARGIN, _feat

LEARNED = ("learned_logit", "learned_rf", "learned_hgb", "pairwise_logit")
SELECTORS = (
    "base_plus_diverse",
    "support_count",
    "max_gap_rule",
    "margin_gated_per_case",
    *LEARNED,
)


def _path(text: str) -> Path:
    p = Path(text)
    return p if p.is_absolute() else REPO_ROOT / p


def _norm(v: Any) -> str:
    return str(v or "").strip().lower() or "na"


def _gid(row: dict[str, Any]) -> str:
    return f"{row.get('example_id','')}|{row.get('seed','')}|{row.get('budget','')}"


def _load_model(train_dir: str) -> dict[str, Any]:
    if not train_dir:
        return {}
    p = _path(train_dir) / "selected_model.joblib"
    if not p.exists():
        return {}
    with p.open("rb") as f:
        return pickle.load(f)


def _score_margin(values: list[float], winner: int) -> float:
    if not values:
        return 0.0
    ordered = sorted((float(v), i) for i, v in enumerate(values))
    if len(ordered) == 1:
        return abs(ordered[-1][0])
    best = ordered[-1][0]
    second = ordered[-2][0] if ordered[-1][1] == winner else ordered[-1][0]
    return float(best - second)


def _pair_scores(cands: list[dict[str, Any]], model: dict[str, Any]) -> list[float]:
    pvec, plr = model.get("pair_vectorizer"), model.get("pair_logit")
    if not pvec or not plr or len(cands) <= 1:
        return [0.0 for _ in cands]
    totals = np.zeros(len(cands), dtype=float)
    for a, b in combinations(range(len(cands)), 2):
        fa, fb = _feat(cands[a]), _feat(cands[b])
        diff = {k: fa.get(k, 0.0) - fb.get(k, 0.0) for k in set(fa) | set(fb)}
        s = float(plr.decision_function(pvec.transform([diff]))[0])
        totals[a] += s
        totals[b] -= s
    return [float(x) for x in totals]


def _choose(cands: list[dict[str, Any]], model: dict[str, Any], per_case: dict[tuple[str, int, int, str], dict[str, str]]) -> dict[str, tuple[dict[str, Any] | str, float]]:
    base = next((c for c in cands if as_int(c.get("selected_by_method", 0), 0) == 1), cands[0])
    support = max(cands, key=lambda c: (as_float(c.get("answer_group_support", 0), 0.0), str(c.get("answer_group_id", ""))))
    entropy = Counter(str(c.get("answer_group_id", "na")) for c in cands)
    total = max(1, sum(entropy.values()))
    h = -sum((v / total) * np.log2((v / total) + 1e-12) for v in entropy.values()) if len(entropy) > 1 else 0.0
    gap_pick = max(cands, key=lambda c: (as_float(c.get("top2_support_gap", 0), 0.0), -h))
    eid, seed, budget = str(cands[0].get("example_id", "")), as_int(cands[0].get("seed", 0), 0), as_int(cands[0].get("budget", 0), 0)
    mg = per_case.get((eid, seed, budget, MARGIN), {})
    margin_answer = str(mg.get("normalized_selected_answer") or base.get("normalized_answer", "na"))
    out: dict[str, tuple[dict[str, Any] | str, float]] = {
        "base_plus_diverse": (base, 0.0),
        "support_count": (support, 0.0),
        "max_gap_rule": (gap_pick, 0.0),
        "margin_gated_per_case": (margin_answer, 0.0),
        "learned_logit": (base, 0.0),
        "learned_rf": (base, 0.0),
        "learned_hgb": (base, 0.0),
        "pairwise_logit": (base, 0.0),
    }
    vec = model.get("vectorizer")
    if vec:
        X = vec.transform([_feat(c) for c in cands])
        if model.get("logistic"):
            scores = [float(x) for x in model["logistic"].decision_function(X)]
            idx = int(np.argmax(scores))
            out["learned_logit"] = (cands[idx], _score_margin(scores, idx))
        if model.get("rf"):
            scores = [float(x) for x in model["rf"].predict_proba(X)[:, 1]]
            idx = int(np.argmax(scores))
            out["learned_rf"] = (cands[idx], _score_margin(scores, idx))
        if model.get("hgb"):
            scores = [float(x) for x in model["hgb"].predict_proba(X)[:, 1]]
            idx = int(np.argmax(scores))
            out["learned_hgb"] = (cands[idx], _score_margin(scores, idx))
    ps = _pair_scores(cands, model)
    if ps:
        idx = int(np.argmax(ps))
        out["pairwise_logit"] = (cands[idx], _score_margin(ps, idx))
    return out


def _answer(sel: dict[str, Any] | str) -> str:
    if isinstance(sel, str):
        return _norm(sel)
    return _norm(sel.get("normalized_answer", "na"))


def _detail(prefix: str, group_id: str, selector: str, sel: dict[str, Any] | str, cands: list[dict[str, Any]], gold: str, base: dict[str, Any] | str, margin: float, failure_type: str) -> dict[str, Any]:
    support = Counter(str(c.get("answer_group_id", "na")) for c in cands)
    answers = [str(c.get("normalized_answer", "na")) for c in cands]
    prompts = [str(c.get("prompt_style", "NA")) for c in cands]
    first = cands[0]
    return {
        "slice": prefix,
        "group_id": group_id,
        "problem_id": str(first.get("example_id", "")),
        "problem_statement": str(first.get("question", "")),
        "gold_answer": gold,
        "base_selected_answer": _answer(base),
        "learned_selected_answer": _answer(sel),
        "selector_name": selector,
        "candidate_answers": json.dumps(answers, ensure_ascii=False),
        "answer_groups": json.dumps(sorted(set(answers)), ensure_ascii=False),
        "support_counts": json.dumps(dict(support), ensure_ascii=False),
        "prompt_styles": json.dumps(prompts, ensure_ascii=False),
        "cross_method_agreement_features": json.dumps(
            [
                {
                    "answer": c.get("normalized_answer", "na"),
                    "n_methods_sharing_norm_answer": c.get("n_methods_sharing_norm_answer", ""),
                    "match_strict_f3_final": c.get("match_strict_f3_final", ""),
                    "match_external_l1_max_final": c.get("match_external_l1_max_final", ""),
                    "match_direct_reserve_strong_v1_final": c.get("match_direct_reserve_strong_v1_final", ""),
                    "match_direct_reserve_strong_plus_diverse_v1_final": c.get("match_direct_reserve_strong_plus_diverse_v1_final", ""),
                }
                for c in cands
            ],
            ensure_ascii=False,
        ),
        "learned_score_margin": margin,
        "failure_type": failure_type,
        "stratum": str(first.get("stratum", "")),
        "problem_gold_present": max(as_int(c.get("problem_gold_present", 0), 0) for c in cands),
        "base_correct": int(_answer(base) == gold and gold != "na"),
        "learned_correct": int(_answer(sel) == gold and gold != "na"),
    }


def evaluate_slice(prefix: str, dataset_dir: str, train_dir: str, per_case_path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows = [
        dict(r)
        for r in read_csv(_path(dataset_dir) / "examples.csv")
        if as_int(r.get("excluded_from_training", 0), 0) == 0 and r.get("method") != MARGIN
    ]
    per_rows = read_csv(_path(per_case_path)) if per_case_path else []
    per = {
        (str(r.get("example_id", "")), as_int(r.get("seed", 0), 0), as_int(r.get("budget", 0), 0), str(r.get("method", ""))): r
        for r in per_rows
    }
    model = _load_model(train_dir)
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("method") == DIVERSE:
            by_group[_gid(r)].append(r)
    case_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    for group_id, cands in sorted(by_group.items()):
        gold = _norm(cands[0].get("gold_norm", "na"))
        picks = _choose(cands, model, per)
        base, _ = picks["base_plus_diverse"]
        drow: dict[str, Any] = {"slice": prefix, "group_id": group_id, "stratum": str(cands[0].get("stratum", "")), "gold_answer": gold}
        learned_answers = []
        for selector in SELECTORS:
            sel, margin = picks[selector]
            ans = _answer(sel)
            ok = int(ans == gold and gold != "na")
            drow[f"selected_answer__{selector}"] = ans
            drow[f"ok__{selector}"] = ok
            drow[f"deg_vs_base__{selector}"] = int(drow.get("ok__base_plus_diverse", 0) == 1 and ok == 0)
            drow[f"improve_vs_base__{selector}"] = int(drow.get("ok__base_plus_diverse", 0) == 0 and ok == 1)
            drow[f"score_margin__{selector}"] = margin
            if selector in LEARNED:
                learned_answers.append(ans)
                if drow[f"deg_vs_base__{selector}"]:
                    detail_rows.append(_detail(prefix, group_id, selector, sel, cands, gold, base, margin, "degradation"))
                if drow[f"improve_vs_base__{selector}"]:
                    detail_rows.append(_detail(prefix, group_id, selector, sel, cands, gold, base, margin, "improvement"))
                if max(as_int(c.get("problem_gold_present", 0), 0) for c in cands) and not ok:
                    detail_rows.append(_detail(prefix, group_id, selector, sel, cands, gold, base, margin, "gold_present_missed"))
        drow["learned_logit_rf_pairwise_agree"] = int(
            drow["selected_answer__learned_logit"] == drow["selected_answer__learned_rf"] == drow["selected_answer__pairwise_logit"]
        )
        drow["all_learned_agree"] = int(len(set(learned_answers)) == 1)
        case_rows.append(drow)
    summary = {"slice": prefix, "n_cases": len(case_rows)}
    for selector in SELECTORS:
        vals = [as_int(r.get(f"ok__{selector}", 0), 0) for r in case_rows]
        summary[f"rate__{selector}"] = sum(vals) / max(1, len(vals))
        summary[f"improvements__{selector}"] = sum(as_int(r.get(f"improve_vs_base__{selector}", 0), 0) for r in case_rows)
        summary[f"degradations__{selector}"] = sum(as_int(r.get(f"deg_vs_base__{selector}", 0), 0) for r in case_rows)
        summary[f"control_degradations__{selector}"] = sum(
            as_int(r.get(f"deg_vs_base__{selector}", 0), 0) for r in case_rows if r.get("stratum") == "control_correct"
        )
    summary["logit_rf_pairwise_agree_rate"] = sum(as_int(r.get("learned_logit_rf_pairwise_agree", 0), 0) for r in case_rows) / max(1, len(case_rows))
    return case_rows, detail_rows, summary


def _audit(timestamp: str, dataset_dir: str, train_dir: str, eval_dir: str, per_case_path: str, out_dir: Path) -> None:
    ds = read_csv(_path(dataset_dir) / "examples.csv")
    ev = read_csv(_path(eval_dir) / "case_level_selection.csv")
    sel = read_csv(_path(eval_dir) / "selector_comparison.csv")
    per = read_csv(_path(per_case_path))
    diverse_per = [r for r in per if r.get("method") == DIVERSE]
    sel_rates = {r["selector"]: as_float(r.get("selected_gold_rate", 0), 0.0) for r in sel}
    learned_rates = {k: sel_rates.get(k, 0.0) for k in LEARNED}
    best = max(learned_rates.items(), key=lambda kv: kv[1])[0] if learned_rates else ""
    control = [r for r in ev if r.get("stratum") == "control_correct"]
    audit_cases, _details, audit_summary = evaluate_slice("first_slice_audit", dataset_dir, train_dir, per_case_path)
    agree_all = int(
        bool(audit_cases)
        and all(
            r.get("selected_answer__learned_logit") == r.get("selected_answer__learned_rf") == r.get("selected_answer__pairwise_logit")
            for r in audit_cases
        )
    )
    row = {
        "timestamp": timestamp,
        "n_unique_cases": len({f"{r.get('example_id')}|{r.get('seed')}|{r.get('budget')}" for r in ds}),
        "candidate_rows": len(ds),
        "positive_candidate_rows": sum(as_int(r.get("is_gold_candidate", 0), 0) for r in ds if as_int(r.get("excluded_from_training", 0), 0) == 0),
        "gold_present_cases": sum(as_int(r.get("gold_present", 0), 0) for r in diverse_per),
        "base_selected_gold_rate": sel_rates.get("base_plus_diverse", 0.0),
        "learned_logit_selected_gold_rate": sel_rates.get("learned_logit", 0.0),
        "learned_rf_selected_gold_rate": sel_rates.get("learned_rf", 0.0),
        "learned_hgb_selected_gold_rate": sel_rates.get("learned_hgb", 0.0),
        "pairwise_logit_selected_gold_rate": sel_rates.get("pairwise_logit", 0.0),
        "support_count_selected_gold_rate": sel_rates.get("support_count", 0.0),
        "control_base_selected_gold_rate": sum(as_int(r.get("ok__base_plus_diverse", 0), 0) for r in control) / max(1, len(control)),
        "control_learned_logit_selected_gold_rate": sum(as_int(r.get("ok__learned_logit", 0), 0) for r in control) / max(1, len(control)),
        "control_learned_rf_selected_gold_rate": sum(as_int(r.get("ok__learned_rf", 0), 0) for r in control) / max(1, len(control)),
        "control_pairwise_logit_selected_gold_rate": sum(as_int(r.get("ok__pairwise_logit", 0), 0) for r in control) / max(1, len(control)),
        "n_improvement_cases_logit": audit_summary.get("improvements__learned_logit", 0),
        "n_degradation_cases_logit": audit_summary.get("degradations__learned_logit", 0),
        "n_improvement_cases_rf": audit_summary.get("improvements__learned_rf", 0),
        "n_degradation_cases_rf": audit_summary.get("degradations__learned_rf", 0),
        "n_improvement_cases_pairwise": audit_summary.get("improvements__pairwise_logit", 0),
        "n_degradation_cases_pairwise": audit_summary.get("degradations__pairwise_logit", 0),
        "best_model": best,
        "logistic_rf_pairwise_agree_all_cases": agree_all,
        "logistic_rf_pairwise_agree_rate": audit_summary.get("logit_rf_pairwise_agree_rate", 0.0),
    }
    write_csv(out_dir / "first_slice_audit.csv", [row])
    (out_dir / "README.md").write_text(
        "# First-slice learned scorer validation audit\n\nDiagnostic-only audit of the 20260426T150000Z scorer artifacts before any second API call.\n",
        encoding="utf-8",
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--first-dataset", required=True)
    p.add_argument("--first-train", required=True)
    p.add_argument("--first-eval", required=True)
    p.add_argument("--first-per-case", required=True)
    p.add_argument("--second-dataset", default="")
    p.add_argument("--second-train", default="")
    p.add_argument("--second-per-case", default="")
    p.add_argument("--combined-dataset", default="")
    p.add_argument("--combined-train", default="")
    p.add_argument("--audit-only", action="store_true")
    args = p.parse_args()

    audit_dir = REPO_ROOT / "outputs" / f"direct_reserve_candidate_scorer_validation_audit_{args.timestamp}"
    _audit(args.timestamp, args.first_dataset, args.first_train, args.first_eval, args.first_per_case, audit_dir)
    if args.audit_only:
        print(f"Wrote {audit_dir}")
        return

    scenarios = [
        ("first_model_on_second", args.second_dataset, args.first_train, args.second_per_case),
        ("second_model_on_first", args.first_dataset, args.second_train, args.first_per_case),
    ]
    if args.combined_dataset and args.combined_train:
        scenarios.append(("combined_grouped_holdout_proxy", args.combined_dataset, args.combined_train, args.second_per_case or args.first_per_case))

    cross_dir = REPO_ROOT / "outputs" / f"direct_reserve_candidate_scorer_cross_slice_eval_{args.timestamp}"
    degr_dir = REPO_ROOT / "outputs" / f"direct_reserve_candidate_scorer_degradation_analysis_{args.timestamp}"
    all_cases: list[dict[str, Any]] = []
    all_detail: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for name, ds, tr, pc in scenarios:
        if not ds or not tr or not pc:
            continue
        cases, details, summary = evaluate_slice(name, ds, tr, pc)
        all_cases.extend(cases)
        all_detail.extend(details)
        summaries.append(summary)
    selector_comparison = []
    for s in summaries:
        for selector in SELECTORS:
            selector_comparison.append(
                {
                    "scenario": s["slice"],
                    "selector": selector,
                    "n_cases": s["n_cases"],
                    "selected_gold_rate": s.get(f"rate__{selector}", 0.0),
                    "improvement_cases": s.get(f"improvements__{selector}", 0),
                    "degradation_cases": s.get(f"degradations__{selector}", 0),
                    "control_degradation_cases": s.get(f"control_degradations__{selector}", 0),
                }
            )
    write_csv(cross_dir / "summary.csv", summaries)
    write_csv(cross_dir / "selector_comparison.csv", selector_comparison)
    write_csv(cross_dir / "case_level_selection.csv", all_cases)
    write_csv(cross_dir / "improvement_cases.csv", [r for r in all_detail if r["failure_type"] == "improvement"])
    write_csv(cross_dir / "degradation_cases.csv", [r for r in all_detail if r["failure_type"] == "degradation"])
    write_csv(cross_dir / "control_degradation_cases.csv", [r for r in all_detail if r["failure_type"] == "degradation" and r.get("stratum") == "control_correct"])
    cross_dir.joinpath("README.md").write_text(
        "# Cross-slice learned candidate scorer eval\n\nDiagnostic-only selector comparisons; no runtime integration.\n",
        encoding="utf-8",
    )

    model_disagreement = [
        r
        for r in all_cases
        if len({r.get("selected_answer__learned_logit"), r.get("selected_answer__learned_rf"), r.get("selected_answer__pairwise_logit")}) > 1
    ]
    gold_present_missed = [r for r in all_detail if r["failure_type"] == "gold_present_missed"]
    write_csv(degr_dir / "degradation_cases.csv", [r for r in all_detail if r["failure_type"] == "degradation"])
    write_csv(degr_dir / "improvement_cases.csv", [r for r in all_detail if r["failure_type"] == "improvement"])
    write_csv(degr_dir / "control_degradation_cases.csv", [r for r in all_detail if r["failure_type"] == "degradation" and r.get("stratum") == "control_correct"])
    write_csv(degr_dir / "model_disagreement_cases.csv", model_disagreement)
    write_csv(degr_dir / "gold_present_missed_cases.csv", gold_present_missed)
    degr_dir.joinpath("README.md").write_text(
        "# Direct-reserve learned scorer degradation analysis\n\nCompares learned selectors against base `direct_reserve_strong_plus_diverse_v1`.\n",
        encoding="utf-8",
    )
    print(f"Wrote {audit_dir}, {cross_dir}, {degr_dir}")


if __name__ == "__main__":
    main()
