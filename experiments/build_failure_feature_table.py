"""Build an offline failure-analysis feature table from canonical FTA artifacts.

This script is diagnostic infrastructure only. It reads cached local evaluation
artifacts, recomputes the frozen FTA/FIX-2+FIX-4 answer per example using the
current canonical policy implementation, and writes a deterministic feature
table for downstream failure analysis.

Gold labels and correctness fields are produced here for offline analysis only.
They must not be used by runtime selector logic.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from experiments.support_aware_selector import (
    _normalize_answer,
    apply_combined_fix24_to_row,
    external_unanimous_answer,
    is_external_unanimous_against_frontier,
    is_low_depth_risk,
    select_external_majority,
)


CANONICAL_DEFAULT_INPUTS: tuple[dict[str, str], ...] = (
    {
        "source_id": "main_300_seed41_budget6",
        "path": "outputs/overnight_fix5_promotion_grade_validation_20260519T040621Z/"
        "runner_output/cohere_real_model_cost_normalized_validation_fix5_overnight_live_20260519T040621Z/"
        "per_example_records.jsonl",
        "rationale": (
            "Canonical raw per-example source for the Aggregate-720 seed=41 slice, "
            "as referenced by the independent verification report."
        ),
    },
    {
        "source_id": "independent_stage1_base_120_seed61_budget6",
        "path": "outputs/fix6_lovec_independent_extra_action_pilot_20260519T163021Z/"
        "base_runner_output/cohere_real_model_cost_normalized_validation_base_live_20260519T163021Z/"
        "per_example_records.jsonl",
        "rationale": (
            "Canonical raw per-example source for the Aggregate-720 seed=61 slice, "
            "as referenced by the independent verification report."
        ),
    },
    {
        "source_id": "final_300_seed71_budget6",
        "path": "outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/"
        "runner_output/cohere_real_model_cost_normalized_validation_final_fix24_live_20260519/"
        "per_example_records.jsonl",
        "rationale": (
            "Canonical raw per-example source for the Final-300 / Aggregate-720 seed=71 "
            "slice and the main paper-facing validation run."
        ),
    },
)

METHOD_FRONTIER = "direct_reserve_semantic_frontier_v2"
METHOD_L1 = "external_l1_max"
METHOD_S1 = "external_s1_budget_forcing"
METHOD_TALE = "external_tale_prompt_budgeting"
METHOD_ORDER = (METHOD_FRONTIER, METHOD_L1, METHOD_S1, METHOD_TALE)
EXTERNAL_METHODS = (METHOD_L1, METHOD_S1, METHOD_TALE)

CSV_FIELD_ORDER = [
    "row_id",
    "example_id",
    "source_id",
    "source_file",
    "dataset",
    "seed",
    "split",
    "subset",
    "problem_text",
    "gold_answer",
    "gold_answer_canonical",
    "gold_answer_usage",
    "frontier_answer",
    "l1_answer",
    "s1_answer",
    "tale_answer",
    "fta_selected_answer",
    "frontier_answer_canonical",
    "l1_answer_canonical",
    "s1_answer_canonical",
    "tale_answer_canonical",
    "fta_selected_answer_canonical",
    "normalized_gold_answer",
    "normalized_frontier_answer",
    "normalized_l1_answer",
    "normalized_s1_answer",
    "normalized_tale_answer",
    "normalized_fta_selected_answer",
    "frontier_correct",
    "l1_correct",
    "s1_correct",
    "tale_correct",
    "fta_correct",
    "any_external_correct",
    "any_candidate_correct",
    "correct_in_candidate_pool",
    "fta_selected_source",
    "effective_policy_label",
    "effective_fix2_action",
    "effective_fix4_action",
    "no_effective_gate_action",
    "weak_frontier_condition_true",
    "external_consensus_condition_true",
    "low_depth_guard_features",
    "external_consensus_features",
    "frontier_support",
    "override_reason",
    "candidate_pool_answer_group_count",
    "external_answers_unanimous",
    "external_majority_answer",
    "external_majority_count",
    "external_unanimous_against_frontier",
    "two_of_three_external_against_frontier",
    "frontier_matches_any_external",
    "answer_group_count",
    "answer_group_sizes",
    "failure_class_coarse",
]


def normalize_answer(answer: Any) -> str | None:
    """Reuse the frozen support-aware normalization logic."""
    return _normalize_answer(answer)


def _warn(warnings: list[str], message: str) -> None:
    warnings.append(message)
    print(f"WARNING: {message}", file=sys.stderr)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help=(
            "Optional input JSONL file or directory. Repeat to provide multiple inputs. "
            "If omitted, the script uses the canonical Aggregate-720 raw sources from the "
            "independent verification audit."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/failure_analysis",
        help="Output directory. Existing target files are never overwritten.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on the number of examples written, after deterministic sorting.",
    )
    return parser.parse_args()


def _infer_split(example_id: str | None, explicit_split: Any) -> str | None:
    if explicit_split not in (None, ""):
        return str(explicit_split)
    if not example_id:
        return None
    parts = example_id.split("_")
    if len(parts) >= 4:
        candidate = parts[-2]
        if candidate in {"train", "test", "validation", "valid", "dev"}:
            return candidate
    return None


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _resolve_input_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_file():
        return path
    if path.is_dir():
        matches = sorted(path.rglob("per_example_records.jsonl"))
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise FileNotFoundError(f"no per_example_records.jsonl found under {path}")
        raise ValueError(
            f"directory {path} resolved to multiple per_example_records.jsonl files; "
            "pass an explicit file path instead"
        )
    raise FileNotFoundError(path)


def resolve_input_specs(cli_inputs: list[str]) -> list[dict[str, str]]:
    if not cli_inputs:
        return [dict(spec) for spec in CANONICAL_DEFAULT_INPUTS]

    specs: list[dict[str, str]] = []
    for idx, item in enumerate(cli_inputs, start=1):
        resolved = _resolve_input_path(item)
        specs.append(
            {
                "source_id": f"user_input_{idx}",
                "path": str(resolved),
                "rationale": "User-specified input override.",
            }
        )
    return specs


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: expected object rows")
            rows.append(row)
    return rows


def _get_answer_value(row: dict[str, Any] | None) -> Any:
    if not row:
        return None
    return _first_non_empty(
        row.get("selected_answer_raw"),
        row.get("final_answer_raw"),
        row.get("selected_answer_canonical"),
        row.get("final_answer_canonical"),
    )


def _get_canonical_answer_value(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    value = _first_non_empty(
        row.get("selected_answer_canonical"),
        row.get("final_answer_canonical"),
    )
    if value in (None, ""):
        return None
    return str(value)


def _compute_correct(
    normalized_gold: str | None,
    normalized_answer: str | None,
) -> bool | None:
    if normalized_gold is None or normalized_answer is None:
        return None
    return normalized_gold == normalized_answer


def _compact_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _compact_jsonable(v) for k, v in value.items() if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [_compact_jsonable(v) for v in value if v not in (None, "", [], {})]
    return value


def _json_for_csv(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _method_answer_groups(normalized_answers: dict[str, str | None]) -> tuple[int, dict[str, int]]:
    counts = Counter(ans for ans in normalized_answers.values() if ans)
    ordered = dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    return len(ordered), ordered


def _external_agreement_features(
    normalized_frontier: str | None,
    normalized_answers: dict[str, str | None],
) -> dict[str, Any]:
    external_norm_map = {method: normalized_answers.get(method) for method in EXTERNAL_METHODS}
    valid = {method: ans for method, ans in external_norm_map.items() if ans}
    counts = Counter(valid.values())
    external_majority_answer = None
    external_majority_count = 0
    if valid:
        selected_answer, _ = select_external_majority(valid)
        if selected_answer:
            external_majority_answer = selected_answer
            external_majority_count = counts[selected_answer]

    unanimous_answer = external_unanimous_answer(valid) if len(valid) == 3 else None
    frontier_matches_any_external = bool(
        normalized_frontier and normalized_frontier in valid.values()
    )
    two_of_three_external_against_frontier = False
    external_unanimous_against_frontier = False
    if normalized_frontier and external_majority_count >= 2 and external_majority_answer:
        two_of_three_external_against_frontier = external_majority_answer != normalized_frontier
    if normalized_frontier and unanimous_answer:
        external_unanimous_against_frontier = unanimous_answer != normalized_frontier

    return {
        "external_answers_unanimous": bool(unanimous_answer),
        "external_majority_answer": external_majority_answer,
        "external_majority_count": external_majority_count,
        "external_unanimous_against_frontier": external_unanimous_against_frontier,
        "two_of_three_external_against_frontier": two_of_three_external_against_frontier,
        "frontier_matches_any_external": frontier_matches_any_external,
        "external_answer_counts": dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))),
    }


def _compute_canonical_correct(
    *,
    selected_answer_canonical: str | None,
    gold_answer_canonical: str | None,
    fallback_exact_match: Any = None,
) -> bool | None:
    if selected_answer_canonical not in (None, "") and gold_answer_canonical not in (None, ""):
        return str(selected_answer_canonical) == str(gold_answer_canonical)
    if fallback_exact_match in (0, 1, False, True):
        return bool(fallback_exact_match)
    return None


def _determine_selected_source(fta_out: dict[str, Any]) -> str | None:
    applied = fta_out.get("combined24_policy_applied")
    if applied == "fix2":
        selection_meta = fta_out.get("fix2_external_selection") or {}
        for key in ("chosen_method", "priority_method", "method"):
            value = selection_meta.get(key)
            if value:
                return str(value)
        return "external_majority"
    if applied == "fix4":
        return "external_unanimous_consensus"
    if applied == "original":
        return "frontier"
    return None


def _selected_parse_failure(
    selected_source: str | None,
    method_rows: dict[str, dict[str, Any]],
) -> bool:
    if selected_source is None:
        return True
    if selected_source == "frontier":
        row = method_rows.get(METHOD_FRONTIER)
        return bool((row or {}).get("parse_extraction_failure"))
    if selected_source == "external_unanimous_consensus":
        return False
    row = method_rows.get(selected_source)
    if row is None:
        return False
    return bool(row.get("parse_extraction_failure"))


def classify_failure_class_coarse(
    *,
    fta_correct: bool | None,
    normalized_fta_selected_answer: str | None,
    explicit_parse_failure: bool,
    correct_in_candidate_pool: bool | None,
) -> str:
    if fta_correct is True:
        return "fta_success"
    if normalized_fta_selected_answer is None or explicit_parse_failure:
        return "format_or_extraction_failure"
    if correct_in_candidate_pool is True:
        return "frontier_allocation_miss"
    if correct_in_candidate_pool is False:
        return "hard_all_methods_wrong_or_pool_miss"
    return "unclassified_failure"


def build_feature_row(
    *,
    source_id: str,
    source_file: str,
    method_rows: dict[str, dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    frontier_row = method_rows.get(METHOD_FRONTIER)
    if frontier_row is None:
        raise ValueError(f"{source_id}: missing {METHOD_FRONTIER} row")

    missing_methods = [method for method in METHOD_ORDER if method not in method_rows]
    if missing_methods:
        _warn(
            warnings,
            f"{source_id}:{frontier_row.get('example_id')}: missing methods {missing_methods}",
        )

    example_id = str(frontier_row.get("example_id") or "")
    dataset = _first_non_empty(frontier_row.get("dataset"))
    seed = frontier_row.get("seed")
    split = _infer_split(example_id, frontier_row.get("split"))
    question = _first_non_empty(frontier_row.get("question"), frontier_row.get("problem"))
    gold_answer = _first_non_empty(
        frontier_row.get("gold_answer"),
        frontier_row.get("gold_answer_canonical"),
    )
    normalized_gold = normalize_answer(gold_answer)
    gold_answer_canonical = _first_non_empty(frontier_row.get("gold_answer_canonical"), gold_answer)

    raw_answers = {
        METHOD_FRONTIER: _get_answer_value(method_rows.get(METHOD_FRONTIER)),
        METHOD_L1: _get_answer_value(method_rows.get(METHOD_L1)),
        METHOD_S1: _get_answer_value(method_rows.get(METHOD_S1)),
        METHOD_TALE: _get_answer_value(method_rows.get(METHOD_TALE)),
    }
    canonical_answers = {
        METHOD_FRONTIER: _get_canonical_answer_value(method_rows.get(METHOD_FRONTIER)),
        METHOD_L1: _get_canonical_answer_value(method_rows.get(METHOD_L1)),
        METHOD_S1: _get_canonical_answer_value(method_rows.get(METHOD_S1)),
        METHOD_TALE: _get_canonical_answer_value(method_rows.get(METHOD_TALE)),
    }
    normalized_answers = {
        method: normalize_answer(answer)
        for method, answer in raw_answers.items()
    }

    external_answers = {
        method: canonical_answers[method]
        for method in EXTERNAL_METHODS
        if method in method_rows
    }
    fta_out = apply_combined_fix24_to_row(frontier_row, external_answers=external_answers)
    fta_selected_answer = _first_non_empty(
        fta_out.get("combined24_answer_raw"),
        fta_out.get("combined24_answer_canonical"),
    )
    fta_selected_answer_canonical = _first_non_empty(
        fta_out.get("combined24_answer_canonical"),
        normalize_answer(fta_selected_answer),
    )
    normalized_fta_selected = normalize_answer(fta_selected_answer)

    rm = frontier_row.get("result_metadata")
    if isinstance(rm, str):
        try:
            rm = json.loads(rm)
        except json.JSONDecodeError:
            rm = {}
            _warn(
                warnings,
                f"{source_id}:{example_id}: frontier result_metadata was invalid JSON; treating as empty",
            )
    if not isinstance(rm, dict):
        rm = {}

    expected_rm_keys = (
        "override_reason",
        "frontier_support",
        "candidate_pool_answer_group_count",
        "support_margin",
        "direct_reserve_confidence_proxy",
    )
    for key in expected_rm_keys:
        if key not in rm:
            _warn(
                warnings,
                f"{source_id}:{example_id}: frontier result_metadata missing expected key '{key}'",
            )

    weak_frontier_condition_true = is_low_depth_risk(rm)
    external_consensus_condition_true = is_external_unanimous_against_frontier(
        frontier_answer=canonical_answers[METHOD_FRONTIER] or raw_answers[METHOD_FRONTIER],
        external_answers=external_answers,
        result_metadata=rm,
    )
    effective_policy_label = str(fta_out.get("combined24_policy_applied") or "unknown")
    effective_fix2_action = effective_policy_label == "fix2"
    effective_fix4_action = effective_policy_label == "fix4"
    no_effective_gate_action = effective_policy_label == "original"

    answer_group_count, answer_group_sizes = _method_answer_groups(normalized_answers)
    external_features = _external_agreement_features(
        normalized_frontier=normalized_answers[METHOD_FRONTIER],
        normalized_answers=normalized_answers,
    )

    frontier_correct = _compute_canonical_correct(
        selected_answer_canonical=canonical_answers[METHOD_FRONTIER],
        gold_answer_canonical=gold_answer_canonical,
        fallback_exact_match=frontier_row.get("exact_match"),
    )
    l1_correct = _compute_canonical_correct(
        selected_answer_canonical=canonical_answers[METHOD_L1],
        gold_answer_canonical=gold_answer_canonical,
        fallback_exact_match=(method_rows.get(METHOD_L1) or {}).get("exact_match"),
    )
    s1_correct = _compute_canonical_correct(
        selected_answer_canonical=canonical_answers[METHOD_S1],
        gold_answer_canonical=gold_answer_canonical,
        fallback_exact_match=(method_rows.get(METHOD_S1) or {}).get("exact_match"),
    )
    tale_correct = _compute_canonical_correct(
        selected_answer_canonical=canonical_answers[METHOD_TALE],
        gold_answer_canonical=gold_answer_canonical,
        fallback_exact_match=(method_rows.get(METHOD_TALE) or {}).get("exact_match"),
    )
    fta_correct = _compute_canonical_correct(
        selected_answer_canonical=fta_selected_answer_canonical,
        gold_answer_canonical=gold_answer_canonical,
        fallback_exact_match=frontier_row.get("exact_match") if no_effective_gate_action else None,
    )
    if gold_answer_canonical in (None, ""):
        any_external_correct = None
        any_candidate_correct = None
    else:
        any_external_correct = any(
            value is True for value in (l1_correct, s1_correct, tale_correct)
        )
        any_candidate_correct = any(
            value is True for value in (frontier_correct, l1_correct, s1_correct, tale_correct)
        )
    gold_in_tree = frontier_row.get("gold_in_tree")
    if isinstance(gold_in_tree, str):
        gold_in_tree = gold_in_tree.strip().lower() in {"1", "true", "yes"}
    if any_candidate_correct is None and gold_in_tree in (None, ""):
        correct_in_candidate_pool = None
    else:
        correct_in_candidate_pool = bool(any_candidate_correct) or bool(gold_in_tree)

    selected_source = _determine_selected_source(fta_out)
    explicit_parse_failure = _selected_parse_failure(selected_source, method_rows) or bool(
        frontier_row.get("parse_extraction_failure")
    ) and selected_source == "frontier"
    failure_class = classify_failure_class_coarse(
        fta_correct=fta_correct,
        normalized_fta_selected_answer=normalized_fta_selected,
        explicit_parse_failure=explicit_parse_failure,
        correct_in_candidate_pool=correct_in_candidate_pool,
    )

    low_depth_guard_features = _compact_jsonable(
        {
            "override_reason": rm.get("override_reason"),
            "frontier_support": rm.get("frontier_support"),
            "candidate_pool_answer_group_count": rm.get("candidate_pool_answer_group_count"),
            "support_margin": rm.get("support_margin"),
            "direct_reserve_confidence_proxy": rm.get("direct_reserve_confidence_proxy"),
            "frontier_candidate_answer": rm.get("frontier_candidate_answer"),
            "fix2_reason": fta_out.get("fix2_reason"),
            "fix2_external_selection": fta_out.get("fix2_external_selection"),
        }
    )
    external_consensus_features = _compact_jsonable(
        {
            "fix4_reason": fta_out.get("fix4_reason"),
            "fix4_unanimous_answer": fta_out.get("fix4_unanimous_answer"),
            "external_majority_answer": external_features["external_majority_answer"],
            "external_majority_count": external_features["external_majority_count"],
            "external_answer_counts": external_features["external_answer_counts"],
        }
    )

    return {
        "row_id": f"{source_id}:{example_id}",
        "example_id": example_id,
        "source_id": source_id,
        "source_file": source_file,
        "dataset": dataset,
        "seed": seed,
        "split": split,
        "subset": None,
        "problem_text": question,
        "gold_answer": gold_answer,
        "gold_answer_canonical": gold_answer_canonical,
        "gold_answer_usage": "offline_diagnostic_only",
        "frontier_answer": raw_answers[METHOD_FRONTIER],
        "l1_answer": raw_answers[METHOD_L1],
        "s1_answer": raw_answers[METHOD_S1],
        "tale_answer": raw_answers[METHOD_TALE],
        "fta_selected_answer": fta_selected_answer,
        "frontier_answer_canonical": canonical_answers[METHOD_FRONTIER],
        "l1_answer_canonical": canonical_answers[METHOD_L1],
        "s1_answer_canonical": canonical_answers[METHOD_S1],
        "tale_answer_canonical": canonical_answers[METHOD_TALE],
        "fta_selected_answer_canonical": fta_selected_answer_canonical,
        "normalized_gold_answer": normalized_gold,
        "normalized_frontier_answer": normalized_answers[METHOD_FRONTIER],
        "normalized_l1_answer": normalized_answers[METHOD_L1],
        "normalized_s1_answer": normalized_answers[METHOD_S1],
        "normalized_tale_answer": normalized_answers[METHOD_TALE],
        "normalized_fta_selected_answer": normalized_fta_selected,
        "frontier_correct": frontier_correct,
        "l1_correct": l1_correct,
        "s1_correct": s1_correct,
        "tale_correct": tale_correct,
        "fta_correct": fta_correct,
        "any_external_correct": any_external_correct,
        "any_candidate_correct": any_candidate_correct,
        "correct_in_candidate_pool": correct_in_candidate_pool,
        "fta_selected_source": selected_source,
        "effective_policy_label": effective_policy_label,
        "effective_fix2_action": effective_fix2_action,
        "effective_fix4_action": effective_fix4_action,
        "no_effective_gate_action": no_effective_gate_action,
        "weak_frontier_condition_true": weak_frontier_condition_true,
        "external_consensus_condition_true": external_consensus_condition_true,
        "low_depth_guard_features": low_depth_guard_features,
        "external_consensus_features": external_consensus_features,
        "frontier_support": rm.get("frontier_support"),
        "override_reason": rm.get("override_reason"),
        "candidate_pool_answer_group_count": rm.get("candidate_pool_answer_group_count"),
        "external_answers_unanimous": external_features["external_answers_unanimous"],
        "external_majority_answer": external_features["external_majority_answer"],
        "external_majority_count": external_features["external_majority_count"],
        "external_unanimous_against_frontier": external_features[
            "external_unanimous_against_frontier"
        ],
        "two_of_three_external_against_frontier": external_features[
            "two_of_three_external_against_frontier"
        ],
        "frontier_matches_any_external": external_features["frontier_matches_any_external"],
        "answer_group_count": answer_group_count,
        "answer_group_sizes": answer_group_sizes,
        "failure_class_coarse": failure_class,
    }


def build_feature_rows_from_specs(
    specs: list[dict[str, str]],
    *,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    warnings: list[str] = []
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    source_stats: list[dict[str, Any]] = []

    for spec in specs:
        path = Path(spec["path"])
        rows = _load_jsonl(path)
        by_example: dict[str, dict[str, Any]] = defaultdict(dict)
        for row in rows:
            example_id = str(row.get("example_id") or "")
            method = str(row.get("method") or "")
            if not example_id:
                _warn(warnings, f"{spec['source_id']}:{path}: row missing example_id; skipping")
                continue
            if not method:
                _warn(warnings, f"{spec['source_id']}:{example_id}: row missing method; skipping")
                continue
            if method in by_example[example_id]:
                _warn(
                    warnings,
                    f"{spec['source_id']}:{example_id}: duplicate method row for {method}; "
                    "keeping first occurrence",
                )
                continue
            by_example[example_id][method] = row

        source_stats.append(
            {
                "source_id": spec["source_id"],
                "path": str(path),
                "rows_read": len(rows),
                "examples_grouped": len(by_example),
                "rationale": spec.get("rationale"),
            }
        )

        for example_id, method_rows in by_example.items():
            key = (spec["source_id"], example_id)
            grouped[key] = {
                "source_id": spec["source_id"],
                "source_file": str(path),
                "method_rows": method_rows,
            }

    sorted_keys = sorted(
        grouped,
        key=lambda item: (
            grouped[item]["method_rows"].get(METHOD_FRONTIER, {}).get("seed", 10**9),
            item[0],
            item[1],
        ),
    )
    if limit is not None:
        sorted_keys = sorted_keys[:limit]

    feature_rows = [
        build_feature_row(
            source_id=grouped[key]["source_id"],
            source_file=grouped[key]["source_file"],
            method_rows=grouped[key]["method_rows"],
            warnings=warnings,
        )
        for key in sorted_keys
    ]

    summary = {
        "input_selection": {
            "mode": "canonical_defaults" if not specs or specs == [dict(spec) for spec in CANONICAL_DEFAULT_INPUTS] else "custom_inputs",
            "canonical_choice_note": (
                "Default inputs are the three raw per-example JSONL sources used by the "
                "canonical Aggregate-720 independent verification audit. The builder replays "
                "FIX-2+FIX-4 over those raw rows but scores correctness and gate counts using "
                "canonical answer surfaces and effective gate actions, matching the paper-facing "
                "Aggregate-720 definitions."
            ),
            "sources": source_stats,
        },
        "rows_written": len(feature_rows),
        "failure_class_counts": dict(Counter(row["failure_class_coarse"] for row in feature_rows)),
        "gate_counts": {
            "effective_fix2_action": sum(bool(row["effective_fix2_action"]) for row in feature_rows),
            "effective_fix4_action": sum(bool(row["effective_fix4_action"]) for row in feature_rows),
            "no_effective_gate_action": sum(bool(row["no_effective_gate_action"]) for row in feature_rows),
            "weak_frontier_condition_true": sum(bool(row["weak_frontier_condition_true"]) for row in feature_rows),
            "external_consensus_condition_true": sum(bool(row["external_consensus_condition_true"]) for row in feature_rows),
        },
        "fta_correct_count": sum(bool(row["fta_correct"]) for row in feature_rows),
        "warnings": warnings,
    }
    return feature_rows, summary


def _ensure_non_destructive_targets(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = {
        "csv": output_dir / "failure_feature_table.csv",
        "jsonl": output_dir / "failure_feature_table.jsonl",
        "summary": output_dir / "failure_feature_summary.json",
    }
    existing = [str(path) for path in targets.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite existing outputs: " + ", ".join(existing)
        )
    return targets


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    output_dir: Path,
) -> dict[str, Path]:
    targets = _ensure_non_destructive_targets(output_dir)

    with targets["jsonl"].open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")

    with targets["csv"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELD_ORDER)
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            for key in ("low_depth_guard_features", "external_consensus_features", "answer_group_sizes"):
                csv_row[key] = _json_for_csv(csv_row.get(key))
            writer.writerow(csv_row)

    with targets["summary"].open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True, ensure_ascii=True)
        handle.write("\n")

    return targets


def main() -> int:
    args = _parse_args()
    specs = resolve_input_specs(args.input)
    rows, summary = build_feature_rows_from_specs(specs, limit=args.limit)
    outputs = write_outputs(rows, summary, output_dir=Path(args.output_dir))

    print(
        json.dumps(
            {
                "rows_written": len(rows),
                "csv": str(outputs["csv"]),
                "jsonl": str(outputs["jsonl"]),
                "summary": str(outputs["summary"]),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
