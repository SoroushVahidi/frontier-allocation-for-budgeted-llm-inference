"""Offline pattern discovery -> root-cause hypothesis -> repair-candidate pipeline.

This script is diagnostic infrastructure only. It builds a richer offline
"pattern feature table" over the canonical Aggregate-720 failure/branch data
plus the frontier-miss drilldown, mines association rules and small
interpretable models to find runtime-visible correlates of failure/recovery,
clusters failure text for qualitative themes, generates template-based
root-cause hypotheses, and replays a small catalog of repair candidates
offline. Nothing here is promoted; FTA / FIX-2+FIX-4
(`experiments/support_aware_selector.py`) remains the sole canonical
selector.

Guardrails (AGENTS.md / docs/CLAIMS.md / docs/FAILURE_FEATURE_TABLE.md):

- No paid API calls; only cached local artifacts are read.
- FTA/FIX-2+FIX-4 selector logic is never modified.
- Gold-derived and tree-signal fields (gold_answer*, gold_in_tree,
  gold_in_final_nodes, gold_in_direct_reserve_attempts, any correctness
  field, frontier_miss_subtype, and every diagnostic label derived from
  them) are OFFLINE_DIAGNOSTIC_LABELS / FORBIDDEN_DECISION_FEATURES: they
  may be used as targets/outcomes for offline mining, and inside
  diagnostic-only models explicitly labeled as such, but never as an
  antecedent/feature of a runtime rule candidate.
- Every repair candidate is exploratory; none is promoted.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier, export_text

from experiments.drilldown_frontier_allocation_misses import (
    TARGET_FAILURE_CLASS,
    build_drilldown_table,
    join_rows,
)
from experiments.explore_offline_selector_rules import RuleSpec, build_split_diagnostics
from experiments.failure_analysis_common import (
    as_bool,
    as_int,
    load_feature_rows,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)
from experiments.stress_test_exploratory_rules import (
    ILLEGAL_FIELD_BLOCKLIST,
    PRIMARY_RULE_NAME,
    PRIMARY_RULE_OVERRIDE_REASON,
    audit_rule_decision_legality,
    decision_canonical_fta,
    decision_external3_majority,
    decision_majority_with_agree_gate,
    decision_pooled4_majority,
    evaluate_rule_full,
    paired_bootstrap_ci,
)

warnings.filterwarnings("ignore", category=ConvergenceWarning)

HARD_FAILURE_CLASS = "hard_all_methods_wrong_or_pool_miss"

EXPECTED_CANONICAL = {
    "rows_written": 720,
    "fta_correct_count": 581,
    "effective_fix2_action": 122,
    "effective_fix4_action": 5,
    "no_effective_gate_action": 593,
}

# ---------------------------------------------------------------------------
# Feature legality bookkeeping (Part A requirement: clearly separate the three)
# ---------------------------------------------------------------------------

RUNTIME_DECISION_FEATURES = (
    "frontier_support",
    "candidate_pool_answer_group_count",
    "override_reason",
    "direct_frontier_agree",
    "effective_policy_label",
    "frontier_matches_external_count",
    "external_majority_count",
    "external_answers_unanimous",
    "external_unanimous_against_frontier",
    "two_of_three_external_against_frontier",
    "answer_group_count",
    "largest_answer_group_size",
    "selected_matches_external_majority",
    "selected_matches_external_unanimity",
    "frontier_answer_shape",
    "fta_selected_answer_shape",
    "l1_answer_shape",
    "s1_answer_shape",
    "tale_answer_shape",
    "frontier_answer_length",
    "fta_selected_answer_length",
    "source_id",
    "seed",
    "branch_answer_group_count",
    "final_nodes_count",
    "direct_reserve_attempts_count",
    "max_branch_depth",
)

OFFLINE_DIAGNOSTIC_LABELS = (
    "fta_correct",
    "frontier_correct",
    "l1_correct",
    "s1_correct",
    "tale_correct",
    "any_candidate_correct",
    "any_external_correct",
    "correct_in_candidate_pool",
    "gold_answer_canonical",
    "gold_in_tree",
    "gold_in_final_nodes",
    "gold_in_direct_reserve_attempts",
    "any_tree_signal_for_gold",
    "failure_class_coarse",
    "frontier_miss_subtype",
    "fta_success",
    "frontier_allocation_miss",
    "hard_all_methods_wrong_or_pool_miss",
    "recoverable_by_external_majority",
    "recoverable_by_external_unanimity",
    "risky_majority_override_regression",
    "hidden_tree_selection_failure",
    "parser_or_normalization_suspect",
)

FORBIDDEN_DECISION_FEATURES = tuple(sorted(ILLEGAL_FIELD_BLOCKLIST | set(OFFLINE_DIAGNOSTIC_LABELS)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-table", default=None)
    parser.add_argument("--branch-diagnostics", default=None)
    parser.add_argument("--drilldown-dir", default=None)
    parser.add_argument("--normalization-mismatches", default=None)
    parser.add_argument("--output-dir", required=True, help="Non-destructive output directory.")
    parser.add_argument("--bootstrap-resamples", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=1234)
    parser.add_argument("--random-state", type=int, default=0)
    return parser.parse_args()


def _latest_overnight_dir() -> Path:
    root = Path("outputs/failure_analysis")
    candidates = sorted(p for p in root.glob("overnight_*") if p.is_dir())
    if not candidates:
        raise FileNotFoundError("no outputs/failure_analysis/overnight_* directory found")
    return candidates[-1]


def _latest_dir(pattern: str) -> Path | None:
    root = Path("outputs/failure_analysis")
    candidates = sorted(p for p in root.glob(pattern) if p.is_dir())
    return candidates[-1] if candidates else None


def resolve_input_paths(args: argparse.Namespace) -> dict[str, Path | None]:
    if args.feature_table and args.branch_diagnostics:
        feature_table = Path(args.feature_table)
        branch_diagnostics = Path(args.branch_diagnostics)
        overnight_dir = None
    else:
        overnight_dir = _latest_overnight_dir()
        feature_table = Path(args.feature_table) if args.feature_table else (
            overnight_dir / "canonical_feature_table" / "failure_feature_table.jsonl"
        )
        branch_diagnostics = Path(args.branch_diagnostics) if args.branch_diagnostics else (
            overnight_dir / "branch_diagnostics" / "branch_diagnostics_table.jsonl"
        )
    drilldown_dir = Path(args.drilldown_dir) if args.drilldown_dir else _latest_dir("frontier_miss_drilldown_*")
    normalization_path = Path(args.normalization_mismatches) if args.normalization_mismatches else (
        (overnight_dir / "normalization_audit" / "normalization_mismatches.csv") if overnight_dir else None
    )
    return {
        "feature_table": feature_table,
        "branch_diagnostics": branch_diagnostics,
        "drilldown_dir": drilldown_dir,
        "normalization_mismatches": normalization_path if normalization_path and normalization_path.exists() else None,
    }


# ---------------------------------------------------------------------------
# Part A: pattern feature table
# ---------------------------------------------------------------------------

_ORDINAL_RE = re.compile(r"\b\d+(st|nd|rd|th)\b", re.IGNORECASE)
_FRACTION_RE = re.compile(r"^-?\d+\s*/\s*\d+$")
_EXPRESSION_RE = re.compile(r"[+*=]")
_UNIT_RE = re.compile(r"\d+\s*[a-zA-Z]+\b")
_TIME_RE = re.compile(r"\d+\s*:\s*\d+")
_PLAIN_NUMERIC_RE = re.compile(r"^-?[\d,]+(\.\d+)?$")


def classify_answer_shape(raw: Any) -> str:
    """Classify a raw candidate-answer string into a coarse shape bucket.

    Categories: empty, percent, currency, ordinal, fraction, expression, unit,
    integer (also covers plain decimals -- there is no separate "decimal"
    bucket in the requested taxonomy, and GSM8K answers that are just a
    decimal-formatted number, e.g. "3.00", are not a distinct data-quality
    signal the way a unit/expression/ordinal suffix is), unknown.
    Order matters: checks run most-specific-first.
    """
    if raw in (None, ""):
        return "empty"
    text = str(raw).strip()
    if not text:
        return "empty"
    if "%" in text:
        return "percent"
    if any(sym in text for sym in ("$", "€", "£")):
        return "currency"
    if _ORDINAL_RE.search(text):
        return "ordinal"
    if _FRACTION_RE.match(text):
        return "fraction"
    if _EXPRESSION_RE.search(text):
        return "expression"
    if _TIME_RE.search(text) or _UNIT_RE.search(text):
        return "unit"
    if _PLAIN_NUMERIC_RE.match(text):
        return "integer"
    return "unknown"


def load_normalization_suspect_row_ids(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    import csv

    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("row_id"):
                ids.add(str(row["row_id"]))
    return ids


def _largest_group_size(sizes: Any) -> int:
    if isinstance(sizes, str):
        try:
            sizes = json.loads(sizes)
        except json.JSONDecodeError:
            sizes = {}
    if not isinstance(sizes, dict) or not sizes:
        return 0
    return max(int(v) for v in sizes.values())


def build_pattern_row(
    row: dict[str, Any],
    *,
    subtype: str | None,
    normalization_suspect_ids: set[str],
) -> dict[str, Any]:
    row_id = str(row.get("row_id"))
    external_majority_count = as_int(row.get("external_majority_count")) or 0
    external_majority_answer = row.get("external_majority_answer")
    normalized_gold = row.get("normalized_gold_answer")
    external_majority_matches_gold = bool(
        external_majority_answer not in (None, "")
        and normalized_gold not in (None, "")
        and str(external_majority_answer) == str(normalized_gold)
    )
    fta_selected_norm = row.get("normalized_fta_selected_answer")
    selected_matches_external_majority = bool(
        external_majority_count >= 2
        and fta_selected_norm not in (None, "")
        and str(fta_selected_norm) == str(external_majority_answer)
    )
    selected_matches_external_unanimity = bool(
        as_bool(row.get("external_answers_unanimous"))
        and fta_selected_norm not in (None, "")
        and str(fta_selected_norm) == str(external_majority_answer)
    )
    frontier_norm = row.get("normalized_frontier_answer")
    frontier_matches_external_count = sum(
        1
        for key in ("normalized_l1_answer", "normalized_s1_answer", "normalized_tale_answer")
        if row.get(key) not in (None, "") and frontier_norm not in (None, "") and str(row.get(key)) == str(frontier_norm)
    )

    failure_class = str(row.get("failure_class_coarse"))
    fta_success = as_bool(row.get("fta_correct"))
    is_frontier_allocation_miss = failure_class == TARGET_FAILURE_CLASS
    is_hard_failure = failure_class == HARD_FAILURE_CLASS

    two_of_three_against_frontier = as_bool(row.get("two_of_three_external_against_frontier"))
    risky_majority_override_regression = bool(
        two_of_three_against_frontier and fta_success and not external_majority_matches_gold
    )

    recoverable_by_external_majority = subtype == "gold_in_external_majority"
    recoverable_by_external_unanimity = subtype == "gold_in_external_unanimity"
    hidden_tree_selection_failure = subtype == "gold_in_tree_only_not_external"

    pattern_row: dict[str, Any] = {
        "row_id": row_id,
        "example_id": row.get("example_id"),
        "source_id": row.get("source_id"),
        "seed": as_int(row.get("seed")),
        "problem_text": row.get("problem_text"),
        # runtime-visible features
        "frontier_support": as_int(row.get("frontier_support")),
        "candidate_pool_answer_group_count": as_int(row.get("candidate_pool_answer_group_count")),
        "override_reason": row.get("override_reason"),
        "direct_frontier_agree": as_bool(row.get("direct_frontier_agree")),
        "effective_policy_label": row.get("effective_policy_label"),
        "frontier_matches_external_count": frontier_matches_external_count,
        "external_majority_count": external_majority_count,
        "external_majority_answer": external_majority_answer,
        "external_answers_unanimous": as_bool(row.get("external_answers_unanimous")),
        "external_unanimous_against_frontier": as_bool(row.get("external_unanimous_against_frontier")),
        "two_of_three_external_against_frontier": two_of_three_against_frontier,
        "answer_group_count": as_int(row.get("answer_group_count")) or 0,
        "largest_answer_group_size": _largest_group_size(row.get("answer_group_sizes")),
        "selected_matches_external_majority": selected_matches_external_majority,
        "selected_matches_external_unanimity": selected_matches_external_unanimity,
        "frontier_matches_any_external": as_bool(row.get("frontier_matches_any_external")),
        "branch_answer_group_count": as_int(row.get("branch_answer_group_count")),
        "final_nodes_count": as_int(row.get("final_nodes_count")),
        "direct_reserve_attempts_count": as_int(row.get("direct_reserve_attempts_count")),
        "max_branch_depth": as_int(row.get("max_branch_depth")),
        # answer-shape / length features (runtime-visible: computed from the
        # candidate answers themselves, not from gold)
        "frontier_answer_shape": classify_answer_shape(row.get("frontier_answer")),
        "l1_answer_shape": classify_answer_shape(row.get("l1_answer")),
        "s1_answer_shape": classify_answer_shape(row.get("s1_answer")),
        "tale_answer_shape": classify_answer_shape(row.get("tale_answer")),
        "fta_selected_answer_shape": classify_answer_shape(row.get("fta_selected_answer")),
        "frontier_answer_length": len(str(row.get("frontier_answer"))) if row.get("frontier_answer") not in (None, "") else 0,
        "fta_selected_answer_length": (
            len(str(row.get("fta_selected_answer"))) if row.get("fta_selected_answer") not in (None, "") else 0
        ),
        # offline diagnostic labels ONLY below this line -- never usable as a
        # runtime decision feature (see FORBIDDEN_DECISION_FEATURES)
        "fta_correct": fta_success,
        "frontier_correct": as_bool(row.get("frontier_correct")),
        "gold_answer_canonical": row.get("gold_answer_canonical"),
        "gold_in_tree": as_bool(row.get("gold_in_tree")),
        "gold_in_final_nodes": as_bool(row.get("gold_in_final_nodes")),
        "gold_in_direct_reserve_attempts": as_bool(row.get("gold_in_direct_reserve_attempts")),
        "any_tree_signal_for_gold": as_bool(row.get("any_tree_signal_for_gold")),
        "failure_class_coarse": failure_class,
        "frontier_miss_subtype": subtype,
        "fta_success": fta_success,
        "frontier_allocation_miss": is_frontier_allocation_miss,
        "hard_all_methods_wrong_or_pool_miss": is_hard_failure,
        "recoverable_by_external_majority": recoverable_by_external_majority,
        "recoverable_by_external_unanimity": recoverable_by_external_unanimity,
        "risky_majority_override_regression": risky_majority_override_regression,
        "hidden_tree_selection_failure": hidden_tree_selection_failure,
        "parser_or_normalization_suspect": row_id in normalization_suspect_ids,
        # carried through for scoring / replay (needed downstream, not a
        # mining feature itself)
        "fta_selected_answer_canonical": row.get("fta_selected_answer_canonical"),
        "frontier_answer_canonical": row.get("frontier_answer_canonical"),
        "l1_answer_canonical": row.get("l1_answer_canonical"),
        "s1_answer_canonical": row.get("s1_answer_canonical"),
        "tale_answer_canonical": row.get("tale_answer_canonical"),
        "effective_fix2_action": as_bool(row.get("effective_fix2_action")),
        "effective_fix4_action": as_bool(row.get("effective_fix4_action")),
        "no_effective_gate_action": as_bool(row.get("no_effective_gate_action")),
    }
    return pattern_row


def build_pattern_table(
    all_rows: list[dict[str, Any]],
    *,
    normalization_suspect_ids: set[str],
) -> list[dict[str, Any]]:
    drilldown_rows = build_drilldown_table(all_rows)
    subtype_by_row_id = {str(r["row_id"]): r["frontier_miss_subtype"] for r in drilldown_rows}
    pattern_rows = [
        build_pattern_row(
            row,
            subtype=subtype_by_row_id.get(str(row.get("row_id"))),
            normalization_suspect_ids=normalization_suspect_ids,
        )
        for row in sorted(all_rows, key=lambda r: str(r.get("row_id")))
    ]
    return pattern_rows


def canonical_count_check(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    actual = {
        "rows_written": len(all_rows),
        "fta_correct_count": sum(as_bool(r.get("fta_correct")) for r in all_rows),
        "effective_fix2_action": sum(as_bool(r.get("effective_fix2_action")) for r in all_rows),
        "effective_fix4_action": sum(as_bool(r.get("effective_fix4_action")) for r in all_rows),
        "no_effective_gate_action": sum(as_bool(r.get("no_effective_gate_action")) for r in all_rows),
    }
    mismatches = [f"{k}: expected {v}, got {actual[k]}" for k, v in EXPECTED_CANONICAL.items() if actual[k] != v]
    return {"expected": EXPECTED_CANONICAL, "actual": actual, "matches_expected": not mismatches, "mismatches": mismatches}


# ---------------------------------------------------------------------------
# Part B: association rule mining (custom miner; mlxtend not installed)
# ---------------------------------------------------------------------------

TARGET_DEFINITIONS: list[tuple[str, str, Callable[[dict[str, Any]], bool], str | None]] = [
    ("frontier_allocation_miss", "frontier_allocation_miss", lambda r: bool(r["frontier_allocation_miss"]), None),
    (
        "recoverable_by_external_majority",
        "recoverable_by_external_majority",
        lambda r: bool(r["recoverable_by_external_majority"]),
        None,
    ),
    (
        "risky_majority_override_regression",
        "risky_majority_override_regression",
        lambda r: bool(r["risky_majority_override_regression"]),
        None,
    ),
    (
        "hidden_tree_selection_failure",
        "hidden_tree_selection_failure",
        lambda r: bool(r["hidden_tree_selection_failure"]),
        None,
    ),
    (
        "hard_all_methods_wrong_or_pool_miss",
        "hard_all_methods_wrong_or_pool_miss",
        lambda r: bool(r["hard_all_methods_wrong_or_pool_miss"]),
        None,
    ),
    (
        "fta_success_under_effective_fix2_action",
        "fta_success",
        lambda r: bool(r["fta_success"]),
        "effective_fix2_action",
    ),
    (
        "fta_success_under_no_effective_gate_action",
        "fta_success",
        lambda r: bool(r["fta_success"]),
        "no_effective_gate_action",
    ),
]


def build_item_index(pattern_rows: list[dict[str, Any]]) -> dict[str, set[int]]:
    """Map each runtime-visible categorical/binary "item" to the set of row indices where it holds."""
    items: dict[str, set[int]] = defaultdict(set)
    for idx, row in enumerate(pattern_rows):
        if row["override_reason"] not in (None, ""):
            items[f"override_reason={row['override_reason']}"].add(idx)
        fs = row["frontier_support"]
        if fs is not None:
            items[f"frontier_support={fs}" if fs <= 2 else "frontier_support_ge_3"].add(idx)
        cpc = row["candidate_pool_answer_group_count"]
        if cpc is not None:
            items[f"cpc={cpc}" if cpc <= 2 else "cpc_ge_3"].add(idx)
        items[f"direct_frontier_agree={row['direct_frontier_agree']}"].add(idx)
        emc = row["external_majority_count"]
        items[f"external_majority_count={emc}"].add(idx)
        items[f"external_answers_unanimous={row['external_answers_unanimous']}"].add(idx)
        items[f"external_unanimous_against_frontier={row['external_unanimous_against_frontier']}"].add(idx)
        items[f"two_of_three_external_against_frontier={row['two_of_three_external_against_frontier']}"].add(idx)
        agc = row["answer_group_count"]
        items[f"answer_group_count={agc}" if agc <= 3 else "answer_group_count_ge_4"].add(idx)
        items[f"effective_policy_label={row['effective_policy_label']}"].add(idx)
    return dict(items)


def _itemset_indices(item_index: dict[str, set[int]], itemset: tuple[str, ...]) -> set[int]:
    result = item_index[itemset[0]]
    for item in itemset[1:]:
        result = result & item_index[item]
    return result


def mine_association_rules(
    pattern_rows: list[dict[str, Any]],
    item_index: dict[str, set[int]],
    *,
    target_name: str,
    target_fn: Callable[[dict[str, Any]], bool],
    universe_filter: str | None = None,
    min_support_count: int = 5,
    min_confidence: float = 0.4,
    min_lift: float = 1.15,
    max_itemset_size: int = 3,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    if universe_filter is not None:
        universe = {idx for idx, row in enumerate(pattern_rows) if row.get(universe_filter)}
    else:
        universe = set(range(len(pattern_rows)))
    if not universe:
        return []

    scoped_items = {name: idxs & universe for name, idxs in item_index.items()}
    scoped_items = {name: idxs for name, idxs in scoped_items.items() if len(idxs) >= min_support_count}

    target_indices = {idx for idx in universe if target_fn(pattern_rows[idx])}
    base_rate = len(target_indices) / len(universe)
    if base_rate == 0:
        return []

    results: list[dict[str, Any]] = []
    item_names = sorted(scoped_items)
    for size in range(1, max_itemset_size + 1):
        for combo in itertools.combinations(item_names, size):
            idxs = scoped_items[combo[0]]
            for name in combo[1:]:
                idxs = idxs & scoped_items[name]
                if len(idxs) < min_support_count:
                    break
            support_count = len(idxs)
            if support_count < min_support_count:
                continue
            hit = idxs & target_indices
            confidence = len(hit) / support_count
            if confidence < min_confidence:
                continue
            lift = confidence / base_rate
            if lift < min_lift:
                continue
            source_breakdown = Counter(str(pattern_rows[i]["source_id"]) for i in idxs)
            source_hit_breakdown = Counter(str(pattern_rows[i]["source_id"]) for i in hit)
            sources_with_support = [s for s, n in source_breakdown.items() if n >= 2]
            stable_across_sources = len(sources_with_support) >= 2
            examples = sorted(str(pattern_rows[i]["row_id"]) for i in list(hit)[:5])
            results.append(
                {
                    "target": target_name,
                    "universe_filter": universe_filter or "all_rows",
                    "itemset": " & ".join(combo),
                    "itemset_size": size,
                    "support_count": support_count,
                    "support": round(support_count / len(universe), 6),
                    "confidence": round(confidence, 6),
                    "lift": round(lift, 6),
                    "base_rate": round(base_rate, 6),
                    "hit_count": len(hit),
                    "source_breakdown": dict(source_breakdown),
                    "source_hit_breakdown": dict(source_hit_breakdown),
                    "stable_across_sources": stable_across_sources,
                    "runtime_visible_only": True,
                    "example_row_ids": examples,
                }
            )
    # Prune redundant supersets: if a larger itemset has identical
    # (support_count, hit_count) to a smaller one, it adds no signal beyond
    # the smaller ("closed itemset") condition -- keep only the smallest.
    by_stats: dict[tuple[int, int], dict[str, Any]] = {}
    for r in results:
        key = (r["support_count"], r["hit_count"])
        current = by_stats.get(key)
        if current is None or r["itemset_size"] < current["itemset_size"]:
            by_stats[key] = r
    deduped = list(by_stats.values())
    deduped.sort(key=lambda r: (-r["lift"], -r["confidence"], -r["support_count"]))
    return deduped[:top_n]


def run_all_association_mining(pattern_rows: list[dict[str, Any]], item_index: dict[str, set[int]]) -> list[dict[str, Any]]:
    all_rules: list[dict[str, Any]] = []
    for rule_id, target_name, target_fn, universe_filter in TARGET_DEFINITIONS:
        rules = mine_association_rules(
            pattern_rows,
            item_index,
            target_name=target_name,
            target_fn=target_fn,
            universe_filter=universe_filter,
        )
        for r in rules:
            r["target_definition_id"] = rule_id
        all_rules.extend(rules)
    return all_rules


# ---------------------------------------------------------------------------
# Part C: interpretable model mining (small DT + LR only)
# ---------------------------------------------------------------------------

NUMERIC_MODEL_FEATURES = (
    "frontier_support",
    "candidate_pool_answer_group_count",
    "external_majority_count",
    "answer_group_count",
    "largest_answer_group_size",
    "frontier_matches_external_count",
    "branch_answer_group_count",
    "final_nodes_count",
    "direct_reserve_attempts_count",
    "max_branch_depth",
)
BOOLEAN_MODEL_FEATURES = (
    "direct_frontier_agree",
    "external_answers_unanimous",
    "external_unanimous_against_frontier",
    "two_of_three_external_against_frontier",
    "frontier_matches_any_external",
    "selected_matches_external_majority",
    "selected_matches_external_unanimity",
)
CATEGORICAL_MODEL_FEATURES = ("override_reason", "effective_policy_label")


def build_feature_matrix(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    numeric = df[list(NUMERIC_MODEL_FEATURES)].apply(pd.to_numeric, errors="coerce").fillna(-1)
    boolean = df[list(BOOLEAN_MODEL_FEATURES)].fillna(False).astype(int)
    categorical = pd.get_dummies(df[list(CATEGORICAL_MODEL_FEATURES)].fillna("none"), prefix=CATEGORICAL_MODEL_FEATURES)
    return pd.concat([numeric, boolean, categorical], axis=1)


def _safe_binary_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    n = len(y_true)
    accuracy = (tp + tn) / n if n else None
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    return {"n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn, "accuracy": accuracy, "precision": precision, "recall": recall}


def run_interpretable_task(
    rows_subset: list[dict[str, Any]],
    *,
    task_name: str,
    label_fn: Callable[[dict[str, Any]], bool | None],
    random_state: int = 0,
) -> list[dict[str, Any]]:
    labeled = []
    for row in rows_subset:
        label = label_fn(row)
        if label is None:
            continue
        labeled.append((row, bool(label)))
    if len(labeled) < 10 or len({label for _, label in labeled}) < 2:
        return [
            {
                "task_name": task_name,
                "model_type": "none",
                "status": "skipped_insufficient_data_or_single_class",
                "row_count": len(labeled),
            }
        ]

    rows_only = [r for r, _ in labeled]
    y = np.array([1 if label else 0 for _, label in labeled])
    X = build_feature_matrix(rows_only)
    feature_names = list(X.columns)
    sources = np.array([str(r["source_id"]) for r in rows_only])
    row_ids = np.array([str(r["row_id"]) for r in rows_only])

    results: list[dict[str, Any]] = []
    model_specs: list[tuple[str, Any]] = [
        ("decision_tree_depth2", DecisionTreeClassifier(max_depth=2, random_state=random_state)),
        ("decision_tree_depth3", DecisionTreeClassifier(max_depth=3, random_state=random_state)),
        ("decision_tree_depth4", DecisionTreeClassifier(max_depth=4, random_state=random_state)),
        ("logistic_regression", LogisticRegression(max_iter=2000, random_state=random_state)),
    ]

    for model_name, model in model_specs:
        full_model = model.__class__(**model.get_params())
        full_model.fit(X.values, y)
        if hasattr(full_model, "feature_importances_"):
            importances = dict(sorted(zip(feature_names, full_model.feature_importances_.tolist()), key=lambda kv: -kv[1])[:8])
            extracted_rules = export_text(full_model, feature_names=feature_names)
        else:
            coefs = full_model.coef_[0].tolist()
            importances = dict(sorted(zip(feature_names, coefs), key=lambda kv: -abs(kv[1]))[:8])
            extracted_rules = "logistic_regression coefficients: " + json.dumps(
                {k: round(v, 4) for k, v in importances.items()}
            )

        source_ids = sorted(set(sources))
        loso_metrics = []
        fp_examples: list[str] = []
        fn_examples: list[str] = []
        for holdout in source_ids:
            train_mask = sources != holdout
            test_mask = sources == holdout
            if train_mask.sum() == 0 or test_mask.sum() == 0:
                continue
            if len(set(y[train_mask].tolist())) < 2:
                loso_metrics.append({"holdout_source": holdout, "status": "skipped_single_class_in_train"})
                continue
            fold_model = model.__class__(**model.get_params())
            fold_model.fit(X.values[train_mask], y[train_mask])
            y_pred = fold_model.predict(X.values[test_mask])
            metrics = _safe_binary_metrics(y[test_mask], y_pred)
            metrics["holdout_source"] = holdout
            loso_metrics.append(metrics)
            test_row_ids = row_ids[test_mask]
            y_test = y[test_mask]
            for rid, yt, yp in zip(test_row_ids, y_test, y_pred):
                if yt == 0 and yp == 1 and len(fp_examples) < 5:
                    fp_examples.append(str(rid))
                if yt == 1 and yp == 0 and len(fn_examples) < 5:
                    fn_examples.append(str(rid))

        fold_accuracies = [m["accuracy"] for m in loso_metrics if m.get("accuracy") is not None]
        if len(fold_accuracies) >= 2:
            spread = max(fold_accuracies) - min(fold_accuracies)
            robustness_verdict = "source_specific_or_unstable" if spread > 0.35 else "appears_robust_across_sources"
        else:
            robustness_verdict = "insufficient_folds_to_assess"

        results.append(
            {
                "task_name": task_name,
                "model_type": model_name,
                "status": "fit",
                "row_count": len(labeled),
                "positive_count": int(y.sum()),
                "feature_count": len(feature_names),
                "feature_importances": importances,
                "extracted_rules_text": extracted_rules,
                "loso_metrics": loso_metrics,
                "false_positive_examples": fp_examples,
                "false_negative_examples": fn_examples,
                "robustness_verdict": robustness_verdict,
                "uses_forbidden_features": False,
            }
        )
    return results


def run_all_interpretable_tasks(pattern_rows: list[dict[str, Any]], *, random_state: int = 0) -> list[dict[str, Any]]:
    all_results: list[dict[str, Any]] = []

    majority_eligible = [r for r in pattern_rows if r["two_of_three_external_against_frontier"]]

    def _c1_label(row: dict[str, Any]) -> bool | None:
        if row["risky_majority_override_regression"]:
            return True
        if not row["fta_correct"] and row["external_majority_answer"] not in (None, "") and str(
            row["external_majority_answer"]
        ) == str(row["gold_answer_canonical"]):
            return False  # a "safe"/beneficial override case
        return None

    all_results.extend(
        run_interpretable_task(
            majority_eligible, task_name="risky_vs_safe_majority_override", label_fn=_c1_label, random_state=random_state
        )
    )

    miss_rows = [r for r in pattern_rows if r["frontier_allocation_miss"]]

    def _c2_label(row: dict[str, Any]) -> bool | None:
        return row["frontier_miss_subtype"] in (
            "gold_in_external_unanimity",
            "gold_in_external_majority",
            "gold_in_tree_and_external",
        )

    all_results.extend(
        run_interpretable_task(
            miss_rows, task_name="recoverable_vs_nonrecoverable_miss", label_fn=_c2_label, random_state=random_state
        )
    )

    all_failure_rows = [r for r in pattern_rows if r["frontier_allocation_miss"] or r["hard_all_methods_wrong_or_pool_miss"]]

    def _c3_label(row: dict[str, Any]) -> bool | None:
        return row["hidden_tree_selection_failure"]

    all_results.extend(
        run_interpretable_task(
            all_failure_rows, task_name="hidden_tree_selection_vs_other_failures", label_fn=_c3_label, random_state=random_state
        )
    )

    def _c4_label(row: dict[str, Any]) -> bool | None:
        if row["hard_all_methods_wrong_or_pool_miss"]:
            return True
        if row["frontier_allocation_miss"]:
            return False
        return None

    all_results.extend(
        run_interpretable_task(
            all_failure_rows,
            task_name="hard_pool_miss_vs_selection_fixable_failure",
            label_fn=_c4_label,
            random_state=random_state,
        )
    )

    return all_results


# ---------------------------------------------------------------------------
# Part D: clustering fallback (TF-IDF + KMeans; no sentence-transformers/BERTopic/HDBSCAN/UMAP)
# ---------------------------------------------------------------------------


def build_cluster_text(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("problem_text") or ""),
        f"subtype {row.get('frontier_miss_subtype') or 'na'}",
        f"override_reason {row.get('override_reason') or 'na'}",
        f"frontier_shape {row.get('frontier_answer_shape')}",
        f"fta_shape {row.get('fta_selected_answer_shape')}",
        f"answer_groups {row.get('answer_group_count')}",
    ]
    return " ".join(parts)


def run_clustering(rows_subset: list[dict[str, Any]], *, group_name: str, random_state: int = 0) -> list[dict[str, Any]]:
    if len(rows_subset) < 4:
        return [
            {
                "group_name": group_name,
                "cluster_id": -1,
                "status": "skipped_too_few_rows",
                "size": len(rows_subset),
            }
        ]
    texts = [build_cluster_text(r) for r in rows_subset]
    n_clusters = max(2, min(5, len(rows_subset) // 5 or 2))
    vectorizer = TfidfVectorizer(max_features=200, stop_words="english", min_df=1)
    X = vectorizer.fit_transform(texts)
    terms = np.array(vectorizer.get_feature_names_out())
    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = km.fit_predict(X)

    clusters = []
    for cluster_id in range(n_clusters):
        members_idx = [i for i, lbl in enumerate(labels) if lbl == cluster_id]
        if not members_idx:
            continue
        members = [rows_subset[i] for i in members_idx]
        centroid = km.cluster_centers_[cluster_id]
        top_term_idx = centroid.argsort()[::-1][:8]
        top_terms = [t for t in terms[top_term_idx] if t]
        dominant_failure_class = Counter(m["failure_class_coarse"] for m in members).most_common(1)[0][0]
        dominant_subtype = Counter(m.get("frontier_miss_subtype") for m in members).most_common(1)[0][0]
        dominant_source = Counter(m["source_id"] for m in members).most_common(1)[0][0]
        dominant_override_reason = Counter(m.get("override_reason") for m in members).most_common(1)[0][0]
        recoverable_share = sum(
            1 for m in members if m.get("recoverable_by_external_majority") or m.get("recoverable_by_external_unanimity")
        ) / len(members)
        candidate_repair_applies = recoverable_share > 0.3 or dominant_subtype in (
            "gold_in_external_majority",
            "gold_in_external_unanimity",
        )
        hypothesis = (
            f"Cluster dominated by {dominant_failure_class} rows (subtype={dominant_subtype}) with "
            f"override_reason={dominant_override_reason}; top terms: {', '.join(top_terms[:5])}."
        )
        clusters.append(
            {
                "group_name": group_name,
                "cluster_id": cluster_id,
                "status": "ok",
                "size": len(members),
                "dominant_failure_class": dominant_failure_class,
                "dominant_subtype": dominant_subtype,
                "dominant_source": dominant_source,
                "dominant_override_reason": dominant_override_reason,
                "top_terms": top_terms,
                "representative_row_ids": [m["row_id"] for m in members[:5]],
                "recoverable_share": round(recoverable_share, 4),
                "candidate_repair_applies": candidate_repair_applies,
                "hypothesis": hypothesis,
            }
        )
    return clusters


def run_all_clustering(pattern_rows: list[dict[str, Any]], *, random_state: int = 0) -> list[dict[str, Any]]:
    groups = {
        "frontier_allocation_miss": [r for r in pattern_rows if r["frontier_allocation_miss"]],
        "hard_all_methods_wrong_or_pool_miss": [r for r in pattern_rows if r["hard_all_methods_wrong_or_pool_miss"]],
        "hidden_tree_selection_failure": [r for r in pattern_rows if r["hidden_tree_selection_failure"]],
        "parser_or_normalization_suspect": [r for r in pattern_rows if r["parser_or_normalization_suspect"]],
    }
    all_clusters: list[dict[str, Any]] = []
    for group_name, subset in groups.items():
        all_clusters.extend(run_clustering(subset, group_name=group_name, random_state=random_state))
    return all_clusters


# ---------------------------------------------------------------------------
# Part F: repair candidates (selector-only, replayed) + non-selector catalog
# ---------------------------------------------------------------------------


def decision_repair_primary_plus_unanimity_fallback(row: dict[str, Any]) -> str | None:
    primary = decision_majority_with_agree_gate(row, require_override_reason=PRIMARY_RULE_OVERRIDE_REASON)
    if primary is not None:
        return primary
    return decision_majority_with_agree_gate(row, unanimous_only=True)


def build_repair_rule_specs() -> list[RuleSpec]:
    return [
        RuleSpec(
            name="baseline_canonical_fta",
            family="baseline",
            description="Canonical FTA / FIX-2+FIX-4 (no additional override).",
            decision_fn=decision_canonical_fta,
        ),
        RuleSpec(
            name="baseline_external3_majority",
            family="baseline",
            description="Majority vote of L1/S1/TALE only.",
            decision_fn=decision_external3_majority,
        ),
        RuleSpec(
            name="baseline_pooled4_majority_reconstructed",
            family="baseline",
            description="Majority vote of frontier+L1/S1/TALE (offline reconstruction).",
            decision_fn=decision_pooled4_majority,
        ),
        RuleSpec(
            name=PRIMARY_RULE_NAME,
            family="repair_candidate",
            description="Primary exploratory rule from the drilldown (5 wins/0 losses on Aggregate-720).",
            decision_fn=lambda row: decision_majority_with_agree_gate(
                row, require_override_reason=PRIMARY_RULE_OVERRIDE_REASON
            ),
        ),
        RuleSpec(
            name="repair_primary_plus_unanimity_fallback",
            family="repair_candidate",
            description=(
                "Source-robust broadened variant: primary rule's override_reason gate, OR (if that "
                "does not fire) a full 3/3 external-unanimity override -- two independently-validated-"
                "safe signals combined."
            ),
            decision_fn=decision_repair_primary_plus_unanimity_fallback,
        ),
    ]


def replay_repair_candidates(
    all_rows: list[dict[str, Any]],
    specs: list[RuleSpec],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> dict[str, dict[str, Any]]:
    return {spec.name: evaluate_rule_full(all_rows, spec) for spec in specs}


def build_bootstrap_table(
    evaluations: dict[str, dict[str, Any]],
    *,
    n_resamples: int,
    seed: int,
) -> list[dict[str, Any]]:
    canonical = evaluations["baseline_canonical_fta"]
    rows = []
    for name in ("repair_primary_plus_unanimity_fallback",):
        ev = evaluations.get(name)
        if ev is None:
            continue
        result = paired_bootstrap_ci(ev["per_row"], canonical["per_row"], n_resamples=n_resamples, seed=seed, stratify_by_source=True)
        rows.append({"comparison_name": f"{name}_vs_canonical_fta", **result})
    return rows


def build_non_selector_repair_catalog(pattern_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hidden_rows = [r for r in pattern_rows if r["hidden_tree_selection_failure"]]
    normalization_rows = [r for r in pattern_rows if r["parser_or_normalization_suspect"]]
    hard_rows = [r for r in pattern_rows if r["hard_all_methods_wrong_or_pool_miss"]]
    high_risk_rows = [
        r
        for r in pattern_rows
        if r["two_of_three_external_against_frontier"] and r.get("override_reason") == "insufficient_support_margin"
    ]
    high_risk_regressions = sum(1 for r in high_risk_rows if r["risky_majority_override_regression"])

    return [
        {
            "candidate_id": "tree_propagation_surface_final_nodes",
            "candidate_type": "tree_propagation",
            "description": (
                "For rows where gold is present in final_nodes but not propagated to any reported "
                "method answer, expose the ranked final_nodes list to the selection layer and add a "
                "cross-check against external baselines before discarding non-selected final nodes."
            ),
            "estimated_affected_rows": len(hidden_rows),
            "estimated_affected_share_of_720": round(len(hidden_rows) / len(pattern_rows), 4),
            "implementation_needed": (
                "Selector-layer change to consult final_nodes (not just the single chosen frontier "
                "answer) when the frontier answer disagrees with all externals; requires access to the "
                "full final_nodes list at decision time, which the current runtime selector already "
                "has via result_metadata."
            ),
            "classification": "offline_replay_feasible_first; needs fresh generation only to validate beyond this corpus",
        },
        {
            "candidate_id": "normalization_patch_arithmetic_and_units",
            "candidate_type": "normalization",
            "description": (
                "Patch the canonical answer normalizer to more consistently handle arithmetic "
                "expressions with a trailing '= result', unit/time suffixes, and ordinal suffixes, "
                "per the categories already catalogued in the overnight normalization audit."
            ),
            "estimated_affected_rows": len(normalization_rows),
            "estimated_affected_share_of_720": round(len(normalization_rows) / len(pattern_rows), 4),
            "implementation_needed": (
                "Deterministic post-processing change in the shared normalization function plus "
                "regression tests over the flagged mismatches; not applied here per task constraints."
            ),
            "classification": "offline_only_fix (deterministic; no API validation required)",
        },
        {
            "candidate_id": "abstention_flag_insufficient_support_margin_majority",
            "candidate_type": "abstention",
            "description": (
                "Flag (do not auto-override) rows where a 2/3 external majority disagrees with the "
                "frontier AND override_reason == insufficient_support_margin for manual review -- this "
                "is the specific override_reason bucket shown to regress FTA-correct rows most often "
                "(see risky_majority_override_regression association rules)."
            ),
            "estimated_affected_rows": len(high_risk_rows),
            "estimated_affected_share_of_720": round(len(high_risk_rows) / len(pattern_rows), 4),
            "implementation_needed": (
                f"No selector change (answer unchanged, equivalent to canonical FTA); add a monitoring "
                f"flag on this subset. {high_risk_regressions}/{len(high_risk_rows)} of these rows would "
                "be regressions if an unconditional majority override were applied, making this a "
                "reasonable target for a review queue rather than an automatic decision."
            ),
            "classification": "offline_only (observability change, not a selector change)",
        },
        {
            "candidate_id": "generation_diversity_for_pool_miss",
            "candidate_type": "generation_diversity",
            "description": (
                "For hard_all_methods_wrong_or_pool_miss rows (gold absent from every candidate and "
                "from the tree), no selection-side repair can help; only wider search/generation "
                "diversity (more branches, higher budget, or a different prompting strategy) could "
                "surface a correct candidate at all."
            ),
            "estimated_affected_rows": len(hard_rows),
            "estimated_affected_share_of_720": round(len(hard_rows) / len(pattern_rows), 4),
            "implementation_needed": "New generation/search-side experiment, not a selector change.",
            "classification": "future_api_run_candidate (requires new model calls to test)",
        },
    ]


# ---------------------------------------------------------------------------
# Part E: root-cause hypotheses (template-based, no external LLM/API calls)
# ---------------------------------------------------------------------------


def render_root_cause_hypotheses(
    *,
    association_rules: list[dict[str, Any]],
    interpretable_results: list[dict[str, Any]],
    cluster_results: list[dict[str, Any]],
    pattern_summary: dict[str, Any],
) -> str:
    lines = [
        "# Root-Cause Hypotheses (Template-Based, Offline Only)",
        "",
        "No external LLM/API calls were used to generate this document. Each hypothesis is assembled "
        "mechanically from the association-rule, interpretable-model, and clustering outputs in this "
        "same run. All hypotheses are exploratory.",
        "",
    ]

    top_rules_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in association_rules:
        top_rules_by_target[r["target"]].append(r)

    for target_name, rules in top_rules_by_target.items():
        rules = sorted(rules, key=lambda r: -r["lift"])[:3]
        for rule in rules:
            lines.append(f"## Pattern: `{rule['itemset']}` -> `{target_name}`")
            lines.append("")
            lines.append("**Runtime-visible condition:** " + rule["itemset"])
            lines.append(
                f"**Affected rows:** {rule['support_count']} (support={rule['support']:.3f}, "
                f"confidence={rule['confidence']:.3f}, lift={rule['lift']:.2f})"
            )
            lines.append(
                f"**Source stability:** {'stable across >=2 sources' if rule['stable_across_sources'] else 'concentrated in one source'} "
                f"({rule['source_breakdown']})"
            )
            lines.append(f"**Representative cases:** {', '.join(rule['example_row_ids'][:3]) or 'none'}")
            lines.append("")
            reason = "selection failure"
            if "risky_majority" in target_name:
                reason = "unsafe majority-override region"
            elif "hidden_tree" in target_name:
                reason = "tree propagation failure"
            elif "hard_all_methods" in target_name:
                reason = "pool-miss/capability ceiling"
            elif "recoverable" in target_name:
                reason = "selection failure (correct answer visible but not chosen)"
            lines.append(f"**Possible reason:** {reason}")
            lines.append("")
            lines.append(
                f"**Evidence:** {rule['hit_count']} of {rule['support_count']} rows matching this condition "
                f"also satisfy `{target_name}` (base rate {rule['base_rate']:.3f} without the condition)."
            )
            lines.append("")
            if "risky_majority" in target_name:
                repair = "abstention/flagging policy for this override_reason region, or exclude it from any majority-override repair candidate"
            elif "hidden_tree" in target_name:
                repair = "tree-propagation repair (surface final_nodes to the selection layer)"
            elif "recoverable" in target_name:
                repair = "selector override rule gated on this exact condition (see repair_candidate_catalog.csv)"
            elif "hard_all_methods" in target_name:
                repair = "no selector-only repair available; generation/search diversity increase needed"
            else:
                repair = "candidate selector rule change, gated narrowly on this condition"
            lines.append(f"**Candidate repair:** {repair}")
            lines.append("")
            lines.append(
                f"**Risk:** small-sample ({rule['support_count']} rows); "
                f"{'' if rule['stable_across_sources'] else 'not '}source-general; needs independent "
                "validation before any promotion; uses only runtime-visible fields "
                f"(runtime_visible_only={rule['runtime_visible_only']})."
            )
            lines.append("")

    lines.append("## Interpretable-model-derived hypotheses")
    lines.append("")
    for res in interpretable_results:
        if res.get("status") != "fit" or res.get("model_type") != "decision_tree_depth3":
            continue
        lines.append(f"### {res['task_name']} (decision tree, depth 3, fit on all available rows)")
        lines.append("")
        lines.append(f"**Row count:** {res['row_count']} (positive={res['positive_count']})")
        lines.append(f"**Robustness verdict:** {res['robustness_verdict']}")
        lines.append("")
        lines.append("**Extracted rule (human-readable):**")
        lines.append("```")
        lines.append(res["extracted_rules_text"].strip())
        lines.append("```")
        lines.append("")

    lines.append("## Cluster-derived hypotheses")
    lines.append("")
    for cluster in cluster_results:
        if cluster.get("status") != "ok":
            continue
        lines.append(
            f"### {cluster['group_name']} / cluster {cluster['cluster_id']} (n={cluster['size']})"
        )
        lines.append("")
        lines.append(f"**Hypothesis:** {cluster['hypothesis']}")
        lines.append(f"**Candidate repair applies:** {cluster['candidate_repair_applies']}")
        lines.append(f"**Representative cases:** {', '.join(cluster['representative_row_ids'])}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------


def render_pattern_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Pattern Feature Table Report",
        "",
        "Offline pattern feature table joining the canonical feature table, branch diagnostics, "
        "frontier-miss drilldown subtypes, and (if available) the normalization audit.",
        "",
        "## Canonical count check",
        "",
    ]
    check = summary["canonical_count_check"]
    for k, v in check["actual"].items():
        lines.append(f"- `{k}`: {v} (expected {check['expected'][k]})")
    lines.append(f"- matches_expected: {check['matches_expected']}")
    lines.extend(["", "## Diagnostic label counts", ""])
    for k, v in summary["label_counts"].items():
        lines.append(f"- `{k}`: {v}")
    lines.extend(["", "## Runtime decision features vs offline diagnostic labels vs forbidden features", ""])
    lines.append(f"- runtime_decision_features ({len(RUNTIME_DECISION_FEATURES)}): {', '.join(RUNTIME_DECISION_FEATURES)}")
    lines.append(f"- offline_diagnostic_labels ({len(OFFLINE_DIAGNOSTIC_LABELS)}): {', '.join(OFFLINE_DIAGNOSTIC_LABELS)}")
    lines.append(f"- forbidden_decision_features ({len(FORBIDDEN_DECISION_FEATURES)}): {', '.join(FORBIDDEN_DECISION_FEATURES)}")
    return "\n".join(lines).rstrip() + "\n"


def render_cluster_report(cluster_results: list[dict[str, Any]]) -> str:
    lines = ["# Cluster Report (TF-IDF + KMeans fallback)", "", "sentence-transformers/BERTopic/HDBSCAN/UMAP were not installed in this venv; falling back to TF-IDF + KMeans per the task's fallback instruction.", ""]
    for cluster in cluster_results:
        if cluster.get("status") != "ok":
            lines.append(f"## {cluster['group_name']}: {cluster.get('status')} (size={cluster.get('size')})")
            lines.append("")
            continue
        lines.append(f"## {cluster['group_name']} / cluster {cluster['cluster_id']}")
        lines.append("")
        lines.append(f"- size: {cluster['size']}")
        lines.append(f"- dominant_failure_class: {cluster['dominant_failure_class']}")
        lines.append(f"- dominant_subtype: {cluster['dominant_subtype']}")
        lines.append(f"- dominant_source: {cluster['dominant_source']}")
        lines.append(f"- dominant_override_reason: {cluster['dominant_override_reason']}")
        lines.append(f"- top_terms: {', '.join(cluster['top_terms'])}")
        lines.append(f"- recoverable_share: {cluster['recoverable_share']}")
        lines.append(f"- candidate_repair_applies: {cluster['candidate_repair_applies']}")
        lines.append(f"- representative_row_ids: {', '.join(cluster['representative_row_ids'])}")
        lines.append(f"- hypothesis: {cluster['hypothesis']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_repair_candidate_report(
    selector_evaluations: dict[str, dict[str, Any]],
    non_selector_catalog: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    split_rows: list[dict[str, Any]],
    bootstrap_rows: list[dict[str, Any]],
) -> str:
    lines = ["# Repair Candidate Report", "", "## Selector-only candidates (replayed offline on Aggregate-720)", ""]
    for name, ev in selector_evaluations.items():
        lines.append(
            f"- `{name}` ({ev['family']}): accuracy={ev['accuracy']:.4f}, wins={ev['wins_vs_canonical_fta']}, "
            f"losses={ev['losses_vs_canonical_fta']}, net_wins={ev['net_wins']}, "
            f"regression_rate_among_fta_correct={ev['regression_rate_among_fta_correct']}"
        )
    lines.extend(["", "## Decision legality audit", ""])
    for row in audit_rows:
        lines.append(f"- `{row['rule_name']}`: is_runtime_legal={row['is_runtime_legal']} (illegal_fields_found={row['illegal_fields_found'] or 'none'})")
    lines.extend(["", "## Leave-one-source-out (dev-tune-then-test across this candidate set only)", ""])
    for row in split_rows:
        lines.append(
            f"- `{row['split_name']}` -> `{row['selected_rule']}`: dev_acc={row['dev_accuracy']:.4f}, "
            f"test_acc={row['test_accuracy']:.4f}, test_net_wins={row['test_net_wins']}, unsafe={row['unsafe']}"
        )
    lines.extend(["", "## Bootstrap CIs", ""])
    for row in bootstrap_rows:
        lines.append(
            f"- `{row['comparison_name']}`: delta={row['observed_delta_accuracy']}, "
            f"95% CI=[{row['ci_low']}, {row['ci_high']}], includes_zero={row['includes_zero']}"
        )
    lines.extend(["", "## Non-selector repair candidates", ""])
    for cand in non_selector_catalog:
        lines.append(f"### {cand['candidate_id']} ({cand['candidate_type']})")
        lines.append("")
        lines.append(cand["description"])
        lines.append(
            f"- estimated_affected_rows: {cand['estimated_affected_rows']} "
            f"({cand['estimated_affected_share_of_720']:.2%} of 720)"
        )
        lines.append(f"- implementation_needed: {cand['implementation_needed']}")
        lines.append(f"- classification: {cand['classification']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_offline_repair_replay_report(selector_evaluations: dict[str, dict[str, Any]]) -> str:
    lines = ["# Offline Repair Replay Report", "", "Full Aggregate-720 replay of every selector-only repair candidate.", ""]
    for name, ev in selector_evaluations.items():
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"- accuracy: {ev['accuracy']}")
        lines.append(f"- correct_count: {ev['correct_count']}/{ev['row_count']}")
        lines.append(f"- wins_vs_canonical_fta: {ev['wins_vs_canonical_fta']}")
        lines.append(f"- losses_vs_canonical_fta: {ev['losses_vs_canonical_fta']}")
        lines.append(f"- net_wins: {ev['net_wins']}")
        lines.append(f"- overrides_triggered: {ev['overrides_triggered']}")
        lines.append(f"- regression_rate_among_fta_correct: {ev['regression_rate_among_fta_correct']}")
        lines.append("- per_source:")
        for source_id, item in ev["per_source"].items():
            lines.append(f"  - `{source_id}` (seed={item['seed']}): wins={item['wins']}, losses={item['losses']}, accuracy={item['accuracy']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_representative_failure_cases(pattern_rows: list[dict[str, Any]], *, limit: int = 5) -> str:
    lines = ["# Representative Failure Cases", ""]
    groups = [
        ("frontier_allocation_miss", lambda r: r["frontier_allocation_miss"]),
        ("hard_all_methods_wrong_or_pool_miss", lambda r: r["hard_all_methods_wrong_or_pool_miss"]),
        ("hidden_tree_selection_failure", lambda r: r["hidden_tree_selection_failure"]),
        ("risky_majority_override_regression", lambda r: r["risky_majority_override_regression"]),
        ("parser_or_normalization_suspect", lambda r: r["parser_or_normalization_suspect"]),
    ]
    for name, predicate in groups:
        subset = [r for r in pattern_rows if predicate(r)]
        lines.append(f"## {name} (n={len(subset)})")
        lines.append("")
        for r in subset[:limit]:
            lines.append(
                f"- {r['row_id']} | seed={r['seed']} | gold={r['gold_answer_canonical']} | "
                f"frontier={r['frontier_answer_canonical']} | fta_selected={r['fta_selected_answer_canonical']} | "
                f"override_reason={r['override_reason']} | frontier_support={r['frontier_support']} | "
                f"subtype={r['frontier_miss_subtype']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_pipeline(paths: dict[str, Path | None], *, bootstrap_resamples: int, bootstrap_seed: int, random_state: int) -> dict[str, Any]:
    feature_rows = load_feature_rows(paths["feature_table"])
    branch_rows = load_feature_rows(paths["branch_diagnostics"])
    all_rows, join_stats = join_rows(feature_rows, branch_rows)

    canonical_check = canonical_count_check(all_rows)
    normalization_suspect_ids = load_normalization_suspect_row_ids(paths["normalization_mismatches"])
    pattern_rows = build_pattern_table(all_rows, normalization_suspect_ids=normalization_suspect_ids)

    label_counts = {
        label: sum(1 for r in pattern_rows if r.get(label) is True)
        for label in (
            "fta_success",
            "frontier_allocation_miss",
            "hard_all_methods_wrong_or_pool_miss",
            "recoverable_by_external_majority",
            "recoverable_by_external_unanimity",
            "risky_majority_override_regression",
            "hidden_tree_selection_failure",
            "parser_or_normalization_suspect",
        )
    }

    item_index = build_item_index(pattern_rows)
    association_rules = run_all_association_mining(pattern_rows, item_index)

    interpretable_results = run_all_interpretable_tasks(pattern_rows, random_state=random_state)

    cluster_results = run_all_clustering(pattern_rows, random_state=random_state)

    repair_specs = build_repair_rule_specs()
    selector_evaluations = replay_repair_candidates(
        all_rows, repair_specs, bootstrap_resamples=bootstrap_resamples, bootstrap_seed=bootstrap_seed
    )
    audit_rows = audit_rule_decision_legality(repair_specs)
    split_rows = build_split_diagnostics(all_rows, repair_specs)
    bootstrap_rows = build_bootstrap_table(selector_evaluations, n_resamples=bootstrap_resamples, seed=bootstrap_seed)
    non_selector_catalog = build_non_selector_repair_catalog(pattern_rows)

    pattern_summary = {
        "join_stats": join_stats,
        "canonical_count_check": canonical_check,
        "row_count": len(pattern_rows),
        "label_counts": label_counts,
        "runtime_decision_features": list(RUNTIME_DECISION_FEATURES),
        "offline_diagnostic_labels": list(OFFLINE_DIAGNOSTIC_LABELS),
        "forbidden_decision_features": list(FORBIDDEN_DECISION_FEATURES),
        "association_rule_count": len(association_rules),
        "interpretable_model_count": len(interpretable_results),
        "cluster_count": len([c for c in cluster_results if c.get("status") == "ok"]),
    }

    return {
        "all_rows": all_rows,
        "pattern_rows": pattern_rows,
        "canonical_check": canonical_check,
        "association_rules": association_rules,
        "interpretable_results": interpretable_results,
        "cluster_results": cluster_results,
        "selector_evaluations": selector_evaluations,
        "audit_rows": audit_rows,
        "split_rows": split_rows,
        "bootstrap_rows": bootstrap_rows,
        "non_selector_catalog": non_selector_catalog,
        "pattern_summary": pattern_summary,
    }


PATTERN_CSV_FIELDS = [
    "row_id",
    "example_id",
    "source_id",
    "seed",
    "frontier_support",
    "candidate_pool_answer_group_count",
    "override_reason",
    "direct_frontier_agree",
    "effective_policy_label",
    "frontier_matches_external_count",
    "external_majority_count",
    "external_majority_answer",
    "external_answers_unanimous",
    "external_unanimous_against_frontier",
    "two_of_three_external_against_frontier",
    "answer_group_count",
    "largest_answer_group_size",
    "selected_matches_external_majority",
    "selected_matches_external_unanimity",
    "frontier_matches_any_external",
    "branch_answer_group_count",
    "final_nodes_count",
    "direct_reserve_attempts_count",
    "max_branch_depth",
    "frontier_answer_shape",
    "l1_answer_shape",
    "s1_answer_shape",
    "tale_answer_shape",
    "fta_selected_answer_shape",
    "frontier_answer_length",
    "fta_selected_answer_length",
    "fta_correct",
    "frontier_correct",
    "gold_in_tree",
    "gold_in_final_nodes",
    "gold_in_direct_reserve_attempts",
    "any_tree_signal_for_gold",
    "failure_class_coarse",
    "frontier_miss_subtype",
    "fta_success",
    "frontier_allocation_miss",
    "hard_all_methods_wrong_or_pool_miss",
    "recoverable_by_external_majority",
    "recoverable_by_external_unanimity",
    "risky_majority_override_regression",
    "hidden_tree_selection_failure",
    "parser_or_normalization_suspect",
]


def main() -> int:
    args = parse_args()
    paths = resolve_input_paths(args)
    result = run_pipeline(
        paths,
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
        random_state=args.random_state,
    )

    output_dir = Path(args.output_dir)

    csv_rows = [{k: row.get(k) for k in PATTERN_CSV_FIELDS} for row in result["pattern_rows"]]
    write_csv(output_dir / "pattern_feature_table.csv", csv_rows, PATTERN_CSV_FIELDS)
    write_jsonl(output_dir / "pattern_feature_table.jsonl", result["pattern_rows"])
    write_json(output_dir / "pattern_summary.json", result["pattern_summary"])
    write_text(output_dir / "pattern_report.md", render_pattern_report(result["pattern_summary"]))

    assoc_csv_rows = [
        {
            "target": r["target"],
            "target_definition_id": r["target_definition_id"],
            "universe_filter": r["universe_filter"],
            "itemset": r["itemset"],
            "itemset_size": r["itemset_size"],
            "support_count": r["support_count"],
            "support": r["support"],
            "confidence": r["confidence"],
            "lift": r["lift"],
            "base_rate": r["base_rate"],
            "hit_count": r["hit_count"],
            "stable_across_sources": r["stable_across_sources"],
            "runtime_visible_only": r["runtime_visible_only"],
            "source_breakdown": json.dumps(r["source_breakdown"], sort_keys=True),
            "example_row_ids": ";".join(r["example_row_ids"]),
        }
        for r in result["association_rules"]
    ]
    write_csv(
        output_dir / "association_rules.csv",
        assoc_csv_rows,
        list(assoc_csv_rows[0].keys()) if assoc_csv_rows else ["target"],
    )

    interp_csv_rows = []
    for r in result["interpretable_results"]:
        interp_csv_rows.append(
            {
                "task_name": r.get("task_name"),
                "model_type": r.get("model_type"),
                "status": r.get("status"),
                "row_count": r.get("row_count"),
                "positive_count": r.get("positive_count"),
                "feature_importances": json.dumps(r.get("feature_importances", {}), sort_keys=True),
                "extracted_rules_text": (r.get("extracted_rules_text") or "").replace("\n", " | "),
                "loso_metrics": json.dumps(r.get("loso_metrics", []), sort_keys=True),
                "false_positive_examples": ";".join(r.get("false_positive_examples", [])),
                "false_negative_examples": ";".join(r.get("false_negative_examples", [])),
                "robustness_verdict": r.get("robustness_verdict"),
                "uses_forbidden_features": r.get("uses_forbidden_features", False),
            }
        )
    write_csv(
        output_dir / "interpretable_rule_candidates.csv",
        interp_csv_rows,
        list(interp_csv_rows[0].keys()) if interp_csv_rows else ["task_name"],
    )

    cluster_csv_rows = [
        {
            "group_name": c.get("group_name"),
            "cluster_id": c.get("cluster_id"),
            "status": c.get("status"),
            "size": c.get("size"),
            "dominant_failure_class": c.get("dominant_failure_class"),
            "dominant_subtype": c.get("dominant_subtype"),
            "dominant_source": c.get("dominant_source"),
            "dominant_override_reason": c.get("dominant_override_reason"),
            "top_terms": ";".join(c.get("top_terms", [])) if c.get("top_terms") else "",
            "recoverable_share": c.get("recoverable_share"),
            "candidate_repair_applies": c.get("candidate_repair_applies"),
            "representative_row_ids": ";".join(c.get("representative_row_ids", [])) if c.get("representative_row_ids") else "",
        }
        for c in result["cluster_results"]
    ]
    write_csv(output_dir / "cluster_summary.csv", cluster_csv_rows, list(cluster_csv_rows[0].keys()))
    write_text(output_dir / "cluster_report.md", render_cluster_report(result["cluster_results"]))

    write_text(
        output_dir / "root_cause_hypotheses.md",
        render_root_cause_hypotheses(
            association_rules=result["association_rules"],
            interpretable_results=result["interpretable_results"],
            cluster_results=result["cluster_results"],
            pattern_summary=result["pattern_summary"],
        ),
    )

    repair_catalog_rows = []
    for name, ev in result["selector_evaluations"].items():
        repair_catalog_rows.append(
            {
                "candidate_id": name,
                "candidate_type": "selector" if ev["family"] != "baseline" else "baseline_reference",
                "description": ev["description"],
                "estimated_affected_rows": ev["overrides_triggered"],
                "estimated_affected_share_of_720": round(ev["overrides_triggered"] / ev["row_count"], 4),
                "implementation_needed": "n/a (already implemented as an offline decision_fn for replay)",
                "classification": "offline_replay_only; exploratory; not promoted",
            }
        )
    for cand in result["non_selector_catalog"]:
        repair_catalog_rows.append(
            {
                "candidate_id": cand["candidate_id"],
                "candidate_type": cand["candidate_type"],
                "description": cand["description"],
                "estimated_affected_rows": cand["estimated_affected_rows"],
                "estimated_affected_share_of_720": cand["estimated_affected_share_of_720"],
                "implementation_needed": cand["implementation_needed"],
                "classification": cand["classification"],
            }
        )
    write_csv(output_dir / "repair_candidate_catalog.csv", repair_catalog_rows, list(repair_catalog_rows[0].keys()))
    write_text(
        output_dir / "repair_candidate_report.md",
        render_repair_candidate_report(
            result["selector_evaluations"],
            result["non_selector_catalog"],
            result["audit_rows"],
            result["split_rows"],
            result["bootstrap_rows"],
        ),
    )

    replay_csv_rows = [
        {
            "rule_name": name,
            "family": ev["family"],
            "accuracy": ev["accuracy"],
            "correct_count": ev["correct_count"],
            "row_count": ev["row_count"],
            "wins_vs_canonical_fta": ev["wins_vs_canonical_fta"],
            "losses_vs_canonical_fta": ev["losses_vs_canonical_fta"],
            "net_wins": ev["net_wins"],
            "overrides_triggered": ev["overrides_triggered"],
            "regression_rate_among_fta_correct": ev["regression_rate_among_fta_correct"],
            "frontier_allocation_miss_wins": ev["frontier_allocation_miss_wins"],
            "fta_success_regressions": ev["fta_success_regressions"],
        }
        for name, ev in result["selector_evaluations"].items()
    ]
    write_csv(output_dir / "offline_repair_replay_results.csv", replay_csv_rows, list(replay_csv_rows[0].keys()))
    write_text(output_dir / "offline_repair_replay_report.md", render_offline_repair_replay_report(result["selector_evaluations"]))

    write_text(output_dir / "representative_failure_cases.md", render_representative_failure_cases(result["pattern_rows"]))

    print(
        json.dumps(
            {
                "feature_table": str(paths["feature_table"]),
                "branch_diagnostics": str(paths["branch_diagnostics"]),
                "drilldown_dir": str(paths["drilldown_dir"]) if paths["drilldown_dir"] else None,
                "normalization_mismatches": str(paths["normalization_mismatches"]) if paths["normalization_mismatches"] else None,
                "output_dir": str(output_dir),
                "canonical_counts_match": result["canonical_check"]["matches_expected"],
                "pattern_rows": len(result["pattern_rows"]),
                "association_rules": len(result["association_rules"]),
                "interpretable_results": len(result["interpretable_results"]),
                "clusters": len([c for c in result["cluster_results"] if c.get("status") == "ok"]),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
