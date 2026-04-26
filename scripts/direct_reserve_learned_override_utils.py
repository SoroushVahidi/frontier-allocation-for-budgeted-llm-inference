from __future__ import annotations

import importlib.metadata
import json
import pickle
import platform
import random
import sys
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression

from experiments.controllers import DirectReserveGateRerankController, DirectReserveLearnedOverrideController
from scripts.learned_branch_scorer_utils import as_int, read_csv
from scripts.train_direct_reserve_candidate_scorer import _feat


def normalize_direct_reserve_plus_diverse_config(controller: Any) -> dict[str, Any]:
    """Return a small stable config projection for parity checks."""
    base = controller.base_controller if isinstance(controller, DirectReserveLearnedOverrideController) else controller
    if not isinstance(base, DirectReserveGateRerankController):
        return {}
    return {
        "direct_prompt_style": str(getattr(base, "direct_prompt_style", "")),
        "direct_prompt_styles": list(getattr(base, "direct_prompt_styles", [])),
        "direct_reserve_attempts_override": getattr(base, "direct_reserve_attempts_override", None),
        "direct_token_budget": int(getattr(base, "direct_token_budget", 0)),
        "direct_token_per_action": float(getattr(base, "direct_token_per_action", 0.0)),
        "gate_top_support_threshold": float(getattr(base, "gate_top_support_threshold", 0.0)),
        "gate_top2_gap_threshold": float(getattr(base, "gate_top2_gap_threshold", 0.0)),
        "gate_entropy_threshold": float(getattr(base, "gate_entropy_threshold", 0.0)),
        "enable_margin_gate_fallback": bool(getattr(base, "enable_margin_gate_fallback", False)),
        "margin_gate_min_support_gap": int(getattr(base, "margin_gate_min_support_gap", 0)),
        "margin_gate_max_entropy": float(getattr(base, "margin_gate_max_entropy", 0.0)),
        "margin_gate_require_multi_prompt_style": bool(getattr(base, "margin_gate_require_multi_prompt_style", False)),
        "max_actions": int(getattr(base, "max_actions", 0)),
    }


def normalize_answer_set(values: list[str | None]) -> tuple[str, ...]:
    return tuple(sorted(str(v or "").strip().lower() for v in values if str(v or "").strip()))


def runtime_env_versions() -> dict[str, str]:
    try:
        joblib_v = importlib.metadata.version("joblib")
    except Exception:
        joblib_v = "unknown"
    return {
        "python": platform.python_version(),
        "numpy": str(np.__version__),
        "sklearn": str(importlib.metadata.version("scikit-learn")),
        "joblib": str(joblib_v),
        "platform": platform.platform(),
    }


