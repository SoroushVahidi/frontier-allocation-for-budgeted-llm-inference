#!/usr/bin/env python3
"""BEST-Route two-lane stabilization pass.

Lane A (stable adjacent):
- runs canonical adjacent import integration contract.

Lane B (runtime stabilization):
- runs explicit 10-test crash isolation matrix,
- applies conservative runtime fixes in rational order,
- attempts tiny synthetic router run,
- records strongest honest state.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = REPO_ROOT / "external" / "best_route_microsoft" / "upstream" / "best-route-llm"
IMPORT_CONFIG = REPO_ROOT / "configs" / "best_route_official_import_v1.json"
CONTRACT_CONFIG = REPO_ROOT / "configs" / "best_route_adjacent_comparison_contract_v1.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs" / "best_route_runtime_stabilization"


@dataclass
class CmdResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


def run_cmd(command: str, *, cwd: Path | None = None, timeout: int = 1200, env: dict[str, str] | None = None) -> CmdResult:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    p = subprocess.run(
        command,
        shell=True,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=merged_env,
    )
    return CmdResult(command=command, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)


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


def append_log(path: Path, title: str, res: CmdResult) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {title}\n")
        f.write(f"$ {res.command}\n")
        f.write(f"exit_code={res.returncode}\n")
        f.write("[stdout]\n")
        f.write(res.stdout or "<empty>\n")
        f.write("\n[stderr]\n")
        f.write(res.stderr or "<empty>\n")
        f.write("\n")


def detect_python311() -> str | None:
    for candidate in ["python3.11", "python3.12", "python3.10"]:
        r = run_cmd(f"{candidate} -c \"import sys; print(sys.version_info[:2])\"", timeout=30)
        if r.returncode == 0:
            return candidate
    return None


def create_tiny_dataset(base: Path) -> dict[str, str]:
    base.mkdir(parents=True, exist_ok=True)
    row = {
        "instruction": "Q: ",
        "input": "1+1?",
        "output": "2",
        "candidates": [
            {
                "model": "llama-31-8b_ourRM_bo1",
                "decoding_method": "",
                "text": "2",
                "scores": {"armoRM_scores": 0.90},
                "token_num_prompt": 5,
                "token_num_responses": 2,
            },
            {
                "model": "gpt-4o_ourRM_bo1",
                "decoding_method": "",
                "text": "2",
                "scores": {"armoRM_scores": 0.95},
                "token_num_prompt": 5,
                "token_num_responses": 2,
            },
        ],
    }
    outputs: dict[str, str] = {}
    for split in ["train", "valid", "test"]:
        p = base / f"{split}.jsonl"
        p.write_text("\n".join(json.dumps({**row, "id": f"{split}-{i}"}) for i in range(6)) + "\n", encoding="utf-8")
        outputs[split] = str(p)
    return outputs


def install_if_missing(python_cmd: str, package: str, out_log: Path, installed: list[str]) -> None:
    module = {"scikit-learn": "sklearn", "llm-blender": "llm_blender"}.get(package, package.replace('-', '_'))
    chk = run_cmd(f"{python_cmd} -c \"import {module}; print('ok')\"", timeout=90)
    append_log(out_log, f"check_import_{package}", chk)
    if chk.returncode == 0:
        return
    cmd = f"{python_cmd} -m pip install {package}"
    res = run_cmd(cmd, timeout=2400)
    append_log(out_log, f"install_{package}", res)
    installed.append(cmd)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run BEST-Route two-lane runtime stabilization pass")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = ap.parse_args()

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_root).resolve() / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / "run_attempt_log.txt"
    log_file.write_text(f"BEST-Route runtime stabilization pass run_id={run_id}\n", encoding="utf-8")

    stage_rows: list[dict[str, Any]] = []
    iso_rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    install_cmds: list[str] = []

    def stage(name: str, status: str, note: str, command: str = "") -> None:
        stage_rows.append({"stage": name, "status": status, "note": note, "command": command})

    # Audit upstream presence.
    if not UPSTREAM.exists():
        clone = run_cmd(f"git clone --depth 1 https://github.com/microsoft/best-route-llm.git {shlex.quote(str(UPSTREAM))}", cwd=REPO_ROOT, timeout=1200)
        append_log(log_file, "clone_upstream", clone)
    upstream_ok = UPSTREAM.exists() and (UPSTREAM / "train_router.py").exists()
    stage("upstream_presence", "pass" if upstream_ok else "fail", "official upstream clone and train_router.py checked")

    # Select runtime: prefer dedicated venv on conservative Python when available.
    selected_python = sys.executable
    runtime_lane = "current_env"
    conservative_py = detect_python311()
    venv_dir = out_dir / "venv_best_route"
    if conservative_py:
        create = run_cmd(f"{conservative_py} -m venv {shlex.quote(str(venv_dir))}", timeout=300)
        append_log(log_file, "create_conservative_venv", create)
        if create.returncode == 0:
            selected_python = str(venv_dir / "bin" / "python")
            runtime_lane = f"isolated_env:{conservative_py}"
            pip_up = run_cmd(f"{selected_python} -m pip install --upgrade pip", timeout=600)
            append_log(log_file, "upgrade_pip_venv", pip_up)
            install_cmds.append(f"{selected_python} -m pip install --upgrade pip")

    stage("runtime_selection", "pass", f"selected_python={selected_python}; mode={runtime_lane}")

    # Conservative dependency setup (avoid random thrashing).
    install_if_missing(selected_python, "torch", log_file, install_cmds)
    install_if_missing(selected_python, "transformers", log_file, install_cmds)
    install_if_missing(selected_python, "tokenizers", log_file, install_cmds)
    install_if_missing(selected_python, "sentencepiece", log_file, install_cmds)
    install_if_missing(selected_python, "llm-blender", log_file, install_cmds)
    install_if_missing(selected_python, "scikit-learn", log_file, install_cmds)
    install_if_missing(selected_python, "pandas", log_file, install_cmds)
    install_if_missing(selected_python, "accelerate", log_file, install_cmds)
    install_if_missing(selected_python, "datasets", log_file, install_cmds)
    install_if_missing(selected_python, "trl", log_file, install_cmds)
    install_if_missing(selected_python, "prettytable", log_file, install_cmds)
    install_if_missing(selected_python, "tabulate", log_file, install_cmds)
    install_if_missing(selected_python, "evaluate", log_file, install_cmds)
    install_if_missing(selected_python, "sacrebleu", log_file, install_cmds)
    install_if_missing(selected_python, "rouge_score", log_file, install_cmds)
    install_if_missing(selected_python, "nltk", log_file, install_cmds)
    install_if_missing(selected_python, "bert_score", log_file, install_cmds)
    install_if_missing(selected_python, "pycocoevalcap", log_file, install_cmds)
    install_if_missing(selected_python, "wandb", log_file, install_cmds)
    install_if_missing(selected_python, "spacy", log_file, install_cmds)

    # Targeted compatibility fix: prefer stable pair for Python>=3.13.
    version_probe = run_cmd(
        f"{selected_python} -c \"import sys,torch,transformers,tokenizers,sentencepiece,json; print(json.dumps({{'python':sys.version,'torch':torch.__version__,'transformers':transformers.__version__,'tokenizers':tokenizers.__version__,'sentencepiece':sentencepiece.__version__}}))\"",
        timeout=120,
    )
    append_log(log_file, "version_probe_before_fix", version_probe)

    forced_fix_cmd = f"{selected_python} -m pip install --upgrade 'transformers==4.50.0' 'tokenizers==0.21.4'"
    forced_fix = run_cmd(forced_fix_cmd, timeout=2400)
    append_log(log_file, "fix_pin_transformers_tokenizers", forced_fix)
    install_cmds.append(forced_fix_cmd)
    stage("conservative_fix_pin", "pass" if forced_fix.returncode == 0 else "fail", "applied compatibility pin transformers==4.50.0 tokenizers==0.21.4", forced_fix_cmd)

    # Lane A: adjacent stable contract.
    adj_cmd = f"{selected_python} scripts/run_best_route_adjacent_integration.py --import-config {shlex.quote(str(IMPORT_CONFIG))} --contract-config {shlex.quote(str(CONTRACT_CONFIG))}"
    adj = run_cmd(adj_cmd, cwd=REPO_ROOT, timeout=900)
    append_log(log_file, "lane_a_adjacent_integration", adj)
    lane_a_ok = adj.returncode == 0
    stage("lane_a_adjacent", "pass" if lane_a_ok else "fail", "canonical adjacent import lane", adj_cmd)

    # Lane B: 10-test crash isolation matrix.
    tests: list[tuple[str, str, Path | None, dict[str, str] | None, int]] = [
        ("01_import_torch", f"{selected_python} -c \"import torch; print(torch.__version__)\"", None, None, 120),
        ("02_import_transformers", f"{selected_python} -c \"import transformers; print(transformers.__version__)\"", None, None, 120),
        ("03_import_tokenizers", f"{selected_python} -c \"import tokenizers; print(tokenizers.__version__)\"", None, None, 120),
        ("04_import_sentencepiece", f"{selected_python} -c \"import sentencepiece as sp; print(sp.__version__)\"", None, None, 120),
        ("05_import_llm_blender", f"{selected_python} -c \"import llm_blender; print(getattr(llm_blender,'__version__','n/a'))\"", None, None, 240),
        ("06_autotokenizer_default", f"{selected_python} -X faulthandler -c \"from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('microsoft/deberta-v3-small'); print('ok')\"", None, {"CUDA_VISIBLE_DEVICES": ""}, 900),
        ("07_autotokenizer_use_fast_false", f"{selected_python} -X faulthandler -c \"from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('microsoft/deberta-v3-small', use_fast=False); print('ok')\"", None, {"CUDA_VISIBLE_DEVICES": ""}, 900),
        ("08_minimal_model_init", f"{selected_python} -X faulthandler -c \"from transformers import AutoModel; AutoModel.from_pretrained('hf-internal-testing/tiny-random-roberta'); print('ok')\"", None, {"CUDA_VISIBLE_DEVICES": ""}, 900),
        ("09_llm_blender_build_tokenizer", f"{selected_python} -X faulthandler -c \"from llm_blender.pair_ranker.model_util import build_tokenizer; build_tokenizer('microsoft/deberta-v3-small'); print('ok')\"", None, {"CUDA_VISIBLE_DEVICES": ""}, 900),
    ]

    for test_id, cmd, cwd, env, timeout in tests:
        r = run_cmd(cmd, cwd=cwd, env=env, timeout=timeout)
        append_log(log_file, test_id, r)
        iso_rows.append({
            "test_id": test_id,
            "command": cmd,
            "exit_code": r.returncode,
            "segfault_139": r.returncode == 139,
            "status": "pass" if r.returncode == 0 else "fail",
        })

    tiny_data = create_tiny_dataset(out_dir / "tiny_dataset")
    tiny_cmd = (
        f"CUDA_VISIBLE_DEVICES='' {selected_python} train_router.py "
        "--model_name microsoft/deberta-v3-small "
        f"--train_data_path {shlex.quote(tiny_data['train'])} "
        f"--eval_data_path {shlex.quote(tiny_data['valid'])} "
        f"--test_data_path {shlex.quote(tiny_data['test'])} "
        "--candidate_models llama-31-8b_ourRM_bo1,gpt-4o_ourRM_bo1 "
        "--candidate_decoding_method , --quality_metric armoRM_scores --loss_type prob_nlabels "
        "--source_maxlength 64 --candidate_maxlength 64 --per_device_train_batch_size 1 "
        "--per_device_eval_batch_size 1 --gradient_accumulation_steps 1 --num_train_epochs 1 "
        "--do_train True --do_eval True --do_predict True --fp16 False "
        "--max_train_data_size 4 --max_eval_data_size 4 --max_predict_data_size 4 "
        f"--output_dir {shlex.quote(str(out_dir / 'tiny_router_run'))} "
        "--overwrite_output_dir True --save_predictions True --report_to none --run_name tiny_best_route_runtime_stabilization"
    )
    tiny = run_cmd(tiny_cmd, cwd=UPSTREAM, timeout=2400)
    append_log(log_file, "10_tiny_router_synthetic", tiny)
    tiny_ok = tiny.returncode == 0 and (out_dir / "tiny_router_run" / "predictions.pt").exists()
    iso_rows.append({
        "test_id": "10_tiny_router_synthetic",
        "command": tiny_cmd,
        "exit_code": tiny.returncode,
        "segfault_139": tiny.returncode == 139,
        "status": "pass" if tiny_ok else "fail",
    })
    stage("lane_b_tiny_router", "pass" if tiny_ok else "fail", "tiny synthetic train_router path", tiny_cmd)

    if not tiny_ok:
        blockers.append({"stage": "lane_b_tiny_router", "exit_code": tiny.returncode, "error": tiny.stderr or tiny.stdout})

    # Outputs
    write_csv(out_dir / "crash_isolation_matrix.csv", iso_rows)
    write_csv(out_dir / "stage_status.csv", stage_rows)
    write_json(
        out_dir / "comparison_readiness.json",
        {
            "baseline": "best_route_microsoft",
            "run_id": run_id,
            "lane_a_adjacent_stable": lane_a_ok,
            "lane_b_tiny_synthetic_router": tiny_ok,
            "status": "partial_runnable_adjacent" if lane_a_ok and tiny_ok else "adjacent_only_with_runtime_blocker",
            "runtime_mode": runtime_lane,
            "honesty_boundary": [
                "This pass does not claim full BEST-Route benchmark-faithful reproduction.",
                "API-backed fallback remains optional adjacent support and is not equivalent to full official local pipeline.",
            ],
            "likely_remaining_blocker_if_any": "none" if tiny_ok else "runtime instability remains in this environment",
        },
    )
    write_json(out_dir / "blockers.json", {"blockers": blockers})
    write_json(
        out_dir / "environment_check.json",
        {
            "python": sys.version,
            "python_executable": sys.executable,
            "selected_python": selected_python,
            "runtime_lane": runtime_lane,
            "upstream_head": run_cmd("git rev-parse HEAD", cwd=UPSTREAM, timeout=60).__dict__ if upstream_ok else {},
        },
    )
    write_json(out_dir / "manifest.json", {
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_best_route_runtime_stabilization_pass.py",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "artifacts": [
            "manifest.json",
            "environment_check.json",
            "install_commands.txt",
            "run_attempt_log.txt",
            "stage_status.csv",
            "crash_isolation_matrix.csv",
            "comparison_readiness.json",
            "blockers.json",
        ],
    })
    (out_dir / "install_commands.txt").write_text("\n".join(install_cmds) + ("\n" if install_cmds else ""), encoding="utf-8")

    print(json.dumps({"run_dir": str(out_dir), "lane_a_ok": lane_a_ok, "lane_b_ok": tiny_ok}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
