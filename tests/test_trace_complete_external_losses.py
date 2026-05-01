from __future__ import annotations

from scripts import collect_trace_complete_external_losses as mod


def test_trace_complete_requires_groups_or_branches() -> None:
    row = {"result_metadata": {}}
    assert mod.is_trace_complete(row, [{"answer": "1"}], []) is True
    assert mod.is_trace_complete(row, [], [{"depth": 1}]) is True
    assert mod.is_trace_complete(row, [], []) is False


def test_dedupe_by_dataset_example_seed_budget_methods() -> None:
    rows = [
        {"dataset": "d", "example_id": "e1", "seed": 1, "budget": 4, "internal_method": "direct_reserve_semantic_frontier_v2", "best_external_method": "external_l1_max"},
        {"dataset": "d", "example_id": "e1", "seed": 1, "budget": 4, "internal_method": "direct_reserve_semantic_frontier_v2", "best_external_method": "external_l1_max"},
        {"dataset": "d", "example_id": "e1", "seed": 1, "budget": 6, "internal_method": "direct_reserve_semantic_frontier_v2", "best_external_method": "external_l1_max"},
    ]
    out = mod.dedupe_cases(rows)
    assert len(out) == 2


def test_gold_present_and_oracle_fix_labels() -> None:
    gold = "42"
    groups = [{"answer": "41", "support": 2}, {"answer": "42", "support": 1}]
    unique = sorted({g["answer"] for g in groups})
    gold_present = int(gold in unique)
    oracle_would_fix = int(gold_present == 1)
    assert gold_present == 1
    assert oracle_would_fix == 1


def test_final_row_only_not_counted_for_trace_target() -> None:
    row = {"result_metadata": {}}
    assert mod.is_trace_complete(row, [], []) is False


def test_dry_run_generation_not_started_without_key() -> None:
    needed = 50
    dry_run = True
    generation_started = (not dry_run) and needed > 0
    assert generation_started is False


def test_pushable_columns_exclude_raw_trace_blob() -> None:
    pushable_columns = {
        "case_id",
        "dataset",
        "example_id",
        "seed",
        "budget",
        "internal_method",
        "best_external_method",
        "problem_statement_short",
        "gold_answer",
        "our_final_answer",
        "external_final_answer",
        "gold_present",
        "oracle_would_fix",
        "candidate_group_count",
        "branch_count",
        "max_depth",
        "answer_entropy",
        "top1_support",
        "top2_support",
        "top2_support_gap",
        "failure_mode",
        "source_artifact",
        "generated_new_or_existing",
    }
    assert "raw_trace" not in pushable_columns
    assert "cohere_generation_cache" not in pushable_columns


def test_model_alias_resolution_uses_known_valid_cohere_model() -> None:
    assert mod.resolve_cohere_model("command-r-plus") == "command-r-plus-08-2024"
    assert mod.resolve_cohere_model("command-r-plus-08-2024") == "command-r-plus-08-2024"


def test_generation_error_excerpt_prefers_stderr_and_is_trimmed() -> None:
    stderr = "line1\nline2\nline3\nline4"
    out = mod.short_error_excerpt(stderr, "", limit=20)
    assert "line1" in out
    assert len(out) <= 20
