#!/usr/bin/env python3
"""Run a bundled oracle-distilled regime evaluation package.

This orchestration script reuses existing builders/trainers/comparison scripts to run:
- anchor baseline,
- one selective regime run,
- repeated matched-random baseline runs for the same regime,
- one comparison summary package.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run(cmd: list[str], *, dry_run: bool, cwd: Path, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = " ".join(shlex.quote(c) for c in cmd)
    if dry_run:
        log_path.write_text(f"[dry-run] {line}\n", encoding="utf-8")
        return 0

    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    log_path.write_text(
        f"$ {line}\n\n[stdout]\n{proc.stdout}\n\n[stderr]\n{proc.stderr}\n",
        encoding="utf-8",
    )
    return int(proc.returncode)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bundled oracle-distilled regime package")
    p.add_argument("--distill-dataset", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--regime", choices=["accepted_only", "accepted_plus_borderline"], required=True)
    p.add_argument("--seed", type=int, default=31)
    p.add_argument("--num-random-draws", type=int, default=3)
    p.add_argument("--random-seed-base", type=int, default=701)
    p.add_argument("--random-seed-step", type=int, default=17)
    p.add_argument("--stratify-by", default="budget")
    p.add_argument("--run-prefix", default="bundle")
    p.add_argument("--model-kind", choices=["logistic", "gbdt"], default="logistic")
    p.add_argument("--uncertain-policy", choices=["none", "filter", "downweight", "downweight_nonpositive"], default="none")
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def _regime_train_buckets(regime: str) -> str:
    if regime == "accepted_only":
        return "accepted"
    if regime == "accepted_plus_borderline":
        return "accepted,borderline"
    raise ValueError(regime)


def _regime_role(regime: str) -> str:
    if regime == "accepted_only":
        return "oracle_distilled_accepted_only"
    if regime == "accepted_plus_borderline":
        return "oracle_distilled_accepted_plus_borderline"
    raise ValueError(regime)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = REPO_ROOT / "scripts"
    logs_dir = out_dir / "logs"

    random_dir = out_dir / "random_draws"
    random_summary = out_dir / "random_draws_summary.json"

    selective_run_dir = out_dir / "run_selective"
    anchor_run_dir = out_dir / "run_anchor_default"
    compare_dir = out_dir / "comparison"

    train_buckets = _regime_train_buckets(args.regime)
    regime_role = _regime_role(args.regime)

    commands: list[dict[str, Any]] = []

    # 1) Build repeated random draws for this regime.
    cmd_build = [
        "python",
        str(scripts_dir / "build_random_matched_coverage_oracle_distillation_dataset.py"),
        "--input-jsonl",
        args.distill_dataset,
        "--summary-json",
        str(random_summary),
        "--target-regime",
        args.regime,
        "--num-draws",
        str(args.num_random_draws),
        "--seed",
        str(args.random_seed_base),
        "--seed-step",
        str(args.random_seed_step),
        "--output-dir",
        str(random_dir),
        "--output-prefix",
        f"{args.regime}_random",
    ]
    if args.stratify_by:
        cmd_build += ["--stratify-by", args.stratify_by]
    commands.append({"name": "build_random_draws", "cmd": cmd_build, "log": str(logs_dir / "01_build_random.log")})

    # 2) Train anchor baseline.
    cmd_anchor = [
        "python",
        str(scripts_dir / "train_oracle_distilled_stop_vs_act_student.py"),
        "--distill-dataset",
        args.distill_dataset,
        "--output-dir",
        str(anchor_run_dir),
        "--run-name",
        f"{args.run_prefix}_anchor_default",
        "--train-buckets",
        "accepted,borderline,rejected",
        "--eval-buckets",
        "accepted,borderline,rejected",
        "--train-selection-mode",
        "bucket",
        "--model-kind",
        args.model_kind,
        "--uncertain-policy",
        args.uncertain_policy,
        "--decision-threshold",
        str(args.decision_threshold),
        "--seed",
        str(args.seed),
        "--filter-policy",
        "anchor_default",
        "--provenance-tag",
        "bundle_runner",
    ]
    commands.append({"name": "train_anchor", "cmd": cmd_anchor, "log": str(logs_dir / "02_train_anchor.log")})

    # 3) Train selective run.
    cmd_selective = [
        "python",
        str(scripts_dir / "train_oracle_distilled_stop_vs_act_student.py"),
        "--distill-dataset",
        args.distill_dataset,
        "--output-dir",
        str(selective_run_dir),
        "--run-name",
        f"{args.run_prefix}_{args.regime}_selective",
        "--train-buckets",
        train_buckets,
        "--eval-buckets",
        "accepted,borderline,rejected",
        "--train-selection-mode",
        "bucket",
        "--model-kind",
        args.model_kind,
        "--uncertain-policy",
        args.uncertain_policy,
        "--decision-threshold",
        str(args.decision_threshold),
        "--seed",
        str(args.seed),
        "--filter-policy",
        regime_role,
        "--provenance-tag",
        "bundle_runner",
    ]
    commands.append({"name": "train_selective", "cmd": cmd_selective, "log": str(logs_dir / "03_train_selective.log")})

    # Execute first three commands before we know draw paths.
    command_results: list[dict[str, Any]] = []
    for item in commands:
        rc = _run(item["cmd"], dry_run=args.dry_run, cwd=REPO_ROOT, log_path=Path(item["log"]))
        out = dict(item)
        out["return_code"] = rc
        command_results.append(out)
        if rc != 0:
            _write_json(out_dir / "bundle_manifest.json", {"status": "failed", "command_results": command_results})
            raise SystemExit(rc)

    draw_rows: list[dict[str, Any]] = []
    if not args.dry_run:
        random_payload = json.loads(random_summary.read_text(encoding="utf-8"))
        draw_rows = list(random_payload.get("draws", []))
    else:
        for i in range(args.num_random_draws):
            seed_i = int(args.random_seed_base + i * args.random_seed_step)
            draw_rows.append(
                {
                    "draw_index": i,
                    "random_seed": seed_i,
                    "output_jsonl": str(random_dir / f"{args.regime}_random_draw_{i:03d}_seed_{seed_i}.jsonl"),
                }
            )

    random_summary_paths: list[str] = []
    for draw in draw_rows:
        draw_idx = int(draw["draw_index"])
        draw_seed = int(draw["random_seed"])
        draw_dataset = str(draw["output_jsonl"])
        run_dir = out_dir / f"run_random_draw_{draw_idx:03d}"
        cmd_random = [
            "python",
            str(scripts_dir / "train_oracle_distilled_stop_vs_act_student.py"),
            "--distill-dataset",
            draw_dataset,
            "--output-dir",
            str(run_dir),
            "--run-name",
            f"{args.run_prefix}_{args.regime}_random_draw_{draw_idx:03d}_seed_{draw_seed}",
            "--train-buckets",
            "accepted,borderline,rejected",
            "--eval-buckets",
            "accepted,borderline,rejected",
            "--train-selection-mode",
            "selected_flag",
            "--model-kind",
            args.model_kind,
            "--uncertain-policy",
            args.uncertain_policy,
            "--decision-threshold",
            str(args.decision_threshold),
            "--seed",
            str(args.seed),
            "--filter-policy",
            "random_matched_coverage_baseline",
            "--random-baseline-source",
            args.regime,
            "--provenance-tag",
            "bundle_runner",
        ]
        log = logs_dir / f"04_train_random_draw_{draw_idx:03d}.log"
        rc = _run(cmd_random, dry_run=args.dry_run, cwd=REPO_ROOT, log_path=log)
        result = {"name": f"train_random_draw_{draw_idx:03d}", "cmd": cmd_random, "log": str(log), "return_code": rc}
        command_results.append(result)
        if rc != 0:
            _write_json(out_dir / "bundle_manifest.json", {"status": "failed", "command_results": command_results})
            raise SystemExit(rc)
        random_summary_paths.append(str(run_dir / "oracle_distilled_student_summary.json"))

    summary_paths = [
        str(anchor_run_dir / "oracle_distilled_student_summary.json"),
        str(selective_run_dir / "oracle_distilled_student_summary.json"),
        *random_summary_paths,
    ]

    compare_cmd = [
        "python",
        str(scripts_dir / "compare_oracle_distilled_stop_vs_act_runs.py"),
        "--output-dir",
        str(compare_dir),
        "--min-random-draws-per-regime",
        str(args.num_random_draws),
        "--required-roles",
        f"anchor_default,{regime_role},random_matched_coverage_baseline",
        "--summaries",
        *summary_paths,
    ]
    rc = _run(compare_cmd, dry_run=args.dry_run, cwd=REPO_ROOT, log_path=logs_dir / "05_compare.log")
    command_results.append({"name": "compare_bundle", "cmd": compare_cmd, "log": str(logs_dir / "05_compare.log"), "return_code": rc})
    if rc != 0:
        _write_json(out_dir / "bundle_manifest.json", {"status": "failed", "command_results": command_results})
        raise SystemExit(rc)

    manifest = {
        "status": "ok",
        "bundle_kind": "oracle_distilled_regime_bundle",
        "regime": args.regime,
        "distill_dataset": args.distill_dataset,
        "output_dir": str(out_dir),
        "num_random_draws": int(args.num_random_draws),
        "random_seed_base": int(args.random_seed_base),
        "random_seed_step": int(args.random_seed_step),
        "child_artifacts": {
            "random_draw_builder_summary": str(random_summary),
            "anchor_summary": str(anchor_run_dir / "oracle_distilled_student_summary.json"),
            "selective_summary": str(selective_run_dir / "oracle_distilled_student_summary.json"),
            "random_draw_summaries": random_summary_paths,
            "comparison_summary": str(compare_dir / "oracle_distilled_student_comparison_summary.json"),
            "comparison_markdown": str(compare_dir / "oracle_distilled_student_comparison.md"),
        },
        "command_results": command_results,
        "safety": {
            "non_claim_mode": True,
            "warning": "Bundled orchestration path only; oracle-performance claims require real validated pilot labels.",
        },
    }
    _write_json(out_dir / "bundle_manifest.json", manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
