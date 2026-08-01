from __future__ import annotations

import re
from typing import Any

ALLOWED_SCHEMA_TYPES = {
    "quantity_ledger_schema",
    "rate_table_schema",
    "before_after_state_schema",
    "ratio_equation_schema",
    "target_difference_schema",
    "average_total_count_schema",
}
EQUATION_REQUIRED_SCHEMAS = {
    "quantity_ledger_schema",
    "rate_table_schema",
    "before_after_state_schema",
    "ratio_equation_schema",
    "target_difference_schema",
    "average_total_count_schema",
}
_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
_FINAL_LINE_RE = re.compile(r"^\s*FINAL_ANSWER:\s*([^\n]+)\s*$", re.M)
REQUIRED_SCHEMA_LABELS = (
    "SCHEMA_TYPE:",
    "TARGET_QUANTITY:",
    "GIVEN_QUANTITIES:",
    "EQUATIONS:",
    "COMPUTATION:",
    "FINAL_ANSWER:",
)


def case_has_minimum_probe_data(case_row: dict[str, Any]) -> tuple[bool, str]:
    problem_text = str(
        case_row.get("problem_text")
        or case_row.get("problem_text if available")
        or case_row.get("question")
        or ""
    ).strip()
    gold = str(case_row.get("gold_answer") or case_row.get("gold_answer if available") or case_row.get("answer") or "").strip()
    if not problem_text:
        return False, "missing_problem_text"
    if not gold:
        return False, "missing_gold_answer"
    return True, ""


def select_schema_for_problem_features(features_or_problem_text: dict[str, Any] | str) -> str:
    if isinstance(features_or_problem_text, dict):
        f = features_or_problem_text
        if f.get("asks_average_target") or f.get("average_cue"):
            return "average_total_count_schema"
        if f.get("asks_rate_or_unit"):
            return "rate_table_schema"
        if f.get("ratio_partition_risk") or f.get("ratio_cue"):
            return "ratio_equation_schema"
        if f.get("state_update_risk") or f.get("state_change_cue"):
            return "before_after_state_schema"
        if f.get("asks_difference"):
            return "target_difference_schema"
        return "quantity_ledger_schema"
    t = (features_or_problem_text or "").lower()
    if "average" in t or "mean" in t:
        return "average_total_count_schema"
    if any(x in t for x in ("per ", "mph", "rate")):
        return "rate_table_schema"
    if any(x in t for x in ("ratio", "twice", "half as")):
        return "ratio_equation_schema"
    if any(x in t for x in ("after", "before", "remaining", "then", "later")):
        return "before_after_state_schema"
    if any(x in t for x in ("difference", "how many more", "less than")):
        return "target_difference_schema"
    return "quantity_ledger_schema"


def parse_schema_grounded_response(text: str) -> dict[str, Any]:
    raw = text or ""
    final_lines = _FINAL_LINE_RE.findall(raw)
    final_answer = ""
    if len(final_lines) == 1:
        nums = _NUM_RE.findall(final_lines[0])
        final_answer = nums[0] if nums else ""

    def _line_value(label: str) -> str:
        m = re.search(rf"^\s*{re.escape(label)}:\s*([^\n]*)\s*$", raw, re.M)
        return (m.group(1).strip() if m else "")

    def _block_list(label: str, next_labels: list[str]) -> list[str]:
        pat = rf"^\s*{re.escape(label)}:\s*$"
        m = re.search(pat, raw, re.M)
        if not m:
            return []
        start = m.end()
        end = len(raw)
        for nl in next_labels:
            mm = re.search(rf"^\s*{re.escape(nl)}:\s*", raw[start:], re.M)
            if mm:
                end = min(end, start + mm.start())
        block = raw[start:end]
        lines = [ln.strip()[1:].strip() for ln in block.splitlines() if ln.strip().startswith("-")]
        return [x for x in lines if x]

    schema_type = _line_value("SCHEMA_TYPE")
    target_quantity = _line_value("TARGET_QUANTITY")
    given_quantities = _block_list("GIVEN_QUANTITIES", ["EQUATIONS", "COMPUTATION", "FINAL_ANSWER"])
    equations = _block_list("EQUATIONS", ["COMPUTATION", "FINAL_ANSWER"])
    computation = _block_list("COMPUTATION", ["FINAL_ANSWER"])

    errors: list[str] = []
    if not schema_type:
        errors.append("missing_schema_type")
    if not target_quantity:
        errors.append("missing_target_quantity")
    if len(final_lines) == 0:
        errors.append("missing_final_answer")
    if len(final_lines) > 1:
        errors.append("multiple_final_answer_lines")
    if len(final_lines) == 1 and not final_answer:
        errors.append("final_answer_not_numeric")
    if not given_quantities:
        errors.append("missing_given_quantities")
    if not computation:
        errors.append("missing_computation")

    return {
        "schema_type": schema_type,
        "target_quantity": target_quantity,
        "given_quantities": given_quantities,
        "equations": equations,
        "computation": computation,
        "final_answer": final_answer,
        "parse_success": len(errors) == 0,
        "parse_errors": errors,
    }


def validate_schema_grounded_response(parsed: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    schema_type = str(parsed.get("schema_type") or "").strip()
    equations = parsed.get("equations") or []
    final_answer = str(parsed.get("final_answer") or "").strip()

    if schema_type not in ALLOWED_SCHEMA_TYPES:
        errors.append("invalid_schema_type")
    if schema_type in EQUATION_REQUIRED_SCHEMAS and not equations:
        errors.append("missing_equations")
    if not final_answer or not _NUM_RE.fullmatch(final_answer):
        errors.append("invalid_final_answer")
    if not parsed.get("target_quantity"):
        errors.append("missing_target_quantity")
    if not parsed.get("given_quantities"):
        errors.append("missing_given_quantities")
    if not parsed.get("computation"):
        errors.append("missing_computation")
    if parsed.get("parse_errors"):
        errors.append("parse_errors_present")

    return {
        **parsed,
        "validation_success": len(errors) == 0,
        "validation_errors": errors,
    }
