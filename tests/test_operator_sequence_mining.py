from __future__ import annotations

import ast
import inspect
from pathlib import Path

from experiments import operator_sequence_mining as osm


def test_operator_sequence_extraction_for_tiny_tree() -> None:
    parent_by_node = {"root": "", "n1": "root", "n2": "n1", "n3": "n2"}
    operator_by_node = {
        "root": "direct_l1_anchor",
        "n1": "equation_first_anchor",
        "n2": "unit_ledger_money_anchor",
        "n3": "backward_check_anchor",
    }

    assert osm.operator_sequence_from_node("n3", parent_by_node, operator_by_node) == (
        "direct_l1_anchor",
        "equation_first_anchor",
        "unit_ledger_money_anchor",
        "backward_check_anchor",
    )
    assert osm.operator_sequence_from_node("root", parent_by_node, operator_by_node) == ("direct_l1_anchor",)


def test_operator_sequence_ngrams_counts_unigram_bigram_trigram() -> None:
    sequence = ("a", "b", "c", "b")

    counts = osm.operator_ngrams(sequence, max_n=3)

    assert counts["n1:a"] == 1
    assert counts["n1:b"] == 2
    assert counts["n1:c"] == 1
    assert counts["n2:a->b"] == 1
    assert counts["n2:b->c"] == 1
    assert counts["n2:c->b"] == 1
    assert counts["n3:a->b->c"] == 1
    assert counts["n3:b->c->b"] == 1


def test_entropy_support_margin_and_outlier_heuristic() -> None:
    counts = {"A": 10, "B": 5, "C": 1}

    assert osm.answer_entropy(counts) > 0.0
    assert osm.support_margin(counts) == 5
    assert osm.is_answer_outlier("B", counts) is True
    assert osm.is_answer_outlier("A", counts) is False
    assert osm.is_answer_outlier("missing", counts) is True


def test_best_descendant_and_gold_in_subtree_propagation() -> None:
    children_by_node = {"root": ["left", "right"], "left": ["left_leaf"], "right": []}
    terminal_quality_by_node = {"left_leaf": 0.9, "right": 0.5}
    gold_present_by_node = {"left_leaf": False, "right": True}

    assert osm.best_descendant_label("root", children_by_node, terminal_quality_by_node) == 0.9
    assert osm.best_descendant_label("left", children_by_node, terminal_quality_by_node) == 0.9
    assert osm.gold_in_subtree_label("root", children_by_node, gold_present_by_node) is True
    assert osm.gold_in_subtree_label("left", children_by_node, gold_present_by_node) is False


def test_build_path_prefix_row_separates_feature_and_label_fields() -> None:
    parent_by_node = {"root": "", "n1": "root", "n2": "n1"}
    operator_by_node = {
        "root": "direct_l1_anchor",
        "n1": "equation_first_anchor",
        "n2": "backward_check_anchor",
    }
    row = osm.build_path_prefix_row(
        node_id="n2",
        parent_by_node=parent_by_node,
        operator_by_node=operator_by_node,
        children_by_node={"root": ["n1"], "n1": ["n2"], "n2": []},
        answer_group_counts={"ans_a": 3, "ans_b": 1},
        current_answer_group="ans_b",
        terminal_quality_by_node={"n2": 0.4},
        gold_present_by_node={"n2": True},
        extra_feature_fields={"sibling_agreement": 0.75},
        extra_label_fields={"delta_quality_after_operator": 0.1},
    )

    feature_keys = {k for k in row if k.startswith("feature_")}
    label_keys = {k for k in row if k.startswith("label_")}

    assert feature_keys
    assert label_keys
    assert feature_keys.isdisjoint(label_keys)
    assert row["feature_path_length"] == 3
    assert row["feature_path_depth"] == 2
    assert row["feature_current_answer_group"] == "ans_b"
    assert row["feature_current_answer_group_support"] == 1
    assert row["feature_is_answer_outlier"] is True
    assert row["label_best_descendant_quality"] == 0.4
    assert row["label_gold_in_subtree"] is True
    assert row["label_delta_quality_after_operator"] == 0.1


def test_operator_sequence_mining_module_has_no_api_client_imports() -> None:
    source_path = inspect.getsourcefile(osm)
    assert source_path is not None
    source = Path(source_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    forbidden = {"openai", "cohere", "anthropic", "requests", "google"}
    assert imported_modules.isdisjoint(forbidden)
