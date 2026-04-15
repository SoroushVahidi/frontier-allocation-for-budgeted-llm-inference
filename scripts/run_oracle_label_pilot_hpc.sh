#!/usr/bin/env bash
set -euo pipefail

# HPC wrapper for the first stop-vs-act oracle-label pilot.
# This script orchestrates:
# 1) preflight checks,
# 2) state-manifest generation (optional),
# 3) oracle-label generation hook,
# 4) label validation/report,
# 5) final run summary.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PILOT_CONFIG="configs/stop_vs_act_oracle_label_pilot_v1.json"
SELECTION_CONFIG="configs/stop_vs_act_oracle_pilot_state_selection_v1.json"
OUTPUT_ROOT="outputs/oracle_label_pilot_hpc"
RUN_ID=""
RUN_DIR=""
STATE_MANIFEST_PATH=""
BUILD_STATE_MANIFEST=0
GENERATOR_CMD=""
DRY_RUN=0
SKIP_VALIDATION=0

usage() {
  cat <<USAGE
Usage: scripts/run_oracle_label_pilot_hpc.sh [options]

Options:
  --pilot-config PATH             Pilot config JSON (default: ${PILOT_CONFIG})
  --selection-config PATH         State-selection config JSON (default: ${SELECTION_CONFIG})
  --output-root DIR               Root output directory (default: ${OUTPUT_ROOT})
  --run-id ID                     Explicit run id (default: utc timestamp)
  --state-manifest PATH           Existing pilot_state_manifest.jsonl to consume
  --build-state-manifest          Build state manifest for this run if --state-manifest is not supplied
  --generator-cmd CMD             Heavy generator command to run (required unless --dry-run)
                                  Command runs from repo root with env vars exported:
                                  ORACLE_PILOT_CONFIG, ORACLE_STATE_MANIFEST,
                                  ORACLE_OUTPUT_DIR, ORACLE_LABELS_JSONL,
                                  ORACLE_LABEL_MANIFEST
  --dry-run                       Print/execute preflight + optional manifest build + validator dry-run only
  --skip-validation               Skip output validation step (not recommended)
  -h, --help                      Show this help

Expected generator outputs inside the run output directory:
  - oracle_stop_vs_act_labels.jsonl
  - oracle_label_manifest.json
USAGE
}

log() {
  printf '[%s] %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

abs_path() {
  python3 - <<'PY' "$1"
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pilot-config)
      PILOT_CONFIG="$2"; shift 2 ;;
    --selection-config)
      SELECTION_CONFIG="$2"; shift 2 ;;
    --output-root)
      OUTPUT_ROOT="$2"; shift 2 ;;
    --run-id)
      RUN_ID="$2"; shift 2 ;;
    --state-manifest)
      STATE_MANIFEST_PATH="$2"; shift 2 ;;
    --build-state-manifest)
      BUILD_STATE_MANIFEST=1; shift ;;
    --generator-cmd)
      GENERATOR_CMD="$2"; shift 2 ;;
    --dry-run)
      DRY_RUN=1; shift ;;
    --skip-validation)
      SKIP_VALIDATION=1; shift ;;
    -h|--help)
      usage
      exit 0 ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

cd "$ROOT_DIR"

PILOT_CONFIG="$(abs_path "$PILOT_CONFIG")"
SELECTION_CONFIG="$(abs_path "$SELECTION_CONFIG")"
OUTPUT_ROOT="$(abs_path "$OUTPUT_ROOT")"

[[ -f "$PILOT_CONFIG" ]] || fail "Pilot config not found: $PILOT_CONFIG"
[[ -f "$SELECTION_CONFIG" ]] || fail "Selection config not found: $SELECTION_CONFIG"
[[ -f "scripts/build_oracle_label_pilot_state_manifest.py" ]] || fail "Missing manifest builder script"
[[ -f "scripts/validate_oracle_label_pilot_outputs.py" ]] || fail "Missing validator script"

if [[ -z "$RUN_ID" ]]; then
  RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
fi

RUN_DIR="${OUTPUT_ROOT}/${RUN_ID}"
mkdir -p "$RUN_DIR/logs"

log "Run id: $RUN_ID"
log "Run directory: $RUN_DIR"

cp "$PILOT_CONFIG" "$RUN_DIR/pilot_config.snapshot.json"
cp "$SELECTION_CONFIG" "$RUN_DIR/selection_config.snapshot.json"

PRECHECK_REPORT="$RUN_DIR/preflight_config_validation.json"
python3 scripts/validate_oracle_label_pilot_outputs.py \
  --pilot-config "$PILOT_CONFIG" \
  --dry-run > "$PRECHECK_REPORT"
log "Preflight config validation succeeded -> $PRECHECK_REPORT"

if [[ -n "$STATE_MANIFEST_PATH" && "$BUILD_STATE_MANIFEST" -eq 1 ]]; then
  fail "Use either --state-manifest or --build-state-manifest, not both"
fi

if [[ -n "$STATE_MANIFEST_PATH" ]]; then
  STATE_MANIFEST_PATH="$(abs_path "$STATE_MANIFEST_PATH")"
  [[ -f "$STATE_MANIFEST_PATH" ]] || fail "State manifest not found: $STATE_MANIFEST_PATH"
  log "Using provided state manifest: $STATE_MANIFEST_PATH"
