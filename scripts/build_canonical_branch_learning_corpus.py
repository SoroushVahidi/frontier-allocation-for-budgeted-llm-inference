#!/usr/bin/env python3
"""Build canonical processed corpora for branch-allocation learning.

This script standardizes heterogeneous brute-force label artifacts into one
manifest-backed corpus layout for pairwise/pointwise/outside-option learning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any


SCHEMA_VERSION = "branch_learning_corpus_v1"
GENERATOR = "build_canonical_branch_learning_corpus.py"
PAIRWISE_PASSTHROUGH_FIELDS = [
    "exact_vs_approx_disagreement_risk",
    "supervision_reliability_weight",
    "supervision_trust_tier",
    "keep_in_quality_mixed_trust",
    "soft_target_prob_i_wins",
    "soft_target_prob_tie",
    "soft_target_prob_j_wins",
    "soft_target_entropy",
    "soft_target_source",
    "partial_order_incomparable_target",
    "partial_order_incomparable_reasons",
    "partial_order_label",
    "partial_order_label_name",
    "partial_order_policy",
    "penalized_lambda",
    "penalized_delta_c_mode",
    "penalized_marginal_value_i",
    "penalized_marginal_value_j",
    "penalized_marginal_gap",
    "penalized_tau_state",
    "penalized_tau_components",
    "penalized_ternary_label",
    "penalized_ternary_label_name",
    "penalized_marginal_defer_target",
    "penalized_delta_c_i_components",
    "penalized_delta_c_j_components",
    "delta_u_i",
    "delta_u_j",
    "delta_c_i",
    "delta_c_j",
    "ternary_defer_label",
    "ternary_defer_label_name",
    "ternary_defer_label_source",
    "defer_target_mode",
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_for_state(state_id: str, seed: int, train_ratio: float, val_ratio: float) -> str:
    h = _stable_hash(f"split|{seed}|{state_id}")
    r = int(h[:12], 16) / float(16**12)
    if r < train_ratio:
        return "train"
    if r < train_ratio + val_ratio:
        return "val"
    return "test"


def _mode_to_exact_flag(mode: str, label_source: str) -> bool:
    mode_l = mode.lower()
    src_l = label_source.lower()
    return mode_l == "exact" or src_l.startswith("exact")


def _canonical_pair_key(state_id: str, bi: str, bj: str) -> tuple[str, str, str]:
    a, b = sorted([str(bi), str(bj)])
    return (str(state_id), a, b)


def _source_manifest(dir_path: Path) -> dict[str, Any]:
    mf = dir_path / "manifest.json"
    return _read_json(mf) if mf.exists() else {}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build canonical branch-learning processed corpus")
    p.add_argument("--base-labels-dir", required=True, help="Directory with candidate/pairwise/state jsonl files")
    p.add_argument(
        "--regime-root-dir",
        default="",
        help="Optional target-regime root containing regime_* subdirs with pairwise labels",
    )
    p.add_argument(
        "--exact-expansion-dir",
        default="",
        help="Optional targeted exact expansion dir (exact_pairwise_labels.jsonl)",
    )
    p.add_argument("--output-root", default="outputs/branch_learning_corpora")
    p.add_argument("--run-id", required=True)
    p.add_argument("--split-seed", type=int, default=17)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--small-margin-threshold", type=float, default=0.08)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path(args.base_labels_dir)
    out_dir = Path(args.output_root) / args.run_id
    rows_dir = out_dir / "rows"
    summaries_dir = out_dir / "summaries"
    meta_dir = out_dir / "meta"
    out_dir.mkdir(parents=True, exist_ok=True)

    candidate_path = base_dir / "candidate_labels.jsonl"
    pairwise_path = base_dir / "pairwise_labels.jsonl"
    state_path = base_dir / "state_summaries.jsonl"
    if not candidate_path.exists() or not pairwise_path.exists() or not state_path.exists():
        raise FileNotFoundError("base labels dir must contain candidate_labels.jsonl, pairwise_labels.jsonl, state_summaries.jsonl")

    base_candidates = _read_jsonl(candidate_path)
    base_pairwise = _read_jsonl(pairwise_path)
    state_rows = _read_jsonl(state_path)

    state_meta: dict[str, dict[str, Any]] = {}
    for s in state_rows:
        sid = str(s.get("state_id", ""))
        state_meta[sid] = {
            "dataset_name": str(s.get("dataset_name", "unknown")),
            "remaining_budget": int(s.get("remaining_budget", 0)),
            "branch_count": int(s.get("branch_count", s.get("num_branches", 0))),
        }

    candidate_map: dict[tuple[str, str], dict[str, Any]] = {}
    canonical_candidates: list[dict[str, Any]] = []
    outside_rows: list[dict[str, Any]] = []
    duplicate_candidates = 0

    for row in base_candidates:
        sid = str(row.get("state_id", ""))
        bid = str(row.get("branch_id", ""))
        key = (sid, bid)
        if key in candidate_map:
            duplicate_candidates += 1
            continue
        candidate_map[key] = row

        mode = str(row.get("mode", "unknown"))
        label_source = str(row.get("label_source", ""))
        exact_flag = _mode_to_exact_flag(mode=mode, label_source=label_source)
        split = _split_for_state(sid, args.split_seed, args.train_ratio, args.val_ratio)
        features_v1 = row.get("features_branch_v1", {}) if isinstance(row.get("features_branch_v1"), dict) else {}
        features_v2 = row.get("features_branch_v2", {}) if isinstance(row.get("features_branch_v2"), dict) else {}

        c = {
            "schema_version": SCHEMA_VERSION,
            "row_type": "candidate",
            "row_uid": _stable_hash(f"candidate|{sid}|{bid}"),
            "state_id": sid,
            "branch_id": bid,
            "example_id": str(row.get("example_id", "")),
            "dataset_name": str(row.get("dataset_name", state_meta.get(sid, {}).get("dataset_name", "unknown"))),
            "remaining_budget": int(row.get("remaining_budget", state_meta.get(sid, {}).get("remaining_budget", 0))),
            "split": split,
            "estimated_value_if_allocate_next": float(row.get("estimated_value_if_allocate_next", 0.0)),
            "branch_vs_outside_gap": float(row.get("branch_vs_outside_gap", 0.0)),
            "allocation_value_std": float(row.get("allocation_value_std", 0.0)),
            "allocation_candidates_evaluated": int(row.get("allocation_candidates_evaluated", 0)),
            "mode": mode,
            "is_exact_label": bool(exact_flag),
            "is_approx_label": bool(not exact_flag and mode.lower() == "approx"),
            "label_source": label_source or ("exact_original" if exact_flag else "approx_original"),
            "source_run_id": str(row.get("source_run_id", "")),
            "source_seed": row.get("source_seed"),
            "source_dataset_name": str(row.get("source_dataset_name", row.get("dataset_name", ""))),
            "features_branch_v1": features_v1,
            "features_branch_v2": features_v2,
        }
        canonical_candidates.append(c)

        outside_rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "row_type": "outside_option",
                "row_uid": _stable_hash(f"outside|{sid}|{bid}"),
                "state_id": sid,
                "branch_id": bid,
                "example_id": c["example_id"],
                "dataset_name": c["dataset_name"],
                "remaining_budget": c["remaining_budget"],
                "split": split,
                "branch_vs_outside_gap": c["branch_vs_outside_gap"],
                "estimated_value_if_allocate_next": c["estimated_value_if_allocate_next"],
                "allocation_value_std": c["allocation_value_std"],
                "is_exact_label": c["is_exact_label"],
                "label_source": c["label_source"],
                "source_run_id": c["source_run_id"],
                "source_seed": c["source_seed"],
            }
        )

    regime_pairwise_sources: list[tuple[str, list[dict[str, Any]], str]] = [
        ("base", base_pairwise, str(pairwise_path)),
    ]

    if args.regime_root_dir:
        regime_root = Path(args.regime_root_dir)
        if regime_root.exists():
            for sub in sorted(regime_root.iterdir()):
                if not sub.is_dir() or not sub.name.startswith("regime_"):
                    continue
                rp = sub / "pairwise_labels.jsonl"
                if rp.exists():
                    regime_name = sub.name.replace("regime_", "", 1)
                    regime_pairwise_sources.append((regime_name, _read_jsonl(rp), str(rp)))

    if args.exact_expansion_dir:
        exact_dir = Path(args.exact_expansion_dir)
        xp = exact_dir / "exact_pairwise_labels.jsonl"
        if xp.exists():
            regime_pairwise_sources.append(("exact_expansion", _read_jsonl(xp), str(xp)))

    precedence = {
        "exact_promoted_hard_region": 40,
        "exact_hard_region_runner": 40,
        "exact_promoted": 35,
        "exact_original": 30,
        "exact": 30,
        "mixed": 25,
        "approx_original": 10,
        "approx": 10,
        "": 0,
    }

    canonical_pair_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicate_pairwise = 0
    duplicate_log: list[dict[str, Any]] = []

    for regime_name, rows, src_path in regime_pairwise_sources:
        for row in rows:
            sid = str(row.get("state_id", ""))
            bi = str(row.get("branch_i", ""))
            bj = str(row.get("branch_j", ""))
            key = _canonical_pair_key(sid, bi, bj)

            ci = candidate_map.get((sid, bi), {})
            cj = candidate_map.get((sid, bj), {})
            margin = float(row.get("margin", 0.0))
            margin_abs = abs(margin)
            std_mean = float(row.get("pair_uncertainty_std_mean", 0.5 * (
                float(ci.get("allocation_value_std", 0.0)) + float(cj.get("allocation_value_std", 0.0))
            )))
            pair_type = str(row.get("pair_type", "generic"))
            label_source = str(row.get("label_source", ""))
            mode_prov = str(row.get("pair_mode_provenance", ""))
            exact_flag = _mode_to_exact_flag(mode=mode_prov, label_source=label_source)
            split = _split_for_state(sid, args.split_seed, args.train_ratio, args.val_ratio)
            rel_margin = float(row.get("relative_margin", margin_abs / max(
                abs(float(ci.get("estimated_value_if_allocate_next", 0.0))),
                abs(float(cj.get("estimated_value_if_allocate_next", 0.0))),
                1e-6,
            )))

            out = {
                "schema_version": SCHEMA_VERSION,
                "row_type": "pairwise",
                "row_uid": _stable_hash(f"pairwise|{sid}|{key[1]}|{key[2]}|{regime_name}"),
                "canonical_pair_uid": _stable_hash(f"pairwise-canonical|{sid}|{key[1]}|{key[2]}"),
                "state_id": sid,
                "branch_i": bi,
                "branch_j": bj,
                "example_id": str(row.get("example_id", "")),
                "dataset_name": str(row.get("dataset_name", state_meta.get(sid, {}).get("dataset_name", "unknown"))),
                "remaining_budget": int(row.get("remaining_budget", state_meta.get(sid, {}).get("remaining_budget", 0))),
                "split": split,
                "label": int(row.get("label", row.get("preference", 0))),
                "preference": int(row.get("preference", row.get("label", 0))),
                "margin": margin,
                "margin_abs": margin_abs,
                "relative_margin": rel_margin,
                "pair_uncertainty_std_mean": std_mean,
                "pair_uncertainty_std_max": float(row.get("pair_uncertainty_std_max", std_mean)),
                "pair_type": pair_type,
                "near_tie_flag": bool(row.get("near_tie_flag", margin_abs <= float(args.near_tie_margin))),
                "small_margin_flag": bool(margin_abs <= float(args.small_margin_threshold)),
                "adjacent_rank_flag": bool(pair_type == "adjacent_rank"),
                "ambiguous_tie_target": bool(row.get("ambiguous_tie_target", False)),
                "ambiguous_tie_reasons": row.get("ambiguous_tie_reasons", []),
                "ternary_label_name": str(row.get("ternary_label_name", "")),
                "is_exact_label": bool(exact_flag),
                "is_approx_label": bool(not exact_flag and (mode_prov == "approx" or label_source.startswith("approx"))),
                "pair_mode_provenance": mode_prov,
                "label_source": label_source or ("exact_original" if exact_flag else "approx_original"),
                "replaced_approx_label": bool(row.get("replaced_approx_label", False)),
                "mined_reasons": row.get("mined_reasons", []),
                "source_regime": regime_name,
                "source_path": src_path,
            }
            for field in PAIRWISE_PASSTHROUGH_FIELDS:
                if field in row:
                    out[field] = row.get(field)
            disagreement_signal = bool(
                out.get("exact_vs_approx_disagreement_risk", False)
                or any("disagreement" in str(x).lower() for x in out.get("ambiguous_tie_reasons", []))
                or any("disagreement" in str(x).lower() for x in out.get("mined_reasons", []))
            )
            out["exact_vs_approx_disagreement_signal"] = disagreement_signal

            if key not in canonical_pair_map:
                canonical_pair_map[key] = out
                continue

            duplicate_pairwise += 1
            existing = canonical_pair_map[key]
            existing_rank = precedence.get(str(existing.get("label_source", "")), 0)
            new_rank = precedence.get(str(out.get("label_source", "")), 0)
            replace = new_rank > existing_rank or (new_rank == existing_rank and out["source_regime"] != "base" and existing.get("source_regime") == "base")
            duplicate_log.append(
                {
                    "state_id": sid,
                    "pair": [key[1], key[2]],
                    "kept_source_regime": out["source_regime"] if replace else existing.get("source_regime"),
                    "dropped_source_regime": existing.get("source_regime") if replace else out["source_regime"],
                    "kept_label_source": out["label_source"] if replace else existing.get("label_source"),
                    "dropped_label_source": existing.get("label_source") if replace else out["label_source"],
                }
            )
            if replace:
                canonical_pair_map[key] = out

    canonical_pairwise = sorted(canonical_pair_map.values(), key=lambda r: (r["dataset_name"], r["state_id"], r["branch_i"], r["branch_j"]))
    canonical_candidates = sorted(canonical_candidates, key=lambda r: (r["dataset_name"], r["state_id"], r["branch_id"]))
    outside_rows = sorted(outside_rows, key=lambda r: (r["dataset_name"], r["state_id"], r["branch_id"]))

    cand_out = rows_dir / "candidate_rows.jsonl"
    pair_out = rows_dir / "pairwise_rows.jsonl"
    outside_out = rows_dir / "outside_option_rows.jsonl"
    _write_jsonl(cand_out, canonical_candidates)
    _write_jsonl(pair_out, canonical_pairwise)
    _write_jsonl(outside_out, outside_rows)

    dataset_counts = Counter(r["dataset_name"] for r in canonical_pairwise)
    budget_counts = Counter(str(r["remaining_budget"]) for r in canonical_pairwise)
    split_counts = Counter(r["split"] for r in canonical_pairwise)
    source_regime_counts = Counter(r["source_regime"] for r in canonical_pairwise)

    hard_slice = {
        "near_tie_pairs": sum(1 for r in canonical_pairwise if bool(r.get("near_tie_flag", False))),
        "small_margin_pairs": sum(1 for r in canonical_pairwise if bool(r.get("small_margin_flag", False))),
        "adjacent_rank_pairs": sum(1 for r in canonical_pairwise if bool(r.get("adjacent_rank_flag", False))),
        "ambiguous_tie_pairs": sum(1 for r in canonical_pairwise if bool(r.get("ambiguous_tie_target", False))),
        "exact_promoted_pairs": sum(1 for r in canonical_pairwise if bool(r.get("replaced_approx_label", False))),
        "exact_vs_approx_disagreement_signal_pairs": sum(
            1 for r in canonical_pairwise if bool(r.get("exact_vs_approx_disagreement_signal", False))
        ),
        "partial_order_rows": sum(1 for r in canonical_pairwise if "partial_order_label" in r),
        "soft_prob_rows": sum(1 for r in canonical_pairwise if "soft_target_prob_tie" in r),
        "penalized_marginal_rows": sum(1 for r in canonical_pairwise if "penalized_marginal_gap" in r),
    }

    exact_vs_approx = {
        "pairwise_exact_rows": sum(1 for r in canonical_pairwise if bool(r.get("is_exact_label", False))),
        "pairwise_approx_rows": sum(1 for r in canonical_pairwise if bool(r.get("is_approx_label", False))),
        "candidate_exact_rows": sum(1 for r in canonical_candidates if bool(r.get("is_exact_label", False))),
        "candidate_approx_rows": sum(1 for r in canonical_candidates if bool(r.get("is_approx_label", False))),
    }

    coverage_by_dataset: dict[str, dict[str, Any]] = {}
    pairs_by_dataset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in canonical_pairwise:
        pairs_by_dataset[r["dataset_name"]].append(r)
    for ds, rows in pairs_by_dataset.items():
        coverage_by_dataset[ds] = {
            "pairwise_rows": len(rows),
            "near_tie_rate": sum(1 for r in rows if r.get("near_tie_flag")) / max(1, len(rows)),
            "adjacent_rank_rate": sum(1 for r in rows if r.get("adjacent_rank_flag")) / max(1, len(rows)),
            "exact_rate": sum(1 for r in rows if r.get("is_exact_label")) / max(1, len(rows)),
            "disagreement_signal_rate": sum(
                1 for r in rows if bool(r.get("exact_vs_approx_disagreement_signal", False))
            ) / max(1, len(rows)),
        }

    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "counts": {
            "candidate_rows": len(canonical_candidates),
            "pairwise_rows": len(canonical_pairwise),
            "outside_option_rows": len(outside_rows),
        },
        "split_counts_pairwise": dict(split_counts),
        "pairwise_rows_by_dataset": dict(dataset_counts),
        "pairwise_rows_by_budget": dict(budget_counts),
        "pairwise_rows_by_source_regime": dict(source_regime_counts),
        "exact_vs_approx": exact_vs_approx,
        "hard_slice_counts": hard_slice,
        "duplicates": {
            "candidate_duplicates_dropped": duplicate_candidates,
            "pairwise_duplicates_resolved": duplicate_pairwise,
            "pairwise_duplicate_log_rows": len(duplicate_log),
        },
        "coverage_by_dataset": coverage_by_dataset,
    }

    slice_stats = {
        "hard_case_slices": hard_slice,
        "coverage_by_dataset": coverage_by_dataset,
        "source_regime_counts": dict(source_regime_counts),
        "notes": [
            "near_tie_flag uses near-tie margin threshold",
            "small_margin_flag uses small-margin threshold",
            "exact-promoted pairs are tracked via replaced_approx_label",
        ],
    }

    checksums = {
        "candidate_rows_sha256": _sha256(cand_out),
        "pairwise_rows_sha256": _sha256(pair_out),
        "outside_option_rows_sha256": _sha256(outside_out),
    }

    source_manifest = {
        "base_labels_dir": str(base_dir),
        "base_manifest": _source_manifest(base_dir),
        "regime_root_dir": str(args.regime_root_dir) if args.regime_root_dir else None,
        "regime_manifest": _source_manifest(Path(args.regime_root_dir)) if args.regime_root_dir and Path(args.regime_root_dir).exists() else {},
        "exact_expansion_dir": str(args.exact_expansion_dir) if args.exact_expansion_dir else None,
        "exact_manifest": _source_manifest(Path(args.exact_expansion_dir)) if args.exact_expansion_dir and Path(args.exact_expansion_dir).exists() else {},
    }

    schema = {
        "schema_version": SCHEMA_VERSION,
        "row_types": {
            "candidate": {
                "required_fields": [
                    "row_uid", "state_id", "branch_id", "dataset_name", "remaining_budget", "split",
                    "estimated_value_if_allocate_next", "branch_vs_outside_gap", "allocation_value_std",
                    "mode", "is_exact_label", "is_approx_label", "label_source",
                ],
                "optional_fields": [
                    "source_run_id", "source_seed", "source_dataset_name", "features_branch_v1", "features_branch_v2",
                ],
            },
            "pairwise": {
                "required_fields": [
                    "row_uid", "canonical_pair_uid", "state_id", "branch_i", "branch_j", "dataset_name",
                    "remaining_budget", "split", "label", "preference", "margin", "margin_abs",
                    "pair_type", "near_tie_flag", "adjacent_rank_flag", "is_exact_label", "is_approx_label",
                    "label_source", "source_regime",
                ],
                "optional_fields": [
                    "relative_margin", "pair_uncertainty_std_mean", "pair_uncertainty_std_max",
                    "small_margin_flag", "ambiguous_tie_target", "ambiguous_tie_reasons", "ternary_label_name",
                    "pair_mode_provenance", "replaced_approx_label", "mined_reasons",
                    "exact_vs_approx_disagreement_signal",
                    *PAIRWISE_PASSTHROUGH_FIELDS,
                ],
            },
            "outside_option": {
                "required_fields": [
                    "row_uid", "state_id", "branch_id", "dataset_name", "remaining_budget", "split",
                    "branch_vs_outside_gap", "estimated_value_if_allocate_next", "allocation_value_std",
                    "is_exact_label", "label_source",
                ],
                "optional_fields": ["source_run_id", "source_seed"],
            },
        },
    }

    _write_json(summaries_dir / "corpus_summary.json", summary)
    _write_json(summaries_dir / "slice_stats.json", slice_stats)
    _write_json(meta_dir / "checksums.json", checksums)
    _write_json(meta_dir / "source_artifacts.json", source_manifest)
    _write_json(meta_dir / "duplicate_resolution_log.json", {"rows": duplicate_log})
    _write_json(meta_dir / "schema.json", schema)

    manifest = {
        "run_id": args.run_id,
        "generator": GENERATOR,
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "base_labels_dir": str(base_dir),
            "regime_root_dir": str(args.regime_root_dir) if args.regime_root_dir else None,
            "exact_expansion_dir": str(args.exact_expansion_dir) if args.exact_expansion_dir else None,
        },
        "config": {
            "split_seed": args.split_seed,
            "train_ratio": args.train_ratio,
            "val_ratio": args.val_ratio,
            "near_tie_margin": args.near_tie_margin,
            "small_margin_threshold": args.small_margin_threshold,
        },
        "outputs": {
            "candidate_rows": str(cand_out),
            "pairwise_rows": str(pair_out),
            "outside_option_rows": str(outside_out),
            "summary": str(summaries_dir / "corpus_summary.json"),
            "slice_stats": str(summaries_dir / "slice_stats.json"),
            "schema": str(meta_dir / "schema.json"),
            "checksums": str(meta_dir / "checksums.json"),
            "duplicate_resolution_log": str(meta_dir / "duplicate_resolution_log.json"),
        },
    }
    _write_json(out_dir / "manifest.json", manifest)

    md_lines = [
        "# Canonical branch-learning corpus",
        "",
        f"- run_id: `{args.run_id}`",
        f"- schema_version: `{SCHEMA_VERSION}`",
        f"- candidate_rows: `{summary['counts']['candidate_rows']}`",
        f"- pairwise_rows: `{summary['counts']['pairwise_rows']}`",
        f"- outside_option_rows: `{summary['counts']['outside_option_rows']}`",
        "",
        "## Exact vs approx",
        f"- pairwise_exact_rows: `{exact_vs_approx['pairwise_exact_rows']}`",
        f"- pairwise_approx_rows: `{exact_vs_approx['pairwise_approx_rows']}`",
        f"- candidate_exact_rows: `{exact_vs_approx['candidate_exact_rows']}`",
        f"- candidate_approx_rows: `{exact_vs_approx['candidate_approx_rows']}`",
        "",
        "## Hard-case slices",
        f"- near_tie_pairs: `{hard_slice['near_tie_pairs']}`",
        f"- small_margin_pairs: `{hard_slice['small_margin_pairs']}`",
        f"- adjacent_rank_pairs: `{hard_slice['adjacent_rank_pairs']}`",
        f"- ambiguous_tie_pairs: `{hard_slice['ambiguous_tie_pairs']}`",
        f"- exact_promoted_pairs: `{hard_slice['exact_promoted_pairs']}`",
        "",
        "## Duplicate handling",
        f"- candidate_duplicates_dropped: `{duplicate_candidates}`",
        f"- pairwise_duplicates_resolved: `{duplicate_pairwise}`",
    ]
    (out_dir / "report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "summary": str(summaries_dir / 'corpus_summary.json')}, indent=2))


if __name__ == "__main__":
    main()
