#!/usr/bin/env python3
"""
Script to locate and extract source read files for isolates from sequence paths.

This script:
1. Reads a TSV file with isolate and sequence path information
2. Locates the read files for each isolate based on the sequencer type
3. Either copies the files directly or concatenates multiple files
4. Saves the resulting files to a specified output directory

Example TSV input:
2011-111111-1   /home/mdu/instruments/nextseq550/250111_NB22345_0541_AHLYJNAFX7
2022-222222-1   /home/mdu/instruments/nextseq2000/250111_VH2234505_158_AAFYCLLM5
2033-333333     /home/mdu/instruments/nextseq500/250111_NS22345_0678_AHV7WNAFX7
"""

import argparse
import os
import sys
import glob
import shutil
import subprocess
import logging
import datetime
import re
from tqdm import tqdm


def setup_logger(log_file=None, log_level=logging.INFO):
    """Set up logger with timestamp and formatting."""
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Create formatter with timestamp
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", 
                                 datefmt="%Y-%m-%d %H:%M:%S")
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if log file specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def parse_arguments():
    """Parse command line arguments with detailed help."""
    parser = argparse.ArgumentParser(
        description="Locate and extract source read files for isolates from sequencing runs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python copy_source_reads.py -i isolate_sequence_path.tsv -o source_reads
  
  # With log file and overwrite existing files
  python copy_source_reads.py -i isolate_sequence_path.tsv -o source_reads -l extract.log --overwrite
  
  # Process only specific isolates
  python copy_source_reads.py -i isolate_sequence_path.tsv -o source_reads --isolates 2011-111111-1 2022-222222-1
  
Notes:
  The input TSV file should contain isolate IDs and sequence paths without headers.
  For NextSeq 550/500, files are searched in <sequence_path>/Alignment_1/*/Fastq/
  For NextSeq 2000, files are searched in <sequence_path>/Analysis/*/Data/fastq/
"""
    )
    
    parser.add_argument(
        "-i", "--input", 
        required=True, 
        help="Input TSV file with isolate and sequence path (no headers)"
    )
    
    parser.add_argument(
        "-o", "--output-dir", 
        default="source_reads",
        help="Output directory for source read files (default: source_reads)"
    )
    
    parser.add_argument(
        "-l", "--log-file",
        help="Log file to write messages (default: console only)"
    )
    
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files in output directory"
    )
    
    parser.add_argument(
        "--isolates",
        nargs="+",
        help="Process only these specific isolates (space-separated list)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output with detailed processing information"
    )
    
    parser.add_argument(
        "-s", "--summary-file",
        default="source_reads.tab",
        help="Output summary file with isolate and file paths (default: source_reads.tab)"
    )    
    
    return parser.parse_args()


def read_isolate_data(input_file, isolate_filter=None):
    """
    Read the input TSV file and return isolate-path pairs.
    
    Args:
        input_file: Path to the TSV file
        isolate_filter: Optional list of isolates to filter by
        
    Returns:
        List of (isolate, path) tuples
    """
    isolate_data = []
    
    try:
        with open(input_file, 'r') as f:
            for line in f:
                # Skip empty lines and comments
                if not line.strip() or line.strip().startswith('#'):
                    continue
                    
                # Parse line as tab-separated values
                parts = line.strip().split('\t')
                if len(parts) < 2:
                    logging.warning(f"Skipping invalid line: {line.strip()}")
                    continue
                
                isolate, seq_path = parts[0], parts[1]
                
                # Apply isolate filter if specified
                if isolate_filter and isolate not in isolate_filter:
                    continue
                    
                isolate_data.append((isolate, seq_path))
    
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading input file: {e}")
        sys.exit(1)
    
    return isolate_data


def determine_sequencer_type(seq_path):
    """
    Determine the sequencer type from the sequence path.
    
    Args:
        seq_path: Path to the sequence directory
        
    Returns:
        Sequencer type ("nextseq550", "nextseq500", "nextseq2000", or None)
    """
    if "nextseq550" in seq_path.lower():
        return "nextseq550"
    elif "nextseq500" in seq_path.lower():
        return "nextseq500"
    elif "nextseq2000" in seq_path.lower():
        return "nextseq2000"
    else:
        return None


def find_read_files(isolate, seq_path, sequencer_type):
    """
    Find read files for an isolate based on sequencer type.
    
    Args:
        isolate: Isolate ID
        seq_path: Path to the sequence directory
        sequencer_type: Type of sequencer
        
    Returns:
        Dictionary with R1 and R2 file lists
    """
    read_files = {"R1": [], "R2": []}
    
    try:
        # Define search path based on sequencer type
        if sequencer_type in ["nextseq550", "nextseq500"]:
            search_path = os.path.join(seq_path, "Alignment_1", "*", "Fastq")
        elif sequencer_type == "nextseq2000":
            search_path = os.path.join(seq_path, "Analysis", "*", "Data", "fastq")
        else:
            logging.error(f"Unknown sequencer type for isolate {isolate}: {sequencer_type}")
            return read_files
        
        # Check if the search path exists
        if not glob.glob(search_path):
            logging.warning(f"Search path not found for isolate {isolate}: {search_path}")
            return read_files
        
        # Use grep-like search to find files matching the isolate pattern
        # First, find all fastq.gz files in the search path
        all_fastq_files = []
        for path in glob.glob(search_path):
            all_fastq_files.extend(glob.glob(os.path.join(path, "*.fastq.gz")))
        
        # Filter for isolate name
        matching_files = [f for f in all_fastq_files if isolate in os.path.basename(f)]
        
        if not matching_files:
            logging.warning(f"No read files found for isolate {isolate} in {search_path}")
            return read_files
        
        # Separate R1 and R2 files
        for file_path in matching_files:
            if "_R1_" in file_path or "_R1." in file_path:
                read_files["R1"].append(file_path)
            elif "_R2_" in file_path or "_R2." in file_path:
                read_files["R2"].append(file_path)
        
        # Sort files to ensure consistent order
        read_files["R1"].sort()
        read_files["R2"].sort()
        
    except Exception as e:
        logging.error(f"Error finding read files for isolate {isolate}: {e}")
    
    return read_files


def process_read_files(isolate, read_files, output_dir, overwrite=False):
    """
    Process read files by either copying or concatenating them.
    
    Args:
        isolate: Isolate ID
        read_files: Dictionary with R1 and R2 file lists
        output_dir: Base output directory
        overwrite: Whether to overwrite existing files
        
    Returns:
        True if successful, False otherwise
    """
    # Create isolate output directory
    isolate_dir = os.path.join(output_dir, isolate)
    os.makedirs(isolate_dir, exist_ok=True)
    
    # Check if we have both R1 and R2 files
    if not read_files["R1"] or not read_files["R2"]:
        logging.warning(f"Missing R1 or R2 files for isolate {isolate}")
        return False
    
    try:
        # Case 1: Exactly one R1 and one R2 file - direct copy
        if len(read_files["R1"]) == 1 and len(read_files["R2"]) == 1:
            r1_src = read_files["R1"][0]
            r2_src = read_files["R2"][0]
            
            r1_dest = os.path.join(isolate_dir, f"{isolate}_R1.fastq.gz")
            r2_dest = os.path.join(isolate_dir, f"{isolate}_R2.fastq.gz")
            
            # Check if output files already exist
            if os.path.exists(r1_dest) and os.path.exists(r2_dest) and not overwrite:
                logging.info(f"Output files already exist for isolate {isolate} and overwrite=False")
                return True
            
            # Copy files
            shutil.copy2(r1_src, r1_dest)
            shutil.copy2(r2_src, r2_dest)
            
            logging.info(f"Copied read files for isolate {isolate}")
        
        # Case 2: Multiple files - concatenate
        else:
            r1_dest = os.path.join(isolate_dir, f"{isolate}_R1.fastq.gz")
            r2_dest = os.path.join(isolate_dir, f"{isolate}_R2.fastq.gz")
            
            # Check if output files already exist
            if os.path.exists(r1_dest) and os.path.exists(r2_dest) and not overwrite:
                logging.info(f"Output files already exist for isolate {isolate} and overwrite=False")
                return True
            
            # Concatenate R1 files
            if read_files["R1"]:
                with open(r1_dest, 'wb') as outfile:
                    for file_path in read_files["R1"]:
                        with open(file_path, 'rb') as infile:
                            shutil.copyfileobj(infile, outfile)
            
            # Concatenate R2 files
            if read_files["R2"]:
                with open(r2_dest, 'wb') as outfile:
                    for file_path in read_files["R2"]:
                        with open(file_path, 'rb') as infile:
                            shutil.copyfileobj(infile, outfile)
            
            logging.info(f"Concatenated {len(read_files['R1'])} R1 files and {len(read_files['R2'])} R2 files for isolate {isolate}")
        
        return True
    
    except Exception as e:
        logging.error(f"Error processing read files for isolate {isolate}: {e}")
        return False


def process_isolates(isolate_data, output_dir, overwrite=False, summary_file=None):
    """
    Process each isolate to find and copy/concatenate read files.
    
    Args:
        isolate_data: List of (isolate, path) tuples
        output_dir: Base output directory
        overwrite: Whether to overwrite existing files
        summary_file: Path to output summary file
        
    Returns:
        Dictionary with counts of successful and failed isolates
    """
    results = {"success": 0, "failure": 0}
    
    # For tracking file paths
    file_paths = []
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each isolate with progress bar
    for isolate, seq_path in tqdm(isolate_data, desc="Processing isolates"):
        logging.info(f"Processing isolate: {isolate} with path: {seq_path}")
        
        # Determine sequencer type
        sequencer_type = determine_sequencer_type(seq_path)
        if not sequencer_type:
            logging.error(f"Could not determine sequencer type for isolate {isolate} from path: {seq_path}")
            results["failure"] += 1
            continue
        
        logging.info(f"Determined sequencer type: {sequencer_type} for isolate {isolate}")
        
        # Find read files
        read_files = find_read_files(isolate, seq_path, sequencer_type)
        
        if not read_files["R1"] and not read_files["R2"]:
            logging.error(f"No read files found for isolate {isolate}")
            results["failure"] += 1
            continue
        
        logging.info(f"Found {len(read_files['R1'])} R1 files and {len(read_files['R2'])} R2 files for isolate {isolate}")
        
        # Define destination file paths
        isolate_dir = os.path.join(output_dir, isolate)
        r1_dest = os.path.join(isolate_dir, f"{isolate}_R1.fastq.gz")
        r2_dest = os.path.join(isolate_dir, f"{isolate}_R2.fastq.gz")
        
        # Process read files
        success = process_read_files(isolate, read_files, output_dir, overwrite)
        
        if success:
            # Add full paths to the tracking list
            r1_full_path = os.path.abspath(r1_dest)
            r2_full_path = os.path.abspath(r2_dest)
            file_paths.append((isolate, r1_full_path, r2_full_path))
            results["success"] += 1
        else:
            results["failure"] += 1
    
    # Write summary file if requested
    if summary_file and file_paths:
        try:
            with open(summary_file, 'w') as f:
                for isolate, r1_path, r2_path in file_paths:
                    f.write(f"{isolate}\t{r1_path}\t{r2_path}\n")
            logging.info(f"Wrote summary file with file paths to {summary_file}")
        except Exception as e:
            logging.error(f"Error writing summary file: {e}")
    
    return results


def main():
    """Main function to orchestrate the script execution."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger(args.log_file, log_level)
    
    logging.info("Starting source read extraction")
    logging.info(f"Input file: {args.input}")
    logging.info(f"Output directory: {args.output_dir}")
    
    # Read isolate data
    isolate_data = read_isolate_data(args.input, args.isolates)
    logging.info(f"Read {len(isolate_data)} isolates from input file")
    
    if not isolate_data:
        logging.error("No isolate data found. Exiting.")
        sys.exit(1)
    
    # Process isolates
    results = process_isolates(isolate_data, args.output_dir, args.overwrite, args.summary_file)
    
    # Report results
    logging.info(f"Processing complete: {results['success']} successful, {results['failure']} failed")
    
    # Exit with error code if any failures
    if results["failure"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()