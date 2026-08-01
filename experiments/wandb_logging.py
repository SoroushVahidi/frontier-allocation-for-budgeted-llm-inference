"""Optional Weights & Biases logging for FTA v3 shadow-policy experiments.

Purely additive side-channel: no function here influences any FTA v3
evaluation, gate, or selection logic. wandb is imported lazily, only when
``--wandb`` is passed, so it is never a hard dependency. If wandb is not
installed or ``WANDB_API_KEY`` is absent, callers fall back to a no-op
(``init_run`` returns ``None``) unless ``--wandb-strict`` was requested.

Secrets: ``WANDB_API_KEY`` (or any config/metric key that looks like a
secret) is never forwarded to W&B. See ``sanitize_config``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

FORBIDDEN_CONFIG_KEY_SUBSTRINGS = ("key", "token", "secret", "password", "credential")

MAX_TABLE_ROWS = 5000

SCENARIO_LABELS = {
    "cohere_math500": "MATH-500",
    "cohere_gsm8k": "GSM8K",
    "aggregate720": "Aggregate-720",
}

STANDARD_TABLE_FILES = (
    "v3_policy_summary.csv",
    "v3_cross_scenario_summary.csv",
    "v3_fold_metrics.csv",
    "v3_recovery_regression_cases.csv",
)
OPTIONAL_LARGE_TABLE_FILES = ("v3_per_example_decisions.csv",)

_SCENARIO_VARIANT_METRIC_MAP = {
    "trigger_count": "triggers",
    "recoveries": "recoveries",
    "regressions": "regressions",
    "neutral_overrides": "neutral_overrides",
    "net_gain": "net_gain",
    "override_precision": "override_precision",
    "estimated_accuracy_delta": "estimated_accuracy_delta",
}

_FOLD_METRIC_MAP = {
    "trigger_count": "triggers",
    "recoveries": "recoveries",
    "regressions": "regressions",
    "net_gain": "net_gain",
    "override_precision": "override_precision",
}


def contains_forbidden_substring(name: str) -> bool:
    lowered = str(name).lower()
    return any(bad in lowered for bad in FORBIDDEN_CONFIG_KEY_SUBSTRINGS)


def sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Drop secret-like keys and any value equal to the live WANDB_API_KEY."""
    api_key = os.environ.get("WANDB_API_KEY")
    clean: dict[str, Any] = {}
    for k, v in config.items():
        if contains_forbidden_substring(str(k)):
            continue
        if api_key and isinstance(v, str) and v == api_key:
            continue
        clean[k] = v
    return clean


def package_available() -> bool:
    try:
        import wandb  # noqa: F401
    except ImportError:
        return False
    return True


