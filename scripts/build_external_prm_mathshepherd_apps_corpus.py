#!/usr/bin/env python3
"""Build conservative canonical-aligned branch-learning rows from PRM800K, Math-Shepherd, and APPS.

This is an integration/readiness artifact builder (not final training evidence).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from datasets import load_dataset


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _to_list(v: Any) -> list[Any]:
    if isinstance(v, list):
        return v
    return []


def _load_rows(dataset_id: str, *, split: str, config_name: str | None = None, max_rows: int) -> list[dict[str, Any]]:
    """Load rows robustly (fallback to streaming for schema-incompatible cards)."""
    kwargs: dict[str, Any] = {"path": dataset_id, "split": split}
    if config_name:
        kwargs["name"] = config_name
    try:
        ds = load_dataset(**kwargs, streaming=False)
        return [dict(r) for r in ds.take(max_rows)]
    except Exception:
        ds_stream = load_dataset(**kwargs, streaming=True)
        out: list[dict[str, Any]] = []
        for idx, row in enumerate(ds_stream):
            out.append(dict(row))
            if idx + 1 >= max_rows:
                break
        return out


def _prm_or_shepherd_candidates(dataset_key: str, dataset_id: str, split: str, max_rows: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    ds_rows = _load_rows(dataset_id, split=split, max_rows=max_rows)
    cands: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []

    for idx, row in enumerate(ds_rows):
        problem = str(row.get("problem") or row.get("question") or row.get("input") or "")
        steps = _to_list(row.get("solution_steps") or row.get("steps") or row.get("completions"))
        labels = _to_list(row.get("step_labels") or row.get("labels") or row.get("process_labels"))

        if not steps:
            # fallback: one coarse candidate row if step detail is absent
            text = str(row.get("solution") or row.get("completion") or row.get("response") or "")
            score = float(row.get("label", 0.0)) if isinstance(row.get("label"), (int, float)) else 0.0
            sid = f"{dataset_key}_state_{idx}"
            bid = f"{sid}_cand0"
            cands.append(
                {
                    "schema_version": "branch_learning_corpus_v1",
                    "row_type": "candidate",
                    "row_uid": _hash(f"{dataset_key}|{sid}|{bid}"),
                    "state_id": sid,
                    "branch_id": bid,
                    "dataset_name": dataset_id,
                    "source_dataset_key": dataset_key,
                    "source_split": split,
                    "supervision_origin": "derived",
                    "supervision_signal_type": "step_or_response_quality",
                    "is_human_labeled": True,
                    "is_rollout_estimated": False,
                    "is_verifier_backed": False,
                    "question_or_problem": problem,
                    "branch_text": text,
                    "quality_score": score,
                    "remaining_budget": 1,
                }
            )
            continue

        sid = f"{dataset_key}_state_{idx}"
        pos_ids: list[str] = []
        neg_ids: list[str] = []

        for s_idx, step_text in enumerate(steps):
            label_val = 0.0
            if s_idx < len(labels) and isinstance(labels[s_idx], (int, float, bool)):
                label_val = float(labels[s_idx])
            bid = f"{sid}_cand{s_idx}"
            cands.append(
                {
                    "schema_version": "branch_learning_corpus_v1",
                    "row_type": "candidate",
                    "row_uid": _hash(f"{dataset_key}|{sid}|{bid}"),
                    "state_id": sid,
                    "branch_id": bid,
                    "dataset_name": dataset_id,
                    "source_dataset_key": dataset_key,
                    "source_split": split,
                    "supervision_origin": "native_step_label",
                    "supervision_signal_type": "step_quality",
                    "is_human_labeled": True,
                    "is_rollout_estimated": False,
                    "is_verifier_backed": False,
                    "question_or_problem": problem,
                    "branch_text": str(step_text),
                    "quality_score": label_val,
                    "remaining_budget": 1,
                }
            )
            outside.append(
                {
                    "schema_version": "branch_learning_corpus_v1",
                    "row_type": "outside_option",
                    "row_uid": _hash(f"outside|{dataset_key}|{sid}|{bid}"),
                    "state_id": sid,
                    "branch_id": bid,
                    "dataset_name": dataset_id,
                    "source_dataset_key": dataset_key,
                    "source_split": split,
                    "supervision_origin": "derived",
                    "is_human_labeled": True,
                    "is_rollout_estimated": False,
                    "is_verifier_backed": False,
                    "continue_over_stop_label": 1 if label_val > 0 else 0,
                    "quality_score": label_val,
                    "remaining_budget": 1,
                }
            )
            if label_val > 0:
                pos_ids.append(bid)
            else:
                neg_ids.append(bid)

        if pos_ids and neg_ids:
            bi = pos_ids[0]
            bj = neg_ids[0]
            pairs.append(
                {
                    "schema_version": "branch_learning_corpus_v1",
                    "row_type": "pairwise",
                    "row_uid": _hash(f"pair|{dataset_key}|{sid}|{bi}|{bj}"),
                    "canonical_pair_uid": _hash(f"pairc|{dataset_key}|{sid}|{min(bi,bj)}|{max(bi,bj)}"),
                    "state_id": sid,
                    "branch_i": bi,
                    "branch_j": bj,
                    "dataset_name": dataset_id,
                    "source_dataset_key": dataset_key,
                    "source_split": split,
                    "supervision_origin": "derived_from_native_step_labels",
                    "is_human_labeled": True,
                    "is_rollout_estimated": False,
                    "is_verifier_backed": False,
                    "label": 1,
                    "preference": 1,
                    "margin": 1.0,
                    "margin_abs": 1.0,
                    "near_tie_flag": False,
                    "adjacent_rank_flag": False,
                    "small_margin_flag": False,
                    "remaining_budget": 1,
                }
            )

    return cands, pairs, outside


def _prm800k_candidates(dataset_id: str, split: str, max_rows: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse PRM800K native step-level ratings into candidate-first supervision rows."""
    ds_rows = _load_rows(dataset_id, split=split, max_rows=max_rows)
    cands: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []

    for idx, row in enumerate(ds_rows):
        question = row.get("question")
        if isinstance(question, dict):
            problem = str(question.get("problem", ""))
        else:
            problem = str(question or row.get("problem") or "")

        label = row.get("label")
        steps = label.get("steps") if isinstance(label, dict) else []
        if not isinstance(steps, list) or not steps:
            continue
        sid = f"prm800k_state_{idx}"
        branch_ids_by_step: dict[int, list[tuple[str, float]]] = {}

        for step_idx, step in enumerate(steps):
            comps = step.get("completions") if isinstance(step, dict) else []
            chosen = step.get("chosen_completion") if isinstance(step, dict) else None
            if not isinstance(comps, list):
                continue
            local_ids: list[tuple[str, float]] = []
            for comp_idx, comp in enumerate(comps):
                if not isinstance(comp, dict):
                    continue
                txt = str(comp.get("text", ""))
                rating = comp.get("rating", None)
                if isinstance(rating, bool):
                    rating_f = 1.0 if rating else 0.0
                elif isinstance(rating, (int, float)):
                    rating_f = float(rating)
                else:
                    continue
                # PRM800K rating range includes {-1, 0, 1}; normalize to [0,1].
                quality = (rating_f + 1.0) / 2.0
                bid = f"{sid}_step{step_idx}_cand{comp_idx}"
                local_ids.append((bid, quality))
                cands.append(
                    {
                        "schema_version": "branch_learning_corpus_v1",
                        "row_type": "candidate",
                        "row_uid": _hash(f"prm800k|{sid}|{bid}"),
                        "state_id": sid,
                        "branch_id": bid,
                        "dataset_name": dataset_id,
                        "source_dataset_key": "prm800k",
                        "source_split": split,
                        "supervision_origin": "native_step_label",
                        "supervision_signal_type": "step_quality",
                        "is_human_labeled": True,
                        "is_rollout_estimated": bool(row.get("generation") is not None),
                        "is_verifier_backed": False,
                        "question_or_problem": problem,
                        "branch_text": txt,
                        "quality_score": quality,
                        "raw_step_rating": rating_f,
                        "step_index": int(step_idx),
                        "completion_index": int(comp_idx),
                        "is_chosen_completion": bool(chosen == comp_idx),
                        "remaining_budget": 1,
                    }
                )
                outside.append(
                    {
                        "schema_version": "branch_learning_corpus_v1",
                        "row_type": "outside_option",
                        "row_uid": _hash(f"outside|prm800k|{sid}|{bid}"),
                        "state_id": sid,
                        "branch_id": bid,
                        "dataset_name": dataset_id,
                        "source_dataset_key": "prm800k",
                        "source_split": split,
                        "supervision_origin": "derived_from_native_step_labels",
                        "is_human_labeled": True,
                        "is_rollout_estimated": bool(row.get("generation") is not None),
                        "is_verifier_backed": False,
                        "continue_over_stop_label": 1 if quality >= 0.5 else 0,
                        "quality_score": quality,
                        "remaining_budget": 1,
                    }
                )
            if local_ids:
                branch_ids_by_step[step_idx] = local_ids

        # Conservative pairwise rows: only within-step comparisons when >1 completion exists.
        for step_idx, local_ids in branch_ids_by_step.items():
            if len(local_ids) < 2:
                continue
            sorted_ids = sorted(local_ids, key=lambda x: x[1], reverse=True)
            best, worst = sorted_ids[0], sorted_ids[-1]
            if abs(best[1] - worst[1]) < 1e-8:
                continue
            bi, bj = best[0], worst[0]
            margin = float(best[1] - worst[1])
            pairs.append(
                {
                    "schema_version": "branch_learning_corpus_v1",
                    "row_type": "pairwise",
                    "row_uid": _hash(f"pair|prm800k|{sid}|{bi}|{bj}|s{step_idx}"),
                    "canonical_pair_uid": _hash(f"pairc|prm800k|{sid}|{min(bi,bj)}|{max(bi,bj)}|s{step_idx}"),
                    "state_id": sid,
                    "branch_i": bi,
                    "branch_j": bj,
                    "dataset_name": dataset_id,
                    "source_dataset_key": "prm800k",
                    "source_split": split,
                    "supervision_origin": "derived_from_native_step_labels",
                    "is_human_labeled": True,
                    "is_rollout_estimated": bool(row.get("generation") is not None),
                    "is_verifier_backed": False,
                    "label": 1,
                    "preference": 1,
                    "margin": margin,
                    "margin_abs": abs(margin),
                    "near_tie_flag": abs(margin) <= 0.05,
                    "adjacent_rank_flag": True,
                    "small_margin_flag": abs(margin) <= 0.15,
                    "remaining_budget": 1,
                }
            )

    return cands, pairs, outside


