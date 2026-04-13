"""Hugging Face dataset registry + lightweight access helpers."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import os
from pathlib import Path
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
        if value is not None and str(value).strip():
            return str(value)
    return ""


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
                    rec["choices"] = str(row[k])
                    break
        records.append(rec)
    return records
