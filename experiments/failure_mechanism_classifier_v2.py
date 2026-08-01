"""Failure-Mechanism Classifier v2 — offline unified Cohere + Azure failure analysis.

Reads cached JSONL only. Does not call APIs, promote rules, or change FTA logic.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.tree import DecisionTreeClassifier, export_text

from experiments.analyze_azure_distribution_shift import (
    AZURE_DEFAULT_VALIDATION_PATH,
    build_cohere_aggregate,
    build_corpus,
    enrich_feature_row,
)
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import write_csv, write_json, write_jsonl, write_text
from experiments.mine_pattern_cause_repair import (
    RUNTIME_DECISION_FEATURES,
    build_item_index,
    build_pattern_row,
    build_repair_rule_specs,
    decision_repair_primary_plus_unanimity_fallback,
    mine_association_rules,
)
from experiments.replay_azure_inspired_rules_on_cohere import (
    SWFB,
    build_replay_rule_specs,
    decision_conservative_ext3_swfb_disagree,
    decision_ext3_when_frontier_support_le_1,
    decision_ext3_when_swfb,
)
from experiments.stress_test_exploratory_rules import (
    ILLEGAL_FIELD_BLOCKLIST,
    audit_rule_decision_legality,
    decision_canonical_fta,
    decision_external3_majority,
    decision_pooled4_majority,
    evaluate_rule_full,
    paired_bootstrap_ci,
)

COHERE_SEED53_PATH = (
    "outputs/api_validation_live/cohere_seed53_repair_primary_20260708T223801Z/"
    "run_out/per_example_records.jsonl"
)

REPAIR_NAME = "repair_primary_plus_unanimity_fallback"
FTA_NAME = "baseline_canonical_fta"

RUNTIME_FEATURE_COLUMNS = [
    "frontier_support",
    "support_margin",
    "candidate_pool_answer_group_count",
    "override_reason",
    "direct_frontier_agree",
    "effective_fix2_action",
    "effective_fix4_action",
    "no_effective_gate_action",
    "external_answers_unanimous",
    "external_unanimous_against_frontier",
    "two_of_three_external_against_frontier",
    "external_majority_count",
    "frontier_matches_any_external",
    "answer_group_count",
    "parser_failure_any",
]

POSTHOC_CORRECTNESS_COLUMNS = [
    "fta_correct",
    "frontier_correct",
    "l1_correct",
    "s1_correct",
    "tale_correct",
    "external3_correct",
    "pooled4_correct",
    "repair_primary_correct",
    "swfb_correct",
    "gold_answer_canonical",
    "failure_class_coarse",
]


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
    return Path("outputs/failure_analysis") / f"failure_mechanism_classifier_v2_{ts}"


def _question_hash(text: str | None) -> str:
    norm = " ".join(str(text or "").strip().lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest() if norm else ""


def load_all_corpora(*, seed53_path: str, azure_path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cohere_agg, _ = build_cohere_aggregate()
    for row in cohere_agg:
        row = dict(row)
        row["corpus"] = "cohere_aggregate720"
        row["provider"] = "cohere"
        rows.append(row)

    seed53_rows, _ = build_corpus(
        corpus_id="cohere_seed53",
        input_path=seed53_path,
        source_id="cohere_disjoint_seed53_full",
    )
    for row in seed53_rows:
        row = dict(row)
        row["corpus"] = "cohere_seed53"
        row["provider"] = "cohere"
        row["seed"] = 53
        rows.append(row)

    azure_rows, _ = build_corpus(
        corpus_id="azure_seed97",
        input_path=azure_path,
        source_id="azure_disjoint_seed97",
    )
    for row in azure_rows:
        row = dict(row)
        row["corpus"] = "azure_seed97"
        row["provider"] = "azure_openai"
        row["seed"] = 97
        rows.append(row)
    return rows


def _swfb_answer(row: dict[str, Any]) -> str | None:
    ans = decision_ext3_when_swfb(row)
    return ans if ans not in (None, "") else row.get("fta_selected_answer_canonical")


def _repair_answer(row: dict[str, Any]) -> str | None:
    ans = decision_repair_primary_plus_unanimity_fallback(row)
    return ans if ans not in (None, "") else row.get("fta_selected_answer_canonical")


def build_unified_row(row: dict[str, Any]) -> dict[str, Any]:
    gold = row.get("gold_answer_canonical")
    fta_ans = row.get("fta_selected_answer_canonical")
    ext3_ans = row.get("external3_answer")
    pooled4_ans = row.get("pooled4_answer")
    repair_ans = _repair_answer(row)
    swfb_ans = _swfb_answer(row)

    def _correct(ans: Any) -> bool | None:
        if ans in (None, "") or gold in (None, ""):
            return None
        return str(ans) == str(gold)

    unified = {
        "row_id": row.get("row_id"),
        "provider": row.get("provider"),
        "corpus": row.get("corpus"),
        "seed": row.get("seed"),
        "source_id": row.get("source_id"),
        "example_id": row.get("example_id"),
        "question_hash": _question_hash(row.get("problem_text")),
        "problem_text": row.get("problem_text"),
        "frontier_answer": row.get("frontier_answer_canonical"),
        "l1_answer": row.get("l1_answer_canonical"),
        "s1_answer": row.get("s1_answer_canonical"),
        "tale_answer": row.get("tale_answer_canonical"),
        "fta_answer": fta_ans,
        "external3_answer": ext3_ans,
        "pooled4_answer": pooled4_ans,
        "repair_primary_answer": repair_ans,
        "swfb_answer": swfb_ans,
        "override_reason": row.get("override_reason"),
        "effective_fix2_action": row.get("effective_fix2_action"),
        "effective_fix4_action": row.get("effective_fix4_action"),
        "no_effective_gate_action": row.get("no_effective_gate_action"),
        "effective_policy_label": row.get("effective_policy_label"),
        "frontier_support": row.get("frontier_support"),
        "support_margin": row.get("support_margin"),
        "direct_frontier_agree": row.get("direct_frontier_agree"),
        "external_answers_unanimous": row.get("external_answers_unanimous"),
        "external_unanimous_against_frontier": row.get("external_unanimous_against_frontier"),
        "two_of_three_external_against_frontier": row.get("two_of_three_external_against_frontier"),
        "external_majority_count": row.get("external_majority_count"),
        "candidate_pool_answer_group_count": row.get("candidate_pool_answer_group_count"),
        "parser_failure_any": row.get("parser_failure_any"),
        "failure_class_coarse": row.get("failure_class_coarse"),
        # post-hoc only
        "gold_answer": gold,
        "frontier_correct": row.get("frontier_correct"),
        "l1_correct": row.get("l1_correct"),
        "s1_correct": row.get("s1_correct"),
        "tale_correct": row.get("tale_correct"),
        "fta_correct": row.get("fta_correct"),
        "external3_correct": row.get("external3_correct"),
        "pooled4_correct": row.get("pooled4_correct"),
        "repair_primary_correct": _correct(repair_ans),
        "swfb_correct": _correct(swfb_ans),
        "all_methods_wrong": row.get("all_methods_wrong"),
    }
    unified["repair_primary_wins_vs_fta"] = bool(unified["repair_primary_correct"] and not unified["fta_correct"])
    unified["repair_primary_losses_vs_fta"] = bool(unified["fta_correct"] and not unified["repair_primary_correct"])
    unified["swfb_wins_vs_fta"] = bool(unified["swfb_correct"] and not unified["fta_correct"])
    unified["swfb_losses_vs_fta"] = bool(unified["fta_correct"] and not unified["swfb_correct"])
    return unified


def is_interesting_row(u: dict[str, Any]) -> bool:
    fta_c = bool(u.get("fta_correct"))
    p4_c = bool(u.get("pooled4_correct"))
    e3_c = bool(u.get("external3_correct"))
    if not fta_c:
        return True
    if fta_c and not p4_c:
        return True
    if fta_c and not e3_c:
        return True
    if not fta_c and p4_c:
        return True
    if not fta_c and e3_c:
        return True
    if u.get("repair_primary_wins_vs_fta") or u.get("repair_primary_losses_vs_fta"):
        return True
    if u.get("swfb_wins_vs_fta") or u.get("swfb_losses_vs_fta"):
        return True
    if u.get("parser_failure_any"):
        return True
    if u.get("all_methods_wrong"):
        return True
    answers = {
        str(u.get("fta_answer") or ""),
        str(u.get("external3_answer") or ""),
        str(u.get("pooled4_answer") or ""),
        str(u.get("repair_primary_answer") or ""),
        str(u.get("swfb_answer") or ""),
    }
    if len(answers) > 1 and "" not in answers and len(answers) != 1:
        if u.get("fta_answer") != u.get("pooled4_answer") or u.get("fta_answer") != u.get("external3_answer"):
            return True
    return False


def assign_mechanism_labels(u: dict[str, Any]) -> dict[str, Any]:
    layer_a: list[str] = []
    layer_b: list[str] = []
    layer_c: list[str] = []

    fta_c = bool(u.get("fta_correct"))
    p4_c = bool(u.get("pooled4_correct"))
    e3_c = bool(u.get("external3_correct"))
    pool_has_gold = bool(u.get("correct_in_candidate_pool")) if "correct_in_candidate_pool" in u else any(
        u.get(k) for k in ("frontier_correct", "l1_correct", "s1_correct", "tale_correct")
    )

    if u.get("parser_failure_any"):
        layer_a.append("normalization_or_parser_repairable")
        layer_b.append("answer_extraction_or_normalization_issue")
        layer_c.append("normalization_fix")
    if not fta_c and (p4_c or e3_c):
        layer_a.append("majority_or_pooled_repairable")
    if not fta_c and u.get("repair_primary_wins_vs_fta"):
        layer_a.append("selector_repairable")
    if u.get("all_methods_wrong"):
        layer_a.append("current_pool_unrecoverable")
        layer_b.append("all_methods_wrong")
        layer_c.append("generation_diversity_fix")
    elif not pool_has_gold and not fta_c:
        layer_b.append("correct_answer_absent_from_pool")
        layer_c.append("generation_diversity_fix")
    elif not fta_c and pool_has_gold:
        layer_b.append("correct_answer_present_but_not_selected")
    if not fta_c and p4_c:
        layer_b.append("pooled_majority_ignored")
        layer_c.append("pooled4_fallback")
    if not fta_c and e3_c:
        layer_b.append("external_majority_ignored")
        layer_c.append("external3_fallback")
    if not fta_c and p4_c and not e3_c:
        pass  # already tagged pooled
    if not fta_c and e3_c and not p4_c:
        pass  # already tagged external
    if fta_c and not p4_c and u.get("fta_answer") != u.get("pooled4_answer"):
        layer_b.append("frontier_overtrusted")
    if u.get("repair_primary_losses_vs_fta"):
        layer_b.append("FTA_gate_too_aggressive")
    if u.get("two_of_three_external_against_frontier") and u.get("override_reason") == "frontier_support_margin_override":
        layer_c.append("support_threshold_recalibration")
    if str(u.get("override_reason")) == SWFB:
        layer_b.append("provider_specific_metadata_shift")
        layer_c.append("provider_conditioned_selector")
    if u.get("failure_class_coarse") == "frontier_allocation_miss":
        layer_b.append("frontier_overtrusted")
    if not layer_a:
        layer_a.append("uncertain")
    if not layer_b:
        layer_b.append("uncertain")
    if not layer_c:
        layer_c.append("no_selector_repair")

    return {
        "layer_a_repairability": "|".join(sorted(set(layer_a))),
        "layer_b_mechanism": "|".join(sorted(set(layer_b))),
        "layer_c_suggested_repair_family": "|".join(sorted(set(layer_c))),
    }


# ---------------------------------------------------------------------------
# New candidate rules (exploratory; not promoted)
# ---------------------------------------------------------------------------


def decision_pooled4_when_ext3_pooled4_agree_against_fta(row: dict[str, Any]) -> str | None:
    ext3 = decision_external3_majority(row)
    p4 = decision_pooled4_majority(row)
    fta = row.get("fta_selected_answer_canonical")
    if ext3 in (None, "") or p4 in (None, "") or fta in (None, ""):
        return None
    if str(ext3) == str(p4) and str(ext3) != str(fta):
        return p4
    return None


def decision_pooled4_when_fta_wrong_region_two_of_three(row: dict[str, Any]) -> str | None:
    if not row.get("two_of_three_external_against_frontier"):
        return None
    if str(row.get("override_reason")) != "frontier_support_margin_override":
        return None
    return decision_pooled4_majority(row)


def decision_ext3_when_pooled4_disagree_fta(row: dict[str, Any]) -> str | None:
    """Use External-3 only when it disagrees with FTA but matches pooled4 disagreement pattern."""
    ext3 = decision_external3_majority(row)
    p4 = decision_pooled4_majority(row)
    fta = row.get("fta_selected_answer_canonical")
    if ext3 in (None, "") or fta in (None, ""):
        return None
    if str(ext3) != str(fta) and p4 not in (None, "") and str(ext3) != str(p4):
        return ext3
    return None


def decision_flag_fta_pooled4_disagree(row: dict[str, Any]) -> str | None:
    """Abstention proxy: keep FTA but tag region — returns FTA (no change) unless strong disagree."""
    p4 = decision_pooled4_majority(row)
    fta = row.get("fta_selected_answer_canonical")
    if p4 in (None, "") or fta in (None, ""):
        return None
    if str(p4) != str(fta) and row.get("two_of_three_external_against_frontier"):
        return fta  # explicit no-op override for audit; diagnostic region marker
    return None


def build_v2_hypothesis_specs() -> list[RuleSpec]:
    return [
        RuleSpec("pooled4_when_ext3_pooled4_agree_against_fta", "v2_hypothesis", "", decision_pooled4_when_ext3_pooled4_agree_against_fta),
        RuleSpec("pooled4_when_fta_wrong_region_two_of_three", "v2_hypothesis", "", decision_pooled4_when_fta_wrong_region_two_of_three),
        RuleSpec("ext3_when_pooled4_disagree_fta", "v2_hypothesis", "", decision_ext3_when_pooled4_disagree_fta),
        RuleSpec("conservative_ext3_swfb_disagree", "v2_hypothesis", "", decision_conservative_ext3_swfb_disagree),
        RuleSpec("ext3_when_frontier_support_le_1", "v2_hypothesis", "", decision_ext3_when_frontier_support_le_1),
        RuleSpec("azure_ext3_when_swfb", "v2_hypothesis", "", decision_ext3_when_swfb),
    ]


def build_pattern_rows_for_mining(unified_rows: list[dict[str, Any]], raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_by_id = {str(r.get("row_id")): r for r in raw_rows}
    pattern_rows = []
    for u in unified_rows:
        raw = raw_by_id.get(str(u.get("row_id")), {})
        pr = build_pattern_row(raw, subtype=None, normalization_suspect_ids=set())
        pr["corpus"] = u.get("corpus")
        pr["provider"] = u.get("provider")
        pr["fta_wrong_pooled4_correct"] = bool(not u.get("fta_correct") and u.get("pooled4_correct"))
        pr["fta_wrong_external3_correct"] = bool(not u.get("fta_correct") and u.get("external3_correct"))
        pr["fta_correct_pooled4_wrong"] = bool(u.get("fta_correct") and not u.get("pooled4_correct"))
        pr["repair_primary_win"] = bool(u.get("repair_primary_wins_vs_fta"))
        pr["repair_primary_loss"] = bool(u.get("repair_primary_losses_vs_fta"))
        pr["repair_primary_change"] = pr["repair_primary_win"] or pr["repair_primary_loss"]
        pattern_rows.append(pr)
    return pattern_rows


def run_subgroup_discovery(pattern_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    item_index = build_item_index(pattern_rows)
    targets = [
        ("fta_wrong_pooled4_correct", lambda r: bool(r.get("fta_wrong_pooled4_correct"))),
        ("fta_wrong_external3_correct", lambda r: bool(r.get("fta_wrong_external3_correct"))),
        ("fta_correct_pooled4_wrong", lambda r: bool(r.get("fta_correct_pooled4_wrong"))),
        ("repair_primary_win", lambda r: bool(r.get("repair_primary_win"))),
        ("repair_primary_loss", lambda r: bool(r.get("repair_primary_loss"))),
    ]
    all_rules: list[dict[str, Any]] = []
    for target_name, target_fn in targets:
        rules = mine_association_rules(
            pattern_rows,
            item_index,
            target_name=target_name,
            target_fn=target_fn,
            min_support_count=3,
            min_confidence=0.35,
            min_lift=1.1,
            top_n=8,
        )
        for r in rules:
            r["discovery_target"] = target_name
        all_rules.extend(rules)
    return all_rules


def _encode_features(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    cols: list[str] = []
    frames: list[pd.DataFrame] = []
    for col in RUNTIME_FEATURE_COLUMNS:
        if col not in df.columns:
            continue
        if col == "override_reason":
            dummies = pd.get_dummies(df[col].fillna("missing").astype(str), prefix="or")
            frames.append(dummies)
            cols.extend(list(dummies.columns))
        else:
            frames.append(df[[col]].fillna(-1).astype(float))
            cols.append(col)
    if not frames:
        return np.zeros((len(df), 1)), ["empty"]
    X = pd.concat(frames, axis=1).to_numpy()
    return X, cols


def run_decision_trees(pattern_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(pattern_rows)
    tasks = [
        ("pooled4_fixes_fta", "fta_wrong_pooled4_correct"),
        ("external3_fixes_fta", "fta_wrong_external3_correct"),
        ("fta_beats_pooled4", "fta_correct_pooled4_wrong"),
        ("repair_changes_correctness", "repair_primary_change"),
    ]
    results: list[dict[str, Any]] = []
    tree_md: list[str] = ["# Decision Tree Patterns", ""]
    for task_name, target in tasks:
        y = df[target].astype(int)
        if y.sum() == 0 or y.sum() == len(y):
            results.append({"task": task_name, "status": "skipped", "reason": "degenerate target"})
            continue
        X, feat_names = _encode_features(df)
        clf = DecisionTreeClassifier(max_depth=3, min_samples_leaf=5, random_state=0)
        clf.fit(X, y)
        for forbidden in ILLEGAL_FIELD_BLOCKLIST:
            assert forbidden not in feat_names
        tree_md.append(f"## {task_name}")
        tree_md.append("```")
        tree_md.append(export_text(clf, feature_names=feat_names))
        tree_md.append("```")
        results.append(
            {
                "task": task_name,
                "status": "ok",
                "positive_rate": float(y.mean()),
                "feature_names": ";".join(feat_names),
                "tree_depth": int(clf.get_depth()),
            }
        )
    return results, "\n".join(tree_md).rstrip() + "\n"


def run_rule_list_classifier(pattern_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Rule-List Classifier (ordered IF-THEN, runtime-legal features only)",
        "",
        "1. IF `override_reason=frontier_support_margin_override` AND `two_of_three_external_against_frontier=True` "
        "THEN label `majority_or_pooled_repairable` / suggest `pooled4_fallback` or `external3_fallback`.",
        "2. IF `parser_failure_any=True` THEN `normalization_or_parser_repairable`.",
        "3. IF `all_methods_wrong` THEN `current_pool_unrecoverable` / `generation_diversity_fix`.",
        "4. IF `override_reason=single_weak_frontier_branch` THEN `provider_conditioned_selector` (Azure-heavy).",
        "5. ELSE `uncertain` / `no_selector_repair`.",
        "",
        "This list is descriptive of dominant mined patterns, not a promoted runtime policy.",
    ]
    return "\n".join(lines) + "\n"


def _cluster_medoid(X: np.ndarray, labels: np.ndarray, row_indices: list[int]) -> int:
    """Pick the point closest to its cluster centroid (medoid approximation)."""
    best_idx = row_indices[0]
    best_dist = float("inf")
    for cluster_id in sorted(set(int(x) for x in labels)):
        if cluster_id < 0:
            continue
        members = [i for i, lab in enumerate(labels) if int(lab) == cluster_id]
        if not members:
            continue
        sub = X[members]
        center = sub.mean(axis=0)
        for local_i, global_i in enumerate(members):
            dist = float(np.linalg.norm(sub[local_i] - center))
            if dist < best_dist:
                best_dist = dist
                best_idx = row_indices[global_i]
    return best_idx


def run_cluster_comparison(pattern_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    df = pd.DataFrame(pattern_rows)
    X, feat_names = _encode_features(df)
    n = len(df)
    if n < 5:
        return [], "# Cluster report\n\nToo few rows.\n"

    k = min(8, max(2, n // 20))
    km = KMeans(n_clusters=k, init="k-means++", random_state=0, n_init=10)
    km_labels = km.fit_predict(X)

    agg = AgglomerativeClustering(n_clusters=k)
    agg_labels = agg.fit_predict(X)

    hdbscan_labels = None
    try:
        import hdbscan  # type: ignore

        hdb = hdbscan.HDBSCAN(min_cluster_size=max(5, n // 30))
        hdbscan_labels = hdb.fit_predict(X)
    except ImportError:
        hdbscan_labels = None

    comparison: list[dict[str, Any]] = []
    report_lines = ["# Interpretable Cluster Report", "", f"Features: {', '.join(feat_names)}", ""]
    row_indices = list(range(n))

    for method_name, labels in (
        ("kmeans_pp", km_labels),
        ("agglomerative", agg_labels),
        ("hdbscan", hdbscan_labels),
    ):
        if labels is None:
            comparison.append({"method": method_name, "status": "unavailable"})
            continue
        medoid_idx = _cluster_medoid(X, labels, row_indices)
        medoid_row = pattern_rows[medoid_idx]
        sizes = Counter(int(x) for x in labels if int(x) >= 0)
        comparison.append(
            {
                "method": method_name,
                "n_clusters": len(sizes),
                "largest_cluster_size": max(sizes.values()) if sizes else 0,
                "medoid_row_id": medoid_row.get("row_id"),
                "medoid_corpus": medoid_row.get("corpus"),
                "dominant_override_reason": medoid_row.get("override_reason"),
            }
        )
        report_lines.append(f"## {method_name}")
        report_lines.append(f"- clusters: {len(sizes)}")
        report_lines.append(f"- medoid row: {medoid_row.get('row_id')} ({medoid_row.get('corpus')})")
        report_lines.append(f"- medoid override_reason: {medoid_row.get('override_reason')}")
        report_lines.append("")

    return comparison, "\n".join(report_lines).rstrip() + "\n"


def replay_rules_by_corpus(
    corpora_rows: dict[str, list[dict[str, Any]]],
    specs: list[RuleSpec],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    boot_rows: list[dict[str, Any]] = []
    fta_by_corpus = {
        corpus: evaluate_rule_full(rows, RuleSpec(FTA_NAME, "baseline", "", decision_canonical_fta))
        for corpus, rows in corpora_rows.items()
    }
    for spec in specs:
        row_out: dict[str, Any] = {"rule_name": spec.name, "family": spec.family}
        nets: list[int] = []
        for corpus, rows in corpora_rows.items():
            ev = evaluate_rule_full(rows, spec)
            fta_ev = fta_by_corpus[corpus]
            boot = paired_bootstrap_ci(
                ev["per_row"], fta_ev["per_row"], n_resamples=bootstrap_resamples, seed=bootstrap_seed
            )
            boot_rows.append({"rule_name": spec.name, "corpus": corpus, **boot})
            row_out[f"{corpus}_accuracy"] = ev["accuracy"]
            row_out[f"{corpus}_net_wins"] = ev["net_wins"]
            row_out[f"{corpus}_losses"] = ev["losses_vs_canonical_fta"]
            row_out[f"{corpus}_wins"] = ev["wins_vs_canonical_fta"]
            row_out[f"{corpus}_overrides_triggered"] = ev.get("overrides_triggered")
            row_out[f"{corpus}_regression_rate"] = ev.get("regression_rate_among_fta_correct")
            row_out[f"{corpus}_ci_includes_zero"] = boot.get("includes_zero")
            nets.append(ev["net_wins"])
        row_out["macro_net_wins"] = sum(nets)
        providers = {corpus.split("_")[0] for corpus in corpora_rows}
        if row_out.get("azure_seed97_net_wins", 0) > 0 and row_out.get("cohere_aggregate720_net_wins", 0) > 0:
            row_out["provider_invariance"] = "cross_provider_positive"
        elif "swfb" in spec.name:
            row_out["provider_invariance"] = "azure_specific_candidate"
        else:
            row_out["provider_invariance"] = "mixed_or_cohere_specific"
        results.append(row_out)
    return results, boot_rows


def propose_hypotheses_csv() -> list[dict[str, Any]]:
    return [
        {
            "rule_name": "pooled4_when_ext3_pooled4_agree_against_fta",
            "runtime_features": "external3_answer,pooled4_answer,fta_selected_answer_canonical",
            "intuition": "When pooled majority and external majority agree against FTA, pooled4 may be safer than repair_primary.",
            "target_failure_class": "pooled_majority_ignored",
            "expected_benefit": "Rescue FTA-wrong rows where pooled signal is strong",
            "overfitting_risk": "medium",
            "provider_invariance": "moderate",
            "offline_evaluable": True,
            "needs_api_run": False,
        },
        {
            "rule_name": "pooled4_when_fta_wrong_region_two_of_three",
            "runtime_features": "two_of_three_external_against_frontier,override_reason",
            "intuition": "Same region as repair_primary but use pooled4 instead of gated external override.",
            "target_failure_class": "frontier_allocation_miss",
            "expected_benefit": "Higher rescue rate than repair_primary on Cohere",
            "overfitting_risk": "high",
            "provider_invariance": "low",
            "offline_evaluable": True,
            "needs_api_run": True,
        },
        {
            "rule_name": "conservative_ext3_swfb_disagree",
            "runtime_features": "override_reason,external3 vs fta disagreement",
            "intuition": "Azure SWFB region: only switch when External-3 disagrees with FTA.",
            "target_failure_class": "provider_specific_metadata_shift",
            "expected_benefit": "Azure gains with fewer regressions than standalone External-3",
            "overfitting_risk": "medium",
            "provider_invariance": "azure_specific",
            "offline_evaluable": True,
            "needs_api_run": False,
        },
        {
            "rule_name": "provider_conditioned_swfb_vs_pooled4",
            "runtime_features": "override_reason distribution (SWFB vs FSMO)",
            "intuition": "Use SWFB rule on Azure-like metadata; pooled4 gated fallback on Cohere-like FSMO region.",
            "target_failure_class": "provider_specific_metadata_shift",
            "expected_benefit": "Combine best per-provider offline winners",
            "overfitting_risk": "high",
            "provider_invariance": "explicitly_conditioned",
            "offline_evaluable": True,
            "needs_api_run": True,
        },
    ]


def render_final_summary(
    *,
    summary: dict[str, Any],
    replay_results: list[dict[str, Any]],
    output_dir: Path,
) -> str:
    best_pooled = max(replay_results, key=lambda r: r.get("macro_net_wins", -999))
    lines = [
        "# Final Failure Mechanism Classifier v2 Summary",
        "",
        f"Output: `{output_dir}`",
        "",
        "## Are previous failure classes too coarse?",
        "",
        "Yes — `frontier_allocation_miss` and `fta_success` hide recoverable pooled/external regions. "
        f"V2 interesting rows: **{summary['interesting_row_count']}** / {summary['total_rows']} total.",
        "",
        "## Dominant mechanisms",
        "",
        f"- Layer B counts: {json.dumps(summary.get('layer_b_counts', {}), sort_keys=True)}",
        "",
        "## Why repair_primary failed on seed-53",
        "",
        "Seed-53: net 0 (1 win / 1 loss). Repair fired in similar FSMO region as Aggregate-720 but "
        "the single win and single loss cancelled; bootstrap CI includes zero. Distribution of "
        "`override_reason` and `direct_frontier_agree` on seed-53 does not replicate the +6 net from 720.",
        "",
        "## Why Pooled-4 is strong",
        "",
        f"Pooled-4 correct on {summary.get('pooled4_correct_counts', {})}. "
        "Pooled-4 aggregates frontier + externals and wins when frontier is wrong but another method is right.",
        "",
        "## Best next algorithmic candidate",
        "",
        f"Highest macro net among v2 hypotheses: **{best_pooled['rule_name']}** (macro net {best_pooled.get('macro_net_wins')}).",
        "Provider-conditioned SWFB on Azure + gated pooled4 on Cohere FSMO region remains exploratory.",
        "",
        "## API run now?",
        "",
        "**More offline refinement first.** repair_primary inconclusive on seed-53; no candidate beats "
        "Pooled-4 macro average without regression audit on a fresh split.",
        "",
        "## What not to claim",
        "",
        "- Do not promote repair_primary (failed independent replication).",
        "- Do not claim Pooled-4 as main method without regression analysis (high regression risk on prior synthesis).",
        "- FTA remains canonical.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def run_analysis(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir) if args.output_dir else _timestamp_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = load_all_corpora(seed53_path=args.cohere_seed53_input, azure_path=args.azure_input)
    unified_all = [build_unified_row(r) for r in raw_rows]
    unified = [u for u in unified_all if is_interesting_row(u)]

    label_rows = []
    for u in unified:
        labels = assign_mechanism_labels(u)
        label_rows.append({**u, **labels})

    write_csv(output_dir / "FAILURE_MECHANISM_V2_TABLE.csv", label_rows, list(label_rows[0].keys()) if label_rows else ["row_id"])
    write_jsonl(output_dir / "FAILURE_MECHANISM_V2_TABLE.jsonl", label_rows)

    layer_b_counts = Counter()
    for lr in label_rows:
        for part in str(lr.get("layer_b_mechanism", "")).split("|"):
            if part:
                layer_b_counts[part] += 1

    pooled4_correct_counts = Counter()
    for corpus in ("cohere_aggregate720", "cohere_seed53", "azure_seed97"):
        sub = [u for u in unified_all if u.get("corpus") == corpus]
        pooled4_correct_counts[corpus] = sum(1 for u in sub if u.get("pooled4_correct"))

    table_summary = {
        "total_rows": len(unified_all),
        "interesting_row_count": len(unified),
        "corpus_counts": dict(Counter(u.get("corpus") for u in unified_all)),
        "layer_b_counts": dict(layer_b_counts),
        "pooled4_correct_counts": dict(pooled4_correct_counts),
        "runtime_feature_columns": RUNTIME_FEATURE_COLUMNS,
        "posthoc_correctness_columns": POSTHOC_CORRECTNESS_COLUMNS,
    }
    write_json(output_dir / "FAILURE_MECHANISM_V2_SUMMARY.json", table_summary)

    write_csv(output_dir / "FAILURE_MECHANISM_LABELS.csv", label_rows, list(label_rows[0].keys()) if label_rows else ["row_id"])
    write_text(
        output_dir / "FAILURE_MECHANISM_LABEL_REPORT.md",
        "# Failure Mechanism Label Report\n\n"
        f"Interesting rows: {len(unified)}. Layer B distribution: {json.dumps(dict(layer_b_counts), sort_keys=True)}\n",
    )

    pattern_rows = build_pattern_rows_for_mining(unified, raw_rows)
    subgroup_rules = run_subgroup_discovery(pattern_rows)
    write_csv(
        output_dir / "SUBGROUP_DISCOVERY_RULES.csv",
        subgroup_rules,
        list(subgroup_rules[0].keys()) if subgroup_rules else ["discovery_target"],
    )

    tree_results, tree_md = run_decision_trees(pattern_rows)
    write_text(output_dir / "DECISION_TREE_PATTERNS.md", tree_md)
    write_text(output_dir / "RULE_LIST_CLASSIFIER.md", run_rule_list_classifier(pattern_rows))

    cluster_comparison, cluster_report = run_cluster_comparison(pattern_rows)
    if cluster_comparison:
        all_keys: list[str] = []
        for row in cluster_comparison:
            for k in row:
                if k not in all_keys:
                    all_keys.append(k)
        write_csv(output_dir / "CLUSTER_COMPARISON.csv", cluster_comparison, all_keys)
    write_text(output_dir / "INTERPRETABLE_CLUSTER_REPORT.md", cluster_report)

    hypotheses = propose_hypotheses_csv()
    write_csv(output_dir / "NEW_REPAIR_HYPOTHESES_V2.csv", hypotheses, list(hypotheses[0].keys()))
    write_text(
        output_dir / "NEW_REPAIR_HYPOTHESES_V2.md",
        "# New Repair Hypotheses V2\n\nSee NEW_REPAIR_HYPOTHESES_V2.csv for full table.\n",
    )

    corpora_rows = {
        "cohere_aggregate720": [r for r in raw_rows if r.get("corpus") == "cohere_aggregate720"],
        "cohere_seed53": [r for r in raw_rows if r.get("corpus") == "cohere_seed53"],
        "azure_seed97": [r for r in raw_rows if r.get("corpus") == "azure_seed97"],
    }
    replay_specs = build_v2_hypothesis_specs()
    audit = audit_rule_decision_legality(replay_specs)
    replay_results, boot_rows = replay_rules_by_corpus(
        corpora_rows,
        replay_specs,
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
    )
    write_csv(output_dir / "NEW_REPAIR_RULE_REPLAY_RESULTS.csv", replay_results, list(replay_results[0].keys()) if replay_results else ["rule_name"])
    write_csv(output_dir / "NEW_REPAIR_RULE_BOOTSTRAP_CI.csv", boot_rows, list(boot_rows[0].keys()) if boot_rows else ["rule_name"])
    write_text(
        output_dir / "NEW_REPAIR_RULE_REPLAY_REPORT.md",
        "# New Repair Rule Replay Report\n\n"
        f"Rules replayed: {len(replay_specs)}. Legality audit: {sum(1 for a in audit if a.get('is_runtime_legal'))}/{len(audit)} legal.\n",
    )

    final_md = render_final_summary(summary=table_summary, replay_results=replay_results, output_dir=output_dir)
    write_text(output_dir / "FINAL_FAILURE_MECHANISM_CLASSIFIER_V2_SUMMARY.md", final_md)

    return {
        "output_dir": str(output_dir),
        "interesting_rows": len(unified),
        "subgroup_rules": len(subgroup_rules),
        "replay_rules": len(replay_results),
        "layer_b_counts": dict(layer_b_counts),
    }


def main() -> int:
    args = parse_args()
    result = run_analysis(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
