"""Hugging Face dataset registry + lightweight access helpers."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
import os
from pathlib import Path
import random
import sys
from typing import Any


@dataclass(frozen=True)
class HFDatasetSpec:
    key: str
    repo_id: str
    default_config: str | None
    default_split: str
    question_fields: tuple[str, ...]
    answer_fields: tuple[str, ...]
    gated: bool = False
    optional: bool = False
    # Short provenance / caveat for docs and reports (not used by loaders).
    provenance_note: str | None = None


@dataclass(frozen=True)
class GitDatasetSpec:
    key: str
    repo_url: str
    default_local_path: str
    required_files: tuple[str, ...]
    question_fields: tuple[str, ...]
    answer_fields: tuple[str, ...]
    provenance_note: str | None = None


HF_DATASET_SPECS: dict[str, HFDatasetSpec] = {
    "openai/gsm8k": HFDatasetSpec(
        key="openai/gsm8k",
        repo_id="openai/gsm8k",
        default_config="main",
        default_split="test",
        question_fields=("question",),
        answer_fields=("answer",),
        provenance_note=None,
    ),
    # MATH (Hendrycks et al.): paper https://arxiv.org/abs/2103.03874
    # Official HF org `hendrycks/math` is not a resolvable Hub dataset id; `hendrycks/competition_math`
    # is the canonical Hendrycks org dataset. `EleutherAI/hendrycks_math` is a widely used mirror.
    "hendrycks/competition_math": HFDatasetSpec(
        key="hendrycks/competition_math",
        repo_id="hendrycks/competition_math",
        default_config="algebra",
        default_split="test",
        question_fields=("problem",),
        answer_fields=("solution",),
        provenance_note="Canonical Hendrycks org Hub id for MATH; configs are subject subsets (e.g. algebra).",
    ),
    "EleutherAI/hendrycks_math": HFDatasetSpec(
        key="EleutherAI/hendrycks_math",
        repo_id="EleutherAI/hendrycks_math",
        default_config="algebra",
        default_split="test",
        question_fields=("problem", "question"),
        answer_fields=("solution", "answer"),
        provenance_note="Community mirror of MATH-style competition math; same broad schema as hendrycks/competition_math.",
    ),
    "Idavidrein/gpqa": HFDatasetSpec(
        key="Idavidrein/gpqa",
        repo_id="Idavidrein/gpqa",
        default_config="gpqa_diamond",
        default_split="train",
        question_fields=("Question", "question"),
        answer_fields=("Correct Answer", "answer"),
        gated=True,
        provenance_note="GPQA Diamond config; requires HF auth / dataset terms acceptance when gated.",
    ),
    # OlympiadBench paper https://arxiv.org/abs/2406.15513 — THUDM/OlympiadBench Hub id is not
    # reliably resolvable; Hothan/OlympiadBench is the supported English math competition config.
    "Hothan/OlympiadBench": HFDatasetSpec(
        key="Hothan/OlympiadBench",
        repo_id="Hothan/OlympiadBench",
        default_config="OE_TO_maths_en_COMP",
        default_split="train",
        question_fields=("question", "problem"),
        answer_fields=("final_answer", "answer", "solution"),
        provenance_note="HF mirror with OlympiadBench-style schema; cite THUDM/OpenBMB paper for benchmark definition.",
    ),
    # AIME 2024 (30 problems): derived card HuggingFaceH4/aime_2024; integer answers.
    "HuggingFaceH4/aime_2024": HFDatasetSpec(
        key="HuggingFaceH4/aime_2024",
        repo_id="HuggingFaceH4/aime_2024",
        default_config=None,
        default_split="train",
        question_fields=("problem",),
        answer_fields=("answer",),
        optional=True,
        provenance_note="Single-year AIME 2024 slice; for broader AIME coverage see AI-MO/aimo-validation-aime (not wired here).",
    ),
    "livecodebench/code_generation_lite": HFDatasetSpec(
        key="livecodebench/code_generation_lite",
        repo_id="livecodebench/code_generation_lite",
        default_config=None,
        default_split="test",
        question_fields=("question_content", "prompt", "question"),
        answer_fields=("starter_code", "solution", "answer"),
        optional=True,
        provenance_note=None,
    ),
    "HuggingFaceH4/MATH-500": HFDatasetSpec(
        key="HuggingFaceH4/MATH-500",
        repo_id="HuggingFaceH4/MATH-500",
        default_config=None,
        default_split="test",
        question_fields=("problem",),
        answer_fields=("answer", "solution"),
        optional=False,
        provenance_note="Chosen canonical MATH-500 id in this repo due stronger maintenance signal and broad community usage; schema matches other mirrors.",
    ),
    "meituan-longcat/AMO-Bench": HFDatasetSpec(
        key="meituan-longcat/AMO-Bench",
        repo_id="meituan-longcat/AMO-Bench",
        default_config=None,
        default_split="test",
        question_fields=("prompt", "question"),
        answer_fields=("answer",),
        optional=False,
        provenance_note="AMO-Bench HF release with MIT license tag and 50-item hard-math test split.",
    ),
    # DROP: requested source `allenai/drop` is not currently resolvable on HF Hub API in this environment.
    # We keep canonical key `allenai/drop` but load from public mirror `ucinlp/drop` and document this fallback.
    "allenai/drop": HFDatasetSpec(
        key="allenai/drop",
        repo_id="ucinlp/drop",
        default_config=None,
        default_split="validation",
        question_fields=("question",),
        answer_fields=("answers_spans",),
        optional=False,
        provenance_note=(
            "Requested HF id allenai/drop was not resolvable in this environment; using public HF mirror ucinlp/drop. "
            "Official AWS registry path is also available: https://registry.opendata.aws/allenai-drop/."
        ),
    ),
    "TAUR-Lab/MuSR": HFDatasetSpec(
        key="TAUR-Lab/MuSR",
        repo_id="TAUR-Lab/MuSR",
        default_config="default",
        default_split="murder_mysteries",
        question_fields=("question", "narrative"),
        answer_fields=("answer_choice", "answer_index"),
        optional=False,
        provenance_note="MuSR reasoning benchmark; default split key reflects task family layout in this HF card.",
    ),
    "openeval/BIG-Bench-Hard": HFDatasetSpec(
        key="openeval/BIG-Bench-Hard",
        repo_id="openeval/BIG-Bench-Hard",
        default_config="default",
        default_split="train",
        question_fields=("input", "question", "examples"),
        answer_fields=("target", "answer", "examples"),
        optional=False,
        provenance_note="BIG-Bench Hard card with task-packed rows (examples nested per task row).",
    ),
    "deepmind/aqua_rat": HFDatasetSpec(
        key="deepmind/aqua_rat",
        repo_id="deepmind/aqua_rat",
        default_config="raw",
        default_split="validation",
        question_fields=("question",),
        answer_fields=("correct", "rationale"),
        optional=False,
        provenance_note="AQuA-RAT multiple-choice benchmark (raw config).",
    ),
}

GIT_DATASET_SPECS: dict[str, GitDatasetSpec] = {
    "google-deepmind/natural-plan": GitDatasetSpec(
        key="google-deepmind/natural-plan",
        repo_url="https://github.com/google-deepmind/natural-plan",
        default_local_path="external_datasets/natural-plan",
        required_files=(
            "data/trip_planning.json",
            "data/meeting_planning.json",
            "data/calendar_scheduling.json",
            "evaluate_trip_planning.py",
            "evaluate_meeting_planning.py",
            "evaluate_calendar_scheduling.py",
        ),
        question_fields=("prompt_0shot", "prompt_5shot"),
        answer_fields=("golden_plan",),
        provenance_note=(
            "Upstream clone-based access only. Do not vendor raw NaturalPlan data into this repository; "
            "pin upstream commit in run manifests."
        ),
    ),
}

# Alternate names / paper shorthand -> canonical registry key
DATASET_KEY_ALIASES: dict[str, str] = {
    "hendrycks/math": "hendrycks/competition_math",
    "math": "hendrycks/competition_math",
    "MATH": "hendrycks/competition_math",
    "gpqa_diamond": "Idavidrein/gpqa",
    "gpqa": "Idavidrein/gpqa",
    "olympiadbench": "Hothan/OlympiadBench",
    "olympiadbench_thudm": "Hothan/OlympiadBench",
    "aime": "HuggingFaceH4/aime_2024",
    "aime_2024": "HuggingFaceH4/aime_2024",
    "math500": "HuggingFaceH4/MATH-500",
    "math-500": "HuggingFaceH4/MATH-500",
    "MATH-500": "HuggingFaceH4/MATH-500",
    "amo-bench": "meituan-longcat/AMO-Bench",
    "amo_bench": "meituan-longcat/AMO-Bench",
    "AMO-Bench": "meituan-longcat/AMO-Bench",
    "naturalplan": "google-deepmind/natural-plan",
    "natural_plan": "google-deepmind/natural-plan",
    "NaturalPlan": "google-deepmind/natural-plan",
    "DROP": "allenai/drop",
    "drop": "allenai/drop",
    "MuSR": "TAUR-Lab/MuSR",
    "musr": "TAUR-Lab/MuSR",
    "big-bench-hard": "openeval/BIG-Bench-Hard",
    "bbh": "openeval/BIG-Bench-Hard",
    "BIG-Bench-Hard": "openeval/BIG-Bench-Hard",
    "aqua_rat": "deepmind/aqua_rat",
    "AQuA": "deepmind/aqua_rat",
    "AQuA-RAT": "deepmind/aqua_rat",
}

REPO_ROOT = Path(__file__).resolve().parents[1]


def _import_hf_load_dataset() -> Any:
    """Import HF `load_dataset` while avoiding local `datasets/` path shadowing."""
    original_path = list(sys.path)
    try:
        sys.path = [p for p in original_path if Path(p).resolve() != REPO_ROOT]
        module = importlib.import_module("datasets")
    finally:
        sys.path = original_path
    load_dataset = getattr(module, "load_dataset", None)
    if load_dataset is None:
        raise ImportError("datasets.load_dataset is unavailable in imported module")
    return load_dataset


def _get_hf_token() -> str | None:
    for env_name in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
        token = os.getenv(env_name)
        if token:
            return token
    return None


def hf_token_presence() -> dict[str, bool]:
    """Presence-only token status; never returns token contents."""
    return {
        "HF_TOKEN": bool(os.getenv("HF_TOKEN")),
        "HUGGINGFACE_HUB_TOKEN": bool(os.getenv("HUGGINGFACE_HUB_TOKEN")),
    }


def _resolve_alias(name: str) -> str:
    for k, v in DATASET_KEY_ALIASES.items():
        if k.lower() == name.strip().lower():
            return v
    return name.strip()


def resolve_dataset_spec(dataset_name: str) -> HFDatasetSpec:
    dataset_name = _resolve_alias(dataset_name)
    if dataset_name in HF_DATASET_SPECS:
        return HF_DATASET_SPECS[dataset_name]
    lower_map = {k.lower(): v for k, v in HF_DATASET_SPECS.items()}
    if dataset_name.lower() in lower_map:
        return lower_map[dataset_name.lower()]
    raise KeyError(f"Unsupported HF dataset: {dataset_name}")


def resolve_git_dataset_spec(dataset_name: str) -> GitDatasetSpec:
    dataset_name = _resolve_alias(dataset_name)
    if dataset_name in GIT_DATASET_SPECS:
        return GIT_DATASET_SPECS[dataset_name]
    lower_map = {k.lower(): v for k, v in GIT_DATASET_SPECS.items()}
    if dataset_name.lower() in lower_map:
        return lower_map[dataset_name.lower()]
    raise KeyError(f"Unsupported git-clone dataset: {dataset_name}")


def check_hf_dataset_access(
    dataset_name: str,
    split: str | None = None,
    config_name: str | None = None,
    streaming: bool = True,
) -> dict[str, Any]:
    spec = resolve_dataset_spec(dataset_name)
    try:
        load_dataset = _import_hf_load_dataset()
    except Exception as exc:  # pragma: no cover
        return {
            "dataset": spec.key,
            "repo_id": spec.repo_id,
            "ok": False,
            "gated": spec.gated,
            "error": f"datasets import failed: {type(exc).__name__}: {exc}",
        }

    token_flags = hf_token_presence()
    token_present = token_flags["HF_TOKEN"] or token_flags["HUGGINGFACE_HUB_TOKEN"]
    split_to_use = split or spec.default_split
    config_to_use = config_name if config_name is not None else spec.default_config
    token = _get_hf_token()

    kwargs: dict[str, Any] = {
        "path": spec.repo_id,
        "split": split_to_use,
        "streaming": streaming,
        "token": token,
    }
    if config_to_use is not None:
        kwargs["name"] = config_to_use

    try:
        ds = load_dataset(**kwargs)
        first = next(iter(ds))
        success = {
            "dataset": spec.key,
            "repo_id": spec.repo_id,
            "ok": True,
            "gated": spec.gated,
            "split": split_to_use,
            "config": config_to_use,
            "token_present": token_present,
            "token_env_presence": token_flags,
            "first_row_keys": sorted(list(first.keys())),
        }
        if spec.key == "Idavidrein/gpqa":
            success.update(_merge_gpqa_loader_results(datasets_loader_ok=True, pandas_result=_gpqa_pandas_fallback()))
        return success
    except Exception as exc:
        failure = {
            "dataset": spec.key,
            "repo_id": spec.repo_id,
            "ok": False,
            "gated": spec.gated,
            "split": split_to_use,
            "config": config_to_use,
            "token_present": token_present,
            "token_env_presence": token_flags,
            "error": f"{type(exc).__name__}: {exc}",
        }
        if spec.key == "Idavidrein/gpqa":
            failure.update(
                _merge_gpqa_loader_results(datasets_loader_ok=False, pandas_result=_gpqa_pandas_fallback())
            )
            failure["ok"] = bool(failure.get("gpqa_accessible"))
        else:
            failure.update({"datasets_loader_ok": False, "pandas_fallback_ok": None, "loader_path_used": "none"})
        return failure


def _gpqa_pandas_fallback() -> dict[str, Any]:
    """Try GPQA via pandas hf:// path after datasets-based loading fails."""
    try:
        import pandas as pd  # type: ignore

        frame = pd.read_csv("hf://datasets/Idavidrein/gpqa/gpqa_extended.csv", nrows=1)
        return {
            "datasets_loader_ok": False,
            "pandas_fallback_ok": True,
            "gpqa_accessible": True,
            "pandas_columns": list(frame.columns),
            "loader_path_used": "pandas_hf://",
        }
    except Exception as pandas_exc:
        return {
            "datasets_loader_ok": False,
            "pandas_fallback_ok": False,
            "gpqa_accessible": False,
            "pandas_error": f"{type(pandas_exc).__name__}: {pandas_exc}",
            "loader_path_used": "none",
        }


