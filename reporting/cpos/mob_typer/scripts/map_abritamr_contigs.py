#!/usr/bin/env python3

import pandas as pd
import argparse
import sys
import os

def map_abritamr_to_contigs(abritamr_file, contigs_file, output_file):
    """
    Map contig IDs from collated abritamr.out file to sample IDs and contig file paths.
    
    Parameters:
    -----------
    abritamr_file : str
        Path to collated abritamr.out file (<gene_name>_abritamr.tab)
    contigs_file : str
        Path to contigs.tab file (no header, sample_id and contig_path columns)
    output_file : str
        Path to output file for contig information
    
    Returns:
    --------
    bool
        True if successful, False otherwise
    """
    print(f"Processing collated abritamr.out file file: {abritamr_file}")
    print(f"Processing contigs file: {contigs_file}")
    
    # Get gene name from abritamr file name
    gene_name = os.path.basename(abritamr_file).split("_abritamr")[0]
    print(f"Detected gene: {gene_name}")
    
    try:
        # Read the ABRIcate AMR file
        abritamr_df = pd.read_csv(abritamr_file, sep='\t')
        
        # Extract Contig ID column (second column)
        contig_info_df = pd.DataFrame()
        # contig_info_df['contig_id'] = abritamr_df.iloc[:, 1]

        # rather than hard coding it as second column, we can use the column name i.e. Contig id
        contig_info_df['contig_id'] = abritamr_df['Contig id']
        
        # Read the contigs.tab file (no header)
        contigs_df = pd.read_csv(contigs_file, sep='\t', header=None)
        
        # Check if the number of rows match
        if len(abritamr_df) != len(contigs_df):
            print(f"WARNING: Number of rows doesn't match between files:")
            print(f"  - Collated abritamr file has {len(abritamr_df)} observations")
            print(f"  - Contigs file has {len(contigs_df)} rows")
            print("  - This may lead to incorrect mapping of contigs to samples")
            
        # Map sample IDs and contig paths
        sample_ids = []
        contig_paths = []
        
        for i in range(len(contig_info_df)):
            if i < len(contigs_df):
                sample_ids.append(contigs_df.iloc[i, 0])  # First column of contigs.tab
                contig_paths.append(contigs_df.iloc[i, 1])  # Second column of contigs.tab
            else:
                # Handle case where abritamr.tab has more rows than contigs.tab
                sample_ids.append(None)
                contig_paths.append(None)
                print(f"WARNING: No matching contig info for ABRIcate row {i+1}")
        
        # Add sample_id and contigs_path columns
        contig_info_df['sample_id'] = sample_ids
        contig_info_df['contigs_path'] = contig_paths
        
        # Write to a new file
        contig_info_df.to_csv(output_file, sep='\t', index=False)
        
        print(f"Successfully created {output_file}")
        print(f"Total rows processed: {len(contig_info_df)}")
        print(f"Rows with missing contig info: {contig_info_df['sample_id'].isna().sum()}")
        
        return True
        
    except Exception as e:
        print(f"Error processing files: {e}")
        return False

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Map contig IDs from ABRIcate AMR output to sample IDs and contig file paths.",
        epilog="""
Examples:
  python map_abritamr_contigs.py -a NDM-1_abritamr.tab -c contigs.tab -o NDM-1_abritamr_contig_info.tab
  python map_abritamr_contigs.py --abritamr KPC-2_abritamr.tab --contigs contigs.tab --output KPC-2_abritamr_contig_info.tab

Note:
  The script assumes that the first row in contigs.tab corresponds to the first observation 
  in the ABRIcate file, the second row to the second observation, and so on. This is critical
  for correct mapping of contig IDs to sample IDs.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-a', '--abritamr', required=True, 
                        help='Path to ABRIcate AMR output file (<gene_name>_abritamr.tab)')
    parser.add_argument('-c', '--contigs', required=True, 
                        help='Path to contigs.tab file (no header, sample_id and contig_path columns)')
    parser.add_argument('-o', '--output', 
                        help='Output file name (default: <gene_name>_abritamr_contig_info.tab)')
    
    args = parser.parse_args()
    
    # Set default output file if not provided
    if not args.output:
        gene_name = os.path.basename(args.abritamr).split("_abritamr")[0]
        args.output = f"{gene_name}_abritamr_contig_info.tab"
        print(f"No output file specified, using default: {args.output}")
    
    # Check if input files exist
    for file_path in [args.abritamr, args.contigs]:
        if not os.path.isfile(file_path):
            sys.exit(f"Error: Input file '{file_path}' does not exist.")
    
    # Process files
    success = map_abritamr_to_contigs(args.abritamr, args.contigs, args.output)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()