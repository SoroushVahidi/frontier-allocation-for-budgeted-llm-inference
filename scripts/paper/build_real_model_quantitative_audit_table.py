#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from paper_data_sources import REPO_ROOT, write_csv, write_tex_table

REQUIRED_COMPARISONS: list[tuple[str, str]] = [
    ("strict_f3_anti_collapse_weak_v1", "external_l1_max"),
    ("strict_f3_anti_collapse_weak_v1", "self_consistency_3"),
    ("strict_f3_anti_collapse_weak_v1", "strict_f3"),
    ("strict_f3", "strict_gate1_cap_k6"),
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _stable_seed(*parts: Any) -> int:
    text = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _bootstrap_ci(diffs: list[float], *, n_boot: int, seed: int) -> tuple[float, float]:
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(diffs)
    draws = [_mean([diffs[rng.randrange(n)] for _ in range(n)]) for _ in range(n_boot)]
    draws.sort()
    return (draws[int(0.025 * n_boot)], draws[min(int(0.975 * n_boot), n_boot - 1)])


def _perm_pvalue(diffs: list[float], *, n_perm: int, seed: int) -> float:
    if not diffs:
        return 1.0
    rng = random.Random(seed)
    obs = abs(_mean(diffs))
    geq = 0
    for _ in range(n_perm):
        signs = [1.0 if rng.random() < 0.5 else -1.0 for _ in diffs]
        stat = abs(_mean([d * s for d, s in zip(diffs, signs)]))
        if stat >= obs - 1e-12:
            geq += 1
    return float((geq + 1.0) / (n_perm + 1.0))


def _discover_real_model_sources() -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    for run_dir in sorted((REPO_ROOT / "outputs").glob("real_model_ours_vs_external_validation_*")):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        provider_status = manifest.get("provider_status", {}) if isinstance(manifest, dict) else {}
        for provider_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
            per_example = provider_dir / "per_example_rows.csv"
            if not per_example.exists() or per_example.stat().st_size == 0:
                continue
            rows = _read_csv(per_example)
            if not rows:
                continue
            provider = str(rows[0].get("provider", provider_dir.name))
            status = provider_status.get(provider, {}) if isinstance(provider_status, dict) else {}
            if status and (not bool(status.get("attempted", True)) or not bool(status.get("completed", True))):
                continue
            discovered.append(
                {
                    "run_dir": run_dir,
                    "provider_dir": provider_dir,
                    "provider": provider,
                    "model": str(rows[0].get("model", status.get("model", ""))),
                    "rows": rows,
                }
            )
    # Keep the largest completed source per (provider, model) to avoid mixing
    # main runs with smoke/drycheck fragments in paper-facing aggregates.
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for src in discovered:
        key = (src["provider"], src["model"])
        prev = best.get(key)
        if prev is None or len(src["rows"]) > len(prev["rows"]):
            best[key] = src
    return sorted(best.values(), key=lambda x: (x["provider"], x["model"], str(x["run_dir"])))


def _pairwise_tests(rows: list[dict[str, str]], comparisons: list[tuple[str, str]], *, scope: str) -> list[dict[str, Any]]:
    idx = {
        (
            str(r.get("provider", "")),
            str(r.get("model", "")),
            str(r.get("dataset", "")),
            str(r.get("budget", "")),
            str(r.get("seed", "")),
            str(r.get("example_id", "")),
            str(r.get("method", "")),
        ): int(float(r.get("is_correct", 0)))
        for r in rows
    }
    all_methods = {str(r.get("method", "")) for r in rows}
    out: list[dict[str, Any]] = []
    for a, b in comparisons:
        if a not in all_methods or b not in all_methods:
            out.append(
                {
                    "scope": scope,
                    "method_a": a,
                    "method_b": b,
                    "n_paired": 0,
                    "accuracy_a": "",
                    "accuracy_b": "",
                    "mean_difference": "",
                    "bootstrap_ci_low": "",
                    "bootstrap_ci_high": "",
                    "permutation_p_value": "",
                    "status": "unavailable_in_artifacts",
                }
            )
            continue
        diffs: list[float] = []
        a_vals: list[float] = []
        b_vals: list[float] = []
        for provider, model, dataset, budget, seed, exid, method in list(idx.keys()):
            if method != a:
                continue
            kb = (provider, model, dataset, budget, seed, exid, b)
            if kb not in idx:
                continue
            av = idx[(provider, model, dataset, budget, seed, exid, a)]
            bv = idx[kb]
            diffs.append(float(av - bv))
            a_vals.append(float(av))
            b_vals.append(float(bv))
        if not diffs:
            out.append(
                {
                    "scope": scope,
                    "method_a": a,
                    "method_b": b,
                    "n_paired": 0,
                    "accuracy_a": "",
                    "accuracy_b": "",
                    "mean_difference": "",
                    "bootstrap_ci_low": "",
                    "bootstrap_ci_high": "",
                    "permutation_p_value": "",
                    "status": "no_paired_cases",
                }
            )
            continue
        ci_low, ci_high = _bootstrap_ci(diffs, n_boot=3000, seed=_stable_seed(scope, a, b, "boot"))
        p = _perm_pvalue(diffs, n_perm=3000, seed=_stable_seed(scope, a, b, "perm"))
        out.append(
            {
                "scope": scope,
                "method_a": a,
                "method_b": b,
                "n_paired": len(diffs),
                "accuracy_a": _mean(a_vals),
                "accuracy_b": _mean(b_vals),
                "mean_difference": _mean(diffs),
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "permutation_p_value": p,
                "status": "ok",
            }
        )
    return out


def _interpret_pairwise(row: dict[str, Any]) -> str:
    if row.get("status") != "ok":
        return "not_available"
    p = float(row.get("permutation_p_value", 1.0))
    lo = float(row.get("bootstrap_ci_low", 0.0))
    hi = float(row.get("bootstrap_ci_high", 0.0))
    delta = float(row.get("mean_difference", 0.0))
    if p < 0.05 and lo > 0 and delta > 0:
        return "supports_competitiveness"
    if p < 0.05 and hi < 0 and delta < 0:
        return "evidence_against_target_method"
    return "mixed_or_insufficient"


def main() -> None:
    p = argparse.ArgumentParser(description="Build paper-facing quantitative real-model audit table from existing artifacts.")
    p.add_argument(
        "--output-csv",
        type=Path,
        default=REPO_ROOT / "outputs" / "paper_tables" / "table_real_model_quantitative_audit.csv",
    )
    p.add_argument(
        "--output-tex",
        type=Path,
        default=REPO_ROOT / "outputs" / "paper_tables" / "table_real_model_quantitative_audit.tex",
    )
    p.add_argument(
        "--output-plot-csv",
        type=Path,
        default=REPO_ROOT / "outputs" / "paper_plot_data" / "real_model_quantitative_audit.csv",
    )
    p.add_argument(
        "--output-pairwise-csv",
        type=Path,
        default=REPO_ROOT / "outputs" / "paper_tables" / "table_real_model_quantitative_audit_pairwise.csv",
    )
    args = p.parse_args()

    sources = _discover_real_model_sources()
    if not sources:
        raise FileNotFoundError("No usable real-model outputs found under outputs/real_model_ours_vs_external_validation_*")

    all_rows: list[dict[str, str]] = []
    for src in sources:
        all_rows.extend(src["rows"])

    grouped: dict[tuple[str, str, str, int, str], list[dict[str, str]]] = defaultdict(list)
    for r in all_rows:
        grouped[
            (
                str(r.get("provider", "")),
                str(r.get("model", "")),
                str(r.get("dataset", "")),
                int(float(r.get("budget", 0))),
                str(r.get("method", "")),
            )
        ].append(r)

    pairwise_all = _pairwise_tests(all_rows, REQUIRED_COMPARISONS, scope="all_providers")
    pairwise_by_provider: list[dict[str, Any]] = []
    provider_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for r in all_rows:
        provider_groups[(str(r.get("provider", "")), str(r.get("model", "")))].append(r)
    for (provider, model), rows in sorted(provider_groups.items()):
        pairwise_by_provider.extend(_pairwise_tests(rows, REQUIRED_COMPARISONS, scope=f"{provider}:{model}"))
    pairwise = pairwise_all + pairwise_by_provider
    write_csv(args.output_pairwise_csv, pairwise)

    pair_lookup = {(str(r["scope"]), str(r["method_a"]), str(r["method_b"])): r for r in pairwise}
    key_pair = pair_lookup.get(("all_providers", "strict_f3", "strict_gate1_cap_k6"), {})
    key_pair_text = (
        f"strict_f3-strict_gate1_cap_k6={float(key_pair.get('mean_difference', 0.0)):+.4f}"
        if key_pair and key_pair.get("status") == "ok"
        else "strict_f3_vs_gate1_unavailable"
    )
    key_interp = _interpret_pairwise(key_pair) if key_pair else "not_available"

    table_rows: list[dict[str, Any]] = []
    for (provider, model, dataset, budget, method), vals in sorted(grouped.items()):
        acc = _mean([float(v.get("is_correct", 0)) for v in vals])
        ci_low, ci_high = _bootstrap_ci(
            [float(v.get("is_correct", 0)) for v in vals],
            n_boot=2000,
            seed=_stable_seed(provider, model, dataset, budget, method, "acc_ci"),
        )
        table_rows.append(
            {
                "provider": provider,
                "model": model,
                "dataset": dataset,
                "budget": budget,
                "method": method,
                "paired_n": len(vals),
                "accuracy": round(acc, 6),
                "confidence_interval": f"[{round(ci_low, 6)}, {round(ci_high, 6)}]",
                "mean_actions": round(_mean([float(v.get("actions_used", 0)) for v in vals]), 6),
                "mean_expansions": round(_mean([float(v.get("expansions", 0)) for v in vals]), 6),
                "mean_verifications": round(_mean([float(v.get("verifications", 0)) for v in vals]), 6),
                "key_pairwise_comparison": key_pair_text,
                "bootstrap_ci_pairwise": (
                    f"[{round(float(key_pair.get('bootstrap_ci_low', 0.0)), 6)}, {round(float(key_pair.get('bootstrap_ci_high', 0.0)), 6)}]"
                    if key_pair and key_pair.get("status") == "ok"
                    else ""
                ),
                "permutation_p_value_pairwise": (
                    round(float(key_pair.get("permutation_p_value", 1.0)), 6)
                    if key_pair and key_pair.get("status") == "ok"
                    else ""
                ),
                "interpretation": key_interp,
            }
        )

    write_csv(args.output_csv, table_rows)
    write_tex_table(args.output_tex, table_rows)
    write_csv(args.output_plot_csv, table_rows)

    source_rows = [
        {
            "run_dir": str(src["run_dir"].relative_to(REPO_ROOT)),
            "provider": src["provider"],
            "model": src["model"],
            "n_rows": len(src["rows"]),
        }
        for src in sources
    ]
    write_csv(REPO_ROOT / "outputs" / "paper_tables" / "table_real_model_quantitative_audit_sources.csv", source_rows)
    print(
        json.dumps(
            {
                "status": "ok",
                "sources_used": source_rows,
                "output_csv": str(args.output_csv.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
