#!/usr/bin/env python3
"""Assess and prepare external reasoning datasets for the new-paper track.

Outputs lightweight readiness artifacts and normalized previews only (no raw dumps).
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.external_reasoning_datasets import run_external_reasoning_dataset_inspection

ROLE_MAP = {"high": 3, "medium": 2, "medium_high": 2, "low": 1, "high_low": 1, None: 0}
DISTANCE_MAP = {"low": 3, "medium": 2, "medium_high": 1, "high": 0, None: 0}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare external reasoning datasets for new-paper track")
    parser.add_argument("--output-root", default="outputs/prepared_reasoning_datasets")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-rows", type=int, default=16)
    parser.add_argument("--preview-per-dataset", type=int, default=20)
    return parser.parse_args()


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _to_text(value: Any, max_len: int = 1200) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").strip()
    text = " ".join(text.split())
    return text[:max_len]


def _clean_pair(a: str, b: str) -> tuple[str, str]:
    return _to_text(a), _to_text(b)


def _normalize_record(dataset_key: str, row: dict[str, Any], supervision_type: str) -> dict[str, Any]:
    prompt = _to_text(
        row.get("question")
        or row.get("problem")
        or row.get("prompt")
        or row.get("instruction")
        or row.get("task")
        or row.get("question_body")
        or row.get("input")
    )

    if supervision_type in {"step_supervision", "process_reward"}:
        trajectory = _to_text(row.get("solution") or row.get("response") or row.get("answer") or row.get("steps"))
        label = row.get("label") or row.get("labels") or row.get("step_labels") or row.get("correctness")
        return {
            "dataset_key": dataset_key,
            "normalized_type": "step_supervision",
            "prompt": prompt,
            "trajectory": trajectory,
            "step_labels": _to_text(label, max_len=1600),
        }

    if supervision_type in {"pairwise_preference", "judge_preference"}:
        chosen, rejected = _clean_pair(
            row.get("chosen") or row.get("answer1_body") or row.get("conversation_a") or row.get("orig_response_A"),
            row.get("rejected") or row.get("answer2_body") or row.get("conversation_b") or row.get("orig_response_B"),
        )
        winner = _to_text(row.get("winner") or row.get("score") or row.get("orig_preference"))
        return {
            "dataset_key": dataset_key,
            "normalized_type": "pairwise_preference",
            "prompt": prompt,
            "chosen": chosen,
            "rejected": rejected,
            "winner_or_score": winner,
        }

    if supervision_type == "verifier_supervision":
        candidate = _to_text(row.get("response") or row.get("answer") or row.get("output") or row.get("completion"))
        verdict = _to_text(row.get("correctness") or row.get("label") or row.get("score") or row.get("feedback"))
        rubric = _to_text(row.get("rubric") or row.get("criteria") or row.get("instruction"))
        return {
            "dataset_key": dataset_key,
            "normalized_type": "verifier_supervision",
            "prompt": prompt,
            "candidate_response": candidate,
            "verdict_signal": verdict,
            "rubric_or_context": rubric,
        }

    response = _to_text(row.get("response") or row.get("answer") or row.get("output") or row.get("table"))
    return {
        "dataset_key": dataset_key,
        "normalized_type": "trajectory_supervision",
        "prompt": prompt,
        "trajectory": response,
    }


def _quality_score(row: dict[str, Any]) -> int:
    score = 0
    if row.get("access_ok"):
        score += 2
    if row.get("row_count"):
        score += 1
    if row.get("schema_fields"):
        score += 1
    if row.get("error"):
        score -= 1
    return max(score, 0)


def _ease_score(row: dict[str, Any]) -> int:
    score = 0
    schema_fields = row.get("schema_fields") or []
    if row.get("access_ok"):
        score += 2
    if len(schema_fields) <= 18 and len(schema_fields) > 0:
        score += 1
    if row.get("selected_split") in {"train", "default", "human", "train_positives"}:
        score += 1
    if row.get("error"):
        score -= 1
    return max(score, 0)


def _role_score(usefulness: dict[str, Any], key: str) -> int:
    return ROLE_MAP.get(usefulness.get(key), 1)


def _distance_score(usefulness: dict[str, Any]) -> int:
    return DISTANCE_MAP.get(usefulness.get("frontier_allocation_label_distance"), 1)


def _tier(total_score: int, direct_relevance: int) -> str:
    if total_score >= 19 and direct_relevance >= 2:
        return "Tier 1: Use now"
    if total_score >= 14:
        return "Tier 2: Promising backup"
    return "Tier 3: Low priority / not worth using now"


def _recommendation(role_scores: dict[str, int], tier: str) -> str:
    if tier.startswith("Tier 1"):
        if role_scores["pairwise_branch_ranking"] >= 3:
            return "Use now for pairwise branch ranking and verifier auxiliary tuning."
        if role_scores["branch_scoring"] >= 3 or role_scores["verifier_training"] >= 3:
            return "Use now for branch scoring/verifier pretraining; combine with repo-specific labels later."
        return "Use now as trajectory/process auxiliary supervision."
    if tier.startswith("Tier 2"):
        return "Keep as backup or mix-in regularizer after Tier 1 baselines are stable."
    return "Defer for this paper unless Tier 1/2 access fails."


def main() -> None:
    args = parse_args()
    run_id = args.run_id or _default_run_id()
    out_dir = Path(args.output_root) / run_id
    previews_dir = out_dir / "normalized_previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)

    inspection = run_external_reasoning_dataset_inspection(sample_rows=args.sample_rows)
    ranking_rows: list[dict[str, Any]] = []
    schema_rows: list[dict[str, Any]] = []

    for row in inspection["results"]:
        usefulness = row.get("usefulness", {})
        role_scores = {
            "branch_scoring": _role_score(usefulness, "branch_scoring"),
            "verifier_training": _role_score(usefulness, "verifier_training"),
            "pairwise_branch_ranking": _role_score(usefulness, "pairwise_branch_ranking"),
            "trajectory_supervision": _role_score(usefulness, "trajectory_supervision"),
        }
        quality_score = _quality_score(row)
        ease_score = _ease_score(row)
        direct_relevance = _distance_score(usefulness)
        total_score = quality_score + ease_score + direct_relevance + sum(role_scores.values())
        tier = _tier(total_score, direct_relevance)
        recommendation = _recommendation(role_scores, tier)

        ranking_rows.append(
            {
                "dataset_key": row["dataset_key"],
                "hf_dataset_id": row["hf_dataset_id"],
                "supervision_type": row["supervision_type"],
                "access_ok": row.get("access_ok"),
                "quality_score_0_4": quality_score,
                "ease_of_use_score_0_4": ease_score,
                "direct_relevance_score_0_3": direct_relevance,
                "branch_scoring_score_1_3": role_scores["branch_scoring"],
                "verifier_training_score_1_3": role_scores["verifier_training"],
                "pairwise_branch_ranking_score_1_3": role_scores["pairwise_branch_ranking"],
                "trajectory_supervision_score_1_3": role_scores["trajectory_supervision"],
                "total_score": total_score,
                "tier": tier,
                "recommendation": recommendation,
                "caveat": row.get("chosen_variant_reason") or "",
            }
        )

        schema_rows.append(
            {
                "dataset_key": row["dataset_key"],
                "hf_dataset_id": row["hf_dataset_id"],
                "supervision_type": row["supervision_type"],
                "selected_config": row.get("selected_config"),
                "selected_split": row.get("selected_split"),
                "row_count_selected_split": row.get("row_count"),
                "schema_fields": "|".join(row.get("schema_fields", [])),
                "normalization_target": (
                    "pairwise_preference"
                    if row["supervision_type"] in {"pairwise_preference", "judge_preference"}
                    else row["supervision_type"]
                ),
            }
        )

        normalized = [
            _normalize_record(row["dataset_key"], sample, row["supervision_type"])
            for sample in row.get("normalization_preview", [])[: args.preview_per_dataset]
            if isinstance(sample, dict)
        ]
        if normalized:
            preview_path = previews_dir / f"{row['dataset_key']}.jsonl"
            with preview_path.open("w", encoding="utf-8") as f:
                for record in normalized:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

    for candidate in inspection.get("candidate_audit", []):
        if candidate.get("integration_status") != "not_integrated":
            continue
        ranking_rows.append(
            {
                "dataset_key": candidate.get("candidate_name", "unknown_candidate").lower().replace(" ", "_"),
                "hf_dataset_id": candidate.get("chosen_source"),
                "supervision_type": "not_integrated_candidate",
                "access_ok": False,
                "quality_score_0_4": 0,
                "ease_of_use_score_0_4": 0,
                "direct_relevance_score_0_3": 0,
                "branch_scoring_score_1_3": 1,
                "verifier_training_score_1_3": 1,
                "pairwise_branch_ranking_score_1_3": 1,
                "trajectory_supervision_score_1_3": 1,
                "total_score": 4,
                "tier": "Tier 3: Low priority / not worth using now",
                "recommendation": "Not integrated; ignore for current paper unless a stable public dataset artifact appears.",
                "caveat": candidate.get("reason", ""),
            }
        )

    ranking_rows.sort(key=lambda x: x["total_score"], reverse=True)

    csv_rank = out_dir / "dataset_readiness_ranking.csv"
    with csv_rank.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(ranking_rows[0].keys()))
        writer.writeheader()
        writer.writerows(ranking_rows)

    csv_schema = out_dir / "normalized_schema_summary.csv"
    with csv_schema.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(schema_rows[0].keys()))
        writer.writeheader()
        writer.writerows(schema_rows)

    tier_groups: dict[str, list[str]] = {}
    for row in ranking_rows:
        tier_groups.setdefault(row["tier"], []).append(row["dataset_key"])

    top_branch = [r["dataset_key"] for r in ranking_rows if r["branch_scoring_score_1_3"] >= 3][:3]
    top_verifier = [r["dataset_key"] for r in ranking_rows if r["verifier_training_score_1_3"] >= 3][:4]
    top_pairwise = [r["dataset_key"] for r in ranking_rows if r["pairwise_branch_ranking_score_1_3"] >= 3][:4]
    top_trajectory = [r["dataset_key"] for r in ranking_rows if r["trajectory_supervision_score_1_3"] >= 3][:4]

    recommendations = {
        "branch_scoring_first": top_branch,
        "verifier_training_first": top_verifier,
        "pairwise_branch_ranking_first": top_pairwise,
        "trajectory_process_supervision_first": top_trajectory,
        "combine_or_single": "Combine Tier 1 pairwise + step/verifier datasets; do not rely on a single external source.",
        "external_only_sufficiency": (
            "External datasets are useful for warm-start supervision, but not sufficient for final frontier-allocation labels; "
            "retain repo-specific oracle branch labels and continuation-value labels."
        ),
        "deprioritize_for_now": [r["dataset_key"] for r in ranking_rows if r["tier"].startswith("Tier 3")],
    }

    prep_report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "dataset_count": len(ranking_rows),
        "all_access_ok": inspection.get("all_access_ok"),
        "tiers": tier_groups,
        "ranking": ranking_rows,
        "normalized_schema_summary": schema_rows,
        "candidate_audit": inspection.get("candidate_audit", []),
        "recommendations": recommendations,
    }

    json_path = out_dir / "dataset_preparation_report.json"
    json_path.write_text(json.dumps(prep_report, indent=2), encoding="utf-8")

    md_path = out_dir / "dataset_preparation_report.md"
    lines = [
        "# External reasoning datasets: readiness + preparation report",
        "",
        f"- Run id: `{run_id}`",
        f"- Generated UTC: `{prep_report['created_utc']}`",
        f"- Dataset count: `{prep_report['dataset_count']}`",
        f"- All access ok: `{prep_report['all_access_ok']}`",
        "",
        "## Tier summary",
        "",
    ]
    for tier, keys in tier_groups.items():
        lines.append(f"- **{tier}**: `{keys}`")

    lines.extend(
        [
            "",
            "## Readiness ranking",
            "",
            "| dataset_key | supervision_type | total_score | tier | branch | verifier | pairwise | trajectory |",
            "|---|---|---:|---|---:|---:|---:|---:|",
        ]
    )

    for row in ranking_rows:
        lines.append(
            f"| `{row['dataset_key']}` | `{row['supervision_type']}` | {row['total_score']} | {row['tier']} | "
            f"{row['branch_scoring_score_1_3']} | {row['verifier_training_score_1_3']} | "
            f"{row['pairwise_branch_ranking_score_1_3']} | {row['trajectory_supervision_score_1_3']} |"
        )

    lines.extend(
        [
            "",
            "## Concrete usage recommendation (new-paper track)",
            "",
            f"- Branch scoring first: `{recommendations['branch_scoring_first']}`",
            f"- Verifier training first: `{recommendations['verifier_training_first']}`",
            f"- Pairwise branch ranking first: `{recommendations['pairwise_branch_ranking_first']}`",
            f"- Trajectory/process supervision first: `{recommendations['trajectory_process_supervision_first']}`",
            f"- Combine strategy: {recommendations['combine_or_single']}",
            f"- External-only sufficiency: {recommendations['external_only_sufficiency']}",
            f"- Deprioritize now: `{recommendations['deprioritize_for_now']}`",
            "",
            "## Candidate audit notes",
            "",
        ]
    )
    for row in prep_report["candidate_audit"]:
        lines.append(
            f"- `{row['candidate_name']}` → status=`{row['integration_status']}`; source=`{row['chosen_source']}`; reason={row['reason']}"
        )

    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- `{json_path}`",
            f"- `{md_path}`",
            f"- `{csv_rank}`",
            f"- `{csv_schema}`",
            f"- normalized previews under `{previews_dir}`",
            "",
            "No raw dataset dumps were created; only lightweight normalized previews were written.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "run_id": run_id,
                "output_dir": str(out_dir),
                "dataset_preparation_report_json": str(json_path),
                "dataset_preparation_report_md": str(md_path),
                "dataset_readiness_ranking_csv": str(csv_rank),
                "normalized_schema_summary_csv": str(csv_schema),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
