#!/usr/bin/env python3
"""Run a stronger BEST-Route integration attempt with iterative dependency installation."""

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


def run_cmd(command: str, cwd: Path | None = None, timeout: int = 900) -> CmdResult:
    proc = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return CmdResult(command=command, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def append_log(path: Path, title: str, result: CmdResult) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {title}\n")
        f.write(f"$ {result.command}\n")
        f.write(f"exit_code={result.returncode}\n")
        f.write("[stdout]\n")
        f.write(result.stdout or "<empty>\n")
        f.write("\n[stderr]\n")
        f.write(result.stderr or "<empty>\n")
        f.write("\n")


def create_tiny_router_dataset(base: Path) -> dict[str, str]:
    base.mkdir(parents=True, exist_ok=True)
    row = {
        "id": "toy-1",
        "instruction": "Solve quickly: ",
        "input": "1+1?",
        "output": "2",
        "candidates": [
            {
                "model": "llama-31-8b_ourRM_bo1",
                "decoding_method": "",
                "text": "2",
                "scores": {"armoRM_scores": 0.9},
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
    payload = "\n".join(json.dumps({**row, "id": f"toy-{i}"}) for i in range(1, 7)) + "\n"
    train = base / "tiny_train.jsonl"
    valid = base / "tiny_valid.jsonl"
    test = base / "tiny_test.jsonl"
    train.write_text(payload, encoding="utf-8")
    valid.write_text(payload, encoding="utf-8")
    test.write_text(payload, encoding="utf-8")
    return {"train": str(train), "valid": str(valid), "test": str(test)}


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/best_route_full_integration_attempt_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "run_attempt_log.txt"
    log_path.write_text(f"BEST-Route full integration attempt run_id={run_id}\n", encoding="utf-8")
    install_log = out_dir / "install_commands.txt"

    stage_rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    commands_run: list[str] = []
    install_commands: list[str] = []

    def record_stage(name: str, status: str, cmd: str | None, note: str = "", result: CmdResult | None = None, fixable_local: bool | None = None, blocker_type: str | None = None) -> None:
        stage_rows.append({
            "stage": name,
            "status": status,
            "command": cmd or "",
            "exit_code": "" if result is None else result.returncode,
            "note": note,
        })
        if status != "pass":
            blockers.append({
                "stage": name,
                "command": cmd,
                "error": (result.stderr.strip() if result and result.stderr.strip() else note),
                "stdout": "" if result is None else result.stdout,
                "fixable_locally": fixable_local,
                "blocker_type": blocker_type,
            })

    # Stage 1: local config validation
    cmd1 = f"{shlex.quote(sys.executable)} scripts/run_best_route_adjacent_integration.py --import-config {shlex.quote(str(IMPORT_CONFIG))} --contract-config {shlex.quote(str(CONTRACT_CONFIG))}"
    res1 = run_cmd(cmd1, cwd=REPO_ROOT)
    commands_run.append(cmd1)
    append_log(log_path, "stage_1_local_repo_config_validation", res1)
    if res1.returncode == 0:
        record_stage("local_repo_side_config_validation", "pass", cmd1, "adjacent integration contract runner executed")
    else:
        record_stage("local_repo_side_config_validation", "fail", cmd1, "repo-side contract validation failed", res1, True, "code_or_config")

    # Stage 2: upstream clone + markers
    if not UPSTREAM_PATH.exists():
        clone_cmd = f"git clone https://github.com/microsoft/best-route-llm.git {shlex.quote(str(UPSTREAM_PATH))}"
        res_clone = run_cmd(clone_cmd, cwd=REPO_ROOT)
        commands_run.append(clone_cmd)
        append_log(log_path, "stage_2_clone", res_clone)
    git_cmd = "git rev-parse HEAD"
    res2 = run_cmd(git_cmd, cwd=UPSTREAM_PATH)
    commands_run.append(f"(cd {UPSTREAM_PATH} && {git_cmd})")
    append_log(log_path, "stage_2_upstream_access", res2)
    markers = ["README.md", "LICENSE.md", "train_router.py", "notebooks/generate_llm_responses.py", "notebooks/scoring_per_model_armoRM.py", "notebooks/scoring_per_model_ourRM.py"]
    missing_markers = [m for m in markers if not (UPSTREAM_PATH / m).exists()]
    if res2.returncode == 0 and not missing_markers:
        record_stage("upstream_repo_accessibility_clone_validation", "pass", git_cmd, "upstream reachable and expected entrypoints present")
    else:
        record_stage("upstream_repo_accessibility_clone_validation", "fail", git_cmd, f"missing markers: {missing_markers}", res2, True, "upstream_unavailable")

    # Stage 3: dependency install in controlled sequence
    dep_checks: list[dict[str, Any]] = []
    install_sequence = [
        f"{shlex.quote(sys.executable)} -m pip install py-cpuinfo",
        f"{shlex.quote(sys.executable)} -m pip install torch",
        f"{shlex.quote(sys.executable)} -m pip install transformers==4.37.2 accelerate huggingface_hub datasets tqdm trl==0.10.1 scikit-learn pandas sentencepiece",
        f"{shlex.quote(sys.executable)} -m pip install git+https://github.com/yuchenlin/LLM-Blender.git",
        f"{shlex.quote(sys.executable)} -m pip install prettytable tabulate spacy bert_score evaluate sacrebleu rouge_score nltk pycocoevalcap wandb",
    ]
    for idx, cmd in enumerate(install_sequence, start=1):
        res = run_cmd(cmd, cwd=REPO_ROOT, timeout=1800)
        commands_run.append(cmd)
        install_commands.append(cmd)
        append_log(log_path, f"stage_3_install_{idx}", res)
        dep_checks.append({"command": cmd, "exit_code": res.returncode, "stdout": res.stdout, "stderr": res.stderr})

    # verify core imports
    verify_imports_cmd = (
        f"{shlex.quote(sys.executable)} -c \"import torch, transformers, llm_blender; "
        "print({'torch':torch.__version__, 'transformers':transformers.__version__, 'llm_blender':getattr(llm_blender,'__version__','n/a')})\""
    )
    res_imp = run_cmd(verify_imports_cmd, cwd=REPO_ROOT)
    commands_run.append(verify_imports_cmd)
    append_log(log_path, "stage_3_verify_imports", res_imp)
    dep_checks.append({"command": verify_imports_cmd, "exit_code": res_imp.returncode, "stdout": res_imp.stdout, "stderr": res_imp.stderr})
    write_json(out_dir / "dependency_check.json", {"steps": dep_checks})
    install_log.write_text("\n".join(install_commands) + ("\n" if install_commands else ""), encoding="utf-8")

    if all(x["exit_code"] == 0 for x in dep_checks):
        record_stage("dependency_install_and_import_verification", "pass", " ; ".join(install_sequence), "dependencies installed and imports verified")
    else:
        first_fail = next(x for x in dep_checks if x["exit_code"] != 0)
        record_stage("dependency_install_and_import_verification", "fail", first_fail["command"], "dependency install/import failed", CmdResult(first_fail["command"], first_fail["exit_code"], first_fail["stdout"], first_fail["stderr"]), True, "dependency_installation")

    # Stage 4: dataset contract validation
    contract = json.loads(CONTRACT_CONFIG.read_text(encoding="utf-8"))
    ds_checks: list[dict[str, Any]] = []
    missing_local_packages: list[str] = []
    for ds, spec in (contract.get("dataset_import_packages", {}) or {}).items():
        rp = (spec or {}).get("results_path", "")
        exists = bool(rp and (REPO_ROOT / rp).exists())
        ds_checks.append({"dataset": ds, "results_path": rp, "exists": exists})
        if not exists:
            missing_local_packages.append(ds)

    expected_upstream_data = [
        "data/mixed_dataset.jsonl",
        "data/mixed_dataset_ALL.jsonl",
        "data/mixed_dataset_armoRM_ALL.jsonl",
        "data/mixed_dataset_armoRM_ALL_token_num_train.jsonl",
        "data/mixed_dataset_armoRM_ALL_token_num_validation.jsonl",
        "data/mixed_dataset_armoRM_ALL_token_num_test.jsonl",
    ]
    upstream_data_presence = [{"path": p, "exists": (UPSTREAM_PATH / p).exists()} for p in expected_upstream_data]
    write_json(out_dir / "dataset_contract_check.json", {
        "local_import_packages": ds_checks,
        "missing_local_import_packages": missing_local_packages,
        "upstream_required_data_files": upstream_data_presence,
    })

    if missing_local_packages:
        record_stage("dataset_contract_validation", "fail", None, f"missing canonical import packages: {missing_local_packages}", None, False, "missing_data_artifacts")
    else:
        record_stage("dataset_contract_validation", "pass", None, "all configured import packages present")

    # Stage 5: upstream smoke-run
    smoke_help_cmd = f"{shlex.quote(sys.executable)} train_router.py --help"
    res_help = run_cmd(smoke_help_cmd, cwd=UPSTREAM_PATH)
    commands_run.append(f"(cd {UPSTREAM_PATH} && {smoke_help_cmd})")
    append_log(log_path, "stage_5_smoke_help", res_help)
    if res_help.returncode == 0:
        record_stage("upstream_smoke_help", "pass", smoke_help_cmd, "train_router.py --help succeeded")
    else:
        record_stage("upstream_smoke_help", "fail", smoke_help_cmd, "train_router.py --help failed", res_help, True, "upstream_runtime")

    # Stage 6: minimal runnable execution (synthetic tiny training job)
    tiny = create_tiny_router_dataset(out_dir / "synthetic_tiny_dataset")
    tiny_out = out_dir / "tiny_router_run"
    tiny_cmd = (
        f"{shlex.quote(sys.executable)} train_router.py "
        "--model_name hf-internal-testing/tiny-random-roberta "
        f"--train_data_path {shlex.quote(tiny['train'])} "
        f"--eval_data_path {shlex.quote(tiny['valid'])} "
        f"--test_data_path {shlex.quote(tiny['test'])} "
        "--candidate_models llama-31-8b_ourRM_bo1,gpt-4o_ourRM_bo1 "
        "--candidate_decoding_method , "
        "--quality_metric armoRM_scores "
        "--loss_type prob_nlabels "
        "--source_maxlength 64 --candidate_maxlength 64 "
        "--per_device_train_batch_size 1 --per_device_eval_batch_size 1 "
        "--gradient_accumulation_steps 1 --num_train_epochs 1 "
        "--do_train True --do_eval True --do_predict True "
        "--fp16 False --max_train_data_size 4 --max_eval_data_size 4 --max_predict_data_size 4 "
        f"--output_dir {shlex.quote(str(tiny_out))} --overwrite_output_dir True --save_predictions True "
        "--report_to none --run_name tiny_best_route_smoke"
    )
    res_tiny = run_cmd(tiny_cmd, cwd=UPSTREAM_PATH, timeout=2400)
    commands_run.append(f"(cd {UPSTREAM_PATH} && {tiny_cmd})")
    append_log(log_path, "stage_6_tiny_router_train", res_tiny)

    if res_tiny.returncode == 0 and (tiny_out / "predictions.pt").exists():
        record_stage("minimal_end_to_end_router_run", "pass", tiny_cmd, "synthetic tiny train/eval/predict completed")
        write_json(out_dir / "results_summary.json", {
            "tiny_router_run_output": str(tiny_out),
            "predictions_exists": True,
            "note": "This is a code-path smoke run on synthetic data, not a faithful BEST-Route benchmark reproduction.",
        })
    else:
        record_stage("minimal_end_to_end_router_run", "fail", tiny_cmd, "synthetic tiny run failed", res_tiny, True, "runtime_or_model_download")

    # Stage 7: comparison row export check
    adj_rows_cmd = f"{shlex.quote(sys.executable)} scripts/run_best_route_adjacent_integration.py --import-config {shlex.quote(str(IMPORT_CONFIG))} --contract-config {shlex.quote(str(CONTRACT_CONFIG))}"
    res_adj = run_cmd(adj_rows_cmd, cwd=REPO_ROOT)
    commands_run.append(adj_rows_cmd)
    append_log(log_path, "stage_7_adjacent_export", res_adj)

    comp_rows_written = False
    if res_adj.returncode == 0:
        # find latest adjacent run and copy rows for this artifact family
        base = REPO_ROOT / "outputs" / "best_route_adjacent_integration"
        if base.exists():
            runs = sorted([p for p in base.iterdir() if p.is_dir()])
            if runs:
                latest = runs[-1]
                src = latest / "comparison_ready_rows.csv"
                if src.exists():
                    (out_dir / "comparison_ready_rows.csv").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                    comp_rows_written = True
    if comp_rows_written:
        record_stage("comparison_row_export", "pass", adj_rows_cmd, "adjacent comparison rows exported")
    else:
        record_stage("comparison_row_export", "fail", adj_rows_cmd, "could not export adjacent comparison rows", res_adj if res_adj.returncode != 0 else None, True, "comparison_export")

    # final readiness
    full_end_to_end = all(r["status"] == "pass" for r in stage_rows)
    readiness = {
        "baseline": "BEST-Route",
        "run_id": run_id,
        "classification": "fully_runnable" if full_end_to_end else "partially_runnable",
        "full_end_to_end_runnable_in_repo": full_end_to_end,
        "paper_table_ready_now": False if not full_end_to_end else True,
        "notes": [
            "Even when tiny synthetic run succeeds, faithful BEST-Route benchmark reproduction still requires official upstream data-generation/scoring/training workflow on real benchmark prompts.",
        ],
        "remaining_blocker_types": [b["blocker_type"] for b in blockers],
    }
    write_json(out_dir / "comparison_readiness.json", readiness)
    write_json(out_dir / "blockers.json", {"blockers": blockers})

    manifest = {
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_best_route_full_integration_attempt.py",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "commands_run": commands_run,
    }
    write_json(out_dir / "manifest.json", manifest)
    write_csv(out_dir / "stage_status.csv", stage_rows)

    # Artifact integrity stage
    required_files = [
        "manifest.json",
        "environment_check.json",
        "dependency_check.json",
        "install_commands.txt",
        "dataset_contract_check.json",
        "run_attempt_log.txt",
        "stage_status.csv",
        "blockers.json",
        "comparison_readiness.json",
    ]
    # write environment snapshot late so installed packages reflected
    env_cmd = (
        f"{shlex.quote(sys.executable)} -c "
        "\"import json,sys,platform,torch; "
        "print(json.dumps({'python':sys.version,'platform':platform.platform(),"
        "'torch':torch.__version__,'cuda_available':torch.cuda.is_available()}, indent=2))\""
    )
    res_env = run_cmd(env_cmd, cwd=REPO_ROOT)
    append_log(log_path, "environment_snapshot", res_env)
    env_payload = {"command": env_cmd, "exit_code": res_env.returncode, "stdout": res_env.stdout, "stderr": res_env.stderr}
    write_json(out_dir / "environment_check.json", env_payload)

    missing_artifacts = [f for f in required_files if not (out_dir / f).exists()]
    if missing_artifacts:
        record_stage("result_export_validation", "fail", None, f"missing artifacts: {missing_artifacts}", None, True, "artifact_export")
    else:
        record_stage("result_export_validation", "pass", None, "all required artifacts present")

    # rewrite outputs after final stage
    write_csv(out_dir / "stage_status.csv", stage_rows)
    write_json(out_dir / "blockers.json", {"blockers": blockers})
    write_json(out_dir / "comparison_readiness.json", readiness)

    print(json.dumps({
        "run_id": run_id,
        "output_dir": str(out_dir),
        "classification": readiness["classification"],
        "num_blockers": len(blockers),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
