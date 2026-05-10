#!/bin/bash
# local_migrate_scattered_project_files_20260510.sh
# Safe migration script for frontier-allocation-for-budgeted-llm-inference

set -e

CANONICAL_DIR="$HOME/frontier-allocation-for-budgeted-llm-inference"
REVIEW_DIR="$CANONICAL_DIR/_migration_review"
ARCHIVE_DIR="$CANONICAL_DIR/archive"
LOG_FILE="$CANONICAL_DIR/migration_20260510.log"

mkdir -p "$REVIEW_DIR/scripts" "$REVIEW_DIR/tests" "$ARCHIVE_DIR"

echo "Starting migration at $(date)" | tee -a "$LOG_FILE"

# Exclude patterns
EXCLUDES=(
    --exclude ".git"
    --exclude "venv"
    --exclude ".venv"
    --exclude "__pycache__"
    --exclude ".pytest_cache"
    --exclude ".ruff_cache"
    --exclude "node_modules"
    --exclude ".env"
    --exclude "*token*"
    --exclude "*credential*"
    --exclude "*key*"
    --exclude "*.log"
)

# Function to safely migrate with rsync
migrate_rsync() {
    local src="$1"
    local dest="$2"
    echo "Migrating $src to $dest..." | tee -a "$LOG_FILE"
    rsync -av --ignore-existing "${EXCLUDES[@]}" "$src/" "$dest/" >> "$LOG_FILE" 2>&1
}

# 1. Migrate unique content from research-next-wt
migrate_rsync "$HOME/research-next-wt/experiments" "$CANONICAL_DIR/experiments"
migrate_rsync "$HOME/research-next-wt/outputs" "$CANONICAL_DIR/outputs"
migrate_rsync "$HOME/research-next-wt/docs" "$CANONICAL_DIR/docs"
migrate_rsync "$HOME/research-next-wt/local_patches" "$CANONICAL_DIR/local_patches"
migrate_rsync "$HOME/research-next-wt/prompts" "$CANONICAL_DIR/prompts"

# 2. Migrate home-level outputs
migrate_rsync "$HOME/outputs" "$CANONICAL_DIR/outputs"

# 3. Migrate home-level scripts and tests to review folder (to avoid overwriting)
echo "Moving home-level scripts and tests to review folder..." | tee -a "$LOG_FILE"
cp -n "$HOME/scripts/"* "$REVIEW_DIR/scripts/" 2>/dev/null || true
cp -n "$HOME/tests/"* "$REVIEW_DIR/tests/" 2>/dev/null || true

# 4. Archive migration artifacts
echo "Archiving migration_artifacts_20260509..." | tee -a "$LOG_FILE"
if [ -d "$HOME/migration_artifacts_20260509" ]; then
    rsync -av "$HOME/migration_artifacts_20260509/" "$ARCHIVE_DIR/migration_artifacts_20260509/" >> "$LOG_FILE" 2>&1
fi

echo "Migration completed at $(date)" | tee -a "$LOG_FILE"
echo "Please review conflicts in $REVIEW_DIR"
