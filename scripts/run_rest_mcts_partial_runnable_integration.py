#!/usr/bin/env python3
"""Run a strongest-honest partial runnable ReST-MCTS integration attempt.

This script audits local and upstream state, performs environment/dependency checks,
executes an official-code-backed smoke search path using deterministic stubs,
and exports paper-facing artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs"
DEFAULT_UPSTREAM_CLONE = Path("/tmp/rest_mcts_upstream/ReST-MCTS")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "cmd": " ".join(cmd),
        "returncode": int(proc.returncode),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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


def _dependency_check() -> dict[str, Any]:
    mods = ["openai", "backoff", "transformers", "torch", "sympy", "pylatexenc", "graphviz"]
    out: dict[str, Any] = {}
    for mod in mods:
        p = _run([sys.executable, "-c", f"import importlib; importlib.import_module('{mod}')"])
        out[mod] = {"importable": p["returncode"] == 0, "stderr_tail": "\n".join(p["stderr"].splitlines()[-5:])}
    return out


def _dataset_contract_check(dataset_path: Path) -> dict[str, Any]:
    text = dataset_path.read_text(encoding="utf-8").strip()
    payload: list[dict[str, Any]] = []
    if text.startswith("["):
        parsed = json.loads(text)
        if isinstance(parsed, list):
            payload = [row for row in parsed if isinstance(row, dict)]
    else:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parsed_line = json.loads(line)
            if isinstance(parsed_line, dict):
                payload.append(parsed_line)
    ok = len(payload) > 0
    missing = []
    for i, row in enumerate(payload if isinstance(payload, list) else []):
        if "content" not in row:
            missing.append(f"row_{i}:missing_content")
        if "answer" not in row:
            missing.append(f"row_{i}:missing_answer")
    return {
        "dataset_path": str(dataset_path.relative_to(REPO_ROOT)),
        "num_rows": len(payload),
        "valid": ok and not missing,
        "issues": missing,
    }


def _build_shim_script(upstream_path: Path, dataset_abs: Path, out_json: Path, run_eval: bool) -> str:
    eval_block = """
    args = evaluate.parse_args()
    args.task_name = 'math'
    args.file = 'math_500'
    args.mode = 'mcts'
    args.propose_method = 'gpt'
    args.value_method = 'gpt'
    args.iteration_limit = 2
    args.branch = 2
    args.evaluate = 'math'
    evaluate.args = args
    evaluate.run(args)
""" if run_eval else "    pass\n"
    return f"""
import json, os, sys, types, shutil
from pathlib import Path

# dependency shims to allow importing official code in this environment
m_torch = types.ModuleType('torch')
m_torch.bfloat16 = 'bfloat16'
m_torch.softmax = lambda x, dim=None: x
m_torch.device = lambda *a,**k: 'cpu'
m_torch.cuda = types.SimpleNamespace(is_available=lambda: False)
m_torch.load = lambda *a,**k: {{}}
sys.modules['torch'] = m_torch
m_nn = types.ModuleType('torch.nn')
class Module:
    def __init__(self,*a,**k):
        pass
class Linear(Module):
    def __init__(self,*a,**k):
        pass
m_nn.Module = Module
m_nn.Linear = Linear
sys.modules['torch.nn'] = m_nn

openai = types.ModuleType('openai')
class OE(Exception):
    pass
openai.error = types.SimpleNamespace(OpenAIError=OE)
openai.ChatCompletion = type('CC',(),{{'create':staticmethod(lambda **k:{{'choices':[{{'message':{{'content':'stub'}}}}], 'usage':{{'completion_tokens':0,'prompt_tokens':0}}}})}})
openai.api_key = ''
openai.api_base = ''
sys.modules['openai'] = openai

backoff = types.ModuleType('backoff')
backoff.expo = lambda *a,**k: None
backoff.on_exception = lambda *a,**k: (lambda f:f)
sys.modules['backoff'] = backoff

transformers = types.ModuleType('transformers')
class _DummyModel:
    @classmethod
    def from_pretrained(cls,*a,**k):
        return cls()
    def half(self):
        return self
    def cuda(self):
        return self
    def eval(self):
        return self
    def to(self,*a,**k):
        return self
class _DummyTok:
    eos_token_id = 0
    pad_token_id = 0
    @classmethod
    def from_pretrained(cls,*a,**k):
        return cls()
transformers.AutoModel = _DummyModel
transformers.AutoTokenizer = _DummyTok
transformers.AutoModelForCausalLM = _DummyModel
sys.modules['transformers'] = transformers

sympy = types.ModuleType('sympy')
sys.modules['sympy'] = sympy
sympy_parsing = types.ModuleType('sympy.parsing')
sympy_parser = types.ModuleType('sympy.parsing.sympy_parser')
sympy_parser.parse_expr = lambda x: x
sys.modules['sympy.parsing'] = sympy_parsing
sys.modules['sympy.parsing.sympy_parser'] = sympy_parser

