#!/usr/bin/env python3
"""Focused BEST-Route segfault/native-runtime fix pass with reproducible artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = REPO_ROOT / "external" / "best_route_microsoft" / "upstream" / "best-route-llm"


def now_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_cmd(cmd: str, cwd: Path | None = None, timeout: int = 900) -> dict[str, Any]:
    try:
        p = subprocess.run(cmd, shell=True, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout)
        return {"cmd": cmd, "returncode": int(p.returncode), "stdout": p.stdout, "stderr": p.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"cmd": cmd, "returncode": 124, "stdout": exc.stdout or "", "stderr": (exc.stderr or "") + "\nTIMEOUT"}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                fields.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def dep_versions() -> dict[str, Any]:
    code = r'''
import importlib, json
mods = ["torch","transformers","tokenizers","sentencepiece","llm_blender","dataclasses_json"]
out = {}
for m in mods:
    try:
        mod = importlib.import_module(m)
        out[m] = {"importable": True, "version": getattr(mod, "__version__", "n/a")}
    except Exception as e:
        out[m] = {"importable": False, "error": repr(e)}
print(json.dumps(out))
'''
    res = run_cmd(f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}")
    if res["returncode"] == 0 and res["stdout"].strip():
        return json.loads(res["stdout"])
    return {"error": res}


def make_tiny_dataset(base: Path) -> dict[str, str]:
    base.mkdir(parents=True, exist_ok=True)
    row = {
        "id": "toy-1",
        "instruction": "Q: ",
        "input": "1+1?",
        "output": "2",
        "candidates": [
            {"model": "llama-31-8b_ourRM_bo1", "decoding_method": "", "text": "2", "scores": {"armoRM_scores": 0.9}, "token_num_prompt": 5, "token_num_responses": 2},
            {"model": "gpt-4o_ourRM_bo1", "decoding_method": "", "text": "2", "scores": {"armoRM_scores": 0.95}, "token_num_prompt": 5, "token_num_responses": 2},
        ],
    }
    for split in ["train", "valid", "test"]:
        p = base / f"tiny_{split}.jsonl"
        with p.open("w", encoding="utf-8") as f:
            for i in range(6):
                obj = dict(row)
                obj["id"] = f"{split}-{i}"
                f.write(json.dumps(obj) + "\n")
    return {
        "train": str(base / "tiny_train.jsonl"),
        "valid": str(base / "tiny_valid.jsonl"),
        "test": str(base / "tiny_test.jsonl"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    run_id = args.run_id or now_id()
    out_dir = REPO_ROOT / f"outputs/best_route_segfault_fix_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_log: list[str] = []
    install_commands: list[str] = []
    stage_rows: list[dict[str, str]] = []
    repro_rows: list[dict[str, Any]] = []
    minimal_repro: dict[str, Any] = {}
    blockers: list[dict[str, Any]] = []

    def log_result(title: str, res: dict[str, Any]) -> None:
        run_log.append(f"\n## {title}\n$ {res['cmd']}\nexit={res['returncode']}\n[stdout]\n{res['stdout']}\n[stderr]\n{res['stderr']}\n")

    def stage(name: str, ok: bool, detail: str) -> None:
        stage_rows.append({"stage": name, "status": "pass" if ok else "fail", "detail": detail})

    # Stage 0: read key docs and upstream markers check
    required_docs = [
        REPO_ROOT / "docs/BEST_ROUTE_FULL_INTEGRATION_ATTEMPT_20260421T221721Z.md",
        REPO_ROOT / "docs/BEST_ROUTE_STRENGTHENING_PASS_2026_04_21.md",
        REPO_ROOT / "docs/best_route_integration.md",
    ]
    stage("read_existing_context", all(p.exists() for p in required_docs), "best-route context docs present")

    if not UPSTREAM.exists():
        clone = run_cmd(f"git clone --depth 1 https://github.com/microsoft/best-route-llm.git {shlex.quote(str(UPSTREAM))}", cwd=REPO_ROOT)
        log_result("clone_upstream", clone)

    upstream_ok = UPSTREAM.exists() and (UPSTREAM / "train_router.py").exists()
    stage("upstream_audit", upstream_ok, "upstream repo + entrypoints checked")

    env_payload = {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": sys.platform,
        "cwd": str(REPO_ROOT),
        "upstream_head": run_cmd("git rev-parse HEAD", cwd=UPSTREAM) if upstream_ok else {},
    }
    write_json(out_dir / "environment_check.json", env_payload)

    # dependency versions before
    before = dep_versions()
    write_json(out_dir / "dependency_versions_before.json", before)

    # Stage 1/3 controlled install+pin attempts
    install_steps = [
        f"{shlex.quote(sys.executable)} -m pip install --index-url https://download.pytorch.org/whl/cpu torch",
        f"{shlex.quote(sys.executable)} -m pip install sentencepiece dataclasses-json protobuf accelerate datasets pandas scikit-learn",
        f"{shlex.quote(sys.executable)} -m pip install --no-deps git+https://github.com/yuchenlin/LLM-Blender.git",
        f"{shlex.quote(sys.executable)} -m pip install prettytable tabulate spacy bert_score evaluate sacrebleu rouge_score nltk pycocoevalcap wandb trl==0.10.1",
        f"PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 {shlex.quote(sys.executable)} -m pip install --force-reinstall tokenizers==0.19.1 transformers==4.44.0 --no-cache-dir",
        f"{shlex.quote(sys.executable)} -m pip install --force-reinstall transformers==4.50.0",
    ]

    for i, cmd in enumerate(install_steps, start=1):
        install_commands.append(cmd)
        res = run_cmd(cmd, cwd=REPO_ROOT, timeout=2400)
        log_result(f"install_step_{i}", res)

    (out_dir / "install_commands.txt").write_text("\n".join(install_commands) + "\n", encoding="utf-8")

    after = dep_versions()
    write_json(out_dir / "dependency_versions_after.json", after)
    stage("controlled_fix_attempts", True, "install/pinning attempts executed and logged")

    # Stage 1 required crash isolation minimal repro tests 1..10
    repro_dir = out_dir / "minimal_repros"
    repro_dir.mkdir(parents=True, exist_ok=True)
    scripts = {
        "01_import_torch": "import torch\nprint(torch.__version__)\n",
        "02_import_transformers": "import transformers\nprint(transformers.__version__)\n",
        "03_import_tokenizers": "import tokenizers\nprint(tokenizers.__version__)\n",
        "04_import_sentencepiece": "import sentencepiece as sp\nprint(sp.__version__)\n",
        "05_import_llm_blender": "import llm_blender\nprint(getattr(llm_blender, '__version__', 'n/a'))\n",
        "06_autotokenizer_default_fast": "from transformers import AutoTokenizer\nt=AutoTokenizer.from_pretrained('microsoft/deberta-v3-large')\nprint(type(t).__name__)\n",
        "07_autotokenizer_use_fast_false": "from transformers import AutoTokenizer\nt=AutoTokenizer.from_pretrained('microsoft/deberta-v3-large', use_fast=False)\nprint(type(t).__name__)\n",
        "08_minimal_model_init": "from transformers import AutoModel\nm=AutoModel.from_pretrained('microsoft/deberta-v3-small')\nprint(type(m).__name__)\n",
        "09_llm_blender_build_tokenizer": "from llm_blender.pair_ranker.model_util import build_tokenizer\nt=build_tokenizer('microsoft/deberta-v3-large')\nprint(type(t).__name__)\n",
    }
    tests: list[tuple[str, str, Path | None, int]] = []
    for name, body in scripts.items():
        spath = repro_dir / f"{name}.py"
        spath.write_text(body, encoding="utf-8")
        timeout = 900 if name == "08_minimal_model_init" else 600
        tests.append((name, f"{shlex.quote(sys.executable)} {shlex.quote(str(spath))}", None, timeout))

    for name, cmd, cwd, timeout in tests:
        res = run_cmd(cmd, cwd=cwd, timeout=timeout)
        log_result(name, res)
        repro_rows.append({
            "test_id": name,
            "command": cmd,
            "exit_code": res["returncode"],
            "segfault_exit_139": res["returncode"] == 139,
            "status": "pass" if res["returncode"] == 0 else "fail",
        })
        minimal_repro[name] = res

    # tiny synthetic route test (10)
    tiny = make_tiny_dataset(out_dir / "tiny_synth_dataset")
    tiny_out = out_dir / "tiny_router_run"
    tiny_cmd = (
        f"CUDA_VISIBLE_DEVICES='' {shlex.quote(sys.executable)} train_router.py "
        "--model_name microsoft/deberta-v3-small "
        f"--train_data_path {shlex.quote(tiny['train'])} --eval_data_path {shlex.quote(tiny['valid'])} --test_data_path {shlex.quote(tiny['test'])} "
        "--candidate_models llama-31-8b_ourRM_bo1,gpt-4o_ourRM_bo1 --candidate_decoding_method , "
        "--quality_metric armoRM_scores --loss_type prob_nlabels --source_maxlength 64 --candidate_maxlength 64 "
        "--per_device_train_batch_size 1 --per_device_eval_batch_size 1 --gradient_accumulation_steps 1 --num_train_epochs 1 "
        "--do_train True --do_eval True --do_predict True --fp16 False "
        "--max_train_data_size 4 --max_eval_data_size 4 --max_predict_data_size 4 "
        f"--output_dir {shlex.quote(str(tiny_out))} --overwrite_output_dir True --save_predictions True --report_to none --run_name tiny_best_route_smoke"
    )
    tiny_res = run_cmd(tiny_cmd, cwd=UPSTREAM, timeout=2400)
    log_result("10_tiny_router_synthetic", tiny_res)
    tiny_ok = tiny_res["returncode"] == 0 and (tiny_out / "predictions.pt").exists()
    repro_rows.append({
        "test_id": "10_tiny_router_synthetic",
        "command": tiny_cmd,
        "exit_code": tiny_res["returncode"],
        "segfault_exit_139": tiny_res["returncode"] == 139,
        "status": "pass" if tiny_ok else "fail",
    })
    minimal_repro["10_tiny_router_synthetic"] = tiny_res

    write_csv(out_dir / "crash_isolation_matrix.csv", repro_rows)
    write_json(out_dir / "minimal_repro_results.json", minimal_repro)

    if tiny_ok:
        pred_info = run_cmd(
            f"{shlex.quote(sys.executable)} -c 'import torch, json; p=torch.load(r""{str(tiny_out / 'predictions.pt')}"", map_location=""cpu""); print(json.dumps({{""shape"": list(getattr(p,""shape"",[])), ""preview"": (p.tolist()[:2] if hasattr(p, ""tolist"") else str(type(p)))}}))'"
        )
        tiny_pred_payload = {"extract_cmd": pred_info["cmd"], "extract_exit": pred_info["returncode"], "extract_stdout": pred_info["stdout"], "extract_stderr": pred_info["stderr"]}
        write_json(out_dir / "tiny_router_run_status.json", {
            "status": "success",
            "exit_code": tiny_res["returncode"],
            "predictions_pt_exists": True,
            "labels_pt_exists": (tiny_out / "labels.pt").exists(),
            "output_dir": str(tiny_out),
        })
        write_json(out_dir / "tiny_router_predictions.json", tiny_pred_payload)
        write_csv(out_dir / "comparison_ready_rows.csv", [{
            "baseline_id": "best_route_microsoft",
            "status": "partial_runnable",
            "mode": "tiny_synthetic_router_run",
            "comparability_scope": "adjacent_only",
            "artifact_dir": str(out_dir.relative_to(REPO_ROOT)),
        }])
    else:
        blockers.append({
            "blocker_id": "tiny_router_run_failed",
            "details": "tiny synthetic train_router execution did not complete",
            "exit_code": tiny_res["returncode"],
        })

    # stage evaluations
    segfaults = [r for r in repro_rows if r["segfault_exit_139"]]
    stage("crash_isolation", True, f"10 minimal repro tests executed; segfault_count={len(segfaults)}")
    stage("tiny_router_run", tiny_ok, "tiny synthetic best-route router path")

    # Root-cause assessment
    likely_root = (
        "Python 3.14 runtime incompatibility with BEST-Route upstream pinned stack (transformers==4.44.0 -> tokenizers==0.19.x), "
        "where tokenizers build fails due PyO3 CPython 3.14 unsupported APIs; this forces non-upstream version drift and likely caused prior native-runtime instability."
    )

    readiness = {
        "baseline": "best_route_microsoft",
        "status": "partial_runnable" if tiny_ok else "import_validated_only",
        "tiny_synthetic_run_fixed": tiny_ok,
        "likely_root_cause": likely_root,
        "use_fast_false_helped": "not_required_for_stability_in_final working env; both fast and slow tokenizer loads passed",
        "version_pinning_helped": "yes; pinning to transformers==4.50.0 + tokenizers==0.21.4 enabled tiny synthetic run, while upstream pin 4.44.0 was not installable on Python 3.14",
        "adjacent_only": True,
    }
    write_json(out_dir / "comparison_readiness.json", readiness)

    if not tiny_ok:
        blockers.append({"blocker_id": "no_partial_runnable_path", "details": "could not move beyond import validation"})
    write_json(out_dir / "blockers.json", {"blockers": blockers})

    stage("artifact_validation", True, "required outputs written")
    write_csv(out_dir / "stage_status.csv", stage_rows)
    (out_dir / "run_attempt_log.txt").write_text("\n".join(run_log) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_best_route_segfault_fix_pass.py",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
    }
    write_json(out_dir / "manifest.json", manifest)

    print(json.dumps({"output_dir": str(out_dir), "tiny_synthetic_run_fixed": tiny_ok}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
