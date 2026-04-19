#!/usr/bin/env python3
"""Build a 20-example defeat casebook with conservative branch-style provenance flags."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

AUDIT_DIR = REPO_ROOT / "outputs/full_comparative_mistake_audit_vs_best_method_20260418"
PROXY_DIR = REPO_ROOT / "outputs/branch_label_bruteforce_learning/current_leading_failure_case_extraction_20260418"
RECOVERABLE_DIR = REPO_ROOT / "outputs/branch_label_bruteforce_learning/natural_language_failure_casebook_dominant_group_20260418"
RICH_TRACE_DIR = REPO_ROOT / "outputs/branch_label_bruteforce_learning/rich_failure_casebook_with_reasoning_traces_20260418"

OUT_DIR = REPO_ROOT / "outputs/twenty_defeat_cases_with_branch_reasoning_20260419"
DOC_PATH = REPO_ROOT / "docs/TWENTY_DEFEAT_CASES_WITH_BRANCH_REASONING_2026_04_19.md"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _classify_branch(branch: dict[str, Any]) -> tuple[str, str, str]:
    """Return (type, provenance_flag, rationale)."""
    depth = branch.get("depth")
    verify = branch.get("verify_count")
    outside_gap = branch.get("branch_vs_outside_gap")
    delta = branch.get("multistep_delta_vs_onestep")

    metrics_known = any(v is not None for v in [depth, verify, outside_gap, delta])
    if not metrics_known:
        return ("unknown / not exposed", "unknown / not exposed", "No auditable branch metrics were exposed.")

    depth_f = float(depth or 0.0)
    verify_f = float(verify or 0.0)
    outside_f = float(outside_gap or 0.0)
    delta_f = float(delta or 0.0)

    if verify_f >= 1.0 and depth_f >= 2.0:
        return (
            "deeper verify-heavy branch",
            "proxy-inferred",
            "Depth and verify count indicate multi-step verification-heavy behavior.",
        )
    if delta_f > 0.05 and depth_f <= 1.0:
        if outside_f < 0:
            return (
                "outside-option-dominated branch",
                "proxy-inferred",
                "Positive multistep uplift exists, but branch still trails the outside option.",
            )
        return (
            "shallow multistep-uplifted branch",
            "proxy-inferred",
            "Positive multistep uplift with shallow depth.",
        )
    if outside_f < 0:
        return (
            "outside-option-dominated branch",
            "proxy-inferred",
            "Branch value trails the outside option.",
        )
    if delta_f <= 0.0 and depth_f <= 1.0:
        return (
            "answer-distinct alternative branch",
            "proxy-inferred",
            "Low uplift and shallow depth suggest a simple alternative path.",
        )
    return (
        "intermediate-total branch",
        "proxy-inferred",
        "Branch shows arithmetic/progressive structure via numeric proxies but no direct text.",
    )


def _to_branch_row(raw: dict[str, Any], role: str = "competing") -> dict[str, Any]:
    return {
        "branch_id": raw.get("branch_id"),
        "role": role,
        "depth": raw.get("depth"),
        "verify_count": raw.get("verify_count"),
        "recent_delta": raw.get("recent_delta"),
        "oracle_one_step_value": raw.get("oracle_one_step_value"),
        "multistep_target_value": raw.get("multistep_target_value"),
        "multistep_delta_vs_onestep": raw.get("multistep_delta_vs_onestep"),
        "branch_vs_outside_gap": raw.get("branch_vs_outside_gap"),
        "outside_option_value": raw.get("outside_option_value"),
        "method_score_k3": raw.get("method_score_k3"),
        "final_answer_text": raw.get("final_answer_text"),
        "raw_reasoning_text": raw.get("raw_reasoning_text"),
    }


def _ensure_b012(branches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(b.get("branch_id")): b for b in branches}
    for bid in ["b0", "b1", "b2"]:
        if bid not in by_id:
            branches.append(
                {
                    "branch_id": bid,
                    "role": "not-exposed",
                    "depth": None,
                    "verify_count": None,
                    "recent_delta": None,
                    "oracle_one_step_value": None,
                    "multistep_target_value": None,
                    "multistep_delta_vs_onestep": None,
                    "branch_vs_outside_gap": None,
                    "outside_option_value": None,
                    "method_score_k3": None,
                    "final_answer_text": None,
                    "raw_reasoning_text": None,
                }
            )
    return sorted(branches, key=lambda b: str(b.get("branch_id")))


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pair_def = _read_json(AUDIT_DIR / "comparison_pair_definition.json")
    ranked = _read_json(AUDIT_DIR / "ranked_casebook_records.json")
    mistake_rows = _read_jsonl(AUDIT_DIR / "all_mistake_records.jsonl")

    failure_rows = [
        r
        for r in mistake_rows
        if bool(r.get("best_method_correct")) and not bool(r.get("our_method_correct"))
    ]
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in failure_rows:
        by_key[(str(r.get("dataset")), str(r.get("example_id")))].append(r)

    proxy_rank_rows = _read_json(PROXY_DIR / "failure_case_ranking_table.json").get("rows", [])
    proxy_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in proxy_rank_rows:
        proxy_by_key[(str(r.get("dataset_name")), str(r.get("example_id")))].append(r)

    recoverable_rows = _read_json(RECOVERABLE_DIR / "recoverable_branch_detail_table.json").get("rows", [])
    recoverable_by_state_branch = {
        (str(r.get("state_id")), str(r.get("branch_id"))): r for r in recoverable_rows
    }

    rich_cases = _read_json(RICH_TRACE_DIR / "rich_failure_cases_structured.json").get("cases", [])
    rich_by_key = {(str(c.get("dataset_name")), str(c.get("example_id"))): c for c in rich_cases}

    selected: list[dict[str, Any]] = []
    for rr in ranked:
        key = (str(rr.get("dataset")), str(rr.get("example_id")))
        rows = by_key.get(key, [])
        if not rows:
            continue
        representative = sorted(rows, key=lambda r: (int(r.get("seed", 0)), int(r.get("budget", 0))), reverse=True)[0]

        branch_rows: list[dict[str, Any]] = []
        oracle_best_branch = None
        our_selected_branch = "unknown / not exposed"
        branch_provenance = "unknown / not exposed"

        rich = rich_by_key.get(key)
        if rich:
            branch_provenance = "proxy-inferred"
            oracle_best_branch = rich.get("oracle_best_branch_id")
            if rich.get("method_chosen_branch_id"):
                our_selected_branch = str(rich.get("method_chosen_branch_id"))
            for b in rich.get("branch_details", []):
                role = "competing"
                if b.get("branch_id") == rich.get("method_chosen_branch_id"):
                    role = "our-method-selected (proxy run)"
                elif b.get("branch_id") == rich.get("oracle_best_branch_id"):
                    role = "oracle-best (proxy run)"
                branch_rows.append(_to_branch_row(b, role=role))

        if not branch_rows and proxy_by_key.get(key):
            branch_provenance = "proxy-inferred"
            p = sorted(proxy_by_key[key], key=lambda x: float(x.get("oracle_gap_if_choose_k3", 0.0)), reverse=True)[0]
            oracle_best_branch = p.get("oracle_best_branch")
            our_selected_branch = p.get("method_choice_k3") or "unknown / not exposed"
            for b in p.get("per_branch", []):
                role = "competing"
                if b.get("branch_id") == p.get("method_choice_k3"):
                    role = "our-method-selected (proxy run)"
                elif b.get("branch_id") == p.get("oracle_best_branch"):
                    role = "oracle-best (proxy run)"
                augmented = dict(b)
                rec = recoverable_by_state_branch.get((str(p.get("state_id")), str(b.get("branch_id"))), {})
                augmented["depth"] = rec.get("features_branch_v1", {}).get("depth")
                augmented["verify_count"] = rec.get("features_branch_v1", {}).get("verify_count")
                augmented["recent_delta"] = rec.get("features_branch_v1", {}).get("recent_delta")
                branch_rows.append(_to_branch_row(augmented, role=role))

        branch_rows = _ensure_b012(branch_rows)
        branch_type_rows = []
        for b in branch_rows:
            ctype, cflag, rationale = _classify_branch(b)
            branch_type_rows.append({
                "branch_id": b.get("branch_id"),
                "role": b.get("role"),
                "classification": ctype,
                "classification_provenance": cflag,
                "classification_rationale": rationale,
                "metrics": {
                    "depth": b.get("depth"),
                    "verify_count": b.get("verify_count"),
                    "oracle_one_step_value": b.get("oracle_one_step_value"),
                    "multistep_target_value": b.get("multistep_target_value"),
                    "multistep_delta_vs_onestep": b.get("multistep_delta_vs_onestep"),
                    "branch_vs_outside_gap": b.get("branch_vs_outside_gap"),
                    "method_score_k3": b.get("method_score_k3"),
                },
                "raw_reasoning_text": b.get("raw_reasoning_text"),
                "final_answer_text": b.get("final_answer_text"),
            })

        main_issue = str(representative.get("primary_group", "other"))
        if main_issue == "insufficient_diversity_realized":
            answer_group_status = "absent from the frontier"
        elif main_issue == "bad_diversity_realized":
            answer_group_status = "present but underweighted"
        elif main_issue == "intermediate_result_or_non_terminal_answer":
            answer_group_status = "present but lost at commit/selection time"
        else:
            answer_group_status = "unknown / not exposed"

        selected.append(
            {
                "dataset": representative.get("dataset"),
                "example_id": representative.get("example_id"),
                "problem_statement": representative.get("problem_text"),
                "ground_truth_answer": representative.get("ground_truth"),
                "our_method": pair_def.get("our_method"),
                "best_method": pair_def.get("best_method"),
                "our_method_selected_branch": our_selected_branch,
                "our_method_final_answer": representative.get("our_method_final_answer"),
                "best_method_final_answer": representative.get("best_method_final_answer"),
                "oracle_best_branch": oracle_best_branch if oracle_best_branch is not None else "unknown / not exposed",
                "branch_explanations": branch_type_rows,
                "branch_detail_provenance": branch_provenance,
                "comparative_explanation": {
                    "what_our_method_effectively_did": representative.get("secondary_factor"),
                    "what_best_method_effectively_did": representative.get("best_method_advantage_type"),
                    "where_divergence_happened": representative.get("pipeline_failure_location"),
                    "main_issue": main_issue,
                    "correct_answer_group_status": answer_group_status,
                },
                "ranking_features": {
                    "n_losses": next((x.get("n_losses") for x in ranked if x.get("dataset") == representative.get("dataset") and x.get("example_id") == representative.get("example_id")), None),
                    "rank_score": next((x.get("rank_score") for x in ranked if x.get("dataset") == representative.get("dataset") and x.get("example_id") == representative.get("example_id")), None),
                },
                "provenance_flags": {
                    "direct_text_supported": False,
                    "proxy_inferred": branch_provenance == "proxy-inferred",
                    "unknown_or_not_exposed": branch_provenance == "unknown / not exposed",
                },
            }
        )
        if len(selected) >= 20:
            break

    if len(selected) < 20:
        raise RuntimeError(f"Expected at least 20 selected cases, found {len(selected)}")

    # Tables and summaries
    selected_ids = [{"dataset": r["dataset"], "example_id": r["example_id"]} for r in selected]
    branch_type_counter = Counter()
    provenance_counter = Counter()
    defeat_counter = Counter()
    failure_loc_counter = Counter()
    for c in selected:
        defeat_counter[c["comparative_explanation"]["main_issue"]] += 1
        failure_loc_counter[c["comparative_explanation"]["where_divergence_happened"]] += 1
        provenance_counter[c["branch_detail_provenance"]] += 1
        for b in c["branch_explanations"]:
            branch_type_counter[b["classification"]] += 1

    ranking_manifest = {
        "selection_policy": {
            "source": "ranked_casebook_records.json",
            "rule": "top-ranked examples by rank_score (importance-oriented) among rows where best method is correct and our method is wrong",
            "tiebreakers": ["n_losses", "rank_score", "proxy branch observability availability"],
        },
        "our_method": pair_def.get("our_method"),
        "best_method": pair_def.get("best_method"),
        "selected_count": len(selected),
        "selected_cases": [
            {
                "dataset": c["dataset"],
                "example_id": c["example_id"],
                "rank_score": c["ranking_features"].get("rank_score"),
                "n_losses": c["ranking_features"].get("n_losses"),
                "branch_detail_provenance": c["branch_detail_provenance"],
            }
            for c in selected
        ],
    }

    commands = {
        "script": "python scripts/build_twenty_defeat_casebook_20260419.py",
        "inputs": [
            str(AUDIT_DIR / "comparison_pair_definition.json"),
            str(AUDIT_DIR / "ranked_casebook_records.json"),
            str(AUDIT_DIR / "all_mistake_records.jsonl"),
            str(PROXY_DIR / "failure_case_ranking_table.json"),
            str(RECOVERABLE_DIR / "recoverable_branch_detail_table.json"),
            str(RICH_TRACE_DIR / "rich_failure_cases_structured.json"),
        ],
        "assumptions": [
            "Best and our methods are taken from comparison_pair_definition.json.",
            "No direct branch free-text traces are available in the loaded branch-trace artifacts; branch types are proxy-inferred when metrics exist.",
            "When comparative rows do not expose branch ids, branch selection is marked unknown/not exposed unless proxy match exists.",
        ],
        "caveats": [
            "Proxy branch artifacts come from branch-allocator diagnostics and are not guaranteed to be the exact execution trace of the broad comparative run.",
            "Therefore branch-level style labels are conservative and provenance-tagged.",
        ],
    }

    # Write machine-readable outputs
    (OUT_DIR / "selected_case_ids.json").write_text(json.dumps(selected_ids, indent=2), encoding="utf-8")
    (OUT_DIR / "per_case_structured_summary.json").write_text(json.dumps({"cases": selected}, indent=2), encoding="utf-8")
    (OUT_DIR / "branch_reasoning_type_table.json").write_text(
        json.dumps(
            {
                "branch_type_counts": dict(branch_type_counter),
                "rows": [
                    {
                        "dataset": c["dataset"],
                        "example_id": c["example_id"],
                        "branch_rows": c["branch_explanations"],
                    }
                    for c in selected
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT_DIR / "provenance_flags.json").write_text(
        json.dumps(
            {
                "counts": dict(provenance_counter),
                "direct_text_supported_cases": sum(1 for c in selected if c["provenance_flags"]["direct_text_supported"]),
                "proxy_inferred_cases": sum(1 for c in selected if c["provenance_flags"]["proxy_inferred"]),
                "unknown_cases": sum(1 for c in selected if c["provenance_flags"]["unknown_or_not_exposed"]),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT_DIR / "case_ranking_manifest.json").write_text(json.dumps(ranking_manifest, indent=2), encoding="utf-8")
    (OUT_DIR / "commands_assumptions_caveats.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")

    # Markdown report
    today = str(date(2026, 4, 19))
    lines: list[str] = []
    lines.append(f"# Twenty defeat cases with branch reasoning ({today})")
    lines.append("")
    lines.append("## Method definitions from repository artifacts")
    lines.append(f"- **Our method**: `{pair_def.get('our_method')}`.")
    lines.append(f"- **Best method**: `{pair_def.get('best_method')}`.")
    lines.append("- Selection source: `outputs/full_comparative_mistake_audit_vs_best_method_20260418/comparison_pair_definition.json`.")
    lines.append("")
    lines.append("## Selection policy")
    lines.append("- Importance-oriented selection using ranked comparative losses (`rank_score`, `n_losses`).")
    lines.append("- Priority to repeated losses, then branch observability availability from proxy bundles.")
    lines.append("- Direct branch text was unavailable in loaded artifacts; proxy metrics were used when available and flagged explicitly.")
    lines.append("")

    for idx, c in enumerate(selected, start=1):
        lines.append(f"## Case {idx}: `{c['dataset']} / {c['example_id']}`")
        lines.append(f"1. Dataset and example id: `{c['dataset']}`, `{c['example_id']}`")
        lines.append(f"2. Full problem statement: {c['problem_statement']}")
        lines.append(f"3. Ground-truth answer: `{c['ground_truth_answer']}`")
        lines.append(
            f"4. Our method selected branch and final answer: branch=`{c['our_method_selected_branch']}`, answer=`{c['our_method_final_answer']}`"
        )
        lines.append(f"5. Best method final answer: `{c['best_method_final_answer']}`")
        lines.append(f"6. Oracle-best branch (if available): `{c['oracle_best_branch']}`")
        lines.append("7-9. Branch-by-branch explanation + type + provenance:")
        for b in c["branch_explanations"]:
            lines.append(
                "   - "
                f"`{b['branch_id']}` ({b['role']}): type=`{b['classification']}`; "
                f"support=`{b['classification_provenance']}`; rationale={b['classification_rationale']} "
                f"(depth={b['metrics']['depth']}, verify_count={b['metrics']['verify_count']}, "
                f"oracle_one_step={b['metrics']['oracle_one_step_value']}, multistep_target={b['metrics']['multistep_target_value']}, "
                f"outside_gap={b['metrics']['branch_vs_outside_gap']})."
            )
        lines.append("- Comparative explanation:")
        ce = c["comparative_explanation"]
        lines.append(f"  - What our method effectively did: `{ce['what_our_method_effectively_did']}`")
        lines.append(f"  - What the best method effectively did: `{ce['what_best_method_effectively_did']}`")
        lines.append(f"  - Divergence location: `{ce['where_divergence_happened']}`")
        lines.append(f"  - Main issue: `{ce['main_issue']}`")
        lines.append(f"  - Correct answer-group status: `{ce['correct_answer_group_status']}`")
        lines.append(f"- Branch detail provenance for this case: `{c['branch_detail_provenance']}`")
        lines.append("")

    lines.append("## Compact taxonomy summaries across 20 cases")
    lines.append("### Branch-type taxonomy counts")
    for k, v in branch_type_counter.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("### Defeat-cause taxonomy counts")
    for k, v in defeat_counter.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("### Failure-stage location counts")
    for k, v in failure_loc_counter.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    dominant_branch = branch_type_counter.most_common(1)[0][0] if branch_type_counter else "unknown"
    dominant_defeat = defeat_counter.most_common(1)[0][0] if defeat_counter else "unknown"
    dominant_stage = failure_loc_counter.most_common(1)[0][0] if failure_loc_counter else "unknown"
    lines.append(f"- Most common branch-type pattern: `{dominant_branch}`.")
    lines.append(f"- Most common defeat-type pattern: `{dominant_defeat}`.")
    lines.append(f"- Losses mostly arise at: `{dominant_stage}`.")
    lines.append("")
    lines.append("## Provenance split")
    lines.append(f"- Direct-text-supported cases: {sum(1 for c in selected if c['provenance_flags']['direct_text_supported'])}")
    lines.append(f"- Proxy-inferred branch cases: {sum(1 for c in selected if c['provenance_flags']['proxy_inferred'])}")
    lines.append(f"- Unknown/not-exposed branch cases: {sum(1 for c in selected if c['provenance_flags']['unknown_or_not_exposed'])}")
    lines.append("")
    lines.append("## Honesty note")
    lines.append("- No branch free-text reasoning was fabricated.")
    lines.append("- Where branch-level text is unavailable, cases are marked `proxy-inferred` or `unknown / not exposed`.")

    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
