#!/bin/bash

# Help function
show_help() {
    echo "Usage: $0 <runid> <sampleid> [--species species_name] [--output output_dir]"
    echo
    echo "Required arguments:"
    echo "  runid        Run ID (format: XYYYY...)"
    echo "  sampleid     Sample ID"
    echo
    echo "Optional arguments:"
    echo "  --species    Species name for abritamr (e.g., Staphylococcus_aureus)"
    echo "               If not provided, abritamr will run without species specification"
    echo "  --output     Output directory (default: abritamr_output)"
    echo
    echo "Output structure:"
    echo "  output_dir/"
    echo "  └── sample-id/"
    echo "      ├── spades/"
    echo "      ├── shovill/"
    echo "      └── skesa/"
    echo
    echo "Before running the script:"
    echo "  conda activate /home/khhor/conda/envs/abritamr"
    echo
    echo "Examples:"
    echo "  $0 X2024001 MDU001 --species Staphylococcus_aureus"
    echo "  $0 X2024001 MDU001 --output my_abritamr_results"
    echo "  $0 X2024001 MDU001"
}

# Parse arguments
if [ "$#" -lt 2 ]; then
    show_help
    exit 1
fi

runid=$1
sampleid=$2
shift 2

# Parse optional arguments
SPECIES=""
OUTPUT_DIR="abritamr_output"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --species) SPECIES="$2"; shift 2;;
        --output) OUTPUT_DIR="$2"; shift 2;;
        --help|-h) show_help; exit 0;;
        *) echo "Unknown parameter: $1"; show_help; exit 1;;
    esac
done

# Extract YYYY from runid
YYYY=${runid:1:4}

# Define assembly paths
SPADES_PATH="/home/mdu/data/$runid/$sampleid/spades/spades.fa"
SHOVILL_PATH="/home/mdu/data/$runid/$sampleid/shovill/current/contigs.fa"
SKESA_PATH="/home/mdu/data/$runid/$sampleid/skesa/current/skesa.fa"

# Function to run abritamr for a specific assembly
run_abritamr_assembly() {
    local assembly_path=$1
    local assembly_type=$2
    
    echo "=========================================="
    echo "Running abritamr for $assembly_type assembly"
    echo "Assembly path: $assembly_path"
    echo "=========================================="
    
    # Check if assembly file exists
    if [ ! -f "$assembly_path" ]; then
        echo "Warning: Assembly file not found: $assembly_path"
        return 1
    fi
    
    # Create output directory for this assembly type
    mkdir -p "$assembly_type"
    cd "$assembly_type" || exit 1
    
    # Run abritamr with or without species
    if [ -n "$SPECIES" ]; then
        echo "Running: abritamr run -c $assembly_path -px $sampleid -j 4 --species $SPECIES"
        abritamr run -c "$assembly_path" -px "$sampleid" -j 4 --species "$SPECIES"
    else
        echo "Running: abritamr run -c $assembly_path -px $sampleid -j 4"
        abritamr run -c "$assembly_path" -px "$sampleid" -j 4
    fi
    
    # Check if abritamr run was successful
    if [ $? -ne 0 ]; then
        echo "Error: abritamr run failed for $assembly_type"
        cd ..
        return 1
    fi
    
    # Move files from sample subdirectory to current directory
    if [ -d "$sampleid" ]; then
        echo "Moving abritamr output files from $sampleid/ to current directory..."
        mv "$sampleid"/* . 2>/dev/null || true
        rmdir "$sampleid" 2>/dev/null || true
    fi
    
    echo "Creating QC file..."
    # Create QC file
    if [ -n "$SPECIES" ]; then
        echo "ISOLATE,SPECIES_EXP,SPECIES_OBS,TEST_QC
$sampleid,$SPECIES,$SPECIES,PASS" > qc.tmp.csv
    else
        echo "ISOLATE,SPECIES_EXP,SPECIES_OBS,TEST_QC
$sampleid,no species,no species,PASS" > qc.tmp.csv
    fi
    
    echo "Running abritamr report..."
    # Run abritamr report
    abritamr report -q qc.tmp.csv -r "$runid" -m summary_matches.txt -p summary_partials.txt --sop general --sop_name MMS118
    
    # Check if report was successful
    if [ $? -ne 0 ]; then
        echo "Error: abritamr report failed for $assembly_type"
        cd ..
        return 1
    fi
    
    echo "Converting Excel files to CSV..."
    # Convert Excel files to CSV
    if [ -f "${runid}_MMS118.xlsx" ]; then
        csvtk xlsx2csv -n MMS118 "${runid}_MMS118.xlsx" > general_amr_matches.csv
        csvtk xlsx2csv -n 'Passed QC partial' "${runid}_MMS118.xlsx" > general_amr_partials.csv
        echo "CSV files created: general_amr_matches.csv, general_amr_partials.csv"
    else
        echo "Warning: Excel file ${runid}_MMS118.xlsx not found"
    fi
    
    cd ..
    echo "Completed abritamr analysis for $assembly_type"
    echo ""
}

# Create main output directory structure
SAMPLE_OUTPUT_DIR="$OUTPUT_DIR/$sampleid"
mkdir -p "$SAMPLE_OUTPUT_DIR"
cd "$SAMPLE_OUTPUT_DIR" || exit 1

echo "Starting abritamr analysis for sample: $sampleid, run: $runid"
echo "Output directory: $SAMPLE_OUTPUT_DIR"
if [ -n "$SPECIES" ]; then
    echo "Species: $SPECIES"
else
    echo "Species: Not specified"
fi
echo ""

# Run abritamr for each assembly type
run_abritamr_assembly "$SPADES_PATH" "spades"
run_abritamr_assembly "$SHOVILL_PATH" "shovill"
run_abritamr_assembly "$SKESA_PATH" "skesa"

echo "=========================================="
echo "All abritamr analyses completed!"
echo "Results are in directory: $SAMPLE_OUTPUT_DIR"
echo "Subdirectories created:"
echo "  - spades/"
echo "  - shovill/"
echo "  - skesa/"
echo "=========================================="
