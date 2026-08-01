"""Offline audit of already-generated per-example artifacts across this repo.

Purpose: before spending more API credit, find out how much already-paid-for
per-example evidence (frontier/L1/S1/TALE answers, gold labels, FTA/Pooled-4/
External-3 decisions) already sits on local disk under `outputs/`, `docs/`,
`experiments/`, `scripts/`, and how much of it is directly reusable for
failure mining, classifier training, or validation diagnostics.

Makes zero API calls. Never deletes, overwrites, moves, or compresses any
existing output -- every artifact under `outputs/` is opened read-only. Gold
labels are used only to compute *post-hoc* correctness labels (see
`compute_post_hoc_correctness()` / `compute_candidate_result()`), never as a
runtime selector feature -- see `compute_candidate_fires()`, which is
restricted (and separately audited, `audit_fires_function_legality()`) to
runtime-legal fields only (frontier_support, the four raw answers).

Two real data shapes exist in this repo's output history and are both
handled:
  - "wide": one row per example, answer columns for all methods already
    present (e.g. `official_four_scenario_case_level_replay.csv`). Directly
    usable -- Compatibility Class A (or B if a few fields are missing).
  - "long": one row per (example_id, method) call (e.g. raw
    `per_example_records.jsonl` from `run_api_validation_repair_candidate.py`
    / `run_cohere_real_model_cost_normalized_validation.py`). Needs a pivot
    adapter (`pivot_long_rows_to_wide()`) grouping by example_id and
    collecting each of the four canonical method answers onto one row --
    Compatibility Class B.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

csv.field_size_limit(10_000_000)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = ("outputs", "docs", "experiments", "scripts")
CANDIDATE_EXTENSIONS = (".jsonl", ".csv")

# Canonical method identifiers used throughout this repo's real-API pipelines.
METHOD_FRONTIER = "direct_reserve_semantic_frontier_v2"
METHOD_L1 = "external_l1_max"
METHOD_S1 = "external_s1_budget_forcing"
METHOD_TALE = "external_tale_prompt_budgeting"
METHOD_CANONICAL_NAMES = {
    "frontier": {METHOD_FRONTIER, "frontier", "frontier_only"},
    "l1": {METHOD_L1, "l1", "l1_only", "external_l1"},
    "s1": {METHOD_S1, "s1", "s1_only", "external_s1"},
    "tale": {METHOD_TALE, "tale", "tale_only", "external_tale"},
}

# Row-count-cheaply-readable cutoff. Above this, we still discover/classify
# the file but do not read it fully into the bank (noted in the report).
MAX_ROWS_TO_BANK = 200_000

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "example_id": ("example_id", "row_id", "id"),
    "question": ("question", "question_text", "prompt", "problem"),
    "gold": ("gold_answer_canonical", "gold_answer", "gold", "answer_gold", "gold_label"),
    "frontier": ("frontier_answer_canonical", "frontier_answer", "final_answer_canonical"),
    "l1": ("l1_answer_canonical", "l1_answer", "external_l1_answer"),
    "s1": ("s1_answer_canonical", "s1_answer", "external_s1_answer"),
    "tale": ("tale_answer_canonical", "tale_answer", "external_tale_answer"),
    "fta": ("fta_selected_answer_canonical", "fta_selected_answer", "fta_answer"),
    "pooled4_precomputed": ("pooled4_answer",),
    "external3_precomputed": ("external_only_answer",),
    "frontier_support": ("frontier_support",),
    "frontier_support_margin": ("frontier_support_margin",),
    "override_reason": ("override_reason",),
    "candidate_pool_answer_group_count": ("candidate_pool_answer_group_count",),
    "provider": ("provider",),
    "dataset": ("dataset",),
    "seed": ("seed", "source_seed"),
    "budget": ("budget", "source_budget"),
    "method": ("method",),
    "parse_extraction_failure": ("parse_extraction_failure", "parse_extraction_failure_frontier"),
}

CORRECTNESS_FIELD_SUBSTRINGS = ("correct", "accuracy", "_win", "_loss")

STATUS_KEYWORDS = [
    ("smoke", "smoke"),
    ("dry_run", "dry-run"),
    ("dryrun", "dry-run"),
    ("test_", "test"),
    ("_test", "test"),
    ("diagnostic", "diagnostic"),
    ("auxiliary", "auxiliary"),
    ("canonical", "canonical"),
    ("official", "canonical"),
    ("failed", "failed"),
]

PROVIDER_KEYWORDS = ["cohere", "mistral", "azure", "cloudrift", "gemini", "cerebras", "fireworks", "vapi", "openai"]
DATASET_KEYWORDS = [("gsm8k", "gsm8k"), ("math-500", "math500"), ("math500", "math500"), ("gpqa", "gpqa")]

SEED_RE = re.compile(r"seed[_=]?(\d+)", re.IGNORECASE)
BUDGET_RE = re.compile(r"budget[_=]?(\d+)|_b(\d+)_", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Section 1: discovery
# ---------------------------------------------------------------------------


@dataclass
class ArtifactRecord:
    path: str
    size_bytes: int
    modified_utc: str
    inferred_provider: str | None
    inferred_dataset: str | None
    inferred_seed: int | None
    inferred_budget: int | None
    row_count: int | None
    schema_fields: list[str]
    has_question: bool
    has_gold: bool
    has_frontier: bool
    has_l1: bool
    has_s1: bool
    has_tale: bool
    has_fta: bool
    has_frontier_support: bool
    has_override_reason: bool
    has_correctness: bool
    shape: str  # "wide" | "long" | "other" | "unreadable"
    status_tags: list[str] = field(default_factory=list)
    compatibility_class: str = ""
    note: str = ""


def discover_candidate_paths(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        for ext in CANDIDATE_EXTENSIONS:
            paths.extend(root.rglob(f"*{ext}"))
    return sorted(set(paths))


def _lower_key_map(keys: Iterable[str]) -> dict[str, str]:
    return {k.lower(): k for k in keys}


def _first_present(lower_map: dict[str, str], row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        real_key = lower_map.get(alias.lower())
        if real_key is not None and row.get(real_key) not in (None, ""):
            return row[real_key]
    return None


def sniff_csv_header(path: Path) -> list[str] | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
        return header
    except (OSError, csv.Error):
        return None


def sniff_jsonl_first_row(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    return None
                return obj if isinstance(obj, dict) else None
    except OSError:
        return None
    return None


def _flatten_one_level(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten one level of nested dicts (e.g. `result_metadata`) so field
    detection can see FTA-style fields tucked inside a metadata blob, matching
    the auxiliary MATH-500 artifact shape documented in
    outputs/math500_cohere_failure_pool_audit_20260528/README.md."""
    flat = dict(row)
    for k, v in row.items():
        if isinstance(v, dict):
            for nested_k, nested_v in v.items():
                flat.setdefault(nested_k, nested_v)
    return flat


