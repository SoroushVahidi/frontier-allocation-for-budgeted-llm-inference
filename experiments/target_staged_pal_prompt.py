"""Target-staged PAL retry templates (offline): paths, materialization, section parse.

No API, no controller wiring. Templates live under prompts/target_staged_pal_retry/.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

VARIANT_A = "target_staged_pal_retry_v1"
VARIANT_B = "target_staged_pal_retry_no_external_v1"
VARIANT_C = "target_staged_pal_retry_oracle_external_v1"

DEPLOYABLE_VARIANTS = frozenset({VARIANT_A, VARIANT_B})
NON_DEPLOYABLE_VARIANTS = frozenset({VARIANT_C})

_PROMPT_DIR = REPO_ROOT / "prompts" / "target_staged_pal_retry"

_TEMPLATE_FILES: dict[str, str] = {
    VARIANT_A: "user_template_v1.md",
    VARIANT_B: "user_template_no_external_v1.md",
    VARIANT_C: "user_template_oracle_v1.md",
}

_REQUIRED_INSTRUCTION_HEADERS: tuple[str, ...] = (
    "TARGET:",
    "UNITS:",
    "GIVEN_QUANTITIES:",
    "SUBGOALS:",
    "CHECKS:",
    "PYTHON:",
)

_ORDERED_SECTION_KEYS: tuple[tuple[str, str], ...] = (
    ("TARGET:", "target"),
    ("UNITS:", "units"),
    ("GIVEN_QUANTITIES:", "given_quantities"),
    ("SUBGOALS:", "subgoals"),
    ("CHECKS:", "checks"),
    ("PYTHON:", "python"),
)

_LEAKAGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bschema_mining\b", re.I),
    re.compile(r"\bbaseline\b", re.I),
    re.compile(r"\btrace\b", re.I),
    re.compile(r"\boracle\b", re.I),
    re.compile(r"\bcomparator\b", re.I),
    re.compile(r"\bexternal\b", re.I),
)


def template_path(variant: str) -> Path:
    name = _TEMPLATE_FILES.get(variant)
    if not name:
        raise ValueError(f"unknown template variant: {variant!r}")
    return _PROMPT_DIR / name


def load_user_template(variant: str) -> str:
    p = template_path(variant)
    return p.read_text(encoding="utf-8")


def materialize_user_prompt(
    variant: str,
    *,
    question: str,
    oracle_hint: str = "",
) -> str:
    """Insert GSM8K question (and optional oracle hint for variant C only)."""
    body = load_user_template(variant)
    if variant == VARIANT_C:
        return (
            body.replace("{oracle_hint}", oracle_hint.strip())
            .replace("{question}", question.strip())
        )
    if variant in DEPLOYABLE_VARIANTS:
        if "{oracle_hint}" in body:
            raise ValueError("deployable template must not contain oracle placeholder")
        return body.replace("{question}", question.strip())
    raise ValueError(f"unknown template variant: {variant!r}")


def prompt_includes_required_sections_instruction(materialized_prompt: str) -> bool:
    """True if materialized user prompt documents all six section headers."""
    return all(h in materialized_prompt for h in _REQUIRED_INSTRUCTION_HEADERS)


def variant_b_leakage_violations(text: str) -> list[str]:
    """Whole-token scan for analysis-only vocabulary (variant B prompts)."""
    return [p.pattern for p in _LEAKAGE_PATTERNS if p.search(text)]


def is_deployable_variant(variant: str) -> bool:
    return variant in DEPLOYABLE_VARIANTS


def assert_deployable_pilot_variant(variant: str) -> str:
    if variant in NON_DEPLOYABLE_VARIANTS:
        raise ValueError(
            f"{variant!r} is diagnosis-only / non-deployable and cannot be selected for pilot manifests"
        )
    if variant not in DEPLOYABLE_VARIANTS:
        raise ValueError(f"unknown or unsupported pilot variant: {variant!r}")
    return variant


def resolve_pilot_manifest_template(manifest: dict[str, Any]) -> str:
    """Read a manifest dict; return validated deployable variant string."""
    v = str(manifest.get("template_variant") or manifest.get("variant") or "")
    if not v:
        raise ValueError("manifest missing template_variant")
    return assert_deployable_pilot_variant(v)


def parse_staged_model_output(text: str) -> dict[str, str]:
    """Slice six sections from a model response (gold-free)."""
    t = text.replace("\r\n", "\n")
    out: dict[str, str] = {}
    for i, (marker, key) in enumerate(_ORDERED_SECTION_KEYS):
        start = t.find(marker)
        if start == -1:
            out[key] = ""
            continue
        body_start = start + len(marker)
        if i + 1 < len(_ORDERED_SECTION_KEYS):
            next_marker = _ORDERED_SECTION_KEYS[i + 1][0]
            end = t.find(next_marker, body_start)
            body = t[body_start:end] if end != -1 else t[body_start:]
        else:
            body = t[body_start:]
        out[key] = body.strip()
    return out


def extract_python_for_pal_executor(python_section: str) -> str:
    """Strip optional fenced block; return source for experiments.pal_executor.execute_pal_code."""
    code = python_section.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        while lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines).strip()
    return code


def all_sections_present(parsed: dict[str, str]) -> bool:
    return all(bool(parsed.get(k, "").strip()) for _, k in _ORDERED_SECTION_KEYS)
