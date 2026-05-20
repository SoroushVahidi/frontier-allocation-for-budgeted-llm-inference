#!/usr/bin/env python3
"""No-API preflight scaffold for final_transform_branch_generation_v1."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPERIMENT_ID = "final_transform_branch_generation_v1"
ALIAS = "ft_branch_gen_v1"
DEFAULT_TRACE_PACKETS = Path("/tmp/codex_pattern_mining_wrong_consensus_97_packets/trace_packets.jsonl")
DEFAULT_GOLD_POOL_REPORT = Path("/tmp/gold_pool_split_wrong_consensus_97_report.md")
DEFAULT_OUTPUT_DIR = Path("/tmp/final_transform_branch_generation_v1_preflight")
DEFAULT_MAX_BRANCH_SLOTS_PER_CASE = 1

BRANCH_FAMILIES = (
    "ratio_base_branch",
    "original_before_process_branch",
    "per_unit_share_branch",
    "profit_revenue_cost_branch",
    "difference_or_remainder_branch",
    "unit_conversion_branch",
    "target_first_final_transform_branch",
    "unknown_final_transform",
)

PROMPT_TEMPLATE_IDS = (
    "ratio_base_branch",
    "original_before_process_branch",
    "per_unit_share_branch",
    "profit_revenue_cost_branch",
    "difference_or_remainder_branch",
    "unit_conversion_branch",
    "target_first_final_transform_branch",
)

FORBIDDEN_PROMPT_PATTERNS = (
    re.compile(r"\bgold_answer\b\s*[:=]", re.I),
    re.compile(r"\banswer_key\b\s*[:=]", re.I),
    re.compile(r"\bhidden[_ -]?labels?\b\s*[:=]", re.I),
    re.compile(r"\bgold\b\s*[:=]", re.I),
)

_TARGET_SURFACE_RE = re.compile(
    r"(?:what is(?: the)?|how many|how much|find(?: the)?|calculate|determine|express(?: the)?)\s+(.+?)(?:\?|$)",
    re.I,
)
_MONEY_RE = re.compile(r"[\$£€]|\b(dollars?|cents?|cost(?:s|ing)?|price(?:s)?|revenue|profit|money|spend|spent|income|earnings?)\b", re.I)
_COUNT_RE = re.compile(r"\b(how many|number of|count|counts)\b", re.I)
_RATE_RE = re.compile(r"\b(per|each|every|rate)\b", re.I)
_DIFF_RE = re.compile(r"\b(more than|less than|difference|remaining|left|left over|remainder|how many more)\b", re.I)
_RATIO_RE = re.compile(
    r"\b(percent|percentage|probability|chance|odds|ratio|fraction|proportion|out of|what fraction|what percent|of the total|among|share of)\b|%",
    re.I,
)
_TIME_RE = re.compile(r"\b(now|today|after|before|from now|initial|final|remaining|left)\b", re.I)

_UNIT_CONVERSION_RE = re.compile(
    r"\b(?:convert|conversion|hours?\s+to\s+minutes?|minutes?\s+to\s+hours?|miles?\s+to\s+feet?|feet\s+to\s+inches?|kilometers?\s+to\s+miles?|grams?\s+to\s+kilograms?|liters?\s+to\s+gallons?|(?:pages?|sheets?)\s+per|per\s+(?:page|sheet)|items?\s+per\s+(?:container|box|bag|pack|carton)|tabloid)\b",
    re.I,
)
_PROFIT_REVENUE_COST_RE = re.compile(
    r"\b(profit|revenue|cost(?:s|ing)?|price(?:s)?|sell(?:s|ing|er)?|sold|bought|loss(?:es)?|sale(?:s)?|spent|spend(?:s|ing)?|income|earn(?:ings?|ed)?|margin)\b",
    re.I,
)
_ORIGINAL_BEFORE_PROCESS_RE = re.compile(
    r"\b(original(?:ly)?|original\s+amount|initial(?:ly)?|at\s+first|used\s+to\s+be|starting\s+with|started\s+with|start\s+with|prior\s+to|pre[- ]?change|before|after\s+(?:halving|doubling|tripling|losing|gaining|spending|giving\s+away|adding|subtracting)|reverse(?:\s+process)?)\b",
    re.I,
)
_PER_UNIT_SHARE_RE = re.compile(
    r"\b(apiece|per\s+(?:person|item|unit|group|team|share|day|week|month|pair|contact)|per\s+pair|pair(?:s)?\s+of|each\s+pair|shared\s+equally|split\s+evenly|divided\s+equally|per-unit|per\s+unit|each\s+(?:person|item|unit|group|team|share|pair)|every\s+(?:person|item|unit|group|team|share)|average\s+per|contacts?\s+per)\b",
    re.I,
)
_RATIO_BASE_RE = re.compile(
    r"\b(percent(?:age)?|probability|likelihood|chance|odds|ratio|fraction|proportion|out\s+of|what\s+(?:percent|percentage|fraction|ratio)|base\s+quantity|base|of\s+the\s+total|among|share\s+of|weighted)\b|%",
    re.I,
)
_GENERIC_TRANSFORM_RE = re.compile(
    r"\b(after|left|remaining|total|each|per|difference|more|less|before|original|cost|price|percent|fraction|ratio|share|final)\b",
    re.I,
)
_TARGET_FIRST_FALLBACK_RE = re.compile(
    r"\b(age|ages|older|younger|how old|twice as old|thrice as old|half as old|times as old|times as much|times as long|half as long|years ago|years from now|combined|sum of their ages|height|length|rope|mountain|money used|how much money|show up|could only play|before|after|final|total)\b",
    re.I,
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten_for_csv(row.get(key)) for key in fieldnames})


def _flatten_for_csv(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    if value is None:
        return ""
    return value


def parse_target_schema(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError("target schema must be a mapping")
    out = {
        "target_variable": _stringify(raw.get("target_variable")),
        "entity": _stringify(raw.get("entity")),
        "unit": _stringify(raw.get("unit")),
        "time_or_state": _stringify(raw.get("time_or_state")),
        "operation_goal": _stringify(raw.get("operation_goal")),
        "known_quantities": [],
        "required_relations": [],
        "uncertainty": bool(raw.get("uncertainty", False)),
    }
    known_quantities = raw.get("known_quantities")
    if isinstance(known_quantities, list):
        for idx, item in enumerate(known_quantities, start=1):
            if not isinstance(item, dict):
                continue
            out["known_quantities"].append(
                {
                    "name": _stringify(item.get("name") or f"quantity_{idx}"),
                    "value": _stringify(item.get("value")),
                    "unit": _stringify(item.get("unit")),
                }
            )
    required_relations = raw.get("required_relations")
    if isinstance(required_relations, list):
        out["required_relations"] = [_stringify(item) for item in required_relations if _stringify(item)]
    return out


def serialize_target_schema(schema: dict[str, Any]) -> str:
    return json.dumps(parse_target_schema(schema), sort_keys=True, ensure_ascii=False)


def _extract_target_surface(question: str) -> str:
    match = _TARGET_SURFACE_RE.search(question or "")
    if not match:
        return ""
    surface = re.sub(r"\s+", " ", match.group(1)).strip(" .")
    return surface[:120]


def _infer_unit(question: str) -> str:
    q = (question or "").lower()
    if _MONEY_RE.search(q):
        return "money"
    if _COUNT_RE.search(q):
        return "count"
    if _RATE_RE.search(q):
        return "rate"
    if _DIFF_RE.search(q):
        return "difference"
    if _RATIO_RE.search(q):
        return "ratio"
    if re.search(r"\b(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years|second|seconds|mile|miles|foot|feet|inch|inches)\b", q):
        return "measurement"
    return "unknown"


def _infer_time_or_state(question: str) -> str:
    q = (question or "").lower()
    if "before" in q or "after" in q:
        return "before_after"
    if "from now" in q:
        return "future_state"
    if "now" in q:
        return "current_state"
    if "final" in q:
        return "final_state"
    if _TIME_RE.search(q):
        return "time_marker"
    return "unknown"


def _infer_operation_goal(question: str) -> str:
    q = (question or "").lower()
    if any(tok in q for tok in ("total", "altogether", "in all", "combined", "sum")):
        return "add"
    if any(tok in q for tok in ("left", "remaining", "difference", "less than", "more than", "remainder")):
        return "subtract"
    if any(tok in q for tok in ("per", "each", "every", "rate", "times", "product", "share")):
        return "multiply_or_divide"
    if any(tok in q for tok in ("ratio", "percent", "percentage", "fraction", "proportion")):
        return "ratio"
    if any(tok in q for tok in ("convert", "conversion", "hours to minutes", "minutes to hours")):
        return "convert"
    if any(tok in q for tok in ("equation", "solve for", "find x", "variable")):
        return "equation"
    return "solve"


def _extract_known_quantities(question: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for idx, match in enumerate(re.finditer(r"(?<!\w)(-?\d+(?:\.\d+)?)(?!\w)", question or ""), start=1):
        start = max(0, match.start() - 40)
        end = min(len(question), match.end() + 40)
        context = question[start:end]
        out.append(
            {
                "name": f"quantity_{idx}",
                "value": match.group(1),
                "unit": _infer_unit(context),
            }
        )
    return out


def build_target_schema(question: str, *, case_id: str = "") -> dict[str, Any]:
    target_surface = _extract_target_surface(question)
    unit = _infer_unit(question)
    target_variable = target_surface or "final_target"
    entity = target_surface or target_variable
    known_quantities = _extract_known_quantities(question)
    operation_goal = _infer_operation_goal(question)
    relations = [f"bind_target:{target_variable}"]
    if operation_goal != "solve":
        relations.append(f"apply_{operation_goal}")
    if unit != "unknown":
        relations.append("preserve_unit_consistency")
    if any(tok in (question or "").lower() for tok in (" or ", "either", "maybe")):
        relations.append("handle_ambiguity")
    if case_id:
        relations.append(f"preflight_case:{case_id}")
    return parse_target_schema(
        {
            "target_variable": target_variable,
            "entity": entity,
            "unit": unit,
            "time_or_state": _infer_time_or_state(question),
            "operation_goal": operation_goal,
            "known_quantities": known_quantities,
            "required_relations": relations,
            "uncertainty": bool(not target_surface or unit == "unknown" or not known_quantities),
        }
    )


def _schema_to_prompt_json(schema: dict[str, Any]) -> str:
    return json.dumps(parse_target_schema(schema), indent=2, sort_keys=True, ensure_ascii=False)


def _contains_forbidden_prompt_markers(prompt: str) -> list[str]:
    hits: list[str] = []
    for pattern in FORBIDDEN_PROMPT_PATTERNS:
        if pattern.search(prompt or ""):
            hits.append(pattern.pattern)
    return hits


def _load_trace_cases(path: Path) -> dict[str, dict[str, Any]]:
    raw = _json_load(path)
    cases = raw.get("cases") if isinstance(raw, dict) else None
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(cases, list):
        return out
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = _stringify(case.get("case_id"))
        if case_id:
            out[case_id] = case
    return out


_GOLD_ABSENT_ROW_RE = re.compile(
    r"^\|\s*(openai_gsm8k_[^|]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.*)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$"
)


def _load_gold_absent_report_rows(report_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not report_path.is_file():
        return rows
    lines = report_path.read_text(encoding="utf-8").splitlines()
    in_bucket_b = False
    for line in lines:
        if line.startswith("## B. gold_absent_from_pool"):
            in_bucket_b = True
            continue
        if in_bucket_b and line.startswith("## ") and not line.startswith("## B. gold_absent_from_pool"):
            break
        if not in_bucket_b:
            continue
        match = _GOLD_ABSENT_ROW_RE.match(line.strip())
        if not match:
            continue
        rows.append(
            {
                "case_id": match.group(1).strip(),
                "question_type": match.group(2).strip(),
                "selected_prediction": match.group(3).strip(),
                "candidate_pool_values": match.group(4).strip(),
                "final_transform_subtype": match.group(5).strip(),
                "generation_branch_needed": match.group(6).strip(),
            }
        )
    return rows


def _candidate_pool_numeric_count(candidate_pool_values: str) -> int:
    values: list[str] = []
    for chunk in (candidate_pool_values or "").split(","):
        token = chunk.strip().split("[", 1)[0].strip()
        if not token:
            continue
        if re.fullmatch(r"-?\d+(?:\.\d+)?", token):
            values.append(token)
    return len(set(values))


def _question_cues(question: str) -> list[str]:
    cues: list[str] = []
    q = (question or "").lower()
    if _UNIT_CONVERSION_RE.search(q):
        cues.append("unit_conversion")
    if _PROFIT_REVENUE_COST_RE.search(q):
        cues.append("profit_revenue_cost")
    if _ORIGINAL_BEFORE_PROCESS_RE.search(q):
        cues.append("original_before_process")
    if _DIFF_RE.search(q):
        cues.append("difference_or_remainder")
    if _RATIO_BASE_RE.search(q):
        cues.append("ratio_base")
    if _PER_UNIT_SHARE_RE.search(q):
        cues.append("per_unit_share")
    return cues


def classify_branch_families(question: str, candidate_pool_values: str | None = None) -> tuple[list[str], list[str], str]:
    cues = _question_cues(question)
    families: list[str] = []
    priority = (
        ("original_before_process_branch", "original_before_process"),
        ("per_unit_share_branch", "per_unit_share"),
        ("profit_revenue_cost_branch", "profit_revenue_cost"),
        ("difference_or_remainder_branch", "difference_or_remainder"),
        ("ratio_base_branch", "ratio_base"),
        ("unit_conversion_branch", "unit_conversion"),
    )
    for family, cue in priority:
        if cue in cues:
            families.append(family)
            break
    if not families:
        numeric_pool_count = _candidate_pool_numeric_count(candidate_pool_values or "")
        q = (question or "").lower()
        if numeric_pool_count >= 2 and (_GENERIC_TRANSFORM_RE.search(q) or _TARGET_FIRST_FALLBACK_RE.search(q)):
            families = ["target_first_final_transform_branch"]
    if not families:
        families = ["unknown_final_transform"]
    if families == ["target_first_final_transform_branch"]:
        reason = "generic transformed-target fallback"
    else:
        reason = " ; ".join(cues) if cues else "no strong final-transform cue"
    return families, cues, reason


def _prompt_template_path(template_id: str) -> Path:
    return Path(__file__).resolve().parents[1] / "prompts" / EXPERIMENT_ID / f"{template_id}.md"


def render_prompt(template_id: str, *, question: str, target_schema: dict[str, Any] | None = None) -> str:
    if template_id == "unknown_final_transform":
        target_schema_json = _schema_to_prompt_json(target_schema or {})
        rendered = (
            "BRANCH_FAMILY: unknown_final_transform\n"
            "MODE: no_api_preflight_only\n\n"
            "Preserve the final target binding and reason conservatively when no strong final-transform cue is present.\n\n"
            "Rules:\n"
            "- Do not use any hidden reference answer, answer-key information, or label metadata.\n"
            "- Bind the final target before arithmetic.\n"
            "- State any uncertainty explicitly.\n\n"
            "QUESTION:\n"
            f"{question}\n\n"
            "TARGET_SCHEMA_JSON:\n"
            f"{target_schema_json}\n\n"
            "Respond with a concise target-binding sketch and then the final answer only."
        )
    else:
        template = _prompt_template_path(template_id).read_text(encoding="utf-8")
        rendered = template.replace("{{question}}", question).replace("{{target_schema_json}}", _schema_to_prompt_json(target_schema or {}))
    if "{{" in rendered or "}}" in rendered:
        raise ValueError(f"unresolved placeholder in {template_id}")
    return rendered


def _assign_branch_families(question: str, *, max_slots: int) -> tuple[list[str], list[str], str]:
    families, cues, reason = classify_branch_families(question)
    return families[: max(1, max_slots)], cues, reason


def build_call_plan(
    *,
    cases: list[dict[str, Any]],
    report_rows: dict[str, dict[str, str]],
    max_branch_slots_per_case: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    call_plan_rows: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()
    cue_counts: Counter[str] = Counter()
    unknown_count = 0

    for case_index, case in enumerate(cases, start=1):
        case_id = _stringify(case.get("case_id"))
        question = _stringify(case.get("question"))
        if case_id not in report_rows:
            continue
        report_meta = report_rows[case_id]
        families, cues, reason = classify_branch_families(question, report_meta["candidate_pool_values"])
        target_schema = build_target_schema(question, case_id=case_id)
        for cue in cues:
            cue_counts[cue] += 1
        families = families[: max(1, max_branch_slots_per_case)]
        if families == ["unknown_final_transform"]:
            unknown_count += 1
        for branch_slot, family in enumerate(families, start=1):
            prompt = render_prompt(family, question=question, target_schema=target_schema)
            template_path = _prompt_template_path(family)
            no_gold_leak_ok = len(_contains_forbidden_prompt_markers(prompt)) == 0
            row = {
                "experiment_id": EXPERIMENT_ID,
                "alias": ALIAS,
                "case_id": case_id,
                "case_index": case_index,
                "question": question,
                "question_type": report_meta["question_type"],
                "selected_prediction": report_meta["selected_prediction"],
                "candidate_pool_values": report_meta["candidate_pool_values"],
                "final_transform_subtype": report_meta["final_transform_subtype"],
                "generation_branch_needed": report_meta["generation_branch_needed"],
                "candidate_branch_families": families,
                "selected_branch_family": family,
                "branch_slot": branch_slot,
                "branch_slot_limit": max_branch_slots_per_case,
                "routing_reason": reason,
                "routing_cues": cues,
                "prompt_template_id": family,
                "prompt_template_path": str(template_path.relative_to(Path(__file__).resolve().parents[1])),
                "prompt": prompt,
                "target_schema": target_schema,
                "target_schema_json": _schema_to_prompt_json(target_schema),
                "render_ok": "{{" not in prompt and "}}" not in prompt,
                "no_gold_leak_ok": no_gold_leak_ok,
                "api_calls_allowed": False,
            }
            call_plan_rows.append(row)
            family_counts[family] += 1

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "alias": ALIAS,
        "case_count": len(report_rows),
        "selected_case_count": len({row["case_id"] for row in call_plan_rows}),
        "call_plan_row_count": len(call_plan_rows),
        "branch_slot_limit": max_branch_slots_per_case,
        "branch_family_counts": dict(family_counts),
        "cue_counts": dict(cue_counts),
        "unknown_routing_count": unknown_count,
        "no_api_clients_constructed": True,
    }
    return call_plan_rows, summary


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Final-Transform Branch Generation v1 Dry Run",
        "",
        f"- experiment_id: `{summary['experiment_id']}`",
        f"- alias: `{summary['alias']}`",
        f"- case_count: `{summary['case_count']}`",
        f"- selected_case_count: `{summary['selected_case_count']}`",
        f"- call_plan_row_count: `{summary['call_plan_row_count']}`",
        f"- branch_slot_limit: `{summary['branch_slot_limit']}`",
        "",
        "## Branch Families",
    ]
    for key, value in sorted((summary.get("branch_family_counts") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Cue Counts",
        ]
    )
    for key, value in sorted((summary.get("cue_counts") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            f"- unknown_routing_count: `{summary['unknown_routing_count']}`",
            f"- no_api_clients_constructed: `{summary['no_api_clients_constructed']}`",
            "",
            "This is a no-API dry run. It does not change runtime defaults or call any model API.",
        ]
    )
    return "\n".join(lines) + "\n"


def run(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-packets", type=Path, default=DEFAULT_TRACE_PACKETS)
    parser.add_argument("--gold-pool-report", type=Path, default=DEFAULT_GOLD_POOL_REPORT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timestamp", type=str, default="")
    parser.add_argument("--max-branch-slots-per-case", type=int, default=DEFAULT_MAX_BRANCH_SLOTS_PER_CASE)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    report_rows_list = _load_gold_absent_report_rows(args.gold_pool_report)
    if not report_rows_list:
        raise FileNotFoundError(f"could not load gold-absent rows from {args.gold_pool_report}")
    report_rows = {row["case_id"]: row for row in report_rows_list}

    trace_cases = _load_trace_cases(args.trace_packets)
    cases = [trace_cases[case_id] for case_id in report_rows if case_id in trace_cases]
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]

    call_plan_rows, summary = build_call_plan(
        cases=cases,
        report_rows=report_rows,
        max_branch_slots_per_case=max(1, args.max_branch_slots_per_case),
    )

    stamp = _stringify(args.timestamp) or _utc_stamp()
    output_dir = args.out_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "alias": ALIAS,
        "mode": "dry_run_only",
        "runtime_defaults_changed": False,
        "api_calls_allowed": False,
        "gold_leakage_allowed": False,
        "trace_packets_path": str(args.trace_packets),
        "gold_pool_report_path": str(args.gold_pool_report),
        "resolved_timestamp": stamp,
        "resolved_output_dir": str(output_dir.resolve()),
        "resolved_case_count": len(cases),
        "resolved_case_ids": [case["case_id"] for case in cases],
        "resolved_total_action_budget": max(1, args.max_branch_slots_per_case),
        "branch_families": list(BRANCH_FAMILIES),
        "prompt_templates": list(PROMPT_TEMPLATE_IDS),
        "branch_slot_limit": max(1, args.max_branch_slots_per_case),
        "case_selection_source": "gold_pool_report",
        "expected_output_files": [
            "manifest.json",
            "call_plan.jsonl",
            "routing_summary.csv",
            "dry_run_report.md",
        ],
        "no_api_clients_constructed": True,
    }

    summary = dict(summary)
    summary.update(
        {
            "manifest_path": str((output_dir / "manifest.json").resolve()),
            "output_dir": str(output_dir.resolve()),
            "trace_packets_path": str(args.trace_packets),
            "gold_pool_report_path": str(args.gold_pool_report),
            "timestamp": stamp,
        }
    )

    _write_json(output_dir / "manifest.json", manifest)
    _write_jsonl(output_dir / "call_plan.jsonl", call_plan_rows)
    _write_csv(output_dir / "routing_summary.csv", call_plan_rows)
    (output_dir / "dry_run_report.md").write_text(_render_report(summary), encoding="utf-8")
    _write_json(output_dir / "dry_run_summary.json", summary)
    return summary


def main() -> None:
    summary = run()
    print(f"Wrote preflight artifacts to {summary['output_dir']}")


if __name__ == "__main__":
    main()
