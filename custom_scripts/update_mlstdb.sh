#!/bin/bash
set -eo pipefail

# ==============================================================================
# MLST Database Updater
# ==============================================================================
# Automates monthly update of MLST databases with connection checks, resumable
# checkpoints, version comparison, multi-environment support, and notifications.
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

Optional:
  --update-env NAME           Conda environment for update commands (default: mlstdb)
  --compare-env NAME          Conda environment for compare command (default: mlst-env)
  -h, --help                  Show this help message and exit

Example:
  $(basename "$0") \\
    --input /path/to/mlstdb/curated_schemes/mlst_schemes_curated_v20261015.tab \\
    --old-ver 20261015 \\
    --new-ver 20261201 \\
    --db-dir /path/to/mlstdb \\
    --latest-link /path/to/mlst/latest \\
    --update-env mlstdb \\
    --compare-env mlst-env
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

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) usage ;;
        -i|--input) INPUT_FILE="$2"; shift 2 ;;
        -o|--old-ver) OLD_VER="$2"; shift 2 ;;
        -n|--new-ver) NEW_VER="$2"; shift 2 ;;
        -d|--db-dir) DB_DIR="$2"; shift 2 ;;
        -l|--latest-link) LATEST_SYMLINK="$2"; shift 2 ;;
        --update-env) UPDATE_ENV="$2"; shift 2 ;;
        --compare-env) COMPARE_ENV="$2"; shift 2 ;;
        *) 
            echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] 🚨 Unknown parameter passed: $1"
            usage 
            ;;
    esac
done

# --- LOGGING UTILITY FUNCTIONS ---
log_info() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1"
}

log_step() {
    echo ""
    echo "================================================================================"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [STEP $1] $2"
    echo "================================================================================"
}

log_substep() {
    echo "$(date '+%Y-%m-%d %H:%M:%S')  --> $1"
}

log_success() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SUCCESS] ✅ $1"
}

log_warn() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [WARN] ⚠️ $1"
}

log_skip() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SKIP] ⏭️ $1"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] 🚨 $1" >&2
}

CURRENT_STEP="Initialization"
FAILED_LINE=""
LAST_ERROR_MSG=""

# Fatal exit helper: sets error context and exits with 1
die() {
    FAILED_LINE="${BASH_LINENO[0]}"
    LAST_ERROR_MSG="$1"
    log_error "$1"
    exit 1
}

# --- NOTIFICATION CONFIGURATION ---
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
        
        local clean_reason="${LAST_ERROR_MSG:-Command exited with error}"
        # Escape double quotes and backslashes for Slack JSON payload
        clean_reason=$(echo "$clean_reason" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')
        
        local err_msg="🚨 *MLST DB Update FAILED*${line_info} (Exit Code: ${exit_code}) during '${CURRENT_STEP}' (Version ${NEW_VER:-unknown}) in ${DB_DIR:-unknown}."
        if [ -n "$LAST_ERROR_MSG" ]; then
            err_msg="${err_msg}\n*Reason:* ${clean_reason}"
        fi
        
        log_error "CRITICAL FAILURE: ${err_msg}"
        if [ -n "$SLACK_WEBHOOK" ]; then
            curl -s -X POST -H 'Content-type: application/json' \
                --data "{\"text\":\"${err_msg}\"}" \
                "$SLACK_WEBHOOK" || true
        fi
    fi
}

# Trap EXIT so that BOTH unexpected command failures and manual exit/die calls trigger notifications
trap cleanup_and_notify_error EXIT
trap 'FAILED_LINE=$LINENO' ERR

# --- PRE-FLIGHT VALIDATION ---
log_step "1/7" "Validating configuration and pre-flight parameters..."

if [[ -z "$INPUT_FILE" || -z "$OLD_VER" || -z "$NEW_VER" || -z "$DB_DIR" || -z "$LATEST_SYMLINK" ]]; then
    die "Missing one or more required arguments."
fi

if [[ ! -f "$INPUT_FILE" ]]; then
    die "Input scheme file not found at: $INPUT_FILE"
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

eval "$(conda shell.bash hook)"
log_success "Pre-flight validation completed."

