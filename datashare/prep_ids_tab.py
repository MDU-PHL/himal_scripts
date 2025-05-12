#!/usr/bin/env python3
# filepath: prep_ids_tab.py

import argparse
import csv
import os
import sys

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process LIMS output file to create an ID mapping file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python process_lims.py -i mdu-ausmdu-lims.tab -o ids.tab
  
Input file format (TSV):
  MDU sample ID   Item code       Alt ID
  2011-xxxxx              AUSMDU000xxxxx
  2011-xxxxx              AUSMDU000xxxxx
  2011-xxxxx         1    AUSMDU000xxxxx
  
Output format:
  Sample IDs with Item codes appended if present (e.g., 2011-XXXXX-1)
  Headers are removed in the output file
  ---
  2011-xxxxx    AUSMDU000xxxxx
  2011-xxxxx    AUSMDU000xxxxx
  2011-xxxxx-1  AUSMDU000xxxxx
        """
    )
    
    parser.add_argument(
        "-i", "--input", default="mdu-ausmdu-lims.tab",
        help="Input LIMS TSV file with sample IDs (default: mdu-ausmdu-lims.tab)"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="ids.tab",
        help="Output file to write processed IDs (default: ids.tab)"
    )
    
    return parser.parse_args()

def process_lims_file(input_file, output_file):
    """
    Process LIMS file to create ID mapping.
    
    Args:
        input_file (str): Path to input TSV file
        output_file (str): Path to output file
    
    Returns:
        int: Number of records processed
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found", file=sys.stderr)
        sys.exit(1)
        
    count = 0
    
    try:
        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            reader = csv.reader(infile, delimiter='\t')
            
            # Skip header
            next(reader, None)
            
            for row in reader:
                if len(row) < 3:
                    continue  # Skip invalid rows
                
                mdu_id = row[0].strip()
                item_code = row[1].strip() if len(row) > 1 else ""
                aus_mdu_id = row[2].strip() if len(row) > 2 else ""
                
                # Create new ID based on whether item code exists
                if item_code:
                    new_id = f"{mdu_id}-{item_code}"
                else:
                    new_id = mdu_id
                    
                # Write both the processed ID and the AUSMDU ID
                outfile.write(f"{new_id}\t{aus_mdu_id}\n")
                count += 1
                
        return count
        
    except Exception as e:
        print(f"Error processing file: {str(e)}", file=sys.stderr)
        sys.exit(1)

def main():
    """Main entry point of the script."""
    args = parse_arguments()
    
    print(f"Processing LIMS file: {args.input}")
    record_count = process_lims_file(args.input, args.output)
    print(f"Successfully processed {record_count} records to {args.output}")

if __name__ == "__main__":
    main()