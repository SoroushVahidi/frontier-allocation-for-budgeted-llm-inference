#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from paper_data_sources import REPO_ROOT, write_csv, write_tex_table

REQUIRED_COMPARISONS = [
    ("strict_f3", "strict_gate1_cap_k6"),
    ("strict_f3", "external_l1_max"),
    ("strict_gate1_cap_k6", "external_l1_max"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build paper-facing claim-safety statistical tests table.")
    p.add_argument(
        "--pairwise-input",
        type=Path,
        default=None,
        help="Path to pairwise_statistical_tests.csv. Defaults to latest unified claim-safety audit run.",
    )
    p.add_argument(
        "--output-csv",
        type=Path,
        default=REPO_ROOT / "outputs" / "paper_tables" / "table_claim_safety_statistical_tests.csv",
    )
    p.add_argument(
        "--output-tex",
        type=Path,
        default=REPO_ROOT / "outputs" / "paper_tables" / "table_claim_safety_statistical_tests.tex",
    )
    p.add_argument(
        "--output-plot-csv",
        type=Path,
        default=REPO_ROOT / "outputs" / "paper_plot_data" / "claim_safety_statistical_tests.csv",
    )
    p.add_argument(
        "--include-supportive-real-model",
        action="store_true",
        help="Include non-matched-surface (real-model) rows as appendix/supportive rows.",
    )
    return p.parse_args()


def _read_csv(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _latest_pairwise_input() -> Path:
    candidates = sorted((REPO_ROOT / "outputs").glob("unified_claim_safety_statistical_audit_*/pairwise_statistical_tests.csv"))
    if not candidates:
        raise FileNotFoundError("No unified claim-safety pairwise_statistical_tests.csv found in outputs/.")
    return candidates[-1]


def _normalize_pair(method_a: str, method_b: str) -> tuple[str, str] | None:
    for a, b in REQUIRED_COMPARISONS:
        if (method_a, method_b) == (a, b) or (method_a, method_b) == (b, a):
            return (a, b)
    return None


def _build_interpretation(row: dict[str, Any]) -> str:
    method_a = str(row["method A"])
    method_b = str(row["method B"])
    mean_diff = float(row["mean difference"])
    ci_low = float(row["bootstrap CI low"])
    ci_high = float(row["bootstrap CI high"])
    p_value = float(row["permutation p-value"])

    decisive = p_value < 0.05 and ((ci_low > 0.0) or (ci_high < 0.0))
    is_internal_top_pair = {method_a, method_b} == {"strict_f3", "strict_gate1_cap_k6"}

    if not decisive:
        if is_internal_top_pair:
            return "fragile / not statistically decisive; leading frontier-allocation variants form a close top cluster"
        return "difference not statistically decisive on this matched surface slice"

    if is_internal_top_pair:
        return "statistically distinguishable on this slice, but winner remains surface-dependent (not universal)"

    stronger = method_a if mean_diff >= 0 else method_b
    return f"{stronger} statistically stronger on this matched-surface slice (budget/dataset-specific)"


def _orient_row(source: dict[str, str], target_a: str, target_b: str) -> dict[str, Any]:
    row_a = str(source.get("method_a", "")).strip()
    row_b = str(source.get("method_b", "")).strip()
    same_orientation = (row_a, row_b) == (target_a, target_b)

    acc_a = _to_float(source.get("accuracy_a"))
    acc_b = _to_float(source.get("accuracy_b"))
    mean_diff = _to_float(source.get("mean_difference"))
    ci_low = _to_float(source.get("bootstrap_ci_low"))
    ci_high = _to_float(source.get("bootstrap_ci_high"))
    wins = _to_int(source.get("win_count"))
    losses = _to_int(source.get("loss_count"))

    if not same_orientation:
        acc_a, acc_b = acc_b, acc_a
        mean_diff = -mean_diff
        ci_low, ci_high = -ci_high, -ci_low
        wins, losses = losses, wins

    evidence_layer = str(source.get("evidence_layer", ""))
    section = "main_matched_surface" if evidence_layer == "matched_surface_simulation" else "appendix_supportive_real_model"

    out = {
        "paper section": section,
        "evidence layer": evidence_layer,
        "dataset": str(source.get("dataset", "")),
        "budget": _to_int(source.get("budget")),
        "method A": target_a,
        "method B": target_b,
        "paired n": _to_int(source.get("n_paired")),
        "accuracy A": round(acc_a, 6),
        "accuracy B": round(acc_b, 6),
        "mean difference": round(mean_diff, 6),
        "bootstrap CI low": round(ci_low, 6),
        "bootstrap CI high": round(ci_high, 6),
        "permutation p-value": round(_to_float(source.get("permutation_p_value")), 6),
        "interpretation": "",
    }
    out["interpretation"] = _build_interpretation(out)
    return out


def _deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        key = (
            r["paper section"],
            r["evidence layer"],
            r["dataset"],
            r["budget"],
            r["method A"],
            r["method B"],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build_table_rows(pairwise_rows: list[dict[str, str]], include_supportive_real_model: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for src in pairwise_rows:
        if str(src.get("comparison_rule", "")).strip() != "required":
            continue
        pair = _normalize_pair(str(src.get("method_a", "")).strip(), str(src.get("method_b", "")).strip())
        if pair is None:
            continue

        evidence_layer = str(src.get("evidence_layer", "")).strip()
        if evidence_layer == "matched_surface_simulation":
            out.append(_orient_row(src, pair[0], pair[1]))
            continue
        if include_supportive_real_model:
            out.append(_orient_row(src, pair[0], pair[1]))

    out = _deduplicate(out)
    out.sort(key=lambda r: (r["paper section"], r["dataset"], int(r["budget"]), r["method A"], r["method B"]))
    if not out:
        raise ValueError("No paper-facing claim-safety statistical rows found after filtering.")
    return out


def main() -> None:
    args = parse_args()
    pairwise_path = args.pairwise_input or _latest_pairwise_input()
    rows = _read_csv(pairwise_path)
    table_rows = build_table_rows(rows, include_supportive_real_model=args.include_supportive_real_model)

    write_csv(args.output_csv, table_rows)
    write_tex_table(args.output_tex, table_rows)
    write_csv(args.output_plot_csv, table_rows)

    def _show(path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)

    print(f"Built claim-safety paper table from: {_show(pairwise_path)}")
    print(f"- {_show(args.output_csv)}")
    print(f"- {_show(args.output_tex)}")
    print(f"- {_show(args.output_plot_csv)}")


if __name__ == "__main__":
    main()
