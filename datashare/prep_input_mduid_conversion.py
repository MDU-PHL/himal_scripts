#!/usr/bin/env python3
"""
MDU ID Conversion Tool

This script converts a list of sample IDs into a CSV format for MDU ID conversion.
It extracts the item code from each sample ID (the part after the second '-' if present)
and creates a CSV file with two columns: 'MDU sample ID' and 'Item code'.
"""

import argparse
import csv
import os
import sys


def extract_item_code(sample_id):
    """
    Extract the item code from a sample ID.
    
    The item code is the part after the second '-' if present,
    or any trailing digits after a single '-'.
    
    Args:
        sample_id (str): The sample ID to process
        
    Returns:
        str: The extracted item code or empty string if not found
    """
    parts = sample_id.strip().split('-')
    
    # Check if there's more than 2 parts (e.g., 2017-XXXXX-56)
    if len(parts) == 3:
        return parts[2]
    # Check if there's are more than 3 parts (e.g., 2017-XXXX-YYYY-2), return after the second '-'
    elif len(parts) > 3:
        return '-'.join(parts[2:])
            
    # No item code found
    return ""


def convert_ids(input_file, output_file):
    """
    Convert sample IDs from input file to MDU conversion CSV format.
    
    Args:
        input_file (str): Path to input file containing sample IDs
        output_file (str): Path to output CSV file
        
    Returns:
        int: Number of processed IDs
    """
    processed = 0
    
    try:
        with open(input_file, 'r') as infile, open(output_file, 'w', newline='') as outfile:
            # Create CSV writer with header
            writer = csv.writer(outfile)
            writer.writerow(["MDU sample ID", "Item code"])
            
            # Process each line
            for line in infile:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue  # Skip empty lines and comments
                
                item_code = extract_item_code(line)
                writer.writerow([line, item_code])
                processed += 1
                
        return processed
    
    except Exception as e:
        print(f"Error processing files: {e}", file=sys.stderr)
        return 0


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Convert sample IDs to MDU conversion CSV format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i ids.txt -o output.csv
  %(prog)s --input=ids.txt --output=conversion.csv

Input file format:
  One sample ID per line, e.g.:
  2017-XXXXX
  2017-YYYY-2
  2017-XXXXX-56

Output CSV format:
  MDU sample ID,Item code
  2017-XXXXX,
  2017-YYYY-2,2
  2017-XXXXX-56,56
"""
    )
    
    parser.add_argument("-i", "--input", required=True, 
                        help="Input file containing sample IDs (one per line)")
    parser.add_argument("-o", "--output", default="input_mduid-conversion.csv",
                        help="Output CSV file (default: input_mduid-conversion.csv)")
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not os.path.isfile(args.input):
        print(f"Error: Input file '{args.input}' not found", file=sys.stderr)
        return 1
    
    # Process the file
    processed = convert_ids(args.input, args.output)
    
    if processed:
        print(f"Successfully processed {processed} sample IDs")
        print(f"Output saved to: {args.output}")
        return 0
    else:
        print("No sample IDs were processed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())