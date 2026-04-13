"""Restricted Python execution for program-of-thought style reasoning (PAL/PoT-inspired)."""

from __future__ import annotations

import io
import signal
from contextlib import redirect_stderr, redirect_stdout
from typing import Any


class SandboxTimeout(Exception):
    pass


def _timeout_handler(signum: int, frame: object) -> None:  # noqa: ARG001
    raise SandboxTimeout("execution timed out")


def run_restricted_python(
    code: str,
    *,
    timeout_seconds: float = 2.0,
    max_output_chars: int = 8000,
) -> dict[str, Any]:
    """Execute *code* with minimal globals and wall-clock timeout (Unix SIGALRM).

    Returns a dict with stdout/stderr snippets, exception text if any, and ok flag.
    This is intentionally lightweight (not a production sandbox).
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    err: str | None = None
    prev_handler = signal.getsignal(signal.SIGALRM)
    try:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, float(timeout_seconds))

        safe_builtins: dict[str, Any] = {
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "int": int,
            "float": float,
            "round": round,
            "pow": pow,
            "divmod": divmod,
            "sorted": sorted,
            "list": list,
            "tuple": tuple,
            "set": set,
            "dict": dict,
            "str": str,
            "bool": bool,
            "True": True,
            "False": False,
            "None": None,
        }

        def _print(*args: object, **kwargs: object) -> None:
            print(*args, file=stdout_buf, **kwargs)

        safe_builtins["print"] = _print

        g: dict[str, Any] = {"__builtins__": safe_builtins}

        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(compile(code, "<pot>", "exec"), g, None)
    except SandboxTimeout as exc:
        err = str(exc)
    except Exception as exc:  # noqa: BLE001 - sandbox boundary
        err = f"{type(exc).__name__}: {exc}"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, prev_handler)

    out = stdout_buf.getvalue()
    err_s = stderr_buf.getvalue()
    if len(out) > max_output_chars:
        out = out[:max_output_chars] + "\n...[truncated]"
    if len(err_s) > max_output_chars:
        err_s = err_s[:max_output_chars] + "\n...[truncated]"

    return {
        "stdout": out,
        "stderr": err_s,
        "exception": err,
        "ok": err is None and not err_s.strip(),
    }
