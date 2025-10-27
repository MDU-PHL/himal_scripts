#!/bin/bash

# skani_summary.sh - Run skani search on multiple isolates and summarize results

set -euo pipefail

# Default values
DATABASE="/home/khhor/BIS008/extra/skani/refseq_db/"
KEEP_TEMP=false
INPUT_FILE=""
OUTPUT_DIR="."
LOG_FILE="skani_summary.log"

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 -i INPUT_FILE [-d DATABASE] [-o OUTPUT_DIR] [--keep-temp]

Run skani search on multiple isolates and concatenate results

OPTIONS:
    -i, --input FILE      Input file with isolate IDs and contig paths (tab-separated)
    -d, --database PATH   Skani database path (default: $DATABASE)
    -o, --output-dir DIR  Output directory for results (default: current directory)
    --keep-temp           Keep individual skani output files
    -h, --help           Show this help message

EXAMPLES:
    $0 -i contigs.tab
    $0 -i contigs.tab -d /path/to/gtdb/db -o /path/to/output --keep-temp

Make sure to 'conda activate skani' environment before running.

Input file format (tab-separated, no headers):
    MDU-ID1	/path/to/contig1.fa
    MDU-ID2	/path/to/contig2.fa

The script will:
1. Run skani search for each isolate against the specified database
2. Concatenate all outputs using csvtk into skani_summary.tsv
3. Log progress and results
EOF
}

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to log errors
log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: $1" | tee -a "$LOG_FILE" >&2
}

# Function to check dependencies
check_dependencies() {
    local missing_deps=()
    
    if ! command -v skani &> /dev/null; then
        missing_deps+=("skani")
    fi
    
    if ! command -v csvtk &> /dev/null; then
        missing_deps+=("csvtk")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        echo "Please install missing dependencies and ensure they are in PATH"
        exit 1
    fi
}

# Function to read contigs file
read_contigs_file() {
    local input_file="$1"
    
    if [[ ! -f "$input_file" ]]; then
        log_error "Input file not found: $input_file"
        exit 1
    fi
    
    local count=$(wc -l < "$input_file")
    log_message "Read $count isolates from $input_file"
}

# Function to run skani search for single isolate
run_skani_search() {
    local mdu_id="$1"
    local contig_path="$2"
    local database_path="$3"
    local output_dir="$4"
    local output_file="${output_dir}/${mdu_id}.txt"
    
    if [[ ! -f "$contig_path" ]]; then
        log_message "WARNING: Contig file not found: $contig_path"
        return 1
    fi
    
    log_message "Processing $mdu_id"
    
    if skani search "$contig_path" -d "$database_path" > "$output_file" 2>/dev/null; then
        log_message "Completed skani search for $mdu_id"
        echo "$output_file"
        return 0
    else
        log_error "Skani search failed for $mdu_id"
        return 1
    fi
}

# Function to concatenate results using csvtk
concatenate_results() {
    local output_dir="$1"
    local output_files=("$@")
    
    # Skip the first argument (output_dir)
    output_files=("${output_files[@]:1}")
    
    if [ ${#output_files[@]} -eq 0 ]; then
        log_error "No output files to concatenate"
        return 1
    fi
    
    log_message "Concatenating ${#output_files[@]} output files using csvtk"
    
    # Change to output directory for csvtk command
    cd "$output_dir"
    
    # Use csvtk to concatenate all .txt files
    if csvtk -t concat *.txt > skani_summary.tsv 2>/dev/null; then
        log_message "Successfully created skani_summary.tsv"
        return 0
    else
        log_error "Failed to concatenate files with csvtk"
        return 1
    fi
}

# Function to process all isolates
process_isolates() {
    local input_file="$1"
    local database_path="$2"
    local output_dir="$3"
    local output_files=()
    
    local total_lines=$(wc -l < "$input_file")
    local current=0
    
    while IFS=$'\t' read -r mdu_id contig_path; do
        ((current++))
        echo "Progress: $current/$total_lines"
        
        local output_file
        if output_file=$(run_skani_search "$mdu_id" "$contig_path" "$database_path" "$output_dir"); then
            output_files+=("$output_file")
        fi
    done < "$input_file"
    
    echo "${output_files[@]}" > "${output_dir}/.temp_files_list"
    echo "${output_files[@]}"
}

# Function to cleanup temporary files
cleanup_temp_files() {
    local output_dir="$1"
    local keep_temp="$2"
    
    if [[ -f "${output_dir}/.temp_files_list" ]]; then
        if [[ "$keep_temp" == "false" ]]; then
            while read -r file; do
                if [[ -f "$file" ]]; then
                    rm -f "$file"
                fi
            done < "${output_dir}/.temp_files_list"
            rm -f "${output_dir}/.temp_files_list"
            log_message "Temporary files cleaned up"
        else
            log_message "Temporary files kept in $output_dir"
        fi
    fi
}



# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--input)
            INPUT_FILE="$2"
            shift 2
            ;;
        -d|--database)
            DATABASE="$2"
            shift 2
            ;;
        -o|--output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --keep-temp)
            KEEP_TEMP=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$INPUT_FILE" ]]; then
    echo "Error: Input file (-i) is required"
    show_usage
    exit 1
fi

# Main execution
main() {
    # Create output directory if it doesn't exist
    mkdir -p "$OUTPUT_DIR"
    
    # Initialize log in output directory
    LOG_FILE="${OUTPUT_DIR}/skani_summary.log"
    echo "Starting skani summary analysis" > "$LOG_FILE"
    
    log_message "Input file: $INPUT_FILE"
    log_message "Database: $DATABASE"
    log_message "Output directory: $OUTPUT_DIR"
    
    # Check dependencies
    check_dependencies
    
    # Check if database exists
    if [[ ! -d "$DATABASE" ]]; then
        log_error "Database path does not exist: $DATABASE"
        exit 1
    fi
    
    # Read input file
    read_contigs_file "$INPUT_FILE"
    
    # Process isolates
    log_message "Starting processing of isolates"
    local output_files
    output_files=$(process_isolates "$INPUT_FILE" "$DATABASE" "$OUTPUT_DIR")
    
    # Concatenate results
    if concatenate_results "$OUTPUT_DIR" $output_files; then
        log_message "Results concatenated into ${OUTPUT_DIR}/skani_summary.tsv"
    else
        log_error "Failed to concatenate results"
        exit 1
    fi
    
    # Cleanup
    cleanup_temp_files "$OUTPUT_DIR" "$KEEP_TEMP"
    
    log_message "Analysis completed successfully."
}

# Run main function
main "$@"