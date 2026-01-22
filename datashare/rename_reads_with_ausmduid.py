#!/usr/bin/env python3
"""
Rename and copy FASTQ reads files using AUSMDU ID mapping.

This script copies FASTQ files and renames them from MDU IDs to AUSMDU IDs
based on provided mapping files. It handles paired-end reads (R1/R2) and
can process files in parallel for improved performance.
"""

import argparse
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Tuple, List, Optional, Union


def log_message(level: str, message: str) -> None:
    """
    Print formatted log message with timestamp.
    
    Args:
        level: Log level (INFO, WARNING, ERROR)
        message: Message to log
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] - {level}: {message}", flush=True)


def load_id_mapping(ids_file: Path) -> Dict[str, str]:
    """
    Load MDU ID to AUSMDU ID mapping from tab-delimited file.
    
    Args:
        ids_file: Path to ids.tab file
        
    Returns:
        Dictionary mapping MDU ID to AUSMDU ID
        
    Raises:
        FileNotFoundError: If ids file doesn't exist
        ValueError: If file format is invalid
    """
    log_message("INFO", f"Loading ID mapping from {ids_file}")
    
    if not ids_file.exists():
        raise FileNotFoundError(f"IDs file not found: {ids_file}")
    
    id_mapping = {}
    line_num = 0
    
    with open(ids_file, 'r') as f:
        for line in f:
            line_num += 1
            line = line.strip()
            if not line:
                continue
                
            parts = line.split('\t')
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid format at line {line_num}: expected 2 columns, got {len(parts)}"
                )
            
            mdu_id, ausmdu_id = parts[0].strip(), parts[1].strip()
            
            if not mdu_id or not ausmdu_id:
                raise ValueError(f"Empty ID at line {line_num}")
            
            if mdu_id in id_mapping:
                log_message("WARNING", f"Duplicate MDU ID '{mdu_id}' at line {line_num}")
            
            id_mapping[mdu_id] = ausmdu_id
    
    log_message("INFO", f"Loaded {len(id_mapping)} ID mappings")
    return id_mapping


def load_reads_mapping(reads_file: Path, ont: bool = False) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """
    Load reads file paths from tab-delimited file.
    
    Args:
        reads_file: Path to reads.tab file
        ont: If True, expect 2 columns (ID, path) for ONT reads; if False, expect 3 columns (ID, R1, R2)
        
    Returns:
        Dictionary mapping MDU ID to tuple of (R1_path, R2_path) or (path, None) for ONT
        
    Raises:
        FileNotFoundError: If reads file doesn't exist
        ValueError: If file format is invalid
    """
    log_message("INFO", f"Loading reads mapping from {reads_file}")
    
    if not reads_file.exists():
        raise FileNotFoundError(f"Reads file not found: {reads_file}")
    
    reads_mapping = {}
    line_num = 0
    expected_cols = 2 if ont else 3
    
    with open(reads_file, 'r') as f:
        for line in f:
            line_num += 1
            line = line.strip()
            if not line:
                continue
                
            parts = line.split('\t')
            if len(parts) != expected_cols:
                raise ValueError(
                    f"Invalid format at line {line_num}: expected {expected_cols} columns, got {len(parts)}"
                )
            
            if ont:
                # ONT format: ID and single path
                mdu_id, read_path = [p.strip() for p in parts]
                
                if not mdu_id or not read_path:
                    raise ValueError(f"Empty field at line {line_num}")
                
                if mdu_id in reads_mapping:
                    log_message("WARNING", f"Duplicate MDU ID '{mdu_id}' at line {line_num}")
                
                reads_mapping[mdu_id] = (read_path, None)
            else:
                # Paired-end format: ID, R1, R2
                mdu_id, r1_path, r2_path = [p.strip() for p in parts]
                
                if not mdu_id or not r1_path or not r2_path:
                    raise ValueError(f"Empty field at line {line_num}")
                
                if mdu_id in reads_mapping:
                    log_message("WARNING", f"Duplicate MDU ID '{mdu_id}' at line {line_num}")
                
                reads_mapping[mdu_id] = (r1_path, r2_path)
    
    log_message("INFO", f"Loaded {len(reads_mapping)} read file mappings")
    return reads_mapping


def extract_suffix_from_filename(filename: str, mdu_id: str) -> str:
    """
    Extract the suffix from filename after removing the MDU ID prefix.
    
    This function carefully handles MDU IDs to avoid confusion between
    IDs with and without item codes (e.g., 2004-111111 vs 2004-111111-2).
    
    Args:
        filename: Original filename
        mdu_id: MDU ID to remove from filename
        
    Returns:
        Suffix portion of filename (e.g., '-KPC_S35_L001_R1_001.fastq.gz')
        
    Raises:
        ValueError: If MDU ID is not found at start of filename
    """
    # Remove file extension temporarily
    basename = filename
    if basename.endswith('.gz'):
        basename = basename[:-3]
    if basename.endswith('.fastq') or basename.endswith('.fq'):
        ext_pos = basename.rfind('.')
        basename = basename[:ext_pos]
    
    # Check if basename starts with the MDU ID
    if not basename.startswith(mdu_id):
        raise ValueError(
            f"Filename '{filename}' does not start with MDU ID '{mdu_id}'"
        )
    
    # Extract suffix - everything after the MDU ID
    suffix = basename[len(mdu_id):]
    
    # Add back the extension
    if filename.endswith('.fastq.gz'):
        suffix += '.fastq.gz'
    elif filename.endswith('.fq.gz'):
        suffix += '.fq.gz'
    elif filename.endswith('.fastq'):
        suffix += '.fastq'
    elif filename.endswith('.fq'):
        suffix += '.fq'
    
    return suffix


def copy_and_rename_file(
    source_path: str,
    output_dir: Path,
    mdu_id: str,
    ausmdu_id: str
) -> Tuple[bool, str]:
    """
    Copy and rename a single FASTQ file.
    
    Args:
        source_path: Source file path
        output_dir: Destination directory
        mdu_id: Original MDU ID
        ausmdu_id: New AUSMDU ID
        
    Returns:
        Tuple of (success, message)
    """
    source = Path(source_path)
    
    if not source.exists():
        return False, f"Source file not found: {source_path}"
    
    try:
        # Extract suffix from original filename
        original_filename = source.name
        suffix = extract_suffix_from_filename(original_filename, mdu_id)
        
        # Create new filename with AUSMDU ID
        new_filename = f"{ausmdu_id}{suffix}"
        dest_path = output_dir / new_filename
        
        # Copy file
        shutil.copy2(source, dest_path)
        
        return True, f"Copied: {original_filename} -> {new_filename}"
        
    except Exception as e:
        return False, f"Error copying {source_path}: {str(e)}"


def process_sample(
    mdu_id: str,
    ausmdu_id: str,
    reads_paths: Tuple[Optional[str], Optional[str]],
    output_dir: Path
) -> Tuple[str, bool, List[str]]:
    """
    Process a single sample (copy and rename R1 and R2 files, or single ONT file).
    
    Args:
        mdu_id: MDU ID
        ausmdu_id: AUSMDU ID
        reads_paths: Tuple of (R1_path, R2_path) or (path, None) for ONT
        output_dir: Output directory
        
    Returns:
        Tuple of (mdu_id, success, messages)
    """
    r1_path, r2_path = reads_paths
    messages = []
    success = True
    
    # Process R1 (or single ONT file)
    r1_success, r1_msg = copy_and_rename_file(r1_path, output_dir, mdu_id, ausmdu_id)
    messages.append(r1_msg)
    success = success and r1_success
    
    # Process R2 (only for paired-end reads)
    if r2_path is not None:
        r2_success, r2_msg = copy_and_rename_file(r2_path, output_dir, mdu_id, ausmdu_id)
        messages.append(r2_msg)
        success = success and r2_success
    
    return mdu_id, success, messages


def validate_inputs(
    id_mapping: Dict[str, str],
    reads_mapping: Dict[str, Tuple[Optional[str], Optional[str]]]
) -> Tuple[List[str], List[str]]:
    """
    Validate that IDs and reads are properly matched.
    
    Args:
        id_mapping: MDU ID to AUSMDU ID mapping
        reads_mapping: MDU ID to read paths mapping
        
    Returns:
        Tuple of (ids_without_ausmdu, ids_without_reads)
    """
    ids_without_ausmdu = []
    ids_without_reads = []
    
    # Check for IDs in reads but not in ID mapping
    for mdu_id in reads_mapping.keys():
        if mdu_id not in id_mapping:
            ids_without_ausmdu.append(mdu_id)
    
    # Check for IDs in ID mapping but not in reads
    for mdu_id in id_mapping.keys():
        if mdu_id not in reads_mapping:
            ids_without_reads.append(mdu_id)
    
    return ids_without_ausmdu, ids_without_reads


def main():
    """Main function to orchestrate the renaming process."""
    parser = argparse.ArgumentParser(
        description="Copy and rename FASTQ files using AUSMDU ID mapping",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (paired-end reads)
  %(prog)s -i ids.tab -r reads.tab -o output_dir
  
  # ONT reads (single file per sample)
  %(prog)s -i ids.tab -r reads_ont.tab -o output_dir --ont
  
  # With parallel processing (4 workers)
  %(prog)s -i ids.tab -r reads.tab -o output_dir -p 4
  
  # Abbreviated arguments
  %(prog)s -i ids.tab -r reads.tab -o output_dir -p 8

Input file formats:
  ids.tab (tab-delimited, no header):
    MDU_ID  AUSMDU_ID
    2004-111111 AUSMDU00012111
  
  reads.tab for paired-end (tab-delimited, no header):
    MDU_ID  R1_PATH   R2_PATH
    2004-111111 /path/to/R1.fastq.gz /path/to/R2.fastq.gz
  
  reads.tab for ONT with --ont flag (tab-delimited, no header):
    MDU_ID  PATH
    2004-111111 /path/to/reads.fastq.gz
        """
    )
    
    parser.add_argument(
        '-i', '--ids',
        type=Path,
        required=True,
        metavar='FILE',
        help='Path to ids.tab file (MDU ID to AUSMDU ID mapping)'
    )
    
    parser.add_argument(
        '-r', '--reads',
        type=Path,
        required=True,
        metavar='FILE',
        help='Path to reads.tab file (MDU ID to read file paths)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=Path,
        required=True,
        metavar='DIR',
        help='Output directory for renamed files'
    )
    
    parser.add_argument(
        '--ont',
        action='store_true',
        help='ONT mode: reads.tab has 2 columns (ID, path) instead of 3 (ID, R1, R2)'
    )
    
    parser.add_argument(
        '-p', '--parallel',
        type=int,
        default=4,
        metavar='N',
        help='Number of parallel workers (default: 4)'
    )
    
    args = parser.parse_args()
    
    log_message("INFO", "Starting rename_reads_with_ausmduid script")
    
    try:
        # Load mappings
        id_mapping = load_id_mapping(args.ids)
        reads_mapping = load_reads_mapping(args.reads, ont=args.ont)
        
        # Validate inputs
        log_message("INFO", "Validating inputs")
        ids_without_ausmdu, ids_without_reads = validate_inputs(id_mapping, reads_mapping)
        
        if ids_without_ausmdu:
            log_message("WARNING", f"{len(ids_without_ausmdu)} MDU IDs have reads but no AUSMDU mapping:")
            for mdu_id in sorted(ids_without_ausmdu):
                log_message("WARNING", f"  - {mdu_id}")
        
        if ids_without_reads:
            log_message("WARNING", f"{len(ids_without_reads)} MDU IDs have AUSMDU mapping but no reads:")
            for mdu_id in sorted(ids_without_reads):
                log_message("WARNING", f"  - {mdu_id}")
        
        # Create output directory
        args.output.mkdir(parents=True, exist_ok=True)
        log_message("INFO", f"Output directory: {args.output}")
        
        # Prepare samples to process (only those with both mapping and reads)
        samples_to_process = []
        for mdu_id, ausmdu_id in id_mapping.items():
            if mdu_id in reads_mapping:
                samples_to_process.append((mdu_id, ausmdu_id, reads_mapping[mdu_id]))
        
        log_message("INFO", f"Processing {len(samples_to_process)} samples")
        
        # Process samples
        success_count = 0
        error_count = 0
        
        if args.parallel > 1:
            log_message("INFO", f"Using {args.parallel} parallel workers")
            with ProcessPoolExecutor(max_workers=args.parallel) as executor:
                futures = {
                    executor.submit(
                        process_sample,
                        mdu_id,
                        ausmdu_id,
                        reads_paths,
                        args.output
                    ): mdu_id
                    for mdu_id, ausmdu_id, reads_paths in samples_to_process
                }
                
                for future in as_completed(futures):
                    mdu_id, success, messages = future.result()
                    
                    if success:
                        success_count += 1
                        log_message("INFO", f"Successfully processed {mdu_id}")
                    else:
                        error_count += 1
                        log_message("ERROR", f"Failed to process {mdu_id}")
                    
                    for msg in messages:
                        level = "INFO" if success else "ERROR"
                        log_message(level, f"  {msg}")
        else:
            log_message("INFO", "Processing sequentially (no parallelization)")
            for mdu_id, ausmdu_id, reads_paths in samples_to_process:
                mdu_id, success, messages = process_sample(
                    mdu_id, ausmdu_id, reads_paths, args.output
                )
                
                if success:
                    success_count += 1
                    log_message("INFO", f"Successfully processed {mdu_id}")
                else:
                    error_count += 1
                    log_message("ERROR", f"Failed to process {mdu_id}")
                
                for msg in messages:
                    level = "INFO" if success else "ERROR"
                    log_message(level, f"  {msg}")
        
        # Summary
        log_message("INFO", "=" * 60)
        log_message("INFO", f"Processing complete:")
        log_message("INFO", f"  - Successfully processed: {success_count} samples")
        if error_count > 0:
            log_message("ERROR", f"  - Failed: {error_count} samples")
        if ids_without_ausmdu:
            log_message("WARNING", f"  - Missing AUSMDU mapping: {len(ids_without_ausmdu)} IDs")
        if ids_without_reads:
            log_message("WARNING", f"  - Missing reads: {len(ids_without_reads)} IDs")
        log_message("INFO", "=" * 60)
        
        # Exit with appropriate code
        if error_count > 0:
            sys.exit(1)
        
    except Exception as e:
        log_message("ERROR", f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()