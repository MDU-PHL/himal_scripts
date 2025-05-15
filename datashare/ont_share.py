#!/usr/bin/env python3

import argparse
import os
import shutil
import glob
import datetime
import sys

def log_message(message):
    """Print a formatted log message with timestamp."""
    now = datetime.datetime.now()
    timestamp = now.strftime("[%Y-%m-%d] [%H:%M:%S]")
    print(f"{timestamp} LOG: {message}")

def read_id_mapping(mapping_file):
    """Read the mapping file and return a dictionary of MDU ID to AUSMDU ID."""
    id_map = {}
    try:
        with open(mapping_file, 'r') as f:
            for line in f:
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        mdu_id = parts[0]
                        ausmdu_id = parts[1]
                        id_map[mdu_id] = ausmdu_id
        return id_map
    except Exception as e:
        log_message(f"Error reading mapping file: {e}")
        sys.exit(1)

def copy_and_rename_files(ont_reads_dir, destination_dir, id_map):
    """Copy and rename files based on the ID mapping."""
    # Create destination directory if it doesn't exist
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)
        log_message(f"Created destination directory: {destination_dir}")
    
    # Process each MDU ID in the mapping
    for mdu_id, ausmdu_id in id_map.items():
        # Find all files matching the pattern
        file_pattern = os.path.join(ont_reads_dir, f"{mdu_id}*fastq.gz")
        matching_files = glob.glob(file_pattern)
        
        if not matching_files:
            log_message(f"Warning: No files found matching {file_pattern}")
            continue
        
        # Process each matching file
        for source_file in matching_files:
            # Get the file name and extract the suffix after MDU ID
            file_name = os.path.basename(source_file)
            suffix = file_name[len(mdu_id):]
            
            # Create the new file name
            new_file_name = f"{ausmdu_id}{suffix}"
            destination_file = os.path.join(destination_dir, new_file_name)
            
            # Copy the file
            log_message(f"Copying {file_name} -> {new_file_name}")
            try:
                shutil.copy2(source_file, destination_file)
                log_message(f"Successfully copied to {destination_file}")
            except Exception as e:
                log_message(f"Error copying file {source_file}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Copy ONT read files to a destination directory with renamed IDs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python ont_share.py -m ids_to_upload.tab -i ont_reads/ -o shared_reads/
  
  # Using abbreviated arguments
  python ont_share.py -m ids_to_upload.tab -i ont_reads/ -o shared_reads/
        """
    )
    
    parser.add_argument("-m", "--mapping-file", required=True,
                        help="Path to the tab-delimited mapping file (MDU ID to AUSMDU ID)")
    parser.add_argument("-i", "--input-dir", required=True,
                        help="Path to the directory containing ONT read files")
    parser.add_argument("-o", "--output-dir", required=True,
                        help="Path to the destination directory for renamed files")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.mapping_file):
        sys.exit(f"Error: Mapping file {args.mapping_file} does not exist")
    
    if not os.path.exists(args.input_dir):
        sys.exit(f"Error: Input directory {args.input_dir} does not exist")
    
    # Read mapping file
    id_map = read_id_mapping(args.mapping_file)
    log_message(f"Loaded {len(id_map)} ID mappings from {args.mapping_file}")
    
    # Copy and rename files
    copy_and_rename_files(args.input_dir, args.output_dir, id_map)
    log_message("File copying completed")

if __name__ == "__main__":
    main()