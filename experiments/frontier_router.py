"""Lightweight query router for cross-controller frontier allocation (new-paper track)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline


@dataclass
class RouterFitArtifacts:
    model: Any
    label_counts: dict[str, int]
    mode: str


class ConstantRouter:
    """Fallback router when there is not enough class diversity to train a model."""

    def __init__(self, label: str):
        self.label = label

    def predict(self, questions: Iterable[str]) -> list[str]:
        return [self.label for _ in questions]


def derive_oracle_labels(
    rows: list[dict[str, Any]],
    *,
    strategy_order: list[str],
) -> dict[str, str]:
    """Return example_id -> oracle-best strategy label.

    Tie break policy:
    1) any correct strategy beats incorrect
    2) fewer actions_used is preferred
    3) lower expansions then lower verifications
    4) stable order in strategy_order
    """
    rank = {name: idx for idx, name in enumerate(strategy_order)}
    by_example: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_example.setdefault(str(row["example_id"]), []).append(row)

    labels: dict[str, str] = {}
    for ex_id, ex_rows in by_example.items():
        best = min(
            ex_rows,
            key=lambda r: (
                0 if r["is_correct"] else 1,
                float(r["actions_used"]),
                float(r["expansions"]),
                float(r["verifications"]),
                rank.get(str(r["strategy"]), 10**9),
            ),
        )
        labels[ex_id] = str(best["strategy"])
    return labels


def fit_lightweight_router(questions: list[str], labels: list[str], *, seed: int) -> RouterFitArtifacts:
    counts: dict[str, int] = {}
    for y in labels:
        counts[y] = counts.get(y, 0) + 1

    if len(counts) < 2:
        top = max(counts.items(), key=lambda kv: kv[1])[0]
        return RouterFitArtifacts(model=ConstantRouter(top), label_counts=counts, mode="constant")

    model = make_pipeline(
        TfidfVectorizer(lowercase=True, ngram_range=(1, 2), max_features=512),
        LogisticRegression(max_iter=300, random_state=seed, class_weight="balanced"),
    )
    model.fit(questions, labels)
    return RouterFitArtifacts(model=model, label_counts=counts, mode="tfidf_logreg")


def selector_accuracy_from_predictions(
    rows: list[dict[str, Any]],
    predictions: dict[str, str],
) -> dict[str, float]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        by_key[(str(row["example_id"]), str(row["strategy"]))] = row

    n = 0
    correct = 0
    actions = 0.0
    for ex_id, strategy in predictions.items():
        row = by_key.get((str(ex_id), str(strategy)))
        if row is None:
            continue
        n += 1
        correct += int(bool(row["is_correct"]))
        actions += float(row["actions_used"])

    if n == 0:
        return {"accuracy": 0.0, "avg_actions": 0.0, "n_examples": 0.0}
    return {
        "accuracy": correct / n,
        "avg_actions": actions / n,
        "n_examples": float(n),
    }