def _merge_gpqa_loader_results(
    *,
    datasets_loader_ok: bool,
    pandas_result: dict[str, Any],
) -> dict[str, Any]:
    pandas_ok = bool(pandas_result.get("pandas_fallback_ok"))
    loader_path_used = "datasets" if datasets_loader_ok else ("pandas_hf://" if pandas_ok else "none")
    merged = {
        "datasets_loader_ok": datasets_loader_ok,
        "pandas_fallback_ok": pandas_result.get("pandas_fallback_ok"),
        "gpqa_accessible": bool(datasets_loader_ok or pandas_ok),
        "loader_path_used": loader_path_used,
    }
    if "pandas_columns" in pandas_result:
        merged["pandas_columns"] = pandas_result["pandas_columns"]
    if "pandas_error" in pandas_result:
        merged["pandas_error"] = pandas_result["pandas_error"]
    return merged


def _pick_first_present(row: dict[str, Any], candidates: tuple[str, ...]) -> str:
    for field in candidates:
        value = row.get(field)
        if value is not None:
            text = _safe_preview(value)
            if text.strip():
                return text
    return ""


def _safe_preview(value: Any, max_chars: int = 600) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            text = str(value)
    text = text.replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]} …<truncated {len(text) - max_chars} chars>"


def sample_hf_examples(
    dataset_name: str,
    pilot_size: int,
    seed: int,
    split: str | None = None,
    config_name: str | None = None,
) -> list[dict[str, str]]:
    """Load a small shuffled sample from a supported HF dataset for pilot usage."""
    spec = resolve_dataset_spec(dataset_name)
    load_dataset = _import_hf_load_dataset()

    split_to_use = split or spec.default_split
    config_to_use = config_name if config_name is not None else spec.default_config
    token = _get_hf_token()

    if config_to_use is None:
        ds = load_dataset(spec.repo_id, split=split_to_use, token=token)
    else:
        ds = load_dataset(spec.repo_id, config_to_use, split=split_to_use, token=token)

    shuffled = ds.shuffle(seed=seed)
    selected = shuffled.select(range(min(pilot_size, len(shuffled))))

    records: list[dict[str, str]] = []
    for idx, row in enumerate(selected):
        question = _pick_first_present(row, spec.question_fields)
        answer = _pick_first_present(row, spec.answer_fields)
        rec: dict[str, str] = {
            "example_id": f"{spec.key.replace('/', '_')}_{idx}",
            "question": question,
            "answer": answer,
        }
        if spec.key == "Idavidrein/gpqa":
            for k in ("choices", "Choices"):
                if k in row and row[k] is not None:
                    rec["choices"] = _safe_preview(row[k], max_chars=600)
                    break
        records.append(rec)
    return records


