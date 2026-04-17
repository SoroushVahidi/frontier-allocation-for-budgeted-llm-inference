#!/usr/bin/env python3
"""Bounded Cohere adjudication for hardest ambiguous pairwise branch comparisons."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any

import cohere


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _pair_key(state_id: str, bi: str, bj: str) -> tuple[str, str, str]:
    a, b = sorted([str(bi), str(bj)])
    return (str(state_id), a, b)


def _adjacent_pair_keys(candidates: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for r in candidates:
        by_state.setdefault(str(r["state_id"]), []).append(r)
    out: set[tuple[str, str, str]] = set()
    for sid, rows in by_state.items():
        ranked = sorted(rows, key=lambda x: float(x.get("estimated_value_if_allocate_next", 0.0)), reverse=True)
        for i in range(max(0, len(ranked) - 1)):
            out.add(_pair_key(sid, str(ranked[i]["branch_id"]), str(ranked[i + 1]["branch_id"])))
    return out


def _hard_score(row: dict[str, Any], pair_std: float, adjacent: bool, near_tie_margin: float) -> float:
    margin_abs = abs(float(row.get("margin", 0.0)))
    score = 0.0
    if margin_abs <= near_tie_margin:
        score += 4.0
    if margin_abs <= 0.08:
        score += 2.0
    if adjacent:
        score += 2.0
    score += min(3.0, pair_std * 20.0)
    return score


def _prompt_for_pair(row: dict[str, Any], ci: dict[str, Any], cj: dict[str, Any]) -> str:
    payload = {
        "task": "Choose which branch should receive the NEXT unit of compute under fixed budget.",
        "instruction": (
            "Return strict JSON with keys winner, confidence, rationale_short. "
            "winner must be one of: branch_i, branch_j, tie. "
            "confidence is a float in [0,1]."
        ),
        "state": {
            "state_id": str(row.get("state_id", "")),
            "remaining_budget": int(row.get("remaining_budget", 0)),
            "dataset_name": str(row.get("dataset_name", "unknown")),
        },
        "branch_i": {
            "branch_id": str(row.get("branch_i", "")),
            "score": float(ci.get("features_branch_v1", {}).get("score", 0.0)),
            "depth": float(ci.get("features_branch_v1", {}).get("depth", 0.0)),
            "recent_delta": float(ci.get("features_branch_v1", {}).get("recent_delta", 0.0)),
            "verify_count": float(ci.get("features_branch_v1", {}).get("verify_count", 0.0)),
            "allocation_value_std": float(ci.get("allocation_value_std", 0.0)),
            "estimated_value_if_allocate_next": float(ci.get("estimated_value_if_allocate_next", 0.0)),
            "branch_vs_outside_gap": float(ci.get("branch_vs_outside_gap", 0.0)),
        },
        "branch_j": {
            "branch_id": str(row.get("branch_j", "")),
            "score": float(cj.get("features_branch_v1", {}).get("score", 0.0)),
            "depth": float(cj.get("features_branch_v1", {}).get("depth", 0.0)),
            "recent_delta": float(cj.get("features_branch_v1", {}).get("recent_delta", 0.0)),
            "verify_count": float(cj.get("features_branch_v1", {}).get("verify_count", 0.0)),
            "allocation_value_std": float(cj.get("allocation_value_std", 0.0)),
            "estimated_value_if_allocate_next": float(cj.get("estimated_value_if_allocate_next", 0.0)),
            "branch_vs_outside_gap": float(cj.get("branch_vs_outside_gap", 0.0)),
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def _parse_json_obj(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
        return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cohere hard-pair adjudication")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--output-dir", default="outputs")
    p.add_argument("--run-id", required=True)
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--max-pairs", type=int, default=24)
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--replace-confidence-min", type=float, default=0.60)
    p.add_argument("--strict-hard-slice-only", action="store_true")
    p.add_argument("--strict-near-tie-required", action="store_true")
    p.add_argument("--strict-adjacent-required", action="store_true")
    p.add_argument("--strict-min-pair-std", type=float, default=0.0)
    p.add_argument("--soft-weight-confidence-min", type=float, default=0.75)
    p.add_argument("--soft-disagree-weight", type=float, default=0.85)
    p.add_argument("--soft-agree-weight", type=float, default=1.05)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-retries", type=int, default=6)
    p.add_argument("--retry-sleep-sec", type=float, default=3.5)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    api_key = os.environ.get("COHERE_API_KEY", "")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is missing")

    labels_dir = Path(args.labels_dir)
    candidates = _read_jsonl(labels_dir / "candidate_labels.jsonl")
    pairwise = _read_jsonl(labels_dir / "pairwise_labels.jsonl")
    states = _read_jsonl(labels_dir / "state_summaries.jsonl")

    cand_map = {(str(r["state_id"]), str(r["branch_id"])): r for r in candidates}
    adjacent_keys = _adjacent_pair_keys(candidates)

    scored: list[tuple[float, dict[str, Any]]] = []
    for r in pairwise:
        sid = str(r["state_id"])
        bi = str(r["branch_i"])
        bj = str(r["branch_j"])
        ci = cand_map.get((sid, bi), {})
        cj = cand_map.get((sid, bj), {})
        pair_std = 0.5 * (float(ci.get("allocation_value_std", 0.0)) + float(cj.get("allocation_value_std", 0.0)))
        adj = _pair_key(sid, bi, bj) in adjacent_keys
        score = _hard_score(r, pair_std, adj, float(args.near_tie_margin))
        if score <= 0.0:
            continue
        rr = dict(r)
        rr["pair_uncertainty_std_mean"] = pair_std
        rr["adjacent_rank_flag"] = bool(adj)
        rr["hard_score"] = score
        scored.append((score, rr))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [r for _s, r in scored[: max(1, int(args.max_pairs))]]

    co = cohere.ClientV2(api_key=api_key)
    adjudications: list[dict[str, Any]] = []
    chosen_map: dict[tuple[str, str, str], dict[str, Any]] = {}

    for row in selected:
        sid = str(row["state_id"])
        bi = str(row["branch_i"])
        bj = str(row["branch_j"])
        ci = cand_map.get((sid, bi), {})
        cj = cand_map.get((sid, bj), {})
        prompt = _prompt_for_pair(row, ci, cj)
        resp = None
        last_err: Exception | None = None
        for attempt in range(max(1, int(args.max_retries))):
            try:
                resp = co.chat(
                    model=str(args.model),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=float(args.temperature),
                    max_tokens=120,
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if "429" in str(exc) or "TooManyRequests" in str(type(exc).__name__):
                    time.sleep(float(args.retry_sleep_sec))
                    continue
                raise
        if resp is None and last_err is not None:
            raise last_err
        text = ""
        if getattr(resp, "message", None) is not None and getattr(resp.message, "content", None):
            parts = resp.message.content
            if parts and hasattr(parts[0], "text"):
                text = str(parts[0].text)

        parsed = _parse_json_obj(text) or {}
        winner = str(parsed.get("winner", "tie")).strip().lower()
        conf = float(parsed.get("confidence", 0.0) or 0.0)
        rationale = str(parsed.get("rationale_short", ""))

        original_label = int(row.get("preference", row.get("label", 0)))
        cohere_label = original_label
        if winner == "branch_i":
            cohere_label = 1
        elif winner == "branch_j":
            cohere_label = 0

        near_tie_flag = bool(abs(float(row.get("margin", 0.0))) <= float(args.near_tie_margin))
        adjacent_flag = bool(row.get("adjacent_rank_flag", False))
        pair_std = float(row.get("pair_uncertainty_std_mean", 0.0))
        strict_gate_ok = True
        if bool(args.strict_hard_slice_only):
            if bool(args.strict_near_tie_required):
                strict_gate_ok = strict_gate_ok and near_tie_flag
            if bool(args.strict_adjacent_required):
                strict_gate_ok = strict_gate_ok and adjacent_flag
            strict_gate_ok = strict_gate_ok and (pair_std >= float(args.strict_min_pair_std))

        replace = (
            winner in {"branch_i", "branch_j"}
            and conf >= float(args.replace_confidence_min)
            and strict_gate_ok
        )
        adjud = {
            "state_id": sid,
            "branch_i": bi,
            "branch_j": bj,
            "hard_score": float(row.get("hard_score", 0.0)),
            "near_tie_flag": near_tie_flag,
            "adjacent_rank_flag": adjacent_flag,
            "pair_uncertainty_std_mean": pair_std,
            "original_label": original_label,
            "cohere_winner": winner,
            "cohere_label": cohere_label,
            "cohere_confidence": conf,
            "replace_label": bool(replace),
            "strict_gate_ok": bool(strict_gate_ok),
            "strict_policy": {
                "strict_hard_slice_only": bool(args.strict_hard_slice_only),
                "strict_near_tie_required": bool(args.strict_near_tie_required),
                "strict_adjacent_required": bool(args.strict_adjacent_required),
                "strict_min_pair_std": float(args.strict_min_pair_std),
            },
            "cohere_model": str(args.model),
            "rationale_short": rationale,
            "prompt_json": prompt,
            "response_text": text,
        }
        adjudications.append(adjud)
        if replace:
            chosen_map[_pair_key(sid, bi, bj)] = adjud

    out_root = Path(args.output_dir)
    adjud_dir = out_root / "cohere_hard_case_adjudication" / args.run_id
    targets_root = out_root / "branch_label_bruteforce_targets" / args.run_id
    base_dir = targets_root / "regime_all_pairs"
    improved_dir = targets_root / "regime_cohere_hard_adjudicated"
    adjud_dir.mkdir(parents=True, exist_ok=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    improved_dir.mkdir(parents=True, exist_ok=True)

    _write_jsonl(adjud_dir / "cohere_adjudications.jsonl", adjudications)

    base_pairs: list[dict[str, Any]] = []
    improved_pairs: list[dict[str, Any]] = []
    replacements = 0
    soft_disagree_downweights = 0
    soft_agree_upweights = 0
    for r in pairwise:
        b = dict(r)
        sid = str(b["state_id"])
        bi = str(b["branch_i"])
        bj = str(b["branch_j"])
        b["pair_type"] = "adjacent_rank" if _pair_key(sid, bi, bj) in adjacent_keys else "generic"
        b["label_source"] = "approx_original"
        b["cohere_adjudicated"] = False
        b["cohere_replaced"] = False
        b["supervision_reliability_weight"] = 1.0
        base_pairs.append(b)

        rr = dict(b)
        key = _pair_key(str(rr["state_id"]), str(rr["branch_i"]), str(rr["branch_j"]))
        picked = chosen_map.get(key)
        if picked is not None:
            rr["preference"] = int(picked["cohere_label"])
            rr["label"] = int(picked["cohere_label"])
            rr["label_source"] = "cohere_adjudicated_hard"
            rr["cohere_adjudicated"] = True
            rr["cohere_replaced"] = True
            rr["cohere_model"] = str(args.model)
            rr["cohere_confidence"] = float(picked["cohere_confidence"])
            rr["replaced_approx_label"] = True
            rr["supervision_reliability_weight"] = min(1.3, 1.0 + 0.3 * float(picked["cohere_confidence"]))
            replacements += 1
        else:
            all_picked = next(
                (
                    a
                    for a in adjudications
                    if _pair_key(str(a["state_id"]), str(a["branch_i"]), str(a["branch_j"])) == key
                ),
                None,
            )
            if all_picked is not None:
                conf = float(all_picked.get("cohere_confidence", 0.0))
                winner = str(all_picked.get("cohere_winner", "tie"))
                coh_lbl = int(all_picked.get("cohere_label", rr.get("preference", rr.get("label", 0))))
                if (
                    winner in {"branch_i", "branch_j"}
                    and conf >= float(args.soft_weight_confidence_min)
                    and bool(all_picked.get("strict_gate_ok", False))
                ):
                    if int(rr.get("preference", rr.get("label", 0))) == coh_lbl:
                        rr["supervision_reliability_weight"] = max(
                            rr.get("supervision_reliability_weight", 1.0),
                            float(args.soft_agree_weight),
                        )
                        rr["cohere_adjudicated"] = True
                        rr["cohere_replaced"] = False
                        rr["cohere_model"] = str(args.model)
                        rr["cohere_confidence"] = conf
                        rr["label_source"] = "cohere_soft_agree_weighted"
                        soft_agree_upweights += 1
                    else:
                        rr["supervision_reliability_weight"] = min(
                            rr.get("supervision_reliability_weight", 1.0),
                            float(args.soft_disagree_weight),
                        )
                        rr["cohere_adjudicated"] = True
                        rr["cohere_replaced"] = False
                        rr["cohere_model"] = str(args.model)
                        rr["cohere_confidence"] = conf
                        rr["label_source"] = "cohere_soft_disagree_downweighted"
                        soft_disagree_downweights += 1
        improved_pairs.append(rr)

    for d, rows in [(base_dir, base_pairs), (improved_dir, improved_pairs)]:
        _write_jsonl(d / "candidate_labels.jsonl", candidates)
        _write_jsonl(d / "pairwise_labels.jsonl", rows)
        _write_jsonl(d / "state_summaries.jsonl", states)

    base_summary = {
        "strategy": "all_pairs",
        "pairs": len(base_pairs),
        "cohere_replaced_pairs": 0,
        "cohere_coverage": 0.0,
    }
    improved_summary = {
        "strategy": "cohere_hard_adjudicated",
        "pairs": len(improved_pairs),
        "cohere_replaced_pairs": replacements,
        "cohere_soft_disagree_downweights": soft_disagree_downweights,
        "cohere_soft_agree_upweights": soft_agree_upweights,
        "cohere_coverage": replacements / max(1, len(improved_pairs)),
    }
    (base_dir / "target_summary.json").write_text(json.dumps(base_summary, indent=2), encoding="utf-8")
    (improved_dir / "target_summary.json").write_text(json.dumps(improved_summary, indent=2), encoding="utf-8")

    manifest = {
        "run_id": args.run_id,
        "labels_dir": str(labels_dir),
        "model": str(args.model),
        "max_pairs": int(args.max_pairs),
        "selected_pairs": len(selected),
        "adjudicated_pairs": len(adjudications),
        "replaced_pairs": replacements,
        "soft_disagree_downweights": soft_disagree_downweights,
        "soft_agree_upweights": soft_agree_upweights,
        "replace_confidence_min": float(args.replace_confidence_min),
        "strict_hard_slice_only": bool(args.strict_hard_slice_only),
        "strict_near_tie_required": bool(args.strict_near_tie_required),
        "strict_adjacent_required": bool(args.strict_adjacent_required),
        "strict_min_pair_std": float(args.strict_min_pair_std),
        "soft_weight_confidence_min": float(args.soft_weight_confidence_min),
        "soft_disagree_weight": float(args.soft_disagree_weight),
        "soft_agree_weight": float(args.soft_agree_weight),
        "outputs": {
            "adjudication_dir": str(adjud_dir),
            "targets_root": str(targets_root),
            "baseline_regime": str(base_dir),
            "improved_regime": str(improved_dir),
        },
    }
    (adjud_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (targets_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "adjudication_dir": str(adjud_dir),
                "targets_root": str(targets_root),
                "replaced_pairs": replacements,
                "soft_disagree_downweights": soft_disagree_downweights,
                "soft_agree_upweights": soft_agree_upweights,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