else
  if [[ "$BUILD_STATE_MANIFEST" -eq 1 || -z "$STATE_MANIFEST_PATH" ]]; then
    STATE_OUT_DIR="$RUN_DIR/pilot_state_manifest"
    mkdir -p "$STATE_OUT_DIR"
    log "Building pilot state manifest..."
    python3 scripts/build_oracle_label_pilot_state_manifest.py \
      --selection-config "$SELECTION_CONFIG" \
      --output-dir "$STATE_OUT_DIR" > "$RUN_DIR/logs/state_manifest_build.log" 2>&1
    STATE_MANIFEST_PATH="$STATE_OUT_DIR/pilot_state_manifest.jsonl"
    [[ -f "$STATE_MANIFEST_PATH" ]] || fail "Manifest build finished but manifest file missing: $STATE_MANIFEST_PATH"
    log "Pilot state manifest built -> $STATE_MANIFEST_PATH"
  fi
fi

LABELS_JSONL="$RUN_DIR/oracle_stop_vs_act_labels.jsonl"
LABEL_MANIFEST="$RUN_DIR/oracle_label_manifest.json"
QUALITY_REPORT="$RUN_DIR/oracle_label_quality_report.json"

export ORACLE_PILOT_CONFIG="$PILOT_CONFIG"
export ORACLE_STATE_MANIFEST="$STATE_MANIFEST_PATH"
export ORACLE_OUTPUT_DIR="$RUN_DIR"
export ORACLE_LABELS_JSONL="$LABELS_JSONL"
export ORACLE_LABEL_MANIFEST="$LABEL_MANIFEST"

GENERATION_STATUS="not_run"
VALIDATION_STATUS="not_run"

if [[ "$DRY_RUN" -eq 1 ]]; then
  GENERATION_STATUS="dry_run_skipped"
  log "Dry-run enabled: skipping heavy oracle-label generation"
else
  [[ -n "$GENERATOR_CMD" ]] || fail "--generator-cmd is required unless --dry-run is set"
  log "Starting oracle-label generation hook"
  log "Generator command: $GENERATOR_CMD"

  set +e
  bash -lc "$GENERATOR_CMD" > "$RUN_DIR/logs/generator.log" 2>&1
  GENERATOR_RC=$?
  set -e

  if [[ $GENERATOR_RC -ne 0 ]]; then
    fail "Generator command failed with exit code $GENERATOR_RC (see $RUN_DIR/logs/generator.log)"
  fi

  [[ -f "$LABELS_JSONL" ]] || fail "Generator finished but labels file missing: $LABELS_JSONL"
  [[ -f "$LABEL_MANIFEST" ]] || fail "Generator finished but label manifest missing: $LABEL_MANIFEST"
  GENERATION_STATUS="completed"
  log "Generator completed and expected output files exist"
fi

if [[ "$SKIP_VALIDATION" -eq 1 ]]; then
  VALIDATION_STATUS="skipped_by_flag"
  log "Validation explicitly skipped"
else
  if [[ "$DRY_RUN" -eq 1 ]]; then
    VALIDATION_STATUS="dry_run_config_only"
    log "Dry-run: validation already completed in config-only mode"
  else
    log "Running oracle-label output validation"
    set +e
    python3 scripts/validate_oracle_label_pilot_outputs.py \
      --pilot-config "$PILOT_CONFIG" \
      --labels-jsonl "$LABELS_JSONL" \
      --manifest-json "$LABEL_MANIFEST" \
      --quality-report-out "$QUALITY_REPORT" \
      > "$RUN_DIR/logs/validator.log" 2>&1
    VALIDATOR_RC=$?
    set -e

    if [[ $VALIDATOR_RC -ne 0 ]]; then
      fail "Validation failed with exit code $VALIDATOR_RC (see $RUN_DIR/logs/validator.log)"
    fi
    [[ -f "$QUALITY_REPORT" ]] || fail "Validator succeeded but quality report missing: $QUALITY_REPORT"
    VALIDATION_STATUS="completed_all_gates_pass"
    log "Validation succeeded and all quality gates passed"
  fi
fi

SUMMARY_JSON="$RUN_DIR/run_summary.json"
cat > "$SUMMARY_JSON" <<JSON
{
  "run_id": "${RUN_ID}",
  "run_dir": "${RUN_DIR}",
  "pilot_config": "${PILOT_CONFIG}",
  "selection_config": "${SELECTION_CONFIG}",
  "state_manifest": "${STATE_MANIFEST_PATH}",
  "dry_run": ${DRY_RUN},
  "generation_status": "${GENERATION_STATUS}",
  "validation_status": "${VALIDATION_STATUS}",
  "labels_jsonl": "${LABELS_JSONL}",
  "label_manifest": "${LABEL_MANIFEST}",
  "quality_report": "${QUALITY_REPORT}",
  "generator_cmd": $(python3 - <<'PY' "$GENERATOR_CMD"
import json,sys
print(json.dumps(sys.argv[1]))
PY
)
}
JSON

log "Run summary written -> $SUMMARY_JSON"
log "Pipeline completed"
