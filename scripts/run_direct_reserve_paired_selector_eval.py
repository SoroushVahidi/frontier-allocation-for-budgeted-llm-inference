#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

from scripts.learned_branch_scorer_utils import as_float, as_int, read_csv, write_csv, write_json
from scripts.direct_reserve_learned_override_utils import load_or_retrain_selector_model
from scripts.train_direct_reserve_candidate_scorer import _feat

BASE_METHOD = "direct_reserve_strong_plus_diverse_v1"
MARGIN_METHOD = "direct_reserve_strong_plus_diverse_margin_gated_v1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Paired selector evaluation on same direct-reserve candidate pools.")
    p.add_argument("--validation-output", required=True)
    p.add_argument(
        "--model-path",
        default="outputs/direct_reserve_candidate_scorer_train_20260426T150000Z/selected_model.joblib",
    )
    p.add_argument("--thresholds", default="0.00,0.02,0.05,0.10,0.20")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--case-limit", type=int, default=0)
    p.add_argument("--selector-model", choices=["rf", "pairwise"], default="rf")
    p.add_argument("--allow-retrain-on-load-failure", action="store_true")
    p.add_argument("--training-dataset", default="")
    p.add_argument("--model-kind", choices=["rf", "pairwise"], default="rf")
    p.add_argument("--random-seed", type=int, default=7)
    return p.parse_args()


def _path(text: str) -> Path:
    p = Path(text)
    return p if p.is_absolute() else REPO_ROOT / p


def _norm(v: Any) -> str:
    return str(v or "").strip().lower() or "na"


def _parse_thresholds(text: str) -> list[float]:
    out = [float(x.strip()) for x in str(text).split(",") if x.strip()]
    return sorted(set(out))


def _ck(row: dict[str, Any]) -> tuple[str, int, int]:
    return (str(row.get("example_id", "")), as_int(row.get("seed"), -1), as_int(row.get("budget"), -1))


def _candidate_feature_row(c: dict[str, Any], support: dict[str, int], base_row: dict[str, Any], gold: str) -> dict[str, Any]:
    ans = _norm(c.get("normalized_candidate_answer", c.get("answer_group", "na")))
    support_v = int(support.get(ans, 0))
    return {
        "method": BASE_METHOD,
        "stratum": str(base_row.get("stratum", "")),
        "source_type": "candidate_branch_table",
        "prompt_style": str(c.get("branch_prompt_style", "NA")),
        "branch_depth": as_int(c.get("branch_depth"), 0),
        "answer_group_support": support_v,
        "answer_group_rank": 1,
        "action_count": as_int(base_row.get("action_count"), 0),
        "top2_support_gap": as_float(base_row.get("top2_support_gap"), 0.0),
        "answer_entropy": as_float(base_row.get("answer_entropy"), 0.0),
        "n_methods_sharing_norm_answer": as_int(c.get("n_methods_sharing_norm_answer"), 0),
        "selected_by_method": as_int(c.get("is_selected"), 0),
        "match_strict_f3_final": 0,
        "match_external_l1_max_final": 0,
        "match_direct_reserve_strong_v1_final": 0,
        "match_direct_reserve_strong_plus_diverse_v1_final": 0,
        "extraction_ok": int(ans != "na"),
        "problem_gold_present": int(gold in support),
        "problem_present_not_selected": 0,
        "diverse_gold_in_pool": int(gold in support),
        "normalized_answer": ans,
        "is_gold_candidate": int(ans == gold),
    }


def _pairwise_scores(cands: list[dict[str, Any]], model: dict[str, Any]) -> list[float]:
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


def _select_support_count(cands: list[dict[str, Any]], base_answer: str) -> str:
    supports = Counter(str(c["normalized_answer"]) for c in cands)
    if not supports:
        return "na"
    max_v = max(supports.values())
    tied = sorted(k for k, v in supports.items() if v == max_v)
    b = _norm(base_answer)
    return b if b in tied else tied[0]


def _base_uncertain(base_row: dict[str, Any]) -> bool:
    gap = as_float(base_row.get("top2_support_gap"), 0.0)
    ent = as_float(base_row.get("answer_entropy"), 0.0)
    return bool(gap <= 0.20 or ent >= 0.80)


