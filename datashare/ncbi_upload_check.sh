#!/bin/bash
# filepath: /home/himals/3_resources/github-repos/himal_scripts/datashare/ncbi_upload_check.sh

# NCBI BioSample Upload Check Script
# Checks if AUSMDU IDs are already uploaded to NCBI BioSample database.
# Note: Use entrez conda environment: conda activate /home/hccooper/conda/envs/entrez

set -euo pipefail

# Default values
INPUT_FILE="ids.txt"
OUTPUT_DIR="ncbi_check_results"
JOBS=4
FOUND_TSV="found_biosamples.tsv"
NOT_FOUND_TXT="not_found_ids.txt"
LOG_FILE="ncbi_check.log"

# Function to print usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Checks if AUSMDU IDs are already uploaded to NCBI BioSample database.

OPTIONS:
    -i, --input FILE        Input file containing AUSMDU IDs (default: $INPUT_FILE)
    -o, --output-dir DIR    Output directory for results (default: $OUTPUT_DIR)
    -j, --jobs NUM          Number of parallel jobs (default: $JOBS)
    -f, --found-file FILE   TSV file for found biosamples (default: $FOUND_TSV)
    -n, --not-found FILE    File for IDs not found (default: $NOT_FOUND_TXT)
    -l, --log-file FILE     Log file path (default: $LOG_FILE)
    -h, --help              Show this help message and exit

EXAMPLES:
    $0 -i ausmdu_ids.txt -o results -j 8
    $0 --input ids.txt --output-dir ./ncbi_results --jobs 4

OUTPUT FILES:
    - found_biosamples.tsv: Tab-separated file with metadata for found IDs
    - not_found_ids.txt: List of IDs not found in NCBI
    - ncbi_check.log: Detailed log of operations

REQUIREMENTS:
    - entrez-direct (esearch, efetch)
    - gnu parallel

NOTE:
    Activate entrez conda environment before running:
    conda activate /home/hccooper/conda/envs/entrez

EOF
}

# Function to log messages with timestamp
log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$message"
    echo "$message" >> "$OUTPUT_DIR/$LOG_FILE"
}

# Function to check dependencies
check_dependencies() {
    local missing_tools=()
    
    for tool in esearch efetch parallel; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log "ERROR: Missing required tools: ${missing_tools[*]}"
        log "ERROR: Please ensure entrez conda environment is activated"
        return 1
    fi
    
    return 0
}

# Function to parse biosample data and extract fields
parse_biosample() {
    local ausmdu_id="$1"
    local data="$2"
    
    # Check if data contains valid biosample information
    if ! echo "$data" | grep -q "Identifiers: BioSample:"; then
        return 1
    fi
    
    # Extract fields using grep and sed
    local biosample_id=$(echo "$data" | grep "Identifiers: BioSample:" | sed -n 's/.*BioSample: \([^;]*\).*/\1/p' | head -1)
    local sra_id=$(echo "$data" | grep "Identifiers: BioSample:" | sed -n 's/.*SRA: \([^ ]*\).*/\1/p' | head -1)
    local organism=$(echo "$data" | grep "Organism:" | sed 's/Organism: //' | head -1)
    local strain=$(echo "$data" | grep "/strain=" | sed 's/.*\/strain="\([^"]*\)".*/\1/' | head -1)
    local collection_date=$(echo "$data" | grep "/collection date=" | sed 's/.*\/collection date="\([^"]*\)".*/\1/' | head -1)
    local location=$(echo "$data" | grep "/geographic location=" | sed 's/.*\/geographic location="\([^"]*\)".*/\1/' | head -1)
    local isolation_source=$(echo "$data" | grep "/isolation source=" | sed 's/.*\/isolation source="\([^"]*\)".*/\1/' | head -1)
    local genotype=$(echo "$data" | grep "/genotype=" | sed 's/.*\/genotype="\([^"]*\)".*/\1/' | head -1)
    local host=$(echo "$data" | grep "/host=" | sed 's/.*\/host="\([^"]*\)".*/\1/' | head -1)
    local host_disease=$(echo "$data" | grep "/host disease=" | sed 's/.*\/host disease="\([^"]*\)".*/\1/' | head -1)
    local accession=$(echo "$data" | grep "Accession:" | sed 's/.*Accession: \([^ ]*\).*/\1/' | head -1)
    
    # Output tab-separated values
    echo -e "${ausmdu_id}\t${biosample_id}\t${sra_id}\t${organism}\t${strain}\t${collection_date}\t${location}\t${isolation_source}\t${genotype}\t${host}\t${host_disease}\t${accession}"
    
    return 0
}

