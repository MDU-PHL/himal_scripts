#!/bin/bash
set -eo pipefail

# ==============================================================================
# MLST Database Updater (First-Principles Engine)
# ==============================================================================
# Features:
#   - Nextflow-style -resume / --resume
#   - Fine-grained step skipping (--skip slack,compare,sync,...)
#   - Exact command transparency ([CMD] $ ...) with elapsed execution timing
#   - Robust EXIT/ERR trapping reporting exact failure line & root reason
#   - Multi-environment Conda orchestration (update-env vs compare-env)
#   - Atomic symlink replacement & root mirror syncing
# ==============================================================================

usage() {
    cat <<EOF
================================================================================
MLST Database Updater
================================================================================
Usage: $(basename "$0") [OPTIONS]

Required Options:
  -i, --input FILE            Path to the input curated schemes .tab file
  -o, --old-ver DATE          Old version date string (e.g., 20261015)
  -n, --new-ver DATE          New version date string (e.g., 20261201)
  -d, --db-dir DIR            Full path to the MLST database build directory
  -l, --latest-link PATH      Full path for the 'latest' symlink

Execution Control Options:
  -r, --resume, -resume       Nextflow-style resume (skip previously completed steps)
  -s, --skip STEPS            Comma-separated list of steps to skip
                              Available: connect, update, sync, check, compare, finalize, slack
  -n, --dry-run               Print exact commands without executing them
  --update-env NAME           Conda environment for update commands (default: mlstdb)
  --compare-env NAME          Conda environment for compare command (default: mlst-env)
  -h, --help                  Show this help message and exit

Examples:
  # Standard full run:
  $(basename "$0") \\
    --input curated_schemes/mlst_schemes_curated_v20261015.tab \\
    --old-ver 20261015 --new-ver 20261201 \\
    --db-dir /path/to/mlstdb --latest-link /path/to/mlst/latest

  # Resume an interrupted run:
  $(basename "$0") -resume \\
    --input curated_schemes/mlst_schemes_curated_v20261015.tab \\
    --old-ver 20261015 --new-ver 20261201 \\
    --db-dir /path/to/mlstdb --latest-link /path/to/mlst/latest

  # Skip comparison and Slack notification:
  $(basename "$0") --skip compare,slack \\
    --input curated_schemes/mlst_schemes_curated_v20261015.tab \\
    --old-ver 20261015 --new-ver 20261201 \\
    --db-dir /path/to/mlstdb --latest-link /path/to/mlst/latest
================================================================================
EOF
    exit 0
}

# --- CLI ARGUMENT DEFAULTS ---
INPUT_FILE=""
OLD_VER=""
NEW_VER=""
DB_DIR=""
LATEST_SYMLINK=""
UPDATE_ENV="${UPDATE_ENV:-mlstdb}"
COMPARE_ENV="${COMPARE_ENV:-mlst-env}"
RESUME=false
DRY_RUN=false
SKIP_STEPS=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) usage ;;
        -i|--input) INPUT_FILE="$2"; shift 2 ;;
        -o|--old-ver) OLD_VER="$2"; shift 2 ;;
        -n|--new-ver) NEW_VER="$2"; shift 2 ;;
        -d|--db-dir) DB_DIR="$2"; shift 2 ;;
        -l|--latest-link) LATEST_SYMLINK="$2"; shift 2 ;;
        -r|--resume|-resume) RESUME=true; shift ;;
        -s|--skip) SKIP_STEPS="$2"; shift 2 ;;
        -n|--dry-run) DRY_RUN=true; shift ;;
        --update-env) UPDATE_ENV="$2"; shift 2 ;;
        --compare-env) COMPARE_ENV="$2"; shift 2 ;;
        *) 
            echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] 🚨 Unknown parameter passed: $1"
            usage 
            ;;
    esac
done

# --- LOGGING & STEP UTILITIES ---
log_info() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1"
}

log_step_header() {
    echo ""
    echo "================================================================================"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [STEP $1] $2"
    echo "================================================================================"
}

