#!/usr/bin/env python3
"""
Collate standard_bacteria_qc.csv files for specified isolates.

This script reads a TSV file containing sample IDs and run IDs, searches for
corresponding QC files, and collates the results into a single CSV output.
If different header sets are encountered, separate output files are created.
"""

import argparse
import csv
import glob
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging with custom format [YYYY-MM-DD HH:MM:SS] - LEVEL: message."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Create custom formatter
    class CustomFormatter(logging.Formatter):
        def format(self, record):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return f"[{timestamp}] - {record.levelname}: {record.getMessage()}"
    
    handler.setFormatter(CustomFormatter())
    logger.addHandler(handler)
    
    return logger


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Collate standard_bacteria_qc.csv files for specified isolates from run directories.',
        epilog='''
Example:
  %(prog)s -i search-FAIL_ID_RUNID.tsv -o collated_qc.csv
  %(prog)s --input samples.tsv --output results.csv --qc-dir /home/mdu/qc --verbose

Input TSV format:
  <sample-id1>\\t<M2024-xxxxx>
  <sample-id2>\\t<D2025-xxxxx>

Note: If different header sets are found, multiple output files will be created
      with names like: collated_qc_1.csv, collated_qc_2.csv, etc.
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-i', '--input',
        type=str,
        required=True,
        metavar='FILE',
        help='Input TSV file containing sample IDs and run IDs (tab-separated)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        required=True,
        metavar='FILE',
        help='Output CSV file for collated QC results (multiple files may be created if headers differ)'
    )
    
    parser.add_argument(
        '-q', '--qc-dir',
        type=str,
        default='/home/mdu/qc',
        metavar='PATH',
        help='Base QC directory path (default: /home/mdu/qc)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output (DEBUG level logging)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.1'
    )
    
    return parser.parse_args()


def extract_year_from_runid(run_id: str, logger: logging.Logger) -> Optional[str]:
    """
    Extract year from run ID (e.g., M2024-xxxxx -> 2024, D2025-xxxxx -> 2025).
    
    Args:
        run_id: Run ID string
        logger: Logger instance
        
    Returns:
        Year as string or None if extraction fails
    """
    try:
        # Match patterns like M2024-xxxxx, D2025-xxxxx, etc.
        match = re.search(r'[A-Z](\d{4})-', run_id)
        if match:
            year = match.group(1)
            logger.debug(f"Extracted year {year} from run ID {run_id}")
            return year
        else:
            logger.warning(f"Could not extract year from run ID: {run_id}")
            return None
    except Exception as e:
        logger.error(f"Error extracting year from {run_id}: {e}")
        return None


def read_input_tsv(input_file: str, logger: logging.Logger) -> List[Tuple[str, str]]:
    """
    Read input TSV file containing sample IDs and run IDs.
    
    Args:
        input_file: Path to input TSV file
        logger: Logger instance
        
    Returns:
        List of tuples (sample_id, run_id)
    """
    logger.info(f"Reading input file: {input_file}")
    
    samples = []
    
    try:
        if not os.path.exists(input_file):
            logger.error(f"Input file does not exist: {input_file}")
            return samples
        
        with open(input_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Split by tab
                parts = line.split('\t')
                
                if len(parts) < 2:
                    logger.warning(f"Line {line_num}: Invalid format (expected tab-separated values): {line}")
                    continue
                
                sample_id = parts[0].strip()
                run_id = parts[1].strip()
                
                if sample_id and run_id:
                    samples.append((sample_id, run_id))
                    logger.debug(f"Added sample: {sample_id} from run: {run_id}")
                else:
                    logger.warning(f"Line {line_num}: Empty sample ID or run ID")
        
        logger.info(f"Successfully read {len(samples)} sample entries")
        return samples
        
    except Exception as e:
        logger.error(f"Error reading input file: {e}")
        return []


def find_qc_files(qc_base_dir: str, year: str, run_id: str, logger: logging.Logger) -> List[str]:
    """
    Find all standard_bacteria_qc.csv* files for a given run.
    
    Args:
        qc_base_dir: Base QC directory path
        year: Year extracted from run ID
        run_id: Run ID
        logger: Logger instance
        
    Returns:
        List of matching file paths
    """
    search_pattern = os.path.join(qc_base_dir, year, run_id, 'standard_bacteria_qc.csv*')
    logger.debug(f"Searching for files: {search_pattern}")
    
    try:
        files = glob.glob(search_pattern)
        
        if files:
            logger.debug(f"Found {len(files)} QC file(s) for {run_id}: {files}")
        else:
            logger.warning(f"No QC files found for {run_id} at {search_pattern}")
        
        return sorted(files)
        
    except Exception as e:
        logger.error(f"Error searching for QC files: {e}")
        return []


def extract_sample_from_qc_file(qc_file: str, sample_id: str, logger: logging.Logger) -> Optional[Tuple[Dict[str, str], List[str]]]:
    """
    Extract a specific sample's QC data from a CSV file.
    
    Args:
        qc_file: Path to QC CSV file
        sample_id: Sample ID to search for
        logger: Logger instance
        
    Returns:
        Tuple of (QC data dictionary, original column order) or None if not found
    """
    logger.debug(f"Searching for {sample_id} in {qc_file}")
    
    try:
        with open(qc_file, 'r') as f:
            reader = csv.DictReader(f)
            
            # Get the original column order from the CSV
            original_columns = reader.fieldnames if reader.fieldnames else []
            
            if not original_columns:
                logger.warning(f"No headers found in {os.path.basename(qc_file)}")
                return None
            
            # The first column should contain the sample ID
            first_column = original_columns[0]
            logger.debug(f"Searching in first column: {first_column}")
            
            for row in reader:
                # Check if sample ID matches in the first column (case-insensitive)
                if first_column in row and row[first_column]:
                    if row[first_column].strip().upper() == sample_id.upper():
                        logger.info(f"Found {sample_id} in {os.path.basename(qc_file)} (column: {first_column})")
                        return row, original_columns
            
            logger.debug(f"Sample {sample_id} not found in {os.path.basename(qc_file)}")
            return None
        
    except Exception as e:
        logger.error(f"Error reading {qc_file}: {e}")
        return None


def get_header_signature(columns: List[str]) -> str:
    """
    Create a signature string from column headers for comparison.
    
    Args:
        columns: List of column names
        
    Returns:
        String signature of the headers
    """
    return '|'.join(columns)


def collate_qc_data(samples: List[Tuple[str, str]], qc_base_dir: str, logger: logging.Logger) -> Dict[str, Tuple[List[Dict[str, str]], List[str]]]:
    """
    Collate QC data for all samples, grouped by header set.
    
    Args:
        samples: List of (sample_id, run_id) tuples
        qc_base_dir: Base QC directory path
        logger: Logger instance
        
    Returns:
        Dictionary mapping header signatures to (list of QC data, headers list)
    """
    logger.info(f"Starting QC data collation for {len(samples)} samples")
    
    # Dictionary to store data grouped by header signature
    grouped_data = {}
    header_count = 0
    found_count = 0
    not_found_count = 0
    
    for sample_id, run_id in samples:
        logger.info(f"Processing: {sample_id} from {run_id}")
        
        # Extract year from run ID
        year = extract_year_from_runid(run_id, logger)
        if not year:
            logger.error(f"Skipping {sample_id}: Could not extract year from {run_id}")
            not_found_count += 1
            continue
        
        # Find QC files
        qc_files = find_qc_files(qc_base_dir, year, run_id, logger)
        
        if not qc_files:
            logger.warning(f"No QC files found for {sample_id} in {run_id}")
            not_found_count += 1
            continue
        
        # Search for sample in QC files
        sample_found = False
        for qc_file in qc_files:
            result = extract_sample_from_qc_file(qc_file, sample_id, logger)
            
            if result:
                qc_data, file_columns = result
                
                # Add metadata
                qc_data['_SOURCE_FILE'] = os.path.basename(qc_file)
                qc_data['_RUN_ID'] = run_id
                qc_data['_YEAR'] = year
                
                # Create final headers with metadata
                final_headers = list(file_columns) + ['_SOURCE_FILE', '_RUN_ID', '_YEAR']
                header_sig = get_header_signature(final_headers)
                
                # Check if this header set already exists
                if header_sig not in grouped_data:
                    header_count += 1
                    grouped_data[header_sig] = ([], final_headers)
                    logger.info(f"New header set detected (#{header_count}): {file_columns[0]} (first column)")
                    logger.debug(f"Full header set: {', '.join(file_columns[:5])}... ({len(file_columns)} columns)")
                
                # Add data to the appropriate group
                grouped_data[header_sig][0].append(qc_data)
                
                sample_found = True
                found_count += 1
                break
        
        if not sample_found:
            logger.warning(f"Sample {sample_id} not found in any QC file for {run_id}")
            not_found_count += 1
    
    logger.info(f"Collation complete: {found_count} found, {not_found_count} not found")
    logger.info(f"Detected {len(grouped_data)} unique header set(s)")
    
    return grouped_data


def generate_output_filename(base_output: str, index: int, total: int) -> str:
    """
    Generate output filename with suffix if multiple files needed.
    
    Args:
        base_output: Base output filename
        index: Current file index (0-based)
        total: Total number of files
        
    Returns:
        Output filename
    """
    if total == 1:
        return base_output
    
    # Split filename and extension
    path = Path(base_output)
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    
    # Add _N before extension
    new_name = f"{stem}_{index + 1}{suffix}"
    return str(parent / new_name) if parent != Path('.') else new_name


def write_output_csv(output_file: str, qc_data: List[Dict[str, str]], headers: List[str], logger: logging.Logger) -> bool:
    """
    Write collated QC data to output CSV file.
    
    Args:
        output_file: Path to output CSV file
        qc_data: List of QC data dictionaries
        headers: List of CSV headers in correct order
        logger: Logger instance
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Writing output to: {output_file}")
    
    try:
        if not qc_data:
            logger.warning("No QC data to write")
            # Still create empty file with headers
            with open(output_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers if headers else ['NO_DATA'])
                writer.writeheader()
            logger.info("Created empty output file")
            return True
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            
            for row in qc_data:
                writer.writerow(row)
        
        logger.info(f"Successfully wrote {len(qc_data)} records with {len(headers)} columns")
        return True
        
    except Exception as e:
        logger.error(f"Error writing output file: {e}")
        return False


def main():
    """Main function to orchestrate the script execution."""
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    logger.info("Starting QC data collation script")
    logger.info(f"Input file: {args.input}")
    logger.info(f"Output base: {args.output}")
    logger.info(f"QC base directory: {args.qc_dir}")
    
    # Read input TSV
    samples = read_input_tsv(args.input, logger)
    if not samples:
        logger.error("No valid samples found in input file")
        sys.exit(1)
    
    # Collate QC data (grouped by header set)
    grouped_data = collate_qc_data(samples, args.qc_dir, logger)
    
    if not grouped_data:
        logger.error("No QC data found for any samples")
        sys.exit(1)
    
    # Write output files
    success_count = 0
    total_groups = len(grouped_data)
    
    logger.info(f"Writing {total_groups} output file(s)")
    
    for idx, (header_sig, (qc_data, headers)) in enumerate(grouped_data.items()):
        output_file = generate_output_filename(args.output, idx, total_groups)
        
        logger.info(f"Output file {idx + 1}/{total_groups}: {output_file}")
        logger.info(f"  - Records: {len(qc_data)}")
        logger.info(f"  - Columns: {len(headers)}")
        logger.info(f"  - First column: {headers[0]}")
        
        if write_output_csv(output_file, qc_data, headers, logger):
            success_count += 1
    
    # Summary
    if success_count == total_groups:
        logger.info(f"QC data collation completed successfully - {success_count} file(s) created")
        sys.exit(0)
    else:
        logger.error(f"Failed to write some output files ({success_count}/{total_groups} successful)")
        sys.exit(1)


if __name__ == '__main__':
    main()