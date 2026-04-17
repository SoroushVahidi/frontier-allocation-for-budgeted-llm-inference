#!/usr/bin/env python3
"""Bounded Cohere Rerank branch-allocation comparison on canonical branch-label artifacts."""

from __future__ import annotations

import argparse
import hashlib
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _split_for_state(state_id: str, seed: int, train_ratio: float, val_ratio: float) -> str:
    h = hashlib.sha256(f"split|{seed}|{state_id}".encode("utf-8")).hexdigest()
    r = int(h[:12], 16) / float(16**12)
    if r < train_ratio:
        return "train"
    if r < train_ratio + val_ratio:
        return "val"
    return "test"


def _pair_key(state_id: str, bi: str, bj: str) -> tuple[str, str, str]:
    a, b = sorted([str(bi), str(bj)])
    return (str(state_id), a, b)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _candidate_doc(row: dict[str, Any], rank_hint: int) -> str:
    f = row.get("features_branch_v1", {}) if isinstance(row.get("features_branch_v1"), dict) else {}
    payload = {
        "branch_id": str(row.get("branch_id", "")),
        "rank_hint_by_estimated_value": int(rank_hint),
        "estimated_value_if_allocate_next": _safe_float(row.get("estimated_value_if_allocate_next", 0.0)),
        "branch_vs_outside_gap": _safe_float(row.get("branch_vs_outside_gap", 0.0)),
        "allocation_value_std": _safe_float(row.get("allocation_value_std", 0.0)),
        "allocation_candidates_evaluated": int(row.get("allocation_candidates_evaluated", 0) or 0),
        "mode": str(row.get("mode", "unknown")),
        "score": _safe_float(f.get("score", 0.0)),
        "depth": _safe_float(f.get("depth", 0.0)),
        "stalled_steps": _safe_float(f.get("stalled_steps", 0.0)),
        "recent_delta": _safe_float(f.get("recent_delta", 0.0)),
        "verify_count": _safe_float(f.get("verify_count", 0.0)),
        "branch_age": _safe_float(f.get("branch_age", 0.0)),
        "parent_relative_score": _safe_float(f.get("parent_relative_score", 0.0)),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _budget_query(state_id: str, dataset_name: str, remaining_budget: int, branch_count: int) -> str:
    query_payload = {
        "task": "rank branches for next compute allocation",
        "objective": "pick branch that most deserves the NEXT unit of compute under fixed budget",
        "selection_rule": [
            "prefer strong expected marginal gain",
            "discount branches with weak outside-option advantage",
            "consider uncertainty and recent progress signals",
            "be conservative near ambiguous ties",
        ],
        "state_context": {
            "state_id": str(state_id),
            "dataset_name": str(dataset_name),
            "remaining_budget": int(remaining_budget),
            "branch_count": int(branch_count),
        },
    }
    return json.dumps(query_payload, ensure_ascii=False, sort_keys=True)


def _near_tie_state(cands: list[dict[str, Any]], margin: float) -> bool:
    ranked = sorted(cands, key=lambda r: _safe_float(r.get("estimated_value_if_allocate_next", 0.0)), reverse=True)
    if len(ranked) < 2:
        return False
    gap = _safe_float(ranked[0].get("estimated_value_if_allocate_next", 0.0)) - _safe_float(ranked[1].get("estimated_value_if_allocate_next", 0.0))
    return abs(gap) <= float(margin)


def _pairwise_vote_top1(state_id: str, cands: list[dict[str, Any]], pair_rows: list[dict[str, Any]]) -> str:
    wins = {str(c["branch_id"]): 0 for c in cands}
    for r in pair_rows:
        if str(r.get("state_id", "")) != state_id:
            continue
        bi = str(r.get("branch_i", ""))
        bj = str(r.get("branch_j", ""))
        if bi not in wins or bj not in wins:
            continue
        pref = int(r.get("preference", r.get("label", 0)))
        if pref == 1:
            wins[bi] += 1
        else:
            wins[bj] += 1
    return max(wins.items(), key=lambda kv: (kv[1], kv[0]))[0]


def _score_top1(cands: list[dict[str, Any]]) -> str:
    return str(max(cands, key=lambda r: _safe_float((r.get("features_branch_v1") or {}).get("score", 0.0))).get("branch_id", ""))


def _oracle_top1(cands: list[dict[str, Any]]) -> str:
    return str(max(cands, key=lambda r: _safe_float(r.get("estimated_value_if_allocate_next", 0.0))).get("branch_id", ""))


def _value_by_branch(cands: list[dict[str, Any]]) -> dict[str, float]:
    return {str(c.get("branch_id", "")): _safe_float(c.get("estimated_value_if_allocate_next", 0.0)) for c in cands}


def _compute_metrics(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    if not rows:
        return {"states": 0}
    acc = sum(int(r.get(key) == r.get("oracle_top1")) for r in rows) / len(rows)
    mean_gap = sum(float(r.get("oracle_value", 0.0)) - float(r.get(f"{key}_value", 0.0)) for r in rows) / len(rows)
    near = [r for r in rows if bool(r.get("near_tie_state", False))]
    non_near = [r for r in rows if not bool(r.get("near_tie_state", False))]
    by_budget: dict[str, dict[str, float]] = {}
    for r in rows:
        b = str(r.get("remaining_budget", 0))
        d = by_budget.setdefault(b, {"n": 0.0, "ok": 0.0})
        d["n"] += 1.0
        d["ok"] += float(int(r.get(key) == r.get("oracle_top1")))
    by_budget_acc = {b: (d["ok"] / max(1.0, d["n"])) for b, d in sorted(by_budget.items(), key=lambda kv: int(kv[0]))}
    return {
        "states": len(rows),
        "top1_accuracy_vs_oracle_proxy": acc,
        "mean_oracle_gap": mean_gap,
        "near_tie_top1_accuracy": (sum(int(r.get(key) == r.get("oracle_top1")) for r in near) / len(near)) if near else 0.0,
        "non_near_tie_top1_accuracy": (sum(int(r.get(key) == r.get("oracle_top1")) for r in non_near) / len(non_near)) if non_near else 0.0,
        "budget_accuracy": by_budget_acc,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded Cohere Rerank branch-allocation comparison")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--output-root", default="outputs/cohere_branch_allocation_rerank")
    p.add_argument("--run-id", required=True)
    p.add_argument("--model", default="rerank-v3.5")
    p.add_argument("--top-n", type=int, default=8)
    p.add_argument("--max-states", type=int, default=80)
    p.add_argument("--split-seed", type=int, default=17)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument("--eval-split", choices=["all", "train", "val", "test"], default="test")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--hard-only-fallback", action="store_true")
    p.add_argument("--fallback-policy", choices=["heuristic_score", "pairwise_vote"], default="heuristic_score")
    p.add_argument("--max-retries", type=int, default=5)
    p.add_argument("--retry-sleep-sec", type=float, default=2.5)
    p.add_argument("--sleep-sec", type=float, default=0.0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    labels_dir = Path(args.labels_dir)
    candidates = _read_jsonl(labels_dir / "candidate_labels.jsonl")
    pairwise = _read_jsonl(labels_dir / "pairwise_labels.jsonl")

    by_state: dict[str, list[dict[str, Any]]] = {}
    for c in candidates:
        sid = str(c.get("state_id", ""))
        by_state.setdefault(sid, []).append(c)

    state_ids = sorted(by_state.keys())
    selected_states: list[str] = []
    for sid in state_ids:
        split = _split_for_state(sid, args.split_seed, args.train_ratio, args.val_ratio)
        if args.eval_split != "all" and split != args.eval_split:
            continue
        if len(by_state[sid]) >= 2:
            selected_states.append(sid)
    selected_states = selected_states[: max(1, int(args.max_states))]

    api_key = os.environ.get("COHERE_API_KEY", "")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY missing")
    client = cohere.ClientV2(api_key=api_key)

    out_dir = Path(args.output_root) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    request_rows: list[dict[str, Any]] = []
    ranking_rows: list[dict[str, Any]] = []

    for sid in selected_states:
        cands = by_state[sid]
        ranked_hint = sorted(cands, key=lambda r: _safe_float(r.get("estimated_value_if_allocate_next", 0.0)), reverse=True)
        rank_map = {str(r.get("branch_id", "")): i + 1 for i, r in enumerate(ranked_hint)}
        docs = [_candidate_doc(c, rank_map.get(str(c.get("branch_id", "")), 999)) for c in cands]
        query = _budget_query(
            state_id=sid,
            dataset_name=str(cands[0].get("dataset_name", "unknown")),
            remaining_budget=int(cands[0].get("remaining_budget", 0) or 0),
            branch_count=len(cands),
        )
        near_tie = _near_tie_state(cands, float(args.near_tie_margin))

        fallback_top1 = _score_top1(cands) if args.fallback_policy == "heuristic_score" else _pairwise_vote_top1(sid, cands, pairwise)
        use_cohere = (not bool(args.hard_only_fallback)) or near_tie

        ordered_branch_ids: list[str] = []
        rerank_scores: list[float] = []
        error_text = ""
        if use_cohere:
            resp = None
            last_err: Exception | None = None
            for _attempt in range(max(1, int(args.max_retries))):
                try:
                    resp = client.rerank(
                        model=str(args.model),
                        query=query,
                        documents=docs,
                        top_n=min(max(1, int(args.top_n)), len(docs)),
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
            results = list(getattr(resp, "results", []) or [])
            seen: set[int] = set()
            for item in results:
                idx = int(getattr(item, "index", -1))
                if idx < 0 or idx >= len(cands):
                    continue
                seen.add(idx)
                ordered_branch_ids.append(str(cands[idx].get("branch_id", "")))
                rerank_scores.append(_safe_float(getattr(item, "relevance_score", 0.0)))
            for idx in range(len(cands)):
                if idx not in seen:
                    ordered_branch_ids.append(str(cands[idx].get("branch_id", "")))
                    rerank_scores.append(float("nan"))
        else:
            ordered_branch_ids = [fallback_top1] + [str(c.get("branch_id", "")) for c in cands if str(c.get("branch_id", "")) != fallback_top1]
            rerank_scores = [float("nan")] * len(ordered_branch_ids)

        cohere_top1 = ordered_branch_ids[0] if ordered_branch_ids else fallback_top1
        oracle_top1 = _oracle_top1(cands)
        score_top1 = _score_top1(cands)
        pairwise_top1 = _pairwise_vote_top1(sid, cands, pairwise)
        values = _value_by_branch(cands)

        request_rows.append(
            {
                "state_id": sid,
                "query_json": query,
                "candidate_docs": docs,
                "cohere_called": bool(use_cohere),
                "fallback_policy": str(args.fallback_policy),
                "hard_only_fallback": bool(args.hard_only_fallback),
                "near_tie_state": bool(near_tie),
                "cohere_error": error_text,
            }
        )
        ranking_rows.append(
            {
                "state_id": sid,
                "dataset_name": str(cands[0].get("dataset_name", "unknown")),
                "remaining_budget": int(cands[0].get("remaining_budget", 0) or 0),
                "branch_count": len(cands),
                "near_tie_state": bool(near_tie),
                "oracle_top1": oracle_top1,
                "oracle_value": values.get(oracle_top1, 0.0),
                "cohere_top1": cohere_top1,
                "cohere_top1_value": values.get(cohere_top1, 0.0),
                "heuristic_score_top1": score_top1,
                "heuristic_score_top1_value": values.get(score_top1, 0.0),
                "pairwise_vote_top1": pairwise_top1,
                "pairwise_vote_top1_value": values.get(pairwise_top1, 0.0),
                "cohere_called": bool(use_cohere),
                "cohere_ranked_branch_ids": ordered_branch_ids,
                "cohere_relevance_scores": rerank_scores,
            }
        )
        if float(args.sleep_sec) > 0:
            time.sleep(float(args.sleep_sec))

    comparison = {
        "cohere_rerank": _compute_metrics(ranking_rows, "cohere_top1"),
        "heuristic_score": _compute_metrics(ranking_rows, "heuristic_score_top1"),
        "pairwise_vote": _compute_metrics(ranking_rows, "pairwise_vote_top1"),
    }
    coverage = sum(int(r.get("cohere_called", False)) for r in ranking_rows) / max(1, len(ranking_rows))
    summary = {
        "run_id": str(args.run_id),
        "labels_dir": str(labels_dir),
        "evaluation": {
            "states_evaluated": len(ranking_rows),
            "eval_split": str(args.eval_split),
            "hard_only_fallback": bool(args.hard_only_fallback),
            "cohere_call_coverage": coverage,
            "near_tie_margin": float(args.near_tie_margin),
        },
        "cohere_config": {
            "model": str(args.model),
            "top_n": int(args.top_n),
            "max_retries": int(args.max_retries),
            "retry_sleep_sec": float(args.retry_sleep_sec),
        },
        "comparison_metrics": comparison,
        "assumptions": [
            "Oracle proxy for top-1 correctness is max estimated_value_if_allocate_next from candidate_labels.",
            "Cohere method is listwise rerank over serialized candidate docs; baseline policies are score-top1 and pairwise-vote top1.",
            "This bounded run evaluates decision proxy quality, not end-to-end solve accuracy.",
        ],
        "caveats": [
            "Listwise-vs-pairwise mismatch remains; comparison uses a shared top-1 proxy target for honesty.",
            "If labels are approximate, oracle proxy inherits approximation noise.",
            "Hard-only fallback mode changes Cohere coverage and should be interpreted as selective-helper behavior.",
        ],
        "artifacts": {
            "request_rows": str(out_dir / "cohere_requests.jsonl"),
            "state_rankings": str(out_dir / "state_rankings.jsonl"),
            "summary_json": str(out_dir / "summary_metrics.json"),
            "summary_md": str(out_dir / "summary_metrics.md"),
            "run_manifest": str(out_dir / "run_manifest.json"),
        },
    }

    _write_jsonl(out_dir / "cohere_requests.jsonl", request_rows)
    _write_jsonl(out_dir / "state_rankings.jsonl", ranking_rows)
    _write_json(out_dir / "summary_metrics.json", summary)

    md_lines = [
        f"# Cohere rerank branch-allocation comparison ({args.run_id})",
        "",
        f"- labels_dir: `{labels_dir}`",
        f"- eval_split: `{args.eval_split}`",
        f"- states_evaluated: `{len(ranking_rows)}`",
        f"- hard_only_fallback: `{bool(args.hard_only_fallback)}`",
        f"- cohere_call_coverage: `{coverage:.4f}`",
        "",
        "## Top-1 accuracy vs oracle proxy",
        f"- Cohere rerank: `{comparison['cohere_rerank'].get('top1_accuracy_vs_oracle_proxy', 0.0):.4f}`",
        f"- Heuristic score baseline: `{comparison['heuristic_score'].get('top1_accuracy_vs_oracle_proxy', 0.0):.4f}`",
        f"- Pairwise-vote baseline: `{comparison['pairwise_vote'].get('top1_accuracy_vs_oracle_proxy', 0.0):.4f}`",
        "",
        "## Mean oracle-value gap (lower better)",
        f"- Cohere rerank: `{comparison['cohere_rerank'].get('mean_oracle_gap', 0.0):.6f}`",
        f"- Heuristic score baseline: `{comparison['heuristic_score'].get('mean_oracle_gap', 0.0):.6f}`",
        f"- Pairwise-vote baseline: `{comparison['pairwise_vote'].get('mean_oracle_gap', 0.0):.6f}`",
    ]
    (out_dir / "summary_metrics.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    manifest = {
        "script": "scripts/run_cohere_rerank_branch_allocation_experiment.py",
        "run_id": str(args.run_id),
        "timestamp_unix": time.time(),
        "args": vars(args),
        "output_dir": str(out_dir),
        "command_template": (
            "python scripts/run_cohere_rerank_branch_allocation_experiment.py "
            "--labels-dir <labels_dir> --run-id <run_id>"
        ),
    }
    _write_json(out_dir / "run_manifest.json", manifest)

    print(json.dumps({
        "output_dir": str(out_dir),
        "states_evaluated": len(ranking_rows),
        "cohere_top1_acc": comparison["cohere_rerank"]["top1_accuracy_vs_oracle_proxy"],
        "heuristic_top1_acc": comparison["heuristic_score"]["top1_accuracy_vs_oracle_proxy"],
        "pairwise_top1_acc": comparison["pairwise_vote"]["top1_accuracy_vs_oracle_proxy"],
    }, indent=2))


if __name__ == "__main__":
    main()
