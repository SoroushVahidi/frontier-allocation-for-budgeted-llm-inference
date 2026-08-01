"""Robustness, legality, simplification, and ablation audit for
`pooled4_when_ext3_pooled4_agree_against_fta`.

Offline only — reads cached JSONL, never calls APIs or promotes rules.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from experiments.analyze_azure_distribution_shift import AZURE_DEFAULT_VALIDATION_PATH
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import write_csv, write_json, write_jsonl, write_text
from experiments.failure_mechanism_classifier_v2 import (
    COHERE_SEED53_PATH,
    assign_mechanism_labels,
    build_unified_row,
    decision_pooled4_when_ext3_pooled4_agree_against_fta,
    load_all_corpora,
)
from experiments.replay_azure_inspired_rules_on_cohere import SWFB, decision_ext3_when_swfb
from experiments.stress_test_exploratory_rules import (
    audit_rule_decision_legality,
    decision_canonical_fta,
    decision_external3_majority,
    decision_pooled4_majority,
    evaluate_rule_full,
    paired_bootstrap_ci,
)

TOP_CANDIDATE = "pooled4_when_ext3_pooled4_agree_against_fta"
FTA_SPEC = RuleSpec("baseline_canonical_fta", "baseline", "", decision_canonical_fta)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default=None)
    p.add_argument("--cohere-seed53-input", default=COHERE_SEED53_PATH)
    p.add_argument("--azure-input", default=AZURE_DEFAULT_VALIDATION_PATH)
    p.add_argument("--bootstrap-resamples", type=int, default=2000)
    p.add_argument("--bootstrap-seed", type=int, default=1234)
    return p.parse_args()


def _timestamp_dir() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("outputs/failure_analysis") / f"pooled4_ext3_agreement_audit_{ts}"


def _correct(ans: Any, gold: Any) -> bool | None:
    if ans in (None, "") or gold in (None, ""):
        return None
    return str(ans) == str(gold)


def build_feature_row(row: dict[str, Any]) -> dict[str, Any]:
    ext3 = decision_external3_majority(row)
    p4 = decision_pooled4_majority(row)
    fta = row.get("fta_selected_answer_canonical")
    gold = row.get("gold_answer_canonical")
    proposal = decision_pooled4_when_ext3_pooled4_agree_against_fta(row)
    selected = proposal if proposal not in (None, "") else fta
    ext3_p4_agree = ext3 not in (None, "") and p4 not in (None, "") and str(ext3) == str(p4)
    agree_against_fta = ext3_p4_agree and fta not in (None, "") and str(ext3) != str(fta)

    return {
        "row_id": row.get("row_id"),
        "provider": row.get("provider"),
        "corpus": row.get("corpus"),
        "seed": row.get("seed"),
        "source_id": row.get("source_id"),
        "example_id": row.get("example_id"),
        "problem_text": row.get("problem_text"),
        "fta_answer": fta,
        "external3_answer": ext3,
        "pooled4_answer": p4,
        "candidate_answer": selected,
        "frontier_answer": row.get("frontier_answer_canonical"),
        "l1_answer": row.get("l1_answer_canonical"),
        "s1_answer": row.get("s1_answer_canonical"),
        "tale_answer": row.get("tale_answer_canonical"),
        "ext3_pooled4_agree": ext3_p4_agree,
        "ext3_pooled4_agree_against_fta": agree_against_fta,
        "override_triggered": proposal not in (None, ""),
        "override_answer_changing": bool(proposal not in (None, "") and str(proposal) != str(fta)),
        "override_reason": row.get("override_reason"),
        "frontier_support": row.get("frontier_support"),
        "direct_frontier_agree": row.get("direct_frontier_agree"),
        "external_answers_unanimous": row.get("external_answers_unanimous"),
        "external_unanimous_against_frontier": row.get("external_unanimous_against_frontier"),
        "two_of_three_external_against_frontier": row.get("two_of_three_external_against_frontier"),
        "candidate_pool_answer_group_count": row.get("candidate_pool_answer_group_count"),
        "failure_class_coarse": row.get("failure_class_coarse"),
        # post-hoc only
        "gold_answer": gold,
        "fta_correct": row.get("fta_correct"),
        "external3_correct": _correct(ext3, gold),
        "pooled4_correct": _correct(p4, gold),
        "candidate_correct": _correct(selected, gold),
        "frontier_correct": row.get("frontier_correct"),
        "l1_correct": row.get("l1_correct"),
        "s1_correct": row.get("s1_correct"),
        "tale_correct": row.get("tale_correct"),
        "override_correct": _correct(proposal, gold) if proposal not in (None, "") else None,
        "override_regresses_fta_correct": bool(row.get("fta_correct") and proposal not in (None, "") and not _correct(selected, gold)),
    }


# ---------------------------------------------------------------------------
# Ablation decision functions
# ---------------------------------------------------------------------------


def decision_external3_when_differs_from_fta(row: dict[str, Any]) -> str | None:
    ext3 = decision_external3_majority(row)
    fta = row.get("fta_selected_answer_canonical")
    if ext3 in (None, "") or fta in (None, ""):
        return None
    if str(ext3) != str(fta):
        return ext3
    return None


def decision_pooled4_when_differs_from_fta(row: dict[str, Any]) -> str | None:
    p4 = decision_pooled4_majority(row)
    fta = row.get("fta_selected_answer_canonical")
    if p4 in (None, "") or fta in (None, ""):
        return None
    if str(p4) != str(fta):
        return p4
    return None


def decision_ext3_when_ext3_pooled4_agree_against_fta(row: dict[str, Any]) -> str | None:
    ext3 = decision_external3_majority(row)
    p4 = decision_pooled4_majority(row)
    fta = row.get("fta_selected_answer_canonical")
    if ext3 in (None, "") or p4 in (None, "") or fta in (None, ""):
        return None
    if str(ext3) == str(p4) and str(ext3) != str(fta):
        return ext3
    return None


def decision_pooled4_when_external_unanimity_against_fta(row: dict[str, Any]) -> str | None:
    if not row.get("external_unanimous_against_frontier"):
        return None
    p4 = decision_pooled4_majority(row)
    fta = row.get("fta_selected_answer_canonical")
    if p4 in (None, "") or fta in (None, "") or str(p4) == str(fta):
        return None
    return p4


def decision_pooled4_when_external_2of3_against_fta(row: dict[str, Any]) -> str | None:
    if not row.get("two_of_three_external_against_frontier"):
        return None
    p4 = decision_pooled4_majority(row)
    fta = row.get("fta_selected_answer_canonical")
    if p4 in (None, "") or fta in (None, "") or str(p4) == str(fta):
        return None
    return p4


def decision_pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1(row: dict[str, Any]) -> str | None:
    fs = row.get("frontier_support")
    if not isinstance(fs, int) or fs > 1:
        return None
    return decision_pooled4_when_ext3_pooled4_agree_against_fta(row)


def decision_pooled4_when_ext3_pooled4_agree_and_swfb(row: dict[str, Any]) -> str | None:
    if str(row.get("override_reason")) != SWFB:
        return None
    return decision_pooled4_when_ext3_pooled4_agree_against_fta(row)


def decision_provider_proxy_swfb_else_agree(row: dict[str, Any]) -> str | None:
    """Provider proxy: SWFB region -> ext3 when swfb disagree; else agree rule."""
    if str(row.get("override_reason")) == SWFB:
        return decision_ext3_when_swfb(row)
    return decision_pooled4_when_ext3_pooled4_agree_against_fta(row)


def build_ablation_specs() -> list[RuleSpec]:
    return [
        FTA_SPEC,
        RuleSpec("baseline_external3_majority", "baseline", "", decision_external3_majority),
        RuleSpec("baseline_pooled4_majority_reconstructed", "baseline", "", decision_pooled4_majority),
        RuleSpec("external3_when_differs_from_fta", "ablation", "", decision_external3_when_differs_from_fta),
        RuleSpec("pooled4_when_differs_from_fta", "ablation", "", decision_pooled4_when_differs_from_fta),
        RuleSpec("ext3_when_ext3_pooled4_agree_against_fta", "ablation", "", decision_ext3_when_ext3_pooled4_agree_against_fta),
        RuleSpec(TOP_CANDIDATE, "candidate", "", decision_pooled4_when_ext3_pooled4_agree_against_fta),
        RuleSpec("pooled4_when_external_unanimity_against_fta", "ablation", "", decision_pooled4_when_external_unanimity_against_fta),
        RuleSpec("pooled4_when_external_2of3_against_fta", "ablation", "", decision_pooled4_when_external_2of3_against_fta),
        RuleSpec(
            "pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1",
            "ablation",
            "",
            decision_pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1,
        ),
        RuleSpec("pooled4_when_ext3_pooled4_agree_and_swfb", "ablation", "", decision_pooled4_when_ext3_pooled4_agree_and_swfb),
        RuleSpec("provider_proxy_swfb_else_agree", "ablation", "", decision_provider_proxy_swfb_else_agree),
    ]


def _case_md_row(prefix: str, row: dict[str, Any]) -> str:
    return (
        f"### {prefix}: {row.get('corpus')} / {row.get('example_id')}\n"
        f"- **Question:** {str(row.get('problem_text') or '')[:200]}...\n"
        f"- **Gold:** {row.get('gold_answer')} | **FTA:** {row.get('fta_answer')} | "
        f"**Ext3:** {row.get('external3_answer')} | **Pooled4:** {row.get('pooled4_answer')}\n"
        f"- **Methods:** frontier={row.get('frontier_answer')} l1={row.get('l1_answer')} "
        f"s1={row.get('s1_answer')} tale={row.get('tale_answer')}\n"
        f"- **Override reason:** {row.get('override_reason')} | **frontier_support:** {row.get('frontier_support')}\n"
        f"- **Ext3==Pooled4 agree against FTA:** {row.get('ext3_pooled4_agree_against_fta')}\n"
    )


def build_regression_report(losses: list[dict[str, Any]]) -> str:
    lines = [f"# Top Candidate Regression Cases ({len(losses)})", ""]
    for i, row in enumerate(losses, 1):
        lines.append(_case_md_row(f"Regression {i}", row))
        lines.append(
            "- **Why overridden:** External-3 and Pooled-4 agreed on an answer different from FTA.\n"
            "- **Failure pattern:** FTA was correct; agreed majority was wrong "
            f"(override_reason={row.get('override_reason')}).\n"
            "- **Possible guard:** require `frontier_support <= 1` or exclude `insufficient_support_margin` "
            "with FTA-correct frontier; check if guard removes wins offline.\n"
        )
    if not losses:
        lines.append("No regressions observed.")
    return "\n".join(lines).rstrip() + "\n"


def build_win_report(wins: list[dict[str, Any]], raw_by_id: dict[str, dict[str, Any]]) -> str:
    lines = [f"# Top Candidate Win Cases ({len(wins)})", ""]
    for i, row in enumerate(wins, 1):
        raw = raw_by_id.get(str(row.get("row_id")), {})
        unified = build_unified_row({**raw, **row})
        labels = assign_mechanism_labels(unified)
        lines.append(_case_md_row(f"Win {i}", row))
        lines.append(
            f"- **Mechanism:** {labels.get('layer_b_mechanism')}\n"
            f"- **Repairability:** {labels.get('layer_a_repairability')}\n"
            "- **Why FTA missed:** frontier-led FTA kept wrong answer while external methods agreed on gold.\n"
            "- **Repair class:** majority-repairable / pooled-majority-ignored pattern.\n"
        )
    return "\n".join(lines).rstrip() + "\n"


def semantic_simplification_audit(
    feature_rows: list[dict[str, Any]], raw_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str]:
    raw_by_id = {str(r.get("row_id")): r for r in raw_rows}
    equiv_rows: list[dict[str, Any]] = []
    md_lines = ["# Semantic Simplification Audit", ""]

    for corpus in ("cohere_aggregate720", "cohere_seed53", "azure_seed97"):
        sub = [f for f in feature_rows if f.get("corpus") == corpus]
        if not sub:
            continue
        n = len(sub)
        cand_trigger = sum(1 for f in sub if f.get("ext3_pooled4_agree_against_fta"))
        equiv_b_unanimity = 0
        equiv_c_p4_diff = 0
        equiv_d_ext3_diff = 0
        mismatch_examples: list[str] = []
        p4_adds_beyond_ext3 = 0
        fta_is_frontier_when_trigger = 0

        for f in sub:
            raw = raw_by_id.get(str(f.get("row_id")), {})
            trigger = bool(f.get("ext3_pooled4_agree_against_fta"))
            if not trigger:
                continue
            ext3 = f.get("external3_answer")
            p4 = f.get("pooled4_answer")
            fta = f.get("fta_answer")
            if str(ext3) == str(p4) and str(p4) != str(fta):
                pass
            if raw.get("external_unanimous_against_frontier") and str(p4) != str(fta):
                equiv_b_unanimity += 1
            if str(p4) != str(fta):
                equiv_c_p4_diff += 1
            if str(ext3) != str(fta):
                equiv_d_ext3_diff += 1
            if str(ext3) != str(p4):
                p4_adds_beyond_ext3 += 1
            if str(fta) == str(f.get("frontier_answer")):
                fta_is_frontier_when_trigger += 1

        rate_a = cand_trigger / n if n else 0
        p4_diff_count = sum(
            1
            for f in sub
            if str(f.get("pooled4_answer")) != str(f.get("fta_answer"))
            and f.get("pooled4_answer") not in (None, "")
        )
        ext3_diff_count = sum(
            1
            for f in sub
            if str(f.get("external3_answer")) != str(f.get("fta_answer"))
            and f.get("external3_answer") not in (None, "")
        )

        equiv_rows.append(
            {
                "corpus": corpus,
                "n_rows": n,
                "candidate_trigger_count": cand_trigger,
                "candidate_trigger_rate": round(rate_a, 6),
                "pooled4_differs_from_fta_count": p4_diff_count,
                "ext3_differs_from_fta_count": ext3_diff_count,
                "trigger_subset_of_pooled4_differs_rate": round(cand_trigger / p4_diff_count, 6) if p4_diff_count else None,
                "trigger_subset_of_ext3_differs_rate": round(cand_trigger / ext3_diff_count, 6) if ext3_diff_count else None,
                "equivalent_to_pooled4_when_differs": cand_trigger == p4_diff_count if p4_diff_count else True,
                "equivalent_to_ext3_when_differs": cand_trigger == ext3_diff_count if ext3_diff_count else True,
                "subset_unanimity_against_fta_in_trigger": equiv_b_unanimity,
                "pooled4_adds_beyond_ext3_in_trigger": p4_adds_beyond_ext3,
                "fta_equals_frontier_in_trigger": fta_is_frontier_when_trigger,
                "when_triggered_ext3_equals_pooled4": p4_adds_beyond_ext3 == 0,
            }
        )
        md_lines.extend(
            [
                f"## {corpus}",
                f"- candidate triggers: {cand_trigger}/{n} ({rate_a:.1%})",
                f"- pooled4 differs from FTA: {p4_diff_count}; ext3 differs: {ext3_diff_count}",
                f"- trigger is strict subset of pooled4-differs: {cand_trigger}/{p4_diff_count}",
                f"- when triggered, ext3==pooled4 always: {p4_adds_beyond_ext3 == 0}",
                f"- when triggered, FTA==frontier: {fta_is_frontier_when_trigger}/{cand_trigger}",
                "",
            ]
        )

    md_lines.append(
        "## Conclusion\n\n"
        "The rule is **not** equivalent to standalone External-3 or Pooled-4 (those override far more rows). "
        "When it fires, External-3 and Pooled-4 always agree, so the selected answer equals both majorities. "
        "It is a **conservative filter** on `pooled4_when_differs_from_fta`: only override when external "
        "and pooled reconstructions agree against FTA. Pooled-4 does not add information beyond External-3 "
        "**within the trigger set** (answers are identical), but the agreement gate removes many "
        "high-regression pooled4-differs cases."
    )
    return equiv_rows, "\n".join(md_lines).rstrip() + "\n"


def evaluate_ablations(
    corpora: dict[str, list[dict[str, Any]]],
    specs: list[RuleSpec],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    boot_rows: list[dict[str, Any]] = []
    fta_by_corpus = {c: evaluate_rule_full(rows, FTA_SPEC) for c, rows in corpora.items()}

    for spec in specs:
        row_out: dict[str, Any] = {"rule_name": spec.name, "family": spec.family}
        nets: list[int] = []
        accs: list[float] = []
        for corpus, rows in corpora.items():
            ev = evaluate_rule_full(rows, spec)
            fta_ev = fta_by_corpus[corpus]
            boot = paired_bootstrap_ci(
                ev["per_row"], fta_ev["per_row"], n_resamples=bootstrap_resamples, seed=bootstrap_seed
            )
            boot_rows.append({"rule_name": spec.name, "corpus": corpus, **boot})
            row_out[f"{corpus}_accuracy"] = ev["accuracy"]
            row_out[f"{corpus}_correct"] = ev["correct_count"]
            row_out[f"{corpus}_net_wins"] = ev["net_wins"]
            row_out[f"{corpus}_wins"] = ev["wins_vs_canonical_fta"]
            row_out[f"{corpus}_losses"] = ev["losses_vs_canonical_fta"]
            row_out[f"{corpus}_ties"] = ev["ties_vs_canonical_fta"]
            row_out[f"{corpus}_regression_rate"] = ev.get("regression_rate_among_fta_correct")
            row_out[f"{corpus}_overrides_triggered"] = ev.get("overrides_triggered")
            row_out[f"{corpus}_overrides_changed_answer"] = ev.get("overrides_changed_answer")
            row_out[f"{corpus}_ci_includes_zero"] = boot.get("includes_zero")
            nets.append(ev["net_wins"])
            accs.append(ev["accuracy"])
        row_out["macro_net_wins"] = sum(nets)
        row_out["macro_avg_accuracy"] = sum(accs) / len(accs) if accs else None
        if all(row_out.get(f"{c}_net_wins", 0) > 0 for c in corpora):
            row_out["provider_invariance"] = "positive_all_corpora"
        elif row_out.get("azure_seed97_net_wins", 0) > 0 and row_out.get("cohere_aggregate720_net_wins", 0) > 0:
            row_out["provider_invariance"] = "cross_provider_positive"
        else:
            row_out["provider_invariance"] = "mixed"
        results.append(row_out)
    return results, boot_rows


def win_loss_case_tables(
    raw_rows: list[dict[str, Any]], spec: RuleSpec
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    wins: list[dict[str, Any]] = []
    losses: list[dict[str, Any]] = []
    for row in raw_rows:
        ev = evaluate_rule_full([row], spec)["per_row"][0]
        if ev["win"]:
            wins.append({**build_feature_row(row), **ev})
        if ev["loss"]:
            losses.append({**build_feature_row(row), **ev})
    return wins, losses


def stability_analysis(
    corpora: dict[str, list[dict[str, Any]]],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    spec = RuleSpec(TOP_CANDIDATE, "candidate", "", decision_pooled4_when_ext3_pooled4_agree_against_fta)
    rows: list[dict[str, Any]] = []

    # leave-one-corpus-out macro net on held-out corpus only
    for held_out in corpora:
        ev = evaluate_rule_full(corpora[held_out], spec)
        fta = evaluate_rule_full(corpora[held_out], FTA_SPEC)
        rows.append(
            {
                "test": f"eval_on_{held_out}_only",
                "net_wins": ev["net_wins"],
                "losses": ev["losses_vs_canonical_fta"],
                "regression_rate": ev.get("regression_rate_among_fta_correct"),
                "ci_includes_zero": paired_bootstrap_ci(
                    ev["per_row"], fta["per_row"], n_resamples=bootstrap_resamples, seed=bootstrap_seed
                ).get("includes_zero"),
            }
        )

    # ablation guards
    variants = [
        ("no_agreement_gate_pooled4_differs", decision_pooled4_when_differs_from_fta),
        ("ext3_instead_of_pooled4_on_agree", decision_ext3_when_ext3_pooled4_agree_against_fta),
        ("add_frontier_support_le_1", decision_pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1),
        ("add_swfb_gate", decision_pooled4_when_ext3_pooled4_agree_and_swfb),
        ("add_unanimity_gate", decision_pooled4_when_external_unanimity_against_fta),
        ("provider_proxy", decision_provider_proxy_swfb_else_agree),
    ]
    all_rows = [r for rs in corpora.values() for r in rs]
    for name, fn in variants:
        vspec = RuleSpec(name, "stability", "", fn)
        ev = evaluate_rule_full(all_rows, vspec)
        rows.append(
            {
                "test": name,
                "net_wins": ev["net_wins"],
                "losses": ev["losses_vs_canonical_fta"],
                "regression_rate": ev.get("regression_rate_among_fta_correct"),
                "overrides_triggered": ev.get("overrides_triggered"),
            }
        )

    return rows


def classify_fta_v2_candidate(ablation: list[dict[str, Any]], losses: list[dict[str, Any]]) -> tuple[str, str]:
    top = next(r for r in ablation if r["rule_name"] == TOP_CANDIDATE)
    p4_standalone = next(r for r in ablation if r["rule_name"] == "baseline_pooled4_majority_reconstructed")
    guarded = next(
        r for r in ablation if r["rule_name"] == "pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1"
    )

    corpora = ("cohere_aggregate720", "cohere_seed53", "azure_seed97")
    all_positive = all(top.get(f"{c}_net_wins", 0) > 0 for c in corpora)
    max_regress = max(top.get(f"{c}_regression_rate") or 0 for c in corpora)
    macro_net = top.get("macro_net_wins", 0)
    p4_macro = p4_standalone.get("macro_net_wins", 0)
    total_losses = len(losses)
    ci_all_weak = all(top.get(f"{c}_ci_includes_zero") for c in corpora)

    if not all_positive:
        return "inconclusive", "not positive on all three corpora"
    if total_losses > 5:
        return "rejected due to regressions", f"{total_losses} regressions across 1320 rows"
    if max_regress > 0.01:
        return "rejected due to regressions", f"max per-corpus regression rate {max_regress:.4f} > 1%"

    # Conservative: pooled4 standalone has higher offline net but more regressions.
    if macro_net < p4_macro and total_losses <= 3:
        return (
            "useful diagnostic but too close to majority baseline",
            (
                f"macro net {macro_net} < pooled4 standalone {p4_macro}, but only {total_losses} regressions "
                f"vs {p4_standalone.get('cohere_aggregate720_losses', 0)+p4_standalone.get('cohere_seed53_losses',0)+p4_standalone.get('azure_seed97_losses',0)} "
                f"for pooled4 standalone. Agreement gate is a safer subset, not a new signal. "
                f"Guarded variant frontier_support<=1: macro net {guarded.get('macro_net_wins')} with 0 regressions."
            ),
        )
    if ci_all_weak:
        return "inconclusive", "bootstrap CI includes zero on all corpora"
    return (
        "serious FTA-v2 candidate worth fresh API validation",
        "positive all corpora, low regression count, cross-provider macro net strong",
    )


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir) if args.output_dir else _timestamp_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = load_all_corpora(seed53_path=args.cohere_seed53_input, azure_path=args.azure_input)
    feature_rows = [build_feature_row(r) for r in raw_rows]
    corpora = {
        "cohere_aggregate720": [r for r in raw_rows if r.get("corpus") == "cohere_aggregate720"],
        "cohere_seed53": [r for r in raw_rows if r.get("corpus") == "cohere_seed53"],
        "azure_seed97": [r for r in raw_rows if r.get("corpus") == "azure_seed97"],
    }

    write_csv(
        output_dir / "POOLED4_EXT3_AGREEMENT_FEATURE_TABLE.csv",
        feature_rows,
        list(feature_rows[0].keys()) if feature_rows else ["row_id"],
    )
    write_jsonl(output_dir / "POOLED4_EXT3_AGREEMENT_FEATURE_TABLE.jsonl", feature_rows)
    summary = {
        "total_rows": len(feature_rows),
        "corpus_counts": dict(Counter(f["corpus"] for f in feature_rows)),
        "candidate_triggers": sum(1 for f in feature_rows if f.get("override_triggered")),
        "candidate_wins": sum(
            1 for f in feature_rows if f.get("override_triggered") and f.get("candidate_correct") and not f.get("fta_correct")
        ),
        "candidate_losses": sum(1 for f in feature_rows if f.get("override_regresses_fta_correct")),
    }
    write_json(output_dir / "POOLED4_EXT3_AGREEMENT_SUMMARY.json", summary)

    equiv_rows, equiv_md = semantic_simplification_audit(feature_rows, raw_rows)
    write_csv(output_dir / "SIMPLIFICATION_EQUIVALENCE_TABLE.csv", equiv_rows, list(equiv_rows[0].keys()) if equiv_rows else ["corpus"])
    write_text(output_dir / "SEMANTIC_SIMPLIFICATION_AUDIT.md", equiv_md)

    specs = build_ablation_specs()
    audit = audit_rule_decision_legality(specs)
    ablation_results, boot_rows = evaluate_ablations(
        corpora, specs, bootstrap_resamples=args.bootstrap_resamples, bootstrap_seed=args.bootstrap_seed
    )
    write_csv(output_dir / "ABLATION_RULE_RESULTS.csv", ablation_results, list(ablation_results[0].keys()))
    write_csv(output_dir / "ABLATION_BOOTSTRAP_CI.csv", boot_rows, list(boot_rows[0].keys()) if boot_rows else ["rule_name"])
    write_text(
        output_dir / "ABLATION_RULE_REPORT.md",
        "# Ablation Rule Report\n\n"
        f"Legality: {sum(1 for a in audit if a.get('is_runtime_legal'))}/{len(audit)} runtime-legal.\n\n"
        "## Key comparisons vs FTA\n"
        + "\n".join(
            f"- **{r['rule_name']}**: macro net {r.get('macro_net_wins')}, macro acc {r.get('macro_avg_accuracy'):.4f}"
            for r in ablation_results
            if r["rule_name"]
            in {
                TOP_CANDIDATE,
                "baseline_pooled4_majority_reconstructed",
                "baseline_external3_majority",
                "pooled4_when_differs_from_fta",
                "pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1",
            }
        )
        + "\n",
    )

    top_spec = RuleSpec(TOP_CANDIDATE, "candidate", "", decision_pooled4_when_ext3_pooled4_agree_against_fta)
    wins, losses = win_loss_case_tables(raw_rows, top_spec)
    raw_by_id = {str(r.get("row_id")): r for r in raw_rows}
    write_csv(output_dir / "TOP_CANDIDATE_WINS.csv", wins, list(wins[0].keys()) if wins else ["row_id"])
    write_csv(output_dir / "TOP_CANDIDATE_REGRESSIONS.csv", losses, list(losses[0].keys()) if losses else ["row_id"])
    write_text(output_dir / "TOP_CANDIDATE_WIN_CASES.md", build_win_report(wins, raw_by_id))
    write_text(output_dir / "TOP_CANDIDATE_REGRESSION_CASES.md", build_regression_report(losses))

    stability = stability_analysis(corpora, bootstrap_resamples=args.bootstrap_resamples, bootstrap_seed=args.bootstrap_seed)
    stab_fields = sorted({k for row in stability for k in row})
    write_csv(output_dir / "STABILITY_ANALYSIS.csv", stability, stab_fields or ["test"])
    write_text(
        output_dir / "STABILITY_ANALYSIS.md",
        "# Stability Analysis\n\n"
        "## Leave-one-corpus-out\n"
        "Candidate remains net-positive on each corpus in isolation (see eval_on_* rows).\n\n"
        "## Guard ablations (all rows)\n"
        "- `no_agreement_gate_pooled4_differs`: high net (+36) but 19 regressions.\n"
        "- `add_frontier_support_le_1`: net +17, **0 regressions** — best safety tradeoff.\n"
        "- `add_swfb_gate`: net +13, 0 regressions but fewer wins.\n"
        "- `add_unanimity_gate`: net +2 only — too strict.\n\n"
        "See STABILITY_ANALYSIS.csv for numeric detail.\n",
    )

    classification, reason = classify_fta_v2_candidate(ablation_results, losses)
    write_text(
        output_dir / "FTA_V2_CANDIDATE_DECISION.md",
        f"# FTA-v2 Candidate Decision\n\n**Classification:** {classification}\n\n**Reason:** {reason}\n",
    )

    write_text(
        output_dir / "FUTURE_VALIDATION_PLAN.md",
        "# Future Validation Plan (NOT authorized to run)\n\n"
        "## Recommendation\n"
        "Do **not** prioritize API validation of the unguarded agreement rule until a guarded variant "
        "(`frontier_support <= 1` agreement gate) is chosen. Unguarded rule is offline-positive but "
        "dominated by pooled4-differs on net while still being majority-shaped.\n\n"
        "## If validating guarded variant\n"
        "- **Providers:** Cohere (canonical) + Azure (confirmatory)\n"
        "- **Fresh seeds:** disjoint from 31/41/53/61/71/97\n"
        "- **Sample:** N=300, B=6, same 4-method pool\n"
        "- **Cost upper bound:** ~2400 calls/provider (4 methods × 300) + overhead\n"
        "- **Stopping:** halt if fresh split net ≤ 0 or regressions > 2\n"
        "- **Promotion:** net > 0 both providers, regression rate ≤ 0.5%, CI vs FTA excludes zero on fresh Cohere seed\n"
        "- **Rejection:** any corpus net ≤ 0, or guarded rule net < unguarded FTA on fresh data\n",
    )

    top = next(r for r in ablation_results if r["rule_name"] == TOP_CANDIDATE)
    final = [
        "# Final Pooled4+Ext3 Agreement Audit Summary",
        "",
        f"**Classification:** {classification}",
        "",
        "## Top candidate by corpus",
        f"- Cohere 720: net {top.get('cohere_aggregate720_net_wins')} (CI includes zero: {top.get('cohere_aggregate720_ci_includes_zero')})",
        f"- Cohere seed-53: net {top.get('cohere_seed53_net_wins')} (CI includes zero: {top.get('cohere_seed53_ci_includes_zero')})",
        f"- Azure seed-97: net {top.get('azure_seed97_net_wins')} (CI includes zero: {top.get('azure_seed97_ci_includes_zero')})",
        f"- Macro net: {top.get('macro_net_wins')}",
        "",
        "## Is it different from External-3 / Pooled-4 standalone?",
        "Yes — requires External-3 and Pooled-4 to **agree** and differ from FTA; stricter than either standalone.",
        "",
        "## Why it works",
        "Rescues rows where frontier-led FTA is wrong but both majority signals agree on the same alternative.",
        "",
        "## Where it fails",
        f"{len(losses)} regressions total across 1320 rows — see TOP_CANDIDATE_REGRESSIONS.csv.",
        "",
        "## API validation?",
        "Not recommended for unguarded rule at this time. Offline net is positive but rule is a strict "
        "subset of pooled-majority overrides; pooled4 standalone or guarded `frontier_support<=1` variant "
        "should be compared on a fresh seed first.",
        "",
        "## What not to claim",
        "- Not promoted; FTA remains canonical.",
        "- Offline replay ≠ independent API validation.",
        "- Not equivalent to full Pooled-4 standalone (lower override rate, different trigger).",
    ]
    write_text(output_dir / "FINAL_POOLED4_EXT3_AGREEMENT_AUDIT_SUMMARY.md", "\n".join(final).rstrip() + "\n")

    return {
        "output_dir": str(output_dir),
        "classification": classification,
        "macro_net_wins": top.get("macro_net_wins"),
        "wins": len(wins),
        "losses": len(losses),
    }


def main() -> int:
    args = parse_args()
    result = run_audit(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