def _apps_candidates(dataset_id: str, split: str, max_rows: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str | None]:
    try:
        ds_rows = _load_rows(dataset_id, config_name="all", split=split, max_rows=max_rows)
    except Exception as exc:
        return ([], [], [], f"{type(exc).__name__}: {exc}")
    cands: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []
    for idx, row in enumerate(ds_rows):
        sid = f"apps_state_{idx}"
        problem = str(row.get("question") or row.get("problem") or "")
        sol_field = row.get("solutions")
        solutions = []
        if isinstance(sol_field, str):
            try:
                parsed = json.loads(sol_field)
                if isinstance(parsed, list):
                    solutions = [str(x) for x in parsed]
            except Exception:
                solutions = []
        elif isinstance(sol_field, list):
            solutions = [str(x) for x in sol_field]

        if not solutions:
            continue

        for s_idx, sol in enumerate(solutions[:3]):
            bid = f"{sid}_cand{s_idx}"
            # APPS does not provide native branch-allocation labels; score is conservative derived proxy.
            proxy_score = float(max(0.0, 1.0 - (len(sol) / 4000.0)))
            cands.append(
                {
                    "schema_version": "branch_learning_corpus_v1",
                    "row_type": "candidate",
                    "row_uid": _hash(f"apps|{sid}|{bid}"),
                    "state_id": sid,
                    "branch_id": bid,
                    "dataset_name": dataset_id,
                    "source_dataset_key": "apps",
                    "source_split": split,
                    "supervision_origin": "derived",
                    "supervision_signal_type": "verifier_backed_potential",
                    "is_human_labeled": False,
                    "is_rollout_estimated": False,
                    "is_verifier_backed": True,
                    "question_or_problem": problem,
                    "branch_text": sol,
                    "quality_score": proxy_score,
                    "remaining_budget": 1,
                    "apps_has_test_fields": bool(row.get("input_output") or row.get("public_input_output") or row.get("private_test_cases")),
                }
            )
            outside.append(
                {
                    "schema_version": "branch_learning_corpus_v1",
                    "row_type": "outside_option",
                    "row_uid": _hash(f"apps_outside|{sid}|{bid}"),
                    "state_id": sid,
                    "branch_id": bid,
                    "dataset_name": dataset_id,
                    "source_dataset_key": "apps",
                    "source_split": split,
                    "supervision_origin": "derived",
                    "is_human_labeled": False,
                    "is_rollout_estimated": False,
                    "is_verifier_backed": True,
                    "continue_over_stop_label": 1 if proxy_score > 0.35 else 0,
                    "quality_score": proxy_score,
                    "remaining_budget": 1,
                }
            )

    return cands, pairs, outside, None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build canonical-aligned external dataset corpus for PRM800K/Math-Shepherd/APPS")
    p.add_argument("--run-id", default="external_prm_mathshepherd_apps_20260416")
    p.add_argument("--output-root", default="outputs/branch_learning_corpora_external")
    p.add_argument("--max-rows-per-dataset", type=int, default=128)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_root) / args.run_id
    rows_dir = out_dir / "rows"

    all_candidates: list[dict[str, Any]] = []
    all_pairs: list[dict[str, Any]] = []
    all_outside: list[dict[str, Any]] = []
    dataset_errors: dict[str, str] = {}

    prm_c, prm_p, prm_o = _prm800k_candidates(
        dataset_id="tasksource/PRM800K",
        split="train",
        max_rows=int(args.max_rows_per_dataset),
    )
    all_candidates.extend(prm_c)
    all_pairs.extend(prm_p)
    all_outside.extend(prm_o)

    ms_c, ms_p, ms_o = _prm_or_shepherd_candidates(
        dataset_key="math_shepherd",
        dataset_id="peiyi9979/Math-Shepherd",
        split="train",
        max_rows=int(args.max_rows_per_dataset),
    )
    all_candidates.extend(ms_c)
    all_pairs.extend(ms_p)
    all_outside.extend(ms_o)

    apps_c, apps_p, apps_o, apps_err = _apps_candidates(
        dataset_id="codeparrot/apps",
        split="train",
        max_rows=int(args.max_rows_per_dataset),
    )
    all_candidates.extend(apps_c)
    all_pairs.extend(apps_p)
    all_outside.extend(apps_o)
    if apps_err:
        dataset_errors["apps"] = apps_err

    _write_jsonl(rows_dir / "candidate_rows.jsonl", all_candidates)
    _write_jsonl(rows_dir / "pairwise_rows.jsonl", all_pairs)
    _write_jsonl(rows_dir / "outside_option_rows.jsonl", all_outside)

    counts_by_key: dict[str, dict[str, int]] = {}
    for key in ["prm800k", "math_shepherd", "apps"]:
        counts_by_key[key] = {
            "candidate_rows": sum(1 for r in all_candidates if r.get("source_dataset_key") == key),
            "pairwise_rows": sum(1 for r in all_pairs if r.get("source_dataset_key") == key),
            "outside_option_rows": sum(1 for r in all_outside if r.get("source_dataset_key") == key),
        }

    provenance_by_dataset: dict[str, dict[str, int]] = {}
    for key in ["prm800k", "math_shepherd", "apps"]:
        crows = [r for r in all_candidates if r.get("source_dataset_key") == key]
        provenance_by_dataset[key] = {
            "source_split_train": sum(1 for r in crows if str(r.get("source_split", "")) == "train"),
            "human_labeled_true": sum(1 for r in crows if bool(r.get("is_human_labeled", False))),
            "rollout_estimated_true": sum(1 for r in crows if bool(r.get("is_rollout_estimated", False))),
            "verifier_backed_true": sum(1 for r in crows if bool(r.get("is_verifier_backed", False))),
            "native_supervision_interpretation": sum(1 for r in crows if str(r.get("supervision_origin", "")).startswith("native")),
            "derived_supervision_interpretation": sum(1 for r in crows if not str(r.get("supervision_origin", "")).startswith("native")),
        }

    summary = {
        "run_id": args.run_id,
        "datasets": ["prm800k", "math_shepherd", "apps"],
        "counts": {
            "candidate_rows": len(all_candidates),
            "pairwise_rows": len(all_pairs),
            "outside_option_rows": len(all_outside),
        },
        "counts_by_dataset_key": counts_by_key,
        "provenance_by_dataset_key": provenance_by_dataset,
        "notes": {
            "prm800k": "native step labels; pairwise/outside labels are derived conservatively",
            "math_shepherd": "native step labels; pairwise/outside labels are derived conservatively",
            "apps": "verifier-backed coding dataset; branch-allocation supervision is derived and partially suitable",
        },
        "dataset_errors": dataset_errors,
    }
    _write_json(out_dir / "summary.json", summary)

    manifest = {
        "run_id": args.run_id,
        "generator": "build_external_prm_mathshepherd_apps_corpus.py",
        "schema_version": "branch_learning_corpus_v1",
        "inputs": {
            "datasets": {
                "prm800k": "tasksource/PRM800K",
                "math_shepherd": "peiyi9979/Math-Shepherd",
                "apps": "codeparrot/apps",
            },
            "max_rows_per_dataset": int(args.max_rows_per_dataset),
        },
        "outputs": {
            "candidate_rows": str(rows_dir / "candidate_rows.jsonl"),
            "pairwise_rows": str(rows_dir / "pairwise_rows.jsonl"),
            "outside_option_rows": str(rows_dir / "outside_option_rows.jsonl"),
            "summary": str(out_dir / "summary.json"),
        },
    }
    _write_json(out_dir / "manifest.json", manifest)

    print(json.dumps({"output_dir": str(out_dir), "summary": str(out_dir / 'summary.json')}, indent=2))


if __name__ == "__main__":
    main()
