#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments import support_aware_selector as sas
from experiments.robust_answer_parser import (
    CONF_AMBIGUOUS,
    CONF_HIGH,
    CONF_LOW,
    CONF_MED,
    answers_equivalent,
    parse_final_answer,
)

REQUIRED_METHODS = (
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
)

POLICIES = ("frontier", "fix2", "fix24", "fix5", "l1", "s1", "tale")
VARIANTS = ("R0", "P1", "P2", "P3", "P4")

EXPLICIT_CUES = {
    "hashes",
    "boxed",
    "answer_colon",
    "final_answer_colon",
    "the_answer_is",
    "so_the_answer_is",
    "therefore_the_answer_is",
    "thus_the_answer_is",
    "in_total",
    "altogether",
}


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    path: Path
    split: str


@dataclass
class ParseInfo:
    method: str
    raw_answer: str
    current_canonical: str | None
    robust_canonical: str | None
    robust_confidence: str
    robust_cue: str
    robust_ambiguous: bool
    robust_competing_candidates: int
    robust_operator_density: float
    used_fix8: bool
    chosen_canonical: str | None
    abstained_to_current: bool


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _group_complete(rows: list[dict[str, Any]]) -> dict[tuple[str, str, int, int], dict[str, dict[str, Any]]]:
    grouped: dict[tuple[str, str, int, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = (
            str(row.get("dataset") or ""),
            str(row.get("example_id") or ""),
            int(row.get("seed") or 0),
            int(row.get("budget") or 0),
        )
        grouped[key][str(row.get("method") or "")] = row
    return {k: v for k, v in grouped.items() if all(m in v for m in REQUIRED_METHODS)}


def _raw_answer(row: dict[str, Any]) -> str:
    for k in ("final_answer_raw", "selected_answer_raw", "controller_final_answer_raw", "repair_answer_raw", "final_answer_canonical"):
        v = row.get(k)
        if v not in (None, ""):
            return str(v)
    return ""


def _current_canonical(row: dict[str, Any]) -> str | None:
    for k in ("final_answer_canonical", "selected_answer_canonical"):
        v = row.get(k)
        if v not in (None, "", "None", "none"):
            return sas._normalize_answer(v)
    raw = _raw_answer(row)
    return sas._normalize_answer(raw)


def _decimal_string(x: float) -> str:
    s = f"{x:.12f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _robust_to_policy_canonical(selected: Any) -> str | None:
    if selected is None:
        return None
    can = selected.canonical_value
    if can in (None, ""):
        return None
    if selected.numeric_value is not None:
        val = float(selected.numeric_value)
        if selected.unit == "usd_cent":
            val = val / 100.0
        return sas._normalize_answer(_decimal_string(val))
    return sas._normalize_answer(can)


def _use_fix8_variant(variant: str, current: str | None, robust: str | None, confidence: str, cue: str, ambiguous: bool) -> bool:
    if variant == "R0":
        return False
    if robust is None:
        return False
    if variant == "P1":
        return (cue in {"hashes", "boxed"}) and (confidence == CONF_HIGH) and (not ambiguous)
    if variant == "P2":
        return (cue in EXPLICIT_CUES) and (confidence in {CONF_HIGH, CONF_MED}) and (not ambiguous)
    if variant == "P3":
        return not ambiguous and confidence != CONF_AMBIGUOUS
    if variant == "P4":
        return (confidence in {CONF_HIGH, CONF_MED}) and (not ambiguous) and (sas._normalize_answer(current) != sas._normalize_answer(robust))
    return False


def _is_correct(ans: str | None, gold: str | None) -> bool:
    if ans in (None, "") or gold in (None, ""):
        return False
    return answers_equivalent(str(ans), str(gold))


def _build_parse_info(row: dict[str, Any], method: str, variant: str) -> ParseInfo:
    raw = _raw_answer(row)
    current = _current_canonical(row)
    decision = parse_final_answer(raw)
    selected = decision.selected
    robust_can = _robust_to_policy_canonical(selected)
    conf = selected.confidence if selected is not None else CONF_AMBIGUOUS
    cue = selected.cue_type if selected is not None else "none"
    amb = bool(decision.ambiguous)
    comp = int(selected.competing_candidates) if selected is not None else 0
    op = float(selected.operator_density) if selected is not None else 0.0

    use_fix8 = _use_fix8_variant(variant, current, robust_can, conf, cue, amb)
    chosen = robust_can if use_fix8 else current

    return ParseInfo(
        method=method,
        raw_answer=raw,
        current_canonical=current,
        robust_canonical=robust_can,
        robust_confidence=conf,
        robust_cue=cue,
        robust_ambiguous=amb,
        robust_competing_candidates=comp,
        robust_operator_density=op,
        used_fix8=use_fix8,
        chosen_canonical=chosen,
        abstained_to_current=not use_fix8,
    )


def _policy_answers_from_group(mm: dict[str, dict[str, Any]], parsed_by_method: dict[str, ParseInfo]) -> dict[str, str | None]:
    frontier_row = dict(mm["direct_reserve_semantic_frontier_v2"])
    frontier_row["final_answer_canonical"] = parsed_by_method["direct_reserve_semantic_frontier_v2"].chosen_canonical
    frontier_row["selected_answer_canonical"] = parsed_by_method["direct_reserve_semantic_frontier_v2"].chosen_canonical

    ext_answers = {
        "external_l1_max": parsed_by_method["external_l1_max"].chosen_canonical,
        "external_s1_budget_forcing": parsed_by_method["external_s1_budget_forcing"].chosen_canonical,
        "external_tale_prompt_budgeting": parsed_by_method["external_tale_prompt_budgeting"].chosen_canonical,
    }

    fix2_row = sas.apply_fix2_to_row(frontier_row, external_answers=ext_answers)
    fix24_row = sas.apply_combined_fix24_to_row(frontier_row, external_answers=ext_answers)
    fix5_row = sas.apply_fix5_tale_default_router(frontier_row, external_answers=ext_answers)

    return {
        "frontier": parsed_by_method["direct_reserve_semantic_frontier_v2"].chosen_canonical,
        "fix2": sas._normalize_answer(fix2_row.get("fix2_answer_canonical")),
        "fix24": sas._normalize_answer(fix24_row.get("combined24_answer_canonical")),
        "fix5": sas._normalize_answer(fix5_row.get("fix5_answer_canonical")),
        "l1": parsed_by_method["external_l1_max"].chosen_canonical,
        "s1": parsed_by_method["external_s1_budget_forcing"].chosen_canonical,
        "tale": parsed_by_method["external_tale_prompt_budgeting"].chosen_canonical,
    }


def _final300_failure_labels(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[str(row.get("example_id") or "")] = str(row.get("root_cause_label") or "")
    return out


def _choose_primary_variant(final300_summary: list[dict[str, Any]]) -> str:
    cands = [r for r in final300_summary if r["variant"] in {"P2", "P3"} and r["policy"] == "fix24"]
    if not cands:
        return "P2"
    cands.sort(key=lambda r: (float(r["net_delta_correct"]), -float(r["regressions"]), float(r["accuracy"])), reverse=True)
    return str(cands[0]["variant"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, default=None)
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir or (repo_root / f"outputs/fix8_parser_canonicalizer_eval_20260520_{stamp}")
    out_dir.mkdir(parents=True, exist_ok=False)

    artifacts = [
        ArtifactSpec(
            name="main_300_seed41",
            path=repo_root / "outputs/overnight_fix5_promotion_grade_validation_20260519T040621Z/runner_output/cohere_real_model_cost_normalized_validation_fix5_overnight_live_20260519T040621Z/per_example_records.jsonl",
            split="main300",
        ),
        ArtifactSpec(
            name="independent_120_seed61",
            path=repo_root / "outputs/fix6_lovec_independent_extra_action_pilot_20260519T163021Z/base_runner_output/cohere_real_model_cost_normalized_validation_base_live_20260519T163021Z/per_example_records.jsonl",
            split="independent120",
        ),
        ArtifactSpec(
            name="final_300_seed71",
            path=repo_root / "outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/runner_output/cohere_real_model_cost_normalized_validation_final_fix24_live_20260519/per_example_records.jsonl",
            split="final300",
        ),
    ]

    failure_label_map = _final300_failure_labels(
        repo_root
        / "outputs/final300_fix7_generalization_and_failure_patterns_20260520_20260520T031533Z/final300_failure_root_cause_labels.csv"
    )

    grouped_all: dict[str, dict[tuple[str, str, int, int], dict[str, dict[str, Any]]]] = {}
    for a in artifacts:
        grouped_all[a.name] = _group_complete(_load_jsonl(a.path))

    parse_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    recovery_rows: list[dict[str, Any]] = []
    regression_rows: list[dict[str, Any]] = []
    ambiguous_rows: list[dict[str, Any]] = []

    by_scope_variant_policy: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for variant in VARIANTS:
        for art in artifacts:
            groups = grouped_all[art.name]
            for (dataset, example_id, seed, budget), mm in groups.items():
                parsed: dict[str, ParseInfo] = {}
                for m in REQUIRED_METHODS:
                    parsed[m] = _build_parse_info(mm[m], m, variant)

                for m, info in parsed.items():
                    row = {
                        "variant": variant,
                        "artifact": art.name,
                        "split": art.split,
                        "dataset": dataset,
                        "example_id": example_id,
                        "seed": seed,
                        "budget": budget,
                        "method": m,
                        "raw_answer": info.raw_answer,
                        "current_canonical": info.current_canonical,
                        "robust_canonical": info.robust_canonical,
                        "robust_confidence": info.robust_confidence,
                        "robust_cue": info.robust_cue,
                        "robust_ambiguous": int(info.robust_ambiguous),
                        "competing_candidates": info.robust_competing_candidates,
                        "operator_density": info.robust_operator_density,
                        "used_fix8": int(info.used_fix8),
                        "abstained_to_current": int(info.abstained_to_current),
                        "changed": int(sas._normalize_answer(info.chosen_canonical) != sas._normalize_answer(info.current_canonical)),
                    }
                    parse_rows.append(row)
                    if info.robust_ambiguous:
                        ambiguous_rows.append(row)

                answers = _policy_answers_from_group(mm, parsed)

                gold = str(mm["direct_reserve_semantic_frontier_v2"].get("gold_answer_canonical") or mm["direct_reserve_semantic_frontier_v2"].get("gold_answer") or "")

                corr = {p: _is_correct(answers[p], gold) for p in POLICIES}

                # Baseline R0 reference for recoveries/regressions.
                parsed_r0: dict[str, ParseInfo] = {}
                for m in REQUIRED_METHODS:
                    parsed_r0[m] = _build_parse_info(mm[m], m, "R0")
                ans_r0 = _policy_answers_from_group(mm, parsed_r0)
                corr_r0 = {p: _is_correct(ans_r0[p], gold) for p in POLICIES}

                base_row = {
                    "variant": variant,
                    "artifact": art.name,
                    "split": art.split,
                    "dataset": dataset,
                    "example_id": example_id,
                    "seed": seed,
                    "budget": budget,
                    "gold_answer": gold,
                    "root_cause_label": failure_label_map.get(example_id, ""),
                }

                for p in POLICIES:
                    base_row[f"{p}_answer"] = answers[p]
                    base_row[f"{p}_correct"] = int(corr[p])
                    base_row[f"{p}_answer_r0"] = ans_r0[p]
                    base_row[f"{p}_correct_r0"] = int(corr_r0[p])
                    base_row[f"{p}_changed_from_r0"] = int(sas._normalize_answer(answers[p]) != sas._normalize_answer(ans_r0[p]))
                    base_row[f"{p}_delta_correct"] = int(corr[p]) - int(corr_r0[p])

                    by_scope_variant_policy[(art.split, variant, p)].append(
                        {
                            "correct": int(corr[p]),
                            "correct_r0": int(corr_r0[p]),
                            "changed": int(sas._normalize_answer(answers[p]) != sas._normalize_answer(ans_r0[p])),
                        }
                    )
                    by_scope_variant_policy[("aggregate720", variant, p)].append(
                        {
                            "correct": int(corr[p]),
                            "correct_r0": int(corr_r0[p]),
                            "changed": int(sas._normalize_answer(answers[p]) != sas._normalize_answer(ans_r0[p])),
                        }
                    )

                case_rows.append(base_row)

                if art.split == "final300" and variant != "R0":
                    if (not corr_r0["fix24"]) and corr["fix24"]:
                        recovery_rows.append(base_row)
                    if corr_r0["fix24"] and (not corr["fix24"]):
                        regression_rows.append(base_row)

    # Summaries for final300 and aggregate720.
    final300_eval: list[dict[str, Any]] = []
    aggregate_eval: list[dict[str, Any]] = []

    for scope, out in (("final300", final300_eval), ("aggregate720", aggregate_eval)):
        for variant in VARIANTS:
            for p in POLICIES:
                rows = by_scope_variant_policy.get((scope, variant, p), [])
                if not rows:
                    continue
                n = len(rows)
                correct = sum(r["correct"] for r in rows)
                correct_r0 = sum(r["correct_r0"] for r in rows)
                changed = sum(r["changed"] for r in rows)
                recoveries = sum(1 for r in rows if r["correct_r0"] == 0 and r["correct"] == 1)
                regressions = sum(1 for r in rows if r["correct_r0"] == 1 and r["correct"] == 0)
                out.append(
                    {
                        "scope": scope,
                        "variant": variant,
                        "policy": p,
                        "n": n,
                        "correct": correct,
                        "accuracy": round(correct / n, 6),
                        "correct_r0": correct_r0,
                        "accuracy_r0": round(correct_r0 / n, 6),
                        "delta_pp_vs_r0": round((correct - correct_r0) * 100.0 / n, 4),
                        "answer_changed": changed,
                        "recoveries": recoveries,
                        "regressions": regressions,
                        "net_delta_correct": recoveries - regressions,
                        "no_change": n - recoveries - regressions,
                    }
                )

    # Stress test on parser/canonicalization failures (final300 label set).
    parser_fail_ids = {eid for eid, label in failure_label_map.items() if label == "parser_or_canonicalization_issue"}

    primary_variant = _choose_primary_variant(final300_eval)

    stress_rows: list[dict[str, Any]] = []
    for r in case_rows:
        if r["split"] != "final300":
            continue
        if r["variant"] != primary_variant:
            continue
        eid = str(r["example_id"])
        if eid not in parser_fail_ids:
            continue

        pr = next(
            (
                p
                for p in parse_rows
                if p["variant"] == primary_variant
                and p["split"] == "final300"
                and p["example_id"] == eid
                and p["method"] == "direct_reserve_semantic_frontier_v2"
            ),
            None,
        )
        stress_rows.append(
            {
                "dataset": r["dataset"],
                "example_id": eid,
                "seed": r["seed"],
                "budget": r["budget"],
                "old_parser_fix24_answer": r["fix24_answer_r0"],
                "fix8_fix24_answer": r["fix24_answer"],
                "offline_gold_answer": r["gold_answer"],
                "cue_used": (pr or {}).get("robust_cue", ""),
                "parser_confidence": (pr or {}).get("robust_confidence", ""),
                "ambiguous": (pr or {}).get("robust_ambiguous", ""),
                "recovery_legitimate": int(r["fix24_correct_r0"] == 0 and r["fix24_correct"] == 1),
                "still_wrong": int(r["fix24_correct"] == 0),
            }
        )

    # Counterexample audit: parser-risk features where baseline already correct.
    counterexample_rows: list[dict[str, Any]] = []
    for pr in parse_rows:
        if pr["split"] != "final300" or pr["variant"] != primary_variant:
            continue
        risk = (
            pr["robust_ambiguous"] == 1
            or pr["robust_confidence"] in {CONF_LOW, CONF_AMBIGUOUS}
            or int(pr["competing_candidates"]) > 1
            or float(pr["operator_density"]) > 0.08
        )
        if not risk:
            continue

        match = next(
            (
                c
                for c in case_rows
                if c["split"] == "final300"
                and c["variant"] == primary_variant
                and c["example_id"] == pr["example_id"]
            ),
            None,
        )
        if not match:
            continue
        # Focus on cases where baseline policy already correct.
        if int(match["fix24_correct_r0"]) != 1:
            continue
        counterexample_rows.append(
            {
                "example_id": pr["example_id"],
                "method": pr["method"],
                "risk_confidence": pr["robust_confidence"],
                "risk_ambiguous": pr["robust_ambiguous"],
                "risk_competing_candidates": pr["competing_candidates"],
                "risk_operator_density": pr["operator_density"],
                "baseline_fix24_correct": match["fix24_correct_r0"],
                "variant_fix24_correct": match["fix24_correct"],
                "variant_fix24_delta": match["fix24_delta_correct"],
                "baseline_fix24_answer": match["fix24_answer_r0"],
                "variant_fix24_answer": match["fix24_answer"],
            }
        )

    # Choose next decision conservatively.
    def _find(summary: list[dict[str, Any]], variant: str, policy: str) -> dict[str, Any] | None:
        for row in summary:
            if row["variant"] == variant and row["policy"] == policy:
                return row
        return None

    primary_f300 = _find(final300_eval, primary_variant, "fix24") or {}
    primary_agg = _find(aggregate_eval, primary_variant, "fix24") or {}
    p1_f300 = _find(final300_eval, "P1", "fix24") or {}

    decision = "B"
    rationale = "Prototype shows parser-side signal but needs conservative validation before promotion."

    f300_delta = float(primary_f300.get("delta_pp_vs_r0", 0.0))
    agg_delta = float(primary_agg.get("delta_pp_vs_r0", 0.0))
    f300_reg = int(primary_f300.get("regressions", 0))
    agg_reg = int(primary_agg.get("regressions", 0))
    f300_rec = int(primary_f300.get("recoveries", 0))

    if agg_delta >= 0.5 and f300_delta >= 0.5 and f300_reg <= 1 and agg_reg <= 2:
        decision = "A"
        rationale = "Broad offline gains with very low regressions on final300 and aggregate720."
    elif (f300_rec == 0 and f300_reg > 0) or agg_delta < 0:
        decision = "E"
        rationale = "Regressions outweigh recoveries or aggregate delta is negative."
    elif float(p1_f300.get("delta_pp_vs_r0", 0.0)) >= f300_delta and int(p1_f300.get("regressions", 0)) <= f300_reg:
        decision = "C"
        rationale = "Explicit-cue-only anchoring is safer than broader parser variant by offline tradeoff."
    elif len(stress_rows) < 12 or len(counterexample_rows) > 0.5 * max(1, len(stress_rows)):
        decision = "D"
        rationale = "Manual parser audit recommended due ambiguity/risk concentration."

    parser_policy_def = {
        "name": "fix8_robust_parser_canonicalizer_prototype",
        "runtime_gold_free": True,
        "variants": {
            "R0": "Current parser/canonicalization baseline.",
            "P1": "Apply FIX-8 only for explicit #### or boxed cues.",
            "P2": "Apply FIX-8 on explicit final-answer cues; abstain on low/ambiguous confidence.",
            "P3": "Apply FIX-8 full conservative hierarchy; abstain only on ambiguous outcomes.",
            "P4": "Apply FIX-8 only when confidence high/medium and output differs from current parser.",
        },
        "primary_candidate": primary_variant,
    }

    parser_metric_summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out_dir),
        "artifacts": [{"name": a.name, "path": str(a.path), "split": a.split} for a in artifacts],
        "primary_candidate": primary_variant,
        "decision": decision,
        "decision_rationale": rationale,
        "final300_fix24": primary_f300,
        "aggregate720_fix24": primary_agg,
        "stress_parser_issue_case_count": len(stress_rows),
        "parser_issue_reference_count": len(parser_fail_ids),
        "ambiguous_parse_rows": len(ambiguous_rows),
        "counterexample_risk_rows": len(counterexample_rows),
        "safety": {
            "no_api_calls": True,
            "no_tmux": True,
            "offline_gold_only": True,
            "outputs_not_overwritten": True,
        },
    }

    # Reports.
    _write_csv(
        out_dir / "fix8_case_decisions.csv",
        case_rows,
        sorted({k for r in case_rows for k in r.keys()}),
    )
    _write_csv(
        out_dir / "fix8_parser_ambiguous_cases.csv",
        ambiguous_rows,
        sorted({k for r in ambiguous_rows for k in r.keys()}),
    )
    _write_csv(
        out_dir / "fix8_parser_stress_test_cases.csv",
        stress_rows,
        sorted({k for r in stress_rows for k in r.keys()}) if stress_rows else [
            "dataset",
            "example_id",
            "seed",
            "budget",
            "old_parser_fix24_answer",
            "fix8_fix24_answer",
            "offline_gold_answer",
            "cue_used",
            "parser_confidence",
            "ambiguous",
            "recovery_legitimate",
            "still_wrong",
        ],
    )
    _write_csv(
        out_dir / "fix8_counterexample_audit.csv",
        counterexample_rows,
        sorted({k for r in counterexample_rows for k in r.keys()}) if counterexample_rows else [
            "example_id",
            "method",
            "risk_confidence",
            "risk_ambiguous",
            "risk_competing_candidates",
            "risk_operator_density",
            "baseline_fix24_correct",
            "variant_fix24_correct",
            "variant_fix24_delta",
            "baseline_fix24_answer",
            "variant_fix24_answer",
        ],
    )
    _write_csv(
        out_dir / "fix8_final300_eval.csv",
        final300_eval,
        [
            "scope",
            "variant",
            "policy",
            "n",
            "correct",
            "accuracy",
            "correct_r0",
            "accuracy_r0",
            "delta_pp_vs_r0",
            "answer_changed",
            "recoveries",
            "regressions",
            "net_delta_correct",
            "no_change",
        ],
    )
    _write_csv(
        out_dir / "fix8_aggregate720_eval.csv",
        aggregate_eval,
        [
            "scope",
            "variant",
            "policy",
            "n",
            "correct",
            "accuracy",
            "correct_r0",
            "accuracy_r0",
            "delta_pp_vs_r0",
            "answer_changed",
            "recoveries",
            "regressions",
            "net_delta_correct",
            "no_change",
        ],
    )

    with (out_dir / "fix8_parser_recovery_cases.jsonl").open("w", encoding="utf-8") as f:
        for r in recovery_rows:
            f.write(json.dumps(r) + "\n")
    with (out_dir / "fix8_parser_regression_cases.jsonl").open("w", encoding="utf-8") as f:
        for r in regression_rows:
            f.write(json.dumps(r) + "\n")

    with (out_dir / "fix8_parser_policy_definition.json").open("w", encoding="utf-8") as f:
        json.dump(parser_policy_def, f, indent=2)
    with (out_dir / "fix8_parser_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(parser_metric_summary, f, indent=2)
    with (out_dir / "fix8_next_decision.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "decision": decision,
                "rationale": rationale,
                "primary_candidate": primary_variant,
                "final300_fix24": primary_f300,
                "aggregate720_fix24": primary_agg,
                "parser_issue_reference_count": len(parser_fail_ids),
                "stress_parser_issue_case_count": len(stress_rows),
                "counterexample_risk_rows": len(counterexample_rows),
                "safety": {
                    "no_api_calls": True,
                    "offline_gold_only": True,
                },
            },
            f,
            indent=2,
        )
    with (out_dir / "metrics.json").open("w", encoding="utf-8") as f:
        json.dump(parser_metric_summary, f, indent=2)

    # Human-readable report.
    r0_f300 = _find(final300_eval, "R0", "fix24") or {}
    r0_agg = _find(aggregate_eval, "R0", "fix24") or {}
    rep_lines = [
        "# FIX-8 Robust Parser/Canonicalizer Offline Evaluation",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Output root: `{out_dir}`",
        "",
        "## Policy Scope",
        "- Runtime parser/canonicalizer only; no model generations changed.",
        "- No API calls, no tmux, no training.",
        "",
        "## Variants",
        "- R0: current parser baseline.",
        "- P1: explicit `####`/boxed anchoring only.",
        "- P2: cue-anchored parser with low/ambiguous abstain.",
        "- P3: full conservative parser with ambiguous abstain.",
        "- P4: confidence guard (high/medium + differs from baseline).",
        "",
        "## FIX-2+FIX-4 (fix24) Summary",
        f"- Final300 baseline R0 accuracy: {float(r0_f300.get('accuracy', 0.0))*100:.2f}% ({r0_f300.get('correct', 0)}/{r0_f300.get('n', 0)})",
        f"- Final300 {primary_variant} accuracy: {float(primary_f300.get('accuracy', 0.0))*100:.2f}% ({primary_f300.get('correct', 0)}/{primary_f300.get('n', 0)}), delta {float(primary_f300.get('delta_pp_vs_r0', 0.0)):+.2f} pp",
        f"- Aggregate720 baseline R0 accuracy: {float(r0_agg.get('accuracy', 0.0))*100:.2f}% ({r0_agg.get('correct', 0)}/{r0_agg.get('n', 0)})",
        f"- Aggregate720 {primary_variant} accuracy: {float(primary_agg.get('accuracy', 0.0))*100:.2f}% ({primary_agg.get('correct', 0)}/{primary_agg.get('n', 0)}), delta {float(primary_agg.get('delta_pp_vs_r0', 0.0)):+.2f} pp",
        "",
        "## Parser-Failure Stress Slice (12-case reference)",
        f"- Referenced parser/canonicalization failures: {len(parser_fail_ids)}",
        f"- Stress rows evaluated under primary candidate: {len(stress_rows)}",
        "",
        "## Decision",
        f"- Primary candidate: {primary_variant}",
        f"- Next decision: {decision}",
        f"- Rationale: {rationale}",
    ]
    (out_dir / "fix8_parser_eval_report.md").write_text("\n".join(rep_lines), encoding="utf-8")

    print(out_dir)


if __name__ == "__main__":
    main()