# ==============================================================================
# STEP 2: TEST API CONNECTIONS
# ==============================================================================
CURRENT_STEP="Step 2: API Connection Test"
log_step "2/7" "Testing database connections (PubMLST & Pasteur)..."

if [ ! -f "$CKPT_DIR/step2_connect.done" ]; then
    cd "$DB_DIR"
    log_substep "Activating Conda environment '$UPDATE_ENV'..."
    conda activate "$UPDATE_ENV"
    
    log_substep "Verifying PubMLST API connection..."
    mlstdb connect -d pubmlst --api-key
    
    log_substep "Verifying Pasteur API connection..."
    mlstdb connect -d pasteur
    
    touch "$CKPT_DIR/step2_connect.done"
    log_success "API connections verified successfully."
else
    log_skip "Connections already verified. Checkpoint exists."
fi

# ==============================================================================
# STEP 3: UPDATE DATABASE
# ==============================================================================
CURRENT_STEP="Step 3: Database Download & BLAST DB Generation"
log_step "3/7" "Downloading schemes and building BLAST database (version $NEW_VER)..."

NEW_PUBMLST_DIR="$DB_DIR/db_all_schemes_v${NEW_VER}/pubmlst"
NEW_BLAST_DIR="$DB_DIR/db_all_schemes_v${NEW_VER}/blast"
UPDATE_LOG="$DB_DIR/mlstdb_update_v${NEW_VER}.log"

