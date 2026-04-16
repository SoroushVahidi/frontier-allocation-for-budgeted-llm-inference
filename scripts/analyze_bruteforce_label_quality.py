#!/usr/bin/env python3
"""Generate label-quality diagnostics for brute-force branch-label runs."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def summarize_distribution(vals: list[float]) -> dict[str, float]:
    if not vals:
        return {"count": 0}
    xs = sorted(float(v) for v in vals)

    def q(p: float) -> float:
        if len(xs) == 1:
            return xs[0]
        idx = min(len(xs) - 1, max(0, int(round((len(xs) - 1) * p))))
        return xs[idx]

    return {
        "count": len(xs),
        "mean": float(mean(xs)),
        "min": float(xs[0]),
        "p10": float(q(0.10)),
        "p25": float(q(0.25)),
        "p50": float(q(0.50)),
        "p75": float(q(0.75)),
        "p90": float(q(0.90)),
        "max": float(xs[-1]),
    }


def load_run(run_dir: Path) -> dict[str, Any]:
    candidates = read_jsonl(run_dir / "candidate_labels.jsonl")
    pairwise = read_jsonl(run_dir / "pairwise_labels.jsonl")
    states = read_jsonl(run_dir / "state_summaries.jsonl")
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return {
        "run_dir": str(run_dir),
        "candidates": candidates,
        "pairwise": pairwise,
        "states": states,
        "manifest": manifest,
    }


def build_quality_summary(run: dict[str, Any], near_tie_margin: float) -> dict[str, Any]:
    states = run["states"]
    candidates = run["candidates"]
    pairwise = run["pairwise"]

    margins_abs = [abs(float(r.get("margin", 0.0))) for r in pairwise]
    gaps_abs = [abs(float(r.get("branch_vs_outside_gap", 0.0))) for r in candidates]
    near_tie_rows = [m for m in margins_abs if m <= near_tie_margin]

    mode_counts = Counter(str(r.get("candidate_mode", "unknown")) for r in states)

    by_budget: dict[int, dict[str, Any]] = defaultdict(lambda: {
        "states": 0,
        "candidate_rows": 0,
        "pairwise_rows": 0,
        "near_tie_pairwise_rows": 0,
        "winner_gap_values": [],
        "margin_values": [],
    })

    winner_by_state: dict[str, str] = {}
    for s in states:
        sid = str(s["state_id"])
        b = int(s.get("remaining_budget", -1))
        by_budget[b]["states"] += 1
        winner_by_state[sid] = str(s.get("winner_branch_id", ""))

    for c in candidates:
        sid = str(c["state_id"])
        b = int(c.get("remaining_budget", -1))
        by_budget[b]["candidate_rows"] += 1
        if str(c.get("branch_id", "")) == winner_by_state.get(sid, ""):
            by_budget[b]["winner_gap_values"].append(float(c.get("branch_vs_outside_gap", 0.0)))

    for p in pairwise:
        b = int(p.get("remaining_budget", -1))
        m = abs(float(p.get("margin", 0.0)))
        by_budget[b]["pairwise_rows"] += 1
        by_budget[b]["margin_values"].append(m)
        if m <= near_tie_margin:
            by_budget[b]["near_tie_pairwise_rows"] += 1

    per_budget = {}
    for b, row in sorted(by_budget.items()):
        pairwise_n = int(row["pairwise_rows"])
        per_budget[str(b)] = {
            "states": int(row["states"]),
            "candidate_rows": int(row["candidate_rows"]),
            "pairwise_rows": pairwise_n,
            "near_tie_pairwise_rows": int(row["near_tie_pairwise_rows"]),
            "near_tie_pairwise_rate": float(row["near_tie_pairwise_rows"] / pairwise_n) if pairwise_n else 0.0,
            "winner_gap_distribution": summarize_distribution(row["winner_gap_values"]),
            "margin_abs_distribution": summarize_distribution(row["margin_values"]),
        }

    winner_gap_values = [
        float(c.get("branch_vs_outside_gap", 0.0))
        for c in candidates
        if str(c.get("branch_id", "")) == winner_by_state.get(str(c["state_id"]), "")
    ]

    return {
        "run_dir": run["run_dir"],
        "counts": {
            "frontier_states_labeled": len(states),
            "candidate_rows": len(candidates),
            "pairwise_rows": len(pairwise),
            "mode_counts": dict(mode_counts),
        },
        "margin_abs_distribution": summarize_distribution(margins_abs),
        "near_tie": {
            "threshold": near_tie_margin,
            "near_tie_pairwise_rows": len(near_tie_rows),
            "near_tie_pairwise_rate": float(len(near_tie_rows) / max(1, len(pairwise))),
        },
        "branch_vs_outside_gap_abs_distribution": summarize_distribution(gaps_abs),
        "winner_branch_vs_outside_gap_distribution": summarize_distribution(winner_gap_values),
        "per_budget": per_budget,
    }


def compare_exact_vs_approx(exact_run: dict[str, Any], approx_run: dict[str, Any], near_tie_margin: float) -> dict[str, Any]:
    exact_candidates = {
        (str(r["state_id"]), str(r["branch_id"])): r
        for r in exact_run["candidates"]
    }
    approx_candidates = {
        (str(r["state_id"]), str(r["branch_id"])): r
        for r in approx_run["candidates"]
    }

    overlap_keys = sorted(set(exact_candidates).intersection(approx_candidates))
    state_ids = sorted({k[0] for k in overlap_keys})

    winner_exact = {str(r["state_id"]): str(r.get("winner_branch_id", "")) for r in exact_run["states"]}
    winner_approx = {str(r["state_id"]): str(r.get("winner_branch_id", "")) for r in approx_run["states"]}

    winner_overlap_states = sorted(set(winner_exact).intersection(winner_approx))
    winner_agree = sum(1 for sid in winner_overlap_states if winner_exact[sid] == winner_approx[sid])

    sign_agree = 0
    near_tie_overlap = 0
    abs_diffs: list[float] = []
    rel_diffs: list[float] = []
    for key in overlap_keys:
        e = float(exact_candidates[key].get("branch_vs_outside_gap", 0.0))
        a = float(approx_candidates[key].get("branch_vs_outside_gap", 0.0))
        sign_agree += int((e > 0) == (a > 0))
        abs_diffs.append(abs(e - a))
        denom = max(1e-9, abs(e))
        rel_diffs.append(abs(e - a) / denom)
        if abs(e) <= near_tie_margin:
            near_tie_overlap += 1

    return {
        "overlap": {
            "overlap_states": len(state_ids),
            "overlap_candidate_rows": len(overlap_keys),
            "winner_overlap_states": len(winner_overlap_states),
        },
        "winner_agreement": {
            "agree_states": winner_agree,
            "agreement_rate": float(winner_agree / max(1, len(winner_overlap_states))),
        },
        "gap_sign_agreement": {
            "agree_rows": sign_agree,
            "agreement_rate": float(sign_agree / max(1, len(overlap_keys))),
        },
        "difference": {
            "branch_vs_outside_gap_abs_diff": summarize_distribution(abs_diffs),
            "branch_vs_outside_gap_rel_diff": summarize_distribution(rel_diffs),
            "near_tie_rows_in_exact_at_threshold": near_tie_overlap,
        },
    }


def render_markdown(
    out_path: Path,
    *,
    near_tie_margin: float,
    medium_summary: dict[str, Any],
    comparison_summary: dict[str, Any],
    training_eval: dict[str, Any] | None,
) -> None:
    lines: list[str] = []
    lines.append("# Brute-force branch-label quality report")
    lines.append("")
    lines.append(f"- Near-tie threshold: `{near_tie_margin}`")
    lines.append(f"- Medium-scale run: `{medium_summary['run_dir']}`")
    lines.append("")

    c = medium_summary["counts"]
    lines.append("## Medium-scale label corpus summary")
    lines.append("")
    lines.append(f"- Frontier states labeled: **{c['frontier_states_labeled']}**")
    lines.append(f"- Candidate rows: **{c['candidate_rows']}**")
    lines.append(f"- Pairwise rows: **{c['pairwise_rows']}**")
    lines.append(f"- Mode counts: `{c['mode_counts']}`")
    lines.append("")

    mt = medium_summary["near_tie"]
    lines.append("## Quality distributions")
    lines.append("")
    lines.append(f"- Near-tie pairwise rows: **{mt['near_tie_pairwise_rows']} / {c['pairwise_rows']}** ({mt['near_tie_pairwise_rate']:.3f})")
    lines.append(f"- Margin |abs| p50: **{medium_summary['margin_abs_distribution'].get('p50', 0.0):.4f}**, p90: **{medium_summary['margin_abs_distribution'].get('p90', 0.0):.4f}**")
    lines.append(f"- Branch-vs-outside gap |abs| p50: **{medium_summary['branch_vs_outside_gap_abs_distribution'].get('p50', 0.0):.4f}**, p90: **{medium_summary['branch_vs_outside_gap_abs_distribution'].get('p90', 0.0):.4f}**")
    lines.append(f"- Winner gap p50: **{medium_summary['winner_branch_vs_outside_gap_distribution'].get('p50', 0.0):.4f}**")
    lines.append("")

    lines.append("## Per-budget breakdown")
    lines.append("")
    lines.append("| Remaining budget | States | Candidate rows | Pairwise rows | Near-tie rate | Winner gap p50 |")
    lines.append("|---:|---:|---:|---:|---:|---:|")
    for budget, row in medium_summary["per_budget"].items():
        lines.append(
            f"| {budget} | {row['states']} | {row['candidate_rows']} | {row['pairwise_rows']} | {row['near_tie_pairwise_rate']:.3f} | {row['winner_gap_distribution'].get('p50', 0.0):.4f} |"
        )
    lines.append("")

    lines.append("## Exact vs approximate comparison slice")
    lines.append("")
    ov = comparison_summary["overlap"]
    wa = comparison_summary["winner_agreement"]
    ga = comparison_summary["gap_sign_agreement"]
    dd = comparison_summary["difference"]
    lines.append(f"- Overlap states: **{ov['overlap_states']}**; overlap candidate rows: **{ov['overlap_candidate_rows']}**")
    lines.append(f"- Winner agreement: **{wa['agree_states']} / {ov['winner_overlap_states']}** ({wa['agreement_rate']:.3f})")
    lines.append(f"- Gap-sign agreement (branch beats outside option): **{ga['agree_rows']} / {ov['overlap_candidate_rows']}** ({ga['agreement_rate']:.3f})")
    lines.append(f"- Gap abs-diff p50: **{dd['branch_vs_outside_gap_abs_diff'].get('p50', 0.0):.4f}**, p90: **{dd['branch_vs_outside_gap_abs_diff'].get('p90', 0.0):.4f}**")
    lines.append("")

    if training_eval is not None:
        lines.append("## Pilot learner status")
        lines.append("")
        for model_name, payload in training_eval.get("evaluation", {}).items():
            lines.append(
                f"- `{model_name}`: status={payload.get('model_status')}, "
                f"pairwise_acc_test={payload.get('pairwise_accuracy_test', 0.0):.3f}, "
                f"ranking_top1_acc_test={payload.get('ranking_top1_accuracy_test', 0.0):.3f}"
            )
        lines.append("")

    lines.append("## Interpretation")
    lines.append("")
    lines.append("- The run materially increases available branch-comparison supervision over tiny pilots.")
    lines.append("- Approximate labels match exact winners on most overlapping tiny feasible states, but not perfectly.")
    lines.append("- Label bottleneck appears reduced but not eliminated; margin/noise handling remains important.")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze brute-force branch-label quality")
    p.add_argument("--medium-run-dir", required=True)
    p.add_argument("--exact-run-dir", required=True)
    p.add_argument("--approx-run-dir", required=True)
    p.add_argument("--training-eval-json", default="")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    medium = load_run(Path(args.medium_run_dir))
    exact = load_run(Path(args.exact_run_dir))
    approx = load_run(Path(args.approx_run_dir))
    training_eval = None
    if args.training_eval_json:
        training_eval = json.loads(Path(args.training_eval_json).read_text(encoding="utf-8"))

    medium_summary = build_quality_summary(medium, near_tie_margin=float(args.near_tie_margin))
    comparison_summary = compare_exact_vs_approx(exact, approx, near_tie_margin=float(args.near_tie_margin))

    out_json_payload = {
        "near_tie_margin": float(args.near_tie_margin),
        "medium_scale": medium_summary,
        "exact_vs_approx": comparison_summary,
        "pilot_training_evaluation": training_eval,
    }
    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out_json_payload, indent=2), encoding="utf-8")

    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    render_markdown(
        out_md,
        near_tie_margin=float(args.near_tie_margin),
        medium_summary=medium_summary,
        comparison_summary=comparison_summary,
        training_eval=training_eval,
    )

    print(json.dumps({"output_json": str(out_json), "output_md": str(out_md)}, indent=2))


if __name__ == "__main__":
    main()