def count_lines_batch(paths: list[Path]) -> dict[Path, int]:
    """Fast line counts via `wc -l`, batched to bound subprocess overhead."""
    counts: dict[Path, int] = {}
    chunk_size = 300
    for i in range(0, len(paths), chunk_size):
        chunk = paths[i : i + chunk_size]
        try:
            result = subprocess.run(
                ["wc", "-l", *[str(p) for p in chunk]],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            for p in chunk:
                counts[p] = -1
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.endswith(" total"):
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            try:
                n = int(parts[0])
            except ValueError:
                continue
            counts[Path(parts[1])] = n
    for p in paths:
        counts.setdefault(p, -1)
    return counts


def infer_provider_dataset_seed_budget(rel_path: str, sample_row: dict[str, Any] | None) -> tuple[str | None, str | None, int | None, int | None]:
    lower_map = _lower_key_map(sample_row.keys()) if sample_row else {}
    provider = None
    dataset = None
    seed = None
    budget = None
    if sample_row:
        provider = _first_present(lower_map, sample_row, FIELD_ALIASES["provider"])
        dataset = _first_present(lower_map, sample_row, FIELD_ALIASES["dataset"])
        seed_val = _first_present(lower_map, sample_row, FIELD_ALIASES["seed"])
        budget_val = _first_present(lower_map, sample_row, FIELD_ALIASES["budget"])
        try:
            seed = int(seed_val) if seed_val is not None else None
        except (TypeError, ValueError):
            seed = None
        try:
            budget = int(budget_val) if budget_val is not None else None
        except (TypeError, ValueError):
            budget = None

    lower_path = rel_path.lower()
    if provider is None:
        for kw in PROVIDER_KEYWORDS:
            if kw in lower_path:
                provider = kw
                break
    if dataset is None:
        for kw, label in DATASET_KEYWORDS:
            if kw in lower_path:
                dataset = label
                break
    if seed is None:
        m = SEED_RE.search(rel_path)
        if m:
            seed = int(m.group(1))
    if budget is None:
        m = BUDGET_RE.search(rel_path)
        if m:
            budget = int(m.group(1) or m.group(2))
    return provider, dataset, seed, budget


def infer_status_tags(rel_path: str, row_count: int | None) -> list[str]:
    lower_path = rel_path.lower()
    tags = [label for kw, label in STATUS_KEYWORDS if kw in lower_path]
    if row_count == 0:
        tags.append("empty")
    if not tags:
        tags.append("unclassified")
    # de-dup while preserving order
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out


def build_artifact_record(path: Path, repo_root: Path, row_count: int | None) -> ArtifactRecord:
    rel_path = str(path.relative_to(repo_root))
    try:
        stat = path.stat()
        size_bytes = stat.st_size
        modified_utc = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        size_bytes = -1
        modified_utc = ""

    schema_fields: list[str] = []
    sample_row: dict[str, Any] | None = None
    shape = "unreadable"

    if size_bytes == 0:
        shape = "other"
    elif path.suffix.lower() == ".csv":
        header = sniff_csv_header(path)
        if header is not None:
            schema_fields = header
            sample_row = {h: "" for h in header}  # placeholder; real values not needed for schema flags
    elif path.suffix.lower() == ".jsonl":
        row = sniff_jsonl_first_row(path)
        if row is not None:
            flat = _flatten_one_level(row)
            schema_fields = list(flat.keys())
            sample_row = flat

    lower_map = _lower_key_map(schema_fields)

    def _has(alias_key: str) -> bool:
        return any(a.lower() in lower_map for a in FIELD_ALIASES[alias_key])

    has_question = _has("question")
    has_gold = _has("gold")
    has_frontier = _has("frontier")
    has_l1 = _has("l1")
    has_s1 = _has("s1")
    has_tale = _has("tale")
    has_fta = _has("fta")
    has_frontier_support = _has("frontier_support")
    has_override_reason = _has("override_reason")
    has_correctness = any(sub in fld.lower() for fld in schema_fields for sub in CORRECTNESS_FIELD_SUBSTRINGS)
    has_method_field = _has("method")

    if schema_fields:
        n_answer_cols = sum([has_frontier, has_l1, has_s1, has_tale])
        if n_answer_cols >= 3:
            shape = "wide"
        elif has_method_field:
            shape = "long"
        else:
            shape = "other"

    provider, dataset, seed, budget = infer_provider_dataset_seed_budget(rel_path, sample_row if path.suffix == ".jsonl" else None)
    status_tags = infer_status_tags(rel_path, row_count)

    return ArtifactRecord(
        path=rel_path,
        size_bytes=size_bytes,
        modified_utc=modified_utc,
        inferred_provider=provider,
        inferred_dataset=dataset,
        inferred_seed=seed,
        inferred_budget=budget,
        row_count=row_count,
        schema_fields=schema_fields,
        has_question=has_question,
        has_gold=has_gold,
        has_frontier=has_frontier,
        has_l1=has_l1,
        has_s1=has_s1,
        has_tale=has_tale,
        has_fta=has_fta,
        has_frontier_support=has_frontier_support,
        has_override_reason=has_override_reason,
        has_correctness=has_correctness,
        shape=shape,
        status_tags=status_tags,
    )


def discover_artifacts(repo_root: Path = REPO_ROOT) -> list[ArtifactRecord]:
    paths = discover_candidate_paths(repo_root)
    counts = count_lines_batch(paths)
    records = []
    for p in paths:
        rc = counts.get(p)
        row_count = None if rc is None or rc < 0 else (rc - 1 if p.suffix.lower() == ".csv" and rc > 0 else rc)
        records.append(build_artifact_record(p, repo_root, row_count))
    return records


# ---------------------------------------------------------------------------
# Section 2: compatibility classification
# ---------------------------------------------------------------------------


def classify_compatibility(rec: ArtifactRecord) -> str:
    if rec.row_count in (None, 0) or rec.shape == "unreadable":
        return "E"
    core_answers = [rec.has_frontier, rec.has_l1, rec.has_s1, rec.has_tale]
    n_answers = sum(core_answers)

    if rec.shape == "wide":
        if rec.has_question and rec.has_gold and n_answers == 4 and rec.has_frontier_support:
            return "A"
        if rec.has_gold and n_answers >= 2:
            return "B"
        if rec.has_question or rec.has_override_reason:
            return "C"
        if rec.inferred_provider and rec.inferred_dataset:
            return "D"
        return "E"

    if rec.shape == "long":
        # Needs pivot-by-example_id adapter; treat as compatible-after-adapter
        # whenever gold + question + example_id-ish are present in the row.
        if rec.has_question and rec.has_gold:
            return "B"
        if rec.has_question or rec.has_override_reason:
            return "C"
        if rec.inferred_provider and rec.inferred_dataset:
            return "D"
        return "E"

    # shape == "other"
    if rec.has_question or rec.has_override_reason:
        return "C"
    if rec.inferred_provider or rec.inferred_dataset:
        return "D"
    return "E"


# ---------------------------------------------------------------------------
# Section 3: bank building (normalization, pivot adapter, derived fields)
# ---------------------------------------------------------------------------


def normalize_answer(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    text = text.lower().rstrip(".").strip()
    try:
        return format(float(text.replace(",", "")), ".10g")
    except ValueError:
        return text


def pooled4_plurality_vote(frontier: Any, l1: Any, s1: Any, tale: Any) -> str | None:
    """Simple normalized-plurality vote across the 4 raw answers. Standalone,
    read-only reimplementation for inventory purposes only -- does not call
    and is not called by any canonical selector code."""
    norm = [normalize_answer(v) for v in (frontier, l1, s1, tale)]
    norm = [v for v in norm if v is not None]
    if not norm:
        return None
    counts: dict[str, int] = defaultdict(int)
    for v in norm:
        counts[v] += 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    if len(ranked) == 1:
        return ranked[0][0]
    if ranked[0][1] > ranked[1][1]:
        return ranked[0][0]
    return None  # tie at the top -- abstain


def external3_strict_majority(l1: Any, s1: Any, tale: Any) -> str | None:
    norm = [normalize_answer(v) for v in (l1, s1, tale)]
    norm = [v for v in norm if v is not None]
    counts: dict[str, int] = defaultdict(int)
    for v in norm:
        counts[v] += 1
    for value, c in counts.items():
        if c >= 2:
            return value
    return None


def compute_candidate_fires(frontier_support: Any, pooled4_answer: str | None, fta_answer: Any) -> bool:
    """Runtime-legal-only reimplementation of the pooled4_fs_le1_notie
    candidate's firing condition (see
    outputs/failure_analysis/pooled4_fs_le1_candidate_freeze_20260709T015058Z/
    POOLED4_FS_LE1_NOTIE_CANDIDATE_SPEC.md): unique Pooled-4 plurality winner,
    frontier_support <= 1, and it differs from FTA's answer.

    Deliberately takes no gold/correctness argument -- see
    audit_fires_function_legality() below, which greps this function's own
    source for forbidden substrings to keep that guarantee auditable.
    """
    if pooled4_answer is None:
        return False
    try:
        fs = float(frontier_support)
    except (TypeError, ValueError):
        return False
    if fs > 1:
        return False
    fta_norm = normalize_answer(fta_answer)
    if fta_norm is None:
        return False
    return pooled4_answer != fta_norm


FORBIDDEN_FIELD_SUBSTRINGS = ("gold", "correct")


def audit_fires_function_legality() -> dict[str, Any]:
    src = inspect.getsource(compute_candidate_fires)
    # Strip the docstring/comments before scanning so English prose mentioning
    # "gold"/"correct" (which explains the guarantee) doesn't self-trigger.
    code_only_lines = []
    in_docstring = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith('"""'):
            in_docstring = not in_docstring
            continue
        if in_docstring or stripped.startswith("#"):
            continue
        code_only_lines.append(line)
    code_only = "\n".join(code_only_lines)
    found = [s for s in FORBIDDEN_FIELD_SUBSTRINGS if s in code_only.lower()]
    return {"function": "compute_candidate_fires", "is_runtime_legal": len(found) == 0, "forbidden_substrings_found": found}


def compute_post_hoc_correctness(answer: Any, gold: Any) -> bool | None:
    """Post-hoc only -- must never feed compute_candidate_fires()."""
    a = normalize_answer(answer)
    g = normalize_answer(gold)
    if a is None or g is None:
        return None
    return a == g


def compute_candidate_result(fires: bool, pooled4_correct: bool | None, fta_correct: bool | None) -> str:
    if not fires:
        return "not_fired"
    if pooled4_correct is None or fta_correct is None:
        return "unknown_gold_missing"
    if pooled4_correct and not fta_correct:
        return "win"
    if fta_correct and not pooled4_correct:
        return "loss"
    return "tie"


ARTIFACT_QUALITY_RANK = {"canonical": 0, "auxiliary": 1, "diagnostic": 2, "smoke": 3, "dry-run": 3, "test": 4, "unclassified": 5}


def artifact_quality_label(status_tags: list[str]) -> str:
    for tag in ("canonical", "auxiliary", "diagnostic", "smoke", "dry-run", "test"):
        if tag in status_tags:
            return tag
    return "unclassified"


BANK_FIELDS = [
    "source_artifact_path",
    "provider",
    "dataset",
    "seed",
    "budget",
    "example_id",
    "question_hash",
    "normalized_question_text_hash",
    "question",
    "gold",
    "frontier_answer",
    "l1_answer",
    "s1_answer",
    "tale_answer",
    "fta_answer",
    "pooled4_answer",
    "external3_answer",
    "frontier_support",
    "frontier_support_margin",
    "override_reason",
    "candidate_pool_answer_group_count",
    "parser_flags",
    "frontier_correct",
    "l1_correct",
    "s1_correct",
    "tale_correct",
    "fta_correct",
    "pooled4_correct",
    "external3_correct",
    "pooled4_differs_from_fta",
    "pooled4_fixes_fta",
    "pooled4_regresses_fta",
    "candidate_fires",
    "candidate_result",
    "artifact_quality",
    "canonical_or_diagnostic",
    "dedup_key",
]


def _question_hash(question: str | None) -> tuple[str | None, str | None]:
    if not question:
        return None, None
    raw_hash = hashlib.sha256(question.encode("utf-8", errors="replace")).hexdigest()[:16]
    normalized = re.sub(r"\s+", " ", question.strip().lower())
    norm_hash = hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:16]
    return raw_hash, norm_hash


def _build_bank_row(
    *,
    source_artifact_path: str,
    provider: str | None,
    dataset: str | None,
    seed: int | None,
    budget: int | None,
    example_id: Any,
    question: Any,
    gold: Any,
    frontier: Any,
    l1: Any,
    s1: Any,
    tale: Any,
    fta: Any,
    frontier_support: Any,
    frontier_support_margin: Any,
    override_reason: Any,
    candidate_pool_answer_group_count: Any,
    parser_flags: Any,
    artifact_quality: str,
) -> dict[str, Any]:
    q_hash, norm_q_hash = _question_hash(str(question) if question else None)
    pooled4 = pooled4_plurality_vote(frontier, l1, s1, tale)
    external3 = external3_strict_majority(l1, s1, tale)

    frontier_correct = compute_post_hoc_correctness(frontier, gold)
    l1_correct = compute_post_hoc_correctness(l1, gold)
    s1_correct = compute_post_hoc_correctness(s1, gold)
    tale_correct = compute_post_hoc_correctness(tale, gold)
    fta_correct = compute_post_hoc_correctness(fta, gold) if fta is not None else None
    pooled4_correct = compute_post_hoc_correctness(pooled4, gold) if pooled4 is not None else None
    external3_correct = compute_post_hoc_correctness(external3, gold) if external3 is not None else None

    fta_norm = normalize_answer(fta)
    pooled4_differs_from_fta = (pooled4 is not None and fta_norm is not None and pooled4 != fta_norm)
    pooled4_fixes_fta = bool(pooled4_differs_from_fta and pooled4_correct and fta_correct is False)
    pooled4_regresses_fta = bool(pooled4_differs_from_fta and fta_correct and pooled4_correct is False)

    fires = compute_candidate_fires(frontier_support, pooled4, fta)
    result = compute_candidate_result(fires, pooled4_correct, fta_correct)

    if norm_q_hash:
        dedup_key = f"qhash:{norm_q_hash}"
    elif example_id not in (None, ""):
        dedup_key = f"eid:{provider}|{dataset}|{seed}|{example_id}"
    else:
        dedup_key = f"nokey:{source_artifact_path}"

    return {
        "source_artifact_path": source_artifact_path,
        "provider": provider,
        "dataset": dataset,
        "seed": seed,
        "budget": budget,
        "example_id": example_id,
        "question_hash": q_hash,
        "normalized_question_text_hash": norm_q_hash,
        "question": question,
        "gold": gold,
        "frontier_answer": frontier,
        "l1_answer": l1,
        "s1_answer": s1,
        "tale_answer": tale,
        "fta_answer": fta,
        "pooled4_answer": pooled4,
        "external3_answer": external3,
        "frontier_support": frontier_support,
        "frontier_support_margin": frontier_support_margin,
        "override_reason": override_reason,
        "candidate_pool_answer_group_count": candidate_pool_answer_group_count,
        "parser_flags": parser_flags,
        "frontier_correct": frontier_correct,
        "l1_correct": l1_correct,
        "s1_correct": s1_correct,
        "tale_correct": tale_correct,
        "fta_correct": fta_correct,
        "pooled4_correct": pooled4_correct,
        "external3_correct": external3_correct,
        "pooled4_differs_from_fta": pooled4_differs_from_fta,
        "pooled4_fixes_fta": pooled4_fixes_fta,
        "pooled4_regresses_fta": pooled4_regresses_fta,
        "candidate_fires": fires,
        "candidate_result": result,
        "artifact_quality": artifact_quality,
        "canonical_or_diagnostic": artifact_quality,
        "dedup_key": dedup_key,
    }


def read_wide_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            return list(csv.DictReader(fh))
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(_flatten_one_level(obj))
    return rows


def pivot_long_rows_to_wide(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapter for Class-B 'long' artifacts: one row per (example_id, method)
    -> one row per example_id with all four method answers as columns."""
    groups: dict[Any, dict[str, Any]] = {}
    for row in rows:
        lower_map = _lower_key_map(row.keys())
        eid = _first_present(lower_map, row, FIELD_ALIASES["example_id"])
        if eid is None:
            eid = _first_present(lower_map, row, FIELD_ALIASES["question"])
        if eid is None:
            continue
        method_raw = _first_present(lower_map, row, FIELD_ALIASES["method"])
        method_key = None
        for canon, aliases in METHOD_CANONICAL_NAMES.items():
            if method_raw in aliases:
                method_key = canon
                break
        group = groups.setdefault(eid, {"__methods__": {}})
        for target, aliases in (
            ("question", FIELD_ALIASES["question"]),
            ("gold", FIELD_ALIASES["gold"]),
            ("provider", FIELD_ALIASES["provider"]),
            ("dataset", FIELD_ALIASES["dataset"]),
            ("seed", FIELD_ALIASES["seed"]),
            ("budget", FIELD_ALIASES["budget"]),
            ("fta", FIELD_ALIASES["fta"]),
            ("frontier_support", FIELD_ALIASES["frontier_support"]),
            ("frontier_support_margin", FIELD_ALIASES["frontier_support_margin"]),
            ("override_reason", FIELD_ALIASES["override_reason"]),
            ("candidate_pool_answer_group_count", FIELD_ALIASES["candidate_pool_answer_group_count"]),
        ):
            val = _first_present(lower_map, row, aliases)
            if val is not None and group.get(target) is None:
                group[target] = val
        if method_key is not None:
            answer = _first_present(
                lower_map,
                row,
                ("selected_answer_canonical", "final_answer_canonical", "final_answer_raw", "selected_answer_raw"),
            )
            if answer is not None:
                group["__methods__"][method_key] = answer
        group.setdefault("example_id", eid)
    wide_rows = []
    for eid, group in groups.items():
        methods = group.pop("__methods__")
        group["frontier"] = methods.get("frontier")
        group["l1"] = methods.get("l1")
        group["s1"] = methods.get("s1")
        group["tale"] = methods.get("tale")
        wide_rows.append(group)
    return wide_rows


def extract_wide_bank_rows(rec: ArtifactRecord, repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / rec.path
    raw_rows = read_wide_rows(path)
    if rec.shape == "long":
        raw_rows = pivot_long_rows_to_wide(raw_rows)

    quality = artifact_quality_label(rec.status_tags)
    out = []
    for row in raw_rows:
        lower_map = _lower_key_map(row.keys())
        if rec.shape == "long":
            frontier, l1, s1, tale = row.get("frontier"), row.get("l1"), row.get("s1"), row.get("tale")
            question = row.get("question")
            gold = row.get("gold")
            fta = row.get("fta")
            example_id = row.get("example_id")
            frontier_support = row.get("frontier_support")
            frontier_support_margin = row.get("frontier_support_margin")
            override_reason = row.get("override_reason")
            cpagc = row.get("candidate_pool_answer_group_count")
            provider = row.get("provider") or rec.inferred_provider
            dataset = row.get("dataset") or rec.inferred_dataset
            seed = row.get("seed") or rec.inferred_seed
            budget = row.get("budget") or rec.inferred_budget
        else:
            example_id = _first_present(lower_map, row, FIELD_ALIASES["example_id"])
            question = _first_present(lower_map, row, FIELD_ALIASES["question"])
            gold = _first_present(lower_map, row, FIELD_ALIASES["gold"])
            frontier = _first_present(lower_map, row, FIELD_ALIASES["frontier"])
            l1 = _first_present(lower_map, row, FIELD_ALIASES["l1"])
            s1 = _first_present(lower_map, row, FIELD_ALIASES["s1"])
            tale = _first_present(lower_map, row, FIELD_ALIASES["tale"])
            fta = _first_present(lower_map, row, FIELD_ALIASES["fta"])
            frontier_support = _first_present(lower_map, row, FIELD_ALIASES["frontier_support"])
            frontier_support_margin = _first_present(lower_map, row, FIELD_ALIASES["frontier_support_margin"])
            override_reason = _first_present(lower_map, row, FIELD_ALIASES["override_reason"])
            cpagc = _first_present(lower_map, row, FIELD_ALIASES["candidate_pool_answer_group_count"])
            provider = _first_present(lower_map, row, FIELD_ALIASES["provider"]) or rec.inferred_provider
            dataset = _first_present(lower_map, row, FIELD_ALIASES["dataset"]) or rec.inferred_dataset
            seed_val = _first_present(lower_map, row, FIELD_ALIASES["seed"])
            budget_val = _first_present(lower_map, row, FIELD_ALIASES["budget"])
            seed = seed_val if seed_val is not None else rec.inferred_seed
            budget = budget_val if budget_val is not None else rec.inferred_budget

        if question is None and example_id is None:
            continue
        parser_flags = _first_present(lower_map, row, FIELD_ALIASES["parse_extraction_failure"]) if rec.shape != "long" else None

        out.append(
            _build_bank_row(
                source_artifact_path=rec.path,
                provider=provider,
                dataset=dataset,
                seed=seed,
                budget=budget,
                example_id=example_id,
                question=question,
                gold=gold,
                frontier=frontier,
                l1=l1,
                s1=s1,
                tale=tale,
                fta=fta,
                frontier_support=frontier_support,
                frontier_support_margin=frontier_support_margin,
                override_reason=override_reason,
                candidate_pool_answer_group_count=cpagc,
                parser_flags=parser_flags,
                artifact_quality=quality,
            )
        )
    return out


def build_global_bank(records: list[ArtifactRecord], repo_root: Path = REPO_ROOT) -> tuple[list[dict[str, Any]], list[str]]:
    all_rows: list[dict[str, Any]] = []
    skipped_too_large: list[str] = []
    for rec in records:
        if rec.compatibility_class not in ("A", "B"):
            continue
        if rec.row_count is None or rec.row_count > MAX_ROWS_TO_BANK:
            skipped_too_large.append(rec.path)
            continue
        try:
            rows = extract_wide_bank_rows(rec, repo_root)
        except (OSError, csv.Error, UnicodeDecodeError):
            continue
        all_rows.extend(rows)
    return all_rows, skipped_too_large


def dedupe_bank(all_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        groups[row["dedup_key"]].append(row)

    def completeness(row: dict[str, Any]) -> int:
        return sum(1 for f in BANK_FIELDS if row.get(f) not in (None, ""))

    deduped: list[dict[str, Any]] = []
    duplicate_map_rows: list[dict[str, Any]] = []
    for key, rows in groups.items():
        ranked = sorted(
            rows,
            key=lambda r: (ARTIFACT_QUALITY_RANK.get(r["artifact_quality"], 9), -completeness(r)),
        )
        kept = ranked[0]
        deduped.append(kept)
        if len(rows) > 1:
            for r in rows:
                duplicate_map_rows.append(
                    {
                        "dedup_key": key,
                        "source_artifact_path": r["source_artifact_path"],
                        "example_id": r["example_id"],
                        "is_kept": r is kept,
                        "group_size": len(rows),
                    }
                )
    return deduped, duplicate_map_rows


# ---------------------------------------------------------------------------
# Section 4+: counting and narrative report generation live in main() below,
# operating purely on the already-computed records / bank (no new I/O).
# ---------------------------------------------------------------------------


def count_by(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(k) for k in keys)].append(row)
    out = []
    for key_vals, group_rows in sorted(groups.items(), key=lambda kv: [str(x) for x in kv[0]]):
        n = len(group_rows)
        oracle_correct = sum(
            1
            for r in group_rows
            if any(r.get(f) for f in ("frontier_correct", "l1_correct", "s1_correct", "tale_correct"))
        )
        all_wrong = sum(
            1
            for r in group_rows
            if all(r.get(f) is False for f in ("frontier_correct", "l1_correct", "s1_correct", "tale_correct"))
        )
        entry = dict(zip(keys, key_vals))
        entry.update(
            {
                "total_examples": n,
                "unique_examples": len({r["dedup_key"] for r in group_rows}),
                "fta_failures": sum(1 for r in group_rows if r.get("fta_correct") is False),
                "pooled4_failures": sum(1 for r in group_rows if r.get("pooled4_correct") is False),
                "external3_failures": sum(1 for r in group_rows if r.get("external3_correct") is False),
                "oracle_correct": oracle_correct,
                "all_methods_wrong": all_wrong,
                "fta_wrong_pooled4_correct": sum(1 for r in group_rows if r.get("fta_correct") is False and r.get("pooled4_correct")),
                "fta_correct_pooled4_wrong": sum(1 for r in group_rows if r.get("fta_correct") and r.get("pooled4_correct") is False),
                "pooled4_differs_from_fta": sum(1 for r in group_rows if r.get("pooled4_differs_from_fta")),
                "candidate_action_region": sum(1 for r in group_rows if r.get("candidate_fires")),
                "candidate_wins": sum(1 for r in group_rows if r.get("candidate_result") == "win"),
                "candidate_losses": sum(1 for r in group_rows if r.get("candidate_result") == "loss"),
                "candidate_ties": sum(1 for r in group_rows if r.get("candidate_result") == "tie"),
                "missing_gold": sum(1 for r in group_rows if r.get("gold") in (None, "")),
                "missing_frontier_support": sum(1 for r in group_rows if r.get("frontier_support") in (None, "")),
            }
        )
        out.append(entry)
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    fieldnames = fieldnames or (list(rows[0].keys()) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str, ensure_ascii=True) + "\n")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def artifact_record_to_dict(rec: ArtifactRecord) -> dict[str, Any]:
    d = dict(rec.__dict__)
    d["schema_fields"] = ";".join(rec.schema_fields)
    d["status_tags"] = ";".join(rec.status_tags)
    return d


def main() -> int:
    global MAX_ROWS_TO_BANK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="New, non-existing output directory to create.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--max-rows-to-bank", type=int, default=MAX_ROWS_TO_BANK)
    args = parser.parse_args()

    MAX_ROWS_TO_BANK = args.max_rows_to_bank

    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to write into an existing directory: {output_dir}")
    output_dir.mkdir(parents=True)

    legality = audit_fires_function_legality()
    if not legality["is_runtime_legal"]:
        raise RuntimeError(f"compute_candidate_fires() legality audit failed: {legality}")

    # --- Step 1: discovery
    records = discover_artifacts(repo_root)
    for rec in records:
        rec.compatibility_class = classify_compatibility(rec)

    write_csv(output_dir / "ARTIFACT_DISCOVERY_TABLE.csv", [artifact_record_to_dict(r) for r in records])
    write_jsonl(output_dir / "ARTIFACT_DISCOVERY_TABLE.jsonl", [artifact_record_to_dict(r) for r in records])

    by_status: dict[str, int] = defaultdict(int)
    for r in records:
        by_status[artifact_quality_label(r.status_tags)] += 1
    discovery_lines = [
        "# Artifact Discovery Report",
        "",
        f"Scanned roots: {', '.join(SCAN_ROOTS)} (extensions: {', '.join(CANDIDATE_EXTENSIONS)})",
        f"Total artifacts discovered: {len(records)}",
        "",
        "## By artifact-quality tag",
        "",
    ] + [f"- {k}: {v}" for k, v in sorted(by_status.items(), key=lambda kv: -kv[1])]
    write_text(output_dir / "ARTIFACT_DISCOVERY_REPORT.md", "\n".join(discovery_lines) + "\n")

    # --- Step 2: compatibility classification
    write_csv(output_dir / "ARTIFACT_COMPATIBILITY_MATRIX.csv", [artifact_record_to_dict(r) for r in records])
    by_class: dict[str, int] = defaultdict(int)
    for r in records:
        by_class[r.compatibility_class] += 1
    compat_lines = [
        "# Artifact Compatibility Report",
        "",
        "A = directly compatible; B = compatible after schema/pivot adapter; "
        "C = qualitative taxonomy only; D = provider/dataset regime analysis only; "
        "E = incomplete/empty/not usable; F = duplicate (resolved during dedup, see bank build report).",
        "",
    ] + [f"- Class {k}: {v}" for k, v in sorted(by_class.items())]
    write_text(output_dir / "ARTIFACT_COMPATIBILITY_REPORT.md", "\n".join(compat_lines) + "\n")

    # --- Step 3: bank building
    all_rows, skipped_too_large = build_global_bank(records, repo_root)
    deduped, duplicate_map_rows = dedupe_bank(all_rows)

    if all_rows:
        write_csv(output_dir / "GLOBAL_FAILURE_BANK_ALL_ROWS.csv", all_rows, BANK_FIELDS)
        write_csv(output_dir / "GLOBAL_FAILURE_BANK_DEDUPED.csv", deduped, BANK_FIELDS)
    else:
        write_text(output_dir / "GLOBAL_FAILURE_BANK_ALL_ROWS.csv", ",".join(BANK_FIELDS) + "\n")
        write_text(output_dir / "GLOBAL_FAILURE_BANK_DEDUPED.csv", ",".join(BANK_FIELDS) + "\n")
    if duplicate_map_rows:
        write_csv(output_dir / "GLOBAL_FAILURE_BANK_DUPLICATE_MAP.csv", duplicate_map_rows)
    else:
        write_text(output_dir / "GLOBAL_FAILURE_BANK_DUPLICATE_MAP.csv", "dedup_key,source_artifact_path,example_id,is_kept,group_size\n")

    write_jsonl(output_dir / "GLOBAL_FAILURE_BANK_SCHEMA.json".replace(".json", ".jsonl"), [{"fields": BANK_FIELDS}])
    (output_dir / "GLOBAL_FAILURE_BANK_SCHEMA.json").write_text(json.dumps({"fields": BANK_FIELDS}, indent=2) + "\n", encoding="utf-8")

    bank_report_lines = [
        "# Global Failure Bank Build Report",
        "",
        f"Class A/B artifacts considered: {sum(1 for r in records if r.compatibility_class in ('A', 'B'))}",
        f"Artifacts skipped (row_count > {MAX_ROWS_TO_BANK} or unknown): {len(skipped_too_large)}",
        f"Total rows extracted (all sources, pre-dedup): {len(all_rows)}",
        f"Unique rows after dedup: {len(deduped)}",
        f"Duplicate groups (size > 1): {sum(1 for _ in {r['dedup_key'] for r in duplicate_map_rows})}",
        "",
        "Dedup key priority: normalized-question-hash > (provider,dataset,seed,example_id) > "
        "no-key (path-scoped, cannot be deduped against other artifacts).",
        "",
        "Note: FTA/Pooled-4/External-3 answers are read directly from source artifacts when present; "
        "this tool does not recompute FTA (that requires the live selector implementation in "
        "experiments/support_aware_selector.py, out of scope for a read-only inventory). Pooled-4 and "
        "External-3 are recomputed here with a standalone normalized-vote function "
        "(pooled4_plurality_vote / external3_strict_majority) when not already present in the source row.",
    ]
    if skipped_too_large:
        bank_report_lines += ["", "## Artifacts skipped as too large to bank (counted in discovery only)", ""]
        bank_report_lines += [f"- {p}" for p in skipped_too_large[:50]]
        if len(skipped_too_large) > 50:
            bank_report_lines.append(f"- ... and {len(skipped_too_large) - 50} more")
    write_text(output_dir / "GLOBAL_FAILURE_BANK_BUILD_REPORT.md", "\n".join(bank_report_lines) + "\n")

    # --- Step 4: counts
    by_artifact = count_by(deduped, ("source_artifact_path",))
    by_provider_dataset = count_by(deduped, ("provider", "dataset", "seed"))
    write_csv(output_dir / "GLOBAL_FAILURE_COUNTS_BY_ARTIFACT.csv", by_artifact)
    write_csv(output_dir / "GLOBAL_FAILURE_COUNTS_BY_PROVIDER_DATASET.csv", by_provider_dataset)

    total_unique = len(deduped)
    total_action_region = sum(1 for r in deduped if r.get("candidate_fires"))
    total_wins = sum(1 for r in deduped if r.get("candidate_result") == "win")
    total_losses = sum(1 for r in deduped if r.get("candidate_result") == "loss")
    counts_summary_lines = [
        "# Global Failure Counts Summary",
        "",
        f"- Unique deduped examples across all compatible artifacts: {total_unique}",
        f"- FTA failures: {sum(1 for r in deduped if r.get('fta_correct') is False)}",
        f"- Pooled-4 failures: {sum(1 for r in deduped if r.get('pooled4_correct') is False)}",
        f"- External-3 failures: {sum(1 for r in deduped if r.get('external3_correct') is False)}",
        f"- Oracle-correct (selector-fixable) cases: {sum(1 for r in deduped if any(r.get(f) for f in ('frontier_correct','l1_correct','s1_correct','tale_correct')))}",
        f"- All-methods-wrong cases: {sum(1 for r in deduped if all(r.get(f) is False for f in ('frontier_correct','l1_correct','s1_correct','tale_correct')))}",
        f"- FTA wrong AND Pooled-4 correct: {sum(1 for r in deduped if r.get('fta_correct') is False and r.get('pooled4_correct'))}",
        f"- FTA correct AND Pooled-4 wrong (regression): {sum(1 for r in deduped if r.get('fta_correct') and r.get('pooled4_correct') is False)}",
        f"- Pooled-4 differs from FTA: {sum(1 for r in deduped if r.get('pooled4_differs_from_fta'))}",
        f"- pooled4_fs_le1_notie action-region cases (fires=True): {total_action_region}",
        f"- current-candidate wins: {total_wins}",
        f"- current-candidate losses: {total_losses}",
        f"- current-candidate ties: {sum(1 for r in deduped if r.get('candidate_result') == 'tie')}",
        f"- missing gold: {sum(1 for r in deduped if r.get('gold') in (None, ''))}",
        f"- missing frontier_support: {sum(1 for r in deduped if r.get('frontier_support') in (None, ''))}",
    ]
    write_text(output_dir / "GLOBAL_FAILURE_COUNTS_SUMMARY.md", "\n".join(counts_summary_lines) + "\n")

    # --- Step 5: underused already-paid data
    n_direct = sum(1 for r in records if r.compatibility_class == "A")
    n_adapter = sum(1 for r in records if r.compatibility_class == "B")
    n_math500 = sum(1 for r in deduped if (r.get("dataset") or "").lower() in ("math500", "math-500"))
    n_gsm8k = sum(1 for r in deduped if (r.get("dataset") or "").lower() == "gsm8k")
    providers_seen = sorted({r.get("provider") for r in deduped if r.get("provider")})
    underused_lines = [
        "# Underused Already-Paid Failure Cases Report",
        "",
        f"- Are there more useful failure cases already available? "
        f"{'Yes' if total_unique > 0 else 'No new evidence found beyond what is already documented.'} "
        f"({total_unique} unique deduped examples recovered from local disk, zero new API calls.)",
        f"- Directly usable for the current GSM8K-style selector replay (Class A artifacts): {n_direct} artifacts.",
        f"- Usable after schema adapters (Class B, long->wide pivot or partial-field): {n_adapter} artifacts.",
        f"- MATH-500 / other-dataset diagnostic unique examples in the deduped bank: {n_math500} (MATH-500-labeled) "
        f"of {total_unique} total; GSM8K-labeled: {n_gsm8k}.",
        f"- Provider-generalization cases (providers observed in the deduped bank): {', '.join(providers_seen) if providers_seen else 'none detected'}.",
        "- Which artifacts should be imported into future failure mining: see top-ranked rows in "
        "GLOBAL_FAILURE_COUNTS_BY_ARTIFACT.csv (highest unique_examples + candidate_action_region, Class A/B only).",
        "- Which should be excluded: Class E (empty/incomplete) and Class F/duplicate-losers "
        "(see GLOBAL_FAILURE_BANK_DUPLICATE_MAP.csv, is_kept=False rows).",
        "- Duplicates: see GLOBAL_FAILURE_BANK_DUPLICATE_MAP.csv for the full group-membership map (nothing silently dropped).",
        "- Field-quality problems: see 'missing gold' / 'missing frontier_support' counts in GLOBAL_FAILURE_COUNTS_SUMMARY.md, "
        "and ARTIFACT_COMPATIBILITY_MATRIX.csv columns has_fta / has_frontier_support / has_override_reason per artifact.",
    ]
    write_text(output_dir / "UNDERUSED_ALREADY_PAID_FAILURE_CASES_REPORT.md", "\n".join(underused_lines) + "\n")

    # --- Step 6: relevance to current bottleneck
    relevance_lines = [
        "# Relevance To Current Generalization Bottleneck",
        "",
        f"- More FTA failures: {sum(1 for r in deduped if r.get('fta_correct') is False)} available offline (no new API calls).",
        f"- More Pooled-4 vs FTA disagreement cases: {sum(1 for r in deduped if r.get('pooled4_differs_from_fta'))}.",
        f"- More current-rule (pooled4_fs_le1_notie) action-region cases: {total_action_region} "
        f"({total_wins} win / {total_losses} loss / {sum(1 for r in deduped if r.get('candidate_result') == 'tie')} tie among them).",
        f"- More Pooled-4 regression cases (FTA correct, Pooled-4 wrong): "
        f"{sum(1 for r in deduped if r.get('fta_correct') and r.get('pooled4_correct') is False)}.",
        f"- Provider generalization: {len(providers_seen)} distinct providers represented in the deduped bank ({', '.join(providers_seen) if providers_seen else 'none'}).",
        f"- Dataset generalization: GSM8K={n_gsm8k}, MATH-500={n_math500}, other="
        f"{total_unique - n_gsm8k - n_math500}.",
        "- Failure-class interpretation: qualitative-only (Class C) artifacts contribute taxonomy context but not row-level bank entries; see ARTIFACT_COMPATIBILITY_REPORT.md.",
        "- Synthetic/stress-test design: Class D (regime/aggregate-only) artifacts are useful for calibrating provider/dataset-level expectations, not row-level mining.",
        "- Information Sciences manuscript evidence: none of this offline audit changes or extends manuscript claims; "
        "it only inventories what already exists for future, separately-authorized mining/validation work.",
    ]
    write_text(output_dir / "RELEVANCE_TO_CURRENT_GENERALIZATION_BOTTLENECK.md", "\n".join(relevance_lines) + "\n")

    # --- Step 7: final recommendation
    ranked_artifacts = sorted(
        by_artifact,
        key=lambda r: (r.get("candidate_action_region", 0), r.get("unique_examples", 0)),
        reverse=True,
    )
    top10 = ranked_artifacts[:10]
    final_lines = [
        "# Final Existing-Failure-Case Inventory Summary",
        "",
        f"- Artifacts discovered: {len(records)}",
        f"- Directly usable artifacts (Class A): {n_direct}",
        f"- Usable-after-adapter artifacts (Class B): {n_adapter}",
        f"- Unique examples in deduped global bank: {total_unique}",
        f"- Unique action-region cases (pooled4_fs_le1_notie fires): {total_action_region}",
        f"- Unique Pooled-4-vs-FTA disagreement cases: {sum(1 for r in deduped if r.get('pooled4_differs_from_fta'))}",
        "",
        "## Top 10 most valuable artifacts (by action-region cases, then unique examples)",
        "",
    ]
    for r in top10:
        final_lines.append(
            f"- `{r['source_artifact_path']}`: unique={r.get('unique_examples', 0)}, "
            f"action_region={r.get('candidate_action_region', 0)}, fta_failures={r.get('fta_failures', 0)}"
        )
    final_lines += [
        "",
        f"## Do we need new API calls immediately?",
        "",
        ("No — " if total_unique > 0 else "Likely yes — ")
        + f"{total_unique} unique examples with FTA/Pooled-4/External-3 fields already exist locally at zero additional cost.",
        "",
        "## Recommended next offline mining task",
        "",
        "Mine the deduped global bank (GLOBAL_FAILURE_BANK_DEDUPED.csv) for pooled4_fs_le1_notie action-region "
        "cases and Pooled-4-vs-FTA disagreements across providers/datasets not yet covered by the frozen "
        "candidate's offline calibration corpora, before authorizing further live validation spend.",
        "",
        "## What NOT to mix into canonical validation",
        "",
        "Do not merge Class C/D/E artifacts, smoke/dry-run/test-tagged rows, or duplicate-loser rows "
        "(GLOBAL_FAILURE_BANK_DUPLICATE_MAP.csv, is_kept=False) into any canonical validation split. "
        "Do not treat recomputed Pooled-4/External-3 values as ground truth for provenance where the "
        "source artifact already ships its own precomputed pooled4_answer/external_only_answer column "
        "(cross-check before use).",
        "",
        "## Decision table",
        "",
        "| Class | Action |",
        "|---|---|",
        "| A | Use immediately in offline mining |",
        "| B | Use after schema adapter (pivot_long_rows_to_wide already applied here) |",
        "| C | Use only as diagnostic / qualitative taxonomy |",
        "| D | Use only as diagnostic / provider-dataset regime context |",
        "| E | Archive/ignore |",
        "| F (duplicate-loser) | Requires no action (already resolved in dedup; kept in DUPLICATE_MAP for traceability) |",
    ]
    write_text(output_dir / "FINAL_EXISTING_FAILURE_CASE_INVENTORY_SUMMARY.md", "\n".join(final_lines) + "\n")

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "artifacts_discovered": len(records),
                "class_a": n_direct,
                "class_b": n_adapter,
                "unique_examples": total_unique,
                "action_region_cases": total_action_region,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
