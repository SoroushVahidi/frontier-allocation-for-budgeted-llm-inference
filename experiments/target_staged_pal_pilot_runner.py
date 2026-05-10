"""Armed pilot runner: target-staged PAL retry with Cohere (lazy import; gated by manifest + CLI)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from experiments.output_layer_repair import canonicalize_answer
from experiments.pal_executor import execute_pal_code
from experiments.target_staged_pal_pilot_dry_run import load_primary_case_problem_texts
from experiments.target_staged_pal_pilot_manifest import (
    EXPECTED_PRIMARY_CASE_IDS,
    validate_pilot_manifest_structure,
)
from experiments.target_staged_pal_prompt import (
    VARIANT_C,
    extract_python_for_pal_executor,
    materialize_user_prompt,
    parse_staged_model_output,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET = "openai/gsm8k"

ModelGenerateFn = Callable[..., tuple[str, int]]


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_primary_case_gold_answers() -> dict[str, str]:
    csv_path = (
        REPO_ROOT
        / "outputs/gold_absent_external_success_schema_mining_20260507"
        / "schema_mining_cases.csv"
    )
    out: dict[str, str] = {}
    with csv_path.open(encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            cid = str(row.get("case_id") or "")
            if cid in EXPECTED_PRIMARY_CASE_IDS:
                out[cid] = str(row.get("gold_answer") or "").strip()
    return out


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_default_cohere_model_fn(
    *,
    model: str,
    max_tokens: int = 4096,
) -> ModelGenerateFn:
    """Build a real Cohere chat callable. Imports `cohere` only when invoked."""

    def _fn(*, prompt: str, case_id: str, per_case_budget: int) -> tuple[str, int]:  # noqa: ARG001
        import cohere  # type: ignore

        api_key = os.getenv("COHERE_API_KEY", "")
        if not api_key:
            raise RuntimeError("COHERE_API_KEY is required for armed Cohere execution")
        client = cohere.ClientV2(api_key=api_key)
        resp = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        text = ""
        msg = getattr(resp, "message", None)
        if msg is not None and getattr(msg, "content", None):
            for part in getattr(msg, "content"):
                t = getattr(part, "text", "")
                if t:
                    text += str(t)
        logical_calls = 1
        return text, logical_calls

    return _fn


def run_target_staged_pal_pilot(
    *,
    manifest_path: Path,
    out_dir: Path,
    execute_api: bool,
    model_fn: ModelGenerateFn | None = None,
    cohere_model: str = "command-a-03-2025",
) -> dict[str, Any]:
    """
    If execute_api is False: return immediately (no API imports).

    If execute_api is True: manifest must have api_execution_enabled == true and pass structure validation.
    """
    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)

    if not execute_api:
        return {
            "status": "not_armed",
            "execute_api": False,
            "message": "Pass --execute-api and set manifest api_execution_enabled true to run Cohere.",
        }

    if manifest.get("api_execution_enabled") is not True:
        raise ValueError(
            "execute_api requested but manifest api_execution_enabled is not true — refusing API setup"
        )

    if manifest.get("hard_logical_call_cap") != 120:
        raise ValueError("hard_logical_call_cap must be exactly 120")
    if manifest.get("primary_case_count") != 11:
        raise ValueError("primary_case_count must be 11")

    validate_pilot_manifest_structure(manifest)

    cases = manifest["cases"]
    per_case_budget = int(manifest.get("per_case_budget") or 0)
    hard_cap = int(manifest.get("hard_logical_call_cap") or 0)
    if per_case_budget * len(cases) > hard_cap:
        raise ValueError("planned logical ceiling (per_case_budget × cases) exceeds hard_logical_call_cap")

    questions = load_primary_case_problem_texts()
    gold_by = _load_primary_case_gold_answers()

    if model_fn is None:
        model_fn = _make_default_cohere_model_fn(model=cohere_model)

    out_dir.mkdir(parents=True, exist_ok=True)
    cumulative_calls = 0

    case_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    prompt_snapshots: list[dict[str, Any]] = []

    for case in cases:
        cid = str(case["source_case_id"])
        tv = str(case["template_variant"])
        if tv == VARIANT_C:
            raise ValueError("oracle / non-deployable template must not appear in pilot manifest")

        prompt = materialize_user_prompt(tv, question=questions[cid])
        phash = _sha256(prompt)

        prompt_snapshots.append(
            {
                "source_case_id": cid,
                "template_variant": tv,
                "prompt_sha256": phash,
                "prompt": prompt,
            }
        )

        raw, used = model_fn(prompt=prompt, case_id=cid, per_case_budget=per_case_budget)
        cumulative_calls += int(used)
        if cumulative_calls > hard_cap:
            raise RuntimeError(
                f"cumulative logical_calls_used {cumulative_calls} exceeds hard_logical_call_cap {hard_cap}"
            )
        if int(used) > per_case_budget:
            raise RuntimeError(
                f"case {cid} reported logical_calls_used={used} exceeding per_case_budget={per_case_budget}"
            )

        parsed = parse_staged_model_output(raw)
        py_src = extract_python_for_pal_executor(parsed.get("python") or "")

        pal_err = ""
        pred = ""
        pal_parse_ok = False
        pal_safety_ok = False
        pal_exec_ok = False
        if py_src.strip():
            exec_res = execute_pal_code(py_src)
            pal_parse_ok = bool(exec_res.pal_parse_ok)
            pal_safety_ok = bool(exec_res.pal_safety_ok)
            pal_exec_ok = bool(exec_res.pal_exec_ok)
            pred = str(exec_res.pal_answer_normalized or "")
            if not pal_exec_ok:
                pal_err = str(exec_res.pal_error_message_sanitized or exec_res.pal_error_type or "")
        else:
            pal_err = "empty_python_section"

        gold = gold_by.get(cid, "")
        exact: bool | None = None
        if gold and pred:
            cg = canonicalize_answer(gold, dataset=DATASET)
            cp = canonicalize_answer(pred, dataset=DATASET)
            exact = bool(cg and cp and cg == cp)

        row = {
            "source_case_id": cid,
            "template_variant": tv,
            "prompt_sha256": phash,
            "raw_model_output": raw,
            "parsed_sections": parsed,
            "extracted_python": py_src,
            "pal_parse_ok": pal_parse_ok,
            "pal_safety_ok": pal_safety_ok,
            "pal_exec_ok": pal_exec_ok,
            "predicted_answer": pred,
            "expected_answer": gold,
            "exact_match": exact,
            "logical_calls_used_this_case": int(used),
            "cumulative_logical_calls_after_case": cumulative_calls,
            "failure_or_error": pal_err,
        }
        case_rows.append(row)
        if pal_err or exact is False or exact is None:
            failure_rows.append(
                {
                    "source_case_id": cid,
                    "failure_or_error": pal_err or ("" if exact else "exact_match_false"),
                    "exact_match": exact,
                }
            )

    summary = {
        "status": "completed",
        "execute_api": True,
        "manifest_path": str(manifest_path),
        "out_dir": str(out_dir.resolve()),
        "cohere_model": cohere_model,
        "primary_case_count": len(cases),
        "per_case_budget": per_case_budget,
        "hard_logical_call_cap": hard_cap,
        "total_logical_calls_used": cumulative_calls,
        "api_execution_enabled": manifest.get("api_execution_enabled"),
        "runner_module": "experiments.target_staged_pal_pilot_runner",
    }

    with (out_dir / "case_results.jsonl").open("w", encoding="utf-8") as fp:
        for r in case_rows:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")

    with (out_dir / "failures.jsonl").open("w", encoding="utf-8") as fp:
        for r in failure_rows:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")

    with (out_dir / "prompts_snapshot.jsonl").open("w", encoding="utf-8") as fp:
        for r in prompt_snapshots:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")

    (out_dir / "config_snapshot.json").write_text(
        json.dumps(
            {
                "manifest": manifest,
                "execute_api": True,
                "cohere_model": cohere_model,
                "runner": summary["runner_module"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--manifest",
        type=Path,
        default=REPO_ROOT / "manifests" / "target_staged_pal_retry_primary_11_20260507.json",
    )
    ap.add_argument(
        "--out",
        type=Path,
        required=True,
    )
    ap.add_argument(
        "--execute-api",
        action="store_true",
        help="Arm API execution (still requires manifest api_execution_enabled true)",
    )
    ap.add_argument(
        "--cohere-model",
        default="command-a-03-2025",
    )
    args = ap.parse_args()

    if not args.execute_api:
        print("Pilot not armed: missing --execute-api. No API calls, no Cohere import.")
        return 0

    manifest = _load_manifest(args.manifest.resolve())
    if manifest.get("api_execution_enabled") is not True:
        print(
            "Refusing API: manifest api_execution_enabled must be true when using --execute-api.",
            file=__import__("sys").stderr,
        )
        return 2

    try:
        s = run_target_staged_pal_pilot(
            manifest_path=args.manifest,
            out_dir=args.out,
            execute_api=True,
            model_fn=None,
            cohere_model=args.cohere_model,
        )
        print(f"Wrote pilot outputs to {s['out_dir']}")
    except (ValueError, RuntimeError) as e:
        print(str(e), file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
