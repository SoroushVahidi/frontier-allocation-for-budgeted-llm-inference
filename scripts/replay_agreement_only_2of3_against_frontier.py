#!/usr/bin/env python3
"""Offline replay for frozen `agreement_only_2of3_against_frontier` policy.

No API calls. Consumes existing artifacts only.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from experiments import support_aware_selector as sas


METHOD_ALIASES = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "l1",
    "external_s1_budget_forcing": "s1",
    "external_tale_prompt_budgeting": "tale",
    "s1": "s1",
    "tale": "tale",
}


def _norm(x: Any) -> str | None:
    return sas._normalize_answer(x)


def _is_correct(ans: Any, gold: Any) -> bool:
    a = _norm(ans)
    g = _norm(gold)
    return bool(a and g and a == g)


def _to_bool(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(int(x))
    s = str(x or "").strip().lower()
    return s in {"1", "true", "yes", "y", "t"}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _pooled4(frontier: str | None, l1: str | None, s1: str | None, tale: str | None) -> tuple[str | None, dict[str, Any]]:
    vals = [frontier, l1, s1, tale]
    c = Counter(v for v in vals if v)
    if not c:
        return None, {"reason": "no_parseable_answers", "tie": False, "vote_count": 0}
    top_ans, top_count = c.most_common(1)[0]
    tied = [k for k, v in c.items() if v == top_count]
    if len(tied) > 1:
        # frozen pooled4 convention in repo: frontier tie-break
        return frontier, {"reason": "tied_frontier_tiebreak", "tie": True, "vote_count": int(top_count)}
    return top_ans, {"reason": "majority", "tie": False, "vote_count": int(top_count)}


def _wlt(policy: list[int], other: list[int]) -> tuple[int, int, int]:
    wins = sum(1 for a, b in zip(policy, other) if a == 1 and b == 0)
    losses = sum(1 for a, b in zip(policy, other) if a == 0 and b == 1)
    ties = sum(1 for a, b in zip(policy, other) if a == b)
    return wins, losses, ties


def _bootstrap_delta_pp(a: np.ndarray, b: np.ndarray, *, n_boot: int = 5000, seed: int = 123) -> tuple[float, float, float]:
    if len(a) == 0:
        return (0.0, 0.0, 0.0)
    rng = np.random.default_rng(seed)
    idx = np.arange(len(a))
    deltas = np.zeros(n_boot, dtype=float)
    for i in range(n_boot):
        s = rng.choice(idx, size=len(a), replace=True)
        deltas[i] = 100.0 * (float(np.mean(a[s])) - float(np.mean(b[s])))
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    point = 100.0 * (float(np.mean(a)) - float(np.mean(b)))
    return (point, float(lo), float(hi))


@dataclass
class ReplayRow:
    dataset: str
    source: str
    example_id: str
    frontier_ans: str | None
    l1_ans: str | None
    s1_ans: str | None
    tale_ans: str | None
    current_fta_ans: str | None
    external3_ans: str | None
    pooled4_ans: str | None
    frozen_policy_ans: str | None
    frozen_policy_deferred: bool
    agreement_pattern: str
    selected_action: str
    selected_source: str
    frozen_reason: str
    frontier_correct: bool
    l1_correct: bool
    s1_correct: bool
    tale_correct: bool
    current_fta_correct: bool
    external3_correct: bool
    pooled4_correct: bool
    frozen_policy_correct: bool


def _row_to_dict(r: ReplayRow) -> dict[str, Any]:
    return {
        "dataset": r.dataset,
        "source": r.source,
        "example_id": r.example_id,
        "frontier_ans": r.frontier_ans,
        "l1_ans": r.l1_ans,
        "s1_ans": r.s1_ans,
        "tale_ans": r.tale_ans,
        "current_fta_ans": r.current_fta_ans,
        "external3_ans": r.external3_ans,
        "pooled4_ans": r.pooled4_ans,
        "frozen_policy_ans": r.frozen_policy_ans,
        "frozen_policy_deferred": int(r.frozen_policy_deferred),
        "agreement_pattern": r.agreement_pattern,
        "selected_action": r.selected_action,
        "selected_source": r.selected_source,
        "frozen_reason": r.frozen_reason,
        "frontier_correct": int(r.frontier_correct),
        "l1_correct": int(r.l1_correct),
        "s1_correct": int(r.s1_correct),
        "tale_correct": int(r.tale_correct),
        "current_fta_correct": int(r.current_fta_correct),
        "external3_correct": int(r.external3_correct),
        "pooled4_correct": int(r.pooled4_correct),
        "frozen_policy_correct": int(r.frozen_policy_correct),
    }


def _make_row_from_jsonl_group(
    *,
    dataset_name: str,
    source_name: str,
    example_id: str,
    grouped: dict[str, dict[str, Any]],
) -> ReplayRow | None:
    if not {"frontier", "l1", "s1", "tale"}.issubset(grouped.keys()):
        return None

    frontier_row = grouped["frontier"]
    l1_row = grouped["l1"]
    s1_row = grouped["s1"]
    tale_row = grouped["tale"]

    frontier = _norm(frontier_row.get("final_answer_canonical") or frontier_row.get("selected_answer_canonical") or frontier_row.get("final_answer_raw"))
    l1 = _norm(l1_row.get("final_answer_canonical") or l1_row.get("selected_answer_canonical") or l1_row.get("final_answer_raw"))
    s1 = _norm(s1_row.get("final_answer_canonical") or s1_row.get("selected_answer_canonical") or s1_row.get("final_answer_raw"))
    tale = _norm(tale_row.get("final_answer_canonical") or tale_row.get("selected_answer_canonical") or tale_row.get("final_answer_raw"))

    rm = frontier_row.get("result_metadata") or {}
    if isinstance(rm, str):
        try:
            rm = json.loads(rm)
        except Exception:
            rm = {}

    ext = {
        "external_l1_max": l1,
        "external_s1_budget_forcing": s1,
        "external_tale_prompt_budgeting": tale,
    }

    # Current FTA replay (FIX-2+FIX-4): exact policy-faithful reconstruction.
    fix24 = sas.apply_combined_fix24_to_row(
        {
            "method": "direct_reserve_semantic_frontier_v2",
            "final_answer_canonical": frontier,
            "selected_answer_canonical": frontier,
            "final_answer_raw": frontier,
            "result_metadata": rm,
        },
        external_answers=ext,
    )
    current_fta = _norm(fix24.get("combined24_answer_canonical"))

    ext3, _ext_meta = sas.select_external_majority(ext)
    ext3 = _norm(ext3)

    pooled4, _p4_meta = _pooled4(frontier, l1, s1, tale)

    frozen_ans, frozen_meta = sas.agreement_only_2of3_against_frontier(
        frontier_answer=frontier,
        l1_answer=l1,
        s1_answer=s1,
        tale_answer=tale,
    )
    frozen_ans = _norm(frozen_ans)

    gold = _norm(
        frontier_row.get("gold_answer_canonical")
        or frontier_row.get("gold_answer")
    )

    frontier_correct = _is_correct(frontier, gold)
    l1_correct = _is_correct(l1, gold)
    s1_correct = _is_correct(s1, gold)
    tale_correct = _is_correct(tale, gold)
    current_fta_correct = _is_correct(current_fta, gold)
    external3_correct = _is_correct(ext3, gold)
    pooled4_correct = _is_correct(pooled4, gold)
    frozen_correct = _is_correct(frozen_ans, gold)

    return ReplayRow(
        dataset=dataset_name,
        source=source_name,
        example_id=example_id,
        frontier_ans=frontier,
        l1_ans=l1,
        s1_ans=s1,
        tale_ans=tale,
        current_fta_ans=current_fta,
        external3_ans=ext3,
        pooled4_ans=pooled4,
        frozen_policy_ans=frozen_ans,
        frozen_policy_deferred=bool(frozen_meta.get("deferred", False)),
        agreement_pattern=str(frozen_meta.get("agreement_pattern", "")),
        selected_action=str(frozen_meta.get("selected_action", "")),
        selected_source=str(frozen_meta.get("selected_source", "")),
        frozen_reason=str(frozen_meta.get("reason", "")),
        frontier_correct=frontier_correct,
        l1_correct=l1_correct,
        s1_correct=s1_correct,
        tale_correct=tale_correct,
        current_fta_correct=current_fta_correct,
        external3_correct=external3_correct,
        pooled4_correct=pooled4_correct,
        frozen_policy_correct=frozen_correct,
    )


def _rows_from_jsonl(path: Path, dataset_name: str, source_name: str) -> list[ReplayRow]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in _load_jsonl(path):
        method = METHOD_ALIASES.get(str(row.get("method") or ""))
        if method is None:
            continue
        ex = str(row.get("example_id") or "")
        if not ex:
            continue
        grouped[ex][method] = row

    out: list[ReplayRow] = []
    for ex, mm in grouped.items():
        rr = _make_row_from_jsonl_group(
            dataset_name=dataset_name,
            source_name=source_name,
            example_id=ex,
            grouped=mm,
        )
        if rr is not None:
            out.append(rr)
    return out


def _rows_from_complete_case_csv(path: Path, dataset_name: str, source_name: str) -> list[ReplayRow]:
    out: list[ReplayRow] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ex = str(row.get("example_id") or "")
            if not ex:
                continue
            frontier = _norm(row.get("frontier_ans"))
            l1 = _norm(row.get("l1_ans"))
            s1 = _norm(row.get("s1_ans"))
            tale = _norm(row.get("tale_ans"))
            current_fta = _norm(row.get("fta_ans"))
            ext3, _ = sas.select_external_majority(
                {
                    "external_l1_max": l1,
                    "external_s1_budget_forcing": s1,
                    "external_tale_prompt_budgeting": tale,
                }
            )
            ext3 = _norm(ext3)
            pooled4, _ = _pooled4(frontier, l1, s1, tale)

            frozen_ans, frozen_meta = sas.agreement_only_2of3_against_frontier(
                frontier_answer=frontier,
                l1_answer=l1,
                s1_answer=s1,
                tale_answer=tale,
            )
            frozen_ans = _norm(frozen_ans)

            gold = _norm(row.get("gold_answer_canonical"))
            frontier_correct = _to_bool(row.get("frontier_default_correct"))
            l1_correct = _to_bool(row.get("always_l1_correct"))
            s1_correct = _to_bool(row.get("s1_correct"))
            tale_correct = _to_bool(row.get("tale_correct"))
            current_fta_correct = _to_bool(row.get("fta_fix2_fix4_correct"))
            external3_correct = _to_bool(row.get("external3_majority_correct")) if row.get("external3_majority_correct") not in (None, "") else _is_correct(ext3, gold)
            pooled4_correct = _to_bool(row.get("pooled4_majority_correct")) if row.get("pooled4_majority_correct") not in (None, "") else _is_correct(pooled4, gold)
            # Preserve artifact-consistent correctness where available.
            frozen_correct = None
            if frozen_ans:
                candidates = [
                    (frontier, frontier_correct),
                    (l1, l1_correct),
                    (s1, s1_correct),
                    (tale, tale_correct),
                    (current_fta, current_fta_correct),
                    (ext3, external3_correct),
                    (pooled4, pooled4_correct),
                ]
                matched = [c for a, c in candidates if a and a == frozen_ans]
                if matched:
                    frozen_correct = bool(any(matched))
            if frozen_correct is None:
                frozen_correct = _is_correct(frozen_ans, gold)

            out.append(
                ReplayRow(
                    dataset=dataset_name,
                    source=source_name,
                    example_id=ex,
                    frontier_ans=frontier,
                    l1_ans=l1,
                    s1_ans=s1,
                    tale_ans=tale,
                    current_fta_ans=current_fta,
                    external3_ans=ext3,
                    pooled4_ans=pooled4,
                    frozen_policy_ans=frozen_ans,
                    frozen_policy_deferred=bool(frozen_meta.get("deferred", False)),
                    agreement_pattern=str(frozen_meta.get("agreement_pattern", "")),
                    selected_action=str(frozen_meta.get("selected_action", "")),
                    selected_source=str(frozen_meta.get("selected_source", "")),
                    frozen_reason=str(frozen_meta.get("reason", "")),
                    frontier_correct=frontier_correct,
                    l1_correct=l1_correct,
                    s1_correct=s1_correct,
                    tale_correct=tale_correct,
                    current_fta_correct=current_fta_correct,
                    external3_correct=external3_correct,
                    pooled4_correct=pooled4_correct,
                    frozen_policy_correct=frozen_correct,
                )
            )
    return out


def _summarize(rows: list[ReplayRow], label: str) -> dict[str, Any]:
    n = len(rows)
    p = [int(r.frozen_policy_correct) for r in rows]
    frontier = [int(r.frontier_correct) for r in rows]
    l1 = [int(r.l1_correct) for r in rows]
    pooled4 = [int(r.pooled4_correct) for r in rows]
    curr = [int(r.current_fta_correct) for r in rows]

    recoveries = sum(1 for r in rows if (not r.frontier_correct) and r.frozen_policy_correct)
    regressions = sum(1 for r in rows if r.frontier_correct and (not r.frozen_policy_correct))

    oracle = [
        int(any([r.frontier_correct, r.l1_correct, r.s1_correct, r.tale_correct]))
        for r in rows
    ]

    wins_curr, losses_curr, ties_curr = _wlt(p, curr)
    wins_l1, losses_l1, ties_l1 = _wlt(p, l1)

    acc = (sum(p) / n) if n else 0.0
    acc_frontier = (sum(frontier) / n) if n else 0.0
    acc_l1 = (sum(l1) / n) if n else 0.0
    acc_pooled4 = (sum(pooled4) / n) if n else 0.0

    return {
        "dataset": label,
        "n": n,
        "policy": sas.AGREEMENT_ONLY_2OF3_POLICY_NAME,
        "correct": int(sum(p)),
        "accuracy": acc,
        "delta_vs_frontier_pp": 100.0 * (acc - acc_frontier),
        "delta_vs_l1_pp": 100.0 * (acc - acc_l1),
        "delta_vs_pooled4_pp": 100.0 * (acc - acc_pooled4),
        "deferral_rate": (sum(1 for r in rows if r.frozen_policy_deferred) / n) if n else 0.0,
        "recoveries_vs_frontier": recoveries,
        "regressions_vs_frontier": regressions,
        "net_gain_vs_frontier": recoveries - regressions,
        "oracle_correct_pool4": int(sum(oracle)),
        "oracle_regret_count_pool4": int(sum(oracle) - sum(p)),
        "wins_vs_current_fta": wins_curr,
        "losses_vs_current_fta": losses_curr,
        "ties_vs_current_fta": ties_curr,
        "wins_vs_l1": wins_l1,
        "losses_vs_l1": losses_l1,
        "ties_vs_l1": ties_l1,
    }


def _ci_rows(rows: list[ReplayRow], label: str) -> list[dict[str, Any]]:
    p = np.array([int(r.frozen_policy_correct) for r in rows], dtype=int)
    curr = np.array([int(r.current_fta_correct) for r in rows], dtype=int)
    l1 = np.array([int(r.l1_correct) for r in rows], dtype=int)
    pooled4 = np.array([int(r.pooled4_correct) for r in rows], dtype=int)

    out: list[dict[str, Any]] = []
    for comp_name, comp in [
        ("current_fta", curr),
        ("l1", l1),
        ("pooled4", pooled4),
    ]:
        delta, lo, hi = _bootstrap_delta_pp(p, comp)
        w, l, t = _wlt(list(p), list(comp))
        out.append(
            {
                "dataset": label,
                "policy": sas.AGREEMENT_ONLY_2OF3_POLICY_NAME,
                "comparison": comp_name,
                "delta_pp": delta,
                "ci95_low_pp": lo,
                "ci95_high_pp": hi,
                "wins": w,
                "losses": l,
                "ties": t,
            }
        )
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in rows for k in r.keys()}) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input-jsonl", action="append", default=[], help="Per-example records JSONL (repeatable)")
    p.add_argument("--input-complete-case-csv", action="append", default=[], help="Complete-case CSV (repeatable)")
    p.add_argument("--dataset-label", action="append", default=[], help="Optional dataset label per input file")
    p.add_argument("--source-label", action="append", default=[], help="Optional source label per input file")
    p.add_argument("--output-dir", type=Path, required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=False)

    inputs: list[tuple[str, Path]] = []
    for x in args.input_jsonl:
        inputs.append(("jsonl", Path(x)))
    for x in args.input_complete_case_csv:
        inputs.append(("complete_case_csv", Path(x)))

    if not inputs:
        raise SystemExit("At least one input is required")

    dataset_labels = list(args.dataset_label)
    source_labels = list(args.source_label)
    while len(dataset_labels) < len(inputs):
        dataset_labels.append("")
    while len(source_labels) < len(inputs):
        source_labels.append("")

    all_rows: list[ReplayRow] = []
    input_summary: list[dict[str, Any]] = []

    for idx, (kind, path) in enumerate(inputs):
        if not path.exists():
            raise FileNotFoundError(path)
        dataset_label = dataset_labels[idx] or ("math500" if kind == "complete_case_csv" else "gsm8k")
        source_label = source_labels[idx] or path.parent.name

        if kind == "jsonl":
            rows = _rows_from_jsonl(path, dataset_label, source_label)
        else:
            rows = _rows_from_complete_case_csv(path, dataset_label, source_label)

        all_rows.extend(rows)
        input_summary.append({"kind": kind, "path": str(path), "dataset_label": dataset_label, "source_label": source_label, "n_rows": len(rows)})

    per_example_rows = [_row_to_dict(r) for r in all_rows]
    _write_csv(out_dir / "per_example_policy_replay.csv", per_example_rows)

    by_dataset: dict[str, list[ReplayRow]] = defaultdict(list)
    for r in all_rows:
        by_dataset[r.dataset].append(r)

    summary_rows: list[dict[str, Any]] = []
    ci_rows: list[dict[str, Any]] = []

    for ds in sorted(by_dataset):
        rows = by_dataset[ds]
        summary_rows.append(_summarize(rows, ds))
        ci_rows.extend(_ci_rows(rows, ds))

    # Combined summary across all provided datasets.
    summary_rows.append(_summarize(all_rows, "combined"))
    ci_rows.extend(_ci_rows(all_rows, "combined"))

    _write_csv(out_dir / "policy_summary.csv", summary_rows)
    _write_csv(out_dir / "paired_ci_summary.csv", ci_rows)

    manifest = {
        "analysis_type": "offline_replay_frozen_agreement_only_2of3_against_frontier",
        "policy_name": sas.AGREEMENT_ONLY_2OF3_POLICY_NAME,
        "policy_version": sas.AGREEMENT_ONLY_2OF3_POLICY_VERSION,
        "inputs": input_summary,
        "outputs": [
            str(out_dir / "per_example_policy_replay.csv"),
            str(out_dir / "policy_summary.csv"),
            str(out_dir / "paired_ci_summary.csv"),
            str(out_dir / "manifest.json"),
        ],
        "no_api_calls": True,
        "runtime_legal_inputs_only": True,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(out_dir)


if __name__ == "__main__":
    main()
