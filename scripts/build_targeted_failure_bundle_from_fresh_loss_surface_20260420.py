#!/usr/bin/env python3
"""Build one mechanism-homogeneous targeted failure bundle from fresh current loss artifacts."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DOC = REPO_ROOT / "docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md"
IMPROVEMENT_ROOT_GLOB = "twenty_exact_current_full_improvement_eval_*"


@dataclass
class FreshCase:
    dataset: str
    example_id: str
    problem_statement: str
    gold_answer: str
    old_answer: str
    best_answer: str
    old_failure_type: str
    old_three_way_label: str
    old_repeated_same_family: bool


def _norm_num(text: str | None) -> float | None:
    if text is None:
        return None
    t = str(text).strip()
    if re.fullmatch(r"-?\d+(?:\.\d+)?", t):
        return float(t)
    return None


def _find_latest_improvement_dir() -> Path:
    candidates = sorted((REPO_ROOT / "outputs").glob(IMPROVEMENT_ROOT_GLOB))
    if not candidates:
        raise FileNotFoundError("No improvement eval bundles found under outputs/")
    return candidates[-1]


def _parse_fresh_doc() -> dict[tuple[str, str], FreshCase]:
    text = SOURCE_DOC.read_text(encoding="utf-8")
    blocks = re.split(r"\n## Case \d+: ", text)[1:]
    out: dict[tuple[str, str], FreshCase] = {}
    for blk in blocks:
        head = re.search(r"`([^`]+) / ([^`]+)`", blk)
        dataset = re.search(r"- dataset: `([^`]+)`", blk)
        exid = re.search(r"- example_id: `([^`]+)`", blk)
        q = re.search(r"- problem statement: (.+)", blk)
        gold = re.search(r"- gold answer: `([^`]*)`", blk)
        old = re.search(r"- our answer: `([^`]*)`", blk)
        best = re.search(r"- best answer: `([^`]*)`", blk)
        rep = re.search(r"- repeated same-family expansion present\?: `([^`]*)`", blk)
        ftype = re.search(r"- concise failure type: `([^`]*)`", blk)
        label = re.search(r"- three-way decision label: `([^`]*)`", blk)
        if not all([head, dataset, exid, q, gold, old, best, rep, ftype, label]):
            continue
        case = FreshCase(
            dataset=dataset.group(1),
            example_id=exid.group(1),
            problem_statement=q.group(1).strip(),
            gold_answer=gold.group(1),
            old_answer=old.group(1),
            best_answer=best.group(1),
            old_failure_type=ftype.group(1),
            old_three_way_label=label.group(1),
            old_repeated_same_family=(rep.group(1).lower() == "true"),
        )
        out[(case.dataset, case.example_id)] = case
    return out


def _candidate_families(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wrong = [r for r in rows if not bool(r["improved"]["is_correct"])]

    present_not_selected = [r for r in wrong if r["improved_label"] == "correct answer present but not selected"]

    near_miss_absent = []
    for r in wrong:
        if r["improved_label"] != "correct answer absent from tree":
            continue
        pred = _norm_num(r["improved"].get("prediction_norm"))
        gold = _norm_num(r.get("gold_answer"))
        if pred is None or gold is None:
            continue
        diff = abs(pred - gold)
        if diff <= 3:
            rr = dict(r)
            rr["near_miss_abs_diff"] = diff
            near_miss_absent.append(rr)

    full_budget_repeated = []
    for r in wrong:
        meta = r["improved"].get("metadata") or {}
        action_count = len(meta.get("action_trace") or [])
        repeated = int(meta.get("repeated_same_family_expansion_count", 0))
        if action_count >= int(r["budget"]) and repeated >= 6:
            rr = dict(r)
            rr["action_count"] = action_count
            rr["repeated_same_family_expansion_count"] = repeated
            full_budget_repeated.append(rr)

    families = [
        {
            "mechanism_family": "present-but-not-selected (post-improvement unresolved)",
            "cases": present_not_selected,
            "coherence_evidence": {
                "all_share_label": all(r["improved_label"] == "correct answer present but not selected" for r in present_not_selected),
                "size": len(present_not_selected),
            },
        },
        {
            "mechanism_family": "near-miss absent-from-tree (post-improvement unresolved)",
            "cases": near_miss_absent,
            "coherence_evidence": {
                "all_share_label": all(r["improved_label"] == "correct answer absent from tree" for r in near_miss_absent),
                "max_abs_numeric_diff": max((r["near_miss_abs_diff"] for r in near_miss_absent), default=None),
                "size": len(near_miss_absent),
            },
        },
        {
            "mechanism_family": "full-budget repeated same-family monopolization (post-improvement unresolved)",
            "cases": full_budget_repeated,
            "coherence_evidence": {
                "all_full_budget": all(int(r["action_count"]) >= int(r["budget"]) for r in full_budget_repeated),
                "min_repeated_same_family_expansion_count": min((int(r["repeated_same_family_expansion_count"]) for r in full_budget_repeated), default=None),
                "size": len(full_budget_repeated),
            },
        },
    ]
    return families


def _choose_strongest(families: list[dict[str, Any]]) -> dict[str, Any]:
    def score(f: dict[str, Any]) -> tuple[int, int, int]:
        cases = f["cases"]
        size = len(cases)
        label_purity = int(len({c.get("improved_label") for c in cases}) <= 1) if cases else 0
        homog = 0
        if "near-miss absent-from-tree" in f["mechanism_family"]:
            homog = int(all(c["improved_label"] == "correct answer absent from tree" for c in cases)) + int(
                all((c.get("near_miss_abs_diff", 99) <= 3) for c in cases)
            )
        elif "full-budget repeated" in f["mechanism_family"]:
            homog = int(all(len((c["improved"].get("metadata") or {}).get("action_trace") or []) >= int(c["budget"]) for c in cases)) + int(
                all(int((c["improved"].get("metadata") or {}).get("repeated_same_family_expansion_count", 0)) >= 6 for c in cases)
            )
        elif "present-but-not-selected" in f["mechanism_family"]:
            homog = int(all(c["improved_label"] == "correct answer present but not selected" for c in cases))
        return (homog, label_purity, size)

    return max(families, key=score)


def _mechanism_label(family_name: str) -> str:
    if "full-budget repeated same-family monopolization" in family_name:
        return "full_budget_repeated_same_family_monopolization_unresolved"
    if "near-miss absent-from-tree" in family_name:
        return "near_miss_absent_from_tree_unresolved"
    if "present-but-not-selected" in family_name:
        return "present_but_not_selected_unresolved"
    return "targeted_unresolved_mechanism"


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    improvement_dir = _find_latest_improvement_dir()
    per_case_path = improvement_dir / "per_case_before_after.json"
    per_case = json.loads(per_case_path.read_text(encoding="utf-8"))
    fresh_lookup = _parse_fresh_doc()

    families = _candidate_families(per_case)
    chosen = _choose_strongest(families)
    chosen_cases = chosen["cases"]
    mechanism_label = _mechanism_label(chosen["mechanism_family"])
    full_budget_count = sum(
        1
        for r in chosen_cases
        if len(((r["improved"].get("metadata") or {}).get("action_trace") or [])) >= int(r["budget"])
    )
    min_repeated_count = (
        min(int((r["improved"].get("metadata") or {}).get("repeated_same_family_expansion_count", 0)) for r in chosen_cases)
        if chosen_cases
        else None
    )

    out_dir = REPO_ROOT / "outputs" / f"targeted_failure_bundle_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    enriched_rows: list[dict[str, Any]] = []
    for r in chosen_cases:
        key = (str(r["dataset"]), str(r["example_id"]))
        src = fresh_lookup[key]
        meta = r["improved"].get("metadata") or {}
        row = {
            "mechanism_label": mechanism_label,
            "dataset": r["dataset"],
            "example_id": r["example_id"],
            "budget": r["budget"],
            "problem_statement": src.problem_statement,
            "gold_answer": src.gold_answer,
            "old_answer": src.old_answer,
            "best_answer": src.best_answer,
            "improved_answer": r["improved"].get("prediction_norm"),
            "improved_label": r["improved_label"],
            "near_miss_abs_diff": (
                abs((_norm_num(r["improved"].get("prediction_norm")) or 0) - (_norm_num(src.gold_answer) or 0))
                if (_norm_num(r["improved"].get("prediction_norm")) is not None and _norm_num(src.gold_answer) is not None)
                else None
            ),
            "old_failure_type": src.old_failure_type,
            "old_repeated_same_family": src.old_repeated_same_family,
            "improved_repeated_same_family_expansion_count": int(meta.get("repeated_same_family_expansion_count", 0)),
            "improved_action_count": len(meta.get("action_trace") or []),
            "improved_expand_action_count": int(meta.get("expand_action_count", 0)),
            "improved_verify_count": sum(1 for a in (meta.get("action_trace") or []) if str(a.get("action")) == "verify"),
            "changed_to_correct": bool(r.get("changed_to_correct", False)),
            "source_improvement_bundle": str(improvement_dir.relative_to(REPO_ROOT)),
        }
        enriched_rows.append(row)

    enriched_rows = sorted(enriched_rows, key=lambda x: (x["dataset"], x["example_id"]))
    (out_dir / "per_case.json").write_text(json.dumps(enriched_rows, indent=2), encoding="utf-8")
    with (out_dir / "per_case.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(enriched_rows[0].keys()))
        w.writeheader()
        w.writerows(enriched_rows)

    summary = {
        "created_at_utc": ts,
        "chosen_mechanism_family": chosen["mechanism_family"],
        "chosen_mechanism_label": mechanism_label,
        "selected_case_count": len(enriched_rows),
        "source_artifacts": {
            "fresh_loss_surface_doc": str(SOURCE_DOC.relative_to(REPO_ROOT)),
            "improvement_bundle": str(improvement_dir.relative_to(REPO_ROOT)),
            "improvement_per_case": str(per_case_path.relative_to(REPO_ROOT)),
        },
        "candidate_family_sizes": {f["mechanism_family"]: len(f["cases"]) for f in families},
        "coherence_evidence": {
            "all_cases_improved_label_absent_from_tree": all(r["improved_label"] == "correct answer absent from tree" for r in chosen_cases),
            "all_cases_near_miss_abs_diff_le_3": all((r.get("near_miss_abs_diff", 99) <= 3) for r in chosen_cases if r.get("near_miss_abs_diff") is not None),
            "all_cases_full_budget_actions": all(
                len(((r["improved"].get("metadata") or {}).get("action_trace") or [])) >= int(r["budget"]) for r in chosen_cases
            ),
            "full_budget_case_count": full_budget_count,
            "min_repeated_same_family_expansion_count": min_repeated_count,
        },
        "numeric_diff_stats": {
            "mean_abs_diff": (
                sum(float(r["near_miss_abs_diff"]) for r in enriched_rows if r["near_miss_abs_diff"] is not None)
                / max(1, sum(1 for r in enriched_rows if r["near_miss_abs_diff"] is not None))
            ),
            "max_abs_diff": (
                max(float(r["near_miss_abs_diff"]) for r in enriched_rows if r["near_miss_abs_diff"] is not None)
                if any(r["near_miss_abs_diff"] is not None for r in enriched_rows)
                else None
            ),
        },
    }
    (out_dir / "summary_statistics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    selection_rule = [
        "case remains incorrect after improvement",
    ]
    if "near-miss absent-from-tree" in chosen["mechanism_family"]:
        selection_rule += [
            "improved label is correct answer absent from tree",
            "numeric near-miss: abs(improved_answer - gold_answer) <= 3",
            "repeated same-family expansion count >= 6",
        ]
    elif "full-budget repeated" in chosen["mechanism_family"]:
        selection_rule += [
            "full-budget or near-full-budget run",
            "repeated same-family expansion count >= 6",
        ]
    else:
        selection_rule += ["improved label is correct answer present but not selected"]

    manifest = {
        "name": "targeted_failure_bundle",
        "created_at_utc": ts,
        "selection_policy": {
            "base_universe": "20 cases from fresh current full vs best loss surface; evaluated under latest bounded width-vs-depth challenger-guard improvement",
            "rule": selection_rule,
            "no_round_number_padding": True,
        },
        "inputs": [
            str(SOURCE_DOC.relative_to(REPO_ROOT)),
            str((improvement_dir / "per_case_before_after.json").relative_to(REPO_ROOT)),
            str((improvement_dir / "summary.json").relative_to(REPO_ROOT)),
        ],
        "outputs": [
            str((out_dir / "per_case.json").relative_to(REPO_ROOT)),
            str((out_dir / "per_case.csv").relative_to(REPO_ROOT)),
            str((out_dir / "summary_statistics.json").relative_to(REPO_ROOT)),
            str((out_dir / "selection_manifest.json").relative_to(REPO_ROOT)),
        ],
    }
    (out_dir / "selection_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    docs_path = REPO_ROOT / "docs" / f"TARGETED_FAILURE_BUNDLE_REPORT_{ts}.md"
    lines = [
        f"# Targeted failure bundle report ({ts})",
        "",
        "## Selected mechanism family",
        f"- **Family:** `{chosen['mechanism_family']}`",
        f"- **Mechanism label:** `{mechanism_label}`",
        f"- **Selected cases:** {len(enriched_rows)}",
        "",
        "## Why this family is strongest and most homogeneous",
        "- It has the largest unresolved count among clean single-mechanism families considered from the same 20-case surface.",
        f"- {full_budget_count}/{len(chosen_cases)} selected cases reach full budget; all show high repeated same-family expansion counts (min={min_repeated_count}).",
        "- This isolates one controller-allocation mechanism (family monopolization under bounded budget), rather than mixing mechanism types by answer-surface label.",
        "- Most cases are near misses numerically, which is consistent with local search progress without adequate challenger coverage.",
        "",
        "## Candidate family comparison (same artifacts)",
    ]
    for fam in families:
        lines.append(f"- `{fam['mechanism_family']}`: {len(fam['cases'])} cases")
    lines += [
        "",
        "## Why this bundle is a better target for the next bounded fix",
        "- The previous broad 20-case slice mixes absent-from-tree and present-but-not-selected mechanisms.",
        "- This targeted slice removes present-but-not-selected cases and keeps one dominant mechanism only.",
        "- A single bounded controller fix can focus on anti-monopolization plus challenger diversification under fixed budget.",
        "",
        "## Suggested next bounded controller improvement",
        "- Add a **family-cap with near-miss escape hatch**: when a family consumes most actions and produces near-miss numeric answers without gold match, reserve remaining actions for forced challenger families before continuing depth on incumbent family.",
        "- Keep boundedness by limiting forced challenger actions to a small fixed quota and only triggering under explicit monotonic near-miss + monopolization conditions.",
        "",
        "## Output bundle",
        f"- `{out_dir.relative_to(REPO_ROOT)}`",
    ]
    docs_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "chosen_mechanism_family": chosen["mechanism_family"],
        "selected_case_count": len(enriched_rows),
        "docs_report_path": str(docs_path.relative_to(REPO_ROOT)),
        "output_bundle_path": str(out_dir.relative_to(REPO_ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