log_substep() {
    echo "$(date '+%Y-%m-%d %H:%M:%S')  --> $1"
}

log_cmd() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S')  \033[1;34m[CMD]\033[0m \$ $1"
}

log_success() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') \033[1;32m[SUCCESS] ✅\033[0m $1"
}

log_warn() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') \033[1;33m[WARN] ⚠️\033[0m $1"
}

log_skip() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') \033[1;35m[SKIP] ⏭️\033[0m $1"
}

log_cached() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') \033[1;36m[CACHED] ⚡\033[0m $1"
}

log_error() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') \033[1;31m[ERROR] 🚨\033[0m $1" >&2
}

CURRENT_STEP="Initialization"
FAILED_LINE=""
LAST_ERROR_MSG=""

die() {
    FAILED_LINE="${BASH_LINENO[0]}"
    LAST_ERROR_MSG="$1"
    log_error "$1"
    exit 1
}

# --- STEP SKIPPING CHECKER ---
should_skip() {
    local step_name="$1"
    [[ ",${SKIP_STEPS}," =~ ,${step_name}, ]]
}

# --- COMMAND EXECUTION RUNNER WITH VISIBILITY & TIMING ---
execute_command() {
    local cmd="$1"
    log_cmd "$cmd"
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "(Dry Run mode enabled — command skipped)"
        return 0
    fi
    
    local start_ts=$(date +%s)
    eval "$cmd"
    local elapsed=$(( $(date +%s) - start_ts ))
    log_substep "Execution completed in ${elapsed}s."
}

# --- CONDA ACTIVATION HELPER ---
activate_conda() {
    local env="$1"
    log_substep "Activating Conda environment '$env'..."
    if [ "$DRY_RUN" = true ]; then
        return 0
    fi
    if command -v conda &>/dev/null; then
        conda activate "$env"
    else
        log_warn "Conda binary not found on PATH; continuing without conda activation."
    fi
}

# --- NOTIFICATION & EXIT TRAP ---
WEBHOOK_FILE="$HOME/.config/slack_webhook/himal_notifier.txt"
SLACK_WEBHOOK=""

if [ -f "$WEBHOOK_FILE" ]; then
    SLACK_WEBHOOK=$(tr -d '\n' < "$WEBHOOK_FILE")
fi