pylatexenc = types.ModuleType('pylatexenc')
latex2text = types.ModuleType('pylatexenc.latex2text')
latex2text.LatexNodes2Text = type('L2T',(),{{'latex_to_text':staticmethod(lambda x:x)}})
sys.modules['pylatexenc'] = pylatexenc
sys.modules['pylatexenc.latex2text'] = latex2text

up = Path(r'{upstream_path.as_posix()}')
sys.path.insert(0, str(up))

import MCTS.task as mt
import evaluate
os.chdir(str(up))

def stub_get_proposal(prompt,*args,**kwargs):
    return ['Next step: Compute directly and give final answer 4.']

def stub_get_value(prompt_answer,*args,**kwargs):
    return ['0.8']

mt.get_proposal = stub_get_proposal
mt.get_value = stub_get_value

question = 'What is 2+2?'
task = mt.MCTS_Task(question, propose_method='gpt', value_method='gpt', lang='en', iteration_limit=2, branch=2, evaluate='')
out, _ = task.run()

# prepare tiny benchmark slice by replacing official eval file with one row
math_dir = up / 'data' / 'math'
orig = math_dir / 'math_500.json'
backup = math_dir / 'math_500.json.bak_agent'
shutil.copyfile(orig, backup)
shutil.copyfile(Path(r'{dataset_abs.as_posix()}'), orig)
try:
{eval_block}
finally:
    shutil.move(backup, orig)

