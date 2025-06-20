#!/usr/bin/env python3
"""
Script to generate qualimap_input.tab file containing isolate IDs and paths to snps.bam files.

This script:
1. Reads a file containing isolate IDs (one per line)
2. Constructs paths to snps.bam files in a snippy results directory
3. Creates a tab-delimited output file mapping isolate IDs to BAM file paths
"""

import argparse
import os
import sys
import logging
from pathlib import Path


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
        description="Generate qualimap_input.tab file mapping isolate IDs to snps.bam file paths.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python qualimap_input_generator.py -i ids.txt -d /path/to/snippy_results -o qualimap_input.tab
  
  # With custom BAM filename and log file
  python qualimap_input_generator.py -i ids.txt -d /path/to/snippy_results -b aligned.bam -l generator.log
  
  # Check if BAM files exist and verbose output
  python qualimap_input_generator.py -i ids.txt -d /path/to/snippy_results --verify -v
"""
    )
    
    parser.add_argument(
        "-i", "--ids-file", 
        required=True, 
        help="Input file containing isolate IDs (one per line)"
    )
    
    parser.add_argument(
        "-d", "--snippy-dir", 
        required=True,
        help="Base directory containing snippy results (with isolate subdirectories)"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="qualimap_input.tab",
        help="Output tab-delimited file (default: qualimap_input.tab)"
    )
    
    parser.add_argument(
        "-b", "--bam-file",
        default="snps.bam",
        help="BAM filename within each isolate directory (default: snps.bam)"
    )
    
    parser.add_argument(
        "-l", "--log-file",
        help="Log file to write messages (default: console only)"
    )
    
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify that BAM files exist (may slow down execution)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output with detailed processing information"
    )
    
    return parser.parse_args()


def read_isolate_ids(ids_file):
    """Read isolate IDs from file, one per line."""
    try:
        with open(ids_file, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        logging.error(f"Isolate IDs file not found: {ids_file}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading isolate IDs file: {e}")
        sys.exit(1)


def generate_qualimap_input(isolate_ids, snippy_dir, bam_filename, output_file, verify=False):
    """Generate qualimap_input.tab with isolate IDs and BAM file paths."""
    success_count = 0
    missing_count = 0
    
    try:
        with open(output_file, 'w') as out:
            for isolate_id in isolate_ids:
                bam_path = os.path.join(snippy_dir, isolate_id, bam_filename)
                
                # Verify BAM file exists if requested
                if verify and not os.path.isfile(bam_path):
                    logging.warning(f"BAM file not found for isolate {isolate_id}: {bam_path}")
                    missing_count += 1
                    continue
                
                # Write to output file
                out.write(f"{isolate_id}\t{bam_path}\n")
                success_count += 1
                
                logging.debug(f"Added entry for isolate {isolate_id}")
        
        return success_count, missing_count
    
    except Exception as e:
        logging.error(f"Error generating qualimap input file: {e}")
        sys.exit(1)


def main():
    """Main function to orchestrate the script execution."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger(args.log_file, log_level)
    
    # Start execution
    logging.info("Starting qualimap input file generation")
    logging.info(f"Isolate IDs file: {args.ids_file}")
    logging.info(f"Snippy results directory: {args.snippy_dir}")
    logging.info(f"Output file: {args.output}")
    
    # Read isolate IDs
    isolate_ids = read_isolate_ids(args.ids_file)
    logging.info(f"Read {len(isolate_ids)} isolate IDs from input file")
    
    if not isolate_ids:
        logging.error("No isolate IDs found. Exiting.")
        sys.exit(1)
    
    # Generate qualimap input file
    success_count, missing_count = generate_qualimap_input(
        isolate_ids, 
        args.snippy_dir, 
        args.bam_file, 
        args.output, 
        args.verify
    )
    
    # Report results
    logging.info(f"Generation complete: {success_count} entries written to {args.output}")
    if args.verify and missing_count > 0:
        logging.warning(f"{missing_count} BAM files were missing")
    
    logging.info("Done")


if __name__ == "__main__":
    main()