# Export functions for parallel
export -f parse_biosample

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--input)
            INPUT_FILE="$2"
            shift 2
            ;;
        -o|--output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -j|--jobs)
            JOBS="$2"
            shift 2
            ;;
        -f|--found-file)
            FOUND_TSV="$2"
            shift 2
            ;;
        -n|--not-found)
            NOT_FOUND_TXT="$2"
            shift 2
            ;;
        -l|--log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Main script execution
main() {
    # Create output directory first
    mkdir -p "$OUTPUT_DIR"
    
    log "Starting NCBI BioSample upload check script"
    
    # Check if conda environment message should be shown
    if [[ -z "${CONDA_DEFAULT_ENV:-}" ]]; then
        log "WARNING: Consider activating entrez conda environment: conda activate /home/hccooper/conda/envs/entrez"
    else
        log "INFO: Using conda environment: $CONDA_DEFAULT_ENV"
    fi
    
    # Check dependencies
    if ! check_dependencies; then
        exit 1
    fi
    
    # Check if input file exists
    if [[ ! -f "$INPUT_FILE" ]]; then
        log "ERROR: Input file not found: $INPUT_FILE"
        exit 1
    fi
    
    # Count total IDs
    local total_ids=$(wc -l < "$INPUT_FILE")
    log "Found $total_ids AUSMDU IDs to check"
    
    # Prepare output files
    log "Preparing output files"
    rm -f "$OUTPUT_DIR/$FOUND_TSV" "$OUTPUT_DIR/$NOT_FOUND_TXT"
    touch "$OUTPUT_DIR/$NOT_FOUND_TXT"
    
    # Create TSV header
    echo -e "AUSMDU_ID\tBioSample_ID\tSRA_ID\tOrganism\tStrain\tCollection_Date\tGeographic_Location\tIsolation_Source\tGenotype\tHost\tHost_Disease\tAccession" > "$OUTPUT_DIR/$FOUND_TSV"
    
    log "Starting parallel checks with $JOBS jobs"
    log "Reading AUSMDU IDs from: $INPUT_FILE"
    log "Output directory: $OUTPUT_DIR"
    
    # Process each ID in parallel
    cat "$INPUT_FILE" | parallel -j "$JOBS" "
        ausmdu_id={}
        echo \"[$(date '+%Y-%m-%d %H:%M:%S')] Checking \$ausmdu_id...\" >> $OUTPUT_DIR/$LOG_FILE
        
        # Query NCBI BioSample database
        result=\$(esearch -db biosample -query \"\$ausmdu_id\" 2>/dev/null | efetch -format text 2>/dev/null || echo '')
        
        # Check if result is empty or contains no valid data
        if [ -z \"\$result\" ] || ! echo \"\$result\" | grep -q 'Identifiers: BioSample:'; then
            echo \"\$ausmdu_id\" >> $OUTPUT_DIR/$NOT_FOUND_TXT
            echo \"[$(date '+%Y-%m-%d %H:%M:%S')] \$ausmdu_id - NOT FOUND\" >> $OUTPUT_DIR/$LOG_FILE
        else
            # Parse and save the data
            parsed=\$(echo \"\$result\" | bash -c 'source /dev/stdin' <<< \"\$(declare -f parse_biosample); parse_biosample \$ausmdu_id \\\"\$result\\\"\")
            if [ -n \"\$parsed\" ]; then
                echo \"\$parsed\" >> $OUTPUT_DIR/$FOUND_TSV
                echo \"[$(date '+%Y-%m-%d %H:%M:%S')] \$ausmdu_id - FOUND\" >> $OUTPUT_DIR/$LOG_FILE
            else
                echo \"\$ausmdu_id\" >> $OUTPUT_DIR/$NOT_FOUND_TXT
                echo \"[$(date '+%Y-%m-%d %H:%M:%S')] \$ausmdu_id - PARSE ERROR\" >> $OUTPUT_DIR/$LOG_FILE
            fi
        fi
    "
    
    # Check if the parallel command succeeded
    if [[ $? -eq 0 ]]; then
        log "NCBI BioSample check completed successfully"
        
        # Generate summary
        local found_count=$(($(wc -l < "$OUTPUT_DIR/$FOUND_TSV") - 1))  # Subtract header
        local not_found_count=$(wc -l < "$OUTPUT_DIR/$NOT_FOUND_TXT")
        
        log "============================================"
        log "SUMMARY:"
        log "Total IDs checked: $total_ids"
        log "Found in NCBI: $found_count"
        log "Not found: $not_found_count"
        log "============================================"
        log "Output files:"
        log "  - Found biosamples: $OUTPUT_DIR/$FOUND_TSV"
        log "  - Not found IDs: $OUTPUT_DIR/$NOT_FOUND_TXT"
        log "  - Log file: $OUTPUT_DIR/$LOG_FILE"
    else
        log "ERROR: Parallel command failed"
        exit 1
    fi
}

# Run the main function
main "$@"