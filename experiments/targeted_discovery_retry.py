"""Offline helpers for targeted discovery retry v1 (gold-free prompts; no API)."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Mapping

FIRST_COHORT_FAMILIES = frozenset({"money_budget", "rate_ratio", "temporal_change", "difference_comparison"})
TARGETED_RETRY_SUPPORTED_FAMILIES_V1 = frozenset(
    {"money_budget", "rate_ratio", "temporal_change", "difference_comparison", "multi_step_total", "average"}
)
TARGETED_RETRY_RECOMMENDED_PROMPT_VERSIONS_V1 = {
    "quantity_ledger": "quantity_ledger_v2_1",
    "rate_table": "v1",
    "before_after_state": "v1",
    "target_difference": "v1",
}
TARGETED_ROUTING_V2_SCAFFOLDS = frozenset(
    {
        "percent_base_denominator",
        "percent_base_denominator_v2",
        "average_target_score",
        "combinatorics_counting",
        "ratio_partition",
        "ratio_partition_v2",
        "state_composition",
        "state_composition_v2",
        "final_target_verifier_retry",
        "l1_style_concise_decomposition",
    }
)

# ASCII digits in the problem paragraph are mapped to fullwidth digits so offline checks like
# ``gold not in prompt`` do not false-positive when gold is a substring of a larger number (e.g. 2 in 29).
_PROBLEM_DIGIT_TRANSLATION = str.maketrans(
    "0123456789", "\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19"
)


def embed_problem_for_prompt(problem_text: str) -> str:
    """Return problem text with digits rewritten for prompt embedding (still human/model readable)."""
    return (problem_text or "").strip().translate(_PROBLEM_DIGIT_TRANSLATION)


SCAFFOLD_BY_FAMILY: dict[str, str] = {
    "money_budget": "quantity_ledger",
    "rate_ratio": "rate_table",
    "temporal_change": "before_after_state",
    "difference_comparison": "target_difference",
}


def classify_family_from_row(row: Mapping[str, str]) -> str:
    return str(row.get("derived_problem_family") or "").strip()


def choose_scaffold(row: Mapping[str, str]) -> str:
    fam = classify_family_from_row(row)
    return SCAFFOLD_BY_FAMILY.get(fam, "quantity_ledger")


def choose_scaffold_v2(row: Mapping[str, str]) -> str:
    """Offline routing-v2 helper for uncovered Stage-2 disagreement patterns."""
    family = str(row.get("proposed_problem_family_v2") or row.get("derived_problem_family") or "").strip()
    text = str(row.get("problem_text") or "").lower()
    if family in TARGETED_ROUTING_V2_SCAFFOLDS:
        return family
    if "average" in text and "score" in text:
        return "average_target_score"
    if "ratio" in text or "twice" in text or "half" in text:
        return "ratio_partition"
    if "percent" in text or "%" in text or "fraction" in text:
        return "percent_base_denominator"
    if "order" in text or "ways" in text or "choose" in text:
        return "combinatorics_counting"
    if any(k in text for k in ("after", "before", "remaining", "left", "total")):
        return "state_composition"
    return "quantity_ledger"


def build_prompt(problem_text: str, scaffold: str, *, prompt_version: str = "v1") -> str:
    text = embed_problem_for_prompt(problem_text)
    shared_footer = (
        "\n\nRules:\n"
        "- Use only the problem statement above; do not assume hidden facts.\n"
        "- Show your reasoning briefly, then give the final numeric answer as the **last line** "
        "in \\boxed{} (single value).\n"
    )
    if scaffold == "quantity_ledger" and prompt_version in {"quantity_ledger_v2_1", "v2_1"}:
        body = (
            "You are solving a grade-school math word problem using a **quantity ledger**.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- Restate the final target quantity exactly once (e.g., annual total paid/earned, profit, remaining amount).\n"
            "- Build a money ledger with named lines for every relevant amount (principal/cost/revenue/profit/bonus/total/remaining as applicable).\n"
            "- For each money/income/bonus/payment quantity in the story, do **recurrence classification**:\n"
            "  - one-time (add once),\n"
            "  - per-period recurring (multiply by number of periods),\n"
            "  - total across the whole horizon (do not multiply),\n"
            "  - unknown (compute only unambiguous parts).\n"
            "- Critical recurrence rule: **Never multiply a one-time bonus/payment by the number of periods** unless the story explicitly says it repeats.\n"
            "- Percent/fraction base rule: if a percentage is described as applying to an original/base amount each interval, use a constant increment (no compounding). If a percentage is a raise on salary, compute the raised salary first.\n"
            "- If the story says a bonus is \"worth X months of salary\" or \"a fraction of a month’s salary\", treat it as **one-time**: compute from the referenced month’s (raised) salary and add once.\n"
            "- Convert units/time spans so everything is on the same basis before combining.\n"
            "- Compute the final requested numeric result.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "quantity_ledger" and prompt_version == "v2":
        # v2 focuses on monetary percentage semantics (fixed increment vs compounding,
        # and whether bonuses use raised vs original salary).
        body = (
            "You are solving a grade-school math word problem using a **quantity ledger**.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- Restate the exact final target quantity the question asks for (for money: total paid/earned, yearly amount, change, remaining, profit, etc.).\n"
            "- Build a money ledger with named lines for every distinct amount in the story (principal/cost/revenue/bonus/total/remaining as applicable).\n"
            "- For any percentage or fraction mentioned, decide what it applies to:\n"
            "  - If the story ties the change to the original/base amount each time, use a fixed increment from the original/base (do not compound).\n"
            "  - If it describes a raise on a salary, compute the raised salary first; any later bonus defined as a fraction of a month's salary must use the raised salary.\n"
            "- Convert units and time spans so everything is on the same basis before combining.\n"
            "- Compute the final requested numeric result carefully.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "quantity_ledger":
        body = (
            "You are solving a grade-school math word problem using a **quantity ledger**.\n\n"
            "Problem:\n"
            f"{text}\n\n"
        "Instructions:\n"
        "- List every numeric quantity with its unit (or \"unitless\") and what it measures.\n"
        "- State clearly which quantity the question asks for (the **target**).\n"
        "- Write the equation or step-by-step arithmetic plan that connects the quantities to the target.\n"
        "- Execute the plan carefully and double-check units and percentages.\n"
        "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "rate_table":
        body = (
            "You are solving a grade-school math word problem using a **rate table**.\n\n"
            "Problem:\n"
            f"{text}\n\n"
        "Instructions:\n"
        "- Identify each relevant **rate** (with units), the **base quantity** or time span, and what **total** is needed.\n"
        "- Build a small table: entity / rate / quantity or duration / subtotal — one row per line of reasoning.\n"
        "- Make sure units cancel consistently before you combine rows.\n"
        "- Compute the final numeric result and verify it matches the story.\n"
        "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "before_after_state":
        body = (
            "You are solving a grade-school math word problem using **before/after state** over time.\n\n"
            "Problem:\n"
            f"{text}\n\n"
        "Instructions:\n"
        "- Write the **initial state** (all relevant quantities).\n"
        "- List **each change in chronological order**, updating the state after each step.\n"
        "- Identify the **final queried quantity** (what the problem asks for at the end).\n"
        "- Compute that quantity from the final state.\n"
        "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "target_difference":
        body = (
            "You are solving a grade-school math word problem with explicit **targets**.\n\n"
            "Problem:\n"
            f"{text}\n\n"
        "Instructions:\n"
        "- Name the main **entities or quantities** (A, B, totals, etc.).\n"
        "- Quote or paraphrase **exactly** what the problem asks for (difference, sum, \"how many more\", half of a total, etc.).\n"
        "- Do **not** return an intermediate value if the question asks for a **difference**, **total**, or **scaled total** — match the target.\n"
        "- Plan and compute accordingly.\n"
        "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "percent_base_denominator":
        body = (
            "You are solving a math word problem with percentage/fraction base tracking.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- List each percent/fraction statement and the exact base quantity it applies to.\n"
            "- For each step, mark whether the base is original, subtotal, remaining, or updated amount.\n"
            "- Do not apply a percent to the wrong base; keep a short ledger of base -> operation -> result.\n"
            "- If multiple periods are involved, state whether the percent is repeating on the same base or applied sequentially.\n"
            "- Compute only the asked target quantity and avoid intermediate-only answers.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "average_target_score":
        body = (
            "You are solving a target-average / missing-value problem.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- Identify: count of items, known values, target average, and unknown value(s).\n"
            "- Convert average target to required total using: required_total = target_average * item_count.\n"
            "- Build equation: known_sum + unknown = required_total (or equivalent).\n"
            "- Solve for the unknown value and check it against the problem constraints.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "combinatorics_counting":
        body = (
            "You are solving a counting/combinatorics problem.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- List objects, choices, and constraints explicitly.\n"
            "- Decide whether order matters; if unsure, test both quickly and pick the one matching the story.\n"
            "- Count systematically using cases, product/addition rule, or simple equations.\n"
            "- Verify no double-counting and no missing cases.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "ratio_partition":
        body = (
            "You are solving a ratio partition problem.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- Identify total quantity and ratio parts.\n"
            "- Convert ratio to unit parts and compute one part value.\n"
            "- Recover requested part(s), difference, or percentage from part values.\n"
            "- If text includes \"half/twice\" relationships, rewrite them in ratio-equation form before solving.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "state_composition":
        body = (
            "You are solving a state-composition problem with sequential operations.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- Start from initial state values.\n"
            "- Apply each operation in story order (add/subtract/scale/convert units).\n"
            "- Keep intermediate states explicit to avoid mixing totals and components.\n"
            "- Restate the exact final target before computing the last step.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "final_target_verifier_retry":
        body = (
            "Solve this math word problem with explicit final-target verification.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- Restate exactly what final quantity is asked (value, difference, remaining, total, or percentage).\n"
            "- Write minimal equations only; no extra narration.\n"
            "- Before final line, check sign/direction (e.g., withheld, remaining, more/less).\n"
            "- Ensure the final line answers the stated target, not an intermediate value.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "ratio_partition_v2":
        body = (
            "Solve this ratio partition problem using concise decomposition.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- Restate the asked target (which part, difference, or percentage).\n"
            "- Convert wording (twice/half/as many) into ratio parts.\n"
            "- Use one compact equation to solve part values.\n"
            "- Compute only the requested target quantity.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "state_composition_v2":
        body = (
            "Solve this sequential state-change problem with concise checkpoints.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- Restate the final target quantity first.\n"
            "- Apply updates in strict story order (before/after/then/later).\n"
            "- Keep a short state ledger after each update.\n"
            "- Verify the final step answers the asked target.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "percent_base_denominator_v2":
        body = (
            "Solve this percent/fraction problem by identifying denominator base before arithmetic.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- For each percent/fraction statement, name the exact base/denominator quantity.\n"
            "- Mark whether base is original, updated, or remaining for each step.\n"
            "- If the text says a rate is of the total/original capacity each hour (or each period), keep a fixed base for every period; do not switch to remaining base unless explicitly stated.\n"
            "- Before finalizing, run a base-consistency check: each percent operation must reference the same base label you declared for that statement.\n"
            "- Keep equations minimal and avoid switching denominator implicitly.\n"
            "- Restate final target and compute only that quantity.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    elif scaffold == "l1_style_concise_decomposition":
        body = (
            "Use concise decomposition with strict target alignment.\n\n"
            "Problem:\n"
            f"{text}\n\n"
            "Instructions:\n"
            "- Restate target in one short sentence.\n"
            "- Write 2-4 compact equation lines.\n"
            "- Prefer direct algebraic setup over verbose explanation.\n"
            "- Final line must be a single value for the asked target.\n"
            "- Output the **final answer only** at the end as specified below.\n"
        )
    else:
        return build_prompt(problem_text, "quantity_ledger")
    return body + shared_footer


def build_final_target_extraction_repair_prompt(problem_text: str) -> str:
    """Stage-3 micro-patch prompt: explicit final-target extraction and minimal equations."""
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve the math word problem with strict final-target extraction.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Instructions:\n"
        "- Restate exactly what final quantity is asked.\n"
        "- Classify target type as one of: total, difference, remaining, rate, ratio part, or specific entity value.\n"
        "- Use only minimal equations needed to compute that target.\n"
        "- Verify the computed value matches the asked target (not an intermediate value).\n"
        "- Provide the final answer exactly once.\n\n"
        "Output format:\n"
        "- target_type: <one short phrase>\n"
        "- equations: <minimal equations>\n"
        "- final_answer: <single numeric answer>\n"
    )


def build_tale_style_decomposition_prompt(problem_text: str) -> str:
    """Stage-3 micro-patch prompt: concise TALE-style decomposition with target check."""
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve the math word problem using concise named subquestions.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Instructions:\n"
        "- Decompose into short subquestions (Q1, Q2, ...).\n"
        "- Solve subquestions sequentially with compact arithmetic.\n"
        "- Verify the final computed value answers the exact requested target.\n"
        "- Provide the final answer exactly once.\n\n"
        "Output format:\n"
        "- decomposition: <Q1..Qn>\n"
        "- work: <concise steps>\n"
        "- target_check: <one line>\n"
        "- final_answer: <single numeric answer>\n"
    )


def build_discovery3_candidate_diversity_prompt(
    problem_text: str,
    target_quantity_type: str | None = None,
    family_hint: str | None = None,
) -> str:
    """Gold-free, prediction-free decomposition prompt for discovery3 retries."""
    text = embed_problem_for_prompt(problem_text)
    target = (target_quantity_type or "unknown").strip() or "unknown"
    fam = (family_hint or "unknown").strip() or "unknown"
    return (
        "Solve this GSM8K-style problem independently.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Discovery3 scaffold:\n"
        f"- target_quantity_type_hint: {target}\n"
        f"- family_hint: {fam}\n"
        "- First identify the exact requested final quantity.\n"
        "- Decompose into concise equations (state transitions and/or rate/ratio equations as needed).\n"
        "- Compute independently from the problem text only.\n"
        "- Verify units and target alignment before finalizing.\n"
        "- Output exactly one final-answer line at the end in this exact format:\n"
        "  FINAL_ANSWER: <number>\n"
        "- Do not put units or words after the number on the FINAL_ANSWER line.\n"
        "- Do not give multiple final answers.\n"
        "- If the answer is a fraction or decimal, put only that value.\n"
    )


def _retry_prompt_output_contract() -> str:
    return (
        "- Output exactly one final-answer line at the end in this exact format:\n"
        "  FINAL_ANSWER: <number>\n"
        "- Do not put units or words after the number on FINAL_ANSWER line.\n"
        "- Do not give multiple final answers.\n"
        "- If the answer is a fraction or decimal, put only that value.\n"
        "- If you are unsure, still output one best numeric answer on FINAL_ANSWER line.\n"
    )


def build_final_target_guarded_retry_prompt(problem_text: str) -> str:
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve this math word problem independently.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Instructions:\n"
        "- Identify the exact requested final quantity before doing arithmetic.\n"
        "- Use concise equations only.\n"
        "- Verify the computed value answers the requested final quantity, not an intermediate value.\n"
        f"{_retry_prompt_output_contract()}"
    )


def build_structural_commit_challenge_retry_prompt(problem_text: str) -> str:
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve this math word problem independently.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Instructions:\n"
        "- Identify the exact requested final quantity.\n"
        "- Solve with concise equations.\n"
        "- Challenge your own result with one short consistency check before finalizing.\n"
        f"{_retry_prompt_output_contract()}"
    )


def build_rate_table_retry_prompt(problem_text: str) -> str:
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve this math word problem independently using a compact rate table when relevant.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Instructions:\n"
        "- Identify the requested final quantity.\n"
        "- If rates/ratios are involved, organize values in a compact rate table.\n"
        "- Use concise equations and compute only the requested quantity.\n"
        f"{_retry_prompt_output_contract()}"
    )


def build_concise_decomposition_retry_prompt(problem_text: str) -> str:
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve this math word problem independently with concise decomposition.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Instructions:\n"
        "- Identify the final requested quantity.\n"
        "- Use 2-4 concise equation steps.\n"
        "- Ensure the final value corresponds to the requested quantity.\n"
        f"{_retry_prompt_output_contract()}"
    )


def _schema_grounded_output_contract() -> str:
    return (
        "Your entire response must be only the block below.\n"
        "Do not explain outside the block.\n"
        "Copy these exact labels.\n"
        "Output format (required):\n"
        "SCHEMA_TYPE: <one of: quantity_ledger_schema, rate_table_schema, before_after_state_schema, "
        "ratio_equation_schema, target_difference_schema, average_total_count_schema>\n"
        "TARGET_QUANTITY: <short phrase>\n"
        "GIVEN_QUANTITIES:\n"
        "- <name>: <value or expression>\n"
        "EQUATIONS:\n"
        "- <equation>\n"
        "COMPUTATION:\n"
        "- <step>\n"
        "FINAL_ANSWER: <number>\n"
        "Rules:\n"
        "- Do not put units or words after FINAL_ANSWER number.\n"
        "- Do not give multiple final answers.\n"
        "- If uncertain, still output one best numeric FINAL_ANSWER.\n"
        "\n"
        "Template:\n"
        "SCHEMA_TYPE:\n"
        "TARGET_QUANTITY:\n"
        "GIVEN_QUANTITIES:\n"
        "-\n"
        "EQUATIONS:\n"
        "-\n"
        "COMPUTATION:\n"
        "-\n"
        "FINAL_ANSWER:\n"
    )


def build_schema_grounded_quantity_ledger_prompt(problem_text: str) -> str:
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve this GSM8K-style problem independently using a quantity-ledger schema.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Use a ledger over given quantities, then compute the requested target.\n"
        f"{_schema_grounded_output_contract()}"
    )


def build_schema_grounded_rate_table_prompt(problem_text: str) -> str:
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve this GSM8K-style problem independently using a rate-table schema.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Represent relevant rates and quantities first, then compute the target.\n"
        f"{_schema_grounded_output_contract()}"
    )


def build_schema_grounded_state_transition_prompt(problem_text: str) -> str:
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve this GSM8K-style problem independently using before/after state transitions.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Track state updates in order and compute the requested final target.\n"
        f"{_schema_grounded_output_contract()}"
    )


def build_schema_grounded_ratio_equation_prompt(problem_text: str) -> str:
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve this GSM8K-style problem independently using a ratio-equation schema.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Translate ratio statements to equations and solve for the requested quantity.\n"
        f"{_schema_grounded_output_contract()}"
    )


def build_schema_grounded_target_difference_prompt(problem_text: str) -> str:
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve this GSM8K-style problem independently using a target-difference schema.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Identify compared quantities and compute exactly the asked difference/target.\n"
        f"{_schema_grounded_output_contract()}"
    )


def build_schema_grounded_average_total_count_prompt(problem_text: str) -> str:
    text = embed_problem_for_prompt(problem_text)
    return (
        "Solve this GSM8K-style problem independently using an average-total-count schema.\n\n"
        "Problem:\n"
        f"{text}\n\n"
        "Convert between average, total, and count explicitly, then solve the asked target.\n"
        f"{_schema_grounded_output_contract()}"
    )


@dataclass(frozen=True)
class Discovery3CandidateDiversitySelectionConfigV1:
    enable_discovery3_candidate_diversity_selection_v1: bool = False
    discovery3_max_extra_calls: int = 1
    enable_percent_base_denominator: bool = False


def build_discovery3_candidate_diversity_selection_config_v1(
    *,
    enable_discovery3_candidate_diversity_selection_v1: bool = False,
    discovery3_max_extra_calls: int = 1,
    enable_percent_base_denominator: bool = False,
) -> Discovery3CandidateDiversitySelectionConfigV1:
    return Discovery3CandidateDiversitySelectionConfigV1(
        enable_discovery3_candidate_diversity_selection_v1=bool(enable_discovery3_candidate_diversity_selection_v1),
        discovery3_max_extra_calls=max(0, int(discovery3_max_extra_calls)),
        enable_percent_base_denominator=bool(enable_percent_base_denominator),
    )


def build_discovery3_patch_metadata(
    *,
    patch_enabled: bool,
    retry_triggered: bool,
    selected_scaffold: str,
    selection_policy_applied: bool,
    selection_reason: str,
    extra_calls_planned: int,
    extra_calls_used: int = 0,
) -> dict[str, str | int | bool]:
    """Canonical metadata fields for the discovery3 opt-in patch."""
    return {
        "discovery3_patch_enabled": bool(patch_enabled),
        "discovery3_diversity_retry_triggered": bool(retry_triggered),
        "discovery3_selected_scaffold": str(selected_scaffold),
        "discovery3_selection_policy_applied": bool(selection_policy_applied),
        "discovery3_selection_reason": str(selection_reason),
        "discovery3_extra_calls_planned": int(extra_calls_planned),
        "discovery3_extra_calls_used": int(extra_calls_used),
    }


def validate_prompt_no_gold(prompt: str, gold_answer: str | None) -> bool:
    """True if the prompt does not contain the gold string and has no obvious answer leaks."""
    g = str(gold_answer or "").strip()
    if not g:
        return True
    p = prompt or ""
    if g in p:
        return False
    esc = re.escape(g)
    if re.search(r"\\boxed\{\s*" + esc + r"\s*\}", p):
        return False
    if re.search(r"(?i)\bgold\b\s*(answer)?\s*[:=]\s*" + esc, p):
        return False
    return True


def provenance_risk(row: Mapping[str, str]) -> str:
    notes = str(row.get("notes") or "")
    conf = str(row.get("derivation_confidence") or "").strip()
    cohort = str(row.get("cohort") or "").strip()
    win = str(row.get("external_winner_names") or "")
    cid = str(row.get("case_id") or "")

    if cohort == "mechanism_unknown_union":
        return "high"
    if conf == "unknown":
        return "high"
    if "reproduce_in_minimal_slice" in notes:
        return "high"
    if "present_not_selected" in notes and "851" in cid:
        return "high"
    if win and "external_l1_max" not in win:
        return "medium"
    return "low"


def dry_run_eligible(
    row: Mapping[str, str],
    *,
    anchor_ids: frozenset[str],
) -> tuple[bool, str]:
    """Return (eligible, exclusion_reason). Exclusion_reason empty if eligible."""
    cohort = str(row.get("cohort") or "").strip()
    if cohort != "gold_absent_tagged":
        return False, "not_gold_absent_tagged"
    fam = classify_family_from_row(row)
    if fam not in FIRST_COHORT_FAMILIES:
        return False, "family_not_in_first_cohort"
    pt = str(row.get("problem_text") or "").strip()
    if not pt:
        return False, "empty_problem_text"
    risk = provenance_risk(row)
    cid = str(row.get("case_id") or "")
    if risk == "high" and cid not in anchor_ids:
        return False, "high_provenance_risk_not_anchor"
    return True, ""


def order_selected_rows(rows: list[dict[str, str]], anchor_order: list[str]) -> list[dict[str, str]]:
    by_id = {r["case_id"]: r for r in rows}
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()
    for aid in anchor_order:
        if aid in by_id:
            ordered.append(by_id[aid])
            seen.add(aid)
    for k in sorted(by_id.keys()):
        if k not in seen:
            ordered.append(by_id[k])
    return ordered


@dataclass(frozen=True)
class TargetedDiscoveryRetryIntegrationConfigV1:
    enable_targeted_discovery_retry_v1: bool = False
    targeted_retry_prompt_versions: dict[str, str] = field(
        default_factory=lambda: dict(TARGETED_RETRY_RECOMMENDED_PROMPT_VERSIONS_V1)
    )
    targeted_retry_supported_families: frozenset[str] = field(
        default_factory=lambda: frozenset(TARGETED_RETRY_SUPPORTED_FAMILIES_V1)
    )
    targeted_retry_allowlist_case_ids: frozenset[str] = field(default_factory=frozenset)
    targeted_retry_max_extra_calls: int = 1
    targeted_retry_no_api_mode: bool = True


@dataclass(frozen=True)
class ProductionEquivalenceStage3Config:
    method_alias: str = (
        "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_"
        "structural_commit_v1_production_equiv_v1"
    )
    enable_structural_commit_v1: bool = True
    enable_adaptive_retry_router_v3: bool = True
    enable_final_target_verifier_v1: bool = True
    enable_targeted_retry: bool = True
    targeted_retry_max_extra_calls: int = 1
    targeted_retry_allowed_scaffolds: tuple[str, ...] = (
        "quantity_ledger_v2_1",
        "rate_table_v1",
        "before_after_state_v1",
        "target_difference_v1",
        "final_target_extraction_repair",
        "l1_style_concise_decomposition",
    )
    enable_percent_base_denominator: bool = False
    no_api_mode: bool = True
    enable_discovery3_candidate_diversity_selection_v1: bool = False


def build_targeted_discovery_retry_integration_config_v1(
    *,
    enable_targeted_discovery_retry_v1: bool = False,
    targeted_retry_allowlist_case_ids: set[str] | frozenset[str] | None = None,
    targeted_retry_no_api_mode: bool = True,
) -> TargetedDiscoveryRetryIntegrationConfigV1:
    allow = frozenset(str(x).strip() for x in (targeted_retry_allowlist_case_ids or set()) if str(x).strip())
    return TargetedDiscoveryRetryIntegrationConfigV1(
        enable_targeted_discovery_retry_v1=bool(enable_targeted_discovery_retry_v1),
        targeted_retry_allowlist_case_ids=allow,
        targeted_retry_no_api_mode=bool(targeted_retry_no_api_mode),
    )


def build_production_equivalence_stage3_config(
    *,
    enable_percent_base_denominator: bool = False,
    targeted_retry_max_extra_calls: int = 1,
    no_api_mode: bool = True,
) -> ProductionEquivalenceStage3Config:
    return ProductionEquivalenceStage3Config(
        enable_percent_base_denominator=bool(enable_percent_base_denominator),
        targeted_retry_max_extra_calls=max(0, int(targeted_retry_max_extra_calls)),
        no_api_mode=bool(no_api_mode),
    )
