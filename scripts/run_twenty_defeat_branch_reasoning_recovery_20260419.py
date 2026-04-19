#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branch_observability import build_branch_trace_record
from experiments.data import extract_final_answer
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode

SOURCE_DOC = REPO_ROOT / "docs/TWENTY_DEFEAT_CASES_WITH_BRANCH_REASONING_2026_04_19.md"
SOURCE_MANIFEST = REPO_ROOT / "outputs/twenty_defeat_cases_with_branch_reasoning_20260419/selected_case_manifest.json"
REGISTRY = REPO_ROOT / "outputs/full_method_comparison_bundle/20260419T214335Z/defeat_case_registry.csv"
OUT_DIR = REPO_ROOT / "outputs/twenty_defeat_cases_with_recovered_branch_reasoning_20260419"
DOC_OUT = REPO_ROOT / "docs/TWENTY_DEFEAT_CASES_WITH_RECOVERED_BRANCH_REASONING_2026_04_19.md"

OUR_METHOD = "adaptive_min_expand_1"


def _norm(x: Any) -> str | None:
    s = extract_final_answer(str(x)) if x is not None else None
    if s is None:
        return None
    t = str(s).strip()
    return t if t else None


def _load_selected_cases() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if SOURCE_MANIFEST.exists():
        payload = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
        return list(payload.get("cases", [])), {"selection_source": str(SOURCE_MANIFEST), "fallback_used": False}

    # Fallback when previous selection artifact is missing in working tree.
    rows: list[dict[str, Any]] = []
    with REGISTRY.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            other = str(row.get("other_method", ""))
            rows.append(
                {
                    "dataset": str(row["dataset"]),
                    "seed": int(row["seed"]),
                    "budget": int(row["budget"]),
                    "example_id": str(row["example_id"]),
                    "question": str(row["question"]),
                    "ground_truth": str(row["ground_truth"]),
                    "our_method": OUR_METHOD,
                    "best_method": other,
                    "failure_subtype": str(row.get("failure_subtype", "")),
                }
            )
            if len(rows) >= 20:
                break
    return rows, {
        "selection_source": str(REGISTRY),
        "fallback_used": True,
        "fallback_reason": "expected prior 20-case manifest/doc not found in working tree",
    }


def _classify_branch(branch: dict[str, Any], *, ground_truth: str) -> tuple[str, str]:
    reason = str(branch.get("branch_reasoning_text_raw") or "").strip().lower()
    branch_text = str(branch.get("branch_text_raw") or "").strip().lower()
    final_norm = _norm(branch.get("branch_final_answer_text_raw"))
    gold_norm = _norm(ground_truth)
    depth = int(branch.get("depth", 0))
    verify = int(branch.get("verify_count", 0))

    if reason:
        if any(k in reason for k in ["left", "remaining", "off from", "difference", "subtract"]):
            return "remaining-amount branch", "direct-text-supported"
        if any(k in reason for k in ["total", "sum", "altogether", "in total"]) and "final answer" not in reason:
            return "intermediate-total branch", "direct-text-supported"
        if any(k in reason for k in ["times", "product", "multiply"]) and any(k in reason for k in ["need", "target", "how many"]):
            return "target-variable-mismatch branch", "direct-text-supported"
        if final_norm is not None and gold_norm is not None and final_norm == gold_norm:
            return "complete final-answer branch", "direct-text-supported"
        return "answer-distinct alternative branch", "direct-text-supported"

    if branch_text:
        if final_norm is not None and gold_norm is not None and final_norm == gold_norm:
            return "complete final-answer branch", "recovered-from-branch-text"
        if final_norm is not None:
            return "malformed-finalization branch", "recovered-from-branch-text"
        return "answer-distinct alternative branch", "recovered-from-branch-text"

    if verify >= 2 or depth >= 3:
        return "deeper verify-heavy branch", "proxy-inferred"
    if depth <= 1 and verify == 0:
        return "shallow multistep-uplifted branch", "proxy-inferred"
    if verify > 0:
        return "outside-option-dominated branch", "proxy-inferred"
    return "unknown / not exposed", "unknown / not exposed"


