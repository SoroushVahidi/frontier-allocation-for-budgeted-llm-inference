#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from experiments.selector_error_features import build_group_feature_rows

L1 = "external_l1_max"


def nrm(x: Any) -> str:
    return str(x or "").strip().lower()


def resolve_path(path: str) -> Path:
    p = Path(path)
    return p if p.is_file() else p / "per_example_records.jsonl"


def extract_pool(md: dict[str, Any], row: dict[str, Any]) -> list[dict[str, Any]]:
    pool = md.get("selector_candidate_pool") or md.get("final_branch_states") or row.get("final_nodes") or []
    return [x for x in pool if isinstance(x, dict)] if isinstance(pool, list) else []


def build_rows(records: list[dict[str, Any]], methods: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_key: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in records:
        by_key[(r.get("example_id"), r.get("dataset"), r.get("seed"), r.get("budget"))][str(r.get("method"))] = r
    feats: list[dict[str, Any]] = []
    for key, mm in by_key.items():
        l1 = mm.get(L1)
        if not l1:
            continue
        gold = nrm(l1.get("gold_answer_canonical") or l1.get("gold_answer"))
        l1_pred = nrm(l1.get("final_answer_canonical") or l1.get("final_answer_raw") or l1.get("selected_answer_canonical") or l1.get("selected_answer_raw"))
        l1_ok = int(l1_pred == gold)
        for method in methods:
            ours = mm.get(method)
            if not ours:
                continue
            md = ours.get("result_metadata") or {}
            pool = extract_pool(md, ours)
            cand = [nrm(x.get("predicted_answer") or x.get("final_answer") or x.get("answer")) for x in pool]
            cand = [c for c in cand if c]
            groups = Counter(cand)
            ours_pred = nrm(ours.get("final_answer_canonical") or ours.get("final_answer_raw") or ours.get("selected_answer_canonical") or ours.get("selected_answer_raw"))
            ours_ok = int(ours_pred == gold)
            gold_present = int(gold in groups)

            grp_rows = []
            for ans, count in groups.items():
                grp_rows.append({"normalized_answer": ans, "final_answer": ans, "support_count": int(count), "trace": "", "ov_score": None, "prm_score": None})
            gf = build_group_feature_rows(str(ours.get("question") or ours.get("question_raw") or ""), grp_rows)
            support_max = max(groups.values()) if groups else 0
            candidate_count = len(cand)
            answer_group_count = len(groups)
            support_concentration = (support_max / max(1, candidate_count)) if candidate_count else 0.0
            dup_count = max(0, candidate_count - answer_group_count)
            srcs = [str(x.get("source_family") or x.get("source") or x.get("source_id") or "").lower() for x in pool]
            selected_source = "unknown"
            for x in pool:
                pa = nrm(x.get("predicted_answer") or x.get("final_answer") or x.get("answer"))
                if pa == ours_pred:
                    s = str(x.get("source_family") or x.get("source") or "").lower()
                    if "direct" in s:
                        selected_source = "direct"
                    elif "frontier" in s:
                        selected_source = "frontier"
            row = {
                "example_id": key[0], "dataset": key[1], "seed": key[2], "budget": key[3], "method": method,
                "candidate_count": candidate_count, "answer_group_count": answer_group_count,
                "direct_present": int(any("direct" in s for s in srcs)), "frontier_present": int(any("frontier" in s for s in srcs)),
                "selected_from_direct": int(selected_source == "direct"), "selected_from_frontier": int(selected_source == "frontier"),
                "support_concentration": float(support_concentration), "duplicate_answer_group_count": int(dup_count),
                "candidate_diversity_count": int(answer_group_count),
                "avg_unified_confidence": float(statistics.mean([g["unified_confidence_score"] for g in gf]) if gf else 0.0),
                "avg_unified_error": float(statistics.mean([g["unified_error_score"] for g in gf]) if gf else 0.0),
                "consistency_flag_rate": float(statistics.mean([sum(g["consistency_flags"].values()) for g in gf]) if gf else 0.0),
                "ov_available": int(any(g.get("ov_score") is not None for g in gf)), "prm_available": int(any(g.get("prm_score") is not None for g in gf)),
                "total_tokens": float(ours.get("total_tokens") or 0), "estimated_cost_usd": float(ours.get("estimated_cost_usd") or 0), "latency_seconds": float(ours.get("latency_seconds") or 0),
                "l1_correct_ours_wrong": int(l1_ok == 1 and ours_ok == 0), "gold_absent_from_pool": int(gold_present == 0), "gold_present_not_selected": int(gold_present == 1 and ours_ok == 0),
                "selector_only_plausible": int(gold_present == 1 and ours_ok == 0), "coverage_repair_plausible": int(gold_present == 0 and l1_ok == 1 and ours_ok == 0),
            }
            # heuristic predictions
            row["heur_low_candidate_count_pred"] = int(candidate_count <= 2)
            row["heur_high_support_concentration_pred"] = int(support_concentration >= 0.8)
            row["heur_low_diversity_pred"] = int(answer_group_count <= 1)
            row["heur_high_error_low_conf_pred"] = int(row["avg_unified_error"] >= 1.5 or row["avg_unified_confidence"] <= 0.4)
            row["heur_token_cost_anomaly_pred"] = int((row["total_tokens"] > 0 and row["candidate_count"] > 0 and row["total_tokens"] / row["candidate_count"] > 1200) or (row["estimated_cost_usd"] > 0.02))
            row["offline_utility_support_minus_error"] = float(support_max - 0.5 * row["avg_unified_error"])
            row["offline_utility_conf_minus_error"] = float(row["avg_unified_confidence"] - 0.2 * row["avg_unified_error"])
            row["offline_utility_cost_adjusted"] = float(row["avg_unified_confidence"] - 0.0001 * row["total_tokens"])
            feats.append(row)
    return feats, {"total_scored_examples": len(by_key), "usable_method_pairs": len(feats)}


def maybe_fit_logistic(rows: list[dict[str, Any]], target: str) -> dict[str, Any]:
    y = np.array([int(r[target]) for r in rows], dtype=int)
    if len(set(y.tolist())) < 2 or len(y) < 20:
        return {"status": "skipped", "reason": "insufficient_rows_or_class_diversity", "target": target}
    cols = ["candidate_count", "answer_group_count", "support_concentration", "duplicate_answer_group_count", "candidate_diversity_count", "avg_unified_confidence", "avg_unified_error", "consistency_flag_rate", "total_tokens", "estimated_cost_usd", "latency_seconds"]
    X = np.array([[float(r[c]) for c in cols] for r in rows], dtype=float)
    n = len(rows)
    cut = max(10, int(0.7 * n))
    Xtr, Xte = X[:cut], X[cut:]
    ytr, yte = y[:cut], y[cut:]
    if len(set(ytr.tolist())) < 2 or len(set(yte.tolist())) < 2:
        return {"status": "skipped", "reason": "train_test_label_degeneracy", "target": target}
    model = LogisticRegression(max_iter=2000)
    model.fit(Xtr, ytr)
    p = model.predict_proba(Xte)[:, 1]
    pred = (p >= 0.5).astype(int)
    return {
        "status": "ok", "target": target, "test_rows": int(len(yte)),
        "accuracy": float(accuracy_score(yte, pred)), "roc_auc": float(roc_auc_score(yte, p)),
        "coefficients": {c: float(v) for c, v in zip(cols, model.coef_[0], strict=True)},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", required=False, default="")
    ap.add_argument("--method", action="append", default=[])
    ap.add_argument("--output-dir", default="")
    args = ap.parse_args()

    synthetic_only = False
    if args.artifact:
        path = resolve_path(args.artifact)
    else:
        path = REPO_ROOT / "tests/fixtures/selector_oracle_synth/per_example_records.jsonl"
        synthetic_only = True
    if not path.is_file():
        path = REPO_ROOT / "tests/fixtures/selector_oracle_synth/per_example_records.jsonl"
        synthetic_only = True
    records = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    methods = args.method or sorted({str(r.get("method")) for r in records if str(r.get("method", "")).startswith("direct_reserve_semantic_frontier_v2") and "outcome" not in str(r.get("method")) and "prm" not in str(r.get("method"))})

    feat_rows, base_summary = build_rows(records, methods)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir) if args.output_dir else (REPO_ROOT / "outputs" / f"l1_loss_predictor_audit_{timestamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "l1_loss_predictor_features.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(feat_rows[0].keys()) if feat_rows else ["example_id", "method"])
        w.writeheader(); w.writerows(feat_rows)

    def heur_acc(pred_col: str, tgt: str) -> float:
        if not feat_rows:
            return 0.0
        return float(sum(int(r[pred_col] == r[tgt]) for r in feat_rows) / len(feat_rows))

    summary = {
        **base_summary,
        "artifact_path": str(path),
        "evidence_mode": "synthetic_only" if synthetic_only else "real_artifact",
        "methods": methods,
        "label_distribution": {
            "l1_correct_ours_wrong": int(sum(r["l1_correct_ours_wrong"] for r in feat_rows)),
            "gold_absent_from_pool": int(sum(r["gold_absent_from_pool"] for r in feat_rows)),
            "gold_present_not_selected": int(sum(r["gold_present_not_selected"] for r in feat_rows)),
        },
        "feature_availability": {
            "ov_available_rows": int(sum(r["ov_available"] for r in feat_rows)),
            "prm_available_rows": int(sum(r["prm_available"] for r in feat_rows)),
            "token_rows": int(sum(1 for r in feat_rows if r["total_tokens"] > 0)),
        },
        "heuristics": {
            "low_candidate_for_gold_absent_acc": heur_acc("heur_low_candidate_count_pred", "gold_absent_from_pool"),
            "high_support_concentration_for_l1_loss_acc": heur_acc("heur_high_support_concentration_pred", "l1_correct_ours_wrong"),
            "low_diversity_for_l1_loss_acc": heur_acc("heur_low_diversity_pred", "l1_correct_ours_wrong"),
            "high_error_low_conf_for_selected_failure_acc": heur_acc("heur_high_error_low_conf_pred", "gold_present_not_selected"),
            "token_cost_anomaly_for_l1_loss_acc": heur_acc("heur_token_cost_anomaly_pred", "l1_correct_ours_wrong"),
        },
        "learned_models": {
            "l1_correct_ours_wrong": maybe_fit_logistic(feat_rows, "l1_correct_ours_wrong"),
            "gold_absent_from_pool": maybe_fit_logistic(feat_rows, "gold_absent_from_pool"),
        },
    }
    (out_dir / "l1_loss_predictor_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    report = [
        "# L1-loss predictor diagnostic", "",
        f"- rows: {len(feat_rows)}", f"- evidence_mode: {summary['evidence_mode']}", f"- artifact: {path}",
        "", "## Heuristic baseline accuracy", json.dumps(summary["heuristics"], indent=2),
        "", "## Learned model status", json.dumps(summary["learned_models"], indent=2),
    ]
    (out_dir / "l1_loss_predictor_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()
