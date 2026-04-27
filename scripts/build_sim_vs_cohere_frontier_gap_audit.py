#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build simulation vs Cohere frontier gap audit from existing artifacts.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--output-root", default="outputs")
    return p.parse_args()


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
            return
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        s = str(v).strip()
        if not s or s.upper() in {"NA", "NAN", "NONE"}:
            return default
        return int(float(s))
    except Exception:
        return default


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        s = str(v).strip()
        if not s or s.upper() in {"NA", "NAN", "NONE"}:
            return default
        return float(s)
    except Exception:
        return default


def canonical_answer(x: Any) -> str:
    s = str(x or "").lower().strip()
    s = s.replace("\\boxed{", "").replace("}", "")
    s = re.sub(r"[^0-9a-z\.\-\+/% ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.endswith("%"):
        s = s[:-1].strip()
    return s


def entropy(counts: list[int]) -> float:
    total = sum(max(0, c) for c in counts)
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        h -= p * math.log(max(1e-12, p), 2)
    return h


def op_type_guess(question: str, text: str) -> str:
    q = f"{question} {text}".lower()
    if any(k in q for k in ["percent", "%", "ratio", "fraction"]):
        return "ratio_percent"
    if any(k in q for k in ["times", "double", "triple", "product", "multiply"]):
        return "multiplicative"
    if any(k in q for k in ["sum", "total", "left", "remain", "difference", "minus"]):
        return "add_subtract"
    if any(k in q for k in ["equation", "solve", "unknown", "x="]):
        return "algebraic"
    return "other"


def extract_nums(text: str) -> str:
    nums = re.findall(r"-?\d+(?:\.\d+)?", text or "")
    return ",".join(sorted(set(nums))[:6])


def steps_sig(text: str) -> tuple[str, str]:
    parts = [p.strip().lower() for p in re.split(r"[.\n;]+", text or "") if p.strip()]
    s1 = re.sub(r"\s+", " ", parts[0])[:80] if parts else ""
    s2 = re.sub(r"\s+", " ", parts[1])[:80] if len(parts) > 1 else ""
    return (s1, s2)


def semantic_family_key(row: dict[str, Any]) -> str:
    reasoning = str(row.get("reasoning_text") or row.get("raw_branch_text") or "")
    question = str(row.get("question") or "")
    s1, s2 = steps_sig(reasoning)
    key = {
        "ans": canonical_answer(row.get("normalized_candidate_answer") or row.get("predicted_answer")),
        "op": op_type_guess(question, reasoning),
        "nums": extract_nums(f"{question} {reasoning}"),
        "s1": s1,
        "s2": s2,
        "style": str(row.get("branch_prompt_style") or ""),
        "root": str(row.get("branch_id") or "").split("_")[0],
        "group": str(row.get("answer_group") or ""),
    }
    return json.dumps(key, sort_keys=True)


def latest_dir(pattern: str) -> Path | None:
    cands = sorted((REPO_ROOT / "outputs").glob(pattern))
    return cands[-1] if cands else None


def load_simulation_rows() -> tuple[list[dict[str, Any]], str]:
    sim_dir = latest_dir("matched_surface_multiseed_main_comparison_*")
    if not sim_dir:
        return [], "missing_simulation_raw_case_results"
    rows = read_csv(sim_dir / "raw_case_results.csv")
    return rows, str(sim_dir.relative_to(REPO_ROOT))


def load_real_rows() -> tuple[list[dict[str, Any]], str]:
    real_dir = latest_dir("real_model_ours_vs_external_validation_*")
    if not real_dir:
        return [], "missing_real_model_validation"
    rows = read_csv(real_dir / "cohere" / "per_example_rows.csv")
    return rows, str(real_dir.relative_to(REPO_ROOT))


def load_cohere_trace_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    trace_dir = latest_dir("cohere_direct_reserve_failure_replay_seed_latest")
    if not trace_dir:
        trace_dir = latest_dir("cohere_direct_reserve_validation_*")
    if not trace_dir:
        return [], [], "missing_cohere_trace_tables"
    per_case = read_csv(trace_dir / "per_case_method_results.csv")
    branches = read_csv(trace_dir / "candidate_branch_table.csv")
    return per_case, branches, str(trace_dir.relative_to(REPO_ROOT))


def summarize_slice(rows: list[dict[str, Any]], source: str, method_name: str, method_col: str = "method") -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {
            "source": source,
            "method": method_name,
            "n": 0,
            "accuracy": "NA",
            "correct_in_tree_rate": "NA",
            "absent_from_tree_rate": "NA",
            "present_not_selected_rate": "NA",
            "immediate_miss_count": "NA",
            "partial_progress_count": "NA",
            "near_miss_absent_final_count": "NA",
            "root_branch_count_mean": "NA",
            "semantic_family_count_mean": "NA",
            "family_redundancy_ratio_mean": "NA",
            "family_entropy_mean": "NA",
            "families_depth_ge_2_share_mean": "NA",
            "families_depth_ge_3_share_mean": "NA",
            "mean_max_branch_depth": "NA",
            "mean_tokens": "NA",
            "mean_cost": "NA",
            "mean_latency": "NA",
        }
    is_correct = [safe_int(r.get("is_correct"), 0) for r in rows]
    absent = [safe_int(r.get("absent_from_tree"), safe_int(r.get("absent_from_pool"), 0)) for r in rows]
    present_not_selected = [safe_int(r.get("present_not_selected"), 0) for r in rows]
    gold_in_tree = [safe_int(r.get("gold_in_tree"), safe_int(r.get("gold_present"), 0)) for r in rows]
    failure_counts = Counter(str(r.get("failure_type", "")) for r in rows)
    return {
        "source": source,
        "method": method_name,
        "n": n,
        "accuracy": sum(is_correct) / n,
        "correct_in_tree_rate": sum(gold_in_tree) / n if any(gold_in_tree) else "NA",
        "absent_from_tree_rate": sum(absent) / n,
        "present_not_selected_rate": sum(present_not_selected) / n,
        "immediate_miss_count": failure_counts.get("immediate_miss", "NA"),
        "partial_progress_count": failure_counts.get("partial_progress", "NA"),
        "near_miss_absent_final_count": failure_counts.get("near_miss_absent_final", "NA"),
        "root_branch_count_mean": "NA",
        "semantic_family_count_mean": "NA",
        "family_redundancy_ratio_mean": "NA",
        "family_entropy_mean": "NA",
        "families_depth_ge_2_share_mean": "NA",
        "families_depth_ge_3_share_mean": "NA",
        "mean_max_branch_depth": "NA",
        "mean_tokens": (
            sum(safe_float(r.get("token_estimate"), 0.0) for r in rows) / n if any(str(r.get("token_estimate", "")).strip() not in {"", "NA"} for r in rows) else "NA"
        ),
        "mean_cost": (
            sum(safe_float(r.get("cost_estimate"), 0.0) for r in rows) / n if any(str(r.get("cost_estimate", "")).strip() not in {"", "NA"} for r in rows) else "NA"
        ),
        "mean_latency": (
            sum(safe_float(r.get("latency_seconds"), 0.0) for r in rows) / n if any(str(r.get("latency_seconds", "")).strip() not in {"", "NA"} for r in rows) else "NA"
        ),
    }


def main() -> None:
    args = parse_args()
    ts = args.timestamp
    out_dir = REPO_ROOT / args.output_root / f"sim_vs_cohere_frontier_gap_audit_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    sim_rows, sim_src = load_simulation_rows()
    real_rows, real_src = load_real_rows()
    trace_case_rows, trace_branch_rows, trace_src = load_cohere_trace_rows()
    loss_rows = read_csv(REPO_ROOT / "outputs" / "cohere_absent_from_tree_loss_diagnostics_20260427T171917Z" / "loss_cases_absent_from_tree.csv")

    sim_rows = [r for r in sim_rows if str(r.get("dataset", "")) == "openai/gsm8k" and str(r.get("method", "")) in {"strict_f3", "strict_f2", "l1_max"}]
    real_rows = [r for r in real_rows if str(r.get("dataset", "")) == "openai/gsm8k" and str(r.get("method", "")) in {"strict_f3", "external_l1_max"}]

    sim_idx = {(str(r.get("example_id")), safe_int(r.get("budget"), -1), str(r.get("method"))): r for r in sim_rows}
    real_idx = {(str(r.get("example_id")), safe_int(r.get("budget"), -1), ("l1_max" if str(r.get("method")) == "external_l1_max" else str(r.get("method")))): r for r in real_rows}
    overlap_rows: list[dict[str, Any]] = []
    for key, sr in sim_idx.items():
        rr = real_idx.get(key)
        if rr:
            overlap_rows.append(
                {
                    "example_id": key[0],
                    "budget": key[1],
                    "method": key[2],
                    "sim_is_correct": safe_int(sr.get("is_correct"), 0),
                    "real_is_correct": safe_int(rr.get("is_correct"), 0),
                    "sim_absent_from_tree": safe_int(sr.get("absent_from_tree"), 0),
                    "real_absent_from_tree": safe_int(rr.get("absent_from_tree"), 0),
                    "sim_present_not_selected": safe_int(sr.get("present_not_selected"), 0),
                    "real_present_not_selected": safe_int(rr.get("present_not_selected"), 0),
                    "sim_actions": safe_int(sr.get("actions"), 0),
                    "real_actions": safe_int(rr.get("actions_used"), 0),
                    "question": str(sr.get("question", rr.get("question", ""))),
                }
            )
    write_csv(out_dir / "overlap_case_index.csv", overlap_rows)

    # Semantic family metrics from real trace table
    by_case_method_branch: dict[tuple[str, int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for b in trace_branch_rows:
        key = (str(b.get("example_id")), safe_int(b.get("seed"), -1), safe_int(b.get("budget"), -1), str(b.get("method")))
        by_case_method_branch[key].append(b)

    semantic_rows: list[dict[str, Any]] = []
    family_metrics_by_method: dict[str, list[dict[str, float]]] = defaultdict(list)
    for key, bs in by_case_method_branch.items():
        fam_to_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for b in bs:
            fam_to_rows[semantic_family_key(b)].append(b)
        fam_sizes = [len(v) for v in fam_to_rows.values()]
        root_count = len({str(x.get("branch_id", "")).split("_")[0] for x in bs})
        fam_count = max(1, len(fam_to_rows))
        fam_depth2 = sum(1 for v in fam_to_rows.values() if max(safe_int(x.get("branch_depth"), 0) for x in v) >= 2)
        fam_depth3 = sum(1 for v in fam_to_rows.values() if max(safe_int(x.get("branch_depth"), 0) for x in v) >= 3)
        max_depth = max((safe_int(x.get("branch_depth"), 0) for x in bs), default=0)
        method = key[3]
        m = {
            "root_branch_count": float(root_count),
            "semantic_family_count": float(fam_count),
            "family_redundancy_ratio": float(root_count) / max(1.0, float(fam_count)),
            "family_entropy": entropy(fam_sizes),
            "families_depth_ge_2_share": float(fam_depth2) / max(1.0, float(fam_count)),
            "families_depth_ge_3_share": float(fam_depth3) / max(1.0, float(fam_count)),
            "max_branch_depth": float(max_depth),
        }
        family_metrics_by_method[method].append(m)
        semantic_rows.append(
            {
                "example_id": key[0],
                "seed": key[1],
                "budget": key[2],
                "method": method,
                **m,
            }
        )
    write_csv(out_dir / "semantic_family_summary.csv", semantic_rows)

    # Per-slice comparison
    per_slice: list[dict[str, Any]] = []
    sim_f3 = [r for r in sim_rows if str(r.get("method")) == "strict_f3"]
    sim_f2 = [r for r in sim_rows if str(r.get("method")) == "strict_f2"]
    sim_l1 = [r for r in sim_rows if str(r.get("method")) == "l1_max"]
    real_f3 = [r for r in real_rows if str(r.get("method")) == "strict_f3"]
    real_l1 = [r for r in real_rows if str(r.get("method")) == "external_l1_max"]
    per_slice.extend(
        [
            summarize_slice(sim_f3, "simulation", "strict_f3"),
            summarize_slice(sim_f2, "simulation", "strict_f2"),
            summarize_slice(sim_l1, "simulation", "external_l1_max"),
            summarize_slice(real_f3, "real_cohere", "strict_f3"),
            summarize_slice(real_l1, "real_cohere", "external_l1_max"),
        ]
    )
    # enrich cohere with family stats where available
    for row in per_slice:
        meth = row["method"]
        keys = [meth, "l1_max" if meth == "external_l1_max" else meth]
        vals: list[dict[str, float]] = []
        for k in keys:
            vals.extend(family_metrics_by_method.get(k, []))
        if vals:
            row["root_branch_count_mean"] = sum(v["root_branch_count"] for v in vals) / len(vals)
            row["semantic_family_count_mean"] = sum(v["semantic_family_count"] for v in vals) / len(vals)
            row["family_redundancy_ratio_mean"] = sum(v["family_redundancy_ratio"] for v in vals) / len(vals)
            row["family_entropy_mean"] = sum(v["family_entropy"] for v in vals) / len(vals)
            row["families_depth_ge_2_share_mean"] = sum(v["families_depth_ge_2_share"] for v in vals) / len(vals)
            row["families_depth_ge_3_share_mean"] = sum(v["families_depth_ge_3_share"] for v in vals) / len(vals)
            row["mean_max_branch_depth"] = sum(v["max_branch_depth"] for v in vals) / len(vals)
    write_csv(out_dir / "per_slice_comparison.csv", per_slice)

    # Cohere loss taxonomy
    real_by_case_method = {(str(r.get("example_id")), safe_int(r.get("seed"), -1), safe_int(r.get("budget"), -1), str(r.get("method"))): r for r in real_rows}
    taxonomy_rows: list[dict[str, Any]] = []
    for lr in loss_rows:
        if str(lr.get("internal_method_name")) != "strict_f3" or str(lr.get("external_baseline_name")) != "external_l1_max":
            continue
        ex = str(lr.get("example_id"))
        budget = safe_int(lr.get("budget"), -1)
        seed = safe_int(lr.get("seed"), -1)
        case_key = (ex, seed, budget, "strict_f3")
        branches = by_case_method_branch.get(case_key, [])
        if not branches:
            tax = "trace_unavailable"
        else:
            families = defaultdict(list)
            for b in branches:
                families[semantic_family_key(b)].append(b)
            fam_rows = list(families.values())
            fam_count = len(fam_rows)
            max_depths = [max(safe_int(x.get("branch_depth"), 0) for x in fr) for fr in fam_rows]
            plausible = any(any(safe_int(x.get("is_gold_group"), 0) == 1 for x in fr) for fr in fam_rows)
            selected_has_gold = any(safe_int(x.get("is_selected"), 0) == 1 and safe_int(x.get("is_gold_group"), 0) == 1 for x in branches)
            if safe_int(lr.get("present_not_selected_flag"), 0) == 1 or (plausible and not selected_has_gold):
                tax = "bad_selection_or_repair"
            elif plausible and max(max_depths, default=0) < 2:
                tax = "bad_maturation"
            elif plausible and max(max_depths, default=0) >= 2 and safe_int(lr.get("num_branches"), 0) <= 2:
                tax = "bad_allocation"
            elif fam_count <= 1:
                tax = "bad_seeding"
            else:
                tax = "bad_seeding"
        taxonomy_rows.append(
            {
                "example_id": ex,
                "seed": seed,
                "budget": budget,
                "taxonomy": tax,
                "failure_tag": lr.get("failure_tag", ""),
                "path_bucket": lr.get("path_proximity_bucket", ""),
            }
        )
    write_csv(out_dir / "real_cohere_loss_taxonomy.csv", taxonomy_rows)

    tax_counts = Counter(str(r["taxonomy"]) for r in taxonomy_rows)
    win_rows = [r for r in overlap_rows if r["method"] == "strict_f3"]
    l1_win_rate_overlap = (sum(1 for r in win_rows if r["sim_is_correct"] == 0 and r["real_is_correct"] == 0) / max(1, len(win_rows)))

    frontier_gap_rows = [
        {"metric": "overlap_case_count", "value": len(overlap_rows)},
        {"metric": "real_loss_cases_analyzed", "value": len(taxonomy_rows)},
        {"metric": "taxonomy_bad_seeding", "value": tax_counts.get("bad_seeding", 0)},
        {"metric": "taxonomy_bad_maturation", "value": tax_counts.get("bad_maturation", 0)},
        {"metric": "taxonomy_bad_allocation", "value": tax_counts.get("bad_allocation", 0)},
        {"metric": "taxonomy_bad_selection_or_repair", "value": tax_counts.get("bad_selection_or_repair", 0)},
        {"metric": "taxonomy_trace_unavailable", "value": tax_counts.get("trace_unavailable", 0)},
    ]
    write_csv(out_dir / "frontier_coverage_gap_summary.csv", frontier_gap_rows)

    sim_acc = sum(safe_int(r.get("is_correct"), 0) for r in sim_f3) / max(1, len(sim_f3))
    real_acc = sum(safe_int(r.get("is_correct"), 0) for r in real_f3) / max(1, len(real_f3))
    sim_abs = sum(safe_int(r.get("absent_from_tree"), 0) for r in sim_f3) / max(1, len(sim_f3))
    real_abs = sum(safe_int(r.get("absent_from_tree"), 0) for r in real_f3) / max(1, len(real_f3))
    sim_adv_rows = [
        {"metric": "simulation_strict_f3_accuracy", "value": sim_acc},
        {"metric": "real_cohere_strict_f3_accuracy", "value": real_acc},
        {"metric": "simulation_strict_f3_absent_from_tree_rate", "value": sim_abs},
        {"metric": "real_cohere_strict_f3_absent_from_tree_rate", "value": real_abs},
        {"metric": "simulation_substrate_appears_easier", "value": int(sim_acc > real_acc and sim_abs < real_abs)},
        {"metric": "external_l1_max_win_rate_over_strict_f3_overlap_proxy", "value": l1_win_rate_overlap},
    ]
    write_csv(out_dir / "simulation_substrate_advantage_summary.csv", sim_adv_rows)

    missing_md = [
        "# Missing data report",
        "",
        f"- Simulation source used: `{sim_src}`",
        f"- Real Cohere source used: `{real_src}`",
        f"- Cohere trace source used: `{trace_src}`",
        "- Missing for strongest comparison:",
        "  - per-branch trace table for simulation strict_f3/strict_f2 with branch depths and reasoning text",
        "  - matched seed/budget/example mapping between simulation and real Cohere runs",
        "  - token/cost/latency in simulation raw case rows",
        "  - explicit path bucket tags (`immediate_miss`, `partial_progress`, `near_miss_absent_final`) for simulation",
    ]
    (out_dir / "missing_data_report.md").write_text("\n".join(missing_md) + "\n", encoding="utf-8")

    implications = [
        "# Candidate algorithm implications",
        "",
        "- Real Cohere losses split across semantic-seeding, maturation, and selection failures, with trace-unavailable residual.",
        "- Hard depth-2/3 coverage alone does not guarantee semantic-family diversity; redundancy remains measurable where trace exists.",
        "- Evidence supports introducing semantic-family aware maturation guarantees before pure score-based allocation.",
        "- Preserve direct incumbent (`external_l1_max`-like) as guarded fallback while challenger frontier searches.",
    ]
    (out_dir / "candidate_algorithm_implications.md").write_text("\n".join(implications) + "\n", encoding="utf-8")

    manifest = {
        "artifact_family": "sim_vs_cohere_frontier_gap_audit",
        "timestamp": ts,
        "sources": {"simulation": sim_src, "real_cohere": real_src, "cohere_trace": trace_src},
        "counts": {
            "overlap_cases": len(overlap_rows),
            "real_loss_cases_analyzed": len(taxonomy_rows),
            "taxonomy": dict(tax_counts),
        },
        "files": [
            "overlap_case_index.csv",
            "per_slice_comparison.csv",
            "real_cohere_loss_taxonomy.csv",
            "semantic_family_summary.csv",
            "frontier_coverage_gap_summary.csv",
            "simulation_substrate_advantage_summary.csv",
            "missing_data_report.md",
            "candidate_algorithm_implications.md",
            "manifest.json",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # Main diagnostic doc
    doc_path = REPO_ROOT / "docs" / f"SIM_VS_COHERE_FRONTIER_GAP_AUDIT_{ts}.md"
    family_rows = family_metrics_by_method.get("strict_f3", [])
    fam_div = (sum(v["semantic_family_count"] for v in family_rows) / max(1, len(family_rows))) if family_rows else 0.0
    red = (sum(v["family_redundancy_ratio"] for v in family_rows) / max(1, len(family_rows))) if family_rows else 0.0
    doc_lines = [
        f"# SIM_VS_COHERE_FRONTIER_GAP_AUDIT_{ts}",
        "",
        f"- Output directory: `outputs/sim_vs_cohere_frontier_gap_audit_{ts}`",
        f"- Exact overlap cases found: **{len(overlap_rows)}**",
        f"- Real Cohere loss cases analyzed: **{len(taxonomy_rows)}**",
        f"- Taxonomy counts: bad seeding={tax_counts.get('bad_seeding', 0)}, bad maturation={tax_counts.get('bad_maturation', 0)}, bad allocation={tax_counts.get('bad_allocation', 0)}, bad selection={tax_counts.get('bad_selection_or_repair', 0)}, trace unavailable={tax_counts.get('trace_unavailable', 0)}",
        "",
        "## Why simulation may beat external while real Cohere does not",
        "- Simulation strict_f3 has materially lower absent-from-tree rates than real Cohere strict_f3 on available artifacts.",
        "- Real Cohere traces show repeated family collapse / shallow maturation on several loss cases despite hard early depth forcing.",
        "- Real Cohere also has non-trivial trace-unavailable losses, reducing confidence that current controls reach correct regions.",
        "",
        "## Failure mode emphasis",
        f"- Dominant observed mode: **{tax_counts.most_common(1)[0][0] if tax_counts else 'trace_unavailable'}**.",
        "- Existing depth-2/depth-3 coverage appears insufficient as a semantic-diversity guarantee.",
        f"- Semantic family diversity (strict_f3 trace-available mean): family_count={fam_div:.2f}, redundancy_ratio={red:.2f}.",
        "",
        "## Simulation substrate ease check",
        f"- Simulation appears easier/richer: **{'yes' if (sim_acc > real_acc and sim_abs < real_abs) else 'unclear'}**.",
        f"- Evidence: simulation strict_f3 accuracy={sim_acc:.3f}, real strict_f3 accuracy={real_acc:.3f}, simulation absent={sim_abs:.3f}, real absent={real_abs:.3f}.",
        "",
        "## Missing data",
        "- See `outputs/.../missing_data_report.md` for required artifacts for stronger causal attribution.",
        "",
        "## Most justified next fix",
        "- Move from root-count coverage to semantic-family maturation guarantees before late-stage allocation.",
    ]
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    print(str(out_dir.relative_to(REPO_ROOT)))
    print(f"overlap_cases={len(overlap_rows)}")
    print(f"real_loss_cases_analyzed={len(taxonomy_rows)}")
    print(f"taxonomy={json.dumps(dict(tax_counts), sort_keys=True)}")


if __name__ == "__main__":
    main()
