#!/usr/bin/env python3
"""Build a HF-backed import package for when_solve_when_verify.

This script downloads official sc-genrm-scaling MATH128 solution/verification tarballs
and derives a conservative, heuristic SC-vs-GenRM success estimate on a bounded slice.
It emits the repository import contract files: metadata.json and results.csv.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tarfile
from typing import Any

from huggingface_hub import hf_hub_download
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _norm_answer(text: str | None) -> str:
    if text is None:
        return ""
    out = str(text).strip()
    out = out.replace("\\boxed", "")
    out = out.replace("{", "").replace("}", "")
    out = out.replace("$", "").replace(",", "")
    out = re.sub(r"\s+", "", out).lower()
    return out


def _extract_answer(solution_text: str) -> str:
    boxed_matches = re.findall(r"\\boxed\{([^{}]+)\}", solution_text)
    if boxed_matches:
        return _norm_answer(boxed_matches[-1])
    final_matches = re.findall(r"The final answer is:?\s*(.+)", solution_text, flags=re.IGNORECASE)
    if final_matches:
        return _norm_answer(final_matches[-1].split("\n")[0].strip())
    return _norm_answer(solution_text[-64:])


def _verification_score(verif_row: dict[str, Any]) -> float:
    p_yes = verif_row.get("p(yes)", -1)
    p_no = verif_row.get("p(no)", -1)
    try:
        p_yes_f = float(p_yes)
    except Exception:
        p_yes_f = -1.0
    try:
        p_no_f = float(p_no)
    except Exception:
        p_no_f = -1.0
    if p_yes_f >= 0:
        return p_yes_f
    if p_no_f >= 0:
        return 1.0 - p_no_f
    txt = str(verif_row.get("verification", "")).lower()
    if "yes" in txt and "no" not in txt:
        return 1.0
    if "no" in txt and "yes" not in txt:
        return 0.0
    return 0.5


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build HF-backed when_solve_when_verify import package")
    p.add_argument(
        "--output-dir",
        default="outputs/when_solve_when_verify_hf_import_package_20260421T190000Z",
        help="Output directory for metadata.json and results.csv",
    )
    p.add_argument("--num-problems", type=int, default=128)
    p.add_argument("--sc-num-solutions", type=int, default=64)
    p.add_argument("--genrm-num-solutions", type=int, default=32)
    p.add_argument("--genrm-num-verifications", type=int, default=16)
    p.add_argument("--compute-budget-tokens", type=int, default=65536)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = (REPO_ROOT / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    solutions_repo = "sc-genrm-scaling/MATH128_Solutions_Llama-3.1-8B-Instruct"
    solutions_file = "compressed_Llama-3.1-8B-Instruct.tar.gz"
    verifs_repo = "sc-genrm-scaling/MATH128_verifications_GenRM-FT_Llama-3.1-8B-Instruct"
    verifs_file = "compressed_MATH128_verifications_GenRM-FT_Llama-3.1-8B-Instruct.tar.gz"

    sol_tar = Path(
        hf_hub_download(
            repo_id=solutions_repo,
            repo_type="dataset",
            filename=solutions_file,
            local_dir=str(out_dir),
        )
    )
    ver_tar = Path(
        hf_hub_download(
            repo_id=verifs_repo,
            repo_type="dataset",
            filename=verifs_file,
            local_dir=str(out_dir),
        )
    )

    gt: dict[int, str] = {}
    predicted: dict[int, list[str]] = {}
    sc_correct = 0
    genrm_correct = 0

    with tarfile.open(sol_tar, "r:gz") as tf:
        sol_members = {m.name: m for m in tf.getmembers() if m.isfile()}
        for pid in range(args.num_problems):
            member = sol_members[f"Llama-3.1-8B-Instruct/{pid}.yaml"]
            row = yaml.safe_load(tf.extractfile(member).read())
            gt_ans = _norm_answer(str(row.get("gt_answer", "")))
            gt[pid] = gt_ans
            samples = row.get("samples", [])
            pred = [_extract_answer(str(s)) for s in samples]
            predicted[pid] = pred

            # Self-consistency majority over first s solutions.
            chosen = ""
            counts: dict[str, int] = {}
            for ans in pred[: args.sc_num_solutions]:
                counts[ans] = counts.get(ans, 0) + 1
            if counts:
                chosen = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)[0][0]
            if chosen == gt_ans:
                sc_correct += 1

    with tarfile.open(ver_tar, "r:gz") as tf:
        ver_members = {m.name: m for m in tf.getmembers() if m.isfile()}
        for pid in range(args.num_problems):
            best_sol = 0
            best_score = -1.0
            for sid in range(args.genrm_num_solutions):
                m = ver_members[f"data/problem_{pid}/solution_{sid}.yaml"]
                row = yaml.safe_load(tf.extractfile(m).read())
                verifs = row.get("verifications", [])
                vals = [_verification_score(v) for v in verifs[: args.genrm_num_verifications]]
                score = sum(vals) / max(1, len(vals))
                if score > best_score:
                    best_score = score
                    best_sol = sid
            if predicted[pid][best_sol] == gt[pid]:
                genrm_correct += 1

    sc_rate = sc_correct / max(1, args.num_problems)
    genrm_rate = genrm_correct / max(1, args.num_problems)

    artifact_id = f"hf-math128-llama8b-genrmft-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    metadata = {
        "source": {"type": "official"},
        "upstream": {
            "repo_url": "https://github.com/nishadsinghi/sc-genrm-scaling",
            "paper_url": "https://arxiv.org/abs/2504.01005",
            "workflow_stages_completed": [
                "solution_generation",
                "verification_generation",
                "fixed_budget_evaluation",
            ],
            "hf_artifacts": {
                "solutions_dataset": solutions_repo,
                "verifications_dataset": verifs_repo,
                "solutions_tar": solutions_file,
                "verifications_tar": verifs_file,
                "solutions_tar_sha256": _sha256(sol_tar),
                "verifications_tar_sha256": _sha256(ver_tar),
            },
        },
        "dataset": {"name": "math128", "split": "test"},
        "budget": {
            "unit": "tokens",
            "fixed_budget_interpretation": "generator_and_verifier_token_budget_joint",
        },
        "strategy_space": ["self_consistency", "genrm_best_of_n"],
        "evaluation_protocol": {
            "kind": "heuristic_local_recompute_from_official_hf_artifacts",
            "num_problems": args.num_problems,
            "sc_num_solutions": args.sc_num_solutions,
            "genrm_num_solutions": args.genrm_num_solutions,
            "genrm_num_verifications": args.genrm_num_verifications,
            "answer_matching": "simple_normalized_answer_match",
            "warning": "This is an import-backed heuristic recompute and not a claim of full faithful upstream rerun parity.",
        },
        "provenance": {
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_uri": "https://huggingface.co/sc-genrm-scaling",
            "artifact_id": artifact_id,
            "commit_or_version_if_available": "hf-artifact-recompute",
        },
    }

    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    with (out_dir / "results.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "mode",
                "source_type",
                "dataset",
                "split",
                "generator_model",
                "verifier_model",
                "strategy_family",
                "num_solutions",
                "num_verifications",
                "compute_budget_tokens",
                "success_rate",
                "artifact_id",
                "commit_or_version",
                "comparability_scope",
            ],
        )
        w.writeheader()
        w.writerow(
            {
                "mode": "when_solve_when_verify_adjacent_import",
                "source_type": "official",
                "dataset": "math128",
                "split": "test",
                "generator_model": "meta-llama/Llama-3.1-8B-Instruct",
                "verifier_model": "none",
                "strategy_family": "self_consistency",
                "num_solutions": str(args.sc_num_solutions),
                "num_verifications": "0",
                "compute_budget_tokens": str(args.compute_budget_tokens),
                "success_rate": f"{sc_rate:.6f}",
                "artifact_id": artifact_id,
                "commit_or_version": "hf-artifact-recompute",
                "comparability_scope": "adjacent_only",
            }
        )
        w.writerow(
            {
                "mode": "when_solve_when_verify_adjacent_import",
                "source_type": "official",
                "dataset": "math128",
                "split": "test",
                "generator_model": "meta-llama/Llama-3.1-8B-Instruct",
                "verifier_model": "sc-genrm-scaling/llama_3.1_8b_genrm_ft",
                "strategy_family": "genrm_best_of_n",
                "num_solutions": str(args.genrm_num_solutions),
                "num_verifications": str(args.genrm_num_verifications),
                "compute_budget_tokens": str(args.compute_budget_tokens),
                "success_rate": f"{genrm_rate:.6f}",
                "artifact_id": artifact_id,
                "commit_or_version": "hf-artifact-recompute",
                "comparability_scope": "adjacent_only",
            }
        )

    summary = {
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "artifact_id": artifact_id,
        "self_consistency_success_rate": sc_rate,
        "genrm_success_rate": genrm_rate,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
