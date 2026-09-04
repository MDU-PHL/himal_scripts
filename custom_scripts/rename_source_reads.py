#!/usr/bin/env python3
"""
Script to rename and copy source read files for isolates.

This script:
1. Reads a TSV file mapping original IDs to new IDs
2. Locates the read files for each original ID in the specified raw directory
3. Renames the files using the new ID and copies them to an output directory
4. Keeps multiple fastq files for each sample without concatenating

Example TSV input:
2011-111111-1   2022-111111-1
2022-222222-1   2023-222222-1
"""

import argparse
import os
import sys
import shutil
import logging
from tqdm import tqdm


def setup_logger(log_file=None, log_level=logging.INFO):
    """Set up logger with timestamp and formatting."""
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", 
                                 datefmt="%Y-%m-%d %H:%M:%S")
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Rename and copy source read files for isolates.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "-i", "--input", 
        required=True, 
        help="Input TSV file with original ID and new ID (no headers)"
    )
    
    parser.add_argument(
        "-r", "--raw-dir", 
        required=True, 
        help="Directory where the raw fastq files are located"
    )
    
    parser.add_argument(
        "-o", "--output-dir", 
        default="renamed_reads",
        help="Output directory for renamed read files (default: renamed_reads)"
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
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output with detailed processing information"
    )
    
    return parser.parse_args()


def read_mapping_data(input_file):
    """
    Read the input TSV file and return original->new ID mapping.
    """
    mapping = {}
    
    try:
        with open(input_file, 'r') as f:
            for line in f:
                if not line.strip() or line.strip().startswith('#'):
                    continue
                    
                parts = line.strip().split('\t')
                if len(parts) < 2:
                    logging.warning(f"Skipping invalid line: {line.strip()}")
                    continue
                
                original_id, new_id = parts[0].strip(), parts[1].strip()
                
                if original_id in mapping:
                    logging.warning(f"Duplicate original ID found: {original_id}. Overwriting with new mapping.")
                
                mapping[original_id] = new_id
    
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading input file: {e}")
        sys.exit(1)
    
    return mapping


def process_samples(mapping, raw_dir, output_dir, overwrite=False):
    """
    Process each sample to find, rename and copy read files.
    """
    results = {"success": 0, "failure": 0}
    
    if not os.path.exists(raw_dir):
        logging.error(f"Raw directory not found: {raw_dir}")
        results["failure"] = len(mapping)
        return results
        
    os.makedirs(output_dir, exist_ok=True)
    
    # Scan raw directory for all fastq files to speed up searching
    logging.info(f"Scanning raw directory: {raw_dir}")
    all_fastqs = []
    for root, dirs, files in os.walk(raw_dir):
        for f in files:
            if f.endswith('.fastq.gz') or f.endswith('.fastq'):
                all_fastqs.append(os.path.join(root, f))
    logging.info(f"Found {len(all_fastqs)} fastq files in raw directory")
    
    for original_id, new_id in tqdm(mapping.items(), desc="Processing samples"):
        logging.info(f"Processing ID: {original_id} -> {new_id}")
        
        # Find files matching the original ID exactly in their basename
        matching_files = [f for f in all_fastqs if original_id in os.path.basename(f)]
        
        if not matching_files:
            logging.warning(f"No read files found for original ID {original_id}")
            results["failure"] += 1
            continue
            
        # Flag inconsistencies
        if len(matching_files) % 2 != 0:
            logging.warning(f"Odd number of files ({len(matching_files)}) found for ID {original_id}. Expected paired-end reads.")
            
        success = True
        for src_path in matching_files:
            filename = os.path.basename(src_path)
            # Rename by replacing the first occurrence of original_id with new_id to be safe
            new_filename = filename.replace(original_id, new_id, 1)
            dest_path = os.path.join(output_dir, new_filename)
            
            if os.path.exists(dest_path) and not overwrite:
                logging.info(f"Destination file already exists (skipping): {dest_path}")
                continue
                
            try:
                shutil.copy2(src_path, dest_path)
                logging.debug(f"Copied and renamed: {filename} -> {new_filename}")
            except Exception as e:
                logging.error(f"Error copying {src_path} to {dest_path}: {e}")
                success = False
                
        if success:
            results["success"] += 1
            logging.info(f"Successfully processed {len(matching_files)} files for ID {original_id}")
        else:
            results["failure"] += 1
            
    return results


def main():
    args = parse_arguments()
    
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger(args.log_file, log_level)
    
    logging.info("Starting source read renaming and copying")
    logging.info(f"Input mapping file: {args.input}")
    logging.info(f"Raw directory: {args.raw_dir}")
    logging.info(f"Output directory: {args.output_dir}")
    
    mapping = read_mapping_data(args.input)
    logging.info(f"Read {len(mapping)} ID mappings from input file")
    
    if not mapping:
        logging.error("No mapping data found. Exiting.")
        sys.exit(1)
    
    results = process_samples(mapping, args.raw_dir, args.output_dir, args.overwrite)
    
    logging.info(f"Processing complete: {results['success']} successful, {results['failure']} failed")
    
    if results["failure"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
