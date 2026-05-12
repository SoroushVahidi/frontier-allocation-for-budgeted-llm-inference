#!/usr/bin/env python3
"""
replay_colored_reasoning_path_policy_v1.py

No-API replay: applies mined transition-rule lift scores to existing candidate
rows, selects the policy-preferred answer, and compares with baseline and
structural-verifier selections.

Policy scoring (gold-free):
  - For each candidate, build the ordered color prefix path (all candidates at
    <= its branch_slot, using the same sort/dedup logic as the mining script).
  - path_policy_score = sum of lift values for each adjacent (A → B) pair,
    looked up from transition_rules (prefix_len=1 rules only).
  - Tie-breakers: higher score → higher target_alignment_score → non-repair →
    stable original order.

Gold (if present in casebook) is used ONLY for final reporting (exact-match
metrics). It is never used in candidate scoring or sequence construction.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the project root is on sys.path when the script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.mine_reasoning_edge_sequences import (
    EDGE_COLORS,
    map_edge_color,
    load_trace_packets,
)

_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_csv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_transition_rules(path: Path) -> list[dict[str, str]]:
    return _load_csv(path)


def load_motif_summary(path: Path) -> list[dict[str, str]]:
    return _load_csv(path)


def load_casebook(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                result[cid] = row
    return result


# ---------------------------------------------------------------------------
# Lift index (gold-free)
# ---------------------------------------------------------------------------

def build_transition_lift_index(
    rules: list[dict[str, str]],
    min_lift: float = 0.0,
) -> dict[tuple[str, str], float]:
    """
    (from_color, to_color) → lift for prefix_len=1 rules with lift >= min_lift.
    When multiple rows match the same pair, take the maximum lift.
    """
    index: dict[tuple[str, str], float] = {}
    for row in rules:
        try:
            if int(row.get("prefix_len", 0) or 0) != 1:
                continue
            lift = float(row.get("lift", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if lift < min_lift:
            continue
        try:
            prefix = json.loads(row["prefix_sequence"])
        except (KeyError, json.JSONDecodeError):
            continue
        nxt = row.get("next_color", "")
        if not prefix or not nxt:
            continue
        key = (prefix[0], nxt)
        if key not in index or lift > index[key]:
            index[key] = lift
    return index


def _pal_vc_lift(rules: list[dict[str, str]]) -> float:
    """Return the lift for the PAL_code → verifier_check transition, or 0."""
    best = 0.0
    for row in rules:
        try:
            if int(row.get("prefix_len", 0) or 0) != 1:
                continue
            prefix = json.loads(row["prefix_sequence"])
        except Exception:
            continue
        if prefix == ["PAL_code"] and row.get("next_color") == "verifier_check":
            try:
                best = max(best, float(row.get("lift", 0.0) or 0.0))
            except (TypeError, ValueError):
                pass
    return best


# ---------------------------------------------------------------------------
# Per-candidate path and scoring (gold-free)
# ---------------------------------------------------------------------------

def _slot(row: dict) -> int:
    try:
        return int(row.get("branch_slot") or 99)
    except (TypeError, ValueError):
        return 99


def build_candidate_prefix_path(
    candidate_rows: list[dict[str, Any]],
    target_slot: int,
) -> list[str]:
    """
    Ordered color sequence for all candidates with branch_slot <= target_slot.
    Uses the same sort/dedup (by bf|color key) as the mining script.
    """
    path: list[str] = []
    seen: set[str] = set()
    for row in sorted(candidate_rows, key=_slot):
        if _slot(row) > target_slot:
            break
        bf = row.get("branch_family") or row.get("prompt_template_id") or ""
        lop = row.get("last_operation_family", "")
        color = map_edge_color(branch_family=bf, last_op=lop)
        key = f"{bf}|{color}"
        if key not in seen:
            path.append(color)
            seen.add(key)
    return path


def score_path(path: list[str], lift_index: dict[tuple[str, str], float]) -> float:
    """Sum lift values for each adjacent (A, B) pair in the path."""
    total = 0.0
    for i in range(len(path) - 1):
        total += lift_index.get((path[i], path[i + 1]), 0.0)
    return total


# ---------------------------------------------------------------------------
# Per-case processing
# ---------------------------------------------------------------------------

def process_case(
    case: dict[str, Any],
    casebook_row: dict[str, str],
    lift_index: dict[tuple[str, str], float],
    pal_vc_lift_value: float,
) -> dict[str, Any]:
    """Score candidates, select best, compute outcome labels."""
    case_id = case.get("case_id", "")
    candidate_rows: list[dict[str, Any]] = (
        case.get("structural_fields", {}).get("candidate_rows", [])
    )

    baseline_answer = casebook_row.get("baseline_answer", "")
    structural_best = casebook_row.get("structural_best_answer", "")
    verifier_answer = casebook_row.get("verifier_answer", "")

    pal_ok = str(case.get("pal_exec_summary", {}).get("pal_exec_ok", "0")) == "1"
    sel_src = case.get("selector_metadata", {}).get("selected_source", "")

    # Deduplicate candidates using the same bf|color key logic
    seen_keys: set[str] = set()
    unique_cands: list[dict[str, Any]] = []
    for row in sorted(candidate_rows, key=_slot):
        bf = row.get("branch_family") or row.get("prompt_template_id") or ""
        lop = row.get("last_operation_family", "")
        color = map_edge_color(branch_family=bf, last_op=lop)
        key = f"{bf}|{color}"
        if key not in seen_keys:
            unique_cands.append(row)
            seen_keys.add(key)

    def _color(row: dict) -> str:
        bf = row.get("branch_family") or row.get("prompt_template_id") or ""
        return map_edge_color(branch_family=bf, last_op=row.get("last_operation_family", ""))

    has_pal = pal_ok or any(_color(r) == "PAL_code" for r in unique_cands)
    has_verifier = any(_color(r) == "verifier_check" for r in unique_cands)
    req_live_vc = has_pal and not has_verifier and pal_vc_lift_value > 1.0

    _base = {
        "case_id": case_id,
        "baseline_answer": baseline_answer,
        "structural_best_answer": structural_best,
        "verifier_answer": verifier_answer,
        "requires_live_verifier_branch_allocation": req_live_vc,
    }

    if not unique_cands:
        return {**_base,
                "policy_selected_answer": "",
                "policy_selected_branch_family": "",
                "policy_selected_color_sequence": "[]",
                "policy_score": 0.0,
                "target_alignment_score": "",
                "policy_agrees_with_structural": False,
                "policy_improves_proxy": False,
                "policy_regresses_proxy": False,
                "no_change": False,
                "metadata_insufficient": True}

    # Score each unique candidate
    scored: list[dict[str, Any]] = []
    for i, row in enumerate(unique_cands):
        bf = row.get("branch_family") or row.get("prompt_template_id") or ""
        lop = row.get("last_operation_family", "")
        color = map_edge_color(branch_family=bf, last_op=lop)
        seq = build_candidate_prefix_path(candidate_rows, _slot(row))
        pscore = score_path(seq, lift_index)
        try:
            tas = float(row.get("target_alignment_score") or 0.0)
        except (TypeError, ValueError):
            tas = 0.0
        is_repair = "repair" in bf.lower()
        answer = str(row.get("candidate_answer", "") or "").strip()
        scored.append({
            "bf": bf, "color": color, "seq": seq,
            "pscore": pscore, "tas": tas,
            "is_repair": is_repair, "answer": answer,
            "orig_index": i,
        })

    scored.sort(key=lambda x: (
        -x["pscore"],
        -x["tas"],
        int(x["is_repair"]),
        x["orig_index"],
    ))

    best = scored[0]
    pol_answer = best["answer"]
    pol_bf = best["bf"]
    pol_seq = best["seq"]
    pol_score = best["pscore"]
    pol_tas = best["tas"]

    if not pol_answer:
        return {**_base,
                "policy_selected_answer": "",
                "policy_selected_branch_family": pol_bf,
                "policy_selected_color_sequence": json.dumps(pol_seq),
                "policy_score": round(pol_score, 4),
                "target_alignment_score": pol_tas,
                "policy_agrees_with_structural": False,
                "policy_improves_proxy": False,
                "policy_regresses_proxy": False,
                "no_change": False,
                "metadata_insufficient": True}

    agrees = bool(structural_best and pol_answer == structural_best)
    no_change = pol_answer == baseline_answer
    improves = (pol_answer != baseline_answer and bool(structural_best)
                and pol_answer == structural_best)
    regresses = (pol_answer != baseline_answer and bool(structural_best)
                 and pol_answer != structural_best)

    return {**_base,
            "policy_selected_answer": pol_answer,
            "policy_selected_branch_family": pol_bf,
            "policy_selected_color_sequence": json.dumps(pol_seq),
            "policy_score": round(pol_score, 4),
            "target_alignment_score": pol_tas,
            "policy_agrees_with_structural": agrees,
            "policy_improves_proxy": improves,
            "policy_regresses_proxy": regresses,
            "no_change": no_change,
            "metadata_insufficient": False}


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("(empty)\n", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _generate_report(
    args: argparse.Namespace,
    cases_loaded: int,
    cases_with_candidates: int,
    meta_insuff: int,
    results: list[dict[str, Any]],
    proxy_fixes: int,
    proxy_regressions: int,
    no_change_count: int,
    agrees_count: int,
    n_with_structural: int,
    requires_live_vc: int,
    gold_summary: dict[str, int] | None,
) -> str:
    agree_rate = (agrees_count / n_with_structural) if n_with_structural > 0 else 0.0
    net_proxy = proxy_fixes - proxy_regressions

    lines = [
        "# Colored Reasoning Path Policy Replay v1",
        "",
        f"- experiment: colored_reasoning_path_policy_v1",
        f"- trace_packets: {args.trace_packets}",
        f"- transition_rules: {args.transition_rules}",
        f"- motif_summary: {getattr(args, 'motif_summary', None)}",
        f"- replay_casebook: {args.replay_casebook}",
        f"- out_dir: {args.out_dir}",
        f"- min_lift: {args.min_lift}",
        f"- timestamp: {_TS}",
        "",
        "## Case coverage",
        "",
        f"- Cases loaded: {cases_loaded}",
        f"- Cases with candidate rows: {cases_with_candidates}",
        f"- Metadata-insufficient (no answer): {meta_insuff}",
        "",
        "## Policy vs baseline (proxy)",
        "",
        f"- Policy improves proxy (policy≠baseline, policy=structural_best): {proxy_fixes}",
        f"- Policy regresses proxy (policy≠baseline, policy≠structural_best): {proxy_regressions}",
        f"- No change (policy=baseline): {no_change_count}",
        f"- Net proxy: {net_proxy:+d}",
        "",
        "## Policy vs structural agreement",
        "",
        f"- Cases with structural_best_answer available: {n_with_structural}",
        f"- Policy agrees with structural best: {agrees_count} / {n_with_structural}"
        f" ({agree_rate:.1%})",
        "",
    ]

    if gold_summary:
        lines += [
            "## Exact accuracy (gold from casebook)",
            "",
            f"- Baseline exact: {gold_summary.get('baseline_exact', 'N/A')}",
            f"- Policy exact: {gold_summary.get('policy_exact', 'N/A')}",
            f"- Structural exact: {gold_summary.get('structural_exact', 'N/A')}",
            f"- Policy fixes (baseline wrong → policy right): {gold_summary.get('fixes_exact', 'N/A')}",
            f"- Policy regressions (baseline right → policy wrong): {gold_summary.get('regressions_exact', 'N/A')}",
            f"- Net exact: {gold_summary.get('net_exact', 'N/A')}",
            "",
        ]

    lines += [
        "## Missing verifier branch",
        "",
        f"- Cases requiring live verifier branch allocation: {requires_live_vc}",
        "",
        "These cases have PAL_code-type candidates but no backward_from_target_check",
        "candidate. The PAL_code → verifier_check transition has lift > 1.0, suggesting",
        "that adding a verifier branch to these cases would likely improve quality.",
        "Offline replay CANNOT create missing verifier candidates — it can only rerank",
        "existing ones. A future live experiment must allocate backward_from_target_check",
        "to these cases.",
        "",
        "## Interpretation",
        "",
        "The policy scores candidates by summing transition-rule lifts along the prefix",
        "path. Candidates at the end of high-lift transitions (e.g., PAL_code → verifier_check,",
        "lift=1.60) score higher than those at the end of low-lift transitions",
        "(e.g., PAL_code → selector, lift=0.94).",
        "",
        "Because this is a no-API replay over existing candidates, the policy can only",
        "rerank what the controller already generated. Cases where the verifier branch was",
        "never run cannot benefit from the verifier's high lift — they require a live",
        "branch-budget experiment.",
        "",
    ]

    if proxy_fixes > proxy_regressions and proxy_fixes >= 5:
        lines += [
            "## Recommendation",
            "",
            f"Proxy signal is positive (net {net_proxy:+d}). Recommend running a live",
            "branch-budget experiment that allocates backward_from_target_check to the",
            f"{requires_live_vc} cases flagged above, to validate whether the verifier",
            "branch improves exact accuracy at inference time.",
        ]
    else:
        lines += [
            "## Recommendation",
            "",
            "Proxy signal is inconclusive or negative. The policy does not show sufficient",
            "improvement over baseline to justify a live branch-budget experiment at this time.",
            "Consider re-examining the transition-rule scoring or expanding the case set.",
        ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="No-API colored reasoning path policy replay."
    )
    p.add_argument("--trace-packets", required=True, type=Path)
    p.add_argument("--transition-rules", required=True, type=Path)
    p.add_argument("--motif-summary", type=Path, default=None)
    p.add_argument("--replay-casebook", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--min-lift", type=float, default=0.0)
    p.add_argument("--no-gold-features", type=str, default="true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading trace packets from {args.trace_packets}", flush=True)
    cases = load_trace_packets(args.trace_packets)
    if args.limit:
        cases = cases[: args.limit]
    print(f"  Loaded {len(cases)} cases", flush=True)

    print(f"Loading transition rules from {args.transition_rules}", flush=True)
    rules = load_transition_rules(args.transition_rules)
    print(f"  Loaded {len(rules)} transition rules", flush=True)

    motifs: list[dict[str, str]] = []
    if args.motif_summary and args.motif_summary.exists():
        print(f"Loading motif summary from {args.motif_summary}", flush=True)
        motifs = load_motif_summary(args.motif_summary)
        print(f"  Loaded {len(motifs)} motifs", flush=True)

    print(f"Loading replay casebook from {args.replay_casebook}", flush=True)
    casebook = load_casebook(args.replay_casebook)
    print(f"  Loaded {len(casebook)} casebook rows", flush=True)

    lift_index = build_transition_lift_index(rules, min_lift=args.min_lift)
    print(f"  Lift index: {len(lift_index)} (from, to) pairs", flush=True)

    pal_vc = _pal_vc_lift(rules)
    print(f"  PAL_code → verifier_check lift: {pal_vc:.4f}", flush=True)

    # Process cases
    results: list[dict[str, Any]] = []
    for case in cases:
        cid = case.get("case_id", "")
        cb_row = casebook.get(cid, {})
        result = process_case(case, cb_row, lift_index, pal_vc)
        results.append(result)

    cases_loaded = len(cases)
    cases_with_cands = sum(
        1 for r in results if not r.get("metadata_insufficient")
        or r.get("policy_selected_answer")
    )
    # More accurate: check if candidate rows exist
    cases_with_cands = sum(
        1 for c in cases
        if c.get("structural_fields", {}).get("candidate_rows")
    )
    meta_insuff = sum(1 for r in results if r.get("metadata_insufficient"))

    n_with_structural = sum(
        1 for r in results if r.get("structural_best_answer", "")
    )
    agrees_count = sum(1 for r in results if r.get("policy_agrees_with_structural"))
    proxy_fixes = sum(1 for r in results if r.get("policy_improves_proxy"))
    proxy_regressions = sum(1 for r in results if r.get("policy_regresses_proxy"))
    no_change_count = sum(1 for r in results if r.get("no_change"))
    requires_live_vc = sum(
        1 for r in results if r.get("requires_live_verifier_branch_allocation")
    )

    # Gold summary (gold used only here, never in scoring)
    gold_summary: dict[str, int] | None = None
    if any(casebook.get(c.get("case_id", ""), {}).get("gold_answer") for c in cases):
        baseline_exact = sum(
            1 for r in results
            if casebook.get(r["case_id"], {}).get("gold_answer") == r["baseline_answer"]
        )
        policy_exact = sum(
            1 for r in results
            if casebook.get(r["case_id"], {}).get("gold_answer") == r.get("policy_selected_answer")
        )
        structural_exact = sum(
            1 for r in results
            if casebook.get(r["case_id"], {}).get("gold_answer") == r.get("structural_best_answer")
        )
        fixes_exact = sum(
            1 for r in results
            if (casebook.get(r["case_id"], {}).get("gold_answer") != r["baseline_answer"]
                and casebook.get(r["case_id"], {}).get("gold_answer") == r.get("policy_selected_answer"))
        )
        regressions_exact = sum(
            1 for r in results
            if (casebook.get(r["case_id"], {}).get("gold_answer") == r["baseline_answer"]
                and casebook.get(r["case_id"], {}).get("gold_answer") != r.get("policy_selected_answer"))
        )
        gold_summary = {
            "baseline_exact": baseline_exact,
            "policy_exact": policy_exact,
            "structural_exact": structural_exact,
            "fixes_exact": fixes_exact,
            "regressions_exact": regressions_exact,
            "net_exact": fixes_exact - regressions_exact,
        }

    # Write outputs
    print("Writing outputs...", flush=True)

    _write_csv(args.out_dir / "case_policy_rows.csv", results)
    _write_jsonl(args.out_dir / "case_policy_rows.jsonl", results)

    missing_vc = [r for r in results if r.get("requires_live_verifier_branch_allocation")]
    _write_csv(args.out_dir / "missing_verifier_branch_cases.csv", missing_vc)

    summary = {
        "experiment": "colored_reasoning_path_policy_v1",
        "timestamp_utc": _TS,
        "trace_packets": str(args.trace_packets),
        "transition_rules": str(args.transition_rules),
        "motif_summary": str(args.motif_summary) if args.motif_summary else None,
        "replay_casebook": str(args.replay_casebook),
        "out_dir": str(args.out_dir),
        "min_lift": args.min_lift,
        "no_gold_features": str(args.no_gold_features).lower() in ("true", "1"),
        "api_calls_made": 0,
        "cases_loaded": cases_loaded,
        "cases_with_candidate_rows": cases_with_cands,
        "metadata_insufficient": meta_insuff,
        "cases_with_structural_best": n_with_structural,
        "policy_agrees_with_structural": agrees_count,
        "policy_agreement_rate": round(agrees_count / n_with_structural, 4)
        if n_with_structural > 0 else 0.0,
        "proxy_fixes": proxy_fixes,
        "proxy_regressions": proxy_regressions,
        "no_change": no_change_count,
        "net_proxy": proxy_fixes - proxy_regressions,
        "requires_live_verifier_branch_allocation": requires_live_vc,
        "pal_vc_lift": round(pal_vc, 4),
        "lift_index_size": len(lift_index),
        "gold_summary": gold_summary,
        "outputs": [
            "manifest.json",
            "case_policy_rows.csv",
            "case_policy_rows.jsonl",
            "policy_summary.json",
            "policy_summary.csv",
            "missing_verifier_branch_cases.csv",
            "report.md",
        ],
    }

    with open(args.out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(args.out_dir / "policy_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    summary_csv_row = {
        k: v for k, v in summary.items()
        if not isinstance(v, (dict, list))
    }
    _write_csv(args.out_dir / "policy_summary.csv", [summary_csv_row])

    report = _generate_report(
        args=args,
        cases_loaded=cases_loaded,
        cases_with_candidates=cases_with_cands,
        meta_insuff=meta_insuff,
        results=results,
        proxy_fixes=proxy_fixes,
        proxy_regressions=proxy_regressions,
        no_change_count=no_change_count,
        agrees_count=agrees_count,
        n_with_structural=n_with_structural,
        requires_live_vc=requires_live_vc,
        gold_summary=gold_summary,
    )
    (args.out_dir / "report.md").write_text(report, encoding="utf-8")

    print(f"Done. Output: {args.out_dir}", flush=True)
    print(f"  Policy agreement rate: {agrees_count}/{n_with_structural}", flush=True)
    print(f"  Proxy fixes/regressions: {proxy_fixes}/{proxy_regressions} (net {proxy_fixes - proxy_regressions:+d})", flush=True)
    print(f"  Requires live verifier branch: {requires_live_vc}", flush=True)

    return summary


if __name__ == "__main__":
    main()