def _resolve_local_clone_path(spec: GitDatasetSpec, local_path: str | None = None) -> Path:
    if local_path:
        return Path(local_path).expanduser().resolve()
    env_path = os.getenv("NATURAL_PLAN_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return (REPO_ROOT / spec.default_local_path).resolve()


def check_git_dataset_access(dataset_name: str, local_path: str | None = None) -> dict[str, Any]:
    spec = resolve_git_dataset_spec(dataset_name)
    clone_path = _resolve_local_clone_path(spec, local_path=local_path)
    missing = [rel for rel in spec.required_files if not (clone_path / rel).exists()]
    ok = clone_path.exists() and not missing
    return {
        "dataset": spec.key,
        "repo_url": spec.repo_url,
        "ok": ok,
        "source_type": "git_clone",
        "clone_path": str(clone_path),
        "required_files": list(spec.required_files),
        "missing_files": missing,
        "clone_command": f"git clone {spec.repo_url} {clone_path}",
        "provenance_note": spec.provenance_note,
    }


def sample_git_dataset_examples(
    dataset_name: str,
    pilot_size: int,
    seed: int,
    local_path: str | None = None,
) -> list[dict[str, str]]:
    spec = resolve_git_dataset_spec(dataset_name)
    clone_path = _resolve_local_clone_path(spec, local_path=local_path)
    access = check_git_dataset_access(dataset_name, local_path=str(clone_path))
    if not access.get("ok"):
        missing = ", ".join(access.get("missing_files", []))
        raise FileNotFoundError(
            f"Git dataset clone missing or incomplete at {clone_path}. Missing: {missing}"
        )

    merged_rows: list[dict[str, str]] = []
    for task_name, rel_path in [
        ("trip_planning", "data/trip_planning.json"),
        ("meeting_planning", "data/meeting_planning.json"),
        ("calendar_scheduling", "data/calendar_scheduling.json"),
    ]:
        data_obj = json.loads((clone_path / rel_path).read_text(encoding="utf-8"))
        if not isinstance(data_obj, dict):
            continue
        for item_id, payload in data_obj.items():
            if not isinstance(payload, dict):
                continue
            question = ""
            for qf in spec.question_fields:
                qval = payload.get(qf)
                if qval is not None and str(qval).strip():
                    question = str(qval)
                    break
            answer = ""
            for af in spec.answer_fields:
                aval = payload.get(af)
                if aval is not None and str(aval).strip():
                    answer = str(aval)
                    break
            merged_rows.append(
                {
                    "example_id": f"{spec.key.replace('/', '_')}_{task_name}_{item_id}",
                    "task_name": task_name,
                    "question": question,
                    "answer": answer,
                }
            )

    rng = random.Random(seed)
    rng.shuffle(merged_rows)
    return merged_rows[: max(0, pilot_size)]
