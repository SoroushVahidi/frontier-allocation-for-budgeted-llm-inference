#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            dumped = obj.model_dump()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            return {}
    if hasattr(obj, "__dict__"):
        maybe = getattr(obj, "__dict__", {})
        if isinstance(maybe, dict):
            return maybe
    return {}


def main() -> int:
    model = os.getenv("COHERE_MODEL", "command-r-plus-08-2024")
    has_key = bool(os.getenv("COHERE_API_KEY"))
    print(f"COHERE_API_KEY: {'present' if has_key else 'absent'}")
    print(f"model: {model}")
    if not has_key:
        print("status: failure (missing COHERE_API_KEY)")
        return 2

    try:
        import cohere  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print(f"status: failure (cohere sdk import error: {type(exc).__name__})")
        return 3

    try:
        client = cohere.ClientV2(api_key=os.environ["COHERE_API_KEY"])
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=4,
        )
        response_dict = _as_dict(response)
        usage = response_dict.get("usage", {})
        billed_units = usage.get("billed_units", {})
        tokens = usage.get("tokens", {})
        print("status: success")
        print("usage.tokens:", json.dumps(tokens, sort_keys=True))
        print("usage.billed_units:", json.dumps(billed_units, sort_keys=True))
        if "meta" in response_dict:
            print("meta:", json.dumps(response_dict["meta"], sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"status: failure ({type(exc).__name__}: {str(exc)[:240]})")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
