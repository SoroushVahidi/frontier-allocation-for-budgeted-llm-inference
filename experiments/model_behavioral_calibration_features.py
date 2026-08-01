"""Scaffold for unseen-model behavioral calibration features
(required_code_changes.md Item 10 / unseen_model_feature_design.md).

Computes ONE model-feature record from a set of already-generated, already-gold-joined
oracle-tree rows (the *_WITH_GOLD_OFFLINE_ONLY.jsonl schema produced by
postprocess_oracle_tree_gold_labels.py) for a single (provider, model, dataset) group.

This module does NOT run any new calibration campaign and does NOT make any API call --
it is pure offline computation over already-collected rows, callable equally on synthetic
test fixtures or real Stage 6 data. Running an actual NEW calibration campaign against a
brand-new model is future work (unseen_model_feature_design.md Section 3); this module is
the computation the calibration campaign's collected rows would be fed into.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = min(len(s) - 1, max(0, round(p * (len(s) - 1))))
    return s[idx]


def _by_problem(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["problem_id"], []).append(r)
    return out


def single_sample_accuracy(rows: list[dict]) -> float | None:
    """Fraction of problems where the FIRST stochastic-restart branch alone (a genuine
    single-sample draw, generation_mode=='stochastic_restart', the earliest one recorded for
    that problem) already produces gold."""
    hits = []
    for pid, prows in _by_problem(rows).items():
        restarts = [r for r in prows if r.get("generation_mode") == "stochastic_restart"]
        if not restarts:
            continue
        first = min(restarts, key=lambda r: r.get("chronological_action_index", 0))
        hits.append(1.0 if bool(first.get("node_produces_gold")) else 0.0)
    return _mean(hits)


def stochastic_disagreement_rate(rows: list[dict]) -> float | None:
    """Fraction of problems where the 2 stochastic-restart root branches produce DIFFERENT
    non-null final candidate_answer values -- a direct entropy/disagreement proxy that needs
    no embeddings."""
    disagreements = []
    for pid, prows in _by_problem(rows).items():
        restarts = [r for r in prows if r.get("generation_mode") == "stochastic_restart"]
        answers = [str(r.get("candidate_answer")) for r in restarts if r.get("candidate_answer")]
        if len(answers) < 2:
            continue
        disagreements.append(1.0 if len(set(answers)) > 1 else 0.0)
    return _mean(disagreements)


def self_consistency_gain(rows: list[dict]) -> float | None:
    """Majority-vote-across-all-finished-root-branches accuracy minus single-sample accuracy.
    Majority vote is computed over every row with is_done==True and a non-null
    candidate_answer for that problem (an approximation -- true root-branch identity would
    require a full ancestry walk, out of scope for a lightweight scaffold; documented here,
    not silently assumed precise)."""
    single = single_sample_accuracy(rows)
    if single is None:
        return None
    maj_hits = []
    for pid, prows in _by_problem(rows).items():
        finished = [r for r in prows if r.get("is_done") and r.get("candidate_answer")]
        if not finished:
            continue
        answers = [str(r["candidate_answer"]) for r in finished]
        counts: dict[str, int] = {}
        for a in answers:
            counts[a] = counts.get(a, 0) + 1
        majority_answer = max(counts.items(), key=lambda kv: kv[1])[0]
        majority_row = next(r for r in finished if str(r["candidate_answer"]) == majority_answer)
        maj_hits.append(1.0 if bool(majority_row.get("node_produces_gold")) else 0.0)
    majority_acc = _mean(maj_hits)
    if majority_acc is None:
        return None
    return majority_acc - single


def action_type_cost_normalized_value(rows: list[dict], generation_mode: str) -> float | None:
    """gold-hit-rate per dollar spent on this action type -- an aggregate, per-action-type
    proxy for learning_target_design.md's marginal_utility_per_cost, coarser than a true
    per-decision-state estimate (that requires the full state/action logging this scaffold
    does not attempt to reconstruct) but directly computable from any gold-joined trace set."""
    subset = [r for r in rows if r.get("generation_mode") == generation_mode]
    if not subset:
        return None
    hit_rate = _mean([1.0 if bool(r.get("node_produces_gold")) else 0.0 for r in subset])
    mean_cost = _mean([float(r.get("monetary_cost_usd") or 0.0) for r in subset])
    if hit_rate is None or not mean_cost:
        return None
    return hit_rate / mean_cost


def mean_reasoning_length_tokens(rows: list[dict]) -> float | None:
    return _mean([float(r.get("tokens_used", {}).get("output_tokens", 0) or 0) for r in rows])


def early_termination_rate(rows: list[dict]) -> float | None:
    """Fraction of ROOT-originated branches (action_from_parent=='ROOT') that were already
    is_done==True after their very first action -- a model that finishes in one shot without
    ever needing a continuation has a high early_termination_rate."""
    roots = [r for r in rows if r.get("action_from_parent") == "ROOT"]
    if not roots:
        return None
    return _mean([1.0 if r.get("is_done") else 0.0 for r in roots])


def branch_diversity(rows: list[dict]) -> float | None:
    """Mean, per problem, of (distinct final answers among finished branches) / (finished
    branches) -- 1.0 means every finished branch disagreed, near 0 means they all converged."""
    ratios = []
    for pid, prows in _by_problem(rows).items():
        finished = [r for r in prows if r.get("is_done") and r.get("candidate_answer")]
        if len(finished) < 2:
            continue
        answers = [str(r["candidate_answer"]) for r in finished]
        ratios.append(len(set(answers)) / len(answers))
    return _mean(ratios)


def first_gold_depth_distribution(rows: list[dict]) -> dict[str, Any]:
    """Per-problem first_observed_gold_depth (deduped -- this field is repeated across every
    row of a problem in the gold-joined schema, so we take one value per problem)."""
    values = []
    seen_problems = set()
    for r in rows:
        pid = r["problem_id"]
        if pid in seen_problems:
            continue
        v = r.get("first_observed_gold_depth")
        if v is not None:
            values.append(float(v))
            seen_problems.add(pid)
    return {"n_problems_with_gold": len(values), "mean": _mean(values), "median": _median(values),
            "min": min(values) if values else None, "max": max(values) if values else None}


def first_gold_cost_distribution(rows: list[dict]) -> dict[str, Any]:
    values = []
    seen_problems = set()
    for r in rows:
        pid = r["problem_id"]
        if pid in seen_problems:
            continue
        v = r.get("first_observed_gold_cost")
        if v is not None:
            values.append(float(v))
            seen_problems.add(pid)
    return {"n_problems_with_gold": len(values), "mean": _mean(values), "median": _median(values),
            "min": min(values) if values else None, "max": max(values) if values else None}


def latency_statistics(rows: list[dict]) -> dict[str, float | None]:
    values = [float(r.get("latency_seconds") or 0.0) for r in rows]
    return {"mean_seconds": _mean(values), "median_seconds": _median(values),
            "p90_seconds": _percentile(values, 0.90)}


def token_cost_statistics(rows: list[dict]) -> dict[str, float | None]:
    input_tokens = [float(r.get("tokens_used", {}).get("input_tokens", 0) or 0) for r in rows]
    output_tokens = [float(r.get("tokens_used", {}).get("output_tokens", 0) or 0) for r in rows]
    costs = [float(r.get("monetary_cost_usd") or 0.0) for r in rows]
    mean_in = _mean(input_tokens)
    mean_out = _mean(output_tokens)
    return {
        "mean_input_tokens": mean_in, "mean_output_tokens": mean_out,
        "mean_cost_usd_per_action": _mean(costs),
        "output_to_input_token_ratio": (mean_out / mean_in) if (mean_in and mean_out is not None) else None,
    }


def compute_calibration_features(rows: list[dict]) -> dict[str, Any]:
    """Compute the full feature record for one (provider, model, dataset) group's rows.

    `rows` must already be gold-joined (i.e. loaded from a *_WITH_GOLD_OFFLINE_ONLY.jsonl
    file, or an equivalent in-memory structure with node_produces_gold /
    first_observed_gold_depth / first_observed_gold_cost fields present) -- this function does
    not itself join gold, matching the repo-wide discipline that gold joining only ever
    happens in postprocess_oracle_tree_gold_labels.py.
    """
    if not rows:
        return {"n_rows": 0, "n_problems": 0}
    providers = {r.get("provider") for r in rows}
    models = {r.get("model") for r in rows}
    datasets = {r.get("dataset") for r in rows}
    return {
        "n_rows": len(rows),
        "n_problems": len(_by_problem(rows)),
        "provider": sorted(providers) if len(providers) > 1 else next(iter(providers), None),
        "model": sorted(models) if len(models) > 1 else next(iter(models), None),
        "dataset": sorted(datasets) if len(datasets) > 1 else next(iter(datasets), None),
        "single_sample_accuracy": single_sample_accuracy(rows),
        "stochastic_disagreement_rate": stochastic_disagreement_rate(rows),
        "self_consistency_gain": self_consistency_gain(rows),
        "continuation_value": action_type_cost_normalized_value(rows, "continuation"),
        "restart_value": action_type_cost_normalized_value(rows, "stochastic_restart"),
        "explicit_strategy_value": action_type_cost_normalized_value(rows, "explicit_strategy"),
        "verification_value": action_type_cost_normalized_value(rows, "verification"),
        "mean_reasoning_length_tokens": mean_reasoning_length_tokens(rows),
        "early_termination_rate": early_termination_rate(rows),
        "branch_diversity": branch_diversity(rows),
        "first_gold_depth_distribution": first_gold_depth_distribution(rows),
        "first_gold_cost_distribution": first_gold_cost_distribution(rows),
        "latency_statistics": latency_statistics(rows),
        "token_cost_statistics": token_cost_statistics(rows),
    }


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Compute one model behavioral-calibration feature record.")
    ap.add_argument("--gold-joined-log", required=True, help="A *_WITH_GOLD_OFFLINE_ONLY.jsonl file.")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = load_jsonl(Path(args.gold_joined_log))
    features = compute_calibration_features(rows)
    Path(args.out).write_text(json.dumps(features, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(features, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
