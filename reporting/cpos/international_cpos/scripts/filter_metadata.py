#!/usr/bin/env python3

import pandas as pd
import argparse
import os
import re
import sys

def main():
    # Set up argument parser with detailed help
    parser = argparse.ArgumentParser(
        description='Filter metadata file based on contigs_list.txt for mashtree analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python filter_metadata.py -c contigs_list.txt -m metadata.csv -o filtered_metadata.csv
  python filter_metadata.py --contigs-list mashtree_analysis/contigs_list.txt --metadata kpneumo_kpc3_pathogen_detection.csv --output mashtree_analysis/filtered_metadata.csv --pattern "GCA_\\d+\\.\\d+"
        '''
    )
    
    parser.add_argument('-c', '--contigs-list', required=True, 
                        help='Path to the contigs_list.txt file containing paths to contig files')
    parser.add_argument('-m', '--metadata', required=True, 
                        help='Path to the full metadata file (CSV format)')
    parser.add_argument('-o', '--output', required=True, 
                        help='Path to save the filtered metadata file')
    parser.add_argument('-p', '--pattern', default=r'(GCA_\d+\.\d+)',
                        help='Regular expression pattern to extract accession from contigs paths (default: GCA_\\d+\\.\\d+). This default pattern extracts NCBI assembly accessions.')
    parser.add_argument('-a', '--accession-col', default='accession',
                        help='Name of the accession column in the metadata file (default: accession)')
    parser.add_argument('-g', '--geo-col', default='geoLocName',
                        help='Name of the geographic location column (default: geoLocName)')
    
    args = parser.parse_args()
    
    # Check if input files exist
    for file_path in [args.contigs_list, args.metadata]:
        if not os.path.isfile(file_path):
            sys.exit(f"Error: File '{file_path}' does not exist.")
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    try:
        # Read the contigs list file and extract accessions
        with open(args.contigs_list, 'r') as f:
            contigs_paths = f.readlines()
        
        # Extract accessions and filenames using regex
        accessions = set()
        accession_to_filename = {}
        
        for path in contigs_paths:
            path = path.strip()
            if not path:  # Skip empty lines
                continue
            
            # Extract accession using regex pattern
            match = re.search(args.pattern, path)
            if match:
                accession = match.group(0)
                accessions.add(accession)
                
                # Extract filename (basename without extension)
                filename = os.path.basename(path)
                filename = os.path.splitext(filename)[0]  # Remove extension
                
                accession_to_filename[accession] = filename
        
        # Read the metadata CSV file
        df = pd.read_csv(args.metadata)
        
        # Check if accession column exists
        if args.accession_col not in df.columns:
            sys.exit(f"Error: Accession column '{args.accession_col}' not found in metadata file.")
        
        # Filter the dataframe to keep only rows where accession is in our list
        # Create a copy to avoid the SettingWithCopyWarning
        filtered_df = df[df[args.accession_col].isin(accessions)].copy()
        
        # Add country column (first word from geoLocName)
        if args.geo_col in df.columns:
            filtered_df.loc[:, 'country'] = filtered_df[args.geo_col].fillna('Unknown').apply(
                lambda x: x.split(':')[0].split(',')[0].strip()
            )
        else:
            print(f"Warning: Geographic location column '{args.geo_col}' not found. 'country' column will not be added.")
        
        # Add filename column based on accession
        filtered_df.loc[:, 'filename'] = filtered_df[args.accession_col].map(accession_to_filename)
        
        # Save the filtered data
        filtered_df.to_csv(args.output, index=False)
        
        # Display summary
        print(f"Found {len(accessions)} unique accessions in contigs list")
        print(f"Filtered data contains {len(filtered_df)} rows")
        print(f"Added 'country' and 'filename' columns")
        print(f"Output saved to: {args.output}")
        
    except Exception as e:
        sys.exit(f"Error: {str(e)}")

if __name__ == "__main__":
    main()