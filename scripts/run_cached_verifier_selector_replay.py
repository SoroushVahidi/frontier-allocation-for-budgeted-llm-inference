#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class MarginRow:
    tau: float
    cases_evaluated_ambiguous_60: int
    trigger_count_ambiguous: int
    fixes_vs_guarded: int
    breaks_vs_guarded: int
    net_fixes: int
    exact_accuracy_all_100_offline: float | None
    exact_accuracy_ambiguous_60_offline: float | None
    gold_present_but_wrong_remaining_offline: int | None


def _norm(x: object) -> str:
    return str(x or "").strip()


def _parse_margins(s: str) -> list[float]:
    parts = [p.strip() for p in (s or "").split(",") if p.strip() != ""]
    if not parts:
        raise SystemExit("--margin must be a float or comma-separated floats")
    out: list[float] = []
    for p in parts:
        try:
            out.append(float(p))
        except ValueError as exc:
            raise SystemExit(f"Invalid margin value: {p}") from exc
    return out


def load_guarded_diag(candidate_diagnostics_csv: Path, method: str) -> dict[str, dict[str, str]]:
    if method != "guarded":
        raise SystemExit("--method currently supports only: guarded")
    out: dict[str, dict[str, str]] = {}
    with candidate_diagnostics_csv.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("method") == method:
                out[str(r["case_id"])] = r
    if not out:
        raise SystemExit(f"No rows found for method={method} in {candidate_diagnostics_csv}")
    return out


def load_per_case(per_case_results_csv: Path) -> dict[str, dict[str, str]]:
    with per_case_results_csv.open(newline="", encoding="utf-8") as f:
        return {str(r["case_id"]): r for r in csv.DictReader(f)}


def load_scores(verifier_scores_jsonl: Path) -> tuple[dict[tuple[str, str], float], dict[str, list[str]]]:
    """
    Load cached scores from ambiguous136-style verifier_scores.jsonl:
      {"plan_id":..., "parse_ok": bool, "support_score": float, "payload": {...}}
    Returns:
      score_by_case_answer: (case_id, normalized_answer) -> max support_score
      debug: case_id -> list[plan_id] for rows that were missing/unusable
    """
    score_by_case_answer: dict[tuple[str, str], float] = {}
    debug: dict[str, list[str]] = {}
    with verifier_scores_jsonl.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            plan_id = str(r.get("plan_id") or "")
            ok = bool(r.get("parse_ok"))
            s = r.get("support_score")
            payload = r.get("payload") or {}
            case_id = str(payload.get("case_id") or "")
            ans = str(payload.get("normalized_answer") or payload.get("final_answer") or "")

            # Fall back to plan_id structure if payload lacks ids (should not happen in pilot).
            if (not case_id or not ans) and plan_id:
                parts = plan_id.split("::")
                if len(parts) >= 2:
                    # plan_id looks like: case_id::normalized_answer_group
                    # but case_id itself contains '::', so we recover by last segment as answer.
                    ans = ans or parts[-1]
                    case_id = case_id or "::".join(parts[:-1])

            case_id = _norm(case_id)
            ans = _norm(ans)
            if not case_id or not ans or (not ok) or s is None:
                if case_id:
                    debug.setdefault(case_id, []).append(plan_id)
                continue
            try:
                sv = float(s)
            except (TypeError, ValueError):
                debug.setdefault(case_id, []).append(plan_id)
                continue

            key = (case_id, ans)
            prev = score_by_case_answer.get(key)
            if prev is None or sv > prev:
                score_by_case_answer[key] = sv
    return score_by_case_answer, debug


def best_challenger(incumbent: str, score_by_answer: dict[str, float]) -> tuple[str | None, float | None]:
    inc = _norm(incumbent)
    cands = [(a, float(s)) for a, s in score_by_answer.items() if _norm(a) != inc]
    if not cands:
        return None, None
    max_s = max(s for _, s in cands)
    tie = sorted(a for a, s in cands if abs(s - max_s) <= 1e-12)
    return (tie[0], max_s) if tie else (None, None)


