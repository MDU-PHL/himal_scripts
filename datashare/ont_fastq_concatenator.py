#!/usr/bin/env python3
"""
Script to concatenate FASTQ files from ONT sequencing runs based on a samplesheet.
The script reads a samplesheet CSV file containing MDU IDs and barcodes, locates 
the corresponding FASTQ files,and concatenates them into single files per MDU ID 
in a structured output directory.
Author: Himal Shrestha
"""

import argparse
import csv
import os
import glob
import subprocess
import sys
import datetime
import re

def log_message(message):
    """Print a formatted log message with timestamp."""
    now = datetime.datetime.now()
    timestamp = now.strftime("[%Y-%m-%d] [%H:%M:%S]")
    print(f"{timestamp} LOG: {message}")

def barcode_to_directory(barcode):
    """Convert barcode format RB## to barcode## format."""
    match = re.match(r"RB(\d+)", barcode)
    if match:
        number = match.group(1)
        # Add leading zero if needed
        if len(number) == 1:
            number = "0" + number
        return f"barcode{number}"
    return None

def concatenate_fastq_files(samplesheet_path, fastq_dir, output_dir, run_id):
    """Concatenate FASTQ files based on samplesheet information."""
    
    # Create output directory structure: output_dir/run_id/
    run_output_dir = os.path.join(output_dir, run_id)
    if not os.path.exists(run_output_dir):
        os.makedirs(run_output_dir)
        log_message(f"Created output directory: {run_output_dir}")
    
    skipped_files = []
    
    # Read samplesheet
    with open(samplesheet_path, 'r') as csv_file:
        reader = csv.DictReader(csv_file, delimiter='\t')
        for row in reader:
            mdu_id = row['MDU_ID'].strip()
            barcode = row['Barcode'].strip()
            
            # Convert barcode format
            barcode_dir = barcode_to_directory(barcode)
            if not barcode_dir:
                log_message(f"Warning: Could not convert barcode {barcode} to directory name. Skipping.")
                continue
            
            # Define paths
            barcode_path = os.path.join(fastq_dir, barcode_dir)
            mdu_output_dir = os.path.join(run_output_dir, mdu_id)
            os.makedirs(mdu_output_dir, exist_ok=True)
            output_file = os.path.join(mdu_output_dir, f"{mdu_id}.fastq.gz")
            
            # Check if output file already exists
            if os.path.exists(output_file):
                log_message(f"Skipping {mdu_id}: Output file already exists at {output_file}")
                skipped_files.append(output_file)
                continue
            
            # Check if barcode directory exists
            if not os.path.exists(barcode_path):
                log_message(f"Warning: Directory {barcode_path} not found. Skipping {mdu_id}.")
                continue
            
            # Find fastq.gz files
            fastq_files = glob.glob(os.path.join(barcode_path, "*.fastq.gz"))
            if not fastq_files:
                log_message(f"Warning: No fastq.gz files found in {barcode_path}. Skipping {mdu_id}.")
                continue
            
            # Concatenate files
            log_message(f"Concatenating fastq files for {barcode_dir}, MDU ID: {mdu_id}")
            cmd = f"cat {barcode_path}/*.fastq.gz > {output_file}"
            log_message(f"Command executed: {cmd}")
            
            try:
                subprocess.run(cmd, shell=True, check=True)
                log_message(f"Successfully created {output_file}")
            except subprocess.CalledProcessError as e:
                log_message(f"Error executing command: {e}")
    
    # Log summary of skipped files
    if skipped_files:
        log_message(f"\nSummary: {len(skipped_files)} file(s) were skipped (already exist, pleaes check):")
        for skipped in skipped_files:
            log_message(f"  - {skipped}")

def main():
    parser = argparse.ArgumentParser(
        description="Concatenate FASTQ files based on samplesheet information.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python3 ont_fastq_concatenator.py -s samplesheet.tsv -f /path/to/fastq -o ont_reads -r RUN001

  # Using abbreviated arguments
  python3 ont_fastq_concatenator.py -s samplesheet.tsv -f /path/to/fastq -o ont_reads -r RUN001
        """
    )
    
    parser.add_argument("-s", "--samplesheet", required=True,
                        help="Path to the samplesheet TSV file")
    parser.add_argument("-f", "--fastq-dir", required=True,
                        help="Path to the directory containing barcode directories with FASTQ files")
    parser.add_argument("-o", "--output-dir", default="/home/mdu/ont_reads",
                        help="Output directory for concatenated FASTQ files (default: /home/mdu/ont_reads)")
    parser.add_argument("-r", "--run-id", required=True,
                        help="Run ID for organising output files")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.samplesheet):
        sys.exit(f"Error: Samplesheet file {args.samplesheet} does not exist")
    
    if not os.path.exists(args.fastq_dir):
        sys.exit(f"Error: FASTQ directory {args.fastq_dir} does not exist")
    
    concatenate_fastq_files(args.samplesheet, args.fastq_dir, args.output_dir, args.run_id)

if __name__ == "__main__":
    main()