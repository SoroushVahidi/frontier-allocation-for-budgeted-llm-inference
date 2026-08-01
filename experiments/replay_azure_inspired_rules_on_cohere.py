"""Offline replay of Azure-inspired External-3/SWFB rules on Cohere Aggregate-720.

Reads cached JSONL only — no API calls. Does not promote any rule or change
canonical FTA/FIX-2+FIX-4 selector logic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.analyze_azure_distribution_shift import (
    AZURE_DEFAULT_VALIDATION_PATH,
    build_cohere_aggregate,
    build_corpus,
    enrich_feature_row,
)
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import write_csv, write_json, write_jsonl, write_text
from experiments.mine_pattern_cause_repair import (
    build_repair_rule_specs,
    decision_repair_primary_plus_unanimity_fallback,
)
from experiments.stress_test_exploratory_rules import (
    audit_rule_decision_legality,
    decision_canonical_fta,
    decision_external3_majority,
    decision_pooled4_majority,
    evaluate_rule_full,
    paired_bootstrap_ci,
)

SWFB = "single_weak_frontier_branch"

REPLAY_FEATURE_FIELDS = [
    "row_id",
    "example_id",
    "source_id",
    "seed",
    "question_hash",
    "problem_text",
    "gold_answer_canonical",
    "frontier_answer_canonical",
    "l1_answer_canonical",
    "s1_answer_canonical",
    "tale_answer_canonical",
    "external3_answer",
    "pooled4_answer",
    "fta_selected_answer_canonical",
    "frontier_correct",
    "l1_correct",
    "s1_correct",
    "tale_correct",
    "external3_correct",
    "pooled4_correct",
    "fta_correct",
    "fta_selected_source",
    "effective_fix2_action",
    "effective_fix4_action",
    "no_effective_gate_action",
    "effective_policy_label",
    "override_reason",
    "single_weak_frontier_branch",
    "frontier_support",
    "support_margin",
    "support_margin_comparable",
    "direct_frontier_agree",
    "direct_frontier_agree_comparable",
    "external_answers_unanimous",
    "external_unanimous_against_frontier",
    "two_of_three_external_against_frontier",
    "candidate_pool_answer_group_count",
    "parser_failure_any",
    "failure_class_coarse",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--azure-input", default=AZURE_DEFAULT_VALIDATION_PATH)
    parser.add_argument(
        "--azure-results-csv",
        default="outputs/failure_analysis/azure_distribution_shift_20260708T215727Z/AZURE_EXPLORATORY_RULE_RESULTS.csv",
        help="Prior Azure exploratory rule results for cross-provider comparison.",
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--bootstrap-resamples", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=1234)
    return parser.parse_args()


def _timestamp_dir() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("outputs/failure_analysis") / f"cohere_replay_azure_inspired_rules_{ts}"


def _question_hash(text: str | None) -> str | None:
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_replay_feature_row(row: dict[str, Any]) -> dict[str, Any]:
    """Cohere replay table row with explicit comparability flags."""
    support_margin = row.get("support_margin")
    dfa = row.get("direct_frontier_agree")
    return {
        **{k: row.get(k) for k in REPLAY_FEATURE_FIELDS if k in row or k not in row},
        "row_id": row.get("row_id"),
        "example_id": row.get("example_id"),
        "source_id": row.get("source_id"),
        "seed": row.get("seed"),
        "question_hash": _question_hash(row.get("problem_text")),
        "problem_text": row.get("problem_text"),
        "gold_answer_canonical": row.get("gold_answer_canonical"),
        "frontier_answer_canonical": row.get("frontier_answer_canonical"),
        "l1_answer_canonical": row.get("l1_answer_canonical"),
        "s1_answer_canonical": row.get("s1_answer_canonical"),
        "tale_answer_canonical": row.get("tale_answer_canonical"),
        "external3_answer": row.get("external3_answer"),
        "pooled4_answer": row.get("pooled4_answer"),
        "fta_selected_answer_canonical": row.get("fta_selected_answer_canonical"),
        "frontier_correct": row.get("frontier_correct"),
        "l1_correct": row.get("l1_correct"),
        "s1_correct": row.get("s1_correct"),
        "tale_correct": row.get("tale_correct"),
        "external3_correct": row.get("external3_correct"),
        "pooled4_correct": row.get("pooled4_correct"),
        "fta_correct": row.get("fta_correct"),
        "fta_selected_source": row.get("fta_selected_source"),
        "effective_fix2_action": row.get("effective_fix2_action"),
        "effective_fix4_action": row.get("effective_fix4_action"),
        "no_effective_gate_action": row.get("no_effective_gate_action"),
        "effective_policy_label": row.get("effective_policy_label"),
        "override_reason": row.get("override_reason"),
        "single_weak_frontier_branch": str(row.get("override_reason")) == SWFB,
        "frontier_support": row.get("frontier_support"),
        "support_margin": support_margin,
        "support_margin_comparable": support_margin is not None,
        "direct_frontier_agree": dfa,
        "direct_frontier_agree_comparable": dfa is not None,
        "external_answers_unanimous": row.get("external_answers_unanimous"),
        "external_unanimous_against_frontier": row.get("external_unanimous_against_frontier"),
        "two_of_three_external_against_frontier": row.get("two_of_three_external_against_frontier"),
        "candidate_pool_answer_group_count": row.get("candidate_pool_answer_group_count"),
        "parser_failure_any": row.get("parser_failure_any"),
        "failure_class_coarse": row.get("failure_class_coarse"),
    }


def decision_ext3_when_swfb(row: dict[str, Any]) -> str | None:
    if str(row.get("override_reason")) != SWFB:
        return None
    return decision_external3_majority(row)


def decision_ext3_when_frontier_support_le_1(row: dict[str, Any]) -> str | None:
    fs = row.get("frontier_support")
    if not isinstance(fs, int) or fs > 1:
        return None
    return decision_external3_majority(row)


def decision_ext3_when_swfb_and_external_unanimity(row: dict[str, Any]) -> str | None:
    if str(row.get("override_reason")) != SWFB:
        return None
    if not row.get("external_answers_unanimous"):
        return None
    return decision_external3_majority(row)


def decision_ext3_when_swfb_and_external_2of3(row: dict[str, Any]) -> str | None:
    if str(row.get("override_reason")) != SWFB:
        return None
    if not row.get("two_of_three_external_against_frontier"):
        return None
    return decision_external3_majority(row)


def decision_conservative_ext3_swfb_disagree(row: dict[str, Any]) -> str | None:
    if str(row.get("override_reason")) != SWFB:
        return None
    ext3 = decision_external3_majority(row)
    fta = row.get("fta_selected_answer_canonical")
    if ext3 in (None, "") or fta in (None, ""):
        return None
    if str(ext3) != str(fta):
        return ext3
    return None


def build_replay_rule_specs() -> list[RuleSpec]:
    repair_specs = {s.name: s for s in build_repair_rule_specs()}
    return [
        RuleSpec(
            name="canonical_fta",
            family="baseline",
            description="Canonical FTA / FIX-2+FIX-4 reference.",
            decision_fn=decision_canonical_fta,
        ),
        RuleSpec(
            name="external3_standalone",
            family="baseline",
            description="External-3 majority every row.",
            decision_fn=decision_external3_majority,
        ),
        RuleSpec(
            name="pooled4_standalone",
            family="baseline",
            description="Pooled-4 majority reconstruction every row.",
            decision_fn=decision_pooled4_majority,
        ),
        RuleSpec(
            name="azure_ext3_when_swfb",
            family="azure_inspired",
            description="External-3 when override_reason=single_weak_frontier_branch.",
            decision_fn=decision_ext3_when_swfb,
        ),
        RuleSpec(
            name="ext3_when_frontier_support_le_1",
            family="azure_inspired",
            description="External-3 when frontier_support <= 1.",
            decision_fn=decision_ext3_when_frontier_support_le_1,
        ),
        RuleSpec(
            name="ext3_when_swfb_and_external_unanimity",
            family="azure_inspired",
            description="External-3 when SWFB and external unanimity.",
            decision_fn=decision_ext3_when_swfb_and_external_unanimity,
        ),
        RuleSpec(
            name="ext3_when_swfb_and_external_2of3_margin",
            family="azure_inspired",
            description="External-3 when SWFB and 2/3 externals against frontier.",
            decision_fn=decision_ext3_when_swfb_and_external_2of3,
        ),
        RuleSpec(
            name="conservative_ext3_when_fta_external_disagree_and_swfb",
            family="azure_inspired",
            description="External-3 when SWFB and FTA answer != External-3 answer.",
            decision_fn=decision_conservative_ext3_swfb_disagree,
        ),
        repair_specs["repair_primary_plus_unanimity_fallback"],
    ]


def evaluate_rules_on_corpus(
    rows: list[dict[str, Any]],
    specs: list[RuleSpec],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    canonical_spec = next(s for s in specs if s.name == "canonical_fta")
    canonical_eval = evaluate_rule_full(rows, canonical_spec)
    evaluations: dict[str, dict[str, Any]] = {"canonical_fta": canonical_eval}

    result_rows: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []

    audits = {a["rule_name"]: a for a in audit_rule_decision_legality(specs)}

    for spec in specs:
        ev = evaluate_rule_full(rows, spec)
        evaluations[spec.name] = ev
        audit = audits.get(spec.name, {})
        overrides_triggered = sum(r["override_triggered"] for r in ev["per_row"])
        overrides_changed = sum(r["override_changed_answer"] for r in ev["per_row"])
        row = {
            "rule_name": spec.name,
            "family": spec.family,
            "accuracy": ev["accuracy"],
            "correct_count": ev["correct_count"],
            "row_count": ev["row_count"],
            "wins_vs_fta": ev["wins_vs_canonical_fta"],
            "losses_vs_fta": ev["losses_vs_canonical_fta"],
            "ties_vs_fta": ev["ties_vs_canonical_fta"],
            "net_wins": ev["net_wins"],
            "override_triggered": overrides_triggered,
            "override_changed_answer": overrides_changed,
            "override_rate": round(overrides_changed / ev["row_count"], 6) if ev["row_count"] else None,
            "regression_count": ev["losses_vs_canonical_fta"],
            "regression_rate_among_fta_correct": ev["regression_rate_among_fta_correct"],
            "is_runtime_legal": audit.get("is_runtime_legal"),
            "illegal_fields_found": audit.get("illegal_fields_found") or "",
            "referenced_fields": audit.get("referenced_fields") or "",
        }
        if spec.name != "canonical_fta":
            ci = paired_bootstrap_ci(
                ev["per_row"],
                canonical_eval["per_row"],
                n_resamples=bootstrap_resamples,
                seed=bootstrap_seed,
                stratify_by_source=True,
            )
            row.update(
                {
                    "ci_delta_vs_fta": ci["observed_delta_accuracy"],
                    "ci_low": ci["ci_low"],
                    "ci_high": ci["ci_high"],
                    "ci_includes_zero": ci["includes_zero"],
                }
            )
            bootstrap_rows.append({"comparison_name": f"{spec.name}_vs_canonical_fta", **ci})
        else:
            row.update(
                {
                    "ci_delta_vs_fta": 0.0,
                    "ci_low": 0.0,
                    "ci_high": 0.0,
                    "ci_includes_zero": True,
                }
            )
        result_rows.append(row)

        for source_id, item in ev.get("per_source", {}).items():
            source_rows.append(
                {
                    "rule_name": spec.name,
                    "source_id": source_id,
                    "seed": item["seed"],
                    "row_count": item["row_count"],
                    "accuracy": item["accuracy"],
                    "wins": item["wins"],
                    "losses": item["losses"],
                    "net_wins": item["net_wins"],
                }
            )

    return result_rows, bootstrap_rows, source_rows, evaluations


def _load_azure_results(path: str | Path) -> dict[str, dict[str, Any]]:
    import csv

    out: dict[str, dict[str, Any]] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            out[row["rule_name"]] = row
    return out


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def cross_provider_compatibility(
    cohere_results: list[dict[str, Any]],
    azure_results: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    azure_name_map = {
        "azure_ext3_when_swfb": "azure_ext3_when_swfb",
        "ext3_when_frontier_support_le_1": "azure_ext3_when_frontier_support_le_1",
        "ext3_when_swfb_and_external_unanimity": None,
        "ext3_when_swfb_and_external_2of3_margin": None,
        "conservative_ext3_when_fta_external_disagree_and_swfb": None,
        "repair_primary_plus_unanimity_fallback": None,
        "external3_standalone": None,
        "pooled4_standalone": None,
    }
    rows = []
    for crow in cohere_results:
        name = crow["rule_name"]
        arow = azure_results.get(azure_name_map.get(name) or name)
        c_net = int(crow["net_wins"])
        c_reg = _float_or_none(crow.get("regression_rate_among_fta_correct")) or 0.0
        c_override = _float_or_none(crow.get("override_rate")) or 0.0
        if arow:
            a_net = int(float(arow["net_wins"]))
            a_reg = _float_or_none(arow.get("regression_rate_among_fta_correct")) or 0.0
            a_override = (
                int(arow["override_changed_answer"]) / int(arow.get("row_count") or 300)
                if arow.get("override_changed_answer")
                else None
            )
        else:
            a_net = None
            a_reg = None
            a_override = None

        if a_net is None:
            classification = "azure_not_evaluated"
        elif c_net > 0 and a_net > 0 and c_reg <= 0.005 and (a_reg or 0) <= 0.005:
            classification = "provider_invariant_promising"
        elif c_net > 0 and a_net > 0:
            classification = "both_positive_check_regressions"
        elif c_net <= 0 and a_net > 0:
            classification = "azure_specific"
        elif c_net < 0:
            classification = "cohere_harmful"
        elif c_net == 0 and a_net > 0:
            classification = "azure_specific"
        else:
            classification = "inconclusive"

        rows.append(
            {
                "rule_name": name,
                "cohere_net_wins": c_net,
                "azure_net_wins": a_net,
                "cohere_override_rate": c_override,
                "azure_override_rate": a_override,
                "cohere_regression_rate": c_reg,
                "azure_regression_rate": a_reg,
                "cohere_accuracy": crow["accuracy"],
                "azure_accuracy": _float_or_none(arow.get("accuracy")) if arow else None,
                "compatibility_classification": classification,
            }
        )
    return rows


def _case_line(row: dict[str, Any], rule_eval_row: dict[str, Any], *, label: str) -> str:
    return (
        f"### {label}: `{row.get('example_id')}` (seed={row.get('seed')})\n"
        f"- Gold: {row.get('gold_answer_canonical')} | Frontier: {row.get('frontier_answer_canonical')} | "
        f"L1: {row.get('l1_answer_canonical')} | S1: {row.get('s1_answer_canonical')} | TALE: {row.get('tale_answer_canonical')}\n"
        f"- FTA: {row.get('fta_selected_answer_canonical')} (correct={row.get('fta_correct')}) | "
        f"Ext3: {row.get('external3_answer')} | Rule selected: {rule_eval_row.get('selected_answer')} "
        f"(correct={rule_eval_row.get('selected_correct')})\n"
        f"- override_reason={row.get('override_reason')} frontier_support={row.get('frontier_support')} "
        f"ext_unanimous={row.get('external_answers_unanimous')} 2of3={row.get('two_of_three_external_against_frontier')}\n"
        f"- {label.split(':')[0]}\n"
    )


def build_representative_cases(
    cohere_rows: list[dict[str, Any]],
    azure_rows: list[dict[str, Any]],
    cohere_evals: dict[str, dict[str, Any]],
    azure_evals: dict[str, dict[str, Any]] | None,
) -> str:
    lines = ["# Representative Cohere / Azure Rule Cases", ""]
    swfb_spec = "azure_ext3_when_swfb"

    def _indexed(per_row: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {r["row_id"]: r for r in per_row}

    cohere_pr = _indexed(cohere_evals[swfb_spec]["per_row"])
    cohere_by_id = {r["row_id"]: r for r in cohere_rows}

    helps_cohere = [
        r for r in cohere_evals[swfb_spec]["per_row"] if r["win"] and str(r.get("override_reason")) == SWFB
    ]
    hurts_cohere = [r for r in cohere_evals[swfb_spec]["per_row"] if r["loss"]]

    lines.append("## Cohere: SWFB + External-3 helps (wins)")
    lines.append("")
    for r in helps_cohere[:5]:
        base = cohere_by_id.get(r["row_id"], r)
        lines.append(_case_line(base, r, label="win"))
        lines.append("")

    lines.append("## Cohere: SWFB + External-3 hurts (losses)")
    lines.append("")
    for r in hurts_cohere[:5]:
        base = cohere_by_id.get(r["row_id"], r)
        lines.append(_case_line(base, r, label="loss"))
        lines.append("")

    if azure_evals and azure_rows:
        azure_by_id = {r["row_id"]: r for r in azure_rows}
        helps_azure = [
            r for r in azure_evals[swfb_spec]["per_row"] if r["win"] and str(r.get("override_reason")) == SWFB
        ]
        lines.append("## Azure: SWFB + External-3 helps (wins)")
        lines.append("")
        for r in helps_azure[:5]:
            base = azure_by_id.get(r["row_id"], r)
            lines.append(_case_line(base, r, label="win"))
            lines.append("")

    fta_beats_ext3 = [r for r in cohere_rows if r.get("fta_correct") and not r.get("external3_correct")][:5]
    lines.append("## Cohere: FTA correct, External-3 wrong (sample)")
    lines.append("")
    for base in fta_beats_ext3:
        pr = cohere_pr.get(base["row_id"], {})
        lines.append(_case_line(base, pr, label="fta_beats_ext3"))
        lines.append("")

    all_fail = [r for r in cohere_rows if r.get("all_methods_wrong")][:3]
    lines.append("## Cohere: all methods wrong (sample)")
    lines.append("")
    for base in all_fail:
        pr = cohere_pr.get(base["row_id"], {})
        lines.append(_case_line(base, pr, label="all_fail"))
        lines.append("")

    return "\n".join(lines)


def classify_swfb_rule(cohere_row: dict[str, Any], compat_row: dict[str, Any]) -> str:
    c_net = int(cohere_row["net_wins"])
    c_loss = int(cohere_row["losses_vs_fta"])
    c_reg = _float_or_none(cohere_row.get("regression_rate_among_fta_correct")) or 0.0
    a_net = compat_row.get("azure_net_wins")
    a_net_i = int(a_net) if a_net is not None else None

    if c_loss > 5 or c_reg > 0.015:
        return "harmful_on_cohere_reject_as_general_repair"
    if a_net_i is not None and a_net_i >= 5 and (c_net <= 3 or c_loss >= 3):
        return "azure_specific_candidate_only"
    if c_net >= 5 and c_reg <= 0.005:
        return "provider_invariant_candidate_worth_independent_validation"
    if c_net > 0 and c_reg <= 0.01:
        return "promising_but_needs_disjoint_validation"
    if c_net <= 0 and a_net_i and a_net_i > 0:
        return "azure_specific_candidate_only"
    return "inconclusive_due_to_small_cohere_gain_or_regressions"


def write_rule_report(result_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> str:
    lines = ["# Cohere Aggregate-720: Azure-Inspired Rule Replay", ""]
    header = (
        "| Rule | Acc | Net | Wins | Losses | Overrides | Reg rate | CI vs FTA | Legal |"
    )
    lines.extend([header, "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"])
    for r in sorted(result_rows, key=lambda x: -x["net_wins"]):
        lines.append(
            f"| `{r['rule_name']}` | {r['accuracy']:.4f} | {r['net_wins']} | {r['wins_vs_fta']} | "
            f"{r['losses_vs_fta']} | {r['override_changed_answer']} | "
            f"{r.get('regression_rate_among_fta_correct', 0):.4f} | "
            f"[{r.get('ci_low')}, {r.get('ci_high')}] | {r.get('is_runtime_legal')} |"
        )
    lines.append("")
    lines.append("## Per-source breakdown (top rules)")
    lines.append("")
    for rule in ("azure_ext3_when_swfb", "external3_standalone", "repair_primary_plus_unanimity_fallback"):
        lines.append(f"### {rule}")
        for s in source_rows:
            if s["rule_name"] == rule:
                lines.append(
                    f"- {s['source_id']} (seed={s['seed']}): acc={s['accuracy']}, net={s['net_wins']}"
                )
        lines.append("")
    return "\n".join(lines)


def write_cross_provider_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Cross-Provider Rule Compatibility", ""]
    lines.append("| Rule | Cohere net | Azure net | Cohere reg | Azure reg | Classification |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for r in rows:
        lines.append(
            f"| `{r['rule_name']}` | {r['cohere_net_wins']} | {r['azure_net_wins']} | "
            f"{r['cohere_regression_rate']} | {r['azure_regression_rate']} | {r['compatibility_classification']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_next_algorithm_direction(
    swfb_cohere: dict[str, Any],
    swfb_class: str,
    compat_rows: list[dict[str, Any]],
) -> str:
    return "\n".join(
        [
            "# Next Algorithm Direction",
            "",
            f"## `azure_ext3_when_swfb` classification: **{swfb_class}**",
            "",
            f"- Cohere Aggregate-720: accuracy={swfb_cohere['accuracy']:.4f}, "
            f"net_wins={swfb_cohere['net_wins']}, losses={swfb_cohere['losses_vs_fta']}, "
            f"regression_rate={swfb_cohere.get('regression_rate_among_fta_correct', 0)}",
            "",
            "## Recommended next offline step",
            "",
            "1. **External-3 fallback family** — highest signal; refine with unanimity/2-of-3 gates on Cohere before any API run.",
            "2. **Provider-conditioned selector** — if SWFB rate continues to diverge, gate rules on `override_reason` distribution.",
            "3. **Recalibrated FIX-2** — only after SWFB fallback is validated; touching canonical FTA is high risk.",
            "4. Tree-propagation / normalization — lower priority unless case review shows parse/tree misses.",
            "5. Learned lightweight selector — defer until a single hand-crafted SWFB rule validates on disjoint Cohere split.",
            "",
            "## Do not implement",
            "",
            "- No promotion to `support_aware_selector.py`",
            "- No manuscript claim updates from this replay alone",
            "",
        ]
    )


def write_final_summary(
    swfb_cohere: dict[str, Any],
    ext3_cohere: dict[str, Any],
    swfb_class: str,
    compat_rows: list[dict[str, Any]],
) -> str:
    swfb_compat = next(r for r in compat_rows if r["rule_name"] == "azure_ext3_when_swfb")
    return "\n".join(
        [
            "# Final Cohere Replay: Azure-Inspired Rules",
            "",
            "## Does `azure_ext3_when_swfb` help on Cohere?",
            "",
            f"**{'Yes' if swfb_cohere['net_wins'] > 0 else 'No / marginal'}** — "
            f"net_wins={swfb_cohere['net_wins']}, accuracy={swfb_cohere['accuracy']:.4f} "
            f"vs FTA baseline on Aggregate-720.",
            "",
            "## Does it regress Cohere FTA-correct cases?",
            "",
            f"**{swfb_cohere['losses_vs_fta']} losses**, regression_rate="
            f"{swfb_cohere.get('regression_rate_among_fta_correct', 0):.4f}.",
            "",
            "## Provider-invariant or Azure-specific?",
            "",
            f"**{swfb_class}** (Azure net={swfb_compat.get('azure_net_wins')}, Cohere net={swfb_compat.get('cohere_net_wins')}).",
            "",
            "## Promote, exploratory, reject, or validate?",
            "",
            "Keep **exploratory**; independent disjoint-split validation required before any promotion discussion.",
            "",
            "## Does Azure change the paper story?",
            "",
            "No change to canonical Cohere FTA claims. Azure remains supporting cross-provider diagnostic context.",
            "",
            "## Before any new API run",
            "",
            "1. Disjoint Cohere seed validation of top SWFB rule if Cohere replay is positive.",
            "2. Replay conservative variants (unanimity/2-of-3 gates) on Aggregate-720.",
            "3. Do not spend on Azure until Cohere compatibility is established.",
            "",
            f"## External-3 standalone on Cohere: accuracy={ext3_cohere['accuracy']:.4f}, net_wins={ext3_cohere['net_wins']}",
            "",
        ]
    )


def run_replay(
    output_dir: Path,
    *,
    azure_input: str,
    azure_results_csv: str,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = build_replay_rule_specs()

    cohere_rows, _ = build_cohere_aggregate()
    replay_table = [build_replay_feature_row(r) for r in cohere_rows]
    write_csv(output_dir / "COHERE_REPLAY_FEATURE_TABLE.csv", replay_table, list(replay_table[0].keys()))
    write_jsonl(output_dir / "COHERE_REPLAY_FEATURE_TABLE.jsonl", replay_table)
    write_json(
        output_dir / "COHERE_REPLAY_FEATURE_SUMMARY.json",
        {
            "rows": len(replay_table),
            "seeds": sorted({r["seed"] for r in replay_table}),
            "fta_correct": sum(1 for r in replay_table if r.get("fta_correct")),
            "swfb_count": sum(1 for r in replay_table if r.get("single_weak_frontier_branch")),
            "support_margin_missing": sum(1 for r in replay_table if not r.get("support_margin_comparable")),
            "direct_frontier_agree_missing": sum(
                1 for r in replay_table if not r.get("direct_frontier_agree_comparable")
            ),
        },
    )

    result_rows, bootstrap_rows, source_rows, evaluations = evaluate_rules_on_corpus(
        cohere_rows,
        specs,
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_seed=bootstrap_seed,
    )
    write_csv(output_dir / "COHERE_AZURE_INSPIRED_RULE_RESULTS.csv", result_rows, list(result_rows[0].keys()))
    write_csv(
        output_dir / "COHERE_AZURE_INSPIRED_BOOTSTRAP_CI.csv",
        bootstrap_rows,
        list(bootstrap_rows[0].keys()) if bootstrap_rows else ["comparison_name"],
    )
    write_text(output_dir / "COHERE_AZURE_INSPIRED_RULE_REPORT.md", write_rule_report(result_rows, source_rows))

    azure_results = _load_azure_results(azure_results_csv) if Path(azure_results_csv).exists() else {}
    compat_rows = cross_provider_compatibility(result_rows, azure_results)
    write_csv(
        output_dir / "CROSS_PROVIDER_RULE_COMPATIBILITY.csv",
        compat_rows,
        list(compat_rows[0].keys()),
    )
    write_text(output_dir / "CROSS_PROVIDER_RULE_COMPATIBILITY.md", write_cross_provider_md(compat_rows))

    azure_rows: list[dict[str, Any]] = []
    azure_evals: dict[str, dict[str, Any]] | None = None
    if Path(azure_input).exists():
        azure_rows, _ = build_corpus(
            corpus_id="azure_seed97",
            input_path=azure_input,
            source_id="azure_openai_seed97",
        )
        _, _, _, azure_evals = evaluate_rules_on_corpus(
            azure_rows,
            [s for s in specs if s.name in {r["rule_name"] for r in result_rows}],
            bootstrap_resamples=bootstrap_resamples,
            bootstrap_seed=bootstrap_seed,
        )

    write_text(
        output_dir / "REPRESENTATIVE_COHERE_AZURE_RULE_CASES.md",
        build_representative_cases(cohere_rows, azure_rows, evaluations, azure_evals),
    )

    swfb_cohere = next(r for r in result_rows if r["rule_name"] == "azure_ext3_when_swfb")
    ext3_cohere = next(r for r in result_rows if r["rule_name"] == "external3_standalone")
    swfb_compat = next(r for r in compat_rows if r["rule_name"] == "azure_ext3_when_swfb")
    swfb_class = classify_swfb_rule(swfb_cohere, swfb_compat)

    write_text(
        output_dir / "NEXT_ALGORITHM_DIRECTION.md",
        write_next_algorithm_direction(swfb_cohere, swfb_class, compat_rows),
    )
    write_text(
        output_dir / "FINAL_COHERE_REPLAY_AZURE_RULES_SUMMARY.md",
        write_final_summary(swfb_cohere, ext3_cohere, swfb_class, compat_rows),
    )

    return {
        "output_dir": str(output_dir),
        "cohere_rows": len(cohere_rows),
        "azure_ext3_when_swfb": {
            "accuracy": swfb_cohere["accuracy"],
            "net_wins": swfb_cohere["net_wins"],
            "losses": swfb_cohere["losses_vs_fta"],
            "classification": swfb_class,
        },
        "external3_standalone": {
            "accuracy": ext3_cohere["accuracy"],
            "net_wins": ext3_cohere["net_wins"],
        },
    }


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else _timestamp_dir()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to write into non-empty directory: {output_dir}")
    summary = run_replay(
        output_dir,
        azure_input=args.azure_input,
        azure_results_csv=args.azure_results_csv,
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
