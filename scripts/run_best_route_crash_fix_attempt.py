#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_PATH = REPO_ROOT / "external" / "best_route_microsoft" / "upstream" / "best-route-llm"
IMPORT_CONFIG = REPO_ROOT / "configs" / "best_route_official_import_v1.json"
CONTRACT_CONFIG = REPO_ROOT / "configs" / "best_route_adjacent_comparison_contract_v1.json"


@dataclass
class CmdResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


def run_cmd(command: str, cwd: Path | None = None, timeout: int = 1200, env: dict[str, str] | None = None) -> CmdResult:
    merged_env = None
    if env is not None:
        merged_env = dict(**subprocess.os.environ)
        merged_env.update(env)
    p = subprocess.run(command, shell=True, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout, env=merged_env)
    return CmdResult(command, p.returncode, p.stdout, p.stderr)


def wjson(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def wcsv(path: Path, rows: list[dict[str, Any]]) -> None:
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
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_log(path: Path, title: str, res: CmdResult) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {title}\n$ {res.command}\nexit_code={res.returncode}\n[stdout]\n{res.stdout or '<empty>'}\n[stderr]\n{res.stderr or '<empty>'}\n")


def package_versions(packages: list[str]) -> dict[str, str]:
    cmd = f"{shlex.quote(sys.executable)} -m pip show " + " ".join(packages)
    r = run_cmd(cmd)
    versions: dict[str, str] = {}
    current = ""
    for line in (r.stdout or "").splitlines():
        if line.startswith("Name:"):
            current = line.split(":", 1)[1].strip()
        if line.startswith("Version:") and current:
            versions[current] = line.split(":", 1)[1].strip()
            current = ""
    return versions


def create_tiny_dataset(base: Path) -> dict[str, str]:
    base.mkdir(parents=True, exist_ok=True)
    row = {
        "instruction": "Q: ",
        "input": "1+1",
        "output": "2",
        "candidates": [
            {"model": "llama-31-8b_ourRM_bo1", "decoding_method": "", "text": "2", "scores": {"armoRM_scores": 0.9}, "token_num_prompt": 5, "token_num_responses": 2},
            {"model": "gpt-4o_ourRM_bo1", "decoding_method": "", "text": "2", "scores": {"armoRM_scores": 0.95}, "token_num_prompt": 5, "token_num_responses": 2},
        ],
    }
    out = {}
    for split in ["train", "valid", "test"]:
        p = base / f"{split}.jsonl"
        p.write_text("\n".join(json.dumps({**row, "id": f"{split}-{i}"}) for i in range(6)) + "\n", encoding="utf-8")
        out[split] = str(p)
    return out


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/best_route_crash_fix_attempt_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / "run_attempt_log.txt"
    log_file.write_text(f"BEST-Route crash fix attempt {run_id}\n", encoding="utf-8")
    install_log = out_dir / "install_commands.txt"

    stage_rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    repro_rows: list[dict[str, Any]] = []
    repro_results: dict[str, Any] = {}
    install_cmds: list[str] = []
    commands_run: list[str] = []

    def rec_stage(stage: str, status: str, command: str = "", note: str = "") -> None:
        stage_rows.append({"stage": stage, "status": status, "command": command, "note": note})

    # Stage: environment + clone
    if not UPSTREAM_PATH.exists():
        cmd = f"git clone https://github.com/microsoft/best-route-llm.git {shlex.quote(str(UPSTREAM_PATH))}"
        res = run_cmd(cmd, cwd=REPO_ROOT)
        commands_run.append(cmd)
        append_log(log_file, "clone_upstream", res)

    base_versions = package_versions(["torch", "transformers", "tokenizers", "sentencepiece", "llm-blender"])
    wjson(out_dir / "dependency_versions_before.json", base_versions)

    env_cmd = f"{shlex.quote(sys.executable)} -c \"import sys,platform,json,torch; print(json.dumps({{'python':sys.version,'platform':platform.platform(),'torch':torch.__version__,'cuda':torch.cuda.is_available()}}, indent=2))\""
    env_res = run_cmd(env_cmd)
    commands_run.append(env_cmd)
    append_log(log_file, "environment_check", env_res)
    wjson(out_dir / "environment_check.json", {"command": env_cmd, "exit_code": env_res.returncode, "stdout": env_res.stdout, "stderr": env_res.stderr})

    rec_stage("environment_and_upstream_presence", "pass" if env_res.returncode == 0 and UPSTREAM_PATH.exists() else "fail", env_cmd, "environment captured and upstream available")

    # Stage 1 isolate matrix initial
    tests = [
        ("python_plain", f"{shlex.quote(sys.executable)} -c \"print('ok')\""),
        ("import_transformers", f"{shlex.quote(sys.executable)} -c \"import transformers; print(transformers.__version__)\""),
        ("import_tokenizers", f"{shlex.quote(sys.executable)} -c \"import tokenizers; print(tokenizers.__version__)\""),
        ("import_sentencepiece", f"{shlex.quote(sys.executable)} -c \"import sentencepiece as sp; print(sp.__version__)\""),
        ("import_torch", f"{shlex.quote(sys.executable)} -c \"import torch; print(torch.__version__)\""),
        ("import_llm_blender", f"{shlex.quote(sys.executable)} -c \"import llm_blender; print('ok')\""),
        ("autotokenizer_default", f"{shlex.quote(sys.executable)} -X faulthandler -c \"from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('microsoft/deberta-v3-small'); print('ok')\""),
        ("autotokenizer_slow", f"{shlex.quote(sys.executable)} -X faulthandler -c \"from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('microsoft/deberta-v3-small', use_fast=False); print('ok')\""),
        ("auto_model_init", f"{shlex.quote(sys.executable)} -X faulthandler -c \"from transformers import AutoModel; AutoModel.from_pretrained('hf-internal-testing/tiny-random-roberta'); print('ok')\""),
        ("llm_blender_build_tokenizer", f"{shlex.quote(sys.executable)} -X faulthandler -c \"from llm_blender.pair_ranker.model_util import build_tokenizer; build_tokenizer('microsoft/deberta-v3-small'); print('ok')\""),
    ]

    for name, cmd in tests:
        res = run_cmd(cmd, timeout=1200)
        commands_run.append(cmd)
        append_log(log_file, f"isolation_{name}", res)
        row = {"test": name, "command": cmd, "exit_code": res.returncode, "status": "pass" if res.returncode == 0 else "fail", "phase": "baseline"}
        repro_rows.append(row)
        repro_results[f"baseline::{name}"] = {"exit_code": res.returncode, "stdout": res.stdout, "stderr": res.stderr}

    # Stage 2/3: controlled fix attempts
    # fix attempt A: force cpu env and rerun tokenizer load
    cpu_test_cmd = f"{shlex.quote(sys.executable)} -X faulthandler -c \"from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('microsoft/deberta-v3-small'); print('ok')\""
    res_cpu = run_cmd(cpu_test_cmd, env={"CUDA_VISIBLE_DEVICES": "", "PYTORCH_ENABLE_MPS_FALLBACK": "1"})
    commands_run.append(cpu_test_cmd + " [CUDA_VISIBLE_DEVICES=]")
    append_log(log_file, "fix_attempt_force_cpu_autotokenizer", res_cpu)
    repro_rows.append({"test": "autotokenizer_default", "command": cpu_test_cmd, "exit_code": res_cpu.returncode, "status": "pass" if res_cpu.returncode == 0 else "fail", "phase": "fix_force_cpu"})
    repro_results["fix_force_cpu::autotokenizer_default"] = {"exit_code": res_cpu.returncode, "stdout": res_cpu.stdout, "stderr": res_cpu.stderr}

    # fix attempt B: tokenizers pin
    pin_cmd = f"{shlex.quote(sys.executable)} -m pip install tokenizers==0.15.0"
    res_pin = run_cmd(pin_cmd, timeout=2400)
    commands_run.append(pin_cmd)
    install_cmds.append(pin_cmd)
    append_log(log_file, "fix_attempt_pin_tokenizers_0_15_0", res_pin)

    res_post_pin_tok = run_cmd(cpu_test_cmd, timeout=1200)
    commands_run.append(cpu_test_cmd + " [post-tokenizers-pin]")
    append_log(log_file, "post_pin_autotokenizer_default", res_post_pin_tok)
    repro_rows.append({"test": "autotokenizer_default", "command": cpu_test_cmd, "exit_code": res_post_pin_tok.returncode, "status": "pass" if res_post_pin_tok.returncode == 0 else "fail", "phase": "fix_pin_tokenizers_0_15_0"})
    repro_results["fix_pin_tokenizers_0_15_0::autotokenizer_default"] = {"exit_code": res_post_pin_tok.returncode, "stdout": res_post_pin_tok.stdout, "stderr": res_post_pin_tok.stderr}

    # Stage 4 rerun tiny synthetic router path
    tiny = create_tiny_dataset(out_dir / "tiny_dataset")
    tiny_cmd = (
        f"{shlex.quote(sys.executable)} -X faulthandler train_router.py "
        "--model_name hf-internal-testing/tiny-random-roberta "
        f"--train_data_path {shlex.quote(tiny['train'])} --eval_data_path {shlex.quote(tiny['valid'])} --test_data_path {shlex.quote(tiny['test'])} "
        "--candidate_models llama-31-8b_ourRM_bo1,gpt-4o_ourRM_bo1 --candidate_decoding_method , --quality_metric armoRM_scores --loss_type prob_nlabels "
        "--source_maxlength 64 --candidate_maxlength 64 --per_device_train_batch_size 1 --per_device_eval_batch_size 1 --gradient_accumulation_steps 1 --num_train_epochs 1 "
        "--do_train True --do_eval True --do_predict True --fp16 False --max_train_data_size 4 --max_eval_data_size 4 --max_predict_data_size 4 "
        f"--output_dir {shlex.quote(str(out_dir / 'tiny_router_run'))} --overwrite_output_dir True --save_predictions True --report_to none --run_name tiny_best_route_crash_fix"
    )
    tiny_res = run_cmd(tiny_cmd, cwd=UPSTREAM_PATH, timeout=2400)
    commands_run.append(f"(cd {UPSTREAM_PATH} && {tiny_cmd})")
    append_log(log_file, "tiny_router_run", tiny_res)

    tiny_ok = tiny_res.returncode == 0 and (out_dir / "tiny_router_run" / "predictions.pt").exists()
    rec_stage("tiny_synthetic_router_run", "pass" if tiny_ok else "fail", tiny_cmd, "tiny run status")
    if tiny_ok:
        wjson(out_dir / "tiny_router_run_status.json", {"status": "pass", "predictions_path": str(out_dir / "tiny_router_run" / "predictions.pt")})
    else:
        blockers.append({"stage": "tiny_synthetic_router_run", "error": tiny_res.stderr or tiny_res.stdout, "exit_code": tiny_res.returncode, "likely": "tokenizer/runtime native crash"})

    # keep adjacent export lane
    adj_cmd = f"{shlex.quote(sys.executable)} scripts/run_best_route_adjacent_integration.py --import-config {shlex.quote(str(IMPORT_CONFIG))} --contract-config {shlex.quote(str(CONTRACT_CONFIG))}"
    adj_res = run_cmd(adj_cmd, cwd=REPO_ROOT)
    commands_run.append(adj_cmd)
    append_log(log_file, "adjacent_export", adj_res)
    if adj_res.returncode == 0:
        base = REPO_ROOT / "outputs" / "best_route_adjacent_integration"
        runs = sorted([p for p in base.iterdir() if p.is_dir()]) if base.exists() else []
        if runs and (runs[-1] / "comparison_ready_rows.csv").exists():
            (out_dir / "comparison_ready_rows.csv").write_text((runs[-1] / "comparison_ready_rows.csv").read_text(encoding="utf-8"), encoding="utf-8")

    rec_stage("adjacent_export_lane", "pass" if adj_res.returncode == 0 else "fail", adj_cmd, "preserve adjacent export")

    # final files
    after_versions = package_versions(["torch", "transformers", "tokenizers", "sentencepiece", "llm-blender"])
    wjson(out_dir / "dependency_versions_after.json", after_versions)
    install_log.write_text("\n".join(install_cmds) + ("\n" if install_cmds else ""), encoding="utf-8")
    wcsv(out_dir / "crash_isolation_matrix.csv", repro_rows)
    wjson(out_dir / "minimal_repro_results.json", repro_results)
    wcsv(out_dir / "stage_status.csv", stage_rows)
    wjson(out_dir / "blockers.json", {"blockers": blockers})

    classification = "partial_runnable" if adj_res.returncode == 0 else "blocked"
    readiness = {
        "baseline": "BEST-Route",
        "run_id": run_id,
        "tiny_run_fixed": tiny_ok,
        "classification": classification,
        "strongest_mode_now": "partial_runnable_baseline" if tiny_ok else "import_validated_adjacent_plus_crash_isolated",
        "most_likely_root_cause": "python_3_14_and_tokenizers_native_runtime_incompatibility" if not tiny_ok else "n/a",
    }
    wjson(out_dir / "comparison_readiness.json", readiness)

    manifest = {
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_best_route_crash_fix_attempt.py",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "commands_run": commands_run,
    }
    wjson(out_dir / "manifest.json", manifest)

    # stage for validations
    needed = [
        "manifest.json","environment_check.json","dependency_versions_before.json","dependency_versions_after.json","install_commands.txt",
        "crash_isolation_matrix.csv","minimal_repro_results.json","run_attempt_log.txt","stage_status.csv","blockers.json","comparison_readiness.json",
    ]
    missing = [n for n in needed if not (out_dir / n).exists()]
    if missing:
        blockers.append({"stage": "artifact_validation", "error": f"missing: {missing}"})
        rec_stage("artifact_validation", "fail", "", f"missing {missing}")
    else:
        rec_stage("artifact_validation", "pass", "", "all required artifact files present")
    wcsv(out_dir / "stage_status.csv", stage_rows)
    wjson(out_dir / "blockers.json", {"blockers": blockers})

    print(json.dumps({"run_id": run_id, "out_dir": str(out_dir), "tiny_run_fixed": tiny_ok, "blockers": len(blockers)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
