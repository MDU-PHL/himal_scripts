#!/usr/bin/env python3

import argparse
import shutil
import os
import sys

def main():
    # Set up argument parser with detailed help
    parser = argparse.ArgumentParser(
        description='Copy contig files listed in a tab-delimited file to a specified directory.',
        epilog='Example: python copy_contigs.py -i mashtree_analysis/contigs.tab -o mashtree_analysis'
    )
    
    parser.add_argument('-i', '--input', required=True, 
                        help='Path to the contigs.tab file with format: <sample_id> <path_to_contig_file>')
    parser.add_argument('-o', '--output', required=True, 
                        help='Directory where contigs files will be copied to')
    parser.add_argument('-e', '--extension', default='.fa',
                        help='Extension to use for copied files (default: .fa)')
    parser.add_argument('-f', '--force', action='store_true',
                        help='Overwrite existing files in the output directory')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print detailed progress information')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.isfile(args.input):
        sys.exit(f"Error: Input file '{args.input}' does not exist.")
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Read contigs.tab file
    try:
        with open(args.input, 'r') as f:
            contigs_data = [line.strip().split() for line in f if line.strip()]
    except Exception as e:
        sys.exit(f"Error reading input file: {str(e)}")
    
    # Validate the contigs data format
    for i, row in enumerate(contigs_data):
        if len(row) != 2:
            sys.exit(f"Error: Line {i+1} in '{args.input}' does not have exactly two columns.")
    
    # Copy and rename files
    success_count = 0
    error_count = 0
    
    for sample_id, contig_path in contigs_data:
        # Define destination path
        dest_path = os.path.join(args.output, f'{sample_id}{args.extension}')
        
        # Check if destination file already exists
        if os.path.exists(dest_path) and not args.force:
            print(f"Warning: '{dest_path}' already exists. Use --force to overwrite.")
            error_count += 1
            continue
        
        # Copy and rename file
        try:
            shutil.copy2(contig_path, dest_path)
            success_count += 1
            if args.verbose:
                print(f"Copied {contig_path} to {dest_path}")
        except Exception as e:
            print(f"Error copying {contig_path}: {str(e)}")
            error_count += 1
    
    print(f"\nProcessing complete:")
    print(f"  - Total entries: {len(contigs_data)}")
    print(f"  - Successfully copied: {success_count}")
    print(f"  - Errors/skipped: {error_count}")

if __name__ == "__main__":
    main()