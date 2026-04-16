"""Learning pipeline for branch-allocation models from brute-force supervision labels."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

from sklearn.linear_model import LogisticRegression, Ridge


ALLOC_FEATURE_NAMES = [
    "remaining_budget",
    "score",
    "depth",
    "stalled_steps",
    "recent_delta",
    "verify_count",
    "branch_age",
    "parent_relative_score",
    "allocation_candidates_evaluated",
    "allocation_value_std",
    "mode_exact",
    "mode_approx",
    "mode_degenerate",
    "branch_hash",
]


@dataclass(frozen=True)
class LearningConfig:
    seed: int = 17
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    near_tie_margin: float = 0.05
    pairwise_max_iter: int = 500
    outside_max_iter: int = 500
    pointwise_alpha: float = 1.0
    train_pairwise: bool = True
    train_pointwise: bool = True
    train_outside_option: bool = True


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _stable_hash01(text: str) -> float:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:12], 16) / float(16**12)


def _branch_hash(branch_id: str) -> float:
    return 2.0 * _stable_hash01(branch_id) - 1.0


def load_label_artifacts(labels_dir: Path) -> dict[str, list[dict[str, Any]]]:
    required = {
        "candidate_labels": labels_dir / "candidate_labels.jsonl",
        "pairwise_labels": labels_dir / "pairwise_labels.jsonl",
        "state_summaries": labels_dir / "state_summaries.jsonl",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required label artifacts in {labels_dir}: {missing}")

    data = {name: _read_jsonl(path) for name, path in required.items()}
    if not data["candidate_labels"]:
        raise ValueError("candidate_labels.jsonl is empty")
    if not data["pairwise_labels"]:
        raise ValueError("pairwise_labels.jsonl is empty")
    return data


def build_candidate_feature_vector(row: dict[str, Any]) -> list[float]:
    f = row.get("features_branch_v1", {}) if isinstance(row.get("features_branch_v1"), dict) else {}
    mode = str(row.get("mode", "approx"))
    out = {
        "remaining_budget": float(row.get("remaining_budget", 0.0)),
        "score": float(f.get("score", 0.0)),
        "depth": float(f.get("depth", 0.0)),
        "stalled_steps": float(f.get("stalled_steps", 0.0)),
        "recent_delta": float(f.get("recent_delta", 0.0)),
        "verify_count": float(f.get("verify_count", 0.0)),
        "branch_age": float(f.get("branch_age", 0.0)),
        "parent_relative_score": float(f.get("parent_relative_score", 0.0)),
        "allocation_candidates_evaluated": float(row.get("allocation_candidates_evaluated", 0.0)),
        "allocation_value_std": float(row.get("allocation_value_std", 0.0)),
        "mode_exact": 1.0 if mode == "exact" else 0.0,
        "mode_approx": 1.0 if mode == "approx" else 0.0,
        "mode_degenerate": 1.0 if mode == "degenerate" else 0.0,
        "branch_hash": _branch_hash(str(row.get("branch_id", ""))),
    }
    return [float(out[name]) for name in ALLOC_FEATURE_NAMES]


def assign_split(state_id: str, cfg: LearningConfig) -> str:
    r = _stable_hash01(f"{cfg.seed}|{state_id}")
    if r < cfg.train_ratio:
        return "train"
    if r < cfg.train_ratio + cfg.val_ratio:
        return "val"
    return "test"


def prepare_learning_tables(data: dict[str, list[dict[str, Any]]], cfg: LearningConfig) -> dict[str, Any]:
    candidates = [dict(row) for row in data["candidate_labels"]]
    pairwise = [dict(row) for row in data["pairwise_labels"]]
    states = [dict(row) for row in data["state_summaries"]]

    cand_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        state_id = str(row["state_id"])
        branch_id = str(row["branch_id"])
        row["split"] = assign_split(state_id, cfg)
        row["x"] = build_candidate_feature_vector(row)
        cand_by_key[(state_id, branch_id)] = row

    for row in pairwise:
        state_id = str(row["state_id"])
        bi = str(row["branch_i"])
        bj = str(row["branch_j"])
        row["split"] = assign_split(state_id, cfg)
        ci = cand_by_key.get((state_id, bi))
        cj = cand_by_key.get((state_id, bj))
        if ci is None or cj is None:
            raise KeyError(f"Pairwise row references missing candidate rows: {(state_id, bi, bj)}")
        xi = ci["x"]
        xj = cj["x"]
        row["x_i"] = xi
        row["x_j"] = xj
        row["x_diff"] = [float(a - b) for a, b in zip(xi, xj)]
        if "label" not in row:
            row["label"] = int(row.get("preference", 0))

    state_to_candidates: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        state_to_candidates.setdefault(str(row["state_id"]), []).append(row)

    state_to_mode = {str(r["state_id"]): str(r.get("candidate_mode", "unknown")) for r in states}
    state_to_dataset = {
        str(r["state_id"]): str(r.get("dataset_name", "unknown"))
        for r in states
    }
    return {
        "candidates": candidates,
        "pairwise": pairwise,
        "states": states,
        "state_to_candidates": state_to_candidates,
        "state_to_mode": state_to_mode,
        "state_to_dataset": state_to_dataset,
    }


def _fit_pairwise_model(rows: list[dict[str, Any]], cfg: LearningConfig) -> dict[str, Any]:
    train = [r for r in rows if r["split"] == "train"]
    if len(train) < 2:
        return {"model_type": "pairwise_logreg", "status": "insufficient_train_rows"}
    x = [r["x_diff"] for r in train]
    y = [int(r["label"]) for r in train]
    if len(set(y)) < 2:
        return {
            "model_type": "pairwise_logreg",
            "status": "single_class_train",
            "constant_label": int(y[0]),
        }
    model = LogisticRegression(max_iter=cfg.pairwise_max_iter, random_state=cfg.seed)
    model.fit(x, y)
    weights = list(float(v) for v in model.coef_[0])
    return {
        "model_type": "pairwise_logreg",
        "status": "ok",
        "feature_names": ALLOC_FEATURE_NAMES,
        "weights": weights,
        "intercept": float(model.intercept_[0]),
    }


def _fit_pointwise_model(rows: list[dict[str, Any]], cfg: LearningConfig) -> dict[str, Any]:
    train = [r for r in rows if r["split"] == "train"]
    if len(train) < 2:
        return {"model_type": "pointwise_ridge", "status": "insufficient_train_rows"}
    x = [r["x"] for r in train]
    y = [float(r["estimated_value_if_allocate_next"]) for r in train]
    model = Ridge(alpha=cfg.pointwise_alpha, random_state=cfg.seed)
    model.fit(x, y)
    return {
        "model_type": "pointwise_ridge",
        "status": "ok",
        "feature_names": ALLOC_FEATURE_NAMES,
        "weights": [float(v) for v in model.coef_],
        "intercept": float(model.intercept_),
    }


def _fit_outside_option_model(rows: list[dict[str, Any]], cfg: LearningConfig) -> dict[str, Any]:
    train = [r for r in rows if r["split"] == "train"]
    if len(train) < 2:
        return {"model_type": "outside_option_logreg", "status": "insufficient_train_rows"}
    x = [r["x"] for r in train]
    y = [1 if float(r.get("branch_vs_outside_gap", 0.0)) > 0 else 0 for r in train]
    if len(set(y)) < 2:
        return {
            "model_type": "outside_option_logreg",
            "status": "single_class_train",
            "constant_label": int(y[0]),
        }
    model = LogisticRegression(max_iter=cfg.outside_max_iter, random_state=cfg.seed)
    model.fit(x, y)
    return {
        "model_type": "outside_option_logreg",
        "status": "ok",
        "feature_names": ALLOC_FEATURE_NAMES,
        "weights": [float(v) for v in model.coef_[0]],
        "intercept": float(model.intercept_[0]),
    }


def train_models(tables: dict[str, Any], cfg: LearningConfig) -> dict[str, Any]:
    models: dict[str, Any] = {}
    if cfg.train_pairwise:
        models["pairwise"] = _fit_pairwise_model(tables["pairwise"], cfg)
    if cfg.train_pointwise:
        models["pointwise"] = _fit_pointwise_model(tables["candidates"], cfg)
    if cfg.train_outside_option:
        models["outside_option"] = _fit_outside_option_model(tables["candidates"], cfg)
    return models


def _dot(w: list[float], x: list[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(w, x))


def scorer_from_model(model: dict[str, Any]) -> Callable[[dict[str, Any]], float]:
    status = str(model.get("status", ""))
    if status != "ok":
        constant = float(model.get("constant_label", 0.0))
        return lambda _row: constant
    w = [float(v) for v in model.get("weights", [])]
    b = float(model.get("intercept", 0.0))

    if model.get("model_type") == "pairwise_logreg":
        return lambda row: _dot(w, row["x"])
    return lambda row: _dot(w, row["x"]) + b


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _safe_mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _ranking_top1_accuracy(state_to_candidates: dict[str, list[dict[str, Any]]], score_fn: Callable[[dict[str, Any]], float], split: str) -> float:
    ok = 0
    total = 0
    for rows in state_to_candidates.values():
        subset = [r for r in rows if r["split"] == split]
        if len(subset) < 2:
            continue
        pred = max(subset, key=score_fn)["branch_id"]
        truth = max(subset, key=lambda r: float(r["estimated_value_if_allocate_next"]))["branch_id"]
        ok += int(pred == truth)
        total += 1
    return ok / max(1, total)


def _pairwise_agreement(
    rows: list[dict[str, Any]],
    score_fn: Callable[[dict[str, Any]], float],
    split: str,
    *,
    near_tie_margin: float,
) -> tuple[float, float, float, float]:
    subset = [r for r in rows if r["split"] == split]
    if not subset:
        return (0.0, 0.0, 0.0, 0.0)
    correct = 0
    near_correct = 0
    far_correct = 0
    near_n = 0
    far_n = 0
    brier_vals: list[float] = []
    for r in subset:
        si = score_fn({"x": r["x_i"]})
        sj = score_fn({"x": r["x_j"]})
        pred_label = 1 if si >= sj else 0
        y = int(r["label"])
        correct += int(pred_label == y)

        pred_prob = _sigmoid(si - sj)
        brier_vals.append((pred_prob - float(y)) ** 2)

        true_margin = abs(float(r.get("margin", 0.0)))
        if true_margin <= float(near_tie_margin):
            near_n += 1
            near_correct += int(pred_label == y)
        else:
            far_n += 1
            far_correct += int(pred_label == y)
    acc = correct / len(subset)
    near = near_correct / max(1, near_n)
    far = far_correct / max(1, far_n)
    brier = _safe_mean(brier_vals)
    return (acc, near, far, brier)


def _slice_pairwise_accuracy(
    rows: list[dict[str, Any]],
    score_fn: Callable[[dict[str, Any]], float],
    split: str,
    state_to_mode: dict[str, str],
    state_to_dataset: dict[str, str],
) -> dict[str, Any]:
    subset = [r for r in rows if r["split"] == split]

    def acc_for(predicate: Callable[[dict[str, Any]], bool]) -> float:
        filt = [r for r in subset if predicate(r)]
        if not filt:
            return 0.0
        ok = 0
        for r in filt:
            si = score_fn({"x": r["x_i"]})
            sj = score_fn({"x": r["x_j"]})
            ok += int((1 if si >= sj else 0) == int(r["label"]))
        return ok / len(filt)

    budgets = sorted({int(r.get("remaining_budget", 0)) for r in subset})
    by_budget = {str(b): acc_for(lambda r, bb=b: int(r.get("remaining_budget", 0)) == bb) for b in budgets}

    modes = sorted({state_to_mode.get(str(r["state_id"]), "unknown") for r in subset})
    by_mode = {
        m: acc_for(lambda r, mm=m: state_to_mode.get(str(r["state_id"]), "unknown") == mm)
        for m in modes
    }

    datasets = sorted({state_to_dataset.get(str(r["state_id"]), "unknown") for r in subset})
    by_dataset = {
        d: acc_for(lambda r, dd=d: state_to_dataset.get(str(r["state_id"]), "unknown") == dd)
        for d in datasets
    }
    return {
        "pairwise_accuracy_by_budget": by_budget,
        "pairwise_accuracy_by_mode": by_mode,
        "pairwise_accuracy_by_dataset": by_dataset,
    }


def evaluate_models(models: dict[str, Any], tables: dict[str, Any], cfg: LearningConfig) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, model in models.items():
        scorer = scorer_from_model(model)
        pair_acc, near_acc, far_acc, brier = _pairwise_agreement(
            tables["pairwise"],
            scorer,
            "test",
            near_tie_margin=float(cfg.near_tie_margin),
        )
        top1 = _ranking_top1_accuracy(tables["state_to_candidates"], scorer, "test")
        slices = _slice_pairwise_accuracy(
            tables["pairwise"],
            scorer,
            "test",
            tables["state_to_mode"],
            tables["state_to_dataset"],
        )
        out[name] = {
            "model_status": model.get("status", "unknown"),
            "pairwise_accuracy_test": pair_acc,
            "ranking_top1_accuracy_test": top1,
            "agreement_with_bruteforce_labels": pair_acc,
            "near_tie_pairwise_accuracy_test": near_acc,
            "far_margin_pairwise_accuracy_test": far_acc,
            "pairwise_margin_brier_test": brier,
            **slices,
        }
    return out


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_markdown_report(path: Path, *, run_id: str, config: LearningConfig, eval_summary: dict[str, Any]) -> None:
    lines = [
        "# Brute-force label branch-allocation learning report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Seed: `{config.seed}`",
        f"- Near-tie threshold: `{config.near_tie_margin}`",
        "",
        "## Safe interpretation",
        "",
        "Models here are learned approximations to expensive branch-allocation labels.",
        "Do not interpret this as exact global oracle allocation on real model trajectories.",
        "",
        "## Test metrics",
        "",
    ]
    for model_name, metrics in eval_summary.items():
        lines.append(f"### {model_name}")
        for k, v in metrics.items():
            lines.append(f"- {k}: `{v}`")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def config_to_dict(cfg: LearningConfig) -> dict[str, Any]:
    return asdict(cfg)