def _support_ok(learned_ans: str, support: dict[str, int]) -> bool:
    total = max(1, sum(int(v) for v in support.values()))
    cnt = int(support.get(learned_ans, 0))
    return bool(cnt >= 2 or (cnt / total) >= 0.50)


def _cross_method_ok(cands: list[dict[str, Any]], learned_ans: str) -> bool:
    best = max((c for c in cands if str(c.get("normalized_answer")) == str(learned_ans)), key=lambda c: as_float(c.get("score", 0.0)), default=None)
    if best is None:
        return False
    return as_int(best.get("n_methods_sharing_norm_answer"), 0) > 0


def _detect_source_type(validation: Path, overlap_with_first_slice: Any) -> tuple[str, str, Any, int]:
    name = validation.name
    overlap_val = overlap_with_first_slice
    is_true_fresh = 0
    warning = ""
    if "20260426T150000Z" in name:
        source_type = "first_slice"
    elif "FRESH_GSM8K_SCORER_VALIDATION" in name:
        source_type = "true_fresh_zero_overlap"
        if overlap_val not in ("unknown", None) and int(overlap_val) > 0:
            source_type = "overlapping_validation"
            warning = "named_fresh_but_overlap_detected"
    elif "20260426T151700Z" in name:
        source_type = "overlapping_validation"
    else:
        source_type = "unknown"
    if source_type == "true_fresh_zero_overlap" and (overlap_val in (0, "0")):
        is_true_fresh = 1
    if source_type != "true_fresh_zero_overlap":
        is_true_fresh = 0
        if not warning:
            warning = "not_true_fresh_zero_overlap"
    return source_type, warning, overlap_val if overlap_val is not None else "unknown", is_true_fresh


