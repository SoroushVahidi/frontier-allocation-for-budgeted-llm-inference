#!/usr/bin/env python3
"""Safe provider readiness check for Cohere and Hugging Face."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COHERE_KEY_ENV = "COHERE_API_KEY"
HF_TOKEN_ENV = "HF_TOKEN"
HF_HUB_TOKEN_ENV = "HUGGINGFACE_HUB_TOKEN"

COHERE_STATUSES = {
    "passed",
    "missing_key",
    "sdk_missing",
    "sdk_install_failed",
    "invalid_key",
    "quota_or_billing",
    "rate_limit",
    "model_unavailable",
    "network_error",
    "unknown_error",
}

HF_STATUSES = {
    "passed",
    "missing_token",
    "sdk_missing",
    "sdk_install_failed",
    "invalid_token",
    "rate_limit",
    "network_error",
    "service_error",
    "unknown_error",
}


def _tracked_secret_values() -> list[str]:
    values: list[str] = []
    for env_name in (COHERE_KEY_ENV, HF_TOKEN_ENV, HF_HUB_TOKEN_ENV):
        value = os.getenv(env_name)
        if value:
            values.append(value)
    return values


def sanitize_error_message(message: str, secret_values: list[str] | None = None) -> str:
    """Redact known secret values and clamp noisy content."""
    if not message:
        return ""
    sanitized = message
    for secret in secret_values or _tracked_secret_values():
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    # Best-effort masking for header-style credential fragments.
    sanitized = re.sub(r"(?i)(authorization\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]", sanitized)
    sanitized = re.sub(r"[\r\n\t]+", " ", sanitized).strip()
    return sanitized[:500]


def _classify_cohere_error(error_text: str) -> str:
    text = (error_text or "").lower()
    if any(token in text for token in ("api key", "unauthorized", "invalid api key", "401")):
        return "invalid_key"
    if any(token in text for token in ("quota", "billing", "payment required", "credit")):
        return "quota_or_billing"
    if any(token in text for token in ("rate limit", "429", "too many requests")):
        return "rate_limit"
    if any(token in text for token in ("model", "not found", "unavailable", "does not exist")):
        return "model_unavailable"
    if any(token in text for token in ("connection", "timeout", "timed out", "dns", "network")):
        return "network_error"
    return "unknown_error"


def _classify_hf_error(error_text: str) -> str:
    text = (error_text or "").lower()
    if any(token in text for token in ("unauthorized", "invalid token", "401", "forbidden", "403")):
        return "invalid_token"
    if any(token in text for token in ("rate limit", "429", "too many requests")):
        return "rate_limit"
    if any(token in text for token in ("connection", "timeout", "timed out", "dns", "network")):
        return "network_error"
    if any(token in text for token in ("5xx", "service unavailable", "internal server error", "bad gateway")):
        return "service_error"
    return "unknown_error"


def _try_import_sdk() -> tuple[bool, bool]:
    cohere_ok = True
    hf_ok = True
    try:
        import cohere  # noqa: F401
    except Exception:
        cohere_ok = False
    try:
        import huggingface_hub  # noqa: F401
    except Exception:
        hf_ok = False
    return cohere_ok, hf_ok


def ensure_sdks() -> dict[str, Any]:
    initial_cohere, initial_hf = _try_import_sdk()
    install_attempted = False
    install_failed = False
    install_error = ""

    if not (initial_cohere and initial_hf):
        install_attempted = True
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "cohere", "huggingface_hub"],
                check=False,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                install_failed = True
                install_error = sanitize_error_message(proc.stderr or proc.stdout or "pip install failed")
        except Exception as exc:
            install_failed = True
            install_error = sanitize_error_message(str(exc))

    after_cohere, after_hf = _try_import_sdk()
    return {
        "cohere_initial": initial_cohere,
        "hf_initial": initial_hf,
        "install_attempted": install_attempted,
        "install_failed": install_failed,
        "install_error": install_error,
        "cohere_after": after_cohere,
        "hf_after": after_hf,
    }


@dataclass
class ProviderResult:
    readiness_status: str
    sanitized_error: str


def check_cohere(model_name: str, sdk_state: dict[str, Any]) -> ProviderResult:
    key_present = bool(os.getenv(COHERE_KEY_ENV))
    if not key_present:
        return ProviderResult("missing_key", "")
    if not sdk_state["cohere_initial"] and not sdk_state["cohere_after"]:
        return ProviderResult(
            "sdk_install_failed" if sdk_state["install_attempted"] else "sdk_missing",
            sdk_state["install_error"],
        )
    if not sdk_state["cohere_after"]:
        return ProviderResult("sdk_missing", "")

    try:
        import cohere

        client = cohere.ClientV2(api_key=os.getenv(COHERE_KEY_ENV, ""))
        # Cohere SDK signatures vary across versions; try a few tiny-call shapes.
        called = False
        errors: list[str] = []
        for call in (
            lambda: client.chat(model=model_name, message="ping", max_tokens=1),
            lambda: client.chat(model=model_name, messages=[{"role": "user", "content": "ping"}], max_tokens=1),
            lambda: client.generate(model=model_name, prompt="ping", max_tokens=1),
        ):
            try:
                call()
                called = True
                break
            except TypeError as exc:
                errors.append(str(exc))
                continue
        if not called and errors:
            raise RuntimeError(errors[-1])
        return ProviderResult("passed", "")
    except Exception as exc:
        sanitized = sanitize_error_message(str(exc))
        status = _classify_cohere_error(sanitized)
        if status not in COHERE_STATUSES:
            status = "unknown_error"
        return ProviderResult(status, sanitized)


def check_huggingface(sdk_state: dict[str, Any]) -> ProviderResult:
    hf_token_present = bool(os.getenv(HF_TOKEN_ENV))
    hf_hub_token_present = bool(os.getenv(HF_HUB_TOKEN_ENV))
    token = os.getenv(HF_TOKEN_ENV) or os.getenv(HF_HUB_TOKEN_ENV) or ""
    if not (hf_token_present or hf_hub_token_present):
        return ProviderResult("missing_token", "")
    if not sdk_state["hf_initial"] and not sdk_state["hf_after"]:
        return ProviderResult(
            "sdk_install_failed" if sdk_state["install_attempted"] else "sdk_missing",
            sdk_state["install_error"],
        )
    if not sdk_state["hf_after"]:
        return ProviderResult("sdk_missing", "")

    try:
        from huggingface_hub import HfApi

        api = HfApi(token=token)
        api.whoami()
        return ProviderResult("passed", "")
    except Exception as exc:
        first_error = sanitize_error_message(str(exc))
        try:
            from huggingface_hub import HfApi

            api = HfApi(token=token)
            api.model_info("bert-base-uncased")
            return ProviderResult("passed", "")
        except Exception as inner_exc:
            sanitized = sanitize_error_message(str(inner_exc) or first_error)
            status = _classify_hf_error(sanitized)
            if status not in HF_STATUSES:
                status = "unknown_error"
            return ProviderResult(status, sanitized)


def build_summary(output_dir: str, cohere_model: str) -> dict[str, Any]:
    sdk_state = ensure_sdks()
    cohere_result = check_cohere(cohere_model, sdk_state)
    hf_result = check_huggingface(sdk_state)

    git_sha = "unknown"
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            git_sha = (proc.stdout or "").strip() or "unknown"
    except Exception:
        git_sha = "unknown"

    return {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit_sha": git_sha,
        "python_executable": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "cohere": {
            "env_var_checked": [COHERE_KEY_ENV],
            "key_present": bool(os.getenv(COHERE_KEY_ENV)),
            "sdk_import_initial": sdk_state["cohere_initial"],
            "sdk_install_attempted": sdk_state["install_attempted"],
            "sdk_import_after_install": sdk_state["cohere_after"],
            "readiness_status": cohere_result.readiness_status,
            "model_requested": cohere_model,
            "sanitized_error": cohere_result.sanitized_error,
        },
        "huggingface": {
            "env_var_checked": [HF_TOKEN_ENV, HF_HUB_TOKEN_ENV],
            "hf_token_present": bool(os.getenv(HF_TOKEN_ENV)),
            "huggingface_hub_token_present": bool(os.getenv(HF_HUB_TOKEN_ENV)),
            "sdk_import_initial": sdk_state["hf_initial"],
            "sdk_install_attempted": sdk_state["install_attempted"],
            "sdk_import_after_install": sdk_state["hf_after"],
            "readiness_status": hf_result.readiness_status,
            "sanitized_error": hf_result.sanitized_error,
        },
        "no_secret_values_written": True,
        "_meta": {"output_dir": output_dir},
    }


def _write_report(summary: dict[str, Any], output_dir: Path) -> None:
    cohere_status = summary["cohere"]["readiness_status"]
    hf_status = summary["huggingface"]["readiness_status"]
    cohere_usable = "yes" if cohere_status == "passed" else "no"
    hf_usable = "yes" if hf_status == "passed" else "no"

    def blocker(status: str, err: str) -> str:
        if status == "passed":
            return "none"
        return err or status

    report = [
        "# Provider Readiness Report",
        "",
        f"- Cohere usable: **{cohere_usable}** (`{cohere_status}`)",
        f"- Hugging Face usable: **{hf_usable}** (`{hf_status}`)",
        f"- Cohere blocker: {blocker(cohere_status, summary['cohere']['sanitized_error'])}",
        f"- Hugging Face blocker: {blocker(hf_status, summary['huggingface']['sanitized_error'])}",
        "- No secret values were printed or written.",
    ]
    (output_dir / "provider_readiness_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def write_outputs(summary: dict[str, Any], output_dir: str) -> None:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "provider_readiness_summary.json").write_text(
        json.dumps({k: v for k, v in summary.items() if k != "_meta"}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_report(summary, out_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Cohere/Hugging Face readiness safely.")
    parser.add_argument("--output-dir", required=True, help="Directory for summary/report outputs.")
    parser.add_argument("--cohere-model", default="command-a-03-2025", help="Cohere model for tiny auth call.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_summary(args.output_dir, args.cohere_model)
    write_outputs(summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
