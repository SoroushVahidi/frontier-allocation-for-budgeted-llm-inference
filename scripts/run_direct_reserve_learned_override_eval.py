#!/usr/bin/env python3
"""Offline threshold sweep for diagnostic direct-reserve learned overrides."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.direct_reserve_learned_override_utils import load_scorer_payload, score_candidates, select_learned_override
from scripts.learned_branch_scorer_utils import as_int, read_csv, write_csv, write_json
from scripts.train_direct_reserve_candidate_scorer import DIVERSE, MARGIN


def _path(text: str) -> Path:
    p = Path(text)
    return p if p.is_absolute() else REPO_ROOT / p


def _norm(v: Any) -> str:
    return str(v or "").strip().lower() or "na"


def _gid(row: dict[str, Any]) -> str:
    return f"{row.get('example_id','')}|{row.get('seed','')}|{row.get('budget','')}"


def _answer(row: dict[str, Any] | str) -> str:
    if isinstance(row, str):
        return _norm(row)
    return _norm(row.get("normalized_answer") or row.get("answer_group_id") or "na")


def _selected_gold(ans: str, gold: str) -> int:
    return int(gold not in {"", "na"} and _norm(ans) == gold)


def _pick_support(cands: list[dict[str, Any]]) -> dict[str, Any]:
    return max(cands, key=lambda c: (int(float(c.get("answer_group_support") or 0)), str(c.get("answer_group_id", ""))))


def _score_pick(cands: list[dict[str, Any]], payload: dict[str, Any], model_type: str) -> tuple[dict[str, Any], float]:
    scores, _reason = score_candidates(cands, payload, model_type=model_type)
    if not scores:
        base = next((c for c in cands if as_int(c.get("selected_by_method", 0), 0) == 1), cands[0])
        return base, 0.0
    best = max(range(len(scores)), key=lambda i: float(scores[i]))
    ordered = sorted(float(x) for x in scores)
    margin = float(ordered[-1] - ordered[-2]) if len(ordered) > 1 else abs(float(ordered[-1]))
    return cands[best], margin


def _load_margin_answers(per_case: str) -> dict[tuple[str, int, int], str]:
    out: dict[tuple[str, int, int], str] = {}
    if not per_case:
        return out
    for r in read_csv(_path(per_case)):
        if str(r.get("method", "")) != MARGIN:
            continue
        out[(str(r.get("example_id", "")), as_int(r.get("seed", 0), 0), as_int(r.get("budget", 0), 0))] = _norm(
            r.get("normalized_selected_answer") or r.get("final_selected_answer") or ""
        )
    return out


def evaluate_slice(
    *,
    slice_name: str,
    dataset_dir: str,
    train_dir: str,
    per_case: str,
    thresholds: list[float],
    out_case: list[dict[str, Any]],
    missing_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload, load_meta = load_scorer_payload(_path(train_dir) / "selected_model.joblib")
    rows = [
        dict(r)
        for r in read_csv(_path(dataset_dir) / "examples.csv")
        if as_int(r.get("excluded_from_training", 0), 0) == 0 and str(r.get("method", "")) == DIVERSE
    ]
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by[_gid(r)].append(r)
    margin_answers = _load_margin_answers(per_case)
    sweep_rows: list[dict[str, Any]] = []
    selector_stats: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for group_id, cands in sorted(by.items()):
        first = cands[0]
        gold = _norm(first.get("gold_norm", "na"))
        base = next((c for c in cands if as_int(c.get("selected_by_method", 0), 0) == 1), cands[0])
        support = _pick_support(cands)
        eid, seed, budget = str(first.get("example_id", "")), as_int(first.get("seed", 0), 0), as_int(first.get("budget", 0), 0)
        margin_ans = margin_answers.get((eid, seed, budget), _answer(base))
        learned_rf, rf_margin = _score_pick(cands, payload, "random_forest")
        pairwise, pair_margin = _score_pick(cands, payload, "pairwise_logit")
        base_ans = _answer(base)
        gold_present = max(as_int(c.get("problem_gold_present", 0), 0) for c in cands)
        row_base = {
            "slice": slice_name,
            "group_id": group_id,
            "example_id": eid,
            "seed": seed,
            "budget": budget,
            "stratum": str(first.get("stratum", "")),
            "gold_answer": gold,
            "base_selected_answer": base_ans,
            "gold_present": int(gold_present),
        }
        selectors: dict[str, tuple[str, float, int]] = {
            "base_plus_diverse": (base_ans, 0.0, 0),
            "support_count": (_answer(support), 0.0, int(_answer(support) != base_ans)),
            "margin_gated_per_case": (margin_ans, 0.0, int(margin_ans != base_ans)),
            "learned_rf_offline_rerank": (_answer(learned_rf), rf_margin, int(_answer(learned_rf) != base_ans)),
            "learned_pairwise_offline_rerank": (_answer(pairwise), pair_margin, int(_answer(pairwise) != base_ans)),
        }
        for threshold in thresholds:
            res = select_learned_override(
                cands,
                base_selected_answer=base_ans,
                margin_threshold=threshold,
                model_payload=payload,
                model_type="random_forest",
            )
            ans = _norm(res.final_answer)
            selectors[f"learned_rf_override_margin_{threshold:.2f}"] = (
                ans,
                float(res.metadata.get("learned_override_margin", 0.0) or 0.0),
                int(bool(res.metadata.get("learned_override_triggered", False))),
            )
            if res.metadata.get("learned_override_missing_features"):
                missing_rows.append({**row_base, "threshold": threshold, "missing_features": ",".join(res.metadata["learned_override_missing_features"])})

        case_row = dict(row_base)
        base_ok = _selected_gold(base_ans, gold)
        for selector, (ans, margin, override) in selectors.items():
            ok = _selected_gold(ans, gold)
            rec = {
                **row_base,
                "selector": selector,
                "selected_answer": ans,
                "selected_gold": ok,
                "score_margin": margin,
                "override_triggered": override,
                "improve_vs_base": int(base_ok == 0 and ok == 1),
                "degrade_vs_base": int(base_ok == 1 and ok == 0),
                "control_degradation": int(str(first.get("stratum", "")) == "control_correct" and base_ok == 1 and ok == 0),
                "present_not_selected_fix": int(gold_present and base_ok == 0 and ok == 1),
            }
            selector_stats[selector].append(rec)
            for key in ("selected_answer", "selected_gold", "score_margin", "override_triggered", "improve_vs_base", "degrade_vs_base"):
                case_row[f"{key}__{selector}"] = rec[key]
        out_case.append(case_row)

    for selector, vals in sorted(selector_stats.items()):
        n = len(vals)
        gp = [r for r in vals if as_int(r.get("gold_present", 0), 0) == 1]
        sweep_rows.append(
            {
                "slice": slice_name,
                "selector": selector,
                "model_path": str(load_meta.get("model_path", "")),
                "n_cases": n,
                "selected_gold_rate": sum(as_int(r.get("selected_gold", 0), 0) for r in vals) / max(1, n),
                "overrides": sum(as_int(r.get("override_triggered", 0), 0) for r in vals),
                "improvements_vs_base": sum(as_int(r.get("improve_vs_base", 0), 0) for r in vals),
                "degradations_vs_base": sum(as_int(r.get("degrade_vs_base", 0), 0) for r in vals),
                "control_degradations": sum(as_int(r.get("control_degradation", 0), 0) for r in vals),
                "gold_present_selected_gold_rate": sum(as_int(r.get("selected_gold", 0), 0) for r in gp) / max(1, len(gp)),
                "present_not_selected_fixes": sum(as_int(r.get("present_not_selected_fix", 0), 0) for r in vals),
            }
        )
    details = [r for vals in selector_stats.values() for r in vals if as_int(r.get("improve_vs_base", 0), 0) or as_int(r.get("degrade_vs_base", 0), 0)]
    return sweep_rows, details


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--slice", action="append", default=[], help="name,dataset_dir,train_dir,per_case_csv")
    p.add_argument("--thresholds", default="0.00,0.02,0.05,0.10,0.20")
    args = p.parse_args()
    specs = args.slice or [
        "first_20260426T150000Z,outputs/direct_reserve_candidate_scorer_dataset_20260426T150000Z,outputs/direct_reserve_candidate_scorer_train_20260426T150000Z,outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T150000Z/per_case_method_results.csv",
        "fresh_zero_overlap,outputs/direct_reserve_candidate_scorer_dataset_20260426T_FRESH_GSM8K_SCORER_VALIDATION,outputs/direct_reserve_candidate_scorer_train_20260426T150000Z,outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T_FRESH_GSM8K_SCORER_VALIDATION/per_case_method_results.csv",
    ]
    thresholds = [float(x) for x in str(args.thresholds).split(",") if x.strip()]
    out_dir = REPO_ROOT / "outputs" / f"direct_reserve_learned_override_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    case_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    sweep_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    for spec in specs:
        parts = [x.strip() for x in spec.split(",", 3)]
        if len(parts) != 4:
            raise SystemExit(f"Bad --slice: {spec}")
        sr, det = evaluate_slice(
            slice_name=parts[0],
            dataset_dir=parts[1],
            train_dir=parts[2],
            per_case=parts[3],
            thresholds=thresholds,
            out_case=case_rows,
            missing_rows=missing_rows,
        )
        sweep_rows.extend(sr)
        detail_rows.extend(det)

    write_csv(out_dir / "threshold_sweep.csv", sweep_rows)
    write_csv(out_dir / "summary.csv", sweep_rows)
    write_csv(out_dir / "case_level_selection.csv", case_rows)
    write_csv(out_dir / "improvement_cases.csv", [r for r in detail_rows if as_int(r.get("improve_vs_base", 0), 0) == 1])
    write_csv(out_dir / "degradation_cases.csv", [r for r in detail_rows if as_int(r.get("degrade_vs_base", 0), 0) == 1])
    write_csv(out_dir / "control_degradation_cases.csv", [r for r in detail_rows if as_int(r.get("control_degradation", 0), 0) == 1])
    write_csv(out_dir / "missing_feature_cases.csv", missing_rows)
    counts = Counter(str(r.get("selector", "")) for r in detail_rows)
    write_json(out_dir / "summary.json", {"thresholds": thresholds, "detail_row_counts": dict(counts)})
    (out_dir / "README.md").write_text(
        "# Direct-reserve learned override offline evaluation\n\n"
        "Diagnostic-only threshold sweep using existing candidate scorer artifacts. No API calls are made.\n",
        encoding="utf-8",
    )
    print(f"Wrote {out_dir}")


if __name__ == "__main__":
    main()