if [ ! -f "$CKPT_DIR/step3_update.done" ]; then
    cd "$DB_DIR"
    log_substep "Activating Conda environment '$UPDATE_ENV'..."
    conda activate "$UPDATE_ENV"
    
    log_substep "Output directory (schemes): $NEW_PUBMLST_DIR"
    log_substep "Output directory (BLAST)  : $NEW_BLAST_DIR"
    log_substep "Update log file           : $UPDATE_LOG"
    log_substep "Running 'mlstdb update' with 4 threads and --resume..."
    
    mlstdb update -i "$INPUT_FILE" \
        -d "db_all_schemes_v${NEW_VER}/pubmlst" \
        -b "db_all_schemes_v${NEW_VER}/blast" \
        --resume \
        -t 4 -v 2>&1 | tee -a "$UPDATE_LOG"
    
    # Validation
    if [ ! -d "$NEW_PUBMLST_DIR" ]; then
        die "Expected directory $NEW_PUBMLST_DIR was not created by mlstdb update!"
    fi
    
    SCHEME_COUNT=$(find "$NEW_PUBMLST_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)
    log_substep "Downloaded schemes count: $SCHEME_COUNT"
    
    if [ "$SCHEME_COUNT" -eq 0 ]; then
        die "No schemes were downloaded into $NEW_PUBMLST_DIR!"
    fi
    
    touch "$CKPT_DIR/step3_update.done"
    log_success "Database update and BLAST compilation completed."
else
    log_skip "Database update already completed. Checkpoint exists."
fi

# ==============================================================================
# STEP 4: SYNC DATABASE TO TARGET DIRECTORY
# ==============================================================================
CURRENT_STEP="Step 4: Sync to Target Directory"
log_step "4/7" "Syncing database to target directory ($TARGET_DIR)..."

TARGET_VERSION_DIR="$TARGET_DIR/db_all_schemes_v${NEW_VER}"

if [ ! -f "$CKPT_DIR/step4_sync.done" ]; then
    if [ "$TARGET_DIR" != "$DB_DIR" ]; then
        log_substep "Source: $DB_DIR/db_all_schemes_v${NEW_VER}/"
        log_substep "Target: $TARGET_VERSION_DIR/"
        mkdir -p "$TARGET_VERSION_DIR"
        
        rsync -rav --progress "$DB_DIR/db_all_schemes_v${NEW_VER}/" "$TARGET_VERSION_DIR/"
        log_success "Synchronized new version to target directory."
    else
        log_substep "Target directory is identical to DB_DIR ($DB_DIR). No copy needed."
    fi
    touch "$CKPT_DIR/step4_sync.done"
else
    log_skip "Database sync already completed. Checkpoint exists."
fi

# ==============================================================================
# STEP 5: DATABASE INSPECTION & SUMMARY
# ==============================================================================
CURRENT_STEP="Step 5: Database Inspection & Summary"
log_step "5/7" "Inspecting downloaded database and generating summary..."

SUMMARY_FILE="$DB_DIR/db_all_schemes_v${NEW_VER}_summary.txt"

if [ ! -f "$CKPT_DIR/step5_check.done" ]; then
    cd "$NEW_PUBMLST_DIR"
    log_substep "Generating file counts per scheme in $NEW_PUBMLST_DIR..."
    find . -type f | cut -d/ -f2 | sort | uniq -c | sort -nr > "$SUMMARY_FILE"
    
    log_substep "Summary written to: $SUMMARY_FILE"
    log_substep "Preview of top 10 schemes by file count:"
    head -n 10 "$SUMMARY_FILE" | while read -r line; do
        echo "       $line"
    done
    
    touch "$CKPT_DIR/step5_check.done"
    log_success "Database summary generated successfully."
else
    log_skip "Database summary already generated. Checkpoint exists."
fi

# ==============================================================================
# STEP 6: VERSION COMPARISON
# ==============================================================================
CURRENT_STEP="Step 6: Version Comparison"
log_step "6/7" "Comparing database versions ($OLD_VER vs $NEW_VER)..."

if [ ! -f "$CKPT_DIR/step6_compare.done" ]; then
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
    log_substep "Activating Conda environment '$COMPARE_ENV' for comparison..."
    conda activate "$COMPARE_ENV"
    
    COMPARE_OUTDIR="$DB_DIR/mlstdb_compare/v${OLD_VER}_vs_v${NEW_VER}"
    COMPARE_LOG="$DB_DIR/mlstdb_compare_v${OLD_VER}_vs_v${NEW_VER}.log"
    mkdir -p "$COMPARE_OUTDIR"
    
    log_substep "Output directory: $COMPARE_OUTDIR"
    log_substep "Log file        : $COMPARE_LOG"
    log_substep "Running 'mlstdb compare' (full type, parallel mode)..."
    
    cd "$DB_DIR"
    mlstdb compare \
        --old-db "$OLD_DB_PATH" \
        --new-db "db_all_schemes_v${NEW_VER}/pubmlst" \
        --outdir "$COMPARE_OUTDIR" \
        --parallel --type full 2>&1 | tee -a "$COMPARE_LOG"
    
    touch "$CKPT_DIR/step6_compare.done"
    log_success "Version comparison completed successfully."
else
    log_skip "Version comparison already completed. Checkpoint exists."
fi

# ==============================================================================
# STEP 7: FINALIZE SYMLINKS & MIRROR DIRECTORIES
# ==============================================================================
CURRENT_STEP="Step 7: Finalize Symlinks and Local Mirror"
log_step "7/7" "Updating 'latest' symlink and local directory mirrors..."

if [ ! -f "$CKPT_DIR/step7_finalize.done" ]; then
    log_substep "Updating symlink: $LATEST_SYMLINK -> $TARGET_VERSION_DIR"
    ln -sfn "$TARGET_VERSION_DIR" "$LATEST_SYMLINK"
    
    log_substep "Replacing root 'blast' and 'pubmlst' directories in $DB_DIR..."
    cd "$DB_DIR"
    rm -rf blast pubmlst
    rsync -rav "$DB_DIR/db_all_schemes_v${NEW_VER}/" .
    
    touch "$CKPT_DIR/step7_finalize.done"
    log_success "Symlink and root mirrors updated."
else
    log_skip "Finalization already completed. Checkpoint exists."
fi

# ==============================================================================
# CLEANUP & COMPLETION NOTIFICATION
# ==============================================================================
log_step "Done" "Cleaning up checkpoints and finalizing report..."
rm -rf "$CKPT_DIR"
log_substep "Removed checkpoint directory ($CKPT_DIR)."

log_success "All update steps completed successfully!"
log_info "Active database is now: Version $NEW_VER"
log_info "Symlink target         : $(readlink -f "$LATEST_SYMLINK")"

if [ -n "$SLACK_WEBHOOK" ]; then
    curl -s -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"✅ *MLST DB Update SUCCESSFUL*: Version ${NEW_VER} successfully built in ${DB_DIR} and linked to ${LATEST_SYMLINK}.\"}" \
        "$SLACK_WEBHOOK" || true
fi