def git_commit_hash(repo_root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def flatten_metrics(data: dict[str, Any], *, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict into slash-separated numeric/bool leaves only."""
    flat: dict[str, Any] = {}
    for k, v in data.items():
        key = f"{prefix}/{k}" if prefix else str(k)
        if isinstance(v, dict):
            flat.update(flatten_metrics(v, prefix=key))
        elif isinstance(v, (bool, int, float)):
            flat[key] = v
        else:
            continue
    return flat


def scenario_label(scenario_id: str) -> str:
    return SCENARIO_LABELS.get(scenario_id, scenario_id)


def _variant_label_map(variant_order: Sequence[str]) -> dict[str, str]:
    return {v: f"V{i}" for i, v in enumerate(variant_order)}


def build_scenario_variant_metrics(
    summaries: list[dict[str, Any]],
    *,
    variant_order: Sequence[str],
) -> dict[str, Any]:
    """Build ``scenario/{Scenario}/{Vn}/{metric}`` keys from per-variant summaries."""
    label_by_variant = _variant_label_map(variant_order)
    metrics: dict[str, Any] = {}
    for s in summaries:
        scen = scenario_label(str(s.get("scenario_id", "")))
        variant_id = str(s.get("variant", ""))
        var = label_by_variant.get(variant_id, variant_id)
        for src_key, metric_name in _SCENARIO_VARIANT_METRIC_MAP.items():
            val = s.get(src_key)
            if isinstance(val, (bool, int, float)):
                metrics[f"scenario/{scen}/{var}/{metric_name}"] = val
    return metrics


def build_fold_metrics(
    fold_rows: list[dict[str, Any]],
    *,
    variant_order: Sequence[str],
    scenario_label_for_folds: str = "MATH-500",
) -> dict[str, Any]:
    label_by_variant = _variant_label_map(variant_order)
    metrics: dict[str, Any] = {}
    for row in fold_rows:
        variant_id = str(row.get("variant", ""))
        var = label_by_variant.get(variant_id, variant_id)
        fold = row.get("fold")
        for src_key, metric_name in _FOLD_METRIC_MAP.items():
            val = row.get(src_key)
            if isinstance(val, (bool, int, float)):
                metrics[f"scenario/{scenario_label_for_folds}/{var}/fold{fold}/{metric_name}"] = val
    return metrics


def build_aggregate_metrics(
    summaries: list[dict[str, Any]],
    *,
    variant_order: Sequence[str],
) -> dict[str, Any]:
    """Sum recoveries/regressions/net_gain/triggers across scenarios, per variant."""
    label_by_variant = _variant_label_map(variant_order)
    by_variant: dict[str, dict[str, float]] = {}
    for s in summaries:
        variant_id = str(s.get("variant", ""))
        var = label_by_variant.get(variant_id, variant_id)
        agg = by_variant.setdefault(
            var, {"recoveries": 0, "regressions": 0, "net_gain": 0, "trigger_count": 0}
        )
        for k in ("recoveries", "regressions", "net_gain", "trigger_count"):
            val = s.get(k)
            if isinstance(val, (bool, int, float)):
                agg[k] += val
    metrics: dict[str, Any] = {}
    for var, agg in by_variant.items():
        metrics[f"aggregate/{var}/recoveries"] = agg["recoveries"]
        metrics[f"aggregate/{var}/regressions"] = agg["regressions"]
        metrics[f"aggregate/{var}/net_gain"] = agg["net_gain"]
        metrics[f"aggregate/{var}/triggers"] = agg["trigger_count"]
    return metrics


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        columns = list(reader.fieldnames or [])
    return rows, columns


def collect_output_files(out_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.csv", "*.json", "*.md"):
        files.extend(sorted(out_dir.glob(pattern)))
    return files


def sanitize_artifact_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.\-]", "-", name) or "fta-v3-shadow-eval"


@dataclass
class WandbCliOptions:
    enabled: bool
    project: str
    entity: str | None
    run_name: str | None
    tags: tuple[str, ...]
    mode: str
    log_tables: bool
    log_artifacts: bool
    strict: bool


def add_wandb_cli_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("wandb (optional)")
    group.add_argument(
        "--wandb", action="store_true", help="Enable optional Weights & Biases logging."
    )
    group.add_argument(
        "--wandb-project",
        default=os.environ.get("WANDB_PROJECT", "frontier-allocation"),
        help="W&B project name (default: $WANDB_PROJECT or 'frontier-allocation').",
    )
    group.add_argument(
        "--wandb-entity",
        default=os.environ.get("WANDB_ENTITY"),
        help="W&B entity (default: $WANDB_ENTITY).",
    )
    group.add_argument("--wandb-run-name", default=None, help="Optional W&B run name.")
    group.add_argument(
        "--wandb-tags", default=None, help="Comma-separated W&B tags, e.g. 'fta-v3,shadow'."
    )
    group.add_argument(
        "--wandb-mode",
        choices=["online", "offline", "disabled"],
        default=None,
        help="W&B mode (default: 'online' when --wandb is used).",
    )
    group.add_argument(
        "--wandb-log-tables",
        dest="wandb_log_tables",
        action="store_true",
        default=True,
        help="Log CSV report tables to W&B (default: on).",
    )
    group.add_argument(
        "--no-wandb-log-tables", dest="wandb_log_tables", action="store_false"
    )
    group.add_argument(
        "--wandb-log-artifacts",
        dest="wandb_log_artifacts",
        action="store_true",
        default=True,
        help="Upload output-dir files as a W&B artifact (default: on).",
    )
    group.add_argument(
        "--no-wandb-log-artifacts", dest="wandb_log_artifacts", action="store_false"
    )
    group.add_argument(
        "--wandb-strict",
        action="store_true",
        help="Fail (raise) instead of warning if W&B cannot be initialized.",
    )


def wandb_options_from_args(args: argparse.Namespace) -> WandbCliOptions:
    tags = tuple(t.strip() for t in (getattr(args, "wandb_tags", None) or "").split(",") if t.strip())
    return WandbCliOptions(
        enabled=bool(getattr(args, "wandb", False)),
        project=getattr(args, "wandb_project", "frontier-allocation"),
        entity=getattr(args, "wandb_entity", None),
        run_name=getattr(args, "wandb_run_name", None),
        tags=tags,
        mode=getattr(args, "wandb_mode", None) or "online",
        log_tables=getattr(args, "wandb_log_tables", True),
        log_artifacts=getattr(args, "wandb_log_artifacts", True),
        strict=bool(getattr(args, "wandb_strict", False)),
    )


class WandbRunHandle:
    """Thin wrapper around a live wandb run. Never holds or forwards secrets."""

    def __init__(
        self,
        *,
        run: Any,
        wandb_module: Any,
        log_tables: bool,
        log_artifacts: bool,
        run_name: str | None,
    ) -> None:
        self._run = run
        self._wandb = wandb_module
        self.log_tables_enabled = log_tables
        self.log_artifacts_enabled = log_artifacts
        self._run_name = run_name

    @property
    def url(self) -> str | None:
        return getattr(self._run, "url", None)

    @property
    def run(self) -> Any:
        """Backward-compatible alias for the underlying wandb run object (prefer `.url`)."""
        return self._run

    def update_config(self, config: dict[str, Any]) -> None:
        self._run.config.update(sanitize_config(config), allow_val_change=True)

    def log_metrics(self, metrics: dict[str, Any]) -> None:
        clean = sanitize_config(metrics)
        if clean:
            self._run.log(clean)

    def log_scenario_variant_metrics(
        self,
        *,
        summaries: list[dict[str, Any]],
        fold_rows: list[dict[str, Any]] | None,
        variant_order: Sequence[str],
    ) -> None:
        metrics = build_scenario_variant_metrics(summaries, variant_order=variant_order)
        if fold_rows:
            metrics.update(build_fold_metrics(fold_rows, variant_order=variant_order))
        metrics.update(build_aggregate_metrics(summaries, variant_order=variant_order))
        self.log_metrics(metrics)

    def _log_csv_table(self, path: Path, *, table_key: str, cap_rows: int | None = None) -> None:
        rows, columns = read_csv_rows(path)
        safe_columns = [c for c in columns if not contains_forbidden_substring(c)]
        if cap_rows is not None and len(rows) > cap_rows:
            print(f"[wandb] Capping table '{table_key}' at {cap_rows} rows (had {len(rows)}).")
            rows = rows[:cap_rows]
        api_key = os.environ.get("WANDB_API_KEY")
        data = []
        for r in rows:
            row_vals = []
            for c in safe_columns:
                v = r.get(c, "")
                if api_key and v == api_key:
                    v = "[REDACTED]"
                row_vals.append(v)
            data.append(row_vals)
        table = self._wandb.Table(columns=safe_columns, data=data)
        self._run.log({table_key: table})

    def log_standard_tables(self, out_dir: Path) -> None:
        if not self.log_tables_enabled:
            return
        for filename in STANDARD_TABLE_FILES:
            path = out_dir / filename
            if path.exists() and path.stat().st_size > 0:
                self._log_csv_table(path, table_key=path.stem)
        for filename in OPTIONAL_LARGE_TABLE_FILES:
            path = out_dir / filename
            if path.exists() and path.stat().st_size > 0:
                self._log_csv_table(path, table_key=path.stem, cap_rows=MAX_TABLE_ROWS)

    def log_all_csv_tables(self, out_dir: Path) -> None:
        if not self.log_tables_enabled:
            return
        for path in sorted(out_dir.glob("*.csv")):
            if path.stat().st_size > 0:
                self._log_csv_table(path, table_key=path.stem, cap_rows=MAX_TABLE_ROWS)

    def log_output_artifact(
        self, out_dir: Path, *, artifact_type: str, name: str | None = None
    ) -> None:
        if not self.log_artifacts_enabled:
            return
        artifact_name = sanitize_artifact_name(name or self._run_name or out_dir.name)
        artifact = self._wandb.Artifact(name=artifact_name, type=artifact_type)
        for f in collect_output_files(out_dir):
            artifact.add_file(str(f))
        self._run.log_artifact(artifact)

    def finish(self) -> None:
        self._run.finish()


def init_run(
    options: WandbCliOptions,
    *,
    script_name: str,
    repo_root: Path,
    extra_config: dict[str, Any] | None = None,
) -> WandbRunHandle | None:
    """Initialize a W&B run, or return None (or raise if strict) if unavailable."""
    if not options.enabled:
        return None

    if not os.environ.get("WANDB_API_KEY"):
        msg = "WANDB_API_KEY is not set in the environment"
        if options.strict:
            raise RuntimeError(f"{msg}; failing due to --wandb-strict.")
        print(f"[wandb] WARNING: {msg}; skipping W&B logging.")
        return None

    try:
        import wandb
    except ImportError as exc:
        msg = f"wandb is not installed ({exc})"
        if options.strict:
            raise RuntimeError(f"{msg}; failing due to --wandb-strict.") from exc
        print(f"[wandb] WARNING: {msg}; skipping W&B logging.")
        return None

    base_config: dict[str, Any] = {
        "script": script_name,
        "git_commit": git_commit_hash(repo_root),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "no_policy_promoted": True,
        "canonical_fta_unchanged": True,
        "no_paid_llm_api_calls": True,
    }
    if extra_config:
        base_config.update(extra_config)

    try:
        run = wandb.init(
            project=options.project,
            entity=options.entity,
            name=options.run_name,
            tags=list(options.tags) or None,
            mode=options.mode,
            config=sanitize_config(base_config),
        )
    except Exception as exc:  # wandb raises assorted auth/network error types
        msg = f"wandb.init() failed ({exc})"
        if options.strict:
            raise RuntimeError(f"{msg}; failing due to --wandb-strict.") from exc
        print(f"[wandb] WARNING: {msg}; continuing without W&B logging.")
        return None

    return WandbRunHandle(
        run=run,
        wandb_module=wandb,
        log_tables=options.log_tables,
        log_artifacts=options.log_artifacts,
        run_name=options.run_name,
    )


def log_fta_v3_shadow_summary(
    run: WandbRunHandle,
    out_dir: Path,
    *,
    variant_order: Sequence[str],
) -> None:
    """Log config, metrics, tables, and artifact for a completed shadow-policy eval run."""
    summary_json = out_dir / "v3_policy_summary.json"
    payload: dict[str, Any] = {}
    if summary_json.exists():
        payload = json.loads(summary_json.read_text(encoding="utf-8"))

    summaries = payload.get("summaries", [])
    fold_rows = payload.get("fold_metrics", [])

    run.update_config(
        {
            "input_paths": payload.get("inputs", {}),
            "output_path": str(out_dir),
            "scenario_names": sorted({str(s.get("scenario_id", "")) for s in summaries}),
            "policy_variants_evaluated": sorted({str(s.get("variant", "")) for s in summaries}),
            "missing_inputs": payload.get("missing", []),
        }
    )
    run.log_scenario_variant_metrics(
        summaries=summaries, fold_rows=fold_rows, variant_order=variant_order
    )
    run.log_standard_tables(out_dir)
    run.log_output_artifact(out_dir, artifact_type="fta-v3-shadow-eval")


def log_generic_output_dir(
    run: WandbRunHandle,
    out_dir: Path,
    *,
    artifact_type: str,
    config: dict[str, Any] | None = None,
) -> None:
    """Best-effort logging for scripts without a dedicated summary schema.

    Logs config, flattens any top-level *_summary.json numeric fields as
    metrics, logs every CSV as a table, and uploads the output dir artifact.
    """
    if config:
        run.update_config(config)
    for json_path in sorted(out_dir.glob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            run.log_metrics(flatten_metrics(payload, prefix=json_path.stem))
    run.log_all_csv_tables(out_dir)
    run.log_output_artifact(out_dir, artifact_type=artifact_type)


def supplemental_log_safe(
    *,
    run_name: str,
    project: str = "frontier-allocation",
    metrics: dict[str, Any],
    extra_config: dict[str, Any] | None = None,
    tags: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Post-hoc W&B logging that never raises; returns status with run_url when available."""
    result: dict[str, Any] = {
        "attempted": True,
        "succeeded": False,
        "run_url": None,
        "run_name": run_name,
        "error_type": None,
    }
    try:
        opts = WandbCliOptions(
            enabled=True,
            project=project,
            entity=None,
            run_name=run_name,
            tags=tags,
            mode="online",
            log_tables=False,
            log_artifacts=False,
            strict=False,
        )
        handle = init_run(
            opts,
            script_name="supplemental_log_safe",
            repo_root=Path.cwd(),
            extra_config=extra_config,
        )
        if handle is None:
            result["note"] = "WANDB_API_KEY missing or wandb unavailable; continuing without W&B"
            return result
        handle.log_metrics(metrics)
        result["run_url"] = handle.url
        handle.finish()
        result["succeeded"] = True
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["note"] = "W&B supplemental logging failed; local artifacts remain authoritative"
    return result