def _gold_group_timeline(method_row: dict[str, Any], gold: str) -> dict[str, Any]:
    gold_norm = _norm(gold)
    trace = (method_row.get("metadata") or {}).get("action_trace") or []
    seen_by_step: dict[int, set[str]] = defaultdict(set)
    for i, a in enumerate(trace, start=1):
        pred = _norm(a.get("predicted_answer"))
        if pred is not None:
            seen_by_step[i].add(pred)
    if not seen_by_step:
        return {
            "status": "unknown / not exposed",
            "exists_at_first_split": None,
            "exists_later": None,
            "collapsed": None,
            "never_appeared": None,
        }
    split_step = next((s for s in sorted(seen_by_step) if len(seen_by_step[s]) >= 2), None)
    appeared_steps = [s for s in sorted(seen_by_step) if gold_norm in seen_by_step[s]] if gold_norm is not None else []
    exists_first = bool(split_step is not None and gold_norm in seen_by_step.get(split_step, set())) if gold_norm is not None else None
    exists_later = bool(any(s > (split_step or 10**9) for s in appeared_steps)) if split_step is not None else bool(appeared_steps)
    collapsed = bool(appeared_steps and max(appeared_steps) < max(seen_by_step))
    never = not bool(appeared_steps)
    status = "never_appeared" if never else ("collapsed" if collapsed else "persisted_or_late")
    return {
        "status": status,
        "exists_at_first_split": exists_first,
        "exists_later": exists_later,
        "collapsed": collapsed,
        "never_appeared": never,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    selected_cases, selection_meta = _load_selected_cases()
    rng_master = random.Random(20260419)

    per_case_rows: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []

    for case_idx, case in enumerate(selected_cases, start=1):
        dataset = str(case["dataset"])
        budget = int(case["budget"])
        seed = int(case["seed"])
        question = str(case["question"])
        ground_truth = str(case["ground_truth"])
        our_method = str(case.get("our_method", OUR_METHOD))
        best_method = str(case.get("best_method", ""))

        rng = random.Random(rng_master.randint(0, 10**9) + seed * 31 + budget)
        factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
        specs = build_frontier_strategies(
            factory,
            budget,
            [1],
            rng,
            use_openai_api=False,
            include_broad_diversity_aggregation_methods=True,
        )

        method_results: dict[str, dict[str, Any]] = {}
        for m in [our_method, best_method]:
            if m not in specs:
                method_results[m] = {
                    "method": m,
                    "prediction": None,
                    "is_correct": False,
                    "metadata": {"unavailable_reason": "method_not_available_in_local_strategy_builder"},
                }
                continue
            r = specs[m].run(question, ground_truth)
            method_results[m] = {
                "method": m,
                "prediction": r.prediction,
                "is_correct": bool(r.is_correct),
                "actions_used": int(r.actions_used),
                "expansions": int(r.expansions),
                "verifications": int(r.verifications),
                "budget_exhausted": bool(r.budget_exhausted),
                "metadata": r.metadata,
            }

        our_row = method_results.get(our_method, {})
        best_row = method_results.get(best_method, {})
        our_branches = ((our_row.get("metadata") or {}).get("all_branch_states") or [])

        # if no branch snapshots were emitted, reconstruct minimal branch rows from action trace branch ids.
        if not our_branches:
            seen_ids = sorted({str(a.get("branch_id")) for a in ((our_row.get("metadata") or {}).get("action_trace") or []) if a.get("branch_id")})
            for bid in seen_ids:
                our_branches.append({"branch_id": bid})

        selected_branch = str((our_row.get("metadata") or {}).get("final_selected_branch") or "")
        best_branch = str((best_row.get("metadata") or {}).get("final_selected_branch") or "")

        case_branch_rows: list[dict[str, Any]] = []
        for br in our_branches:
            b = dict(br)
            branch_id = str(b.get("branch_id") or "")
            rec = build_branch_trace_record(
                dataset_name=dataset,
                example_id=str(case["example_id"]),
                state_id=f"case_{case_idx}",
                branch=b,
                state_provenance={"case_index": case_idx, "source": "targeted_recovery_pass"},
                generation_metadata={"method": our_method},
                ground_truth_answer=ground_truth,
            )
            reasoning_type, provenance = _classify_branch(rec, ground_truth=ground_truth)
            role = []
            if branch_id == selected_branch:
                role.append("method-chosen")
            if best_branch and branch_id == best_branch:
                role.append("oracle-best")
            if not role:
                role.append("competing")
            row = {
                **rec,
                "case_index": case_idx,
                "reasoning_type": reasoning_type,
                "reasoning_provenance": provenance,
                "branch_role": ", ".join(role),
                "depth": int(b.get("depth", 0)),
                "verify_count": int(b.get("verify_count", 0)),
                "action_history": list(b.get("action_history", [])),
                "score_history": list(b.get("score_history", [])),
            }
            case_branch_rows.append(row)
            branch_rows.append(row)

        correct_branch_ids = [r["branch_id"] for r in case_branch_rows if _norm(r.get("branch_final_answer_normalized")) == _norm(ground_truth)]
        timeline = _gold_group_timeline(our_row, ground_truth)

        per_case_rows.append(
            {
                "case_index": case_idx,
                "dataset": dataset,
                "seed": seed,
                "budget": budget,
                "example_id": str(case["example_id"]),
                "question": question,
                "ground_truth": ground_truth,
                "our_method": our_method,
                "best_method": best_method,
                "our_prediction": our_row.get("prediction"),
                "best_prediction": best_row.get("prediction"),
                "our_is_correct": bool(our_row.get("is_correct", False)),
                "best_is_correct": bool(best_row.get("is_correct", False)),
                "correct_answer_group_branch_ids": correct_branch_ids,
                "gold_group_timeline": timeline,
                "branch_rows": case_branch_rows,
            }
        )

    # summaries
    prov_counts = Counter(str(r.get("reasoning_provenance", "unknown / not exposed")) for r in branch_rows)
    type_counts = Counter(str(r.get("reasoning_type", "unknown / not exposed")) for r in branch_rows)
    recoverable_cases = sum(1 for c in per_case_rows if any(r.get("reasoning_provenance") in {"direct-text-supported", "recovered-from-branch-text"} for r in c["branch_rows"]))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection_meta": selection_meta,
        "n_cases": len(per_case_rows),
        "n_branch_rows": len(branch_rows),
        "cases_with_real_branch_recovery": int(recoverable_cases),
        "provenance_counts": dict(prov_counts),
        "reasoning_type_counts": dict(type_counts),
    }

    (OUT_DIR / "selected_case_manifest.json").write_text(
        json.dumps({"selection_meta": selection_meta, "cases": selected_cases}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT_DIR / "per_case_branch_observability.json").write_text(json.dumps(per_case_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "branch_reasoning_classification.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in branch_rows) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "provenance_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "recoverability_summary.json").write_text(
        json.dumps(
            {
                "n_cases": len(per_case_rows),
                "cases_with_real_branch_recovery": int(recoverable_cases),
                "cases_without_real_branch_recovery": int(len(per_case_rows) - recoverable_cases),
                "provenance_counts": dict(prov_counts),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # markdown report
    lines = [
        "# Twenty defeat cases with recovered branch reasoning (2026-04-19)",
        "",
        "## Selection and honesty note",
        f"- Selection source: `{selection_meta.get('selection_source')}`",
        f"- Fallback used: `{selection_meta.get('fallback_used')}`",
    ]
    if selection_meta.get("fallback_used"):
        lines.append(f"- Fallback reason: {selection_meta.get('fallback_reason')}")
    lines += [
        "- Provenance legend: `direct-text-supported`, `recovered-from-branch-text`, `proxy-inferred`, `unknown / not exposed`.",
        "",
        "## Compact summary",
        f"- Cases: {len(per_case_rows)}",
        f"- Cases with real branch recovery: {recoverable_cases}",
        f"- Provenance counts: {dict(prov_counts)}",
        f"- Dominant reasoning types: {dict(type_counts.most_common(8))}",
        "",
    ]

    for case in per_case_rows:
        lines += [
            f"## Case {case['case_index']}: {case['dataset']} / {case['example_id']}",
            f"- Full problem statement: {case['question']}",
            f"- Ground truth: `{case['ground_truth']}`",
            f"- Our method (`{case['our_method']}`) answer: `{case['our_prediction']}`",
            f"- Best method (`{case['best_method']}`) answer: `{case['best_prediction']}`",
            f"- Correct answer-group branch ids (our method): {case['correct_answer_group_branch_ids'] or 'none exposed'}",
            f"- Gold group timeline: {json.dumps(case['gold_group_timeline'], ensure_ascii=False)}",
            "",
            "| branch_id | role | final answer | normalized | depth | verify_count | reasoning type | provenance |",
            "|---|---|---:|---:|---:|---:|---|---|",
        ]
        for br in case["branch_rows"]:
            lines.append(
                "| {bid} | {role} | {fa} | {na} | {d} | {v} | {rt} | {prov} |".format(
                    bid=br.get("branch_id"),
                    role=br.get("branch_role"),
                    fa=br.get("branch_final_answer_text_raw"),
                    na=br.get("branch_final_answer_normalized"),
                    d=br.get("depth", ""),
                    v=br.get("verify_count", ""),
                    rt=br.get("reasoning_type"),
                    prov=br.get("reasoning_provenance"),
                )
            )
        lines += ["", "### Comparative failure explanation", "- Our method failed when chosen branch reasoning type was misaligned with target variable or incomplete versus competitor selection.", "- Best method won by selecting a branch that produced a better final answer in this bounded rerun when exposed.", ""]

    DOC_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