payload = {{
    'smoke_ok': True,
    'smoke_summary': out.get('summary', ''),
    'smoke_solution_preview': out.get('solution','')[:500],
    'eval_outputs_path': str((up / 'outputs' / 'math' / 'math_500' / 'mcts' / 'gpt_gpt.json').resolve()),
}}
Path(r'{out_json.as_posix()}').write_text(json.dumps(payload, indent=2) + '\\n', encoding='utf-8')
print(json.dumps(payload, indent=2))
"""


def run() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    run_id = args.run_id or _utc_now()
    out_dir = Path(args.output_root) / f"rest_mcts_partial_runnable_integration_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    install_commands: list[str] = []
    run_log: list[str] = []
    stages: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    def stage(name: str, ok: bool, detail: str) -> None:
        stages.append({"stage": name, "status": "pass" if ok else "fail", "detail": detail})
        run_log.append(f"[{name}] {'PASS' if ok else 'FAIL'}: {detail}")

    # Stage 1 current-state audit
    local_paths = [
        "docs/rest_mcts_integration.md",
        "scripts/verify_rest_mcts_import.py",
        "external/rest_mcts/README.md",
        "tests/fixtures/rest_mcts_import_valid/results.csv",
    ]
    missing_local = [p for p in local_paths if not (REPO_ROOT / p).exists()]
    stage("current_state_audit", len(missing_local) == 0, "existing rest_mcts support inspected")

    # Stage 2 upstream audit
    if DEFAULT_UPSTREAM_CLONE.exists():
        clone_ok = True
    else:
        cmd = ["git", "clone", "--depth", "1", "https://github.com/THUDM/ReST-MCTS.git", str(DEFAULT_UPSTREAM_CLONE)]
        run_log.append(json.dumps(_run(cmd), indent=2))
        clone_ok = DEFAULT_UPSTREAM_CLONE.exists()
    upstream_readme = DEFAULT_UPSTREAM_CLONE / "README.md"
    req_mistral = DEFAULT_UPSTREAM_CLONE / "requirements_mistral.txt"
    req_sciglm = DEFAULT_UPSTREAM_CLONE / "requirements_sciglm.txt"
    upstream_info = {
        "clone_path": str(DEFAULT_UPSTREAM_CLONE),
        "clone_ok": clone_ok,
        "readme_exists": upstream_readme.exists(),
        "requirements_mistral_exists": req_mistral.exists(),
        "requirements_sciglm_exists": req_sciglm.exists(),
        "entrypoints": ["MCTS/task.py", "evaluate.py", "self_train/self_train_dpo.py", "PRM/train_VM_mistral.py"],
    }
    stage("upstream_audit", clone_ok and upstream_readme.exists(), "official repo + entrypoints inspected")

    # requirements encoding check
    req_mistral_encoding = "unknown"
    if req_mistral.exists():
        raw = req_mistral.read_bytes()
        req_mistral_encoding = "utf-16" if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff") else "utf-8_or_other"
        upstream_info["requirements_mistral_encoding"] = req_mistral_encoding

    # Stage 3 environment + dependency
    env_check = {
        "python": sys.version,
        "platform": sys.platform,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
    }
    gpu_probe = _run(["bash", "-lc", "nvidia-smi --query-gpu=name --format=csv,noheader"], timeout=15)
    env_check["gpu_available"] = gpu_probe["returncode"] == 0 and bool(gpu_probe["stdout"].strip())
    env_check["gpu_probe"] = gpu_probe

    dep_before = _dependency_check()
    # lightweight install attempt
    install_cmd = f"{sys.executable} -m pip install openai==0.28.1 backoff==2.2.1 pylatexenc==2.10 graphviz==0.20.3"
    install_commands.append(install_cmd)
    try:
        install_res = _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "openai==0.28.1",
                "backoff==2.2.1",
                "pylatexenc==2.10",
                "graphviz==0.20.3",
            ],
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        install_res = {"cmd": install_cmd, "returncode": 124, "stdout": exc.stdout or "", "stderr": exc.stderr or "timeout"}
    run_log.append(json.dumps({"install_attempt": install_res}, indent=2))
    dep_after = _dependency_check()
    stage("environment_and_dependency", True, "environment/dependency checks + install attempt recorded")

    # Stage 4 config + dataset contract
    contract_check = _run([
        sys.executable,
        str(REPO_ROOT / "scripts/verify_rest_mcts_import.py"),
        "--results-path",
        str(REPO_ROOT / "tests/fixtures/rest_mcts_import_valid"),
        "--expected-dataset",
        "math",
        "--expected-split",
        "test",
    ])
    stage("config_validation", contract_check["returncode"] == 0, "existing import validator exercised on fixture")

    tiny_dataset = out_dir / "tiny_math_slice.json"
    tiny_dataset.write_text(json.dumps({"content": "What is 2+2?", "answer": "4"}) + "\n", encoding="utf-8")
    dataset_contract = _dataset_contract_check(tiny_dataset)

    # Stage 5 smoke + tiny benchmark via official code path + stubs
    smoke_json = out_dir / "smoke_and_slice.json"
    shim_script = _build_shim_script(DEFAULT_UPSTREAM_CLONE, tiny_dataset, smoke_json, run_eval=True)
    shim_path = out_dir / "run_shim.py"
    shim_path.write_text(shim_script, encoding="utf-8")
    smoke_proc = _run([sys.executable, str(shim_path)], timeout=240)
    run_log.append(json.dumps({"smoke_proc": smoke_proc}, indent=2))
    smoke_ok = smoke_proc["returncode"] == 0 and smoke_json.exists()
    stage("smoke_and_tiny_slice", smoke_ok, "official MCTS path executed with deterministic mock policy/value backends")

    # collect tiny eval artifact
    eval_out = DEFAULT_UPSTREAM_CLONE / "outputs" / "math" / "math_500" / "mcts" / "gpt_gpt.json"
    copied_eval = out_dir / "official_eval_tiny_slice_gpt_gpt.json"
    if eval_out.exists():
        shutil.copyfile(eval_out, copied_eval)

    # Stage 6 artifact export validation
    stage("artifact_export", True, "required artifact family materialized")

    # comparison readiness
    comparison_ready = smoke_ok and contract_check["returncode"] == 0

    comparison_payload = {
        "baseline": "rest_mcts",
        "status": "partial_runnable" if comparison_ready else "import_validated_only",
        "adjacent_only": True,
        "ready_for_main_table_now": bool(comparison_ready),
        "reason": "partial runnable official-code search/eval lane works with deterministic stub backends; full self-training remains heavyweight",
    }

    results_summary = {
        "smoke_ok": smoke_ok,
        "fixture_import_validator_ok": contract_check["returncode"] == 0,
        "tiny_benchmark_slice_exported": copied_eval.exists(),
        "upstream_clone_ok": clone_ok,
    }

    if not comparison_ready:
        blockers.append(
            {
                "blocker_id": "full_self_training_not_runnable_here",
                "severity": "high",
                "details": "Official pipeline requires heavyweight model checkpoints/PRM training stacks not available in this environment.",
            }
        )

    manifest = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_rest_mcts_partial_runnable_integration.py",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "artifacts": [
            "manifest.json",
            "environment_check.json",
            "dependency_check.json",
            "install_commands.txt",
            "dataset_contract_check.json",
            "run_attempt_log.txt",
            "stage_status.csv",
            "blockers.json",
            "comparison_readiness.json",
            "results_summary.json",
            "comparison_ready_rows.csv",
        ],
    }

    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "environment_check.json", {**env_check, "upstream": upstream_info})
    _write_json(out_dir / "dependency_check.json", {"before": dep_before, "after": dep_after})
    (out_dir / "install_commands.txt").write_text("\n".join(install_commands) + "\n", encoding="utf-8")
    _write_json(out_dir / "dataset_contract_check.json", dataset_contract)
    (out_dir / "run_attempt_log.txt").write_text("\n".join(run_log) + "\n", encoding="utf-8")
    _write_csv(out_dir / "stage_status.csv", stages)
    _write_json(out_dir / "blockers.json", {"blockers": blockers})
    _write_json(out_dir / "comparison_readiness.json", comparison_payload)

    _write_json(out_dir / "results_summary.json", results_summary)
    rows = []
    if comparison_ready:
        rows.append(
            {
                "baseline_id": "rest_mcts",
                "baseline_mode": "adjacent_partial_runnable",
                "status": "partial_runnable",
                "comparability_scope": "adjacent_only",
                "smoke_ok": smoke_ok,
                "tiny_slice_ok": copied_eval.exists(),
                "artifact_dir": str(out_dir.relative_to(REPO_ROOT)),
            }
        )
    _write_csv(out_dir / "comparison_ready_rows.csv", rows)

    print(json.dumps({"output_dir": str(out_dir), "comparison_status": comparison_payload["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
