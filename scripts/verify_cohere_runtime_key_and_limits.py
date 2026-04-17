#!/usr/bin/env python3
"""Bounded verification that runtime is using the intended Cohere key and no longer trial-limited."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

import cohere


MODEL_NAME = "command-r-plus-08-2024"


def _mask_key(key: str) -> dict[str, Any]:
    if not key:
        return {"present": False, "prefix": None, "suffix": None, "sha256_12": None, "length": 0}
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return {
        "present": True,
        "prefix": key[:6],
        "suffix": key[-4:],
        "sha256_12": digest[:12],
        "length": len(key),
    }


def _extract_text(resp: Any) -> str:
    msg = getattr(resp, "message", None)
    content = getattr(msg, "content", None)
    if not content:
        return ""
    first = content[0]
    txt = getattr(first, "text", "")
    return str(txt or "")


def _probe_once(client: cohere.ClientV2, model: str) -> dict[str, Any]:
    prompt = "Reply with exactly: OK"
    start = time.perf_counter()
    try:
        resp = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=8,
        )
        latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
        text = _extract_text(resp).strip()
        return {
            "success": True,
            "latency_ms": latency_ms,
            "http_429": False,
            "response_preview": text[:80],
            "error_type": None,
            "error_message": None,
        }
    except Exception as exc:  # noqa: BLE001
        latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
        err = str(exc)
        is_429 = ("429" in err) or ("toomanyrequests" in type(exc).__name__.lower())
        return {
            "success": False,
            "latency_ms": latency_ms,
            "http_429": is_429,
            "response_preview": None,
            "error_type": type(exc).__name__,
            "error_message": err[:500],
        }


def _burst(client: cohere.ClientV2, model: str, requests: int, sleep_sec: float) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    had_429 = False
    stopped_early = False

    for i in range(requests):
        result = _probe_once(client=client, model=model)
        result["request_index"] = i + 1
        events.append(result)

        if result["http_429"]:
            had_429 = True
            stopped_early = True
            break

        if sleep_sec > 0 and i < requests - 1:
            time.sleep(sleep_sec)

    success_count = sum(1 for e in events if e["success"])
    fail_count = len(events) - success_count
    latencies = [e["latency_ms"] for e in events if e["latency_ms"] is not None]
    return {
        "requested_count": requests,
        "executed_count": len(events),
        "success_count": success_count,
        "failure_count": fail_count,
        "had_429": had_429,
        "stopped_early": stopped_early,
        "latency_ms_min": min(latencies) if latencies else None,
        "latency_ms_max": max(latencies) if latencies else None,
        "latency_ms_avg": (round(sum(latencies) / len(latencies), 2) if latencies else None),
        "events": events,
    }


def _runtime_key_diagnostic() -> dict[str, Any]:
    env_key = os.environ.get("COHERE_API_KEY", "")
    key_info = _mask_key(env_key)
    return {
        "cohere_api_key_present": key_info["present"],
        "cohere_api_key_fingerprint": {
            "prefix": key_info["prefix"],
            "suffix": key_info["suffix"],
            "sha256_12": key_info["sha256_12"],
            "length": key_info["length"],
        },
        "runtime_path_used": "os.environ['COHERE_API_KEY'] (same path used by scripts/cohere_adjudicate_hard_pairs.py)",
        "inference_about_cached_old_key": (
            "No evidence of cached key in-process; client is instantiated directly from current os.environ value"
            if key_info["present"]
            else "Unable to infer caching because COHERE_API_KEY is missing"
        ),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify Cohere production key usage and bounded rate-limit behavior")
    p.add_argument("--run-id", default=f"cohere_production_key_verification_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    p.add_argument("--output-root", default="outputs/cohere_runtime_verification")
    p.add_argument("--doc-path", default="")
    p.add_argument("--model", default=MODEL_NAME)
    p.add_argument("--burst-count", type=int, default=8)
    p.add_argument("--burst-sleep-sec", type=float, default=0.2)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ts = datetime.now(timezone.utc).isoformat()
    out_dir = Path(args.output_root) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    key_diag = _runtime_key_diagnostic()

    results: dict[str, Any] = {
        "run_id": args.run_id,
        "timestamp_utc": ts,
        "model": args.model,
        "runtime_key_diagnostic": key_diag,
    }

    if not key_diag["cohere_api_key_present"]:
        results["probe_result"] = {
            "success": False,
            "latency_ms": None,
            "http_429": False,
            "error_type": "MissingAPIKey",
            "error_message": "COHERE_API_KEY is missing",
        }
        results["burst_result"] = {
            "requested_count": args.burst_count,
            "executed_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "had_429": False,
            "stopped_early": True,
            "events": [],
        }
        results["final_status"] = {
            "ready_for_bounded_hard_pair_adjudication": False,
            "reason": "stale_or_missing_runtime_key",
            "details": "COHERE_API_KEY missing in runtime environment",
        }
    else:
        env_key = os.environ["COHERE_API_KEY"]
        client = cohere.ClientV2(api_key=env_key)

        probe = _probe_once(client=client, model=args.model)
        burst = _burst(client=client, model=args.model, requests=max(1, args.burst_count), sleep_sec=max(0.0, args.burst_sleep_sec))

        if probe["http_429"] or burst["had_429"]:
            ready = False
            reason = "rate_limit_still_active"
            details = "429 observed during probe or bounded burst"
        elif not probe["success"]:
            ready = False
            reason = "probe_failed_non_429"
            details = probe["error_message"] or "unknown error"
        else:
            ready = True
            reason = "bounded_probe_ok"
            details = "Probe and bounded burst completed without 429"

        results["probe_result"] = probe
        results["burst_result"] = burst
        results["final_status"] = {
            "ready_for_bounded_hard_pair_adjudication": ready,
            "reason": reason,
            "details": details,
        }

    key_file = out_dir / "safe_key_fingerprint.json"
    probe_file = out_dir / "probe_result.json"
    burst_file = out_dir / "burst_test_summary.json"
    final_file = out_dir / "final_status.json"
    full_file = out_dir / "verification_full.json"

    key_file.write_text(json.dumps(results["runtime_key_diagnostic"], indent=2) + "\n", encoding="utf-8")
    probe_file.write_text(json.dumps(results.get("probe_result", {}), indent=2) + "\n", encoding="utf-8")
    burst_file.write_text(json.dumps(results.get("burst_result", {}), indent=2) + "\n", encoding="utf-8")
    final_file.write_text(json.dumps(results.get("final_status", {}), indent=2) + "\n", encoding="utf-8")
    full_file.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    if args.doc_path:
        doc_path = Path(args.doc_path)
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        status = results["final_status"]
        probe = results.get("probe_result", {})
        burst = results.get("burst_result", {})
        key_fp = results["runtime_key_diagnostic"]["cohere_api_key_fingerprint"]
        lines = [
            "# Cohere production-key runtime verification pass (2026-04-17)",
            "",
            f"Run ID: `{args.run_id}`",
            "",
            "## Runtime key usage check",
            f"- Runtime key path inspected: `{results['runtime_key_diagnostic']['runtime_path_used']}`.",
            f"- Key present: `{results['runtime_key_diagnostic']['cohere_api_key_present']}`.",
            f"- Safe key fingerprint: prefix `{key_fp['prefix']}`, suffix `{key_fp['suffix']}`, sha256_12 `{key_fp['sha256_12']}`, length `{key_fp['length']}`.",
            f"- Cached/old-key inference: {results['runtime_key_diagnostic']['inference_about_cached_old_key']}",
            "",
            "## Tiny live Cohere probe",
            f"- Model: `{args.model}`.",
            f"- Success: `{probe.get('success')}`.",
            f"- Latency ms: `{probe.get('latency_ms')}`.",
            f"- 429 observed: `{probe.get('http_429')}`.",
            f"- Error (if any): `{probe.get('error_type')}` / `{probe.get('error_message')}`.",
            "",
            "## Bounded burst test",
            f"- Requested count: `{burst.get('requested_count')}`; executed: `{burst.get('executed_count')}`.",
            f"- Successes: `{burst.get('success_count')}`; failures: `{burst.get('failure_count')}`.",
            f"- 429 observed: `{burst.get('had_429')}`; stopped early: `{burst.get('stopped_early')}`.",
            f"- Latency min/avg/max (ms): `{burst.get('latency_ms_min')}` / `{burst.get('latency_ms_avg')}` / `{burst.get('latency_ms_max')}`.",
            "",
            "## Final readiness decision",
            f"- Ready for rerunning bounded Cohere hard-pair adjudication: `{status.get('ready_for_bounded_hard_pair_adjudication')}`.",
            f"- Decision reason: `{status.get('reason')}`.",
            f"- Details: {status.get('details')}",
            "",
            "## Artifacts",
            f"- `{key_file.as_posix()}`",
            f"- `{probe_file.as_posix()}`",
            f"- `{burst_file.as_posix()}`",
            f"- `{final_file.as_posix()}`",
            f"- `{full_file.as_posix()}`",
        ]
        doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "run_id": args.run_id,
        "output_dir": out_dir.as_posix(),
        "doc_path": args.doc_path,
        "final_status": results.get("final_status", {}),
    }, indent=2))


if __name__ == "__main__":
    main()
