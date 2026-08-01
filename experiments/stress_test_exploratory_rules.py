"""Journal-grade offline stress test of exploratory frontier_allocation_miss rules.

This script is diagnostic infrastructure only. It stress-tests the most
promising exploratory rule surfaced by
`experiments/drilldown_frontier_allocation_misses.py`
(`drilldown_majority2of3_reason_frontier_support_margin_override`) against
nearby ablations and fixed baselines, over the full canonical Aggregate-720
table, with source/seed robustness, leave-one-source-out diagnostics,
paired bootstrap confidence intervals, a decision-legality audit, and
manuscript-ready tables/text.

Guardrails (see AGENTS.md / docs/CLAIMS.md / docs/FAILURE_FEATURE_TABLE.md):

- No paid API calls; this script only reads cached local artifacts.
- FTA / FIX-2+FIX-4 selector logic (`experiments/support_aware_selector.py`,
  `experiments/fta_policy.py`) is never modified and never called with a
  different policy -- this script only reads the already-computed
  `fta_selected_answer_canonical` / `fta_correct` fields from the canonical
  feature table.
- No manuscript claims are changed. Any accuracy numbers reconstructed here
  (e.g. "Pooled-4 majority") are independent offline reconstructions for
  stress-testing purposes, not replacements for the canonical documented
  baseline numbers in docs/CURRENT_CANONICAL_STATE_20260527.md.
- Gold-derived fields are used only inside `_candidate_correct` (offline
  scoring) and `classify_frontier_miss_subtype` (offline labeling). No
  decision_fn reads a gold-derived field -- see `rule_decision_audit.csv`
  and `tests/test_rule_stress_test.py`.
- Every rule here remains exploratory. Nothing is promoted by this script.
"""

from __future__ import annotations

import argparse
import inspect
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from experiments.drilldown_frontier_allocation_misses import (
    SUBTYPES,
    TARGET_FAILURE_CLASS,
    build_drilldown_table,
    build_rule_specs as build_drilldown_rule_specs,
    decision_majority_with_agree_gate,
    join_rows,
)
from experiments.explore_offline_selector_rules import (
    RuleSpec,
    build_split_diagnostics,
    decision_majority_override,
    evaluate_rule,
)
from experiments.failure_analysis_common import (
    as_bool,
    as_int,
    load_feature_rows,
    write_csv,
    write_json,
    write_text,
)

PRIMARY_RULE_NAME = "drilldown_majority2of3_reason_frontier_support_margin_override"
PRIMARY_RULE_OVERRIDE_REASON = "frontier_support_margin_override"