def _write_json(path: Any, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _retrain_rf_or_pairwise(
    *,
    training_dataset: Any,
    model_kind: str,
    random_seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = [dict(r) for r in read_csv(training_dataset) if as_int(r.get("excluded_from_training", 0), 0) == 0]
    if not rows:
        raise RuntimeError(f"no rows available in training dataset: {training_dataset}")
    y = np.array([as_int(r.get("is_gold_candidate", 0), 0) for r in rows], dtype=int)
    if len(np.unique(y)) < 2:
        raise RuntimeError("training dataset has fewer than two classes")

    vec = DictVectorizer(sparse=False)
    X = vec.fit_transform([_feat(r) for r in rows])
    rf = RandomForestClassifier(
        n_estimators=120,
        max_depth=5,
        class_weight="balanced",
        random_state=int(random_seed),
        n_jobs=-1,
    )
    rf.fit(X, y)
    payload: dict[str, Any] = {"vectorizer": vec, "rf": rf}

    if str(model_kind) == "pairwise":
        from collections import defaultdict
        from itertools import combinations

        by_gid: dict[str, list[int]] = defaultdict(list)
        for i, r in enumerate(rows):
            gid = f"{r.get('example_id','')}|{r.get('seed','')}|{r.get('budget','')}"
            by_gid[gid].append(i)
        rng = random.Random(int(random_seed))
        pair_feats: list[dict[str, float]] = []
        pair_y: list[int] = []
        for ids in by_gid.values():
            pos = [i for i in ids if y[i] == 1]
            neg = [i for i in ids if y[i] == 0]
            if not pos or not neg:
                continue
            n_pair = min(200, 10 * len(pos) * max(1, len(neg)))
            for t in range(n_pair):
                if t % 2 == 0:
                    a, b = rng.choice(pos), rng.choice(neg)
                    pair_y.append(1)
                else:
                    a, b = rng.choice(neg), rng.choice(pos)
                    pair_y.append(0)
                fa, fb = _feat(rows[a]), _feat(rows[b])
                pair_feats.append({k: fa.get(k, 0.0) - fb.get(k, 0.0) for k in set(fa) | set(fb)})
        if pair_feats and len(set(pair_y)) >= 2:
            pvec = DictVectorizer(sparse=False)
            Xp = pvec.fit_transform(pair_feats)
            plr = LogisticRegression(max_iter=1500, class_weight="balanced", solver="lbfgs", C=0.5)
            plr.fit(Xp, np.array(pair_y, dtype=int))
            payload["pair_vectorizer"] = pvec
            payload["pair_logit"] = plr
    feature_columns = sorted({k for r in rows for k in _feat(r).keys()})
    meta = {
        "n_training_rows": int(len(rows)),
        "n_case_groups": int(
            len({f"{r.get('example_id','')}|{r.get('seed','')}|{r.get('budget','')}" for r in rows})
        ),
        "feature_columns": feature_columns,
    }
    return payload, meta


def load_or_retrain_selector_model(
    *,
    model_path: Any,
    allow_retrain_on_load_failure: bool,
    training_dataset: Any | None,
    output_dir: Any,
    model_kind: str = "rf",
    random_seed: int = 7,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Load model artifact or retrain a compatible fallback model.

    Returns (model_payload_or_none, metadata).
    """
    md: dict[str, Any] = {
        "requested_model_path": str(model_path),
        "allow_retrain_on_load_failure": bool(allow_retrain_on_load_failure),
        "training_dataset": str(training_dataset) if training_dataset else "",
        "model_kind": str(model_kind),
        "random_seed": int(random_seed),
        "runtime_env": runtime_env_versions(),
    }
    try:
        with model_path.open("rb") as f:
            payload = pickle.load(f)
        if not isinstance(payload, dict):
            raise ValueError("loaded model payload is not a dict")
        md["model_load_status"] = "loaded"
        md["model_used_path"] = str(model_path)
        return payload, md
    except Exception as e:
        md["model_load_status"] = "load_failed"
        md["model_load_error"] = repr(e)
        if not allow_retrain_on_load_failure:
            return None, md
        if not training_dataset:
            md["model_load_status"] = "load_failed_no_training_dataset"
            return None, md
        payload, retrain_meta = _retrain_rf_or_pairwise(
            training_dataset=training_dataset, model_kind=str(model_kind), random_seed=int(random_seed)
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        retrained_model = output_dir / "retrained_model.joblib"
        with retrained_model.open("wb") as f:
            pickle.dump(payload, f)
        _write_json(
            output_dir / "retrained_model_manifest.json",
            {
                **md,
                **retrain_meta,
                "model_load_status": "retrained_fallback",
                "model_used_path": str(retrained_model),
                "model_type": "random_forest" if str(model_kind) == "rf" else "random_forest_plus_optional_pairwise",
            },
        )
        _write_json(output_dir / "feature_schema_used.json", {"feature_columns": retrain_meta["feature_columns"]})
        (output_dir / "training_dataset_path.txt").write_text(str(training_dataset) + "\n", encoding="utf-8")
        md.update(
            {
                **retrain_meta,
                "model_load_status": "retrained_fallback",
                "model_used_path": str(retrained_model),
                "model_type": "random_forest" if str(model_kind) == "rf" else "random_forest_plus_optional_pairwise",
            }
        )
        return payload, md

