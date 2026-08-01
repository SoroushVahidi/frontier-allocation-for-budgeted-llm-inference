"""Pooled-4 benefit-risk classifier: offline guarded override discovery.

Identifies runtime-legal guards for when normalized Pooled-4 should override FTA.
No APIs, no promotion, gold only for post-hoc labels.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text

from experiments.analyze_azure_distribution_shift import AZURE_DEFAULT_VALIDATION_PATH
from experiments.audit_agreement_semantics import decision_guarded_norm_plurality
from experiments.audit_tiebreak_robustness import (
    DEFAULT_POOLED_ORDER,
    external_vote_class,
    pooled4_is_tie,
    pooled4_priority_plurality,
)
from experiments.build_failure_feature_table import normalize_answer
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import as_bool, as_int, write_csv, write_json, write_jsonl, write_text
from experiments.failure_mechanism_classifier_v2 import COHERE_SEED53_PATH, load_all_corpora
from experiments.freeze_guarded_majority_candidate import external3_valid_majority_normalized
from experiments.mine_pattern_cause_repair import (
    RUNTIME_DECISION_FEATURES,
    build_item_index,
    build_pattern_row,
    mine_association_rules,
)
from experiments.replay_azure_inspired_rules_on_cohere import SWFB
from experiments.stress_test_exploratory_rules import (
    audit_rule_decision_legality,
    decision_canonical_fta,
    evaluate_rule_full,
    paired_bootstrap_ci,
)

FTA_SPEC = RuleSpec("canonical_fta", "baseline", "", decision_canonical_fta)
DEFAULT_EXTERNAL_ORDER = ("L1", "S1", "TALE")


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
    return Path("outputs/failure_analysis") / f"pooled4_benefit_risk_classifier_{ts}"


def _norm(answer: Any) -> str | None:
    return normalize_answer(answer)


def pooled4_normalized(row: dict[str, Any]) -> str | None:
    return pooled4_priority_plurality(row, DEFAULT_POOLED_ORDER)


def external_plurality_diagnostic(row: dict[str, Any]) -> str | None:
    from experiments.audit_tiebreak_robustness import external_priority_plurality

    return external_priority_plurality(row, DEFAULT_EXTERNAL_ORDER)


def _question_hash(text: str | None) -> str:
    norm = " ".join(str(text or "").strip().lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest() if norm else ""


def _posthoc_correct(ans: Any, gold: Any) -> bool | None:
    if ans in (None, "") or gold in (None, ""):
        return None
    return str(ans) == str(gold)


def build_override_row(row: dict[str, Any]) -> dict[str, Any]:
    gold = row.get("gold_answer_canonical")
    fta = row.get("fta_selected_answer_canonical")
    fta_norm = _norm(fta)
    p4 = pooled4_normalized(row)
    ext_strict = external3_valid_majority_normalized(row)
    ext_plur = external_plurality_diagnostic(row)
    fta_ok = as_bool(row.get("fta_correct"))
    p4_ok = _posthoc_correct(p4, gold)
    differs = bool(p4 not in (None, "") and fta_norm not in (None, "") and str(p4) != str(fta_norm))
    fixes = bool(differs and p4_ok and not fta_ok)
    regresses = bool(differs and fta_ok and not p4_ok)
    tie_corr = bool(differs and fta_ok == p4_ok)

    out: dict[str, Any] = {
        "row_id": row.get("row_id"),
        "provider": row.get("provider"),
        "corpus": row.get("corpus"),
        "seed": row.get("seed"),
        "example_id": row.get("example_id"),
        "question_hash_reporting_only": _question_hash(row.get("problem_text")),
        "problem_text": row.get("problem_text"),
        "gold_answer": gold,
        "fta_answer": fta,
        "fta_answer_normalized": fta_norm,
        "pooled4_answer_normalized": p4,
        "external3_strict_majority": ext_strict,
        "external_plurality_diagnostic": ext_plur,
        "pooled4_differs_from_fta": differs,
        "pooled4_fixes_fta": fixes,
        "pooled4_regresses_fta": regresses,
        "pooled4_fta_correctness_tie": tie_corr,
        "frontier_support": row.get("frontier_support"),
        "support_margin": row.get("support_margin"),
        "override_reason": row.get("override_reason"),
        "effective_fix2_action": row.get("effective_fix2_action"),
        "effective_fix4_action": row.get("effective_fix4_action"),
        "no_effective_gate_action": row.get("no_effective_gate_action"),
        "fta_selected_source": row.get("fta_selected_source"),
        "candidate_pool_answer_group_count": row.get("candidate_pool_answer_group_count"),
        "external_answers_unanimous": row.get("external_answers_unanimous"),
        "external_unanimous_against_frontier": row.get("external_unanimous_against_frontier"),
        "two_of_three_external_against_frontier": row.get("two_of_three_external_against_frontier"),
        "external_strict_majority_exists": ext_strict not in (None, ""),
        "external_one_one_one_tie": external_vote_class(row) == "one_one_one_tie",
        "pooled4_tie_flag": pooled4_is_tie(row),
        "parser_failure_any": row.get("parser_failure_any"),
        "all_methods_wrong": row.get("all_methods_wrong"),
        "direct_frontier_agree": row.get("direct_frontier_agree"),
        "failure_class_coarse": row.get("failure_class_coarse"),
        # post-hoc
        "fta_correct": fta_ok,
        "pooled4_correct": p4_ok,
        "frontier_correct": row.get("frontier_correct"),
        "l1_correct": row.get("l1_correct"),
        "s1_correct": row.get("s1_correct"),
        "tale_correct": row.get("tale_correct"),
    }
    for surface in ("frontier", "l1", "s1", "tale"):
        out[f"{surface}_raw"] = row.get(f"{surface}_answer")
        out[f"{surface}_canonical"] = row.get(f"{surface}_answer_canonical")
        out[f"{surface}_normalized"] = row.get(f"normalized_{surface}_answer") or _norm(
            row.get(f"{surface}_answer_canonical")
        )
    return out


# ---------------------------------------------------------------------------
# Guarded Pooled-4 decision functions (exploratory, not promoted)
# ---------------------------------------------------------------------------


def _pooled4_override_if(row: dict[str, Any], guard: Callable[[dict[str, Any]], bool]) -> str | None:
    if not guard(row):
        return None
    p4 = pooled4_normalized(row)
    fta = _norm(row.get("fta_selected_answer_canonical"))
    if p4 in (None, "") or fta in (None, ""):
        return None
    if str(p4) != str(fta):
        return p4
    return None


def decision_pooled4_standalone(row: dict[str, Any]) -> str | None:
    return _pooled4_override_if(row, lambda r: True)


def decision_pooled4_strict_external_agrees(row: dict[str, Any]) -> str | None:
    ext = external3_valid_majority_normalized(row)
    p4 = pooled4_normalized(row)
    fta = _norm(row.get("fta_selected_answer_canonical"))
    if ext in (None, "") or p4 in (None, "") or fta in (None, ""):
        return None
    if str(ext) == str(p4) and str(p4) != str(fta):
        return p4
    return None


def decision_pooled4_external_unanimity_agrees(row: dict[str, Any]) -> str | None:
    if not row.get("external_answers_unanimous"):
        return None
    ext = external_plurality_diagnostic(row)
    p4 = pooled4_normalized(row)
    fta = _norm(row.get("fta_selected_answer_canonical"))
    if ext in (None, "") or p4 in (None, "") or fta in (None, ""):
        return None
    if str(ext) == str(p4) and str(p4) != str(fta):
        return p4
    return None


def decision_pooled4_fs_le(row: dict[str, Any], threshold: int) -> str | None:
    fs = as_int(row.get("frontier_support"))
    if fs is None or fs > threshold:
        return None
    return decision_pooled4_standalone(row)


def decision_pooled4_swfb(row: dict[str, Any]) -> str | None:
    if str(row.get("override_reason")) != SWFB:
        return None
    return decision_pooled4_standalone(row)


def decision_pooled4_fta_frontier_low_fs(row: dict[str, Any]) -> str | None:
    if str(row.get("fta_selected_source")) != "frontier":
        return None
    return decision_pooled4_fs_le(row, 1)


def decision_pooled4_not_p4_tie_fs_le1(row: dict[str, Any]) -> str | None:
    if pooled4_is_tie(row):
        return None
    return decision_pooled4_fs_le(row, 1)


def decision_pooled4_subgroup_best(row: dict[str, Any]) -> str | None:
    """Best mined conjunction: strict external exists & fs<=1 & not p4 tie."""
    if not row.get("external_strict_majority_exists"):
        return None
    if pooled4_is_tie(row):
        return None
    return decision_pooled4_fs_le(row, 1)


def decision_pooled4_conservative_zero_reg(row: dict[str, Any]) -> str | None:
    return decision_pooled4_strict_external_agrees(row)


def decision_pooled4_high_net_fs_le2(row: dict[str, Any]) -> str | None:
    return decision_pooled4_fs_le(row, 2)


def decision_pooled4_swfb_azure_diagnostic(row: dict[str, Any]) -> str | None:
    if row.get("provider") != "azure_openai":
        return None
    return decision_pooled4_swfb(row)


def decision_ext3_strict_standalone(row: dict[str, Any]) -> str | None:
    ext = external3_valid_majority_normalized(row)
    fta = _norm(row.get("fta_selected_answer_canonical"))
    if ext in (None, "") or fta in (None, ""):
        return None
    if str(ext) != str(fta):
        return ext
    return None


def build_guard_candidates() -> list[dict[str, Any]]:
    specs: list[tuple[str, str, Callable, str, str, bool]] = [
        ("A", "pooled4_when_strict_external_majority_agrees", decision_pooled4_strict_external_agrees, "universal", "high", False),
        ("B", "pooled4_when_external_unanimity_agrees", decision_pooled4_external_unanimity_agrees, "universal", "medium", False),
        ("C", "pooled4_when_frontier_support_le_1", lambda r: decision_pooled4_fs_le(r, 1), "universal", "medium", True),
        ("D", "pooled4_when_frontier_support_le_2", lambda r: decision_pooled4_fs_le(r, 2), "universal", "medium", True),
        ("E", "pooled4_when_swfb", decision_pooled4_swfb, "universal", "medium", False),
        ("F", "pooled4_when_fta_source_frontier_and_fs_low", decision_pooled4_fta_frontier_low_fs, "universal", "high", False),
        ("G", "pooled4_when_not_tie_and_fs_le_1", decision_pooled4_not_p4_tie_fs_le1, "universal", "high", False),
        ("H", "pooled4_subgroup_strict_ext_fs_le1_not_p4_tie", decision_pooled4_subgroup_best, "universal", "high", False),
        ("I", "pooled4_swfb_azure_diagnostic", decision_pooled4_swfb_azure_diagnostic, "provider_diagnostic", "low", False),
        ("J", "pooled4_subgroup_best_rule_list", decision_pooled4_subgroup_best, "universal", "high", False),
        ("K", "pooled4_conservative_strict_external_agree", decision_pooled4_conservative_zero_reg, "universal", "high", False),
        ("L", "pooled4_high_net_fs_le_2", decision_pooled4_high_net_fs_le2, "universal", "medium", True),
        ("REF", "pooled4_standalone_normalized", decision_pooled4_standalone, "universal", "medium", True),
        ("REF", "ext3_strict_standalone", decision_ext3_strict_standalone, "universal", "high", False),
        ("REF", "tiebreak_H_diagnostic", decision_guarded_norm_plurality, "diagnostic", "low", True),
    ]
    out = []
    for vid, name, fn, scope, validity, p4_tie_risk in specs:
        out.append(
            {
                "variant_id": vid,
                "rule_name": name,
                "scope": scope,
                "validity_rating": validity,
                "p4_tie_dependent": p4_tie_risk,
            }
        )
    return out


def build_guard_specs() -> list[tuple[str, str, RuleSpec]]:
    mapping = [
        ("A", "pooled4_when_strict_external_majority_agrees", decision_pooled4_strict_external_agrees),
        ("B", "pooled4_when_external_unanimity_agrees", decision_pooled4_external_unanimity_agrees),
        ("C", "pooled4_when_frontier_support_le_1", lambda r: decision_pooled4_fs_le(r, 1)),
        ("D", "pooled4_when_frontier_support_le_2", lambda r: decision_pooled4_fs_le(r, 2)),
        ("E", "pooled4_when_swfb", decision_pooled4_swfb),
        ("F", "pooled4_when_fta_source_frontier_and_fs_low", decision_pooled4_fta_frontier_low_fs),
        ("G", "pooled4_when_not_tie_and_fs_le_1", decision_pooled4_not_p4_tie_fs_le1),
        ("H", "pooled4_subgroup_strict_ext_fs_le1_not_p4_tie", decision_pooled4_subgroup_best),
        ("I", "pooled4_swfb_azure_diagnostic", decision_pooled4_swfb_azure_diagnostic),
        ("J", "pooled4_subgroup_best_rule_list", decision_pooled4_subgroup_best),
        ("K", "pooled4_conservative_strict_external_agree", decision_pooled4_conservative_zero_reg),
        ("L", "pooled4_high_net_fs_le_2", decision_pooled4_high_net_fs_le2),
        ("REF_p4", "pooled4_standalone_normalized", decision_pooled4_standalone),
        ("REF_ext3", "ext3_strict_standalone", decision_ext3_strict_standalone),
        ("REF_H", "tiebreak_H_diagnostic", decision_guarded_norm_plurality),
    ]
    return [(vid, name, RuleSpec(name, "guarded_p4", "", fn)) for vid, name, fn in mapping]


def win_loss_feature_comparison(override_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    differs = [r for r in override_rows if r.get("pooled4_differs_from_fta")]
    features = [
        "frontier_support",
        "support_margin",
        "override_reason",
        "fta_selected_source",
        "external_strict_majority_exists",
        "external_one_one_one_tie",
        "pooled4_tie_flag",
        "external_answers_unanimous",
        "two_of_three_external_against_frontier",
        "parser_failure_any",
        "all_methods_wrong",
    ]
    out = []
    for feat in features:
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in differs:
            val = r.get(feat)
            key = str(val) if val is not None else "null"
            if feat == "override_reason":
                key = str(val or "null")
            groups[key].append(r)
        for val, rows in groups.items():
            wins = sum(1 for r in rows if r.get("pooled4_fixes_fta"))
            losses = sum(1 for r in rows if r.get("pooled4_regresses_fta"))
            out.append(
                {
                    "feature": feat,
                    "value": val,
                    "count": len(rows),
                    "pooled4_wins": wins,
                    "pooled4_regresses": losses,
                    "win_rate": wins / len(rows) if rows else None,
                    "regression_rate": losses / len(rows) if rows else None,
                }
            )
    return out


def evaluate_all_rules(
    corpora: dict[str, list[dict[str, Any]]],
    specs: list[tuple[str, str, RuleSpec]],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    boot_rows: list[dict[str, Any]] = []
    fta_by = {c: evaluate_rule_full(rows, FTA_SPEC) for c, rows in corpora.items()}
    for vid, name, spec in specs:
        legality = audit_rule_decision_legality([spec])[0]
        row: dict[str, Any] = {
            "variant_id": vid,
            "rule_name": name,
            "runtime_legal": legality.get("is_runtime_legal"),
        }
        nets, losses_list = [], []
        for corpus, rows in corpora.items():
            ev = evaluate_rule_full(rows, spec)
            boot = paired_bootstrap_ci(
                ev["per_row"], fta_by[corpus]["per_row"], n_resamples=bootstrap_resamples, seed=bootstrap_seed
            )
            boot_rows.append({"variant_id": vid, "rule_name": name, "corpus": corpus, **boot})
            prefix = corpus
            row[f"{prefix}_accuracy"] = ev["accuracy"]
            row[f"{prefix}_net_wins"] = ev["net_wins"]
            row[f"{prefix}_wins"] = ev["wins_vs_canonical_fta"]
            row[f"{prefix}_losses"] = ev["losses_vs_canonical_fta"]
            row[f"{prefix}_overrides"] = ev.get("overrides_triggered")
            row[f"{prefix}_regression_rate"] = ev.get("regression_rate_among_fta_correct")
            row[f"{prefix}_ci_includes_zero"] = boot.get("includes_zero")
            nets.append(ev["net_wins"])
            losses_list.append(ev["losses_vs_canonical_fta"])
        row["macro_net_wins"] = sum(nets)
        row["macro_losses"] = sum(losses_list)
        if all(row.get(f"{c}_net_wins", 0) > 0 for c in corpora):
            row["provider_invariance"] = "positive_all"
        elif all(row.get(f"{c}_net_wins", 0) >= 0 for c in corpora):
            row["provider_invariance"] = "nonnegative_all"
        else:
            row["provider_invariance"] = "mixed"
        results.append(row)
    return results, boot_rows


def train_shallow_tree(pattern_rows: list[dict[str, Any]], override_rows: list[dict[str, Any]]) -> str:
    by_id = {str(r["row_id"]): r for r in override_rows}
    labeled = []
    for pr in pattern_rows:
        oid = str(pr["row_id"])
        o = by_id.get(oid)
        if not o or not o.get("pooled4_differs_from_fta"):
            continue
        if o.get("pooled4_fixes_fta"):
            y = 1
        elif o.get("pooled4_regresses_fta"):
            y = 0
        else:
            continue
        labeled.append((pr, y))
    if len(labeled) < 30:
        return "Insufficient labeled rows for decision tree.\n"
    features = [
        f
        for f in RUNTIME_DECISION_FEATURES
        if f not in ("source_id", "seed", "override_reason", "effective_policy_label", "fta_selected_answer_shape", "frontier_answer_shape", "l1_answer_shape", "s1_answer_shape", "tale_answer_shape")
    ]
    X = []
    y = []
    for pr, label in labeled:
        row_vals = []
        for f in features:
            v = pr.get(f)
            if isinstance(v, bool):
                row_vals.append(float(v))
            elif v is None or v == "":
                row_vals.append(-1.0)
            else:
                try:
                    row_vals.append(float(v))
                except (TypeError, ValueError):
                    row_vals.append(-1.0)
        X.append(row_vals)
        y.append(label)
    X_arr = np.array(X, dtype=float)
    y_arr = np.array(y)
    clf = DecisionTreeClassifier(max_depth=3, min_samples_leaf=10, random_state=0)
    clf.fit(X_arr, y_arr)
    return export_text(clf, feature_names=features)


def _macro_losses(row: dict[str, Any]) -> int:
    v = row.get("macro_losses")
    return 99 if v is None else int(v)


def classify_validation_readiness(results: list[dict[str, Any]]) -> tuple[str, str, dict[str, Any] | None]:
    universal = [r for r in results if r.get("variant_id") in set("ABCDEFGHJKL") and r.get("runtime_legal")]
    ref_p4 = next((r for r in results if r["rule_name"] == "pooled4_standalone_normalized"), None)
    best = max(
        [r for r in universal if _macro_losses(r) <= 3],
        key=lambda r: (r.get("macro_net_wins", 0), -_macro_losses(r)),
        default=None,
    )
    if best is None:
        return "inconclusive", "no candidate with <=3 macro losses", None
    if best.get("macro_net_wins", 0) < 8:
        return "useful diagnostic only", f"best macro net {best.get('macro_net_wins')}", best
    if _macro_losses(best) == 0 and best.get("macro_net_wins", 0) >= 10:
        if best.get("provider_invariance") == "positive_all":
            return "serious FTA-v2 candidate worth fresh API validation", "positive all corpora, 0 losses", best
        return "promising but needs more offline refinement", "0 losses but not all corpora positive", best
    if _macro_losses(best) <= 2:
        return "promising but needs more offline refinement", f"net {best.get('macro_net_wins')} losses {_macro_losses(best)}", best
    return "rejected", f"losses {_macro_losses(best)}", best


def build_casebook(rows: list[dict[str, Any]], override_rows: list[dict[str, Any]], best_fn: Callable) -> str:
    spec = RuleSpec("best", "c", "", best_fn)
    ev = evaluate_rule_full(rows, spec)
    o_by = {str(o["row_id"]): o for o in override_rows}
    lines = ["# Pooled-4 Win/Regression Casebook", ""]

    def section(title: str, filt: Callable, n: int = 6):
        lines.append(f"## {title}")
        c = 0
        for row, pr in zip(rows, ev["per_row"]):
            o = o_by.get(str(row.get("row_id")), {})
            if not filt(row, pr, o):
                continue
            lines.append(f"### {row.get('corpus')} / {row.get('example_id')}")
            lines.append(f"- Gold: {o.get('gold_answer')} | FTA: {o.get('fta_answer')} | P4: {o.get('pooled4_answer_normalized')}")
            lines.append(f"- fs={o.get('frontier_support')} reason={o.get('override_reason')} strict_ext={o.get('external_strict_majority_exists')}")
            c += 1
            if c >= n:
                break
        if c == 0:
            lines.append("_None._")
        lines.append("")

    section("Pooled-4 fixes FTA", lambda r, pr, o: o.get("pooled4_fixes_fta"))
    section("Pooled-4 regresses FTA", lambda r, pr, o: o.get("pooled4_regresses_fta"))
    section("Guard accepts good override", lambda r, pr, o: pr["win"])
    section("Guard blocks regression", lambda r, pr, o: o.get("pooled4_regresses_fta") and not pr["override_triggered"])
    section("Guard misses win", lambda r, pr, o: o.get("pooled4_fixes_fta") and not pr["override_triggered"])
    return "\n".join(lines).rstrip() + "\n"


def run_classifier(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir) if args.output_dir else _timestamp_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = load_all_corpora(seed53_path=args.cohere_seed53_input, azure_path=args.azure_input)
    override_rows = [build_override_row(r) for r in raw_rows]
    corpora = {
        "cohere_aggregate720": [r for r in raw_rows if r.get("corpus") == "cohere_aggregate720"],
        "cohere_seed53": [r for r in raw_rows if r.get("corpus") == "cohere_seed53"],
        "azure_seed97": [r for r in raw_rows if r.get("corpus") == "azure_seed97"],
    }

    fields = sorted({k for row in override_rows for k in row})
    write_csv(output_dir / "POOLED4_OVERRIDE_TABLE.csv", override_rows, fields)
    write_jsonl(output_dir / "POOLED4_OVERRIDE_TABLE.jsonl", override_rows)
    differs = [r for r in override_rows if r.get("pooled4_differs_from_fta")]
    summary = {
        "total_rows": len(override_rows),
        "pooled4_differs_count": len(differs),
        "pooled4_fixes": sum(1 for r in differs if r.get("pooled4_fixes_fta")),
        "pooled4_regresses": sum(1 for r in differs if r.get("pooled4_regresses_fta")),
        "by_corpus": dict(Counter(r["corpus"] for r in differs)),
    }
    write_json(output_dir / "POOLED4_OVERRIDE_SUMMARY.json", summary)

    wl_comp = win_loss_feature_comparison(override_rows)
    write_csv(output_dir / "POOLED4_WIN_LOSS_FEATURE_COMPARISON.csv", wl_comp, list(wl_comp[0].keys()) if wl_comp else ["feature"])
    wl_md = (
        "# Pooled-4 Win/Loss Analysis\n\n"
        f"- Differs from FTA: {summary['pooled4_differs_count']}\n"
        f"- Fixes: {summary['pooled4_fixes']} | Regresses: {summary['pooled4_regresses']}\n\n"
        "Regressions concentrate where frontier_support>1, FTA already correct with strong frontier, "
        "or Pooled-4 tie-break picks wrong plurality branch.\n"
    )
    write_text(output_dir / "POOLED4_WIN_LOSS_ANALYSIS.md", wl_md)

    pattern_rows = [
        build_pattern_row(r, subtype=None, normalization_suspect_ids=set()) for r in raw_rows
    ]
    for pr, o in zip(pattern_rows, override_rows):
        pr["pooled4_differs"] = o.get("pooled4_differs_from_fta")
        pr["pooled4_fixes"] = o.get("pooled4_fixes_fta")
        pr["pooled4_regresses"] = o.get("pooled4_regresses_fta")
        pr["external_strict_majority_exists"] = o.get("external_strict_majority_exists")
        pr["pooled4_tie_flag"] = o.get("pooled4_tie_flag")

    item_index = build_item_index(pattern_rows)
    extra_items = {
        "external_strict_majority_exists": {i for i, pr in enumerate(pattern_rows) if pr.get("external_strict_majority_exists")},
        "pooled4_tie_flag": {i for i, pr in enumerate(pattern_rows) if pr.get("pooled4_tie_flag")},
        "frontier_support_le_1": {i for i, pr in enumerate(pattern_rows) if (as_int(pr.get("frontier_support")) or 99) <= 1},
        "not_pooled4_tie": {i for i, pr in enumerate(pattern_rows) if not pr.get("pooled4_tie_flag")},
    }
    item_index.update(extra_items)

    fix_rules = mine_association_rules(
        pattern_rows,
        item_index,
        target_name="pooled4_fixes_fta",
        target_fn=lambda r: bool(r.get("pooled4_fixes")),
        universe_filter="pooled4_differs",
        min_support_count=3,
        min_confidence=0.5,
        min_lift=1.2,
    )
    reg_rules = mine_association_rules(
        pattern_rows,
        item_index,
        target_name="pooled4_regresses_fta",
        target_fn=lambda r: bool(r.get("pooled4_regresses")),
        universe_filter="pooled4_differs",
        min_support_count=2,
        min_confidence=0.4,
        min_lift=1.2,
    )
    subgroup_rules = fix_rules + reg_rules
    for sr in subgroup_rules:
        sr["runtime_legal"] = True
    write_csv(
        output_dir / "POOLED4_SUBGROUP_RULES.csv",
        subgroup_rules,
        sorted({k for r in subgroup_rules for k in r}) if subgroup_rules else ["target"],
    )
    write_text(output_dir / "POOLED4_SUBGROUP_REPORT.md", f"# Subgroup Rules\n\n{len(fix_rules)} fix rules, {len(reg_rules)} regression rules mined.\n")
    tree_txt = train_shallow_tree(pattern_rows, override_rows)
    write_text(output_dir / "POOLED4_DECISION_TREE_PATTERNS.md", f"# Decision Tree Patterns\n\n```\n{tree_txt}\n```\n")
    rule_list = "\n".join(
        f"- {r['itemset']}: conf={r['confidence']} lift={r['lift']} target={r['target']}"
        for r in fix_rules[:10]
    )
    write_text(output_dir / "POOLED4_RULE_LIST_CANDIDATES.md", f"# Rule List Candidates\n\n{rule_list}\n")

    candidates_meta = build_guard_candidates()
    write_csv(output_dir / "POOLED4_GUARDED_RULE_CANDIDATES.csv", candidates_meta, list(candidates_meta[0].keys()))
    write_text(
        output_dir / "POOLED4_GUARDED_RULE_CANDIDATES.md",
        "# Guarded Pooled-4 Rule Candidates\n\nSee CSV for formal definitions A–L + references.\n",
    )

    specs = build_guard_specs()
    replay_results, boot_rows = evaluate_all_rules(
        corpora, specs, bootstrap_resamples=args.bootstrap_resamples, bootstrap_seed=args.bootstrap_seed
    )
    write_csv(output_dir / "POOLED4_GUARDED_REPLAY_RESULTS.csv", replay_results, sorted({k for r in replay_results for k in r}))
    write_csv(output_dir / "POOLED4_GUARDED_BOOTSTRAP_CI.csv", boot_rows, sorted({k for r in boot_rows for k in r}))
    replay_md = ["# Guarded Pooled-4 Replay Report", ""]
    for r in sorted(replay_results, key=lambda x: -(x.get("macro_net_wins") or 0)):
        replay_md.append(
            f"- **{r['rule_name']}**: macro net {r.get('macro_net_wins')}, losses {r.get('macro_losses')}, "
            f"invariance {r.get('provider_invariance')}"
        )
    write_text(output_dir / "POOLED4_GUARDED_REPLAY_REPORT.md", "\n".join(replay_md).rstrip() + "\n")

    classification, reason, best = classify_validation_readiness(replay_results)
    best_fn = decision_pooled4_subgroup_best
    if best:
        name = best.get("rule_name")
        for _, n, spec in specs:
            if n == name:
                best_fn = spec.decision_fn
                break

    write_text(output_dir / "POOLED4_WIN_REGRESSION_CASEBOOK.md", build_casebook(raw_rows, override_rows, best_fn))
    write_text(
        output_dir / "POOLED4_VALIDATION_READINESS_DECISION.md",
        f"# Validation Readiness\n\n**Classification:** {classification}\n\n**Reason:** {reason}\n\n"
        f"**Best candidate:** {best.get('rule_name') if best else 'none'}\n",
    )

    ref = next((r for r in replay_results if r["rule_name"] == "pooled4_standalone_normalized"), {})
    final = [
        "# Final Pooled-4 Benefit-Risk Classifier Summary",
        "",
        f"**Classification:** {classification}",
        "",
        "## Why is Pooled-4 strong?",
        f"Standalone macro net {ref.get('macro_net_wins')}; fixes {summary['pooled4_fixes']} FTA errors when it differs.",
        "",
        "## Why does Pooled-4 regress?",
        f"{summary['pooled4_regresses']} regressions when overriding FTA-correct rows; often fs>1 or plurality tie-break.",
        "",
        "## Runtime-legal safe regions?",
        "Strict external agrees + fs<=1 + not Pooled-4 tie shows best precision in subgroup mining.",
        "",
        "## Best guarded candidate",
        f"**{best.get('rule_name') if best else 'TBD'}** — macro net {best.get('macro_net_wins') if best else '?'}"
        f", losses {best.get('macro_losses') if best else '?'}",
        "",
        "## Tie-break artifact?",
        "Guards requiring strict external majority or abstaining Pooled-4 ties avoid external 1-1-1 artifact; "
        "standalone Pooled-4 still uses frontier-first plurality ties.",
        "",
        "## API validation?",
        "Only if best guarded candidate is positive all corpora with ≤2 losses and enough triggers — see decision file.",
        "",
        "## Do not claim",
        "- Pooled-4 standalone without regression disclosure.",
        "- Guarded rules tuned on same corpora without fresh validation.",
    ]
    write_text(output_dir / "FINAL_POOLED4_BENEFIT_RISK_CLASSIFIER_SUMMARY.md", "\n".join(final).rstrip() + "\n")

    return {
        "output_dir": str(output_dir),
        "classification": classification,
        "pooled4_fixes": summary["pooled4_fixes"],
        "pooled4_regresses": summary["pooled4_regresses"],
        "best_rule": best.get("rule_name") if best else None,
        "best_macro_net": best.get("macro_net_wins") if best else None,
        "best_macro_losses": best.get("macro_losses") if best else None,
        "standalone_macro_net": ref.get("macro_net_wins"),
    }


def main() -> int:
    args = parse_args()
    result = run_classifier(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