def predict_one_case(
    *,
    case_id: str,
    incumbent: str,
    score_by_answer: dict[str, float],
    tau: float,
) -> tuple[str, bool, str]:
    """
    Return: (prediction, switched, reason)
    - If incumbent score missing: keep incumbent and return reason.
    """
    inc = _norm(incumbent)
    s_inc = score_by_answer.get(inc)
    if s_inc is None:
        return inc, False, "missing_incumbent_score_kept_incumbent"
    ca, s_ch = best_challenger(inc, score_by_answer)
    if ca is None or s_ch is None:
        return inc, False, "no_scored_challenger_kept_incumbent"
    if (s_ch - s_inc) >= tau - 1e-12:
        return _norm(ca), True, "override_margin_met"
    return inc, False, "blocked_insufficient_margin"


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline replay of a verifier selector using cached verifier_scores.jsonl (no API calls).")
    ap.add_argument("--per-case-results", required=True)
    ap.add_argument("--candidate-diagnostics", required=True)
    ap.add_argument("--verifier-scores", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--margin", required=True, help="float or comma-separated floats (sweep)")
    ap.add_argument("--method", required=True, choices=["guarded"])
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    margins = _parse_margins(args.margin)
    diag = load_guarded_diag(Path(args.candidate_diagnostics), args.method)
    per_case = load_per_case(Path(args.per_case_results))
    score_by_case_answer, _ = load_scores(Path(args.verifier_scores))

    all_cases = sorted(diag.keys())
    gold_by_case = {cid: _norm(diag[cid].get("effective_gold_for_eval")) for cid in all_cases}
    inc_by_case = {cid: _norm(diag[cid].get("normalized_prediction")) for cid in all_cases}
    ambiguous_set = {cid for cid in all_cases if int(float(diag[cid].get("distinct_normalized_candidate_count") or 0)) >= 2}

    def eval_row_for_tau(tau: float) -> tuple[MarginRow, list[dict[str, object]]]:
        triggers = fixes = breaks = 0
        correct_100 = correct_amb = 0
        gp_wrong_remain = 0

        casebook_rows: list[dict[str, object]] = []

        for cid in all_cases:
            gold = gold_by_case[cid]
            inc = inc_by_case[cid]
            sb: dict[str, float] = {}
            for (c2, ans), sc in score_by_case_answer.items():
                if c2 == cid:
                    sb[_norm(ans)] = float(sc)

            if cid in ambiguous_set:
                pred, switched, reason = predict_one_case(case_id=cid, incumbent=inc, score_by_answer=sb, tau=tau)
            else:
                pred, switched, reason = inc, False, "not_ambiguous_kept_incumbent"

            if switched and cid in ambiguous_set:
                triggers += 1

            inc_ok = _norm(inc) == _norm(gold)
            pr_ok = _norm(pred) == _norm(gold)
            if pr_ok:
                correct_100 += 1
                if cid in ambiguous_set:
                    correct_amb += 1

            # Gold-present-but-wrong remaining: use per_case_results guard flag if available.
            pr = per_case.get(cid, {})
            gp = str(pr.get("guarded_gold_present", "")).lower()
            if gp == "yes" and not pr_ok:
                gp_wrong_remain += 1

            if (not inc_ok) and pr_ok:
                fixes += 1
            if inc_ok and (not pr_ok):
                breaks += 1

            casebook_rows.append(
                {
                    "case_id": cid,
                    "example_id": diag[cid].get("example_id", ""),
                    "ambiguous_case": "yes" if cid in ambiguous_set else "no",
                    "distinct_normalized_candidate_count": diag[cid].get("distinct_normalized_candidate_count", ""),
                    "guarded_incumbent": inc,
                    "verifier_pred": pred,
                    "switched": "yes" if switched else "no",
                    "decision_reason": reason,
                    "incumbent_support_score": sb.get(inc, ""),
                    "verifier_pred_support_score": sb.get(pred, ""),
                    "gold_offline_eval_only": gold,
                    "incumbent_exact_offline": "yes" if inc_ok else "no",
                    "verifier_exact_offline": "yes" if pr_ok else "no",
                }
            )

        amb_cases = sorted(ambiguous_set)
        n_amb = len(amb_cases)
        row = MarginRow(
            tau=tau,
            cases_evaluated_ambiguous_60=n_amb,
            trigger_count_ambiguous=triggers,
            fixes_vs_guarded=fixes,
            breaks_vs_guarded=breaks,
            net_fixes=fixes - breaks,
            exact_accuracy_all_100_offline=correct_100 / float(len(all_cases)) if all_cases else None,
            exact_accuracy_ambiguous_60_offline=(correct_amb / float(n_amb)) if n_amb else None,
            gold_present_but_wrong_remaining_offline=gp_wrong_remain if per_case else None,
        )
        return row, casebook_rows

    margin_rows: list[dict[str, object]] = []
    # For usability: write per-margin casebook only when a single margin requested.
    casebook_to_write: list[dict[str, object]] | None = None
    summary_for_margin: dict[str, object] | None = None

    for tau in margins:
        row, casebook_rows = eval_row_for_tau(tau)
        margin_rows.append(row.__dict__)
        if len(margins) == 1:
            casebook_to_write = casebook_rows
            summary_for_margin = row.__dict__

    # Baseline
    baseline_correct = sum(1 for cid in all_cases if _norm(inc_by_case[cid]) == _norm(gold_by_case[cid]))
    baseline_acc = baseline_correct / float(len(all_cases)) if all_cases else None

    # Best margins
    best_by_net = max(margin_rows, key=lambda r: (int(r["net_fixes"]), float(r["exact_accuracy_all_100_offline"] or 0.0)))
    min_breaks = min(int(r["breaks_vs_guarded"]) for r in margin_rows)
    best_low_break = max([r for r in margin_rows if int(r["breaks_vs_guarded"]) == min_breaks], key=lambda r: (int(r["net_fixes"]), -float(r["tau"])))
    best_by_acc = max(margin_rows, key=lambda r: (float(r["exact_accuracy_all_100_offline"] or 0.0), int(r["net_fixes"])))

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "method": args.method,
        "inputs": {
            "per_case_results": str(Path(args.per_case_results)),
            "candidate_diagnostics": str(Path(args.candidate_diagnostics)),
            "verifier_scores": str(Path(args.verifier_scores)),
        },
        "margins": margins,
        "baseline_guarded_exact_correct_count_offline": baseline_correct,
        "baseline_guarded_exact_accuracy_offline": baseline_acc,
        "ambiguous_case_count": len(ambiguous_set),
        "total_cases": len(all_cases),
        "notes": "Decisions use only incumbent + cached verifier scores; gold is used only for offline evaluation fields.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # Margin sweep summary (always written; single-row CSV if one margin)
    with (out_dir / "margin_sweep_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(margin_rows[0].keys()) if margin_rows else ["tau"])
        w.writeheader()
        w.writerows(margin_rows)
    (out_dir / "margin_sweep_summary.json").write_text(
        json.dumps(
            {
                "baseline_guarded_exact_accuracy_offline": baseline_acc,
                "ambiguous_case_count": len(ambiguous_set),
                "margins": margin_rows,
                "best_margin_by_net_fixes": best_by_net,
                "best_margin_by_low_break_risk": best_low_break,
                "best_margin_by_exact_accuracy_all": best_by_acc,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if casebook_to_write is not None:
        with (out_dir / "selector_replay_casebook.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(casebook_to_write[0].keys()) if casebook_to_write else ["case_id"])
            w.writeheader()
            w.writerows(casebook_to_write)

    summary = {
        "baseline_guarded_exact_accuracy_offline": baseline_acc,
        "best_margin_by_net_fixes": best_by_net,
        "best_margin_by_low_break_risk": best_low_break,
        "best_margin_by_exact_accuracy_all": best_by_acc,
        "single_margin_summary": summary_for_margin,
    }
    (out_dir / "selector_replay_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    report = "\n".join(
        [
            "# Cached verifier selector replay (offline)",
            "",
            f"- Output: `{out_dir}`",
            f"- Method: `{args.method}`",
            f"- Total cases: **{len(all_cases)}**; ambiguous: **{len(ambiguous_set)}**",
            f"- Baseline guarded exact (offline): **{baseline_acc:.4f}**" if baseline_acc is not None else "- Baseline guarded exact (offline): (missing)",
            f"- Best τ by net fixes: **{best_by_net['tau']}** (net **{best_by_net['net_fixes']}**, breaks **{best_by_net['breaks_vs_guarded']}**)",
            f"- Best τ by low break risk: **{best_low_break['tau']}** (breaks **{best_low_break['breaks_vs_guarded']}**, net **{best_low_break['net_fixes']}**)",
            "",
            "No API calls are made by this script.",
            "",
        ]
    )
    (out_dir / "report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()

