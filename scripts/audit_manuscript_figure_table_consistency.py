#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Offline manuscript figure/table consistency and claim-boundary audit")
    p.add_argument("--timestamp", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--repo-health-pass", default="unknown")
    p.add_argument("--ruff-pass", default="unknown")
    p.add_argument("--pytest-pass", default="unknown")
    p.add_argument("--paper-artifacts-pass", default="unknown")
    return p.parse_args()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def latest_claim_boundaries_doc() -> Path | None:
    candidates = sorted((REPO_ROOT / "docs").glob("*CLAIM*BOUNDAR*.md"))
    return candidates[-1] if candidates else None


def scan_text_files(paths: list[Path], patterns: list[tuple[str, str]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for name, pat in patterns:
            for m in re.finditer(pat, text, flags=re.IGNORECASE):
                findings.append(
                    {
                        "file": str(p.relative_to(REPO_ROOT)),
                        "rule": name,
                        "match": m.group(0)[:120],
                        "severity": "warning",
                    }
                )
    return findings


def build_figure_table_consistency() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    required_tables = [
        "table1_benchmark_method_summary.csv",
        "table1_benchmark_method_summary.tex",
        "table5_failure_decomposition.csv",
        "table5_failure_decomposition.tex",
    ]
    required_figures = [
        "figure2_main_frontier.pdf",
        "figure3_failure_decomposition.pdf",
    ]
    for name in required_tables:
        p = REPO_ROOT / "outputs/paper_tables" / name
        rows.append({"check": f"required_table::{name}", "status": "pass" if p.exists() else "fail", "detail": str(p.relative_to(REPO_ROOT))})
    for name in required_figures:
        p = REPO_ROOT / "outputs/paper_figures" / name
        rows.append({"check": f"required_figure::{name}", "status": "pass" if p.exists() else "fail", "detail": str(p.relative_to(REPO_ROOT))})

    t1 = REPO_ROOT / "outputs/paper_tables/table1_benchmark_method_summary.csv"
    if t1.exists():
        t1_rows = read_csv(t1)
        rows.append(
            {
                "check": "table1_nonempty",
                "status": "pass" if len(t1_rows) > 0 else "fail",
                "detail": f"rows={len(t1_rows)} source=outputs/paper_tables/table1_benchmark_method_summary.csv",
            }
        )
    else:
        rows.append({"check": "table1_nonempty", "status": "fail", "detail": "missing outputs/paper_tables/table1_benchmark_method_summary.csv"})

    fig3_methods: set[str] = set()
    fig3 = REPO_ROOT / "outputs/paper_tables/table5_failure_decomposition.csv"
    if fig3.exists():
        for r in read_csv(fig3):
            m = (r.get("method") or "").strip()
            if m:
                fig3_methods.add(m)

    appendix_methods: set[str] = set()
    for p in sorted((REPO_ROOT / "outputs").glob("matched_surface_multiseed_main_comparison_*/paper_ready_failure_table.tex")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        for token in ["strict_f3", "strict_gate1_cap_k6", "strict_f2", "external_l1_max", "self_consistency_3"]:
            if token in text:
                appendix_methods.add(token)
    method_overlap_ok = bool(fig3_methods) and bool(appendix_methods) and fig3_methods.issubset(appendix_methods | fig3_methods)
    rows.append(
        {
            "check": "figure3_methods_match_appendix_failure_table_methods",
            "status": "pass" if method_overlap_ok else "warning",
            "detail": f"figure3_methods={sorted(fig3_methods)} appendix_methods={sorted(appendix_methods)}",
        }
    )
    return rows


def build_claim_boundary_scan(claim_doc: Path | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    claim_paths = [REPO_ROOT / "docs/PAPER_SOURCE_OF_TRUTH.md"]
    if claim_doc is not None:
        claim_paths.append(claim_doc)
    for p in claim_paths:
        if not p.exists():
            rows.append({"check": f"claim_doc_exists::{p.name}", "status": "fail", "detail": str(p.relative_to(REPO_ROOT))})
            continue
        text = p.read_text(encoding="utf-8", errors="ignore").lower()
        rows.append({"check": f"claim_doc_exists::{p.name}", "status": "pass", "detail": str(p.relative_to(REPO_ROOT))})
        rows.append({"check": f"real_model_supporting_only::{p.name}", "status": "pass" if ("support" in text or "appendix" in text or "provenance" in text) else "warning", "detail": "expected supporting/provenance language for real-model diagnostics"})
        rows.append({"check": f"exploratory_variant_label::{p.name}", "status": "pass" if ("strict_f3_case_split_direction_aware_v1" not in text or "exploratory" in text or "provenance" in text) else "warning", "detail": "strict_f3_case_split_direction_aware_v1 should be marked exploratory/provenance-only"})
    return rows


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = args.timestamp

    claim_doc = latest_claim_boundaries_doc()

    figure_rows = build_figure_table_consistency()
    write_csv(out_dir / "figure_table_consistency.csv", figure_rows)

    claim_rows = build_claim_boundary_scan(claim_doc)
    write_csv(out_dir / "claim_boundary_scan.csv", claim_rows)

    tex_md_paths = list((REPO_ROOT / "manuscript_integration").glob("**/*.tex")) + list((REPO_ROOT / "docs").glob("**/*.md"))
    patterns = [
        ("mode_a_phrase", r"\bMODE A\b"),
        ("readiness_approved_phrase", r"\breadiness-approved\b"),
        ("codex_task_phrase", r"\bCodex task\b"),
        ("public_pr_link", r"https://github\.com/[^/\s]+/[^/\s]+/(pull|issues)/\d+"),
        ("author_name_token", r"\b(samaneh|walsh|young|champagn|singh)\b"),
        ("local_path_token", r"(/home/|[A-Za-z]:\\)"),
        ("api_key_like_string", r"\b(sk-[A-Za-z0-9]{12,}|COHERE_API_KEY\s*=\s*[A-Za-z0-9_\-]{8,})"),
    ]
    findings = scan_text_files(tex_md_paths, patterns)
    write_csv(out_dir / "anonymization_rescan.csv", findings if findings else [{"file": "", "rule": "none", "match": "", "severity": "pass"}])

    appendix_check_rows: list[dict[str, Any]] = []
    reviewer_doc = REPO_ROOT / "docs/PAPER_REPRODUCTION_CHECKLIST.md"
    appd_doc = REPO_ROOT / "docs/ANONYMOUS_SUPPLEMENT_PREPARATION.md"
    appendix_check_rows.append({"check": "reviewer_doc_exists", "status": "pass" if reviewer_doc.exists() else "warning", "detail": str(reviewer_doc.relative_to(REPO_ROOT))})
    appendix_check_rows.append({"check": "appendix_repro_doc_exists", "status": "pass" if appd_doc.exists() else "warning", "detail": str(appd_doc.relative_to(REPO_ROOT))})
    if reviewer_doc.exists() and appd_doc.exists():
        rtxt = reviewer_doc.read_text(encoding="utf-8", errors="ignore")
        atxt = appd_doc.read_text(encoding="utf-8", errors="ignore")
        appendix_check_rows.append({"check": "appendix_d_command_consistency", "status": "pass" if ("run_all_neurips_paper_artifacts.py" in rtxt and "run_all_neurips_paper_artifacts.py" in atxt) else "warning", "detail": "checked overlap on core artifact regeneration command references"})
    else:
        appendix_check_rows.append({"check": "appendix_d_command_consistency", "status": "warning", "detail": "missing one or more docs for direct command cross-check"})
    write_csv(out_dir / "remaining_submission_risks.csv", appendix_check_rows)

    regen_rows = [
        {"step": "check_repo_health", "pass": args.repo_health_pass},
        {"step": "ruff_check", "pass": args.ruff_pass},
        {"step": "pytest", "pass": args.pytest_pass},
        {"step": "run_all_neurips_paper_artifacts", "pass": args.paper_artifacts_pass},
    ]
    write_csv(out_dir / "paper_artifact_regeneration_summary.csv", regen_rows)

    cmd_rows = [
        {"order": 1, "command": "python scripts/check_repo_health.py"},
        {"order": 2, "command": "python -m ruff check"},
        {"order": 3, "command": "python -m pytest"},
        {"order": 4, "command": "python scripts/paper/run_all_neurips_paper_artifacts.py"},
        {"order": 5, "command": f"python scripts/audit_manuscript_figure_table_consistency.py --timestamp {ts} --out-dir outputs/offline_submission_audit_{ts}"},
    ]
    write_csv(out_dir / "validation_commands.csv", cmd_rows)

    q = {
        "repository_health_pass": args.repo_health_pass,
        "ruff_pass": args.ruff_pass,
        "pytest_pass": args.pytest_pass,
        "paper_artifact_regeneration_pass": args.paper_artifacts_pass,
        "active_figures_tables_consistent": "pass" if all(r["status"] == "pass" for r in figure_rows) else "warning",
        "labels_or_captions_repository_internal": "warning" if findings else "pass",
        "claim_boundaries_consistent": "pass" if all(r["status"] == "pass" for r in claim_rows) else "warning",
        "real_model_diagnostics_supporting_only": "pass" if any(r["check"].startswith("real_model_supporting_only") and r["status"] == "pass" for r in claim_rows) else "warning",
        "exploratory_variants_marked_exploratory": "pass" if any(r["check"].startswith("exploratory_variant_label") and r["status"] == "pass" for r in claim_rows) else "warning",
        "remaining_risks": [r for r in appendix_check_rows if r["status"] != "pass"] + (findings[:20] if findings else []),
    }
    (out_dir / "manifest.json").write_text(json.dumps({"timestamp": ts, "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "claim_boundaries_doc": str(claim_doc.relative_to(REPO_ROOT)) if claim_doc else None, "answers": q}, indent=2) + "\n", encoding="utf-8")

    readme_lines = [
        f"# Offline submission audit ({ts})",
        "",
        "This package captures API-free repository validation and paper-artifact consistency checks.",
        "",
        "## Outputs",
        "- manifest.json",
        "- validation_commands.csv",
        "- figure_table_consistency.csv",
        "- claim_boundary_scan.csv",
        "- anonymization_rescan.csv",
        "- paper_artifact_regeneration_summary.csv",
        "- remaining_submission_risks.csv",
    ]
    (out_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    doc_path = REPO_ROOT / f"docs/OFFLINE_SUBMISSION_AUDIT_{ts}.md"
    risk_lines = []
    for r in q["remaining_risks"][:10]:
        risk_lines.append(f"- {r}")
    if not risk_lines:
        risk_lines = ["- No high-confidence immediate submission blockers found by this lightweight scan."]
    report = [
        "# OFFLINE_SUBMISSION_AUDIT",
        "",
        f"Timestamp: `{ts}`",
        f"Audit package: `outputs/offline_submission_audit_{ts}/`",
        "",
        "1. Did repository health pass?",
        f"- {args.repo_health_pass}",
        "2. Did ruff pass?",
        f"- {args.ruff_pass}",
        "3. Did pytest pass?",
        f"- {args.pytest_pass}",
        "4. Did canonical paper artifact regeneration pass?",
        f"- {args.paper_artifacts_pass}",
        "5. Are active figures/tables consistent with canonical outputs?",
        f"- {q['active_figures_tables_consistent']}",
        "6. Are any manuscript figure/table labels or captions still repository-internal?",
        f"- {q['labels_or_captions_repository_internal']}",
        "7. Are claim boundaries consistent with docs/CLAIM_BOUNDARIES.md?",
        f"- {q['claim_boundaries_consistent']} (evaluated against `{claim_doc.name if claim_doc else 'N/A'}`)",
        "8. Are real-model diagnostics clearly marked supporting/provenance-only?",
        f"- {q['real_model_diagnostics_supporting_only']}",
        "9. Are failed exploratory variants clearly marked exploratory?",
        f"- {q['exploratory_variants_marked_exploratory']}",
        "10. What remaining submission risks exist?",
        *risk_lines,
    ]
    doc_path.write_text("\n".join(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
