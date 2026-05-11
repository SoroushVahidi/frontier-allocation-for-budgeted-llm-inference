#!/usr/bin/env python3
"""
Controlled Cohere-assisted labeling for PAL unresolved failure mechanisms.

Defaults to a no-API dry-run; API mode requires --allow-api and enforces --max-calls.
This is an annotation utility only (not a controller change and not a baseline comparison).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_FAILURE_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv"
DEFAULT_GOLD_ABSENT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
DEFAULT_ANCHOR_EFFECT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_20260510.csv"
DEFAULT_OUTPUTS_ROOT = REPO_ROOT / "outputs"

DEFAULT_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
DEFAULT_SUBSET = "diagnostic_15"

DIAGNOSTIC_15_CASE_IDS = (
    "openai_gsm8k_297",
    "openai_gsm8k_168",
    "openai_gsm8k_180",
    "openai_gsm8k_190",
    "openai_gsm8k_197",
    "openai_gsm8k_213",
    "openai_gsm8k_264",
    "openai_gsm8k_347",
    "openai_gsm8k_367",
    "openai_gsm8k_376",
    "openai_gsm8k_391",
    "openai_gsm8k_204",
    "openai_gsm8k_228",
    "openai_gsm8k_233",
    "openai_gsm8k_354",
)


def _utc_now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_truthy(value: Any) -> bool:
    text = _stringify(value).strip().lower()
    if not text:
        return False
    return text not in {"0", "0.0", "false", "no", "none", "nan", "unknown"}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _iter_case_coverage_rows(path: Path) -> Iterable[dict[str, str]]:
    yield from _read_csv_rows(path)


def _latest_case_coverage_csv(outputs_root: Path) -> Path | None:
    candidates = list(outputs_root.rglob("case_coverage_details.csv"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p.stat().st_mtime, str(p)))


def _load_gold_absent_map(path: Path) -> dict[str, dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for row in _read_csv_rows(path):
        case_id = _stringify(row.get("case_id"))
        if case_id and case_id not in by_id:
            by_id[case_id] = row
    return by_id


def _load_anchor_effect_map(path: Path) -> dict[str, dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for row in _read_csv_rows(path):
        case_id = _stringify(row.get("case_id"))
        if case_id and case_id not in by_id:
            by_id[case_id] = row
    return by_id


def _load_failure_map(path: Path) -> dict[str, dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for row in _read_csv_rows(path):
        case_id = _stringify(row.get("case_id"))
        if case_id and case_id not in by_id:
            by_id[case_id] = row
    return by_id


def _extract_question_from_source(*, case_id: str, source_path: str) -> str:
    """Best-effort question retrieval from a selected_source_path artifact."""
    path = Path(source_path)
    if not path.is_file():
        return ""
    # Common case: pal_results.csv rows contain "question".
    if path.suffix.lower() == ".csv":
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    return ""
                if "example_id" not in reader.fieldnames or "question" not in reader.fieldnames:
                    return ""
                for row in reader:
                    if _stringify(row.get("example_id")) == case_id:
                        return _stringify(row.get("question"))
        except Exception:
            return ""
    return ""


@dataclass(frozen=True)
class LabelRequest:
    case_id: str
    method: str
    coverage_status: str
    question: str
    gold: str
    prediction: str
    tags: list[str]
    source_path: str


def _build_tags(
    *,
    case_id: str,
    gold_absent_row: dict[str, str] | None,
    anchor_row: dict[str, str] | None,
) -> list[str]:
    tags: list[str] = []
    if gold_absent_row is not None:
        tags.append("gold_absent")
        qt = _stringify(gold_absent_row.get("question_type"))
        if qt:
            tags.append(f"question_type:{qt}")
        nb = _stringify(gold_absent_row.get("num_candidate_groups"))
        if nb:
            tags.append(f"num_candidate_groups:{nb}")
        db = _stringify(gold_absent_row.get("diversity_bucket"))
        if db:
            tags.append(f"diversity_bucket:{db}")
        err = _stringify(gold_absent_row.get("error_type"))
        if err:
            tags.append(f"error_type:{err}")
    if anchor_row is not None and (
        _is_truthy(anchor_row.get("anchor_matches_l1_max")) or _is_truthy(anchor_row.get("external_l1_exact"))
    ):
        tags.append("direct_l1_anchor_potential")
    return tags


def _select_case_ids(
    *,
    subset: str,
    limit: int,
    coverage_rows: list[dict[str, str]],
    method: str,
    gold_absent_map: dict[str, dict[str, str]],
    anchor_map: dict[str, dict[str, str]],
) -> list[str]:
    subset = str(subset or "").strip()
    if subset == "diagnostic_15":
        ids = list(DIAGNOSTIC_15_CASE_IDS)
        return ids[:limit] if limit > 0 else ids

    # Synthetic subset: unresolved PAL failures where anchor-effect metadata indicates direct-L1 potential.
    if subset == "direct_l1_potential":
        candidates: list[str] = []
        for row in coverage_rows:
            if _stringify(row.get("method")) != method:
                continue
            if _stringify(row.get("coverage_status")) != "still_fails":
                continue
            cid = _stringify(row.get("case_id"))
            if not cid:
                continue
            anchor_row = anchor_map.get(cid)
            if anchor_row is None:
                continue
            if _is_truthy(anchor_row.get("anchor_matches_l1_max")) or _is_truthy(anchor_row.get("external_l1_exact")):
                candidates.append(cid)
        out = sorted(dict.fromkeys(candidates))
        return out[:limit] if limit > 0 else out

    # Default: all unresolved PAL still-failing covered cases.
    if subset in {"unresolved_covered", "unresolved", "all_unresolved"}:
        candidates = [
            _stringify(r.get("case_id"))
            for r in coverage_rows
            if _stringify(r.get("method")) == method and _stringify(r.get("coverage_status")) == "still_fails"
        ]
        out = [c for c in candidates if c]
        out = sorted(dict.fromkeys(out))
        return out[:limit] if limit > 0 else out

    raise ValueError(f"Unknown subset: {subset!r}. Supported: diagnostic_15, direct_l1_potential, unresolved_covered.")


def _prompt_for_request(req: LabelRequest) -> str:
    # Keep the prompt scoped: question/gold/prediction + lightweight tags + goal.
    tags = ", ".join(req.tags) if req.tags else "(none)"
    return (
        "You are a careful annotation assistant. Your task is to label the likely concrete failure mechanism.\n"
        "This is not ground truth and not a policy decision.\n\n"
        f"case_id: {req.case_id}\n"
        f"method: {req.method}\n"
        f"coverage_status: {req.coverage_status}\n"
        f"tags: {tags}\n\n"
        "QUESTION:\n"
        f"{req.question}\n\n"
        f"GOLD_ANSWER: {req.gold}\n"
        f"MODEL_PREDICTION: {req.prediction}\n\n"
        "Return a single JSON object with keys:\n"
        "- mechanism_label: one of [target_quantity_misread, arithmetic_error, unit_mismatch, premature_intermediate_answer, "
        "wrong_supported_consensus, extraction_or_formatting, gold_absent_from_candidates, insufficient_metadata]\n"
        "- confidence: float in [0,1]\n"
        "- evidence: short string citing what in the question/prediction suggests the label\n"
        "- recommended_next_fix: short string\n"
    )


def _load_cohere_client() -> Any:
    # Import only in API mode so dry-run/tests do not require the dependency.
    import cohere  # type: ignore

    api_key = os.getenv("COHERE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is not set; cannot run with --allow-api.")
    return cohere.Client(api_key)


def _call_cohere(*, client: Any, model: str, prompt: str) -> tuple[str, dict[str, Any]]:
    # Use generate-style completion to avoid depending on chat-specific SDK variants.
    resp = client.generate(model=model, prompt=prompt, max_tokens=512, temperature=0.2)
    text = ""
    try:
        text = str(resp.generations[0].text or "")
    except Exception:
        text = str(getattr(resp, "text", "") or "")
    meta = {
        "cohere_model": model,
    }
    return text.strip(), meta


def _parse_label_json(text: str) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(text)
    except Exception as exc:
        return None, f"json_parse_error:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return None, "json_not_object"
    return payload, ""


def _load_existing_case_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            cid = _stringify(row.get("case_id"))
            if cid:
                seen.add(cid)
    return seen


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--coverage-details-csv", default="", help="Path to case_coverage_details.csv from the recovery audit.")
    p.add_argument("--outputs-root", default=str(DEFAULT_OUTPUTS_ROOT), help="Root outputs directory for auto-discovery of coverage CSV.")
    p.add_argument("--failure-csv", default=str(DEFAULT_FAILURE_CSV), help="Failure corpus CSV (for fallback gold/problem text).")
    p.add_argument("--gold-absent-csv", default=str(DEFAULT_GOLD_ABSENT_CSV), help="Gold-absent corpus CSV (tags/question_type).")
    p.add_argument("--anchor-effect-csv", default=str(DEFAULT_ANCHOR_EFFECT_CSV), help="Direct L1 anchor patch-effect CSV (anchor-potential tags).")
    p.add_argument("--method", default=DEFAULT_METHOD, help="Method ID to label (defaults to PAL method).")
    p.add_argument("--subset", default=DEFAULT_SUBSET, help="Subset: diagnostic_15, direct_l1_potential, unresolved_covered.")
    p.add_argument("--limit", type=int, default=0, help="Optional max cases to label from the chosen subset.")
    p.add_argument("--output-dir", default="", help="Output directory (default: /tmp/cohere_pal_failure_mechanism_labels_<timestamp>).")
    p.add_argument("--timestamp", default=_utc_now_stamp(), help="UTC timestamp suffix for default output-dir.")
    p.add_argument("--resume", action="store_true", help="Skip case_ids already present in label_rows.jsonl under output-dir.")
    p.add_argument("--dry-run", "--validate-only", action="store_true", dest="dry_run", help="No-API validate and write stub outputs.")
    p.add_argument("--allow-api", action="store_true", help="Allow Cohere API calls (requires COHERE_API_KEY).")
    p.add_argument("--max-calls", type=int, default=0, help="Hard cap on Cohere calls (required when --allow-api).")
    p.add_argument("--model", default="command-r-plus-08-2024", help="Cohere model name for labeling calls.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    outputs_root = Path(args.outputs_root).expanduser()
    coverage_csv = Path(args.coverage_details_csv).expanduser() if args.coverage_details_csv else Path("")

    failure_csv = Path(args.failure_csv).expanduser()
    gold_absent_csv = Path(args.gold_absent_csv).expanduser()
    anchor_csv = Path(args.anchor_effect_csv).expanduser()
    for p in (failure_csv, gold_absent_csv, anchor_csv):
        if not p.is_file():
            raise FileNotFoundError(f"Missing required CSV: {p}")

    method = str(args.method or "").strip()
    subset = str(args.subset or "").strip()
    limit = int(args.limit or 0)

    coverage_rows: list[dict[str, str]] = []
    gold_absent_map = _load_gold_absent_map(gold_absent_csv)
    anchor_map = _load_anchor_effect_map(anchor_csv)
    failure_map = _load_failure_map(failure_csv)

    if not coverage_csv.is_file():
        found = _latest_case_coverage_csv(outputs_root)
        if found is not None:
            coverage_csv = found
    if coverage_csv.is_file():
        coverage_rows = list(_iter_case_coverage_rows(coverage_csv))
    else:
        # Allow dry-run diagnostic selection without requiring the recovery audit output to exist locally.
        if subset not in {"diagnostic_15"}:
            raise FileNotFoundError(
                f"Missing coverage-details CSV: supply --coverage-details-csv or generate case_coverage_details.csv under {outputs_root}"
            )

    case_ids = _select_case_ids(
        subset=subset,
        limit=limit,
        coverage_rows=coverage_rows,
        method=method,
        gold_absent_map=gold_absent_map,
        anchor_map=anchor_map,
    )

    out_dir = Path(args.output_dir).expanduser() if args.output_dir else Path("/tmp") / f"cohere_pal_failure_mechanism_labels_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "label_rows.jsonl"
    report_path = out_dir / "report.md"
    manifest_path = out_dir / "manifest.json"
    summary_path = out_dir / "summary.json"

    already = _load_existing_case_ids(rows_path) if bool(args.resume) else set()
    pending = [cid for cid in case_ids if cid not in already]

    allow_api = bool(args.allow_api)
    dry_run = bool(args.dry_run) or (not allow_api)
    max_calls = int(args.max_calls or 0)
    if allow_api and max_calls <= 0:
        raise ValueError("--allow-api requires a positive --max-calls cap.")

    labeled_rows: list[dict[str, Any]] = []
    actual_calls = 0
    client = None
    if allow_api and not dry_run:
        client = _load_cohere_client()

    for cid in pending:
        cov_row = next(
            (r for r in coverage_rows if _stringify(r.get("case_id")) == cid and _stringify(r.get("method")) == method),
            {},
        )
        if not cov_row and subset == "diagnostic_15":
            # Fallback: synthesize a minimal coverage row from the tracked failure corpus.
            fail = failure_map.get(cid, {})
            cov_row = {
                "case_id": cid,
                "method": method,
                "coverage_status": _stringify(fail.get("failure_family")) or "unknown",
                "selected_source_path": _stringify(fail.get("artifact_source")),
                "selected_prediction": _stringify(fail.get("selected_answer")),
                "selected_gold": _stringify(fail.get("gold_answer")),
            }
        coverage_status = _stringify(cov_row.get("coverage_status"))
        pred = _stringify(cov_row.get("selected_prediction"))
        gold = _stringify(cov_row.get("selected_gold")) or _stringify(failure_map.get(cid, {}).get("gold_answer"))
        source_path = _stringify(cov_row.get("selected_source_path"))
        question = _extract_question_from_source(case_id=cid, source_path=source_path) or _stringify(
            failure_map.get(cid, {}).get("problem_text")
        )
        tags = _build_tags(case_id=cid, gold_absent_row=gold_absent_map.get(cid), anchor_row=anchor_map.get(cid))

        req = LabelRequest(
            case_id=cid,
            method=method,
            coverage_status=coverage_status,
            question=question,
            gold=gold,
            prediction=pred,
            tags=tags,
            source_path=source_path,
        )
        prompt = _prompt_for_request(req)

        label_payload: dict[str, Any] | None = None
        parse_error = ""
        api_meta: dict[str, Any] = {"api_calls_made": 0}

        if allow_api and not dry_run:
            if actual_calls >= max_calls:
                break
            text, call_meta = _call_cohere(client=client, model=str(args.model), prompt=prompt)
            actual_calls += 1
            api_meta.update(call_meta)
            api_meta["api_calls_made"] = 1
            label_payload, parse_error = _parse_label_json(text)
        else:
            # Dry-run: record request hash and prompt hash but do not call any API.
            api_meta["prompt_sha256"] = _sha256_text(prompt)
            api_meta["request_sha256"] = _sha256_text(json.dumps(req.__dict__, sort_keys=True))

        labeled_rows.append(
            {
                "case_id": cid,
                "method": method,
                "subset": subset,
                "coverage_status": coverage_status,
                "selected_source_path": source_path,
                "gold": gold,
                "prediction": pred,
                "tags": tags,
                "question": question,
                "allow_api": allow_api,
                "dry_run": dry_run,
                "label_json": label_payload,
                "parse_error": parse_error,
                "api_meta": api_meta,
            }
        )

    _write_jsonl(rows_path, labeled_rows if not bool(args.resume) else _merge_jsonl(rows_path, labeled_rows))

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "coverage_details_csv": str(coverage_csv) if coverage_csv.is_file() else "",
        "failure_csv": str(failure_csv),
        "gold_absent_csv": str(gold_absent_csv),
        "anchor_effect_csv": str(anchor_csv),
        "method": method,
        "subset": subset,
        "requested_case_count": len(case_ids),
        "pending_case_count": len(pending),
        "labeled_rows_written": len(labeled_rows),
        "allow_api": allow_api,
        "dry_run": dry_run,
        "max_calls": max_calls if allow_api else 0,
        "actual_calls": actual_calls,
        "model": str(args.model),
    }
    _write_json(manifest_path, manifest)

    label_counts: dict[str, int] = {}
    parse_failures = 0
    for row in labeled_rows:
        if row.get("label_json") is None:
            if row.get("parse_error"):
                parse_failures += 1
            continue
        mech = _stringify((row.get("label_json") or {}).get("mechanism_label"))
        if mech:
            label_counts[mech] = label_counts.get(mech, 0) + 1
    summary = {
        "manifest": manifest,
        "label_counts": dict(sorted(label_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "parse_failures": parse_failures,
        "api_calls_made": actual_calls,
    }
    _write_json(summary_path, summary)

    report_lines = [
        "# Cohere PAL Failure Mechanism Labeling Report",
        "",
        f"- generated_at_utc: `{manifest['generated_at_utc']}`",
        f"- method: `{method}`",
        f"- subset: `{subset}`",
        f"- requested_cases: `{len(case_ids)}`",
        f"- labeled_written: `{len(labeled_rows)}`",
        f"- dry_run: `{dry_run}`",
        f"- allow_api: `{allow_api}`",
        f"- max_calls: `{manifest['max_calls']}`",
        f"- actual_calls: `{actual_calls}`",
        "",
        "## Label Counts",
        "",
    ]
    if summary["label_counts"]:
        for k, v in summary["label_counts"].items():
            report_lines.append(f"- `{k}`: `{v}`")
    else:
        report_lines.append("- (no labels; dry-run or all parse failures)")
    report_lines.append("")
    report_lines.append("## Notes")
    report_lines.append("")
    report_lines.append("- Labels are heuristic annotations, not ground truth.")
    report_lines.append("- This script defaults to no-API mode; API calls require --allow-api and a --max-calls cap.")
    report_path.write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _merge_jsonl(existing_path: Path, new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    if existing_path.is_file():
        with existing_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    merged.append(json.loads(line))
                except Exception:
                    continue
    merged.extend(new_rows)
    return merged


if __name__ == "__main__":
    raise SystemExit(main())
