"""Offline operator-sequence mining helpers for reasoning-path analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _positive_counts(counts: Mapping[str, Any] | Counter[str] | None) -> list[int]:
    vals: list[int] = []
    for value in dict(counts or {}).values():
        iv = _coerce_int(value, default=0)
        if iv > 0:
            vals.append(iv)
    return vals


@dataclass(frozen=True)
class NodeRecord:
    node_id: str
    parent_id: str | None = None
    operator: str | None = None
    answer_group: str | None = None
    terminal_quality: float | None = None
    gold_present: bool | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "operator": self.operator,
            "answer_group": self.answer_group,
            "terminal_quality": self.terminal_quality,
            "gold_present": self.gold_present,
        }
        row.update(dict(self.metadata))
        return row


@dataclass(frozen=True)
class EdgeRecord:
    parent_id: str
    node_id: str
    operator: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "parent_id": self.parent_id,
            "node_id": self.node_id,
            "operator": self.operator,
        }
        row.update(dict(self.metadata))
        return row


@dataclass(frozen=True)
class PathPrefixRecord:
    node_id: str
    parent_id: str | None
    operator_sequence: tuple[str, ...]
    feature_fields: Mapping[str, Any] = field(default_factory=dict)
    label_fields: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "feature_operator_sequence": self.operator_sequence,
        }
        row.update({f"feature_{key}": value for key, value in dict(self.feature_fields).items()})
        row.update({f"label_{key}": value for key, value in dict(self.label_fields).items()})
        row.update(dict(self.metadata))
        return row


def operator_sequence_from_node(
    node_id: str,
    parent_by_node: Mapping[str, Any],
    operator_by_node: Mapping[str, Any],
) -> tuple[str, ...]:
    """Return the root-to-node operator sequence for a node."""
    current = _as_str(node_id)
    if not current:
        return tuple()

    seen: set[str] = set()
    operators: list[str] = []
    while current and current not in seen:
        seen.add(current)
        operator = _as_str(operator_by_node.get(current))
        if operator:
            operators.append(operator)
        parent = _as_str(parent_by_node.get(current))
        if not parent or parent == current:
            break
        current = parent
    operators.reverse()
    return tuple(operators)


def operator_ngrams(sequence: Sequence[str], max_n: int = 3) -> dict[str, int]:
    """Count contiguous operator n-grams up to ``max_n``."""
    if max_n < 1:
        return {}
    seq = [str(item).strip() for item in sequence if str(item).strip()]
    counts: dict[str, int] = {}
    for n in range(1, max_n + 1):
        if len(seq) < n:
            continue
        for start in range(0, len(seq) - n + 1):
            gram = "->".join(seq[start : start + n])
            key = f"n{n}:{gram}"
            counts[key] = counts.get(key, 0) + 1
    return counts


def answer_entropy(counts: Mapping[str, Any] | Counter[str] | None) -> float:
    """Compute Shannon entropy over support counts using natural log."""
    values = _positive_counts(counts)
    total = sum(values)
    if total <= 0 or len(values) <= 1:
        return 0.0
    entropy = 0.0
    for count in values:
        p = count / total
        entropy -= p * math.log(max(p, 1e-12))
    return float(entropy)


def support_margin(counts: Mapping[str, Any] | Counter[str] | None) -> int:
    """Return top-count minus second-count support."""
    values = sorted(_positive_counts(counts), reverse=True)
    if not values:
        return 0
    top = values[0]
    second = values[1] if len(values) > 1 else 0
    return int(top - second)


def is_answer_outlier(answer_group: str | None, counts: Mapping[str, Any] | Counter[str] | None) -> bool:
    """Transparent minority-support heuristic for an answer group."""
    group = _as_str(answer_group)
    if not group:
        return False

    group_count = _coerce_int(dict(counts or {}).get(group), default=0)
    if group_count <= 0:
        return True

    values = sorted(_positive_counts(counts), reverse=True)
    if not values:
        return False
    top = values[0]
    second = values[1] if len(values) > 1 else 0
    return group_count < top and group_count <= second


def best_descendant_label(
    node_id: str,
    children_by_node: Mapping[str, Sequence[str]] | None,
    terminal_quality_by_node: Mapping[str, Any] | None,
) -> float:
    """Return the best terminal quality reachable from a node, including the node itself."""
    children = children_by_node or {}
    terminal = terminal_quality_by_node or {}
    memo: dict[str, float] = {}

    def _best(current: str, seen: set[str]) -> float:
        key = _as_str(current)
        if not key or key in seen:
            return 0.0
        if key in memo:
            return memo[key]

        seen = set(seen)
        seen.add(key)
        best = _coerce_float(terminal.get(key), default=0.0)
        for child in children.get(key, []) or []:
            best = max(best, _best(_as_str(child), seen))
        memo[key] = float(best)
        return float(best)

    return float(_best(_as_str(node_id), set()))


def gold_in_subtree_label(
    node_id: str,
    children_by_node: Mapping[str, Sequence[str]] | None,
    gold_present_by_node: Mapping[str, Any] | None,
) -> bool:
    """Return True if gold is present at or below the node."""
    children = children_by_node or {}
    gold = gold_present_by_node or {}
    memo: dict[str, bool] = {}

    def _has_gold(current: str, seen: set[str]) -> bool:
        key = _as_str(current)
        if not key or key in seen:
            return False
        if key in memo:
            return memo[key]

        seen = set(seen)
        seen.add(key)
        present = bool(gold.get(key))
        if not present:
            for child in children.get(key, []) or []:
                if _has_gold(_as_str(child), seen):
                    present = True
                    break
        memo[key] = present
        return present

    return bool(_has_gold(_as_str(node_id), set()))


def build_path_prefix_row(
    *,
    node_id: str,
    parent_by_node: Mapping[str, Any],
    operator_by_node: Mapping[str, Any],
    children_by_node: Mapping[str, Sequence[str]] | None = None,
    answer_group_counts: Mapping[str, Any] | None = None,
    current_answer_group: str | None = None,
    terminal_quality_by_node: Mapping[str, Any] | None = None,
    gold_present_by_node: Mapping[str, Any] | None = None,
    extra_feature_fields: Mapping[str, Any] | None = None,
    extra_label_fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a prefix-level row with feature_* and label_* separation."""
    node_key = _as_str(node_id)
    if not node_key:
        raise ValueError("node_id is required")

    parent_id = _as_str(parent_by_node.get(node_key)) or None
    sequence = operator_sequence_from_node(node_key, parent_by_node, operator_by_node)
    counts = dict(answer_group_counts or {})
    group = _as_str(current_answer_group)
    group_support = _coerce_int(counts.get(group), default=0) if group else 0
    total_support = sum(max(0, _coerce_int(v, default=0)) for v in counts.values())
    answer_share = float(group_support / total_support) if total_support > 0 and group else 0.0
    terminal_quality = _coerce_float((terminal_quality_by_node or {}).get(node_key), default=0.0)
    feature_fields: dict[str, Any] = {
        "path_length": len(sequence),
        "path_depth": max(0, len(sequence) - 1),
        "current_answer_group": group or None,
        "current_answer_group_support": group_support,
        "current_answer_group_share": answer_share,
        "answer_entropy": answer_entropy(counts),
        "support_margin": support_margin(counts),
        "is_answer_outlier": is_answer_outlier(group, counts) if group else False,
        "operator_sequence_key": "->".join(sequence),
        "operator_ngram_counts": operator_ngrams(sequence, max_n=3),
    }
    label_fields: dict[str, Any] = {
        "terminal_quality": terminal_quality,
        "best_descendant_quality": best_descendant_label(node_key, children_by_node, terminal_quality_by_node),
        "gold_in_subtree": gold_in_subtree_label(node_key, children_by_node, gold_present_by_node),
    }
    if extra_feature_fields:
        feature_fields.update(dict(extra_feature_fields))
    if extra_label_fields:
        label_fields.update(dict(extra_label_fields))

    return PathPrefixRecord(
        node_id=node_key,
        parent_id=parent_id,
        operator_sequence=sequence,
        feature_fields=feature_fields,
        label_fields=label_fields,
    ).to_row()

