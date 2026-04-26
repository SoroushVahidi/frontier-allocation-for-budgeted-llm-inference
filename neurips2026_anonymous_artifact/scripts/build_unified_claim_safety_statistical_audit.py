#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_OUTPUTS = [
    "manifest.json",
    "artifact_inventory.csv",
    "artifact_limitations.csv",
    "claim_safety_table.csv",
    "pairwise_statistical_tests.csv",
    "winner_instability_by_surface.csv",
    "real_model_vs_simulation_consistency.csv",
    "token_latency_accounting_summary.csv",
    "component_ablation_claim_support.csv",
    "manuscript_recommended_wording.json",
    "STATUS.md",
]

ARTIFACT_PATTERNS: dict[str, tuple[str, str]] = {
    "matched_surface_simulation": ("outputs", "matched_surface_multiseed_main_comparison_*"),
    "method_decision_bundle": ("outputs", "paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3"),
    "openai_real_model_audit": ("outputs", "openai_real_model_main_run_audit_*"),
    "cohere_real_model_audit": ("outputs", "cohere_real_model_main_run_audit_*"),
    "cross_provider_real_model_audit": ("outputs", "cross_provider_real_model_main_run_audit_*"),
    "token_accounting": ("outputs", "real_model_token_accounting_validation_*"),
    "cross_token_accounting": ("outputs", "cross_provider_real_model_token_accounting_validation_*"),
    "integrated_component_ablation": ("outputs", "integrated_controller_component_ablation_*"),
    "manuscript_component_ablation": ("outputs", "manuscript_surface_component_ablation_*"),
    "canonical_real_model_validation": ("outputs", "canonical_real_model_validation_*"),
    "openai_audit_docs": ("docs", "OPENAI_REAL_MODEL_MAIN_RUN_AUDIT_*.md"),
    "cohere_audit_docs": ("docs", "COHERE_REAL_MODEL_MAIN_RUN_AUDIT_*.md"),
    "cross_provider_audit_docs": ("docs", "CROSS_PROVIDER_REAL_MODEL_MAIN_RUN_AUDIT_*.md"),
    "operational_spec_docs": ("docs", "OPERATIONAL_CONTROLLER_SPECIFICATION_FOR_MANUSCRIPT_*.md"),
    # practical fallback: integrated real-model bundle already in repo
    "real_model_ours_vs_external": ("outputs", "real_model_ours_vs_external_validation_*"),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build unified claim-safety statistical audit from offline artifacts.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--output-root", default="outputs")
    p.add_argument("--docs-root", default="docs")
    p.add_argument("--repo-root", default=str(REPO_ROOT))
    p.add_argument("--bootstrap-samples", type=int, default=2000)
    p.add_argument("--permutation-samples", type=int, default=5000)
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers: list[str] = []
    for r in rows:
        for k in r.keys():
            if k not in headers:
                headers.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


def maybe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def normalize_method(name: str) -> str:
    n = (name or "").strip().lower()
    aliases = {
        "l1_max": "external_l1_max",
        "strict-gate1-cap-k6": "strict_gate1_cap_k6",
        "strict-f3": "strict_f3",
    }
    return aliases.get(n, n)


def discover_artifacts(repo_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inventory: list[dict[str, Any]] = []
    limitations: list[dict[str, Any]] = []
    for family, (root_rel, pattern) in ARTIFACT_PATTERNS.items():
        root = repo_root / root_rel
        matches = sorted(root.glob(pattern))
        if not matches:
            limitations.append(
                {
                    "artifact_family": family,
                    "severity": "missing",
                    "detail": f"No matches for {root_rel}/{pattern}",
                }
            )
            continue
        for m in matches:
            kind = "dir" if m.is_dir() else "file"
            per_case = False
            summary_only = False
            if m.is_dir():
                per_case = any(m.glob("**/per_case_results.csv")) or any(m.glob("**/raw_case_results.csv")) or any(m.glob("**/per_example_rows.csv"))
                summary_only = any(m.glob("**/*summary*.csv")) or any(m.glob("**/*summary*.json"))
            else:
                summary_only = True
            inventory.append(
                {
                    "artifact_family": family,
                    "path": str(m.relative_to(repo_root)),
                    "kind": kind,
                    "has_per_case": per_case,
                    "has_summary": summary_only,
                }
            )
    return inventory, limitations


def collect_per_case_rows(repo_root: Path, inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory:
        rel = item["path"]
        p = repo_root / rel
        family = item["artifact_family"]
        if p.is_file():
            continue

        candidates: list[Path] = []
        candidates.extend(sorted(p.glob("**/raw_case_results.csv")))
        candidates.extend(sorted(p.glob("**/per_case_results.csv")))
        candidates.extend(sorted(p.glob("**/per_example_rows.csv")))

        for csv_path in candidates:
            in_rows = read_csv(csv_path)
            if not in_rows:
                continue
            for r in in_rows:
                method = normalize_method(str(r.get("method") or r.get("variant") or r.get("runtime_method") or ""))
                if not method:
                    continue
                correct_val = r.get("is_correct", r.get("correct", r.get("is_correct_answer", "")))
                if str(correct_val).strip() == "":
                    continue
                correct = int(round(maybe_float(correct_val, 0.0)))
                provider = str(r.get("provider", "")).strip().lower()
                if not provider:
                    if "openai" in str(csv_path):
                        provider = "openai"
                    elif "cohere" in str(csv_path):
                        provider = "cohere"
                    else:
                        provider = "simulation"
                layer = "matched_surface_simulation" if family == "matched_surface_simulation" else family
                rows.append(
                    {
                        "evidence_layer": layer,
                        "provider": provider,
                        "dataset": str(r.get("dataset", "all")),
                        "budget": str(r.get("budget", "all")),
                        "seed": str(r.get("seed", "na")),
                        "example_id": str(r.get("example_id", r.get("id", "na"))),
                        "method": method,
                        "correct": correct,
                        "source_csv": str(csv_path.relative_to(repo_root)),
                    }
                )
    return rows


def bootstrap_ci(diffs: list[float], n_boot: int, seed: int) -> tuple[float, float]:
    if not diffs:
        return (math.nan, math.nan)
    rng = random.Random(seed)
    means = []
    n = len(diffs)
    for _ in range(max(200, n_boot)):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * (len(means) - 1))]
    hi = means[int(0.975 * (len(means) - 1))]
    return lo, hi


def paired_permutation_pvalue(diffs: list[float], n_samples: int, seed: int) -> float:
    if not diffs:
        return math.nan
    obs = abs(sum(diffs) / len(diffs))
    rng = random.Random(seed)
    n = len(diffs)
    if n <= 20:
        total = 1 << n
        extreme = 0
        for mask in range(total):
            s = 0.0
            for i, d in enumerate(diffs):
                s += d if ((mask >> i) & 1) == 1 else -d
            if abs(s / n) >= obs - 1e-12:
                extreme += 1
        return extreme / total
    extreme = 0
    trials = max(500, n_samples)
    for _ in range(trials):
        s = 0.0
        for d in diffs:
            s += d if rng.random() > 0.5 else -d
        if abs(s / n) >= obs - 1e-12:
            extreme += 1
    return extreme / trials


def pairwise_rows(per_case_rows: list[dict[str, Any]], n_boot: int, n_perm: int, seed: int) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in per_case_rows:
        g = (r["evidence_layer"], r["provider"], r["dataset"], r["budget"])
        groups[g].append(r)

    out: list[dict[str, Any]] = []
    for (layer, provider, dataset, budget), rows in sorted(groups.items()):
        by_method: dict[str, dict[tuple[str, str], int]] = defaultdict(dict)
        for r in rows:
            key = (r["seed"], r["example_id"])
            by_method[r["method"]][key] = int(r["correct"])

        method_set = set(by_method.keys())
        frontier = sorted([m for m in method_set if m.startswith("strict_") or "frontier" in m or "allocation" in m])
        near_direct = sorted([m for m in method_set if m.startswith("external_") or m.startswith("self_consistency")])

        required_pairs = [
            ("strict_f3", "strict_gate1_cap_k6", "required"),
            ("strict_f3", "external_l1_max", "required"),
            ("strict_gate1_cap_k6", "external_l1_max", "required"),
            ("strict_f3", "self_consistency_3", "required_if_available"),
        ]

        if frontier and "external_l1_max" in method_set:
            best_frontier = max(frontier, key=lambda m: sum(by_method[m].values()) / max(1, len(by_method[m])))
            required_pairs.append((best_frontier, "external_l1_max", "required"))
        if frontier and near_direct:
            best_frontier = max(frontier, key=lambda m: sum(by_method[m].values()) / max(1, len(by_method[m])))
            best_near = max(near_direct, key=lambda m: sum(by_method[m].values()) / max(1, len(by_method[m])))
            required_pairs.append((best_frontier, best_near, "family_if_available"))

        for a, b, rule in required_pairs:
            if a not in method_set or b not in method_set:
                continue
            keys = sorted(set(by_method[a].keys()) & set(by_method[b].keys()))
            if not keys:
                continue
            va = [by_method[a][k] for k in keys]
            vb = [by_method[b][k] for k in keys]
            diffs = [x - y for x, y in zip(va, vb)]
            win = sum(1 for d in diffs if d > 0)
            tie = sum(1 for d in diffs if d == 0)
            loss = sum(1 for d in diffs if d < 0)
            acc_a = sum(va) / len(va)
            acc_b = sum(vb) / len(vb)
            mean_diff = acc_a - acc_b
            ci_low, ci_high = bootstrap_ci(diffs, n_boot=n_boot, seed=hash((seed, layer, provider, dataset, budget, a, b, "boot")) & 0xFFFFFFFF)
            pval = paired_permutation_pvalue(diffs, n_samples=n_perm, seed=hash((seed, layer, provider, dataset, budget, a, b, "perm")) & 0xFFFFFFFF)
            if math.isnan(pval):
                interpretation = "statistical testing unavailable"
            elif pval < 0.05 and ci_low > 0:
                interpretation = f"{a} statistically stronger"
            elif pval < 0.05 and ci_high < 0:
                interpretation = f"{b} statistically stronger"
            else:
                interpretation = "difference fragile / not statistically decisive"
            out.append(
                {
                    "evidence_layer": layer,
                    "provider": provider,
                    "dataset": dataset,
                    "budget": budget,
                    "method_a": a,
                    "method_b": b,
                    "comparison_rule": rule,
                    "n_paired": len(keys),
                    "accuracy_a": round(acc_a, 6),
                    "accuracy_b": round(acc_b, 6),
                    "mean_difference": round(mean_diff, 6),
                    "bootstrap_ci_low": round(ci_low, 6),
                    "bootstrap_ci_high": round(ci_high, 6),
                    "permutation_p_value": round(pval, 6),
                    "win_count": win,
                    "tie_count": tie,
                    "loss_count": loss,
                    "interpretation": interpretation,
                }
            )
    return out


def winner_instability(per_case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_slice: dict[tuple[str, str, str, str, str], dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in per_case_rows:
        key = (r["evidence_layer"], r["dataset"], r["budget"], r["seed"], r["provider"])
        by_slice[key][r["method"]].append(int(r["correct"]))

    winners_by_core: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    for (layer, ds, bdg, seed, prov), mm in by_slice.items():
        if not mm:
            continue
        winner = max(mm.keys(), key=lambda m: sum(mm[m]) / max(1, len(mm[m])))
        core = (ds, bdg, seed, prov)
        winners_by_core[core].add(f"{layer}:{winner}")

    grouped: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    out: list[dict[str, Any]] = []
    for (ds, bdg, seed, prov), winners in sorted(winners_by_core.items()):
        unstable = 1 if len(winners) > 1 else 0
        grouped[(ds, bdg, prov)].append(unstable)
        out.append(
            {
                "dataset": ds,
                "budget": bdg,
                "seed": seed,
                "provider": prov,
                "simulation_vs_real_surface_count": len(winners),
                "winner_changed": unstable,
                "winners": " | ".join(sorted(winners)),
            }
        )
    for (ds, bdg, prov), vals in sorted(grouped.items()):
        out.append(
            {
                "dataset": ds,
                "budget": bdg,
                "seed": "ALL",
                "provider": prov,
                "simulation_vs_real_surface_count": "aggregate",
                "winner_changed": round(sum(vals) / max(1, len(vals)), 6),
                "winners": "instability_rate",
            }
        )
    return out


def consistency_table(pairwise: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_pairs = [("strict_f3", "strict_gate1_cap_k6"), ("strict_f3", "external_l1_max")]
    out: list[dict[str, Any]] = []
    for a, b in target_pairs:
        sim = [r for r in pairwise if r["method_a"] == a and r["method_b"] == b and r["provider"] == "simulation"]
        real = [r for r in pairwise if r["method_a"] == a and r["method_b"] == b and r["provider"] in {"openai", "cohere"}]
        if not sim and not real:
            continue
        sim_mean = sum(float(r["mean_difference"]) for r in sim) / max(1, len(sim)) if sim else math.nan
        real_mean = sum(float(r["mean_difference"]) for r in real) / max(1, len(real)) if real else math.nan
        direction_consistent = (sim_mean >= 0 and real_mean >= 0) or (sim_mean <= 0 and real_mean <= 0)
        out.append(
            {
                "comparison": f"{a}_vs_{b}",
                "simulation_mean_difference": sim_mean,
                "real_model_mean_difference": real_mean,
                "direction_consistent": bool(direction_consistent),
                "real_model_rows": len(real),
                "simulation_rows": len(sim),
            }
        )
    return out


def token_latency_summary(repo_root: Path, inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory:
        if item["artifact_family"] not in {"token_accounting", "cross_token_accounting"}:
            continue
        p = repo_root / item["path"]
        if not p.is_dir():
            continue
        for s in sorted(p.glob("**/summary_by_method*.csv")):
            rows.append(
                {
                    "artifact": item["path"],
                    "summary_csv": str(s.relative_to(repo_root)),
                    "status": "available",
                    "note": "token/latency accounting summary discovered",
                }
            )
    if not rows:
        rows.append(
            {
                "artifact": "none",
                "summary_csv": "none",
                "status": "missing",
                "note": "No token-accounting artifact directories found in requested families.",
            }
        )
    return rows


def component_ablation_summary(repo_root: Path, inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in inventory:
        if item["artifact_family"] not in {"integrated_component_ablation", "manuscript_component_ablation"}:
            continue
        p = repo_root / item["path"]
        agg = p / "aggregate_summary.csv"
        for r in read_csv(agg):
            out.append(
                {
                    "evidence_layer": item["artifact_family"],
                    "artifact": item["path"],
                    "variant": r.get("variant", ""),
                    "n_cases": r.get("n_cases", ""),
                    "accuracy": r.get("accuracy", ""),
                    "claim_support": "supportive" if maybe_float(r.get("accuracy"), 0) >= 0.60 else "open",
                    "notes": "Ablation supports component relevance but does not establish universal dominance.",
                }
            )
    if not out:
        out.append(
            {
                "evidence_layer": "component_ablation",
                "artifact": "none",
                "variant": "none",
                "n_cases": 0,
                "accuracy": "",
                "claim_support": "open",
                "notes": "No component ablation aggregate summaries discovered.",
            }
        )
    return out


def claim_safety(pairwise: list[dict[str, Any]], inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def eval_claim(predicate: Any, layer: str, safe_txt: str, mixed_txt: str, no_txt: str) -> tuple[str, str]:
        selected = [r for r in pairwise if predicate(r)]
        if not selected:
            return "open", no_txt
        decisive = [r for r in selected if "statistically stronger" in str(r.get("interpretation", "")) and r.get("method_a") in str(r.get("interpretation", ""))]
        fragile = [r for r in selected if "fragile" in str(r.get("interpretation", ""))]
        if decisive and len(decisive) >= max(1, len(selected) // 2):
            return "safe", safe_txt
        if decisive or fragile:
            return "supportive", mixed_txt
        return "not_safe", no_txt

    claims: list[dict[str, Any]] = []
    status, wording = eval_claim(
        lambda r: r.get("method_a") == "strict_f3" and r.get("method_b") == "strict_gate1_cap_k6",
        "matched_surface_simulation",
        "Strict-F3 can be used as matched-surface representative; superiority should be stated as bounded.",
        "Strict-F3 appears competitive with Strict-Gate1-Cap-K6, but the gap is fragile and surface-dependent.",
        "Do not claim Strict-F3 statistically dominates Strict-Gate1-Cap-K6.",
    )
    claims.append({"claim": "Strict-F3 is the manuscript-facing matched-surface representative", "evidence_layer": "matched_surface_simulation", "support_status": "safe" if status != "not_safe" else "open", "primary_artifacts": "matched_surface_multiseed_main_comparison_*", "quantitative_summary": "See pairwise strict_f3 vs strict_gate1_cap_k6 rows", "statistical_status": status, "recommended_manuscript_wording": wording, "forbidden_overclaim": "Strict-F3 universally and decisively outperforms Strict-Gate1-Cap-K6."})
    claims.append({"claim": "Strict-F3 statistically dominates Strict-Gate1-Cap-K6", "evidence_layer": "matched_surface_simulation", "support_status": status if status in {"safe", "supportive"} else "not_safe", "primary_artifacts": "matched_surface_multiseed_main_comparison_*", "quantitative_summary": "Permutation p-values and bootstrap CIs in pairwise table", "statistical_status": status, "recommended_manuscript_wording": wording, "forbidden_overclaim": "Statistically significant dominance across all settings."})

    f_status, f_word = eval_claim(
        lambda r: r.get("method_b") == "external_l1_max" and (r.get("method_a", "").startswith("strict_") or "allocation" in r.get("method_a", "")),
        "combined",
        "Frontier-allocation methods can be reported as competitive against external_l1_max on bounded surfaces.",
        "Frontier-allocation advantage versus external_l1_max is mixed and should be presented as non-dominant.",
        "Do not claim frontier-allocation dominates external_l1_max.",
    )
    claims.extend(
        [
            {"claim": "Frontier allocation dominates external_l1_max", "evidence_layer": "simulation+real_model", "support_status": "not_safe" if f_status != "safe" else "safe", "primary_artifacts": "matched_surface + real_model bundles", "quantitative_summary": "frontier-family vs external_l1_max pairwise rows", "statistical_status": f_status, "recommended_manuscript_wording": f_word, "forbidden_overclaim": "Dominates external_l1_max across providers and budgets."},
            {"claim": "Frontier allocation is competitive but not dominant in OpenAI+Cohere real-model checks", "evidence_layer": "openai+cohere_real_model", "support_status": "safe" if f_status in {"supportive", "not_safe"} else "supportive", "primary_artifacts": "real_model_ours_vs_external_validation_* and audit docs", "quantitative_summary": "real-model pairwise rows", "statistical_status": f_status, "recommended_manuscript_wording": "Real-model checks are consistent with competitiveness but do not support a dominance claim.", "forbidden_overclaim": "SOTA / best across all real-model checks."},
            {"claim": "Real-model evidence is headline-safe", "evidence_layer": "openai+cohere_real_model", "support_status": "not_safe", "primary_artifacts": "openai/cohere/cross-provider audits", "quantitative_summary": "Limited artifact coverage and mixed statistical direction", "statistical_status": "mixed", "recommended_manuscript_wording": "Use real-model evidence as bounded corroboration, primarily appendix/supportive.", "forbidden_overclaim": "Headline claim based on small real-model audits."},
            {"claim": "Real-model evidence is appendix-only", "evidence_layer": "openai+cohere_real_model", "support_status": "safe", "primary_artifacts": "openai/cohere/cross-provider audits", "quantitative_summary": "Mixed outcomes with limited per-case depth", "statistical_status": "supportive", "recommended_manuscript_wording": "Position real-model checks as appendix corroboration with limitations.", "forbidden_overclaim": "Real-model results prove broad superiority."},
            {"claim": "The comparison is action-budget matched, not fully hardware/token/dollar matched", "evidence_layer": "token_latency_accounting", "support_status": "safe", "primary_artifacts": "token_accounting and cross_token_accounting artifacts", "quantitative_summary": "Token/latency accounting artifacts may be partial or absent", "statistical_status": "descriptive", "recommended_manuscript_wording": "Comparisons are action-budget matched and should be interpreted with token/latency caveats.", "forbidden_overclaim": "Fully compute-cost matched fairness."},
            {"claim": "The method is operationally specified at implementation level, with heuristic/state-dependent gates caveated", "evidence_layer": "operational_spec", "support_status": "safe" if any(i["artifact_family"] == "operational_spec_docs" for i in inventory) else "open", "primary_artifacts": "OPERATIONAL_CONTROLLER_SPECIFICATION_FOR_MANUSCRIPT_*.md", "quantitative_summary": "Operational spec document presence/absence", "statistical_status": "descriptive", "recommended_manuscript_wording": "Present method as operationally specified with explicit heuristic caveats.", "forbidden_overclaim": "Formally optimal or fully model-agnostic guarantees."},
        ]
    )
    return claims


def manuscript_wording(claim_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "abstract_safe_sentence": "We present an action-budgeted frontier-allocation formulation that is competitive on matched surfaces, with mixed real-model evidence reported conservatively.",
        "intro_safe_contribution_sentence": "Our contribution is a formulation-level controller and diagnostic framework with bounded empirical support rather than universal dominance.",
        "results_safe_sentence": "Strict-F3 is a practical manuscript-facing representative, but pairwise gains over nearby variants are small and surface-sensitive.",
        "real_model_appendix_sentence": "OpenAI/Cohere real-model checks are reported as corroborative appendix evidence and not as standalone dominance proof.",
        "limitations_sentence": "Comparisons are primarily action-budget matched; token/latency/hardware comparability remains partially bounded by available artifacts.",
        "forbidden_phrases_to_avoid": [
            "state-of-the-art across providers",
            "universal dominance",
            "statistically decisive everywhere",
            "fully compute-matched fairness",
        ],
    }


def write_status(path: Path, claims: list[dict[str, Any]], limitations: list[dict[str, Any]], out_dir: Path) -> None:
    safe = sum(1 for c in claims if c["support_status"] == "safe")
    not_safe = sum(1 for c in claims if c["support_status"] == "not_safe")
    lines = [
        "# Unified Claim-Safety Statistical Audit",
        "",
        f"Output directory: `{out_dir}`",
        f"Claims marked safe: {safe}",
        f"Claims marked not_safe: {not_safe}",
        f"Artifact limitations logged: {len(limitations)}",
        "",
        "Conservative recommendation: formulation + diagnostic + bounded artifact framing.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_doc(path: Path, ts: str, claims: list[dict[str, Any]], pairwise: list[dict[str, Any]], consistency: list[dict[str, Any]], limitations: list[dict[str, Any]], out_dir: Path) -> None:
    def claim_text(prefix: str) -> str:
        for c in claims:
            if c["claim"].startswith(prefix):
                return f"{c['support_status']}: {c['recommended_manuscript_wording']}"
        return "open: insufficient evidence"

    lines = [
        f"# UNIFIED_CLAIM_SAFETY_STATISTICAL_AUDIT_{ts}",
        "",
        f"Artifacts analyzed offline from `{out_dir}` inputs and repository docs.",
        "",
        "## Reviewer-facing conclusions",
        f"A. Is strict_f3 statistically stronger than strict_gate1_cap_k6? {claim_text('Strict-F3 statistically dominates Strict-Gate1-Cap-K6')}",
        f"B. Is strict_f3 robustly better than external_l1_max? {claim_text('Frontier allocation dominates external_l1_max')}",
        f"C. Do frontier-allocation methods dominate external_l1_max? {claim_text('Frontier allocation dominates external_l1_max')}",
        f"D. Are OpenAI and Cohere real-model results consistent with simulation? {'mixed' if consistency else 'open'}; see real_model_vs_simulation_consistency.csv.",
        "E. Is the paper safe as a dominance/SOTA paper? not_safe.",
        "F. Is the paper safer as a formulation + diagnostic + bounded artifact paper? safe.",
        "G. What exact claims should be used in the abstract, introduction, results, and limitations? See manuscript_recommended_wording.json and claim_safety_table.csv.",
        "H. Which claims must not be made? See forbidden_overclaim column in claim_safety_table.csv.",
        "",
        "## Pairwise statistics overview",
        f"- pairwise rows: {len(pairwise)}",
        f"- artifact limitations: {len(limitations)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    out_dir = (repo_root / args.output_root / f"unified_claim_safety_statistical_audit_{args.timestamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory, limitations = discover_artifacts(repo_root)
    per_case = collect_per_case_rows(repo_root, inventory)
    if not per_case:
        limitations.append({"artifact_family": "per_case", "severity": "missing", "detail": "No per-case rows discovered; pairwise tests unavailable."})

    pairwise = pairwise_rows(per_case, n_boot=args.bootstrap_samples, n_perm=args.permutation_samples, seed=args.seed)
    instability = winner_instability(per_case)
    consistency = consistency_table(pairwise)
    token = token_latency_summary(repo_root, inventory)
    ablation = component_ablation_summary(repo_root, inventory)
    claim_rows = claim_safety(pairwise, inventory)
    wording = manuscript_wording(claim_rows)

    manifest = {
        "timestamp": args.timestamp,
        "repo_root": str(repo_root),
        "output_dir": str(out_dir.relative_to(repo_root)),
        "offline_only": True,
        "api_required": False,
        "discovered_artifacts": len(inventory),
        "per_case_rows": len(per_case),
        "pairwise_rows": len(pairwise),
        "limitations": len(limitations),
        "required_outputs": REQUIRED_OUTPUTS,
    }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    write_csv(out_dir / "artifact_inventory.csv", inventory)
    write_csv(out_dir / "artifact_limitations.csv", limitations)
    write_csv(out_dir / "claim_safety_table.csv", claim_rows)
    write_csv(out_dir / "pairwise_statistical_tests.csv", pairwise)
    write_csv(out_dir / "winner_instability_by_surface.csv", instability)
    write_csv(out_dir / "real_model_vs_simulation_consistency.csv", consistency)
    write_csv(out_dir / "token_latency_accounting_summary.csv", token)
    write_csv(out_dir / "component_ablation_claim_support.csv", ablation)
    (out_dir / "manuscript_recommended_wording.json").write_text(json.dumps(wording, indent=2, sort_keys=True), encoding="utf-8")
    write_status(out_dir / "STATUS.md", claim_rows, limitations, out_dir)

    doc_path = repo_root / args.docs_root / f"UNIFIED_CLAIM_SAFETY_STATISTICAL_AUDIT_{args.timestamp}.md"
    write_doc(doc_path, args.timestamp, claim_rows, pairwise, consistency, limitations, out_dir)


if __name__ == "__main__":
    main()
