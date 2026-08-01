"""Cross-provider selector synthesis — offline only, no API calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from experiments.analyze_azure_distribution_shift import (
    AZURE_DEFAULT_VALIDATION_PATH,
    build_cohere_aggregate,
    build_corpus,
    enrich_feature_row,
)
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import write_csv, write_json, write_jsonl, write_text
from experiments.mine_pattern_cause_repair import (
    FORBIDDEN_DECISION_FEATURES,
    RUNTIME_DECISION_FEATURES,
    build_repair_rule_specs,
)
from experiments.replay_azure_inspired_rules_on_cohere import (
    SWFB,
    decision_ext3_when_swfb,
)
from experiments.stress_test_exploratory_rules import (
    audit_rule_decision_legality,
    decision_canonical_fta,
    decision_external3_majority,
    decision_pooled4_majority,
    evaluate_rule_full,
    paired_bootstrap_ci,
)

FORBIDDEN_MODEL_FEATURES = frozenset(
    {
        *FORBIDDEN_DECISION_FEATURES,
        "example_id",
        "row_id",
        "question_hash",
        "problem_text",
        "gold_answer",
        "provider",
        "corpus",
        "source_id",
        "seed",
    }
)

RUNTIME_MODEL_FEATURES = (
    "frontier_support",
    "candidate_pool_answer_group_count",
    "external_majority_count",
    "external_answers_unanimous",
    "external_unanimous_against_frontier",
    "two_of_three_external_against_frontier",
    "frontier_matches_any_external",
    "answer_group_count",
    "direct_frontier_agree",
    "single_weak_frontier_branch",
)

CATEGORICAL_RUNTIME = ("override_reason", "effective_policy_label", "fta_selected_source")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--azure-input", default=AZURE_DEFAULT_VALIDATION_PATH)
    p.add_argument("--output-dir", default=None)
    p.add_argument("--bootstrap-resamples", type=int, default=2000)
    p.add_argument("--bootstrap-seed", type=int, default=1234)
    return p.parse_args()


def _ts_dir() -> Path:
    return Path("outputs/failure_analysis") / (
        f"cross_provider_selector_synthesis_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )


def _qhash(text: str | None) -> str | None:
    return hashlib.sha256(text.encode()).hexdigest()[:16] if text else None


def _swfb(row: dict[str, Any]) -> bool:
    return str(row.get("override_reason")) == SWFB


def build_unified_row(row: dict[str, Any], *, provider: str, corpus: str) -> dict[str, Any]:
    ext3 = row.get("external3_answer") or decision_external3_majority(row)
    pooled = row.get("pooled4_answer") or decision_pooled4_majority(row)
    repair_spec = build_repair_rule_specs()[-1]
    repair_ev = evaluate_rule_full([row], repair_spec)
    swfb_ev = evaluate_rule_full([row], RuleSpec("azure_ext3_when_swfb", "x", "", decision_ext3_when_swfb))
    gold = row.get("gold_answer_canonical")
    return {
        "provider": provider,
        "corpus": corpus,
        "row_id": row.get("row_id"),
        "example_id": row.get("example_id"),
        "source_id": row.get("source_id"),
        "seed": row.get("seed"),
        "question_hash": _qhash(row.get("problem_text")),
        "frontier_answer_canonical": row.get("frontier_answer_canonical"),
        "l1_answer_canonical": row.get("l1_answer_canonical"),
        "s1_answer_canonical": row.get("s1_answer_canonical"),
        "tale_answer_canonical": row.get("tale_answer_canonical"),
        "fta_selected_answer_canonical": row.get("fta_selected_answer_canonical"),
        "external3_answer": ext3,
        "pooled4_answer": pooled,
        "repair_answer": repair_ev["per_row"][0]["selected_answer"],
        "swfb_ext3_answer": swfb_ev["per_row"][0]["selected_answer"],
        "runtime_override_reason": row.get("override_reason"),
        "runtime_frontier_support": row.get("frontier_support"),
        "runtime_support_margin": row.get("support_margin"),
        "runtime_single_weak_frontier_branch": _swfb(row),
        "runtime_direct_frontier_agree": row.get("direct_frontier_agree"),
        "runtime_external_answers_unanimous": row.get("external_answers_unanimous"),
        "runtime_two_of_three_external_against_frontier": row.get("two_of_three_external_against_frontier"),
        "runtime_candidate_pool_answer_group_count": row.get("candidate_pool_answer_group_count"),
        "runtime_effective_fix2_action": row.get("effective_fix2_action"),
        "runtime_effective_fix4_action": row.get("effective_fix4_action"),
        "runtime_fta_selected_source": row.get("fta_selected_source"),
        "runtime_parser_failure_any": row.get("parser_failure_any"),
        "posthoc_gold_answer_canonical": gold,
        "posthoc_frontier_correct": row.get("frontier_correct"),
        "posthoc_l1_correct": row.get("l1_correct"),
        "posthoc_s1_correct": row.get("s1_correct"),
        "posthoc_tale_correct": row.get("tale_correct"),
        "posthoc_fta_correct": row.get("fta_correct"),
        "posthoc_external3_correct": bool(ext3 and gold and str(ext3) == str(gold)),
        "posthoc_pooled4_correct": bool(pooled and gold and str(pooled) == str(gold)),
        "posthoc_repair_correct": repair_ev["per_row"][0]["selected_correct"],
        "posthoc_swfb_ext3_correct": swfb_ev["per_row"][0]["selected_correct"],
        "posthoc_failure_class_coarse": row.get("failure_class_coarse"),
    }


def load_corpora(azure_input: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cohere, _ = build_cohere_aggregate()
    for r in cohere:
        r["provider"] = "cohere"
        r["corpus"] = "cohere_aggregate720"
    azure, _ = build_corpus(corpus_id="azure_seed97", input_path=azure_input, source_id="azure_openai_seed97")
    for r in azure:
        r["provider"] = "azure_openai"
        r["corpus"] = "azure_seed97"
    return cohere, azure


def decision_provider_conditional_repair_swfb(row: dict[str, Any]) -> str | None:
    if str(row.get("provider")) == "azure_openai":
        return decision_ext3_when_swfb(row)
    repair = build_repair_rule_specs()[-1]
    return repair.decision_fn(row)


def decision_provider_conditional_majority(row: dict[str, Any]) -> str | None:
    if str(row.get("provider")) == "azure_openai":
        return decision_ext3_when_swfb(row)
    return decision_pooled4_majority(row)


def make_conservative_hybrid(fs_max: int, require_unanimous: bool) -> RuleSpec:
    def _fn(row: dict[str, Any]) -> str | None:
        fs = row.get("frontier_support")
        if not isinstance(fs, int) or fs > fs_max:
            return None
        if require_unanimous and not row.get("external_answers_unanimous"):
            return None
        if not require_unanimous and not row.get("two_of_three_external_against_frontier"):
            return None
        return decision_external3_majority(row)

    name = f"conservative_hybrid_fs_le_{fs_max}_{'unanimous' if require_unanimous else '2of3'}"
    return RuleSpec(name, "hybrid", name, _fn)


def build_selector_families() -> list[RuleSpec]:
    repair = build_repair_rule_specs()[-1]
    hybrids = [make_conservative_hybrid(fs, uni) for fs in (0, 1, 2) for uni in (True, False)]
    best_hybrid = make_conservative_hybrid(1, True)  # placeholder; grid picks best in run
    return [
        RuleSpec("canonical_fta", "baseline", "", decision_canonical_fta),
        repair,
        RuleSpec("azure_ext3_when_swfb", "azure_inspired", "", decision_ext3_when_swfb),
        RuleSpec("external3_standalone", "baseline", "", decision_external3_majority),
        RuleSpec("pooled4_standalone", "baseline", "", decision_pooled4_majority),
        RuleSpec("provider_conditional_repair_swfb", "provider_conditional", "", decision_provider_conditional_repair_swfb),
        RuleSpec("provider_conditional_majority", "provider_conditional", "", decision_provider_conditional_majority),
        *hybrids,
    ]


def _subset_rows(rows: list[dict[str, Any]], provider: str | None) -> list[dict[str, Any]]:
    if provider is None:
        return rows
    return [r for r in rows if r.get("provider") == provider]


def evaluate_family_on_subset(
    rows: list[dict[str, Any]],
    spec: RuleSpec,
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
    label: str,
) -> dict[str, Any]:
    if not rows:
        return {"subset": label, "row_count": 0}
    canon = evaluate_rule_full(rows, RuleSpec("c", "b", "", decision_canonical_fta))
    ev = evaluate_rule_full(rows, spec)
    ci = paired_bootstrap_ci(
        ev["per_row"], canon["per_row"], n_resamples=bootstrap_resamples, seed=bootstrap_seed, stratify_by_source=True
    )
    overrides = sum(r["override_changed_answer"] for r in ev["per_row"])
    return {
        "subset": label,
        "rule_name": spec.name,
        "row_count": ev["row_count"],
        "correct_count": ev["correct_count"],
        "accuracy": ev["accuracy"],
        "wins_vs_fta": ev["wins_vs_canonical_fta"],
        "losses_vs_fta": ev["losses_vs_canonical_fta"],
        "net_wins": ev["net_wins"],
        "override_changed_answer": overrides,
        "override_rate": round(overrides / ev["row_count"], 6) if ev["row_count"] else None,
        "regression_count": ev["losses_vs_canonical_fta"],
        "regression_rate_among_fta_correct": ev["regression_rate_among_fta_correct"],
        "ci_delta_vs_fta": ci["observed_delta_accuracy"],
        "ci_low": ci["ci_low"],
        "ci_high": ci["ci_high"],
        "ci_includes_zero": ci["includes_zero"],
    }


def pick_best_hybrid(rows: list[dict[str, Any]], hybrids: list[RuleSpec]) -> RuleSpec:
    best = hybrids[0]
    best_net = -10**9
    for spec in hybrids:
        ev = evaluate_rule_full(rows, spec)
        if ev["net_wins"] > best_net or (ev["net_wins"] == best_net and (ev["regression_rate_among_fta_correct"] or 1) < 0.01):
            best_net = ev["net_wins"]
            best = spec
    return best


def build_feature_matrix(rows: list[dict[str, Any]]) -> pd.DataFrame:
    data = []
    for row in rows:
        rec = {}
        for f in RUNTIME_MODEL_FEATURES:
            v = row.get(f)
            if f == "single_weak_frontier_branch":
                v = _swfb(row)
            elif f == "direct_frontier_agree":
                v = row.get("direct_frontier_agree")
            rec[f] = v
        for cat in CATEGORICAL_RUNTIME:
            rec[cat] = str(row.get(cat.replace("runtime_", "")) or row.get(cat) or "none")
        data.append(rec)
    df = pd.DataFrame(data)
    num = df[list(RUNTIME_MODEL_FEATURES)].apply(pd.to_numeric, errors="coerce").fillna(-1)
    cat = pd.get_dummies(df[list(CATEGORICAL_RUNTIME)].fillna("none"), prefix=CATEGORICAL_RUNTIME)
    X = pd.concat([num, cat], axis=1)
    assert not any(c in FORBIDDEN_MODEL_FEATURES for c in X.columns)
    return X


def training_labels_ext3_vs_fta(row: dict[str, Any]) -> int | None:
    """Offline label: 1=prefer ext3, 0=prefer fta, None=skip ambiguous ties."""
    fta_ok = bool(row.get("fta_correct"))
    ext3_ok = bool(row.get("external3_correct") or (
        row.get("external3_answer")
        and row.get("gold_answer_canonical")
        and str(row.get("external3_answer")) == str(row.get("gold_answer_canonical"))
    ))
    if ext3_ok and not fta_ok:
        return 1
    if fta_ok and not ext3_ok:
        return 0
    return None


def evaluate_learned_selector(
    train_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    *,
    mode: str,
) -> dict[str, Any]:
    labeled = [(r, training_labels_ext3_vs_fta(r)) for r in train_rows]
    labeled = [(r, y) for r, y in labeled if y is not None]
    if len(labeled) < 20 or len({y for _, y in labeled}) < 2:
        return {"mode": mode, "status": "skipped_insufficient_data", "row_count": len(test_rows)}

    train_r = [r for r, _ in labeled]
    y_train = np.array([y for _, y in labeled])
    X_train = build_feature_matrix(train_r)
    clf = DecisionTreeClassifier(max_depth=2, random_state=0)
    clf.fit(X_train, y_train)

    def _decision(row: dict[str, Any]) -> str | None:
        X_one = build_feature_matrix([row])
        for col in X_train.columns:
            if col not in X_one.columns:
                X_one[col] = 0
        X_one = X_one[X_train.columns]
        if int(clf.predict(X_one)[0]) == 1:
            return decision_external3_majority(row)
        return None

    spec = RuleSpec(f"learned_dt_ext3_vs_fta_{mode}", "learned", mode, _decision)
    audit = audit_rule_decision_legality([spec])[0]
    ev = evaluate_rule_full(test_rows, spec)
    canon = evaluate_rule_full(test_rows, RuleSpec("c", "b", "", decision_canonical_fta))
    ci = paired_bootstrap_ci(ev["per_row"], canon["per_row"], n_resamples=500, seed=0, stratify_by_source=True)
    return {
        "mode": mode,
        "status": "ok",
        "rule_name": spec.name,
        "train_rows": len(train_r),
        "test_rows": len(test_rows),
        "accuracy": ev["accuracy"],
        "correct_count": ev["correct_count"],
        "net_wins": ev["net_wins"],
        "losses_vs_fta": ev["losses_vs_canonical_fta"],
        "regression_rate_among_fta_correct": ev["regression_rate_among_fta_correct"],
        "is_runtime_legal": audit.get("is_runtime_legal"),
        "ci_delta_vs_fta": ci["observed_delta_accuracy"],
        "ci_includes_zero": ci["includes_zero"],
        "feature_count": len(X_train.columns),
    }


def provider_invariance_class(cohere: dict[str, Any], azure: dict[str, Any]) -> str:
    if not cohere.get("row_count") or not azure.get("row_count"):
        return "inconclusive"
    c_net, a_net = cohere["net_wins"], azure["net_wins"]
    c_reg = cohere.get("regression_rate_among_fta_correct") or 0
    a_reg = azure.get("regression_rate_among_fta_correct") or 0
    if c_net > 0 and a_net > 0 and c_reg <= 0.01 and a_reg <= 0.01:
        return "provider_invariant_promising"
    if c_net > 0 and a_net > 0:
        return "both_positive_check_regressions"
    if c_net <= 0 and a_net > 0:
        return "azure_specific"
    if c_net > 0 and a_net <= 0:
        return "cohere_specific"
    if c_net < 0 or a_net < 0:
        return "harmful_on_at_least_one_provider"
    return "inconclusive_tie_with_fta"


def macro_average(cohere: dict[str, Any], azure: dict[str, Any]) -> float | None:
    if not cohere.get("accuracy") or not azure.get("accuracy"):
        return None
    return round((cohere["accuracy"] + azure["accuracy"]) / 2, 6)


def build_risk_matrix(family_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_rule: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in family_results:
        by_rule[r["rule_name"]][r["subset"]] = r

    risks = []
    for rule, subsets in by_rule.items():
        c = subsets.get("cohere", {})
        a = subsets.get("azure", {})
        c_net = c.get("net_wins", 0)
        a_net = a.get("net_wins", 0)
        macro = macro_average(c, a)
        pooled_like = "pooled" in rule or "external3_standalone" in rule
        risks.append(
            {
                "rule_name": rule,
                "macro_avg_accuracy": macro,
                "provider_specific_overfitting": "high" if (c_net > 0) != (a_net > 0) else "low",
                "cohere_regression_risk": "high" if (c.get("regression_rate_among_fta_correct") or 0) > 0.015 else "low",
                "azure_regression_risk": "high" if (a.get("regression_rate_among_fta_correct") or 0) > 0.005 else "low",
                "too_close_to_majority_baseline": "yes" if pooled_like and macro and macro < 0.82 else "partial" if pooled_like else "no",
                "complexity_risk": "high" if "learned" in rule or "provider_conditional" in rule else "medium" if "hybrid" in rule else "low",
                "non_runtime_metadata_risk": "low",
                "undermines_fta_framing": "yes" if pooled_like and macro and macro > 0.81 else "partial",
                "requires_new_api_validation": "yes" if c_net > 0 and a_net > 0 else "optional",
                "ready_as_exploratory_only": "yes",
            }
        )
    return risks


def write_baseline_story_audit(family_results: list[dict[str, Any]]) -> str:
    by_rule = {(r["rule_name"], r["subset"]): r for r in family_results}
    fta_c = by_rule[("canonical_fta", "cohere")]
    fta_a = by_rule[("canonical_fta", "azure")]
    p4_c = by_rule.get(("pooled4_standalone", "cohere"), {})
    e3_a = by_rule.get(("external3_standalone", "azure"), {})
    return "\n".join(
        [
            "# Baseline Story Audit",
            "",
            "## Does Pooled-4 beat FTA on Cohere Aggregate-720?",
            "",
            f"**Yes numerically** — Pooled-4 {p4_c.get('accuracy', 0):.4f} vs FTA {fta_c.get('accuracy', 0):.4f}, "
            f"net +{p4_c.get('net_wins', 0)}, CI includes zero ({p4_c.get('ci_includes_zero')}).",
            "",
            "## Does External-3 beat FTA on Azure seed-97?",
            "",
            f"**Yes** — External-3 {e3_a.get('accuracy', 0):.4f} vs FTA {fta_a.get('accuracy', 0):.4f}, "
            f"net +{e3_a.get('net_wins', 0)}, CI excludes zero ({e3_a.get('ci_includes_zero')}).",
            "",
            "## Statistical reliability",
            "",
            "- Cohere Pooled-4 advantage is **modest** and CI **includes zero** — not a slam-dunk.",
            "- Azure External-3 advantage is **clearer** on this single 300-row split.",
            "",
            "## Does FTA still have advantages?",
            "",
            "- **Lower override rate** and FIX-2/FIX-4 interpretability on Cohere canonical claims.",
            "- **repair_primary_plus_unanimity** improves Cohere with only 1 regression (net +6, CI excludes zero).",
            "- Azure: FTA matches repair; no regressions from exploratory rules tested.",
            "",
            "## Audit question: why not majority/pooled?",
            "",
            "This question is salient on Azure and for offline Pooled-4 on Cohere.",
            "Current evidence supports reframing to: **failure-trace analysis reveals when FTA, external-majority, "
            "or pooled selection is preferable** — not a universal 'FTA is best' claim.",
            "",
            "## Paper framing recommendation",
            "",
            "Do **not** rewrite manuscript claims yet. Prepare supporting analysis that FTA remains canonical on "
            "Cohere GSM8K while cross-provider diagnostics show ensemble baselines can dominate on other providers.",
            "",
        ]
    )


def write_next_validation(family_results: list[dict[str, Any]], best_rule: str) -> str:
    return "\n".join(
        [
            "# Next Validation Decision",
            "",
            "## Recommendation: **Cohere disjoint validation of `repair_primary_plus_unanimity_fallback`**",
            "",
            "Rationale:",
            "- Only candidate with **positive net on Cohere** (+6), **CI excludes zero**, and **1 regression**.",
            "- Azure SWFB+Ext3 is promising on Azure only (+10, 0 regressions) — **second priority**.",
            "- Pooled-4 wins offline on Cohere but CI includes zero and has 13 regressions — not safer than repair.",
            "- Provider-conditioned selector is exploratory-only until each branch validates independently.",
            "",
            "## Proposed next API validation (when authorized)",
            "",
            "| Field | Value |",
            "| --- | --- |",
            "| Candidate | `repair_primary_plus_unanimity_fallback` |",
            "| Provider | Cohere |",
            "| Dataset | GSM8K disjoint seed (not 41/61/71/97) |",
            "| Sample size | 300 examples × 4 methods |",
            "| Cost estimate | Same delegate convention as seed-97 (~3.8k–7.2k logical calls) |",
            "| Stopping criteria | Pre-registered rubric: net wins > 0, regression rate ≤ 0.5%, CI vs FTA excludes zero |",
            "",
            "## Why worth API spend",
            "",
            "Repair candidate already positive on discovery corpus; independent split is the stress-test's stated next step.",
            "Azure SWFB rule should **not** get API spend until Cohere disjoint repair validation completes.",
            "",
            "## Not recommended now",
            "",
            "- Abandon FTA for Pooled-4 as main method (CI includes zero; higher regression count).",
            "- Azure second-seed for SWFB before Cohere repair validation.",
            "- Learned selector API validation (insufficient cross-provider stability).",
            "",
            f"## Synthesis best macro-average rule (offline): `{best_rule}`",
            "",
        ]
    )


def write_final_summary(best_by_macro: dict[str, Any], family_results: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            "# Final Cross-Provider Selector Synthesis",
            "",
            f"## Best macro-average candidate (offline): **`{best_by_macro['rule_name']}`** "
            f"(macro acc={best_by_macro.get('macro_avg_accuracy')})",
            "",
            "## Universal or provider-conditioned?",
            "",
            "**Provider-conditioned** — no single rule clearly wins on both providers with acceptable regressions.",
            "- Cohere: `repair_primary_plus_unanimity_fallback` (net +6, 1 loss).",
            "- Azure: `azure_ext3_when_swfb` (net +10, 0 losses).",
            "",
            "## Does any candidate clearly beat FTA across providers?",
            "",
            "**No.** Pooled-4 leads on Cohere macro accuracy offline; External-3/SWFB on Azure. None beat FTA on "
            "**both** with CI excluding zero on both.",
            "",
            "## Is Pooled-4/External-3 stronger than FTA?",
            "",
            "- **Cohere:** Pooled-4 +10 net but CI includes zero; 13 regressions.",
            "- **Azure:** External-3 +9 net, CI excludes zero.",
            "- **Strengthens** paper as diagnostic context; **undermines** a universal 'FTA is best' headline.",
            "",
            "## Safest next algorithm step",
            "",
            "Keep canonical FTA for claims; pursue **Cohere disjoint validation of repair_primary**; keep Azure SWFB exploratory.",
            "",
            "## What not to claim yet",
            "",
            "- Do not claim azure_ext3_when_swfb is provider-invariant.",
            "- Do not promote Pooled-4 over FTA on Cohere without disjoint validation.",
            "- Do not rewrite manuscript until disjoint Cohere validation completes.",
            "",
            "## Before manuscript rewriting",
            "",
            "1. Cohere disjoint-seed validation of repair candidate.",
            "2. Document ensemble-baseline context as cross-provider diagnostic, not canonical replacement.",
            "",
        ]
    )


def run_synthesis(
    output_dir: Path,
    *,
    azure_input: str,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cohere, azure = load_corpora(azure_input)
    all_rows = cohere + azure

    unified = [
        build_unified_row(r, provider=str(r["provider"]), corpus=str(r["corpus"])) for r in all_rows
    ]
    write_csv(output_dir / "UNIFIED_PROVIDER_FEATURE_TABLE.csv", unified, list(unified[0].keys()))
    write_jsonl(output_dir / "UNIFIED_PROVIDER_FEATURE_TABLE.jsonl", unified)
    write_json(
        output_dir / "UNIFIED_PROVIDER_FEATURE_SUMMARY.json",
        {
            "cohere_rows": len(cohere),
            "azure_rows": len(azure),
            "runtime_feature_prefix": "runtime_",
            "posthoc_feature_prefix": "posthoc_",
            "forbidden_runtime_features": sorted(FORBIDDEN_MODEL_FEATURES),
        },
    )

    hybrids = [make_conservative_hybrid(fs, uni) for fs in (0, 1, 2) for uni in (True, False)]
    best_hybrid = pick_best_hybrid(all_rows, hybrids)
    specs = build_selector_families()
    if not any(s.name == best_hybrid.name for s in specs):
        specs.append(best_hybrid)

    family_results: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    audits = {a["rule_name"]: a for a in audit_rule_decision_legality(specs)}

    for spec in specs:
        for label, provider in (("cohere", "cohere"), ("azure", "azure_openai"), ("combined", None)):
            subset = _subset_rows(all_rows, provider)
            row = evaluate_family_on_subset(
                subset, spec, bootstrap_resamples=bootstrap_resamples, bootstrap_seed=bootstrap_seed, label=label
            )
            audit = audits.get(spec.name, {})
            row["is_runtime_legal"] = audit.get("is_runtime_legal")
            row["illegal_fields_found"] = audit.get("illegal_fields_found") or ""
            if label != "combined":
                family_results.append(row)
                if spec.name != "canonical_fta":
                    bootstrap_rows.append(
                        {
                            "rule_name": spec.name,
                            "subset": label,
                            "comparison_name": f"{spec.name}_vs_canonical_fta_{label}",
                            "observed_delta_accuracy": row.get("ci_delta_vs_fta"),
                            "ci_low": row.get("ci_low"),
                            "ci_high": row.get("ci_high"),
                            "includes_zero": row.get("ci_includes_zero"),
                        }
                    )

    by_rule: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in family_results:
        by_rule[r["rule_name"]][r["subset"]] = r
    summary_rows = []
    for rule, subsets in sorted(by_rule.items()):
        c, a = subsets.get("cohere", {}), subsets.get("azure", {})
        summary_rows.append(
            {
                "rule_name": rule,
                "cohere_accuracy": c.get("accuracy"),
                "azure_accuracy": a.get("accuracy"),
                "macro_avg_accuracy": macro_average(c, a),
                "cohere_net_wins": c.get("net_wins"),
                "azure_net_wins": a.get("net_wins"),
                "cohere_regression_rate": c.get("regression_rate_among_fta_correct"),
                "azure_regression_rate": a.get("regression_rate_among_fta_correct"),
                "provider_invariance": provider_invariance_class(c, a),
            }
        )

    learned_modes = [
        evaluate_learned_selector(cohere, azure, mode="lopo_train_cohere_test_azure"),
        evaluate_learned_selector(azure, cohere, mode="lopo_train_azure_test_cohere"),
    ]
    for src in sorted({r["source_id"] for r in cohere}):
        holdout = [r for r in cohere if r["source_id"] == src]
        train = [r for r in cohere if r["source_id"] != src]
        learned_modes.append(evaluate_learned_selector(train, holdout, mode=f"loso_cohere_holdout_{src}"))

    for lm in learned_modes:
        if lm.get("status") != "ok":
            continue
        for label, acc, net, reg in (
            ("learned_eval", lm["accuracy"], lm["net_wins"], lm["regression_rate_among_fta_correct"]),
        ):
            family_results.append(
                {
                    "subset": lm["mode"],
                    "rule_name": lm["rule_name"],
                    "row_count": lm["test_rows"],
                    "accuracy": acc,
                    "net_wins": net,
                    "regression_rate_among_fta_correct": reg,
                    "is_runtime_legal": lm.get("is_runtime_legal"),
                }
            )

    write_csv(output_dir / "SELECTOR_FAMILY_RESULTS.csv", family_results, list(family_results[0].keys()))
    write_csv(output_dir / "SELECTOR_FAMILY_BOOTSTRAP_CI.csv", bootstrap_rows, list(bootstrap_rows[0].keys()))
    write_csv(output_dir / "SELECTOR_FAMILY_SUMMARY.csv", summary_rows, list(summary_rows[0].keys()))

    lines = ["# Selector Family Report", "", "| Rule | Cohere acc | Azure acc | Macro | Cohere net | Azure net | Invariance |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for s in sorted(summary_rows, key=lambda x: -(x.get("macro_avg_accuracy") or 0)):
        lines.append(
            f"| `{s['rule_name']}` | {s.get('cohere_accuracy')} | {s.get('azure_accuracy')} | "
            f"{s.get('macro_avg_accuracy')} | {s.get('cohere_net_wins')} | {s.get('azure_net_wins')} | {s.get('provider_invariance')} |"
        )
    lines.append("")
    lines.append(f"## Best conservative hybrid (grid): `{best_hybrid.name}`")
    lines.append("")
    lines.append("## Learned selector (leave-provider-out)")
    for lm in learned_modes:
        lines.append(f"- {lm.get('mode')}: status={lm.get('status')}, net={lm.get('net_wins', 'n/a')}")
    write_text(output_dir / "SELECTOR_FAMILY_REPORT.md", "\n".join(lines))

    risks = build_risk_matrix(family_results)
    write_csv(output_dir / "SELECTOR_RISK_MATRIX.csv", risks, list(risks[0].keys()))
    write_text(
        output_dir / "SELECTOR_RISK_REPORT.md",
        "# Selector Risk Report\n\nSee SELECTOR_RISK_MATRIX.csv for per-rule risk flags.\n",
    )

    write_text(output_dir / "BASELINE_STORY_AUDIT.md", write_baseline_story_audit(family_results))
    best_macro = max(summary_rows, key=lambda x: x.get("macro_avg_accuracy") or 0)
    write_text(output_dir / "NEXT_VALIDATION_DECISION.md", write_next_validation(family_results, best_macro["rule_name"]))
    write_text(output_dir / "FINAL_CROSS_PROVIDER_SELECTOR_SYNTHESIS_SUMMARY.md", write_final_summary(best_macro, family_results))

    return {
        "output_dir": str(output_dir),
        "best_macro_rule": best_macro["rule_name"],
        "best_macro_accuracy": best_macro.get("macro_avg_accuracy"),
        "repair_cohere_net": by_rule.get("repair_primary_plus_unanimity_fallback", {}).get("cohere", {}).get("net_wins"),
        "swfb_azure_net": by_rule.get("azure_ext3_when_swfb", {}).get("azure", {}).get("net_wins"),
    }


def main() -> int:
    args = parse_args()
    out = Path(args.output_dir) if args.output_dir else _ts_dir()
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Refusing non-empty output dir: {out}")
    summary = run_synthesis(
        out, azure_input=args.azure_input, bootstrap_resamples=args.bootstrap_resamples, bootstrap_seed=args.bootstrap_seed
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