def main() -> None:
    args = parse_args()
    thresholds = _parse_thresholds(args.thresholds)

    validation = _path(args.validation_output)
    if not validation.exists():
        raise SystemExit(f"validation output missing: {validation}")
    out_dir = REPO_ROOT / "outputs" / f"direct_reserve_paired_selector_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = _path(args.model_path)
    training_dataset = _path(args.training_dataset) if str(args.training_dataset).strip() else None
    metadata_issues: list[dict[str, Any]] = []
    missing_feature_cases: list[dict[str, Any]] = []
    model_payload, model_meta = load_or_retrain_selector_model(
        model_path=model_path,
        allow_retrain_on_load_failure=bool(args.allow_retrain_on_load_failure),
        training_dataset=training_dataset,
        output_dir=out_dir,
        model_kind=str(args.model_kind),
        random_seed=int(args.random_seed),
    )
    model_load_status = str(model_meta.get("model_load_status", "unknown"))
    model_used_path = str(model_meta.get("model_used_path", model_path))
    if "model_load_error" in model_meta:
        metadata_issues.append(
            {
                "issue_type": "model_load_failed",
                "detail": str(model_meta.get("model_load_error")),
                "model_path": str(model_path),
            }
        )

    per_case = [dict(r) for r in read_csv(validation / "per_case_method_results.csv")]
    cand_rows = [dict(r) for r in read_csv(validation / "candidate_branch_table.csv")]
    _ags = read_csv(validation / "answer_group_summary.csv")
    if not per_case or not cand_rows:
        raise SystemExit("required input CSVs missing or empty in validation package")

    overlap_with_first_slice: Any = "unknown"
    first_slice_planned = REPO_ROOT / "outputs" / "cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T150000Z" / "planned_cases.csv"
    this_planned = validation / "planned_cases.csv"
    overlap_report = validation / "overlap_report.csv"
    if overlap_report.exists():
        rr = read_csv(overlap_report)
        if rr:
            try:
                overlap_with_first_slice = int(rr[0].get("overlap_count", rr[0].get("overlap_with_first_slice", "unknown")))
            except Exception:
                overlap_with_first_slice = "unknown"
    if overlap_with_first_slice == "unknown" and first_slice_planned.exists() and this_planned.exists():
        first_ids = {str(r.get("example_id", "")).strip() for r in read_csv(first_slice_planned) if str(r.get("example_id", "")).strip()}
        this_ids = {str(r.get("example_id", "")).strip() for r in read_csv(this_planned) if str(r.get("example_id", "")).strip()}
        overlap_with_first_slice = int(len(first_ids & this_ids))
    if overlap_with_first_slice == "unknown":
        manifest = validation / "manifest.json"
        if manifest.exists():
            try:
                raw = manifest.read_text(encoding="utf-8")
                md = __import__("json").loads(raw)
                if int(md.get("excluded_ids_count", 0)) > 0 and any("20260426T150000Z" in str(x) for x in md.get("exclude_previous_output", [])):
                    overlap_with_first_slice = int(md.get("excluded_ids_count", 0))
            except Exception:
                pass
    source_type, artifact_warning, overlap_with_first_slice, is_true_fresh = _detect_source_type(
        validation, overlap_with_first_slice
    )

    base_rows: dict[tuple[str, int, int], dict[str, Any]] = {}
    margin_rows: dict[tuple[str, int, int], dict[str, Any]] = {}
    for r in per_case:
        key = _ck(r)
        method = str(r.get("method", ""))
        if method == BASE_METHOD:
            base_rows[key] = r
        elif method == MARGIN_METHOD:
            margin_rows[key] = r

    by_case_candidates: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for c in cand_rows:
        if str(c.get("method", "")) != BASE_METHOD:
            continue
        by_case_candidates[_ck(c)].append(c)

    all_keys = sorted(set(base_rows.keys()) | set(by_case_candidates.keys()))
    if args.case_limit > 0:
        all_keys = all_keys[: args.case_limit]

    case_level_selection: list[dict[str, Any]] = []
    override_cases: list[dict[str, Any]] = []
    improvement_cases: list[dict[str, Any]] = []
    degradation_cases: list[dict[str, Any]] = []
    control_degradation_cases: list[dict[str, Any]] = []

    if model_payload is None:
        # graceful stop with metadata; do not produce misleading selector results
        summary = [
            {
                "validation_output": str(validation),
                "source_package": str(validation.name),
                "source_type": source_type,
                "overlap_with_first_slice": overlap_with_first_slice,
                "is_true_fresh_zero_overlap": is_true_fresh,
                "artifact_warning": artifact_warning,
                "selector_model": args.selector_model,
                "model_load_status": model_load_status,
                "model_used_path": model_used_path,
                "n_cases": 0,
                "base_selected_gold_rate": "",
                "support_count_selected_gold_rate": "",
                "best_threshold": "",
                "best_learned_selected_gold_rate": "",
                "best_override_count": "",
                "best_improvement_count": "",
                "best_degradation_count": "",
                "best_control_degradation_count": "",
                "missing_model_or_feature_count": len(missing_feature_cases),
                "metadata_issue_count": len(metadata_issues),
            }
        ]
        write_csv(out_dir / "summary.csv", summary)
        write_csv(out_dir / "threshold_sweep.csv", [])
        write_csv(out_dir / "case_level_selection.csv", [])
        write_csv(out_dir / "override_cases.csv", [])
        write_csv(out_dir / "improvement_cases.csv", [])
        write_csv(out_dir / "degradation_cases.csv", [])
        write_csv(out_dir / "control_degradation_cases.csv", [])
        write_csv(out_dir / "missing_feature_cases.csv", missing_feature_cases)
        write_csv(out_dir / "metadata_issues.csv", metadata_issues)
        (out_dir / "README.md").write_text(
            "\n".join(
                [
                    "# Direct reserve paired selector eval",
                    "",
                    f"- source package: `{validation.name}`",
                    f"- source type: `{source_type}`",
                    f"- overlap_with_first_slice: `{overlap_with_first_slice}`",
                    f"- is_true_fresh_zero_overlap: `{is_true_fresh}`",
                    f"- artifact_warning: `{artifact_warning}`",
                    f"- model status: `{model_load_status}`",
                    "- stopped gracefully before selector evaluation because model was unavailable and retraining was not enabled or failed",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Wrote (graceful stop): {out_dir}")
        return

    vec = model_payload.get("vectorizer")
    rf = model_payload.get("rf")
    has_pairwise = bool(model_payload.get("pair_vectorizer") and model_payload.get("pair_logit"))

    for key in all_keys:
        b = base_rows.get(key)
        cands_raw = by_case_candidates.get(key, [])
        if b is None:
            metadata_issues.append({"issue_type": "missing_base_row", "example_id": key[0], "seed": key[1], "budget": key[2]})
            continue
        if not cands_raw:
            metadata_issues.append({"issue_type": "missing_candidate_pool", "example_id": key[0], "seed": key[1], "budget": key[2]})
            continue
        gold = _norm(b.get("gold_answer", ""))
        base_ans = _norm(b.get("normalized_selected_answer", b.get("final_selected_answer", "na")))
        support = Counter(_norm(c.get("normalized_candidate_answer", c.get("answer_group", "na"))) for c in cands_raw)
        cands = [_candidate_feature_row(c, support, b, gold) for c in cands_raw]

        # same-pool marker (base and learned both from same cands list)
        same_pool_id = "|".join(sorted(set(str(c.get("normalized_answer")) for c in cands)))

        learned_ans = base_ans
        learned_margin = 0.0
        learned_selector_available = False
        learned_scores: list[float] = []
        if args.selector_model == "rf":
            if vec is None or rf is None:
                missing_feature_cases.append(
                    {"example_id": key[0], "seed": key[1], "budget": key[2], "missing": "rf_model_or_vectorizer_unavailable"}
                )
            else:
                X = vec.transform([_feat(c) for c in cands])
                learned_scores = [float(x) for x in rf.predict_proba(X)[:, 1]]
                if learned_scores:
                    learned_selector_available = True
                    order = sorted(enumerate(learned_scores), key=lambda kv: kv[1], reverse=True)
                    best_i = int(order[0][0])
                    learned_ans = str(cands[best_i]["normalized_answer"])
                    learned_margin = float(order[0][1] - (order[1][1] if len(order) > 1 else 0.0))
        else:
            if not has_pairwise:
                missing_feature_cases.append(
                    {"example_id": key[0], "seed": key[1], "budget": key[2], "missing": "pairwise_model_unavailable"}
                )
            else:
                learned_scores = _pairwise_scores(cands, model_payload)
                if learned_scores:
                    learned_selector_available = True
                    order = sorted(enumerate(learned_scores), key=lambda kv: kv[1], reverse=True)
                    best_i = int(order[0][0])
                    learned_ans = str(cands[best_i]["normalized_answer"])
                    learned_margin = float(order[0][1] - (order[1][1] if len(order) > 1 else 0.0))

        support_ans = _select_support_count(cands, base_answer=base_ans)
        margin_ans = _norm(margin_rows.get(key, {}).get("normalized_selected_answer", "na")) if key in margin_rows else "na"
        stratum = str(b.get("stratum", ""))
        base_ok = int(base_ans == gold and gold != "na")
        support_ok = int(support_ans == gold and gold != "na")
        learned_ok = int(learned_ans == gold and gold != "na")
        margin_ok = int(margin_ans == gold and gold != "na") if margin_ans != "na" else -1
        gold_present = int(gold in support)
        present_not_selected_base = int(gold_present and base_ans != gold)
        present_not_selected_fix = int(present_not_selected_base == 1 and learned_ans == gold)

        row: dict[str, Any] = {
            "example_id": key[0],
            "seed": key[1],
            "budget": key[2],
            "stratum": stratum,
            "gold_answer": gold,
            "candidate_count": len(cands),
            "answer_group_count": len(support),
            "base_selected_answer": base_ans,
            "support_selected_answer": support_ans,
            "learned_selected_answer_raw": learned_ans,
            "margin_gated_selected_answer": margin_ans,
            "base_ok": base_ok,
            "support_ok": support_ok,
            "learned_ok_raw": learned_ok,
            "margin_gated_ok": margin_ok,
            "learned_selector_available": int(learned_selector_available),
            "learned_margin": learned_margin,
            "same_candidate_pool_used": 1,
            "candidate_pool_id": same_pool_id,
            "gold_present": gold_present,
            "present_not_selected_base": present_not_selected_base,
            "present_not_selected_fix_raw": present_not_selected_fix,
        }
        base_uncertain = _base_uncertain(b)
        learned_support_ok = _support_ok(learned_ans, support)
        learned_cross_method_ok = _cross_method_ok(cands, learned_ans)
        row["base_uncertain"] = int(base_uncertain)
        row["learned_support_ok"] = int(learned_support_ok)
        row["learned_cross_method_ok"] = int(learned_cross_method_ok)

        for t in thresholds:
            override = int(learned_selector_available and learned_margin >= t and learned_ans != base_ans)
            final = learned_ans if override else base_ans
            ok = int(final == gold and gold != "na")
            row[f"threshold_{t:.2f}_override"] = override
            row[f"threshold_{t:.2f}_final_answer"] = final
            row[f"threshold_{t:.2f}_ok"] = ok
            row[f"threshold_{t:.2f}_improve_vs_base"] = int(base_ok == 0 and ok == 1)
            row[f"threshold_{t:.2f}_degrade_vs_base"] = int(base_ok == 1 and ok == 0)
            row[f"threshold_{t:.2f}_control_degradation"] = int(stratum == "control_correct" and base_ok == 1 and ok == 0)
            row[f"threshold_{t:.2f}_present_not_selected_fix"] = int(present_not_selected_base == 1 and ok == 1)
            if override:
                override_cases.append(
                    {
                        "threshold": f"{t:.2f}",
                        "example_id": key[0],
                        "seed": key[1],
                        "budget": key[2],
                        "base_answer": base_ans,
                        "learned_answer": learned_ans,
                        "learned_margin": learned_margin,
                        "gold_answer": gold,
                        "is_improvement": int(base_ok == 0 and ok == 1),
                        "is_degradation": int(base_ok == 1 and ok == 0),
                    }
                )
            if row[f"threshold_{t:.2f}_improve_vs_base"] == 1:
                improvement_cases.append({"threshold": f"{t:.2f}", "example_id": key[0], "seed": key[1], "budget": key[2]})
            if row[f"threshold_{t:.2f}_degrade_vs_base"] == 1:
                degradation_cases.append({"threshold": f"{t:.2f}", "example_id": key[0], "seed": key[1], "budget": key[2]})
            if row[f"threshold_{t:.2f}_control_degradation"] == 1:
                control_degradation_cases.append({"threshold": f"{t:.2f}", "example_id": key[0], "seed": key[1], "budget": key[2]})
        case_level_selection.append(row)

    # Summaries
    n_cases = len(case_level_selection)
    threshold_sweep: list[dict[str, Any]] = []
    for t in thresholds:
        threshold_sweep.append(
            {
                "threshold": f"{t:.2f}",
                "n_cases": n_cases,
                "base_selected_gold_rate": sum(as_int(r.get("base_ok"), 0) for r in case_level_selection) / max(1, n_cases),
                "learned_selected_gold_rate": sum(as_int(r.get(f"threshold_{t:.2f}_ok"), 0) for r in case_level_selection) / max(1, n_cases),
                "support_count_selected_gold_rate": sum(as_int(r.get("support_ok"), 0) for r in case_level_selection) / max(1, n_cases),
                "margin_gated_selected_gold_rate": (
                    sum(as_int(r.get("margin_gated_ok"), 0) for r in case_level_selection if as_int(r.get("margin_gated_ok"), -1) >= 0)
                    / max(1, sum(1 for r in case_level_selection if as_int(r.get("margin_gated_ok"), -1) >= 0))
                ),
                "override_count": sum(as_int(r.get(f"threshold_{t:.2f}_override"), 0) for r in case_level_selection),
                "improvement_count": sum(as_int(r.get(f"threshold_{t:.2f}_improve_vs_base"), 0) for r in case_level_selection),
                "degradation_count": sum(as_int(r.get(f"threshold_{t:.2f}_degrade_vs_base"), 0) for r in case_level_selection),
                "control_degradation_count": sum(
                    as_int(r.get(f"threshold_{t:.2f}_control_degradation"), 0) for r in case_level_selection
                ),
                "gold_present_rate": sum(as_int(r.get("gold_present"), 0) for r in case_level_selection) / max(1, n_cases),
                "present_not_selected_fix_count": sum(
                    as_int(r.get(f"threshold_{t:.2f}_present_not_selected_fix"), 0) for r in case_level_selection
                ),
                "missing_model_or_feature_count": len(missing_feature_cases),
            }
        )
    best = max(threshold_sweep, key=lambda r: as_float(r.get("learned_selected_gold_rate"), 0.0)) if threshold_sweep else {}
    summary = [
        {
            "validation_output": str(validation),
            "source_package": str(validation.name),
            "source_type": source_type,
            "overlap_with_first_slice": overlap_with_first_slice,
            "is_true_fresh_zero_overlap": is_true_fresh,
            "artifact_warning": artifact_warning,
            "selector_model": args.selector_model,
            "model_load_status": model_load_status,
            "model_used_path": model_used_path,
            "n_cases": n_cases,
            "base_selected_gold_rate": sum(as_int(r.get("base_ok"), 0) for r in case_level_selection) / max(1, n_cases),
            "support_count_selected_gold_rate": sum(as_int(r.get("support_ok"), 0) for r in case_level_selection) / max(1, n_cases),
            "best_threshold": best.get("threshold", ""),
            "best_learned_selected_gold_rate": best.get("learned_selected_gold_rate", ""),
            "best_override_count": best.get("override_count", ""),
            "best_improvement_count": best.get("improvement_count", ""),
            "best_degradation_count": best.get("degradation_count", ""),
            "best_control_degradation_count": best.get("control_degradation_count", ""),
            "missing_model_or_feature_count": len(missing_feature_cases),
            "metadata_issue_count": len(metadata_issues),
        }
    ]

    write_csv(out_dir / "summary.csv", summary)
    write_csv(out_dir / "threshold_sweep.csv", threshold_sweep)
    write_csv(out_dir / "case_level_selection.csv", case_level_selection)
    write_csv(out_dir / "override_cases.csv", override_cases)
    write_csv(out_dir / "improvement_cases.csv", improvement_cases)
    write_csv(out_dir / "degradation_cases.csv", degradation_cases)
    write_csv(out_dir / "control_degradation_cases.csv", control_degradation_cases)
    write_csv(out_dir / "missing_feature_cases.csv", missing_feature_cases)
    write_csv(out_dir / "metadata_issues.csv", metadata_issues)

    # policy sweep
    policy_dir = REPO_ROOT / "outputs" / f"direct_reserve_paired_selector_policy_sweep_{args.timestamp}"
    policy_rows: list[dict[str, Any]] = []
    policy_improvements: list[dict[str, Any]] = []
    policy_degradations: list[dict[str, Any]] = []
    policy_control_degradations: list[dict[str, Any]] = []
    policies = (
        "margin_only",
        "margin_plus_support",
        "margin_plus_cross_method",
        "margin_plus_base_uncertain",
        "safe_union",
    )
    for r in case_level_selection:
        base_ok = as_int(r.get("base_ok"), 0)
        base_ans = str(r.get("base_selected_answer", "na"))
        learned_ans = str(r.get("learned_selected_answer_raw", "na"))
        gold = str(r.get("gold_answer", "na"))
        stratum = str(r.get("stratum", ""))
        for t in thresholds:
            margin_cond = as_int(r.get("learned_selector_available"), 0) == 1 and as_float(r.get("learned_margin"), 0.0) >= t and learned_ans != base_ans
            support_cond = as_int(r.get("learned_support_ok"), 0) == 1
            cross_cond = as_int(r.get("learned_cross_method_ok"), 0) == 1
            uncertain_cond = as_int(r.get("base_uncertain"), 0) == 1
            policy_override = {
                "margin_only": margin_cond,
                "margin_plus_support": margin_cond and support_cond,
                "margin_plus_cross_method": margin_cond and cross_cond,
                "margin_plus_base_uncertain": margin_cond and uncertain_cond,
                "safe_union": margin_cond and (cross_cond or uncertain_cond),
            }
            for p in policies:
                ov = int(policy_override[p])
                final = learned_ans if ov else base_ans
                ok = int(final == gold and gold != "na")
                imp = int(base_ok == 0 and ok == 1)
                deg = int(base_ok == 1 and ok == 0)
                cdeg = int(stratum == "control_correct" and deg == 1)
                policy_rows.append(
                    {
                        "policy": p,
                        "threshold": f"{t:.2f}",
                        "example_id": r.get("example_id"),
                        "seed": r.get("seed"),
                        "budget": r.get("budget"),
                        "base_answer": base_ans,
                        "learned_answer": learned_ans,
                        "final_answer": final,
                        "gold_answer": gold,
                        "override": ov,
                        "base_ok": base_ok,
                        "final_ok": ok,
                        "improvement": imp,
                        "degradation": deg,
                        "control_degradation": cdeg,
                    }
                )
                if imp:
                    policy_improvements.append({"policy": p, "threshold": f"{t:.2f}", "example_id": r.get("example_id"), "seed": r.get("seed"), "budget": r.get("budget")})
                if deg:
                    policy_degradations.append({"policy": p, "threshold": f"{t:.2f}", "example_id": r.get("example_id"), "seed": r.get("seed"), "budget": r.get("budget")})
                if cdeg:
                    policy_control_degradations.append({"policy": p, "threshold": f"{t:.2f}", "example_id": r.get("example_id"), "seed": r.get("seed"), "budget": r.get("budget")})

    policy_summary: list[dict[str, Any]] = []
    for p in policies:
        for t in thresholds:
            rows = [x for x in policy_rows if x["policy"] == p and x["threshold"] == f"{t:.2f}"]
            n = max(1, len(rows))
            imp = sum(as_int(x.get("improvement"), 0) for x in rows)
            deg = sum(as_int(x.get("degradation"), 0) for x in rows)
            policy_summary.append(
                {
                    "policy": p,
                    "threshold": f"{t:.2f}",
                    "n_cases": len(rows),
                    "selected_gold_rate": sum(as_int(x.get("final_ok"), 0) for x in rows) / n,
                    "override_count": sum(as_int(x.get("override"), 0) for x in rows),
                    "improvement_count": imp,
                    "degradation_count": deg,
                    "control_degradation_count": sum(as_int(x.get("control_degradation"), 0) for x in rows),
                    "improvement_degradation_ratio": (imp / deg) if deg > 0 else float(imp),
                }
            )
    write_csv(policy_dir / "policy_summary.csv", policy_summary)
    write_csv(policy_dir / "policy_case_level_selection.csv", policy_rows)
    write_csv(policy_dir / "policy_improvement_cases.csv", policy_improvements)
    write_csv(policy_dir / "policy_degradation_cases.csv", policy_degradations)
    write_csv(policy_dir / "policy_control_degradation_cases.csv", policy_control_degradations)
    (policy_dir / "README.md").write_text(
        "\n".join(
            [
                "# Direct reserve paired selector policy sweep",
                "",
                f"- source package: `{validation.name}`",
                f"- source type: `{source_type}`",
                f"- overlap_with_first_slice: `{overlap_with_first_slice}`",
                f"- is_true_fresh_zero_overlap: `{is_true_fresh}`",
                "- Same candidate pools are reused across policy variants.",
                "- Diagnostic-only; not canonical evidence.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / "README.md").write_text(
        "\n".join(
            [
                "# Direct reserve paired selector eval",
                "",
                "- Uses the same candidate pool (`candidate_branch_table.csv` for base method) for all selector comparisons.",
                "- No API calls are made.",
                f"- Validation input: `{validation}`",
                f"- Source package: `{validation.name}`",
                f"- Source type: `{source_type}`",
                f"- overlap_with_first_slice: `{overlap_with_first_slice}`",
                f"- is_true_fresh_zero_overlap: `{is_true_fresh}`",
                f"- artifact_warning: `{artifact_warning}`",
                f"- Selector model: `{args.selector_model}`",
                f"- Model status: `{model_load_status}`",
                f"- Model path used: `{model_used_path}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()

