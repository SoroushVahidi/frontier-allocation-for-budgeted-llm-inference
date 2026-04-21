#!/usr/bin/env python3
"""Audit HF access gaps and produce actionable checklist."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from huggingface_hub import HfApi

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "outputs" / "hf_access_gap_audit" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    token_present = bool(os.getenv("HF_TOKEN"))
    api = HfApi()
    whoami = {}
    if token_present:
        try:
            whoami = api.whoami()
        except Exception:
            whoami = {}

    checks = {}
    for repo_id in [
        "sc-genrm-scaling/llama_3.1_8b_genrm_ft",
        "sc-genrm-scaling/qwen_2.5_7b_genrm_ft",
    ]:
        ok = True
        err = ""
        try:
            api.model_info(repo_id)
        except Exception as exc:
            ok = False
            err = str(exc)[:240]
        checks[repo_id] = {"ok": ok, "error": err}

    for repo_id in [
        "sc-genrm-scaling/MATH128_Solutions_Llama-3.1-8B-Instruct",
        "sc-genrm-scaling/MATH128_verifications_GenRM-FT_Llama-3.1-8B-Instruct",
    ]:
        ok = True
        err = ""
        try:
            api.dataset_info(repo_id)
        except Exception as exc:
            ok = False
            err = str(exc)[:240]
        checks[repo_id] = {"ok": ok, "error": err}

    s1 = _read_json(REPO_ROOT / "configs/s1_full_or_official_adapter_v1.json")
    tale = _read_json(REPO_ROOT / "configs/tale_official_adapter_v1.json")
    l1 = _read_json(REPO_ROOT / "configs/l1_official_full_adapter_v1.json")
    mode_b_paths = {
        "s1_mode_b_results_path": str(s1.get("official", {}).get("results_path", "")),
        "tale_mode_b_results_path": str(tale.get("official", {}).get("results_path", "")),
        "l1_mode_b_results_path": str(l1.get("official", {}).get("results_path", "")),
    }

    checklist = [
        {
            "item": "HF token available to job environment",
            "status": "done" if token_present else "blocked",
            "next_action": "Set HF_TOKEN in job env if blocked.",
        },
        {
            "item": "when_solve_when_verify official HF artifacts accessible",
            "status": "done" if all(v["ok"] for k, v in checks.items() if "sc-genrm-scaling/" in k) else "blocked",
            "next_action": "Check permissions/network if blocked.",
        },
        {
            "item": "s1/TALE/L1 MODE B official result packages configured",
            "status": "blocked" if any(not v for v in mode_b_paths.values()) else "done",
            "next_action": "Provide validated official MODE B package paths for s1/TALE/L1.",
        },
        {
            "item": "OpenAI API key required for exact GPT-4o synthetic verification reproduction",
            "status": "blocked_optional",
            "next_action": "Provide OPENAI_API_KEY only if exact upstream data-generation path is required.",
        },
    ]

    payload = {
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "hf_token_present": token_present,
        "hf_user": whoami.get("name") or whoami.get("fullname") or "",
        "checks": checks,
        "mode_b_results_paths": mode_b_paths,
        "checklist": checklist,
    }
    (out_dir / "hf_access_gap_audit.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# HF access gap audit",
        "",
        f"- run_id: `{run_id}`",
        f"- hf_token_present: `{token_present}`",
        f"- hf_user: `{payload['hf_user']}`",
        "",
        "## Actionable checklist",
    ]
    for row in checklist:
        lines.append(f"- [{ 'x' if row['status']=='done' else ' '}] {row['item']} ({row['status']})")
        lines.append(f"  - next: {row['next_action']}")
    (out_dir / "hf_access_gap_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "run_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