cleanup_and_notify_error() {
    local exit_code=$?
    if [ "$exit_code" -ne 0 ]; then
        local line_info=""
        if [ -n "$FAILED_LINE" ]; then
            line_info=" at line ${FAILED_LINE}"
        fi
        
        local clean_reason="${LAST_ERROR_MSG:-Command exited with non-zero exit code}"
        clean_reason=$(echo "$clean_reason" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')
        
        local err_msg="🚨 *MLST DB Update FAILED*${line_info} (Exit Code: ${exit_code}) during '${CURRENT_STEP}' (Version ${NEW_VER:-unknown}) in ${DB_DIR:-unknown}."
        if [ -n "$LAST_ERROR_MSG" ]; then
            err_msg="${err_msg}\n*Reason:* ${clean_reason}"
        fi
        
        log_error "CRITICAL FAILURE: ${err_msg}"
        
        # Only notify via Slack if not explicitly skipped by user
        if [ -n "$SLACK_WEBHOOK" ] && ! should_skip "slack"; then
            curl -s -X POST -H 'Content-type: application/json' \
                --data "{\"text\":\"${err_msg}\"}" \
                "$SLACK_WEBHOOK" || true
        fi
    fi
}
trap cleanup_and_notify_error EXIT
trap 'FAILED_LINE=$LINENO' ERR

# ==============================================================================
# STEP 1: PRE-FLIGHT VALIDATION
# ==============================================================================
CURRENT_STEP="Step 1: Pre-flight Validation"
log_step_header "1/7" "Validating configuration and environment..."

if [[ -z "$INPUT_FILE" || -z "$OLD_VER" || -z "$NEW_VER" || -z "$DB_DIR" || -z "$LATEST_SYMLINK" ]]; then
    die "Missing one or more required arguments. Run with --help for usage."
fi

if [[ ! -f "$INPUT_FILE" ]]; then
    die "Input curated scheme file not found: $INPUT_FILE"
fi

TARGET_DIR="$(dirname "$LATEST_SYMLINK")"
mkdir -p "$DB_DIR"
mkdir -p "$TARGET_DIR"

log_substep "Input Schemes : $INPUT_FILE"
log_substep "Old Version   : $OLD_VER"
log_substep "New Version   : $NEW_VER"
log_substep "Build DB Dir  : $DB_DIR"
log_substep "Target Dir    : $TARGET_DIR"
log_substep "Latest Symlink: $LATEST_SYMLINK"
log_substep "Resume Mode   : $RESUME"
log_substep "Dry Run Mode  : $DRY_RUN"
[ -n "$SKIP_STEPS" ] && log_substep "Skip Steps    : $SKIP_STEPS"
log_substep "Update Env    : $UPDATE_ENV"
log_substep "Compare Env   : $COMPARE_ENV"

if [ -n "$SLACK_WEBHOOK" ]; then
    log_substep "Slack Webhook : Configured ($WEBHOOK_FILE)"
else
    log_warn "Webhook file not found at $WEBHOOK_FILE. Slack alerts disabled."
fi

CKPT_DIR="${DB_DIR}/.checkpoints_v${NEW_VER}"
mkdir -p "$CKPT_DIR"
log_substep "Checkpoints   : $CKPT_DIR"

if command -v conda &>/dev/null; then
    eval "$(conda shell.bash hook)"
fi

log_success "Pre-flight validation passed."

# ==============================================================================
# STEP 2: TEST API CONNECTIONS
# ==============================================================================
CURRENT_STEP="Step 2: API Connection Test"
log_step_header "2/7" "Verifying API connectivity (PubMLST & Pasteur)..."

if should_skip "connect"; then
    log_skip "Step explicitly skipped via --skip connect."
elif [ "$RESUME" = true ] && [ -f "$CKPT_DIR/step2_connect.done" ]; then
    log_cached "Connections already verified. Checkpoint cached (Nextflow-style resume)."
else
    cd "$DB_DIR"
    activate_conda "$UPDATE_ENV"
    
    execute_command "mlstdb connect -d pubmlst --api-key"
    execute_command "mlstdb connect -d pasteur"
    
    [ "$DRY_RUN" = false ] && touch "$CKPT_DIR/step2_connect.done"
    log_success "API connections verified successfully."
fi

# ==============================================================================
# STEP 3: UPDATE DATABASE
# ==============================================================================
CURRENT_STEP="Step 3: Database Download & BLAST DB Generation"
log_step_header "3/7" "Downloading schemes and building BLAST database (version $NEW_VER)..."

NEW_PUBMLST_DIR="$DB_DIR/db_all_schemes_v${NEW_VER}/pubmlst"
NEW_BLAST_DIR="$DB_DIR/db_all_schemes_v${NEW_VER}/blast"
UPDATE_LOG="$DB_DIR/mlstdb_update_v${NEW_VER}.log"

if should_skip "update"; then
    log_skip "Step explicitly skipped via --skip update."
elif [ "$RESUME" = true ] && [ -f "$CKPT_DIR/step3_update.done" ]; then
    log_cached "Database update already completed. Checkpoint cached (Nextflow-style resume)."
else
    cd "$DB_DIR"
    activate_conda "$UPDATE_ENV"
    
    CMD="mlstdb update -i \"$INPUT_FILE\" -d \"db_all_schemes_v${NEW_VER}/pubmlst\" -b \"db_all_schemes_v${NEW_VER}/blast\" --resume -t 4 -v 2>&1 | tee -a \"$UPDATE_LOG\""
    execute_command "$CMD"
    
    if [ "$DRY_RUN" = false ]; then
        if [ ! -d "$NEW_PUBMLST_DIR" ]; then
            die "Expected directory '$NEW_PUBMLST_DIR' was not created by update!"
        fi
        
        SCHEME_COUNT=$(find "$NEW_PUBMLST_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)
        log_substep "Downloaded schemes count: $SCHEME_COUNT"
        
        if [ "$SCHEME_COUNT" -eq 0 ]; then
            die "No schemes were downloaded into '$NEW_PUBMLST_DIR'!"
        fi
        touch "$CKPT_DIR/step3_update.done"
    fi
    log_success "Database update and BLAST compilation completed."
fi

# ==============================================================================
# STEP 4: SYNC DATABASE TO TARGET DIRECTORY
# ==============================================================================
CURRENT_STEP="Step 4: Sync to Target Directory"
log_step_header "4/7" "Syncing database to target directory ($TARGET_DIR)..."

TARGET_VERSION_DIR="$TARGET_DIR/db_all_schemes_v${NEW_VER}"

if should_skip "sync"; then
    log_skip "Step explicitly skipped via --skip sync."
elif [ "$RESUME" = true ] && [ -f "$CKPT_DIR/step4_sync.done" ]; then
    log_cached "Database sync already completed. Checkpoint cached (Nextflow-style resume)."
else
    if [ "$TARGET_DIR" != "$DB_DIR" ]; then
        mkdir -p "$TARGET_VERSION_DIR"
        CMD="rsync -rav --progress \"$DB_DIR/db_all_schemes_v${NEW_VER}/\" \"$TARGET_VERSION_DIR/\""
        execute_command "$CMD"
        log_success "Synchronized new version to target directory."
    else
        log_substep "Target directory is identical to DB_DIR ($DB_DIR). No copy needed."
    fi
    [ "$DRY_RUN" = false ] && touch "$CKPT_DIR/step4_sync.done"
fi

# ==============================================================================
# STEP 5: DATABASE INSPECTION & SUMMARY
# ==============================================================================
CURRENT_STEP="Step 5: Database Inspection & Summary"
log_step_header "5/7" "Inspecting downloaded database and generating summary..."

SUMMARY_FILE="$DB_DIR/db_all_schemes_v${NEW_VER}_summary.txt"

if should_skip "check"; then
    log_skip "Step explicitly skipped via --skip check."
elif [ "$RESUME" = true ] && [ -f "$CKPT_DIR/step5_check.done" ]; then
    log_cached "Database summary already completed. Checkpoint cached (Nextflow-style resume)."
else
    cd "$NEW_PUBMLST_DIR" 2>/dev/null || cd "$DB_DIR"
    CMD="find . -type f | cut -d/ -f2 | sort | uniq -c | sort -nr > \"$SUMMARY_FILE\""
    execute_command "$CMD"
    
    if [ "$DRY_RUN" = false ]; then
        log_substep "Summary written to: $SUMMARY_FILE"
        log_substep "Preview of top 10 schemes by file count:"
        head -n 10 "$SUMMARY_FILE" | while read -r line; do
            echo "       $line"
        done
        touch "$CKPT_DIR/step5_check.done"
    fi
    log_success "Database summary generated successfully."
fi

# ==============================================================================
# STEP 6: VERSION COMPARISON
# ==============================================================================
CURRENT_STEP="Step 6: Version Comparison"
log_step_header "6/7" "Comparing database versions ($OLD_VER vs $NEW_VER)..."

if should_skip "compare"; then
    log_skip "Step explicitly skipped via --skip compare."
elif [ "$RESUME" = true ] && [ -f "$CKPT_DIR/step6_compare.done" ]; then
    log_cached "Version comparison already completed. Checkpoint cached (Nextflow-style resume)."
else
    log_substep "Locating previous version ($OLD_VER) database..."
    
    OLD_DB_PATH=""
    if [ -d "$DB_DIR/db_all_schemes_v${OLD_VER}/pubmlst" ]; then
        OLD_DB_PATH="$DB_DIR/db_all_schemes_v${OLD_VER}/pubmlst"
    elif [ -d "$TARGET_DIR/db_all_schemes_v${OLD_VER}/pubmlst" ]; then
        OLD_DB_PATH="$TARGET_DIR/db_all_schemes_v${OLD_VER}/pubmlst"
    fi
    
    if [ -z "$OLD_DB_PATH" ]; then
        die "Old database directory for version '$OLD_VER' was not found in either '$DB_DIR' or '$TARGET_DIR'. Cannot perform version comparison."
    fi
    
    log_substep "Found old version database at: $OLD_DB_PATH"
    activate_conda "$COMPARE_ENV"
    
    COMPARE_OUTDIR="$DB_DIR/mlstdb_compare/v${OLD_VER}_vs_v${NEW_VER}"
    COMPARE_LOG="$DB_DIR/mlstdb_compare_v${OLD_VER}_vs_v${NEW_VER}.log"
    mkdir -p "$COMPARE_OUTDIR"
    
    cd "$DB_DIR"
    CMD="mlstdb compare --old-db \"$OLD_DB_PATH\" --new-db \"db_all_schemes_v${NEW_VER}/pubmlst\" --outdir \"$COMPARE_OUTDIR\" --parallel --type full 2>&1 | tee -a \"$COMPARE_LOG\""
    execute_command "$CMD"
    
    [ "$DRY_RUN" = false ] && touch "$CKPT_DIR/step6_compare.done"
    log_success "Version comparison completed successfully."
fi

# ==============================================================================
# STEP 7: FINALIZE SYMLINKS & MIRROR DIRECTORIES
# ==============================================================================
CURRENT_STEP="Step 7: Finalize Symlinks and Local Mirror"
log_step_header "7/7" "Updating 'latest' symlink and local directory mirrors..."

if should_skip "finalize"; then
    log_skip "Step explicitly skipped via --skip finalize."
elif [ "$RESUME" = true ] && [ -f "$CKPT_DIR/step7_finalize.done" ]; then
    log_cached "Finalization already completed. Checkpoint cached (Nextflow-style resume)."
else
    CMD_SYMLINK="ln -sfn \"$TARGET_VERSION_DIR\" \"$LATEST_SYMLINK\""
    execute_command "$CMD_SYMLINK"
    
    cd "$DB_DIR"
    CMD_MIRROR="rm -rf blast pubmlst && rsync -rav \"$DB_DIR/db_all_schemes_v${NEW_VER}/\" ."
    execute_command "$CMD_MIRROR"
    
    [ "$DRY_RUN" = false ] && touch "$CKPT_DIR/step7_finalize.done"
    log_success "Symlink and root mirrors updated."
fi

# ==============================================================================
# CLEANUP & COMPLETION NOTIFICATION
# ==============================================================================
log_step_header "Done" "Cleaning up checkpoints and finalizing report..."
[ "$DRY_RUN" = false ] && rm -rf "$CKPT_DIR"
log_substep "Removed checkpoint directory ($CKPT_DIR)."

log_success "All update steps completed successfully!"
log_info "Active database is now: Version $NEW_VER"
log_info "Symlink target         : $(readlink -f "$LATEST_SYMLINK" 2>/dev/null || echo "$TARGET_VERSION_DIR")"

# Step: Slack notification
if should_skip "slack"; then
    log_skip "Slack notification explicitly skipped via --skip slack."
elif [ -n "$SLACK_WEBHOOK" ]; then
    log_substep "Sending success notification to Slack..."
    CMD_SLACK="curl -s -X POST -H 'Content-type: application/json' --data '{\"text\":\"✅ *MLST DB Update SUCCESSFUL*: Version ${NEW_VER} successfully built in ${DB_DIR} and linked to ${LATEST_SYMLINK}.\"}' \"$SLACK_WEBHOOK\""
    execute_command "$CMD_SLACK"
fi
