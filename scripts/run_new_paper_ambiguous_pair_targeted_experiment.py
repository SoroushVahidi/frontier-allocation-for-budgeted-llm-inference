#!/usr/bin/env python3
"""Bounded targeted adaptation using curated ambiguous-branch pairs (new-paper)."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.controllers import AdaptiveController
from experiments.frontier_matrix_core import build_frontier_strategies, evaluate_strategies_on_examples, generator_factory_for_mode, load_pilot_examples
from experiments.scoring import LearnedBTBranchScorer, TieAwareBTBranchScorer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run ambiguous-pair targeted adaptation experiment")
    p.add_argument("--output-root", default="outputs/new_paper/ambiguous_pair_targeted_experiment")
    p.add_argument("--run-id", default=None)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--seed", type=int, default=111)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=140)
    p.add_argument("--oracle-episodes", type=int, default=30)
    p.add_argument("--max-ambiguous-pairs", type=int, default=520)
    p.add_argument("--ambiguous-repeat-factor", type=int, default=4)
    p.add_argument("--overall-eval-seeds", default="111,112")
    p.add_argument("--overall-subset-size", type=int, default=18)
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _linear_score(model: dict[str, Any], feats: dict[str, float]) -> float:
    s = float(model.get("intercept", 0.0))
    for name, w in model.get("weights", {}).items():
        s += float(w) * float(feats.get(name, 0.0))
    return s


def _pref(delta: float, tie_margin: float = 0.02) -> int:
    if abs(delta) <= tie_margin:
        return 0
    return 1 if delta > 0 else -1


def _canonical_pref(a: str, b: str, pref_a_vs_b: int) -> int:
    lo = sorted([str(a), str(b)])[0]
    return int(pref_a_vs_b) if str(a) == lo else int(-pref_a_vs_b)


def _pair_key(ep: int, dec: int, a: str, b: str) -> str:
    x, y = sorted([str(a), str(b)])
    return f"{int(ep)}|{int(dec)}|{x}|{y}"


def _controller_eval(
    seed: int,
    dataset: str,
    subset_size: int,
    budget: int,
    baseline_model: Path,
    target_model: Path,
    raokupper_model: Path,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    examples = load_pilot_examples(dataset, subset_size, seed)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)

    base_specs = build_frontier_strategies(
        gen_factory,
        budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        bt_pairwise_model_path=str(baseline_model),
    )

    strategies: dict[str, Any] = {
        "adaptive_bt_pairwise_proxy": base_specs["adaptive_bt_pairwise"],
        "adaptive_bt_pairwise_targeted": AdaptiveController(
            gen_factory(), LearnedBTBranchScorer(target_model, max_actions_per_problem=budget), budget,
            high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_targeted",
        ),
        "adaptive_bt_pairwise_tie_aware_raokupper": AdaptiveController(
            gen_factory(), TieAwareBTBranchScorer(raokupper_model, max_actions_per_problem=budget), budget,
            high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_tie_aware_raokupper",
        ),
    }
    metrics, _ = evaluate_strategies_on_examples(examples, strategies)
    out: list[dict[str, Any]] = []
    for method, m in metrics.items():
        out.append({"seed": seed, "method": method, "accuracy": float(m["accuracy"]), "avg_actions": float(m["avg_actions"])})
    return out


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: build/refresh ambiguous dataset asset (starting point for this targeted path).
    source_root = run_dir / "ambiguous_dataset_source"
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/run_new_paper_ambiguous_branch_dataset.py"),
        "--output-root",
        str(source_root),
        "--run-id",
        "source",
        "--seed",
        str(args.seed),
        "--budget",
        str(args.budget),
        "--ranking-episodes",
        str(args.ranking_episodes),
        "--oracle-episodes",
        str(args.oracle_episodes),
        "--max-pairs",
        str(args.max_ambiguous_pairs),
    ])

    source_dir = source_root / "source"
    source_manifest = _load_json(source_dir / "run_manifest.json")
    ambiguous_rows = _load_jsonl(source_dir / "ambiguous_branch_pairs.jsonl")
    pairwise_path = Path(source_manifest["input_artifacts"]["pairwise_dataset"])
    bt_model_path = Path(source_manifest["input_artifacts"]["bt_model"])
    rk_model_path = Path(source_manifest["input_artifacts"]["raokupper_model"])
    oracle_branch_labels_path = Path(source_manifest["input_artifacts"]["oracle_branch_labels"])
    oracle_pairwise_path = Path(source_manifest["input_artifacts"]["oracle_pairwise_preferences"])

    pair_rows = _load_jsonl(pairwise_path)
    amb_pair_keys = {str(r["pair_key"]) for r in ambiguous_rows if str(r.get("source_group")) == "pairwise_bt_dataset"}

    # Step 2: create cheap targeted reweighting dataset (duplicate ambiguous train pairs).
    reweighted_rows: list[dict[str, Any]] = []
    duplicated = 0
    for row in pair_rows:
        reweighted_rows.append(row)
        key = _pair_key(int(row["episode_id"]), int(row["decision_id"]), str(row["branch_a_id"]), str(row["branch_b_id"]))
        if row.get("split") == "train" and key in amb_pair_keys:
            for _ in range(max(0, int(args.ambiguous_repeat_factor) - 1)):
                reweighted_rows.append(row)
                duplicated += 1
    reweighted_path = run_dir / "pairwise_dataset_ambiguous_reweighted.jsonl"
    _write_jsonl(reweighted_path, reweighted_rows)

    targeted_model_path = run_dir / "model_bt_ambiguous_reweighted.json"
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(reweighted_path),
        "--output",
        str(targeted_model_path),
        "--seed",
        str(args.seed),
        "--objective",
        "bt",
    ])

    # Step 3: ambiguous-slice comparison vs oracle-ish reference.
    bt_model = _load_json(bt_model_path)
    rk_model = _load_json(rk_model_path)
    targeted_model = _load_json(targeted_model_path)

    oracle_branch_rows = _load_jsonl(oracle_branch_labels_path)
    oracle_pair_rows = _load_jsonl(oracle_pairwise_path)
    curated_by_key = {str(r["pair_key"]): r for r in ambiguous_rows}

    branch_map: dict[str, dict[str, Any]] = {}
    for row in oracle_branch_rows:
        branch_map[f"{int(row['episode_id'])}|{int(row['decision_id'])}|{row['branch_id']}"] = row

    oracle_slice_rows: list[dict[str, Any]] = []
    for row in oracle_pair_rows:
        key = _pair_key(int(row["episode_id"]), int(row["decision_id"]), str(row["branch_a_id"]), str(row["branch_b_id"]))
        curated = curated_by_key.get(key)
        if curated is None or not bool(curated.get("has_oracle_reference")):
            continue
        oracle_pref = int(row.get("oracle_preference", 0))
        if oracle_pref == 0:
            continue

        a_branch = branch_map.get(f"{int(row['episode_id'])}|{int(row['decision_id'])}|{row['branch_a_id']}")
        b_branch = branch_map.get(f"{int(row['episode_id'])}|{int(row['decision_id'])}|{row['branch_b_id']}")
        if a_branch is None or b_branch is None:
            continue
        feats_a = a_branch.get("features_v7", {})
        feats_b = b_branch.get("features_v7", {})

        proxy_pref = _canonical_pref(str(row["branch_a_id"]), str(row["branch_b_id"]), int(row.get("proxy_preference", 0)))
        bt_pref = _canonical_pref(str(row["branch_a_id"]), str(row["branch_b_id"]), _pref(_linear_score(bt_model, feats_a) - _linear_score(bt_model, feats_b)))
        rk_pref = _canonical_pref(str(row["branch_a_id"]), str(row["branch_b_id"]), _pref(_linear_score(rk_model, feats_a) - _linear_score(rk_model, feats_b)))
        tgt_pref = _canonical_pref(str(row["branch_a_id"]), str(row["branch_b_id"]), _pref(_linear_score(targeted_model, feats_a) - _linear_score(targeted_model, feats_b)))
        oracle_pref_can = _canonical_pref(str(row["branch_a_id"]), str(row["branch_b_id"]), oracle_pref)

        oracle_slice_rows.append(
            {
                "pair_key": key,
                "quality_tier": curated.get("quality_tier", "C"),
                "reason_codes": "|".join(curated.get("reason_codes", [])),
                "oracle_preference_canonical": oracle_pref_can,
                "proxy_preference_canonical": proxy_pref,
                "proxy_bt_preference_canonical": bt_pref,
                "raokupper_preference_canonical": rk_pref,
                "targeted_preference_canonical": tgt_pref,
            }
        )

    _write_csv(run_dir / "ambiguous_slice_comparison.csv", oracle_slice_rows)

    def _agreement(field: str) -> float:
        if not oracle_slice_rows:
            return 0.0
        return sum(1 for r in oracle_slice_rows if int(r[field]) == int(r["oracle_preference_canonical"])) / len(oracle_slice_rows)

    ambiguous_method_rows = [
        {"scope": "ambiguous_slice", "method": "proxy_preference", "metric": "agreement_vs_oracle", "value": _agreement("proxy_preference_canonical"), "n": len(oracle_slice_rows)},
        {"scope": "ambiguous_slice", "method": "proxy_bt", "metric": "agreement_vs_oracle", "value": _agreement("proxy_bt_preference_canonical"), "n": len(oracle_slice_rows)},
        {"scope": "ambiguous_slice", "method": "raokupper", "metric": "agreement_vs_oracle", "value": _agreement("raokupper_preference_canonical"), "n": len(oracle_slice_rows)},
        {"scope": "ambiguous_slice", "method": "targeted_bt_reweighted", "metric": "agreement_vs_oracle", "value": _agreement("targeted_preference_canonical"), "n": len(oracle_slice_rows)},
    ]

    # Step 4: cheap overall bounded controller comparison.
    overall_rows: list[dict[str, Any]] = []
    eval_seeds = [int(x.strip()) for x in args.overall_eval_seeds.split(",") if x.strip()]
    for s in eval_seeds:
        overall_rows.extend(
            _controller_eval(
                seed=s,
                dataset=args.dataset,
                subset_size=args.overall_subset_size,
                budget=args.budget,
                baseline_model=bt_model_path,
                target_model=targeted_model_path,
                raokupper_model=rk_model_path,
            )
        )
    _write_csv(run_dir / "method_metrics.csv", overall_rows)

    method_to_vals: dict[str, list[float]] = {}
    for r in overall_rows:
        method_to_vals.setdefault(str(r["method"]), []).append(float(r["accuracy"]))
    overall_mean = {k: (sum(v) / len(v)) for k, v in method_to_vals.items()}
    proxy_overall = overall_mean.get("adaptive_bt_pairwise_proxy", 0.0)

    summary_rows = []
    for m, acc in sorted(overall_mean.items()):
        mapped = {
            "adaptive_bt_pairwise_proxy": "proxy_bt",
            "adaptive_bt_pairwise_tie_aware_raokupper": "raokupper",
            "adaptive_bt_pairwise_targeted": "targeted_bt_reweighted",
        }.get(m, m)
        amb = next((float(r["value"]) for r in ambiguous_method_rows if r["method"] == mapped), None)
        summary_rows.append(
            {
                "method": mapped,
                "overall_mean_accuracy": acc,
                "overall_delta_vs_proxy_bt": acc - proxy_overall,
                "ambiguous_agreement_vs_oracle": amb,
            }
        )
    _write_csv(run_dir / "overall_vs_ambiguous_summary.csv", summary_rows)

    all_metrics = list(ambiguous_method_rows)
    for m, acc in overall_mean.items():
        all_metrics.append({"scope": "overall_controller", "method": m, "metric": "mean_accuracy", "value": acc, "n": len(method_to_vals[m])})
    _write_csv(run_dir / "method_metrics_extended.csv", all_metrics)

    targeted_amb = next(float(r["value"]) for r in ambiguous_method_rows if r["method"] == "targeted_bt_reweighted")
    proxy_amb = next(float(r["value"]) for r in ambiguous_method_rows if r["method"] == "proxy_bt")
    rk_amb = next(float(r["value"]) for r in ambiguous_method_rows if r["method"] == "raokupper")
    targeted_overall = overall_mean.get("adaptive_bt_pairwise_targeted", 0.0)

    interpretation = [
        f"# Ambiguous-pair targeted experiment ({run_id})",
        "",
        "## Setup",
        "- Starting asset: curated ambiguous-branch dataset (source run generated inside this experiment).",
        f"- Targeted adaptation: duplicate ambiguous train pairs by factor={args.ambiguous_repeat_factor} and retrain lightweight BT.",
        f"- Ambiguous oracle-referenced slice size: {len(oracle_slice_rows)}.",
        f"- Overall controller seeds: {eval_seeds} (subset={args.overall_subset_size}).",
        "",
        "## Direct answers",
        f"- Can curated ambiguous data improve hard slice? **{'Yes' if targeted_amb > proxy_amb else 'No/mixed'}** (targeted={targeted_amb:.3f}, proxy_bt={proxy_amb:.3f}).",
        f"- Better than prior lightweight patches? **{'Potentially on hard slice only' if targeted_amb > max(proxy_amb, rk_amb) else 'Not yet'}**.",
        f"- Does it hurt overall? **{'No clear hurt' if targeted_overall >= proxy_overall else 'Yes, slight overall drop'}** (targeted={targeted_overall:.3f}, proxy_bt={proxy_overall:.3f}).",
        "- Is this dataset evaluation-only or also adaptation-useful? **Primarily evaluation + targeted adaptation candidate; still not a gold supervision source.**",
        "- Should this be next low-compute direction? **Yes, for hard-slice-focused iterations with conservative overall checks.**",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interpretation) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "dataset": args.dataset,
        "seed": args.seed,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "oracle_episodes": args.oracle_episodes,
        "ambiguous_repeat_factor": args.ambiguous_repeat_factor,
        "overall_eval_seeds": eval_seeds,
        "overall_subset_size": args.overall_subset_size,
        "source_dataset_dir": str(source_dir),
        "artifacts": {
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "ambiguous_slice_comparison": str(run_dir / "ambiguous_slice_comparison.csv"),
            "overall_vs_ambiguous_summary": str(run_dir / "overall_vs_ambiguous_summary.csv"),
            "run_manifest": str(run_dir / "run_manifest.json"),
            "interpretation": str(run_dir / "interpretation.md"),
        },
        "counts": {
            "n_pairwise_rows_original": len(pair_rows),
            "n_pairwise_rows_reweighted": len(reweighted_rows),
            "n_duplicated_rows": duplicated,
            "n_ambiguous_keys_from_source": len(amb_pair_keys),
            "n_oracle_ambiguous_pairs_eval": len(oracle_slice_rows),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "ambiguous_pairs_eval": len(oracle_slice_rows), "overall_mean": overall_mean}, indent=2))


if __name__ == "__main__":
    main()