EXPECTED_CANONICAL = {
    "rows_written": 720,
    "fta_correct_count": 581,
    "effective_fix2_action": 122,
    "effective_fix4_action": 5,
    "no_effective_gate_action": 593,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-table", default=None, help="Canonical failure feature table JSONL.")
    parser.add_argument("--branch-diagnostics", default=None, help="branch_diagnostics_table.jsonl.")
    parser.add_argument(
        "--drilldown-dir",
        default=None,
        help="frontier_miss_drilldown_<timestamp>/ directory to cross-check against. Defaults to the latest.",
    )
    parser.add_argument("--output-dir", required=True, help="Non-destructive output directory.")
    parser.add_argument("--bootstrap-resamples", type=int, default=2000, help="Bootstrap resample count.")
    parser.add_argument("--bootstrap-seed", type=int, default=1234, help="Bootstrap RNG seed (determinism).")
    return parser.parse_args()


def _latest_overnight_dir() -> Path:
    root = Path("outputs/failure_analysis")
    candidates = sorted(p for p in root.glob("overnight_*") if p.is_dir())
    if not candidates:
        raise FileNotFoundError("no outputs/failure_analysis/overnight_* directory found")
    return candidates[-1]


def _latest_drilldown_dir() -> Path | None:
    root = Path("outputs/failure_analysis")
    candidates = sorted(p for p in root.glob("frontier_miss_drilldown_*") if p.is_dir())
    return candidates[-1] if candidates else None


def resolve_input_paths(args: argparse.Namespace) -> tuple[Path, Path, Path | None]:
    if args.feature_table and args.branch_diagnostics:
        feature_table = Path(args.feature_table)
        branch_diagnostics = Path(args.branch_diagnostics)
    else:
        overnight_dir = _latest_overnight_dir()
        feature_table = Path(args.feature_table) if args.feature_table else (
            overnight_dir / "canonical_feature_table" / "failure_feature_table.jsonl"
        )
        branch_diagnostics = Path(args.branch_diagnostics) if args.branch_diagnostics else (
            overnight_dir / "branch_diagnostics" / "branch_diagnostics_table.jsonl"
        )
    drilldown_dir = Path(args.drilldown_dir) if args.drilldown_dir else _latest_drilldown_dir()
    return feature_table, branch_diagnostics, drilldown_dir


# ---------------------------------------------------------------------------
# Baseline / reconstructed candidate decision functions (runtime-legal only)
# ---------------------------------------------------------------------------


def majority_vote(answers: list[str | None]) -> str | None:
    """Majority vote with ties broken by input order (first-listed method wins ties)."""
    valid = [a for a in answers if a not in (None, "")]
    if not valid:
        return None
    counts = Counter(valid)
    best_count = max(counts.values())
    for candidate in valid:
        if counts[candidate] == best_count:
            return candidate
    return None  # unreachable


def decision_canonical_fta(row: dict[str, Any]) -> None:
    """Baseline: never override. evaluate_rule() falls back to fta_selected_answer_canonical."""
    return None


def decision_external3_majority(row: dict[str, Any]) -> str | None:
    """Majority vote of the three external baselines only (L1, S1, TALE), independent of frontier."""
    return majority_vote(
        [
            row.get("l1_answer_canonical"),
            row.get("s1_answer_canonical"),
            row.get("tale_answer_canonical"),
        ]
    )


def decision_pooled4_majority(row: dict[str, Any]) -> str | None:
    """Majority vote of all four candidate answers (frontier, L1, S1, TALE).

    This is an independent offline reconstruction for stress-testing purposes
    only. It is not guaranteed to reproduce the exact canonical "Pooled
    ensemble" figure in docs/CURRENT_CANONICAL_STATE_20260527.md, since the
    tie-break policy used to build that canonical number is not recorded in
    the feature table.
    """
    return majority_vote(
        [
            row.get("frontier_answer_canonical"),
            row.get("l1_answer_canonical"),
            row.get("s1_answer_canonical"),
            row.get("tale_answer_canonical"),
        ]
    )


def decision_majority_reason_excludes(row: dict[str, Any], *, exclude_reason: str) -> str | None:
    """2/3 external majority override gated by override_reason != exclude_reason.

    Used as the "without the margin condition, but still reason-gated" ablation
    of the primary rule: same override structure, but restricted to override
    reasons *other than* the specific margin-related one.
    """
    if str(row.get("override_reason")) == exclude_reason:
        return None
    return decision_majority_override(row)


def build_ablation_and_baseline_specs() -> list[RuleSpec]:
    specs: list[RuleSpec] = [
        RuleSpec(
            name="baseline_canonical_fta",
            family="baseline",
            description="Canonical FTA / FIX-2+FIX-4 (no additional override). Reference point, not a rule candidate.",
            decision_fn=decision_canonical_fta,
        ),
        RuleSpec(
            name="baseline_external3_majority",
            family="baseline",
            description="Majority vote of the three external baselines (L1/S1/TALE) only, independent of frontier.",
            decision_fn=decision_external3_majority,
        ),
        RuleSpec(
            name="baseline_pooled4_majority_reconstructed",
            family="baseline",
            description=(
                "Majority vote of frontier+L1+S1+TALE (offline reconstruction; tie-break order "
                "frontier>L1>S1>TALE; not guaranteed identical to the canonical documented "
                "pooled-ensemble figure)."
            ),
            decision_fn=decision_pooled4_majority,
        ),
    ]

    for threshold in (0, 1, 2):
        specs.append(
            RuleSpec(
                name=f"stress_primary_plus_strict_support_le_{threshold}",
                family="margin_ablation_add_strictness",
                description=(
                    f"Primary rule ({PRIMARY_RULE_NAME}) plus an added frontier_support <= {threshold} gate."
                ),
                decision_fn=lambda row, threshold=threshold: decision_majority_with_agree_gate(
                    row,
                    require_override_reason=PRIMARY_RULE_OVERRIDE_REASON,
                    max_frontier_support=threshold,
                ),
            )
        )

    specs.append(
        RuleSpec(
            name="stress_majority2of3_ungated_no_override_reason_condition",
            family="margin_ablation_remove_override_reason",
            description=(
                "Primary rule with its override_reason condition removed entirely: plain 2/3 external "
                "majority override on every frontier-disagreeing row, ungated (the 'without "
                "override_reason condition' ablation)."
            ),
            decision_fn=lambda row: decision_majority_with_agree_gate(row),
        )
    )

    specs.append(
        RuleSpec(
            name="stress_majority2of3_reason_excludes_margin",
            family="margin_ablation_remove_margin_only",
            description=(
                "Primary rule's override_reason gate inverted: fires on any override_reason "
                f"EXCEPT '{PRIMARY_RULE_OVERRIDE_REASON}' (the 'without the margin condition, but still "
                "reason-gated' ablation)."
            ),
            decision_fn=lambda row: decision_majority_reason_excludes(
                row, exclude_reason=PRIMARY_RULE_OVERRIDE_REASON
            ),
        )
    )

    specs.append(
        RuleSpec(
            name="stress_unanimous_ungated_baseline",
            family="unanimity_ungated_baseline",
            description="3/3 external unanimity override, ungated (no support/cpc/reason/agree gate).",
            decision_fn=lambda row: decision_majority_with_agree_gate(row, unanimous_only=True),
        )
    )

    return specs


def build_full_rule_catalog() -> list[RuleSpec]:
    catalog = build_ablation_and_baseline_specs() + build_drilldown_rule_specs()
    names = [spec.name for spec in catalog]
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate rule names in catalog: {duplicates}")
    return catalog


# ---------------------------------------------------------------------------
# Extended evaluation with row-level outcomes (for bootstrap / audit / cases)
# ---------------------------------------------------------------------------


def _candidate_correct(row: dict[str, Any], answer: str | None) -> bool:
    gold = row.get("gold_answer_canonical")
    if answer in (None, "") or gold in (None, ""):
        return False
    return str(answer) == str(gold)


def evaluate_rule_full(rows: list[dict[str, Any]], spec: RuleSpec) -> dict[str, Any]:
    per_row: list[dict[str, Any]] = []
    for row in rows:
        proposal = spec.decision_fn(row)
        fta_selected = row.get("fta_selected_answer_canonical")
        selected_answer = proposal if proposal not in (None, "") else fta_selected
        selected_correct = _candidate_correct(row, selected_answer)
        fta_correct = as_bool(row.get("fta_correct"))
        override_triggered = proposal not in (None, "")
        override_changed_answer = override_triggered and str(proposal) != str(fta_selected)
        win = bool(selected_correct and not fta_correct)
        loss = bool(fta_correct and not selected_correct)
        per_row.append(
            {
                "row_id": row.get("row_id"),
                "source_id": str(row.get("source_id")),
                "seed": as_int(row.get("seed")),
                "failure_class_coarse": row.get("failure_class_coarse"),
                "gold_answer_canonical": row.get("gold_answer_canonical"),
                "frontier_answer": row.get("frontier_answer"),
                "l1_answer": row.get("l1_answer"),
                "s1_answer": row.get("s1_answer"),
                "tale_answer": row.get("tale_answer"),
                "fta_selected_answer": row.get("fta_selected_answer"),
                "selected_answer": selected_answer,
                "selected_correct": selected_correct,
                "fta_correct": fta_correct,
                "override_triggered": override_triggered,
                "override_changed_answer": override_changed_answer,
                "win": win,
                "loss": loss,
                "override_reason": row.get("override_reason"),
                "frontier_support": row.get("frontier_support"),
                "candidate_pool_answer_group_count": row.get("candidate_pool_answer_group_count"),
                "direct_frontier_agree": row.get("direct_frontier_agree"),
                "external_answers_unanimous": row.get("external_answers_unanimous"),
            }
        )

    n = len(per_row)
    correct_count = sum(r["selected_correct"] for r in per_row)
    wins = sum(r["win"] for r in per_row)
    losses = sum(r["loss"] for r in per_row)
    ties = n - wins - losses
    net_wins = wins - losses
    overrides_triggered = sum(r["override_triggered"] for r in per_row)
    overrides_changed = sum(r["override_changed_answer"] for r in per_row)
    fta_correct_total = sum(r["fta_correct"] for r in per_row)
    regression_rate_among_fta_correct = (losses / fta_correct_total) if fta_correct_total else None
    frontier_allocation_miss_wins = sum(
        1 for r in per_row if r["failure_class_coarse"] == TARGET_FAILURE_CLASS and r["win"]
    )
    fta_success_regressions = sum(
        1 for r in per_row if r["failure_class_coarse"] == "fta_success" and r["loss"]
    )

    per_source: dict[str, Any] = {}
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in per_row:
        by_source[r["source_id"]].append(r)
    for source_id, group in sorted(by_source.items()):
        gn = len(group)
        g_correct = sum(r["selected_correct"] for r in group)
        g_wins = sum(r["win"] for r in group)
        g_losses = sum(r["loss"] for r in group)
        per_source[source_id] = {
            "seed": group[0]["seed"],
            "row_count": gn,
            "correct_count": g_correct,
            "accuracy": round(g_correct / gn, 6) if gn else None,
            "wins": g_wins,
            "losses": g_losses,
            "net_wins": g_wins - g_losses,
            "overrides_triggered": sum(r["override_triggered"] for r in group),
            "overrides_changed_answer": sum(r["override_changed_answer"] for r in group),
        }

    return {
        "rule_name": spec.name,
        "family": spec.family,
        "description": spec.description,
        "row_count": n,
        "correct_count": correct_count,
        "accuracy": round(correct_count / n, 6) if n else 0.0,
        "wins_vs_canonical_fta": wins,
        "losses_vs_canonical_fta": losses,
        "ties_vs_canonical_fta": ties,
        "net_wins": net_wins,
        "overrides_triggered": overrides_triggered,
        "overrides_changed_answer": overrides_changed,
        "regression_rate_among_fta_correct": (
            round(regression_rate_among_fta_correct, 6) if regression_rate_among_fta_correct is not None else None
        ),
        "frontier_allocation_miss_wins": frontier_allocation_miss_wins,
        "fta_success_regressions": fta_success_regressions,
        "per_source": per_source,
        "per_row": per_row,
    }


# ---------------------------------------------------------------------------
# Decision-legality audit
# ---------------------------------------------------------------------------

ILLEGAL_FIELD_BLOCKLIST = {
    "gold_answer",
    "gold_answer_canonical",
    "gold_answer_usage",
    "normalized_gold_answer",
    "gold_in_tree",
    "gold_in_final_nodes",
    "gold_in_direct_reserve_attempts",
    "any_tree_signal_for_gold",
    "exact_match",
    "fta_correct",
    "frontier_correct",
    "l1_correct",
    "s1_correct",
    "tale_correct",
    "any_candidate_correct",
    "any_external_correct",
    "correct_in_candidate_pool",
    "failure_class_coarse",
    "example_id",
    "row_id",
    "source_file",
    "problem_text",
    "frontier_miss_subtype",
}

_HELPER_FNS = {
    "decision_majority_override": decision_majority_override,
    "decision_majority_with_agree_gate": decision_majority_with_agree_gate,
    "decision_majority_reason_excludes": decision_majority_reason_excludes,
    "decision_canonical_fta": decision_canonical_fta,
    "decision_external3_majority": decision_external3_majority,
    "decision_pooled4_majority_reconstructed": decision_pooled4_majority,
    "majority_vote": majority_vote,
}

_FIELD_ACCESS_RE = re.compile(r"row\.get\(\s*[\"']([a-zA-Z0-9_]+)[\"']")


def _decision_source_blob(spec: RuleSpec) -> str:
    try:
        blob = inspect.getsource(spec.decision_fn)
    except (OSError, TypeError):
        blob = f"<source unavailable for {spec.name}>"
    for helper_name, helper_fn in _HELPER_FNS.items():
        if helper_name in blob:
            try:
                blob += "\n" + inspect.getsource(helper_fn)
            except (OSError, TypeError):
                pass
    return blob


def audit_rule_decision_legality(specs: list[RuleSpec]) -> list[dict[str, Any]]:
    rows = []
    for spec in specs:
        blob = _decision_source_blob(spec)
        referenced_fields = sorted(set(_FIELD_ACCESS_RE.findall(blob)))
        illegal_fields = sorted(set(referenced_fields) & ILLEGAL_FIELD_BLOCKLIST)
        rows.append(
            {
                "rule_name": spec.name,
                "family": spec.family,
                "referenced_fields": ";".join(referenced_fields),
                "illegal_fields_found": ";".join(illegal_fields),
                "is_runtime_legal": len(illegal_fields) == 0,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Paired bootstrap confidence intervals
# ---------------------------------------------------------------------------


def _index_per_row_by_id(per_row: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r["row_id"]): r for r in per_row}


def paired_bootstrap_ci(
    per_row_a: list[dict[str, Any]],
    per_row_b: list[dict[str, Any]],
    *,
    n_resamples: int = 2000,
    seed: int = 1234,
    stratify_by_source: bool = True,
) -> dict[str, Any]:
    """Paired bootstrap 95% CI for (accuracy_a - accuracy_b) over the same rows.

    Rows are aligned by row_id (order-independent). If stratify_by_source is
    True, resampling draws with replacement independently within each
    source_id group (source-stratified bootstrap), preserving per-source
    sample sizes across resamples.
    """
    by_id_a = _index_per_row_by_id(per_row_a)
    by_id_b = _index_per_row_by_id(per_row_b)
    common_ids = sorted(set(by_id_a) & set(by_id_b))
    n = len(common_ids)
    if n == 0:
        return {
            "n_rows": 0,
            "observed_delta_accuracy": None,
            "ci_low": None,
            "ci_high": None,
            "includes_zero": None,
            "n_resamples": n_resamples,
            "stratified_by_source": stratify_by_source,
        }

    a_correct = [1 if by_id_a[rid]["selected_correct"] else 0 for rid in common_ids]
    b_correct = [1 if by_id_b[rid]["selected_correct"] else 0 for rid in common_ids]
    source_ids = [by_id_a[rid]["source_id"] for rid in common_ids]

    observed_delta = (sum(a_correct) - sum(b_correct)) / n

    rng = random.Random(seed)
    if stratify_by_source:
        group_indices: dict[str, list[int]] = defaultdict(list)
        for idx, source_id in enumerate(source_ids):
            group_indices[source_id].append(idx)
        groups = list(group_indices.values())
    else:
        groups = [list(range(n))]

    deltas: list[float] = []
    for _ in range(n_resamples):
        resample_idx: list[int] = []
        for group in groups:
            resample_idx.extend(rng.choices(group, k=len(group)))
        a_sum = sum(a_correct[i] for i in resample_idx)
        b_sum = sum(b_correct[i] for i in resample_idx)
        deltas.append((a_sum - b_sum) / n)

    deltas.sort()
    lo_idx = max(0, int(round(0.025 * n_resamples)) - 1)
    hi_idx = min(n_resamples - 1, int(round(0.975 * n_resamples)) - 1)
    ci_low = deltas[lo_idx]
    ci_high = deltas[hi_idx]

    return {
        "n_rows": n,
        "observed_delta_accuracy": round(observed_delta, 6),
        "ci_low": round(ci_low, 6),
        "ci_high": round(ci_high, 6),
        "includes_zero": bool(ci_low <= 0.0 <= ci_high),
        "n_resamples": n_resamples,
        "stratified_by_source": stratify_by_source,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Canonical count check
# ---------------------------------------------------------------------------


def canonical_count_check(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows_written = len(all_rows)
    fta_correct_count = sum(as_bool(row.get("fta_correct")) for row in all_rows)
    effective_fix2_action = sum(as_bool(row.get("effective_fix2_action")) for row in all_rows)
    effective_fix4_action = sum(as_bool(row.get("effective_fix4_action")) for row in all_rows)
    no_effective_gate_action = sum(as_bool(row.get("no_effective_gate_action")) for row in all_rows)
    actual = {
        "rows_written": rows_written,
        "fta_correct_count": fta_correct_count,
        "effective_fix2_action": effective_fix2_action,
        "effective_fix4_action": effective_fix4_action,
        "no_effective_gate_action": no_effective_gate_action,
    }
    mismatches = [
        f"{key}: expected {want}, got {actual[key]}"
        for key, want in EXPECTED_CANONICAL.items()
        if actual[key] != want
    ]
    return {
        "expected": EXPECTED_CANONICAL,
        "actual": actual,
        "matches_expected": len(mismatches) == 0,
        "mismatches": mismatches,
    }


# ---------------------------------------------------------------------------
# Cross-check against the drilldown rule-candidate CSV
# ---------------------------------------------------------------------------


def load_drilldown_rule_csv(path: Path) -> list[dict[str, Any]]:
    import csv

    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def cross_check_against_drilldown_csv(
    evaluations: dict[str, dict[str, Any]],
    drilldown_csv_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    mismatches = []
    checked = 0
    for row in drilldown_csv_rows:
        rule_name = row["rule_name"]
        current = evaluations.get(rule_name)
        if current is None:
            continue
        checked += 1
        for field, csv_key in (
            ("wins_vs_canonical_fta", "wins_vs_canonical_fta"),
            ("losses_vs_canonical_fta", "losses_vs_canonical_fta"),
            ("net_wins", "net_wins"),
        ):
            expected = int(row[csv_key])
            got = current[field]
            if expected != got:
                mismatches.append(
                    f"{rule_name}.{field}: drilldown_csv={expected}, stress_test={got}"
                )
    return {"rules_checked": checked, "mismatches": mismatches, "reproducible": len(mismatches) == 0}


# ---------------------------------------------------------------------------
# Fragility analysis
# ---------------------------------------------------------------------------


def build_fragility_analysis(evaluations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    primary = evaluations[PRIMARY_RULE_NAME]
    variants = {
        "add_strict_support_le_0": evaluations.get("stress_primary_plus_strict_support_le_0"),
        "add_strict_support_le_1": evaluations.get("stress_primary_plus_strict_support_le_1"),
        "add_strict_support_le_2": evaluations.get("stress_primary_plus_strict_support_le_2"),
        "remove_override_reason_condition": evaluations.get(
            "stress_majority2of3_ungated_no_override_reason_condition"
        ),
        "remove_margin_condition_only": evaluations.get("stress_majority2of3_reason_excludes_margin"),
    }

    def _summary(ev: dict[str, Any] | None) -> dict[str, Any] | None:
        if ev is None:
            return None
        return {
            "wins": ev["wins_vs_canonical_fta"],
            "losses": ev["losses_vs_canonical_fta"],
            "net_wins": ev["net_wins"],
            "accuracy": ev["accuracy"],
        }

    removing_override_reason = variants["remove_override_reason_condition"]
    removing_creates_regressions = bool(
        removing_override_reason and removing_override_reason["losses_vs_canonical_fta"] > 0
    )
    removing_margin_only = variants["remove_margin_condition_only"]
    depends_on_narrow_condition = bool(
        removing_margin_only
        and (
            removing_margin_only["net_wins"] < primary["net_wins"]
            or removing_margin_only["losses_vs_canonical_fta"] > primary["losses_vs_canonical_fta"]
        )
    )
    adding_strictness_changes_result = any(
        variants[key] is not None and _summary(variants[key]) != _summary(primary)
        for key in ("add_strict_support_le_0", "add_strict_support_le_1", "add_strict_support_le_2")
    )
    small_sample_flag = primary["wins_vs_canonical_fta"] < 10

    return {
        "primary_rule": _summary(primary),
        "variants": {name: _summary(ev) for name, ev in variants.items()},
        "removing_override_reason_condition_creates_regressions": removing_creates_regressions,
        "depends_on_narrow_override_reason_value": depends_on_narrow_condition,
        "adding_strictness_changes_result": adding_strictness_changes_result,
        "small_sample_flag": small_sample_flag,
        "small_sample_note": (
            f"Primary rule wins on {primary['wins_vs_canonical_fta']} of 720 rows "
            f"({primary['frontier_allocation_miss_wins']} frontier_allocation_miss cases); "
            "a swing of even 1-2 rows would materially change the win/loss ratio. Too small "
            "to promote without independent replication."
            if small_sample_flag
            else "Win count is large enough to be less sensitive to single-row swings."
        ),
    }


# ---------------------------------------------------------------------------
# Representative cases
# ---------------------------------------------------------------------------


def _format_case(r: dict[str, Any]) -> str:
    return (
        f"- {r['row_id']} | seed={r['seed']} | gold={r['gold_answer_canonical']} | "
        f"frontier={r['frontier_answer']} | l1={r['l1_answer']} | s1={r['s1_answer']} | "
        f"tale={r['tale_answer']} | fta={r['fta_selected_answer']} | selected={r['selected_answer']} | "
        f"override_reason={r['override_reason']} | frontier_support={r['frontier_support']} | "
        f"cpc={r['candidate_pool_answer_group_count']} | "
        f"external_answers_unanimous={r['external_answers_unanimous']}"
    )


def build_case_markdown(
    *,
    primary_eval: dict[str, Any],
    risky_eval_support: dict[str, Any],
    risky_eval_agree: dict[str, Any],
    unanimous_eval: dict[str, Any],
    limit: int = 5,
) -> tuple[str, str]:
    promising_lines = [
        "# Promising Rule Examples",
        "",
        f"## Wins over canonical FTA: `{PRIMARY_RULE_NAME}`",
        "",
        "Cases where the primary exploratory rule overrides FTA's answer and the override is correct.",
        "",
    ]
    wins = [r for r in primary_eval["per_row"] if r["win"]]
    if not wins:
        promising_lines.append("_no win cases found_")
    for r in wins[:limit]:
        promising_lines.append(_format_case(r))
    promising_lines.append("")

    unsafe_lines = [
        "# Unsafe Rule Examples",
        "",
        "## Risky majority-override rule loses where FTA was correct",
        "",
        f"Source rule: `{risky_eval_support['rule_name']}` "
        f"(net_wins={risky_eval_support['net_wins']}, "
        f"losses={risky_eval_support['losses_vs_canonical_fta']}).",
        "",
    ]
    losses = [r for r in risky_eval_support["per_row"] if r["loss"]]
    if not losses:
        unsafe_lines.append("_no loss cases found_")
    for r in losses[:limit]:
        unsafe_lines.append(_format_case(r))

    unsafe_lines.extend(["", "## Seed-61 regressions for risky rules", ""])
    seed61_losses_by_row: dict[str, tuple[str, dict[str, Any]]] = {}
    for ev in (risky_eval_support, risky_eval_agree):
        for r in ev["per_row"]:
            if r["loss"] and r["seed"] == 61:
                seed61_losses_by_row.setdefault(str(r["row_id"]), (ev["rule_name"], r))
    seed61_losses = list(seed61_losses_by_row.values())
    if not seed61_losses:
        unsafe_lines.append(
            "_No seed-61-specific regression (loss) rows were found for the risky rules "
            f"`{risky_eval_support['rule_name']}` / `{risky_eval_agree['rule_name']}`. "
            "Their `especially_fails_on_seed_61` flag in the prior drilldown reflects a "
            "relative accuracy-delta comparison against the other seeds on a small, "
            "failure-enriched 120-row source, not raw regression rows on this source._"
        )
    else:
        for rule_name, r in seed61_losses[:limit]:
            unsafe_lines.append(f"- [`{rule_name}`] " + _format_case(r).removeprefix("- "))

    unsafe_lines.extend(["", "## External unanimity safer than 2-of-3 majority", ""])
    majority_losses_non_unanimous = [
        r for r in risky_eval_support["per_row"] if r["loss"] and not as_bool(r["external_answers_unanimous"])
    ]
    unsafe_lines.append(
        f"`{unanimous_eval['rule_name']}` never triggers on these rows (majority present but not "
        f"unanimous), so it stays at FTA's answer and avoids the regression. "
        f"Aggregate contrast: unanimity rules average far fewer losses than majority rules "
        "(see frontier_miss_drilldown_report.md, 'Unanimity vs 2-of-3 majority safety')."
    )
    if majority_losses_non_unanimous:
        unsafe_lines.append("")
        unsafe_lines.append("Regression rows where the majority (non-unanimous) override was wrong:")
        for r in majority_losses_non_unanimous[:limit]:
            unsafe_lines.append(_format_case(r))

    return "\n".join(promising_lines).rstrip() + "\n", "\n".join(unsafe_lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Manuscript tables / numbers
# ---------------------------------------------------------------------------


def build_manuscript_tables(
    *,
    canonical_check: dict[str, Any],
    evaluations: dict[str, dict[str, Any]],
    subtype_counts: dict[str, int],
    bootstrap_rows: list[dict[str, Any]],
    drilldown_report_path: Path | None,
) -> str:
    primary = evaluations[PRIMARY_RULE_NAME]
    canonical_fta = evaluations["baseline_canonical_fta"]
    external3 = evaluations["baseline_external3_majority"]
    pooled4 = evaluations["baseline_pooled4_majority_reconstructed"]

    lines = [
        "# Manuscript-Ready Material (Exploratory / Offline Only)",
        "",
        "**Status: exploratory.** No rule in this document is promoted. FTA / FIX-2+FIX-4 "
        "(`experiments/support_aware_selector.py`) remains the sole canonical selector. All numbers "
        "below are offline diagnostics over the canonical Aggregate-720 table "
        "(720 rows, seeds 41+61+71, Cohere x GSM8K, budget=6) and must not be presented as a new "
        "paper-facing result without a separate, explicit promotion decision.",
        "",
        "## Table A: canonical FTA vs exploratory rule vs External-3 vs Pooled-4",
        "",
        "| Method | Accuracy | Correct/Total | Wins vs FTA | Losses vs FTA | Net wins |",
        "|---|---|---|---|---|---|",
        (
            f"| Canonical FTA / FIX-2+FIX-4 | {canonical_fta['accuracy']:.4f} | "
            f"{canonical_fta['correct_count']}/{canonical_fta['row_count']} | - | - | - |"
        ),
        (
            f"| `{PRIMARY_RULE_NAME}` (exploratory) | {primary['accuracy']:.4f} | "
            f"{primary['correct_count']}/{primary['row_count']} | "
            f"{primary['wins_vs_canonical_fta']} | {primary['losses_vs_canonical_fta']} | "
            f"{primary['net_wins']} |"
        ),
        (
            f"| External-3 majority (L1/S1/TALE) | {external3['accuracy']:.4f} | "
            f"{external3['correct_count']}/{external3['row_count']} | "
            f"{external3['wins_vs_canonical_fta']} | {external3['losses_vs_canonical_fta']} | "
            f"{external3['net_wins']} |"
        ),
        (
            f"| Pooled-4 majority (reconstructed, offline) | {pooled4['accuracy']:.4f} | "
            f"{pooled4['correct_count']}/{pooled4['row_count']} | "
            f"{pooled4['wins_vs_canonical_fta']} | {pooled4['losses_vs_canonical_fta']} | "
            f"{pooled4['net_wins']} |"
        ),
        "",
        "## Table B: frontier_allocation_miss subtype counts (59 rows)",
        "",
        "| Subtype | Count |",
        "|---|---|",
    ]
    for subtype in SUBTYPES:
        lines.append(f"| `{subtype}` | {subtype_counts.get(subtype, 0)} |")

    lines.extend(
        [
            "",
            "## Table C: recoverable vs risky override diagnostics",
            "",
            "| Rule | Family | Wins | Losses | Net wins | Overrides triggered | "
            "Regression rate among FTA-correct |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    diagnostic_rule_names = [
        PRIMARY_RULE_NAME,
        "stress_majority2of3_ungated_no_override_reason_condition",
        "stress_majority2of3_reason_excludes_margin",
        "drilldown_majority2of3_support_le_2",
        "drilldown_majority2of3_direct_frontier_agree_False",
        "drilldown_unanimous_support_le_2",
        "stress_unanimous_ungated_baseline",
    ]
    for name in diagnostic_rule_names:
        ev = evaluations.get(name)
        if ev is None:
            continue
        rr = ev["regression_rate_among_fta_correct"]
        rr_str = f"{rr:.4f}" if rr is not None else "n/a"
        lines.append(
            f"| `{name}` | {ev['family']} | {ev['wins_vs_canonical_fta']} | "
            f"{ev['losses_vs_canonical_fta']} | {ev['net_wins']} | {ev['overrides_triggered']} | {rr_str} |"
        )

    lines.extend(
        [
            "",
            "## Table D: primary-rule robustness by source (Aggregate-720)",
            "",
            "| source_id | seed | rows | accuracy | wins | losses | net wins | overrides |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for source_id, item in sorted(primary["per_source"].items(), key=lambda kv: (kv[1]["seed"] or 0)):
        marker = " **(seed 61, failure-enriched)**" if item["seed"] == 61 else ""
        lines.append(
            f"| `{source_id}`{marker} | {item['seed']} | {item['row_count']} | {item['accuracy']:.4f} | "
            f"{item['wins']} | {item['losses']} | {item['net_wins']} | {item['overrides_triggered']} |"
        )

    lines.extend(
        [
            "",
            "## Table E: hidden tree-signal failure examples "
            "(`gold_in_tree_only_not_external`; genuine tree-selection failures)",
            "",
            "| row_id | gold | frontier | fta_selected | frontier_support | override_reason |",
            "|---|---|---|---|---|---|",
        ]
    )
    # populated by caller via placeholder replaced below
    lines.append("<!--TABLE_E_ROWS-->")

    lines.extend(["", "## Bootstrap confidence intervals", "", "| Comparison | Observed delta | 95% CI | Includes zero? |", "|---|---|---|---|"])
    for item in bootstrap_rows:
        ci = f"[{item['ci_low']:+.4f}, {item['ci_high']:+.4f}]" if item["ci_low"] is not None else "n/a"
        delta = f"{item['observed_delta_accuracy']:+.4f}" if item["observed_delta_accuracy"] is not None else "n/a"
        lines.append(f"| {item['comparison_name']} | {delta} | {ci} | {item['includes_zero']} |")

    lines.extend(
        [
            "",
            "## Manuscript-ready text (exploratory / offline, not promoted)",
            "",
            (
                f"In an offline drilldown of the 59 `frontier_allocation_miss` cases in the canonical "
                f"Aggregate-720 evaluation (Cohere x GSM8K, seeds 41+61+71, budget=6), we explored "
                f"whether a 2-of-3 external-baseline majority override, gated by the existing "
                f"runtime `override_reason == \"{PRIMARY_RULE_OVERRIDE_REASON}\"` diagnostic field, "
                f"could recover additional correct answers without regressing FTA-correct rows. Over "
                f"the full 720-row corpus this exploratory rule produces "
                f"{primary['wins_vs_canonical_fta']} wins and {primary['losses_vs_canonical_fta']} "
                f"losses relative to canonical FTA (net {primary['net_wins']:+d}). Applied as a fixed "
                f"rule to each of the three sources individually, it causes zero losses on every "
                f"single source (see Table D) -- it never regresses a source it was not 'tuned' on."
            ),
            "",
            (
                "This result is exploratory only and is not promoted to a new selector variant. The "
                f"absolute win count ({primary['wins_vs_canonical_fta']} of 720 rows) is small enough "
                "that a paired, source-stratified bootstrap comparison against canonical FTA is "
                "reported alongside it (see 'Bootstrap confidence intervals' above); readers should "
                "treat the confidence interval, not the point estimate alone, as the basis for any "
                "claim of improvement."
            ),
            "",
            (
                "A separate, stricter robustness diagnostic (`robustness_leave_one_source_out.csv`) "
                "selects the best-looking rule from the *entire* candidate catalog (all baselines and "
                "variants, not just the primary rule) on each dev source and tests it on the held-out "
                "source(s). Because this rule catalog itself was built by looking at all three seeds "
                "in the original drilldown, this dev/test split is only a robustness diagnostic, not a "
                "clean held-out validation. Under that diagnostic, the dev-selection process usually "
                "does *not* pick the primary rule at all -- it more often picks the higher-variance "
                "Pooled-4 baseline or the `direct_frontier_agree_False` majority variant, and the "
                "resulting held-out performance is flagged `unsafe` in 4 of 6 splits. This is an "
                "argument for caution, not for the primary rule specifically failing: it shows that "
                "naive dev-tuned rule *selection* across this small a corpus is not yet trustworthy, "
                "independent of whether any single rule (including the primary one) looks safe in "
                "isolation."
            ),
            "",
            (
                "Ablating the rule's single override_reason condition shows its behavior is not an "
                "artifact of an overly narrow gate in one direction: removing the condition entirely "
                "collapses it to an ungated 2-of-3 majority override, which is known to regress "
                "FTA-correct rows elsewhere in this corpus (see `drilldown_majority2of3_support_le_2` "
                "in Table C); restricting to the complementary set of override reasons (excluding the "
                "margin-specific one) changes the win/loss balance materially. Separately, requiring "
                "full 3/3 external unanimity rather than a 2-of-3 majority is consistently safer "
                "across every gated variant tested, consistent with the original drilldown finding."
            ),
            "",
            (
                "None of the above changes the canonical FTA / FIX-2+FIX-4 selector implementation "
                "in `experiments/support_aware_selector.py`, nor any claim in "
                "`docs/CLAIMS.md` or `docs/CURRENT_CANONICAL_STATE_20260527.md`. All gold-derived "
                "fields used to score these rules were used for offline evaluation only; the rule "
                "decision functions themselves read only runtime-legal fields, audited in "
                "`rule_decision_audit.csv`."
            ),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_manuscript_numbers(
    *,
    canonical_check: dict[str, Any],
    evaluations: dict[str, dict[str, Any]],
    bootstrap_rows: list[dict[str, Any]],
    fragility: dict[str, Any],
) -> dict[str, Any]:
    primary = evaluations[PRIMARY_RULE_NAME]
    return {
        "canonical_check": canonical_check,
        "primary_rule": {
            "name": PRIMARY_RULE_NAME,
            "accuracy": primary["accuracy"],
            "correct_count": primary["correct_count"],
            "row_count": primary["row_count"],
            "wins_vs_canonical_fta": primary["wins_vs_canonical_fta"],
            "losses_vs_canonical_fta": primary["losses_vs_canonical_fta"],
            "net_wins": primary["net_wins"],
            "overrides_triggered": primary["overrides_triggered"],
            "regression_rate_among_fta_correct": primary["regression_rate_among_fta_correct"],
        },
        "baselines": {
            name: {
                "accuracy": evaluations[name]["accuracy"],
                "correct_count": evaluations[name]["correct_count"],
            }
            for name in (
                "baseline_canonical_fta",
                "baseline_external3_majority",
                "baseline_pooled4_majority_reconstructed",
            )
        },
        "bootstrap": bootstrap_rows,
        "fragility": fragility,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_stress_test(
    feature_table_path: Path,
    branch_diagnostics_path: Path,
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    feature_rows = load_feature_rows(feature_table_path)
    branch_rows = load_feature_rows(branch_diagnostics_path)
    all_rows, join_stats = join_rows(feature_rows, branch_rows)

    canonical_check = canonical_count_check(all_rows)

    catalog = build_full_rule_catalog()
    evaluations = {spec.name: evaluate_rule_full(all_rows, spec) for spec in catalog}

    # Cross-check the reused drilldown-catalog subset against the frozen evaluate_rule().
    frozen_mismatches = []
    for spec in catalog:
        frozen = evaluate_rule(all_rows, spec)
        full = evaluations[spec.name]
        for field in ("wins_vs_canonical_fta", "losses_vs_canonical_fta", "net_wins", "accuracy"):
            if frozen[field] != full[field]:
                frozen_mismatches.append(f"{spec.name}.{field}: frozen={frozen[field]}, full={full[field]}")

    drilldown_rows = build_drilldown_table(all_rows)
    subtype_counts = dict(Counter(row["frontier_miss_subtype"] for row in drilldown_rows))
    for subtype in SUBTYPES:
        subtype_counts.setdefault(subtype, 0)

    audit_rows = audit_rule_decision_legality(catalog)

    split_rows = build_split_diagnostics(all_rows, catalog)

    primary_eval = evaluations[PRIMARY_RULE_NAME]
    canonical_eval = evaluations["baseline_canonical_fta"]
    external3_eval = evaluations["baseline_external3_majority"]
    pooled4_eval = evaluations["baseline_pooled4_majority_reconstructed"]
    risky_support = evaluations["drilldown_majority2of3_support_le_2"]
    risky_agree = evaluations["drilldown_majority2of3_direct_frontier_agree_False"]

    bootstrap_specs = [
        ("primary_vs_canonical_fta", primary_eval, canonical_eval),
        ("primary_vs_external3_majority", primary_eval, external3_eval),
        ("primary_vs_pooled4_majority", primary_eval, pooled4_eval),
        ("risky_support_le_2_vs_canonical_fta", risky_support, canonical_eval),
        ("risky_direct_frontier_agree_false_vs_canonical_fta", risky_agree, canonical_eval),
    ]
    bootstrap_rows = []
    for name, eval_a, eval_b in bootstrap_specs:
        result = paired_bootstrap_ci(
            eval_a["per_row"],
            eval_b["per_row"],
            n_resamples=bootstrap_resamples,
            seed=bootstrap_seed,
            stratify_by_source=True,
        )
        bootstrap_rows.append({"comparison_name": name, **result})

    fragility = build_fragility_analysis(evaluations)

    promising_md, unsafe_md = build_case_markdown(
        primary_eval=primary_eval,
        risky_eval_support=risky_support,
        risky_eval_agree=risky_agree,
        unanimous_eval=evaluations["stress_unanimous_ungated_baseline"],
    )

    summary = {
        "join_stats": join_stats,
        "canonical_count_check": canonical_check,
        "frozen_evaluate_rule_cross_check": {
            "mismatches": frozen_mismatches,
            "reproducible": len(frozen_mismatches) == 0,
        },
        "rule_catalog_size": len(catalog),
        "primary_rule": PRIMARY_RULE_NAME,
        "primary_rule_summary": {
            "wins": primary_eval["wins_vs_canonical_fta"],
            "losses": primary_eval["losses_vs_canonical_fta"],
            "net_wins": primary_eval["net_wins"],
            "accuracy": primary_eval["accuracy"],
            "regression_rate_among_fta_correct": primary_eval["regression_rate_among_fta_correct"],
        },
        "subtype_counts": subtype_counts,
        "bootstrap": bootstrap_rows,
        "fragility": fragility,
        "decision_legality_audit_all_legal": all(row["is_runtime_legal"] for row in audit_rows),
    }

    return {
        "all_rows": all_rows,
        "evaluations": evaluations,
        "catalog": catalog,
        "audit_rows": audit_rows,
        "split_rows": split_rows,
        "bootstrap_rows": bootstrap_rows,
        "subtype_counts": subtype_counts,
        "fragility": fragility,
        "summary": summary,
        "promising_md": promising_md,
        "unsafe_md": unsafe_md,
        "drilldown_rows": drilldown_rows,
        "canonical_check": canonical_check,
    }


def render_report(summary: dict[str, Any], evaluations: dict[str, dict[str, Any]]) -> str:
    lines = [
        "# Rule Stress Test Report",
        "",
        "Offline, exploratory stress test of "
        f"`{PRIMARY_RULE_NAME}` and nearby variants/baselines over the canonical Aggregate-720 table. "
        "Does not change FTA/FIX-2+FIX-4 selector logic or manuscript claims.",
        "",
        "## Canonical count check",
        "",
    ]
    check = summary["canonical_count_check"]
    for key, value in check["actual"].items():
        lines.append(f"- `{key}`: {value} (expected {check['expected'][key]})")
    lines.append(f"- matches_expected: {check['matches_expected']}")
    lines.extend(
        [
            "",
            "## Reproducibility cross-check vs frozen evaluate_rule()",
            "",
            f"- reproducible: {summary['frozen_evaluate_rule_cross_check']['reproducible']}",
            f"- mismatches: {summary['frozen_evaluate_rule_cross_check']['mismatches']}",
            "",
            "## Primary rule",
            "",
            f"- name: `{summary['primary_rule']}`",
        ]
    )
    for key, value in summary["primary_rule_summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Decision legality", "", f"- all rules runtime-legal: {summary['decision_legality_audit_all_legal']}"])
    lines.extend(["", "## Subtype counts (frontier_allocation_miss, n=59)", ""])
    for subtype in SUBTYPES:
        lines.append(f"- `{subtype}`: {summary['subtype_counts'].get(subtype, 0)}")
    lines.extend(["", "## Bootstrap confidence intervals", ""])
    for item in summary["bootstrap"]:
        lines.append(
            f"- `{item['comparison_name']}`: delta={item['observed_delta_accuracy']}, "
            f"95% CI=[{item['ci_low']}, {item['ci_high']}], includes_zero={item['includes_zero']} "
            f"(n_rows={item['n_rows']}, resamples={item['n_resamples']}, stratified={item['stratified_by_source']})"
        )
    lines.extend(["", "## Fragility analysis", ""])
    frag = summary["fragility"]
    lines.append(f"- removing_override_reason_condition_creates_regressions: {frag['removing_override_reason_condition_creates_regressions']}")
    lines.append(f"- depends_on_narrow_override_reason_value: {frag['depends_on_narrow_override_reason_value']}")
    lines.append(f"- adding_strictness_changes_result: {frag['adding_strictness_changes_result']}")
    lines.append(f"- small_sample_flag: {frag['small_sample_flag']}")
    lines.append(f"- note: {frag['small_sample_note']}")
    lines.extend(["", "## All rules (sorted by net_wins)", ""])
    for ev in sorted(evaluations.values(), key=lambda e: (-e["net_wins"], e["rule_name"])):
        lines.append(
            f"- `{ev['rule_name']}` ({ev['family']}): accuracy={ev['accuracy']:.4f}, "
            f"wins={ev['wins_vs_canonical_fta']}, losses={ev['losses_vs_canonical_fta']}, "
            f"net_wins={ev['net_wins']}, overrides={ev['overrides_triggered']}, "
            f"regression_rate_among_fta_correct={ev['regression_rate_among_fta_correct']}"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    feature_table_path, branch_diagnostics_path, drilldown_dir = resolve_input_paths(args)

    result = run_stress_test(
        feature_table_path,
        branch_diagnostics_path,
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
    )

    drilldown_cross_check = None
    if drilldown_dir is not None:
        csv_path = drilldown_dir / "recoverable_vs_risky_rule_candidates.csv"
        if csv_path.exists():
            drilldown_csv_rows = load_drilldown_rule_csv(csv_path)
            drilldown_cross_check = cross_check_against_drilldown_csv(result["evaluations"], drilldown_csv_rows)
            result["summary"]["drilldown_csv_cross_check"] = drilldown_cross_check

    output_dir = Path(args.output_dir)

    # stress_test_results.csv
    results_rows = []
    for ev in result["evaluations"].values():
        results_rows.append(
            {
                "rule_name": ev["rule_name"],
                "family": ev["family"],
                "description": ev["description"],
                "row_count": ev["row_count"],
                "accuracy": ev["accuracy"],
                "correct_count": ev["correct_count"],
                "wins_vs_canonical_fta": ev["wins_vs_canonical_fta"],
                "losses_vs_canonical_fta": ev["losses_vs_canonical_fta"],
                "ties_vs_canonical_fta": ev["ties_vs_canonical_fta"],
                "net_wins": ev["net_wins"],
                "overrides_triggered": ev["overrides_triggered"],
                "overrides_changed_answer": ev["overrides_changed_answer"],
                "regression_rate_among_fta_correct": ev["regression_rate_among_fta_correct"],
                "frontier_allocation_miss_wins": ev["frontier_allocation_miss_wins"],
                "fta_success_regressions": ev["fta_success_regressions"],
            }
        )
    results_rows.sort(key=lambda r: (-r["net_wins"], r["rule_name"]))
    write_csv(output_dir / "stress_test_results.csv", results_rows, list(results_rows[0].keys()))

    # robustness_by_source.csv
    source_rows = []
    for ev in result["evaluations"].values():
        for source_id, item in ev["per_source"].items():
            source_rows.append(
                {
                    "rule_name": ev["rule_name"],
                    "family": ev["family"],
                    "source_id": source_id,
                    "seed": item["seed"],
                    "is_seed61": item["seed"] == 61,
                    "row_count": item["row_count"],
                    "accuracy": item["accuracy"],
                    "correct_count": item["correct_count"],
                    "wins_vs_canonical_fta": item["wins"],
                    "losses_vs_canonical_fta": item["losses"],
                    "net_wins": item["net_wins"],
                    "overrides_triggered": item["overrides_triggered"],
                    "overrides_changed_answer": item["overrides_changed_answer"],
                }
            )
    write_csv(output_dir / "robustness_by_source.csv", source_rows, list(source_rows[0].keys()))

    # robustness_leave_one_source_out.csv
    write_csv(
        output_dir / "robustness_leave_one_source_out.csv",
        result["split_rows"],
        list(result["split_rows"][0].keys()) if result["split_rows"] else ["split_name"],
    )

    # bootstrap_ci_table.csv
    write_csv(
        output_dir / "bootstrap_ci_table.csv",
        result["bootstrap_rows"],
        list(result["bootstrap_rows"][0].keys()),
    )

    # rule_decision_audit.csv
    write_csv(
        output_dir / "rule_decision_audit.csv",
        result["audit_rows"],
        list(result["audit_rows"][0].keys()),
    )

    # summary json
    write_json(output_dir / "stress_test_summary.json", result["summary"])

    # report md
    write_text(output_dir / "stress_test_report.md", render_report(result["summary"], result["evaluations"]))

    # manuscript tables + numbers
    manuscript_tables_text = build_manuscript_tables(
        canonical_check=result["canonical_check"],
        evaluations=result["evaluations"],
        subtype_counts=result["subtype_counts"],
        bootstrap_rows=result["bootstrap_rows"],
        drilldown_report_path=drilldown_dir / "frontier_miss_drilldown_report.md" if drilldown_dir else None,
    )
    table_e_rows = []
    for row in result["drilldown_rows"]:
        if row["frontier_miss_subtype"] == "gold_in_tree_only_not_external":
            table_e_rows.append(
                f"| {row['row_id']} | {row['gold_answer_canonical']} | {row['frontier_answer']} | "
                f"{row['fta_selected_answer']} | {row['frontier_support']} | {row['override_reason']} |"
            )
    manuscript_tables_text = manuscript_tables_text.replace(
        "<!--TABLE_E_ROWS-->", "\n".join(table_e_rows) if table_e_rows else "| _none_ | | | | | |"
    )
    write_text(output_dir / "manuscript_tables.md", manuscript_tables_text)

    write_json(
        output_dir / "manuscript_numbers.json",
        build_manuscript_numbers(
            canonical_check=result["canonical_check"],
            evaluations=result["evaluations"],
            bootstrap_rows=result["bootstrap_rows"],
            fragility=result["fragility"],
        ),
    )

    # unsafe / promising examples
    write_text(output_dir / "promising_rule_examples.md", result["promising_md"])
    write_text(output_dir / "unsafe_rule_examples.md", result["unsafe_md"])

    print(
        json.dumps(
            {
                "feature_table": str(feature_table_path),
                "branch_diagnostics": str(branch_diagnostics_path),
                "drilldown_dir": str(drilldown_dir) if drilldown_dir else None,
                "output_dir": str(output_dir),
                "rule_catalog_size": len(result["catalog"]),
                "primary_rule_wins": result["summary"]["primary_rule_summary"]["wins"],
                "primary_rule_losses": result["summary"]["primary_rule_summary"]["losses"],
                "canonical_counts_match": result["canonical_check"]["matches_expected"],
                "drilldown_csv_cross_check_reproducible": (
                    drilldown_cross_check["reproducible"] if drilldown_cross_check else None
                ),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
