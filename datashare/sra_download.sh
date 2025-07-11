#!/bin/bash
# filepath: /home/himals/3_resources/github-repos/himal_scripts/datashare/sra_download.sh

# SRA Download Script
# Downloads SRA files for biosample IDs and converts them to FASTQ format.
# Note: Use sra-tools conda environment: conda activate sra-tools

set -euo pipefail

# Default values
INPUT_FILE="list_genomes_to_redownload.txt"
OUTPUT_DIR="sra_data"
JOBS=24
NO_READS_FILE="no_reads_available.txt"

# Function to print usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Downloads SRA files for biosample IDs and converts them to FASTQ format.

OPTIONS:
    -i, --input FILE        Input file containing biosample IDs (default: $INPUT_FILE)
    -o, --output-dir DIR    Output directory for SRA data (default: $OUTPUT_DIR)
    -j, --jobs NUM          Number of parallel jobs (default: $JOBS)
    -n, --no-reads-file FILE File to store biosample IDs with no reads (default: $NO_READS_FILE)
    -h, --help              Show this help message and exit

EXAMPLES:
    $0 -i biosamples.txt -o sra_data -j 12
    $0 --input list_genomes_to_redownload.txt --output-dir ./downloads --jobs 24

REQUIREMENTS:
    - sra-tools (prefetch, fasterq-dump)
    - gnu parallel

NOTE:
    Activate sra-tools conda environment for best results:
    conda activate sra-tools

EOF
}

# Function to log messages with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check dependencies
check_dependencies() {
    local missing_tools=()
    
    for tool in prefetch fasterq-dump parallel; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log "ERROR: Missing required tools: ${missing_tools[*]}"
        log "ERROR: Please ensure sra-tools conda environment is activated"
        return 1
    fi
    
    return 0
}

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
        -n|--no-reads-file)
            NO_READS_FILE="$2"
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
    log "Starting SRA download script"
    
    # Check if conda environment message should be shown
    if [[ -z "${CONDA_DEFAULT_ENV:-}" ]]; then
        log "WARNING: Consider activating sra-tools conda environment: conda activate sra-tools"
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
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Prepare the no_reads_available.txt file
    log "Preparing $NO_READS_FILE"
    rm -rf "$NO_READS_FILE"
    touch "$NO_READS_FILE"
    
    log "Starting parallel download with $JOBS jobs"
    log "Reading biosample IDs from: $INPUT_FILE"
    log "Output directory: $OUTPUT_DIR"
    
    # Read biosample IDs from the file and process in parallel
    cat "$INPUT_FILE" | parallel -j "$JOBS" "
    biosample={}; 
    # Create the directory for the biosample
    mkdir -p $OUTPUT_DIR/\$biosample; 
    echo \"[$(date '+%Y-%m-%d %H:%M:%S')] Processing \$biosample...\"; 
    # Prefetch the SRA file into the biosample directory
    prefetch \$biosample -O $OUTPUT_DIR/\$biosample; 
    # Find all downloaded SRA files (handling nested directories)
    sra_files=\$(find $OUTPUT_DIR/\$biosample -name \"*.sra\"); 
    # Check if no SRA files are found
    if [ -z \"\$sra_files\" ]; then 
        echo \$biosample >> $NO_READS_FILE;
        echo \"[$(date '+%Y-%m-%d %H:%M:%S')] No SRA files found for \$biosample\";
    else 
        # Process each SRA file found
        for sra_file in \$sra_files; do 
            echo \"[$(date '+%Y-%m-%d %H:%M:%S')] Running fasterq-dump on \$sra_file\"; 
            fasterq-dump --split-files -O $OUTPUT_DIR/\$biosample \"\$sra_file\"; 
            # Remove the .sra file
            echo \"[$(date '+%Y-%m-%d %H:%M:%S')] Removing \$sra_file\";
            rm -rf \"\$sra_file\"; 
        done
    fi
    "
    
    # Check if the parallel command succeeded
    if [[ $? -eq 0 ]]; then
        log "SRA download completed successfully"
        if [[ -s "$NO_READS_FILE" ]]; then
            log "WARNING: Some biosamples had no reads available. Check $NO_READS_FILE"
        fi
    else
        log "ERROR: Parallel command failed"
        exit 1
    fi
}

# Run the main function
main "$@"